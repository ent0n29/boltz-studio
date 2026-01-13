"""Standalone Modal function for BoltzGen - kept separate from boltz_studio package."""

import modal

app = modal.App("boltzgen-standalone")

boltzgen_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("boltzgen>=0.2.0", "pyyaml", "gemmi")
    .env({"HF_HOME": "/cache/huggingface"})
)

model_cache = modal.Volume.from_name("boltzgen-cache", create_if_missing=True)


@app.function(
    image=boltzgen_image,
    gpu="A100",  # A100 is much faster than A10G
    timeout=1800,
    volumes={"/cache": model_cache},
)
def run_design(
    target_pdb: str,
    pdb_id: str | None = None,  # Optional: fetch directly from RCSB
    protocol: str = "nanobody-anything",
    num_designs: int = 100,
    binder_length_min: int = 80,
    binder_length_max: int = 140,
) -> dict:
    """Run BoltzGen on Modal GPU."""
    import subprocess
    import tempfile
    import json
    from pathlib import Path
    import urllib.request

    import yaml
    import gemmi

    work_dir = Path(tempfile.mkdtemp())
    print(f"Working directory: {work_dir}")

    # If PDB ID provided, download CIF directly from RCSB (most reliable)
    if pdb_id:
        print(f"Downloading CIF for {pdb_id} from RCSB...")
        url = f"https://files.rcsb.org/download/{pdb_id.upper()}.cif"
        target_path = work_dir / "target.cif"
        urllib.request.urlretrieve(url, str(target_path))
        print(f"Downloaded to {target_path}")

        # Parse CIF to get polymer chain IDs (label_asym_id for protein chains only)
        doc = gemmi.cif.read(str(target_path))
        block = doc.sole_block()

        # Get polymer entity IDs from _entity_poly table
        poly_entity_ids = set()
        entity_poly = block.find("_entity_poly.", ["entity_id"])
        if entity_poly:
            for row in entity_poly:
                poly_entity_ids.add(row[0])

        # Get label_asym_id for polymer entities only (from _struct_asym)
        target_chains = []
        struct_asym = block.find("_struct_asym.", ["id", "entity_id"])
        if struct_asym:
            for row in struct_asym:
                asym_id, entity_id = row[0], row[1]
                if entity_id in poly_entity_ids and asym_id not in target_chains:
                    target_chains.append(asym_id)

        # Fallback: get unique label_asym_id from ATOM records only
        if not target_chains:
            for row in block.find("_atom_site.", ["group_PDB", "label_asym_id"]):
                if row[0] == "ATOM" and row[1] not in target_chains:
                    target_chains.append(row[1])
    else:
        # Use provided structure content
        is_cif = target_pdb.strip().startswith('data_') or '_atom_site.' in target_pdb

        if is_cif:
            target_path = work_dir / "target.cif"
            target_path.write_text(target_pdb)
            doc = gemmi.cif.read_string(target_pdb)
            block = doc.sole_block()

            # Get label_asym_id values
            target_chains = []
            label_asym_col = block.find_values("_atom_site.label_asym_id")
            if label_asym_col:
                for val in label_asym_col:
                    if val not in target_chains:
                        target_chains.append(val)
        else:
            # Convert PDB to CIF using gemmi
            structure = gemmi.read_pdb_string(target_pdb)
            structure.setup_entities()
            target_path = work_dir / "target.cif"
            structure.make_mmcif_document().write_file(str(target_path))

            # For PDB->CIF conversion, chain names are used as label_asym_id
            target_chains = []
            for model in structure:
                for chain in model:
                    if chain.name not in target_chains and len(list(chain)) > 0:
                        target_chains.append(chain.name)

    print(f"Target chains (label_asym_id): {target_chains}")

    # Pick binder chain that doesn't conflict
    binder_chain = 'X'
    for c in 'XYZWVUTSRQPONMLKJIHGFEDCB':
        if c not in target_chains:
            binder_chain = c
            break

    print(f"Using binder chain: {binder_chain}")

    # Build BoltzGen YAML spec
    spec = {
        "entities": [
            # Designed protein chain (binder)
            {
                "protein": {
                    "id": binder_chain,
                    "sequence": f"{binder_length_min}..{binder_length_max}",
                }
            },
            # Target from structure file
            {
                "file": {
                    "path": target_path.name,
                    "include": [
                        {"chain": {"id": c}} for c in target_chains
                    ]
                }
            },
        ]
    }

    spec_path = work_dir / "spec.yaml"
    spec_path.write_text(yaml.dump(spec, default_flow_style=False))

    # Print spec for debugging
    print(f"YAML spec:\n{spec_path.read_text()}")

    output_dir = work_dir / "output"
    output_dir.mkdir()

    cmd = [
        "boltzgen", "run", str(spec_path),
        "--output", str(output_dir),
        "--protocol", protocol,
        "--num_designs", str(num_designs),
        "--budget", str(min(num_designs, 10)),
    ]
    print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(work_dir))

    # Enhanced logging
    print("=" * 60)
    print("BOLTZGEN OUTPUT:")
    print("=" * 60)
    print(f"Return code: {result.returncode}")
    print(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        print(f"STDERR:\n{result.stderr}")
    print("=" * 60)

    # List output directory contents for debugging
    print("Output directory contents:")
    for p in output_dir.rglob("*"):
        if p.is_file():
            print(f"  {p.relative_to(output_dir)} ({p.stat().st_size} bytes)")

    if result.returncode != 0:
        # Try to identify which step failed
        error_msg = result.stderr or result.stdout
        step = "unknown"
        if "design" in error_msg.lower():
            step = "design"
        elif "inverse_folding" in error_msg.lower() or "folding" in error_msg.lower():
            step = "inverse_folding"
        elif "filter" in error_msg.lower():
            step = "filtering"

        return {
            "success": False,
            "error": error_msg,
            "failed_step": step,
            "results": []
        }

    # Parse results - look for filtered or output PDB files
    results = []
    three_to_one = {
        'ALA': 'A', 'CYS': 'C', 'ASP': 'D', 'GLU': 'E', 'PHE': 'F',
        'GLY': 'G', 'HIS': 'H', 'ILE': 'I', 'LYS': 'K', 'LEU': 'L',
        'MET': 'M', 'ASN': 'N', 'PRO': 'P', 'GLN': 'Q', 'ARG': 'R',
        'SER': 'S', 'THR': 'T', 'VAL': 'V', 'TRP': 'W', 'TYR': 'Y',
    }

    # Look for final ranked designs (CIF format)
    final_designs_dir = output_dir / "final_ranked_designs" / "final_10_designs"
    if not final_designs_dir.exists():
        final_designs_dir = output_dir / "final_ranked_designs"
    if not final_designs_dir.exists():
        final_designs_dir = output_dir

    print(f"Looking for results in: {final_designs_dir}")

    # Load metrics CSV if available
    metrics_csv = output_dir / "final_ranked_designs" / "final_designs_metrics_10.csv"
    metrics_data = {}
    if metrics_csv.exists():
        print(f"Found metrics CSV: {metrics_csv}")
        import csv
        with open(metrics_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                design_id = row.get('design_id', row.get('id', ''))
                metrics_data[design_id] = row
                print(f"  Loaded metrics for: {design_id}")

    # Process CIF files (BoltzGen outputs CIF, not PDB)
    cif_files = sorted(final_designs_dir.glob("*.cif"))
    print(f"Found {len(cif_files)} CIF files")

    for cif_file in cif_files[:10]:
        cif_content = cif_file.read_text()

        # Parse CIF to extract sequence and B-factors for binder chain
        seq = []
        plddt_scores = []

        # Parse using gemmi for reliable CIF reading
        try:
            structure = gemmi.read_structure(str(cif_file))
            for model in structure:
                for chain in model:
                    if chain.name == binder_chain:
                        for residue in chain:
                            if residue.name in three_to_one:
                                seq.append(three_to_one[residue.name])
                                # Get B-factor from CA atom
                                ca = residue.find_atom("CA", "*")
                                if ca:
                                    plddt_scores.append(ca.b_iso)
        except Exception as e:
            print(f"Error parsing {cif_file}: {e}")
            continue

        if not seq:
            print(f"No sequence found in {cif_file.name}")
            continue

        # Calculate average pLDDT
        avg_plddt = sum(plddt_scores) / len(plddt_scores) if plddt_scores else 0.0

        # Try to get metrics from CSV
        design_id = cif_file.stem.replace('rank', '').split('_')[0] if 'rank' in cif_file.stem else cif_file.stem
        csv_metrics = metrics_data.get(design_id, metrics_data.get(cif_file.stem, {}))

        ptm_score = float(csv_metrics.get('ipTM', csv_metrics.get('ptm', 0.0)))
        affinity_score = float(csv_metrics.get('affinity', csv_metrics.get('binding_affinity', 0.0)))

        # Confidence from CSV or compute from pLDDT
        confidence = float(csv_metrics.get('confidence', avg_plddt / 100.0))

        # Convert CIF to PDB for frontend compatibility
        pdb_content = ""
        try:
            structure = gemmi.read_structure(str(cif_file))
            pdb_content = structure.make_pdb_string()
        except Exception as e:
            print(f"Could not convert to PDB: {e}")
            pdb_content = cif_content  # Fallback to CIF

        results.append({
            "rank": len(results) + 1,
            "sequence": ''.join(seq),
            "structure_pdb": pdb_content,
            "plddt_score": round(avg_plddt, 2),
            "ptm_score": round(ptm_score, 3),
            "affinity_score": round(affinity_score, 3),
            "confidence_score": round(confidence, 3),
        })

        print(f"Result {len(results)}: seq_len={len(seq)}, pLDDT={avg_plddt:.1f}, file={cif_file.name}")

    return {"success": True, "results": results, "total_generated": len(results)}


# For testing: modal run modal_boltzgen.py
@app.local_entrypoint()
def main():
    # Test with a real PDB structure (p53-MDM2, simple 2-chain complex)
    print("Testing BoltzGen with PDB 1YCR (p53-MDM2)...")
    result = run_design.remote(
        target_pdb="",  # Will be ignored since pdb_id is provided
        pdb_id="1YCR",
        num_designs=10,
        binder_length_min=80,
        binder_length_max=120,
    )

    print("\n" + "=" * 60)
    print("FINAL RESULT:")
    print("=" * 60)
    print(f"Success: {result.get('success')}")
    if result.get('error'):
        print(f"Error: {result.get('error')}")
        print(f"Failed step: {result.get('failed_step')}")
    else:
        print(f"Total generated: {result.get('total_generated')}")
        for r in result.get('results', [])[:3]:
            print(f"  Rank {r['rank']}: pLDDT={r['plddt_score']:.1f}, len={len(r['sequence'])}")

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
    from pathlib import Path
    import urllib.request

    import yaml
    import gemmi

    work_dir = Path(tempfile.mkdtemp())

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
    print(f"stdout: {result.stdout}")
    print(f"stderr: {result.stderr}")

    if result.returncode != 0:
        return {"success": False, "error": result.stderr or result.stdout, "results": []}

    # Parse results - look for filtered or output PDB files
    results = []
    three_to_one = {
        'ALA': 'A', 'CYS': 'C', 'ASP': 'D', 'GLU': 'E', 'PHE': 'F',
        'GLY': 'G', 'HIS': 'H', 'ILE': 'I', 'LYS': 'K', 'LEU': 'L',
        'MET': 'M', 'ASN': 'N', 'PRO': 'P', 'GLN': 'Q', 'ARG': 'R',
        'SER': 'S', 'THR': 'T', 'VAL': 'V', 'TRP': 'W', 'TYR': 'Y',
    }

    # Try filtered directory first, then output
    results_dir = output_dir / "filtered"
    if not results_dir.exists():
        results_dir = output_dir

    for pdb_file in sorted(results_dir.glob("**/*.pdb"))[:10]:
        pdb_content = pdb_file.read_text()

        # Extract sequence from designed binder chain
        seq = []
        seen = set()
        for line in pdb_content.split('\n'):
            if line.startswith('ATOM') and line[12:16].strip() == 'CA':
                chain = line[21]
                if chain == binder_chain:  # Only get designed chain
                    key = (chain, line[22:26].strip())
                    res = line[17:20].strip()
                    if key not in seen and res in three_to_one:
                        seen.add(key)
                        seq.append(three_to_one[res])

        results.append({
            "rank": len(results) + 1,
            "sequence": ''.join(seq),
            "structure_pdb": pdb_content,
            "plddt_score": 0.0,
            "ptm_score": 0.0,
            "affinity_score": 0.0,
            "confidence_score": 0.0,
        })

    return {"success": True, "results": results, "total_generated": len(results)}


# For testing: modal run modal_boltzgen.py
@app.local_entrypoint()
def main():
    test_pdb = """ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C
END"""
    result = run_design.remote(test_pdb, num_designs=10)
    print(result)

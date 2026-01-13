"""Modal.com integration for running BoltzGen on cloud GPUs."""

import subprocess
import sys
from pathlib import Path


def check_modal_configured() -> bool:
    """Check if Modal is configured with valid credentials."""
    try:
        modal_config = Path.home() / ".modal.toml"
        if modal_config.exists():
            content = modal_config.read_text()
            if "token_id" in content and "token_secret" in content:
                return True
        return False
    except Exception:
        return False


def submit_modal_job(
    target_pdb: str,
    protocol: str,
    num_designs: int,
    binder_length_min: int,
    binder_length_max: int,
    binding_site_residues: list[str] | None = None,
    pdb_id: str | None = None,
) -> dict:
    """Submit a BoltzGen job to Modal by running the standalone script."""
    import json
    import tempfile

    # Write target PDB to temp file (as fallback if pdb_id not provided)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdb', delete=False) as f:
        f.write(target_pdb)
        pdb_path = f.name

    # Path to standalone Modal script
    script_path = Path(__file__).parent.parent.parent / "modal_boltzgen.py"

    # Build the pdb_id parameter
    pdb_id_param = f'pdb_id="{pdb_id}",' if pdb_id else ""

    # Run Modal with the standalone script
    cmd = [
        sys.executable, "-c", f"""
import modal
import json

app = modal.App.lookup("boltzgen-standalone", create_if_missing=True)

# Import the function from the standalone file
import importlib.util
spec = importlib.util.spec_from_file_location("modal_boltzgen", "{script_path}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Run via app context
with mod.app.run():
    result = mod.run_design.remote(
        target_pdb=open("{pdb_path}").read(),
        {pdb_id_param}
        protocol="{protocol}",
        num_designs={num_designs},
        binder_length_min={binder_length_min},
        binder_length_max={binder_length_max},
    )
    print("MODAL_RESULT:" + json.dumps(result))
"""
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

    # Clean up
    Path(pdb_path).unlink(missing_ok=True)

    # Parse result
    for line in result.stdout.split('\n'):
        if line.startswith("MODAL_RESULT:"):
            return json.loads(line[13:])

    return {
        "success": False,
        "error": result.stderr or result.stdout or "Unknown error",
        "results": [],
    }


async def submit_modal_job_async(
    target_pdb: str,
    protocol: str,
    num_designs: int,
    binder_length_min: int,
    binder_length_max: int,
    binding_site_residues: list[str] | None = None,
    pdb_id: str | None = None,
) -> dict:
    """Async version of submit_modal_job."""
    import asyncio

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: submit_modal_job(
            target_pdb=target_pdb,
            protocol=protocol,
            num_designs=num_designs,
            binder_length_min=binder_length_min,
            binder_length_max=binder_length_max,
            binding_site_residues=binding_site_residues,
            pdb_id=pdb_id,
        )
    )
    return result

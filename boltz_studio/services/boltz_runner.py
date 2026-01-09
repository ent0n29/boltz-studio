"""Run Boltz predictions."""

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

from ..models import PredictionRequest
from .job_store import JobStore
from .output_parser import OutputParser


class BoltzRunner:
    """Execute Boltz CLI predictions."""

    def __init__(self, job_store: JobStore):
        self.job_store = job_store
        self.parser = OutputParser()

    @staticmethod
    def detect_accelerator() -> str:
        """Detect best available accelerator."""
        import torch

        if torch.backends.mps.is_available():
            return "gpu"  # PyTorch routes to MPS on Apple Silicon
        elif torch.cuda.is_available():
            return "gpu"
        return "cpu"

    @staticmethod
    def find_boltz_cmd() -> str:
        """Find boltz CLI executable."""
        cmd = shutil.which("boltz")
        if cmd:
            return cmd
        return str(Path(sys.executable).parent / "boltz")

    def generate_yaml(self, request: PredictionRequest, work_dir: Path) -> Path:
        """Generate YAML input file for Boltz CLI."""
        yaml_content = {"version": 1, "sequences": []}
        for seq in request.sequences:
            yaml_content["sequences"].append({
                seq.type: {"id": seq.id, "sequence": seq.sequence}
            })

        yaml_file = work_dir / f"{request.name}.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(yaml_content, f)

        return yaml_file

    async def run(self, job_id: str, request: PredictionRequest) -> None:
        """Run Boltz prediction asynchronously."""
        try:
            self.job_store.update(job_id, status="running", progress=0.1)

            # Create temp directory
            work_dir = Path(tempfile.mkdtemp(prefix=f"boltz_{job_id}_"))

            # Generate input
            yaml_file = self.generate_yaml(request, work_dir)
            self.job_store.update(job_id, progress=0.2)

            # Build command
            cmd = [
                self.find_boltz_cmd(),
                "predict",
                str(yaml_file),
                "--out_dir", str(work_dir / "output"),
                "--accelerator", self.detect_accelerator(),
                "--recycling_steps", str(request.recycling_steps),
                "--sampling_steps", str(request.sampling_steps),
                "--diffusion_samples", str(request.diffusion_samples),
                "--output_format", "pdb",
                "--use_msa_server",
            ]

            self.job_store.update(job_id, progress=0.3)

            # Execute
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(work_dir),
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(f"Boltz failed: {stderr.decode()[:500]}")

            self.job_store.update(job_id, progress=0.9)

            # Parse outputs
            output_dir = (
                work_dir / "output" / f"boltz_results_{request.name}"
                / "predictions" / request.name
            )

            result = {
                "structure_pdb": self.parser.parse_pdb(output_dir),
                "confidence": self.parser.parse_confidence(output_dir),
                "plddt_per_residue": self.parser.parse_plddt(output_dir),
            }

            self.job_store.update(
                job_id,
                status="completed",
                progress=1.0,
                result=result,
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.job_store.update(job_id, status="failed", error=str(e))

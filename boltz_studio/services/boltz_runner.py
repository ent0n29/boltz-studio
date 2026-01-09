"""Run Boltz predictions."""

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from ..logger import get_logger
from ..models import PredictionRequest
from .job_store import JobStore
from .output_parser import OutputParser

logger = get_logger("boltz_runner")


class BoltzRunner:
    """Execute Boltz CLI predictions."""

    def __init__(self, job_store: JobStore) -> None:
        """Initialize runner with job store.

        Args:
            job_store: JobStore instance for updating job status
        """
        self.job_store = job_store
        self.parser = OutputParser()

    @staticmethod
    def detect_accelerator() -> str:
        """Detect best available accelerator.

        Returns:
            Accelerator string: 'gpu' or 'cpu'
        """
        import torch

        if torch.backends.mps.is_available():
            logger.info("Using MPS (Apple Silicon GPU)")
            return "gpu"  # PyTorch routes to MPS on Apple Silicon
        elif torch.cuda.is_available():
            logger.info("Using CUDA GPU")
            return "gpu"
        logger.info("Using CPU")
        return "cpu"

    @staticmethod
    def find_boltz_cmd() -> str:
        """Find boltz CLI executable.

        Returns:
            Path to boltz command
        """
        cmd = shutil.which("boltz")
        if cmd:
            return cmd
        return str(Path(sys.executable).parent / "boltz")

    def generate_yaml(self, request: PredictionRequest, work_dir: Path) -> Path:
        """Generate YAML input file for Boltz CLI.

        Args:
            request: Prediction request
            work_dir: Working directory for output

        Returns:
            Path to generated YAML file
        """
        yaml_content: dict[str, Any] = {"version": 1, "sequences": []}
        for seq in request.sequences:
            yaml_content["sequences"].append({
                seq.type: {"id": seq.id, "sequence": seq.sequence}
            })

        yaml_file = work_dir / f"{request.name}.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(yaml_content, f)

        logger.debug(f"Generated input YAML: {yaml_file}")
        return yaml_file

    async def run(self, job_id: str, request: PredictionRequest) -> None:
        """Run Boltz prediction asynchronously.

        Args:
            job_id: Job identifier
            request: Prediction request
        """
        try:
            logger.info(f"Starting prediction for job {job_id}")
            self.job_store.update(job_id, status="running", progress=0.1)

            # Create temp directory
            work_dir = Path(tempfile.mkdtemp(prefix=f"boltz_{job_id}_"))
            logger.debug(f"Work directory: {work_dir}")

            # Generate input
            yaml_file = self.generate_yaml(request, work_dir)
            self.job_store.update(job_id, progress=0.2)

            # Build command
            accelerator = self.detect_accelerator()
            cmd = [
                self.find_boltz_cmd(),
                "predict",
                str(yaml_file),
                "--out_dir", str(work_dir / "output"),
                "--accelerator", accelerator,
                "--recycling_steps", str(request.recycling_steps),
                "--sampling_steps", str(request.sampling_steps),
                "--diffusion_samples", str(request.diffusion_samples),
                "--output_format", "pdb",
                "--use_msa_server",
            ]

            logger.info(f"Executing: {' '.join(cmd[:3])}...")
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
                error_msg = stderr.decode()[:500]
                logger.error(f"Boltz failed for job {job_id}: {error_msg}")
                raise Exception(f"Boltz failed: {error_msg}")

            self.job_store.update(job_id, progress=0.9)

            # Parse outputs
            output_dir = (
                work_dir / "output" / f"boltz_results_{request.name}"
                / "predictions" / request.name
            )

            result: dict[str, Any] = {
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
            logger.info(f"Prediction completed for job {job_id}")

        except Exception as e:
            logger.exception(f"Prediction failed for job {job_id}")
            self.job_store.update(job_id, status="failed", error=str(e))

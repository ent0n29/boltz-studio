"""Run Boltz predictions."""

import asyncio
import pickle
import shutil
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any

import yaml

from ..logger import get_logger
from ..models import PredictionRequest
from .job_store import JobStore
from .model_manager import get_model_manager
from .output_parser import OutputParser
from .progress_manager import get_progress_manager

logger = get_logger("boltz_runner")


class BoltzRunner:
    """Execute Boltz predictions via direct API or CLI."""

    def __init__(self, job_store: JobStore) -> None:
        """Initialize runner with job store.

        Args:
            job_store: JobStore instance for updating job status
        """
        self.job_store = job_store
        self.parser = OutputParser()
        self.progress_manager = get_progress_manager()
        self.model_manager = get_model_manager()

    async def _update_and_broadcast(self, job_id: str, **kwargs: Any) -> None:
        """Update job in store and broadcast to WebSocket subscribers.

        Args:
            job_id: Job identifier
            **kwargs: Fields to update
        """
        self.job_store.update(job_id, **kwargs)
        job = self.job_store.get(job_id)
        if job:
            await self.progress_manager.broadcast(job_id, job)

    @staticmethod
    def detect_accelerator() -> str:
        """Detect best available accelerator for CLI mode.

        Returns:
            Accelerator string: 'gpu' or 'cpu'
        """
        try:
            import torch

            if torch.backends.mps.is_available():
                logger.info("Using MPS (Apple Silicon GPU)")
                return "gpu"
            elif torch.cuda.is_available():
                logger.info("Using CUDA GPU")
                return "gpu"
        except ImportError:
            logger.warning("torch not available, defaulting to CPU")
        logger.info("Using CPU")
        return "cpu"

    @staticmethod
    def find_boltz_cmd() -> str | None:
        """Find boltz CLI executable.

        Returns:
            Path to boltz command, or None if not found
        """
        cmd = shutil.which("boltz")
        if cmd:
            return cmd
        venv_boltz = Path(sys.executable).parent / "boltz"
        if venv_boltz.exists():
            return str(venv_boltz)
        return None

    def generate_yaml(self, request: PredictionRequest, work_dir: Path) -> Path:
        """Generate YAML input file for Boltz.

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
        """Run Boltz prediction, using direct API if available.

        Args:
            job_id: Job identifier
            request: Prediction request
        """
        if self.model_manager.is_direct_api_available:
            await self._run_direct(job_id, request)
        else:
            await self._run_cli(job_id, request)

    async def _run_direct(self, job_id: str, request: PredictionRequest) -> None:
        """Run prediction using direct Boltz Python API.

        This properly integrates with Boltz's data pipeline.

        Args:
            job_id: Job identifier
            request: Prediction request
        """
        try:
            logger.info(f"Starting prediction (direct API) for job {job_id}")
            await self._update_and_broadcast(job_id, status="running", progress=0.05)

            # Get event loop for progress updates from sync thread
            loop = asyncio.get_event_loop()

            # Progress callback for sync function
            def update_progress(progress: float) -> None:
                asyncio.run_coroutine_threadsafe(
                    self._update_and_broadcast(job_id, progress=progress),
                    loop
                )

            # Run in thread pool to not block event loop
            result = await loop.run_in_executor(
                None,
                self._predict_direct_sync,
                request,
                job_id,
                update_progress,
            )

            await self._update_and_broadcast(
                job_id,
                status="completed",
                progress=1.0,
                result=result,
            )
            logger.info(f"Prediction (direct API) completed for job {job_id}")

        except Exception as e:
            logger.exception(f"Prediction (direct API) failed for job {job_id}")
            await self._update_and_broadcast(job_id, status="failed", error=str(e))

    def _predict_direct_sync(
        self,
        request: PredictionRequest,
        job_id: str,
        update_progress: callable,
    ) -> dict[str, Any]:
        """Synchronous prediction using Boltz's internal API.

        Args:
            request: Prediction request
            job_id: Job identifier
            update_progress: Callback to update progress (0.0 to 1.0)

        Returns:
            Prediction result dictionary
        """
        import torch
        from pytorch_lightning import Trainer
        from rdkit import Chem

        from boltz.data.module.inferencev2 import Boltz2InferenceDataModule
        from boltz.data.mol import load_canonicals
        from boltz.data.parse.yaml import parse_yaml
        from boltz.data.types import MSA, Manifest
        from boltz.data.write.writer import BoltzWriter
        from boltz.data import const

        # Suppress warnings
        warnings.filterwarnings(
            "ignore", ".*that has Tensor Cores.*"
        )

        # Set torch settings
        torch.set_grad_enabled(False)
        torch.set_float32_matmul_precision("highest")
        Chem.SetDefaultPickleProperties(Chem.PropertyPickleOptions.AllProps)

        # Get cache and create work directory
        update_progress(0.10)  # 10% - Starting
        cache = self.model_manager.get_cache_path()
        work_dir = Path(tempfile.mkdtemp(prefix=f"boltz_{job_id}_"))
        out_dir = work_dir / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Work directory: {work_dir}")

        # Generate YAML input
        yaml_file = self.generate_yaml(request, work_dir)

        # Load CCD data
        mol_dir = cache / "mols"
        ccd = load_canonicals(mol_dir)

        # Parse YAML to get target
        target = parse_yaml(yaml_file, ccd, mol_dir, boltz2=True)
        target_id = target.record.id

        # Create output directories
        msa_dir = out_dir / "msa"
        records_dir = out_dir / "processed" / "records"
        structure_dir = out_dir / "processed" / "structures"
        processed_msa_dir = out_dir / "processed" / "msa"
        processed_constraints_dir = out_dir / "processed" / "constraints"
        processed_templates_dir = out_dir / "processed" / "templates"
        processed_mols_dir = out_dir / "processed" / "mols"
        predictions_dir = out_dir / "predictions"

        for d in [
            msa_dir, records_dir, structure_dir, processed_msa_dir,
            processed_constraints_dir, processed_templates_dir,
            processed_mols_dir, predictions_dir
        ]:
            d.mkdir(parents=True, exist_ok=True)

        # Handle MSA generation
        prot_id = const.chain_type_ids["PROTEIN"]
        to_generate = {}
        for chain in target.record.chains:
            if (chain.mol_type == prot_id) and (chain.msa_id == 0):
                entity_id = chain.entity_id
                msa_id = f"{target_id}_{entity_id}"
                to_generate[msa_id] = target.sequences[entity_id]
                chain.msa_id = msa_dir / f"{msa_id}.csv"
            elif chain.msa_id == 0:
                chain.msa_id = -1

        # Generate MSA using server
        if to_generate:
            update_progress(0.20)  # 20% - Starting MSA generation
            logger.info(f"Generating MSA for {len(to_generate)} protein entities")
            self._compute_msa(
                data=to_generate,
                target_id=target_id,
                msa_dir=msa_dir,
            )
            update_progress(0.45)  # 45% - MSA complete

        # Process MSA data
        msas = sorted({c.msa_id for c in target.record.chains if c.msa_id != -1})
        msa_id_map = {}
        for msa_idx, msa_id in enumerate(msas):
            msa_path = Path(msa_id)
            if not msa_path.exists():
                raise FileNotFoundError(f"MSA file {msa_path} not found")

            processed = processed_msa_dir / f"{target_id}_{msa_idx}.npz"
            msa_id_map[msa_id] = f"{target_id}_{msa_idx}"

            if not processed.exists():
                from boltz.data.parse.csv import parse_csv
                msa: MSA = parse_csv(msa_path, max_seqs=8192)
                msa.dump(processed)

        # Update chain MSA references
        for c in target.record.chains:
            if (c.msa_id != -1) and (c.msa_id in msa_id_map):
                c.msa_id = msa_id_map[c.msa_id]

        # Dump templates
        for template_id, template in target.templates.items():
            name = f"{target.record.id}_{template_id}.npz"
            template_path = processed_templates_dir / name
            template.dump(template_path)

        # Dump constraints
        constraints_path = processed_constraints_dir / f"{target.record.id}.npz"
        target.residue_constraints.dump(constraints_path)

        # Dump extra molecules
        with (processed_mols_dir / f"{target.record.id}.pkl").open("wb") as f:
            pickle.dump(target.extra_mols, f)

        # Dump structure
        struct_path = structure_dir / f"{target.record.id}.npz"
        target.structure.dump(struct_path)

        # Dump record
        record_path = records_dir / f"{target.record.id}.json"
        target.record.dump(record_path)

        # Create manifest
        manifest = Manifest([target.record])
        manifest.dump(out_dir / "processed" / "manifest.json")

        update_progress(0.55)  # 55% - Data preprocessing complete
        logger.info("Data preprocessing complete, running prediction...")

        # Create data module
        data_module = Boltz2InferenceDataModule(
            manifest=manifest,
            target_dir=structure_dir,
            msa_dir=processed_msa_dir,
            mol_dir=mol_dir,
            num_workers=0,  # Use 0 for sync operation
            constraints_dir=processed_constraints_dir,
            template_dir=processed_templates_dir,
            extra_mols_dir=processed_mols_dir,
            override_method=None,
        )

        # Get cached model
        update_progress(0.65)  # 65% - Loading model
        model = self.model_manager.get_model()
        update_progress(0.75)  # 75% - Model ready

        # Create prediction writer
        pred_writer = BoltzWriter(
            data_dir=structure_dir,
            output_dir=predictions_dir,
            output_format="pdb",
            boltz2=True,
            write_embeddings=False,
        )

        # Create trainer
        accelerator = self.model_manager._get_accelerator()
        trainer = Trainer(
            default_root_dir=out_dir,
            strategy="auto",
            callbacks=[pred_writer],
            accelerator=accelerator,
            devices=1,
            precision="bf16-mixed",
            logger=False,
            enable_progress_bar=False,
        )

        # Run prediction
        update_progress(0.80)  # 80% - Running prediction
        trainer.predict(
            model,
            datamodule=data_module,
            return_predictions=False,
        )
        update_progress(0.95)  # 95% - Prediction complete

        logger.info("Prediction complete, parsing outputs...")

        # Parse outputs
        output_dir = predictions_dir / request.name
        return {
            "structure_pdb": self.parser.parse_pdb(output_dir),
            "confidence": self.parser.parse_confidence(output_dir),
            "plddt_per_residue": self.parser.parse_plddt(output_dir),
        }

    def _compute_msa(
        self,
        data: dict[str, str],
        target_id: str,
        msa_dir: Path,
    ) -> None:
        """Compute MSA using MMseqs2 server.

        Args:
            data: Dictionary of sequence ID to sequence
            target_id: Target identifier
            msa_dir: Directory to save MSA files
        """
        from boltz.data.msa.mmseqs2 import run_mmseqs2
        from boltz.data import const

        msa_server_url = "https://api.colabfold.com"
        msa_pairing_strategy = "greedy"

        logger.info(f"Calling MSA server for {len(data)} sequences")

        if len(data) > 1:
            paired_msas = run_mmseqs2(
                list(data.values()),
                msa_dir / f"{target_id}_paired_tmp",
                use_env=True,
                use_pairing=True,
                host_url=msa_server_url,
                pairing_strategy=msa_pairing_strategy,
            )
        else:
            paired_msas = [""] * len(data)

        unpaired_msa = run_mmseqs2(
            list(data.values()),
            msa_dir / f"{target_id}_unpaired_tmp",
            use_env=True,
            use_pairing=False,
            host_url=msa_server_url,
            pairing_strategy=msa_pairing_strategy,
        )

        for idx, name in enumerate(data):
            # Get paired sequences
            paired = paired_msas[idx].strip().splitlines()
            paired = paired[1::2]  # ignore headers
            paired = paired[: const.max_paired_seqs]

            # Set key per row and remove empty sequences
            keys = [idx for idx, s in enumerate(paired) if s != "-" * len(s)]
            paired = [s for s in paired if s != "-" * len(s)]

            # Combine paired-unpaired sequences
            unpaired = unpaired_msa[idx].strip().splitlines()
            unpaired = unpaired[1::2]
            unpaired = unpaired[: (const.max_msa_seqs - len(paired))]
            if paired:
                unpaired = unpaired[1:]  # ignore query if already present

            # Combine
            seqs = paired + unpaired
            keys = keys + [-1] * len(unpaired)

            # Dump MSA
            csv_str = ["key,sequence"] + [f"{key},{seq}" for key, seq in zip(keys, seqs)]

            msa_path = msa_dir / f"{name}.csv"
            with msa_path.open("w") as f:
                f.write("\n".join(csv_str))

        logger.info("MSA generation complete")

    async def _run_cli(self, job_id: str, request: PredictionRequest) -> None:
        """Run prediction using Boltz CLI (fallback mode).

        Args:
            job_id: Job identifier
            request: Prediction request
        """
        try:
            logger.info(f"Starting prediction (CLI) for job {job_id}")
            await self._update_and_broadcast(job_id, status="running", progress=0.1)

            # Create temp directory
            work_dir = Path(tempfile.mkdtemp(prefix=f"boltz_{job_id}_"))
            logger.debug(f"Work directory: {work_dir}")

            # Generate input
            yaml_file = self.generate_yaml(request, work_dir)
            await self._update_and_broadcast(job_id, progress=0.2)

            # Build command
            boltz_cmd = self.find_boltz_cmd()
            if boltz_cmd is None:
                raise RuntimeError(
                    "Boltz not installed. Install with: pip install boltz"
                )

            accelerator = self.detect_accelerator()
            cmd = [
                boltz_cmd,
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
            await self._update_and_broadcast(job_id, progress=0.3)

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
                logger.error(f"Boltz CLI failed for job {job_id}: {error_msg}")
                raise Exception(f"Boltz failed: {error_msg}")

            await self._update_and_broadcast(job_id, progress=0.9)

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

            await self._update_and_broadcast(
                job_id,
                status="completed",
                progress=1.0,
                result=result,
            )
            logger.info(f"Prediction (CLI) completed for job {job_id}")

        except Exception as e:
            logger.exception(f"Prediction (CLI) failed for job {job_id}")
            await self._update_and_broadcast(job_id, status="failed", error=str(e))

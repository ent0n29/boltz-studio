"""BoltzGen runner service for binder design.

This service manages the execution of BoltzGen design jobs, including:
- YAML spec generation from user input
- Subprocess execution of boltzgen CLI
- Progress monitoring
- Result parsing
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..config import settings
from ..logger import get_logger
from ..models.binder_design import (
    DesignJobCreate,
    DesignJobStatus,
    DesignProgress,
    DesignProtocol,
)
from .database import get_connection

logger = get_logger("boltzgen_runner")

# BoltzGen output directory
BOLTZGEN_WORKDIR = Path(settings.data_dir) / "boltzgen_jobs"
BOLTZGEN_WORKDIR.mkdir(parents=True, exist_ok=True)


def check_boltzgen_available() -> bool:
    """Check if boltzgen CLI is available."""
    return shutil.which("boltzgen") is not None


def check_modal_available() -> bool:
    """Check if Modal is configured with valid credentials."""
    try:
        from .modal_runner import check_modal_configured
        return check_modal_configured()
    except Exception:
        return False


class BoltzGenRunner:
    """Service for running BoltzGen design jobs."""

    def __init__(self):
        self._running_jobs: dict[str, asyncio.Task] = {}
        self._progress_callbacks: dict[str, list] = {}
        self._boltzgen_available = check_boltzgen_available()
        self._modal_available = check_modal_available()

        if self._boltzgen_available:
            logger.info("BoltzGen CLI available - using local GPU")
        elif self._modal_available:
            logger.info("Modal configured - using cloud GPU for BoltzGen")
        else:
            logger.warning("BoltzGen not available locally, Modal not configured. Jobs will run in simulation mode.")

    async def submit_job(self, user_id: str, job_data: DesignJobCreate) -> str:
        """Submit a new design job.

        Args:
            user_id: User submitting the job
            job_data: Job configuration

        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        output_dir = BOLTZGEN_WORKDIR / job_id

        # Get target structure
        target_pdb = await self._get_target_pdb(job_data)

        # Generate YAML spec
        spec_yaml = self._generate_yaml_spec(job_data, target_pdb)

        # Create job in database
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO design_jobs (
                    id, user_id, name, target_id, custom_target_pdb,
                    protocol, status, num_designs,
                    binder_length_min, binder_length_max,
                    binding_site_residues, constraints, spec_yaml, output_dir
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    user_id,
                    job_data.name,
                    job_data.target_id,
                    job_data.custom_target_pdb[:1000] if job_data.custom_target_pdb else None,
                    job_data.protocol,
                    "queued",
                    job_data.num_designs,
                    job_data.binder_length_min,
                    job_data.binder_length_max,
                    json.dumps(job_data.binding_site.model_dump()) if job_data.binding_site else None,
                    json.dumps(job_data.constraints.model_dump()) if job_data.constraints else None,
                    spec_yaml,
                    str(output_dir),
                ),
            )

        logger.info(f"Created design job {job_id} for user {user_id}")

        # Start job in background
        task = asyncio.create_task(self._run_job(job_id, spec_yaml, output_dir, job_data))
        self._running_jobs[job_id] = task

        return job_id

    async def _get_target_pdb(self, job_data: DesignJobCreate) -> str:
        """Get target PDB content from target_id or custom_target_pdb."""
        if job_data.custom_target_pdb:
            return job_data.custom_target_pdb

        if job_data.target_id:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT structure_pdb, pdb_id FROM design_targets WHERE id = ?",
                    (job_data.target_id,),
                ).fetchone()

                if row and row["structure_pdb"]:
                    return row["structure_pdb"]

                # If no structure stored, fetch from PDB
                if row and row["pdb_id"]:
                    return await self._fetch_pdb(row["pdb_id"])

        raise ValueError("No target structure available")

    async def _fetch_pdb(self, pdb_id: str) -> str:
        """Fetch PDB structure from RCSB."""
        import httpx

        # Use PDB format - simpler and more compatible with BoltzGen
        url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _generate_yaml_spec(
        self, job_data: DesignJobCreate, target_pdb: str
    ) -> str:
        """Generate BoltzGen YAML specification from job data."""
        # Build the spec based on protocol
        spec: dict[str, Any] = {"entities": []}

        # Add designed entity (binder)
        binder_entity = self._get_binder_entity(job_data)
        spec["entities"].append(binder_entity)

        # Add target entity
        target_entity = self._get_target_entity(job_data)
        spec["entities"].append(target_entity)

        # Add constraints if any
        if job_data.constraints:
            constraints = self._get_constraints(job_data)
            if constraints:
                spec["constraints"] = constraints

        return yaml.dump(spec, default_flow_style=False)

    def _get_binder_entity(self, job_data: DesignJobCreate) -> dict:
        """Get binder entity specification based on protocol."""
        length_spec = f"{job_data.binder_length_min}..{job_data.binder_length_max}"

        if job_data.protocol == "nanobody-anything":
            return {
                "protein": {
                    "id": "A",
                    "sequence": length_spec,
                    "type": "nanobody",
                }
            }
        elif job_data.protocol == "antibody-anything":
            return {
                "protein": {
                    "id": "A",
                    "sequence": length_spec,
                    "type": "antibody",
                }
            }
        elif job_data.protocol == "peptide-anything":
            return {
                "protein": {
                    "id": "A",
                    "sequence": length_spec,
                    "cyclic": job_data.constraints.cyclic if job_data.constraints else False,
                }
            }
        else:  # protein-anything, protein-small_molecule
            return {
                "protein": {
                    "id": "A",
                    "sequence": length_spec,
                }
            }

    def _get_target_entity(self, job_data: DesignJobCreate) -> dict:
        """Get target entity specification."""
        entity: dict[str, Any] = {
            "file": {
                "path": "target.pdb",  # Will be written to job directory
                "include": [],
            }
        }

        # Add binding site specification
        if job_data.binding_site:
            chain_spec: dict[str, Any] = {"chain": {"id": job_data.binding_site.chain_id}}

            if job_data.binding_site.residues:
                # Format residues as comma-separated list
                residue_str = ",".join(str(r) for r in job_data.binding_site.residues)
                chain_spec["chain"]["binding"] = residue_str

            entity["file"]["include"].append(chain_spec)
        else:
            # Include all chains as binding target
            entity["file"]["include"].append({"chain": {"id": "B", "binding": "all"}})

        return entity

    def _get_constraints(self, job_data: DesignJobCreate) -> list[dict]:
        """Get constraint specifications."""
        constraints = []

        if job_data.constraints:
            if job_data.constraints.disulfide_bonds:
                constraints.append({"type": "disulfide"})

            if job_data.constraints.secondary_structure:
                constraints.append({
                    "type": "secondary_structure",
                    "value": job_data.constraints.secondary_structure,
                })

        return constraints

    async def _run_job(
        self,
        job_id: str,
        spec_yaml: str,
        output_dir: Path,
        job_data: DesignJobCreate,
    ) -> None:
        """Run the BoltzGen pipeline for a job."""
        try:
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)

            # Write spec file
            spec_path = output_dir / "design_spec.yaml"
            spec_path.write_text(spec_yaml)

            # Write target PDB
            target_pdb = await self._get_target_pdb(job_data)
            target_path = output_dir / "target.pdb"
            target_path.write_text(target_pdb)

            # Update status
            await self._update_job_status(job_id, "generating", 0.1, "Starting design generation")

            # Check if boltzgen is available locally or via Modal
            if not self._boltzgen_available:
                if self._modal_available:
                    logger.info(f"Running job {job_id} via Modal cloud GPU")
                    await self._run_modal(job_id, target_pdb, job_data)
                    return
                else:
                    logger.info(f"Running job {job_id} in simulation mode (no GPU available)")
                    await self._run_simulation(job_id, output_dir, job_data)
                    return

            # Run BoltzGen
            cmd = [
                "boltzgen",
                "run",
                str(spec_path),
                "--output", str(output_dir),
                "--protocol", job_data.protocol,
                "--num_designs", str(job_data.num_designs),
                "--budget", str(min(job_data.num_designs, 10)),
            ]

            logger.info(f"Running BoltzGen: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(output_dir),
            )

            # Monitor progress
            await self._monitor_progress(job_id, process, output_dir)

            # Wait for completion
            return_code = await process.wait()

            if return_code != 0:
                raise RuntimeError(f"BoltzGen exited with code {return_code}")

            # Parse results
            await self._parse_results(job_id, output_dir)

            # Update final status
            await self._update_job_status(job_id, "completed", 1.0, "Design complete")

            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            await self._update_job_status(job_id, "failed", 0.0, str(e))
            raise

        finally:
            # Clean up running task reference
            self._running_jobs.pop(job_id, None)

    async def _run_simulation(
        self,
        job_id: str,
        output_dir: Path,
        job_data: DesignJobCreate,
    ) -> None:
        """Run a simulation of the design pipeline for development/testing."""
        import random

        # Simulate progress through stages
        stages = [
            ("generating", 0.2, "Generating binder sequences..."),
            ("folding", 0.5, "Folding structures..."),
            ("analyzing", 0.7, "Analyzing binding affinity..."),
            ("filtering", 0.9, "Filtering top designs..."),
        ]

        for status, progress, message in stages:
            await self._update_job_status(job_id, status, progress, message)
            await asyncio.sleep(1.5)  # Simulate work

        # Generate 5 mock results
        num_results = min(5, job_data.num_designs)
        mock_sequence_base = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSDSWIHWVRQAPGKGLEWVAWISPYGGSTYYADSVKGRFTISRDNSK"

        with get_connection() as conn:
            for rank in range(1, num_results + 1):
                result_id = str(uuid.uuid4())
                # Generate slightly varied sequences
                seq = mock_sequence_base + f"{'A' * (rank + job_data.binder_length_min - len(mock_sequence_base))}"
                plddt = round(85 + random.uniform(-10, 10), 1)
                ptm = round(0.8 + random.uniform(-0.1, 0.15), 2)
                affinity = round(-8 + random.uniform(-4, 2), 1)
                confidence = round(0.75 + random.uniform(-0.15, 0.2), 2)

                conn.execute(
                    """
                    INSERT INTO design_results (
                        id, job_id, rank, sequence, plddt_score, ptm_score,
                        affinity_score, confidence_score, is_published
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (result_id, job_id, rank, seq, plddt, ptm, affinity, confidence)
                )

            # Update job with result count
            conn.execute(
                "UPDATE design_jobs SET total_passed = ? WHERE id = ?",
                (num_results, job_id)
            )

        # Mark as completed
        await self._update_job_status(job_id, "completed", 1.0, "Design complete (simulation)")
        logger.info(f"Job {job_id} completed (simulation mode)")

    async def _run_modal(
        self,
        job_id: str,
        target_pdb: str,
        job_data: DesignJobCreate,
    ) -> None:
        """Run BoltzGen via Modal cloud GPU."""
        from .modal_runner import submit_modal_job_async

        # Update status
        await self._update_job_status(job_id, "generating", 0.2, "Submitting to cloud GPU...")

        # Parse binding site residues if provided
        binding_site = None
        if job_data.binding_site:
            binding_site = job_data.binding_site.residues

        # Get PDB ID if available (for direct download on Modal)
        pdb_id = None
        if job_data.target_id:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT pdb_id FROM design_targets WHERE id = ?",
                    (job_data.target_id,),
                ).fetchone()
                if row:
                    pdb_id = row["pdb_id"]

        # Submit to Modal
        await self._update_job_status(job_id, "folding", 0.4, "Running BoltzGen on cloud GPU...")

        result = await submit_modal_job_async(
            target_pdb=target_pdb,
            protocol=job_data.protocol,
            num_designs=min(job_data.num_designs, 100),  # Limit for cost control
            binder_length_min=job_data.binder_length_min,
            binder_length_max=job_data.binder_length_max,
            binding_site_residues=binding_site,
            pdb_id=pdb_id,  # Let Modal download directly from RCSB
        )

        if not result.get("success"):
            raise RuntimeError(f"Modal job failed: {result.get('error', 'Unknown error')}")

        await self._update_job_status(job_id, "analyzing", 0.8, "Processing results...")

        # Store results in database
        with get_connection() as conn:
            for r in result.get("results", []):
                result_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO design_results (
                        id, job_id, rank, sequence, structure_pdb,
                        plddt_score, ptm_score, affinity_score, confidence_score,
                        is_published
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        result_id, job_id, r["rank"], r["sequence"],
                        r.get("structure_pdb"), r.get("plddt_score", 0),
                        r.get("ptm_score", 0), r.get("affinity_score", 0),
                        r.get("confidence_score", 0),
                    )
                )

            # Update job with result count
            conn.execute(
                "UPDATE design_jobs SET total_passed = ? WHERE id = ?",
                (len(result.get("results", [])), job_id)
            )

        # Mark as completed
        await self._update_job_status(job_id, "completed", 1.0, "Design complete (Modal cloud GPU)")
        logger.info(f"Job {job_id} completed via Modal with {len(result.get('results', []))} results")

    async def _monitor_progress(
        self,
        job_id: str,
        process: asyncio.subprocess.Process,
        output_dir: Path,
    ) -> None:
        """Monitor job progress from process output."""
        step_progress = {
            "design": 0.2,
            "inverse_folding": 0.4,
            "folding": 0.6,
            "affinity": 0.7,
            "analysis": 0.8,
            "filtering": 0.9,
        }

        assert process.stdout is not None

        async for line in process.stdout:
            text = line.decode().strip()
            logger.debug(f"[{job_id}] {text}")

            # Parse progress from BoltzGen output
            for step, progress in step_progress.items():
                if step.lower() in text.lower():
                    await self._update_job_status(
                        job_id,
                        step if step != "inverse_folding" else "generating",
                        progress,
                        f"Running {step}...",
                    )
                    break

    async def _update_job_status(
        self,
        job_id: str,
        status: str,
        progress: float,
        message: str | None = None,
    ) -> None:
        """Update job status in database and notify subscribers."""
        with get_connection() as conn:
            updates = ["status = ?", "progress = ?", "current_step = ?"]
            values = [status, progress, message]

            if status == "generating":
                updates.append("started_at = CURRENT_TIMESTAMP")

            if status in ("completed", "failed"):
                updates.append("completed_at = CURRENT_TIMESTAMP")

            values.append(job_id)

            conn.execute(
                f"UPDATE design_jobs SET {', '.join(updates)} WHERE id = ?",
                values,
            )

        # Notify progress callbacks
        for callback in self._progress_callbacks.get(job_id, []):
            try:
                await callback(DesignProgress(
                    job_id=job_id,
                    status=status,
                    progress=progress,
                    message=message,
                ))
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    async def _parse_results(self, job_id: str, output_dir: Path) -> None:
        """Parse BoltzGen results and store in database."""
        # Look for result files
        results_dir = output_dir / "filtered"
        if not results_dir.exists():
            results_dir = output_dir / "results"

        if not results_dir.exists():
            logger.warning(f"No results directory found for job {job_id}")
            return

        # Parse ranked designs
        designs = []
        for pdb_file in sorted(results_dir.glob("*.pdb")):
            try:
                rank = int(pdb_file.stem.split("_")[-1]) if "_" in pdb_file.stem else len(designs) + 1
                structure = pdb_file.read_text()

                # Extract sequence from PDB
                sequence = self._extract_sequence_from_pdb(structure)

                # Look for metrics file
                metrics_file = pdb_file.with_suffix(".json")
                metrics = {}
                if metrics_file.exists():
                    metrics = json.loads(metrics_file.read_text())

                designs.append({
                    "rank": rank,
                    "sequence": sequence,
                    "structure_pdb": structure,
                    "plddt_score": metrics.get("plddt"),
                    "ptm_score": metrics.get("ptm"),
                    "affinity_score": metrics.get("affinity"),
                    "confidence_score": metrics.get("confidence"),
                    "metrics": metrics,
                })
            except Exception as e:
                logger.warning(f"Failed to parse result {pdb_file}: {e}")

        # Store results in database
        with get_connection() as conn:
            for design in designs:
                result_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO design_results (
                        id, job_id, rank, sequence, structure_pdb,
                        plddt_score, ptm_score, affinity_score, confidence_score, metrics
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_id,
                        job_id,
                        design["rank"],
                        design["sequence"],
                        design["structure_pdb"],
                        design.get("plddt_score"),
                        design.get("ptm_score"),
                        design.get("affinity_score"),
                        design.get("confidence_score"),
                        json.dumps(design.get("metrics", {})),
                    ),
                )

            # Update job with result counts
            conn.execute(
                """
                UPDATE design_jobs
                SET total_generated = ?, total_passed = ?
                WHERE id = ?
                """,
                (len(designs), len(designs), job_id),
            )

        logger.info(f"Stored {len(designs)} results for job {job_id}")

    def _extract_sequence_from_pdb(self, pdb_content: str) -> str:
        """Extract amino acid sequence from PDB file."""
        from Bio.PDB import PDBParser
        from Bio.SeqUtils import seq1
        import io

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("design", io.StringIO(pdb_content))

        sequences = []
        for model in structure:
            for chain in model:
                seq = ""
                for residue in chain:
                    if residue.id[0] == " ":  # Standard residue
                        try:
                            seq += seq1(residue.resname)
                        except Exception:
                            pass
                if seq:
                    sequences.append(seq)

        return sequences[0] if sequences else ""

    def register_progress_callback(self, job_id: str, callback) -> None:
        """Register a callback for job progress updates."""
        if job_id not in self._progress_callbacks:
            self._progress_callbacks[job_id] = []
        self._progress_callbacks[job_id].append(callback)

    def unregister_progress_callback(self, job_id: str, callback) -> None:
        """Unregister a progress callback."""
        if job_id in self._progress_callbacks:
            try:
                self._progress_callbacks[job_id].remove(callback)
            except ValueError:
                pass

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        task = self._running_jobs.get(job_id)
        if task and not task.done():
            task.cancel()
            await self._update_job_status(job_id, "cancelled", 0.0, "Job cancelled by user")
            return True
        return False

    def get_job(self, job_id: str) -> dict | None:
        """Get job details from database."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM design_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_job_results(
        self, job_id: str, offset: int = 0, limit: int = 20
    ) -> list[dict]:
        """Get results for a job."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM design_results
                WHERE job_id = ?
                ORDER BY rank
                LIMIT ? OFFSET ?
                """,
                (job_id, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_user_jobs(
        self, user_id: str, offset: int = 0, limit: int = 20
    ) -> list[dict]:
        """Get jobs for a user."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM design_jobs
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]


# Singleton instance
_runner: BoltzGenRunner | None = None


def get_boltzgen_runner() -> BoltzGenRunner:
    """Get the BoltzGen runner singleton."""
    global _runner
    if _runner is None:
        _runner = BoltzGenRunner()
    return _runner

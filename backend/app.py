"""
BoltzStudio Backend API
FastAPI server for protein structure prediction and design
"""

import asyncio
import json
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import uvicorn

# We'll import Boltz components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


app = FastAPI(
    title="BoltzStudio API",
    description="Protein Design & Structure Prediction API powered by Boltz",
    version="0.1.0",
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage (in production, use Redis/DB)
jobs: dict[str, dict] = {}

# ============================================================================
# Pydantic Models
# ============================================================================

class SequenceInput(BaseModel):
    """Input sequence for prediction."""
    id: str = Field(..., description="Chain identifier (e.g., 'A')")
    sequence: str = Field(..., description="Amino acid sequence")
    type: str = Field(default="protein", description="Sequence type: protein, dna, rna")


class LigandInput(BaseModel):
    """Input ligand for prediction."""
    id: str = Field(..., description="Ligand identifier")
    smiles: Optional[str] = Field(None, description="SMILES string")
    ccd: Optional[str] = Field(None, description="CCD code")


class PredictionRequest(BaseModel):
    """Request for structure prediction."""
    sequences: list[SequenceInput]
    ligands: Optional[list[LigandInput]] = None
    name: Optional[str] = Field(default="prediction", description="Job name")
    recycling_steps: int = Field(default=1, ge=1, le=10)
    sampling_steps: int = Field(default=50, ge=10, le=200)
    diffusion_samples: int = Field(default=1, ge=1, le=5)


class MutationRequest(BaseModel):
    """Request for mutation analysis."""
    sequence: str
    mutations: list[str]  # e.g., ["A10G", "L25V"]
    chain_id: str = "A"


class JobStatus(BaseModel):
    """Job status response."""
    job_id: str
    status: str  # queued, running, completed, failed
    progress: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class PredictionResult(BaseModel):
    """Prediction result."""
    job_id: str
    structure_pdb: str  # PDB format string
    structure_cif: str  # mmCIF format string
    confidence: dict
    plddt_per_residue: list[float]


# ============================================================================
# Helper Functions
# ============================================================================

def generate_yaml_input(request: PredictionRequest, output_path: Path) -> Path:
    """Generate YAML input file for Boltz."""
    yaml_content = {
        "version": 1,
        "sequences": []
    }

    for seq in request.sequences:
        if seq.type == "protein":
            yaml_content["sequences"].append({
                "protein": {
                    "id": seq.id,
                    "sequence": seq.sequence
                }
            })
        elif seq.type == "dna":
            yaml_content["sequences"].append({
                "dna": {
                    "id": seq.id,
                    "sequence": seq.sequence
                }
            })
        elif seq.type == "rna":
            yaml_content["sequences"].append({
                "rna": {
                    "id": seq.id,
                    "sequence": seq.sequence
                }
            })

    if request.ligands:
        for lig in request.ligands:
            lig_entry = {"id": lig.id}
            if lig.smiles:
                lig_entry["smiles"] = lig.smiles
            elif lig.ccd:
                lig_entry["ccd"] = lig.ccd
            yaml_content["sequences"].append({"ligand": lig_entry})

    import yaml
    yaml_file = output_path / f"{request.name}.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(yaml_content, f)

    return yaml_file


async def run_boltz_prediction(job_id: str, request: PredictionRequest):
    """Run Boltz prediction in background."""
    import subprocess
    import yaml

    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["progress"] = 0.1

        # Create temp directory for this job
        work_dir = Path(tempfile.mkdtemp(prefix=f"boltz_{job_id}_"))

        # Generate input YAML
        yaml_file = generate_yaml_input(request, work_dir)

        jobs[job_id]["progress"] = 0.2

        # Run Boltz prediction
        # Using subprocess to avoid blocking the event loop
        cmd = [
            sys.executable, "-m", "boltz", "predict",
            str(yaml_file),
            "--out_dir", str(work_dir / "output"),
            "--accelerator", "cpu",  # Use CPU for now
            "--recycling_steps", str(request.recycling_steps),
            "--sampling_steps", str(request.sampling_steps),
            "--diffusion_samples", str(request.diffusion_samples),
            "--output_format", "pdb",
        ]

        # Check if MSA is needed (for proteins)
        has_protein = any(seq.type == "protein" for seq in request.sequences)
        if has_protein:
            cmd.append("--use_msa_server")

        jobs[job_id]["progress"] = 0.3

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise Exception(f"Boltz failed: {stderr.decode()}")

        jobs[job_id]["progress"] = 0.9

        # Find output files
        output_dir = work_dir / "output" / f"boltz_results_{request.name}" / "predictions" / request.name

        # Read structure file
        pdb_file = list(output_dir.glob("*.pdb"))
        cif_file = list(output_dir.glob("*.cif"))

        structure_pdb = ""
        structure_cif = ""

        if pdb_file:
            with open(pdb_file[0]) as f:
                structure_pdb = f.read()

        if cif_file:
            with open(cif_file[0]) as f:
                structure_cif = f.read()

        # Read confidence
        confidence_file = list(output_dir.glob("confidence_*.json"))
        confidence = {}
        if confidence_file:
            with open(confidence_file[0]) as f:
                confidence = json.load(f)

        # Read pLDDT per residue
        import numpy as np
        plddt_file = list(output_dir.glob("plddt_*.npz"))
        plddt_per_residue = []
        if plddt_file:
            data = np.load(plddt_file[0])
            plddt_per_residue = data["plddt"].tolist() if "plddt" in data else []

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 1.0
        jobs[job_id]["result"] = {
            "structure_pdb": structure_pdb,
            "structure_cif": structure_cif,
            "confidence": confidence,
            "plddt_per_residue": plddt_per_residue,
            "work_dir": str(work_dir),
        }

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        import traceback
        traceback.print_exc()


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "BoltzStudio API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


@app.post("/predict", response_model=JobStatus)
async def predict_structure(
    request: PredictionRequest,
    background_tasks: BackgroundTasks
):
    """
    Submit a structure prediction job.

    Returns a job ID that can be used to check status and retrieve results.
    """
    job_id = str(uuid.uuid4())[:8]

    jobs[job_id] = {
        "status": "queued",
        "progress": 0.0,
        "result": None,
        "error": None,
        "request": request.model_dump(),
    }

    # Run prediction in background
    background_tasks.add_task(run_boltz_prediction, job_id, request)

    return JobStatus(
        job_id=job_id,
        status="queued",
        progress=0.0
    )


@app.get("/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a prediction job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        result=job.get("result"),
        error=job.get("error")
    )


@app.get("/job/{job_id}/structure")
async def get_structure(job_id: str, format: str = "pdb"):
    """Get the predicted structure in PDB or mmCIF format."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed: {job['status']}")

    if format == "pdb":
        return {"structure": job["result"]["structure_pdb"]}
    elif format == "cif":
        return {"structure": job["result"]["structure_cif"]}
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'pdb' or 'cif'")


@app.post("/mutate")
async def analyze_mutations(request: MutationRequest, background_tasks: BackgroundTasks):
    """
    Analyze the effect of mutations on protein structure.

    Runs predictions for wild-type and each mutant, returning comparison.
    """
    # Create wild-type prediction
    wt_request = PredictionRequest(
        sequences=[SequenceInput(id=request.chain_id, sequence=request.sequence)],
        name="wildtype"
    )

    wt_job_id = str(uuid.uuid4())[:8]
    jobs[wt_job_id] = {
        "status": "queued",
        "progress": 0.0,
        "result": None,
        "error": None,
    }
    background_tasks.add_task(run_boltz_prediction, wt_job_id, wt_request)

    # Create mutant predictions
    mutant_jobs = []
    for mutation in request.mutations:
        # Parse mutation (e.g., "A10G" -> position 10, A->G)
        pos = int(''.join(filter(str.isdigit, mutation)))
        new_aa = mutation[-1]

        mutant_seq = list(request.sequence)
        mutant_seq[pos - 1] = new_aa  # 1-indexed
        mutant_seq = ''.join(mutant_seq)

        mut_request = PredictionRequest(
            sequences=[SequenceInput(id=request.chain_id, sequence=mutant_seq)],
            name=f"mutant_{mutation}"
        )

        mut_job_id = str(uuid.uuid4())[:8]
        jobs[mut_job_id] = {
            "status": "queued",
            "progress": 0.0,
            "result": None,
            "error": None,
        }
        background_tasks.add_task(run_boltz_prediction, mut_job_id, mut_request)
        mutant_jobs.append({"mutation": mutation, "job_id": mut_job_id})

    return {
        "wildtype_job_id": wt_job_id,
        "mutant_jobs": mutant_jobs
    }


@app.get("/jobs")
async def list_jobs():
    """List all jobs."""
    return {
        job_id: {
            "status": job["status"],
            "progress": job.get("progress"),
        }
        for job_id, job in jobs.items()
    }


@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its results."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    del jobs[job_id]
    return {"status": "deleted"}


# ============================================================================
# Design Endpoints
# ============================================================================

@app.post("/design/random-mutate")
async def random_mutate(
    sequence: str,
    num_mutations: int = 1,
    positions: Optional[list[int]] = None
):
    """
    Generate random mutations for a protein sequence.

    Args:
        sequence: Original amino acid sequence
        num_mutations: Number of mutations to introduce
        positions: Optional list of positions to mutate (1-indexed)
    """
    import random

    AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"

    seq_list = list(sequence)
    mutations = []

    if positions is None:
        positions = random.sample(range(1, len(sequence) + 1), min(num_mutations, len(sequence)))

    for pos in positions[:num_mutations]:
        original = seq_list[pos - 1]
        # Pick a different amino acid
        new_aa = random.choice([aa for aa in AMINO_ACIDS if aa != original])
        mutations.append(f"{original}{pos}{new_aa}")
        seq_list[pos - 1] = new_aa

    return {
        "original_sequence": sequence,
        "mutated_sequence": ''.join(seq_list),
        "mutations": mutations
    }


@app.post("/design/optimize-stability")
async def optimize_stability(
    sequence: str,
    chain_id: str = "A",
    num_variants: int = 5,
    background_tasks: BackgroundTasks = None
):
    """
    Generate and evaluate variants optimized for stability.

    Uses a simple strategy of mutating to more stable amino acids
    at flexible positions (low pLDDT).
    """
    # First, predict wild-type structure
    wt_request = PredictionRequest(
        sequences=[SequenceInput(id=chain_id, sequence=sequence)],
        name="stability_wt"
    )

    wt_job_id = str(uuid.uuid4())[:8]
    jobs[wt_job_id] = {
        "status": "queued",
        "progress": 0.0,
        "result": None,
        "error": None,
    }

    if background_tasks:
        background_tasks.add_task(run_boltz_prediction, wt_job_id, wt_request)

    return {
        "wildtype_job_id": wt_job_id,
        "message": "Submit wildtype prediction first, then use /design/random-mutate to generate variants"
    }


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

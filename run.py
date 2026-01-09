#!/usr/bin/env python3
"""
BoltzStudio - Single command launcher
Run with: python studio/run.py
"""

import asyncio
import json
import subprocess
import sys
import tempfile
import threading
import uuid
import webbrowser
from pathlib import Path
from typing import Optional

# Check dependencies
try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ImportError:
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "pyyaml", "-q"])
    import uvicorn
    from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field

# ============================================================================
# Configuration
# ============================================================================

PORT = 8000
BOLTZ_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(BOLTZ_ROOT))

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(title="BoltzStudio", version="0.1.0")

# In-memory job storage
jobs: dict[str, dict] = {}

# ============================================================================
# Models
# ============================================================================

class SequenceInput(BaseModel):
    id: str = "A"
    sequence: str
    type: str = "protein"

class PredictionRequest(BaseModel):
    sequences: list[SequenceInput]
    name: str = "prediction"
    recycling_steps: int = 1
    sampling_steps: int = 50
    diffusion_samples: int = 1

# ============================================================================
# Prediction Logic
# ============================================================================

async def run_boltz_prediction(job_id: str, request: PredictionRequest):
    """Run Boltz prediction."""
    import yaml
    import numpy as np

    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["progress"] = 0.1

        # Create temp directory
        work_dir = Path(tempfile.mkdtemp(prefix=f"boltz_{job_id}_"))

        # Generate YAML input
        yaml_content = {"version": 1, "sequences": []}
        for seq in request.sequences:
            yaml_content["sequences"].append({
                seq.type: {"id": seq.id, "sequence": seq.sequence}
            })

        yaml_file = work_dir / f"{request.name}.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(yaml_content, f)

        jobs[job_id]["progress"] = 0.2

        # Build command - find boltz in same directory as python executable
        import shutil
        boltz_cmd = shutil.which("boltz") or str(Path(sys.executable).parent / "boltz")

        # Boltz CLI only accepts: gpu, cpu, tpu
        # For Apple Silicon, 'gpu' should use MPS via PyTorch
        import torch
        if torch.backends.mps.is_available():
            accelerator = "gpu"  # PyTorch will route to MPS
        elif torch.cuda.is_available():
            accelerator = "gpu"
        else:
            accelerator = "cpu"

        cmd = [
            boltz_cmd, "predict",
            str(yaml_file),
            "--out_dir", str(work_dir / "output"),
            "--accelerator", accelerator,
            "--recycling_steps", str(request.recycling_steps),
            "--sampling_steps", str(request.sampling_steps),
            "--diffusion_samples", str(request.diffusion_samples),
            "--output_format", "pdb",
            "--use_msa_server",
        ]

        jobs[job_id]["progress"] = 0.3

        # Run prediction
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(BOLTZ_ROOT)
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise Exception(f"Boltz failed: {stderr.decode()[:500]}")

        jobs[job_id]["progress"] = 0.9

        # Find outputs
        output_dir = work_dir / "output" / f"boltz_results_{request.name}" / "predictions" / request.name

        # Read structure
        pdb_files = list(output_dir.glob("*.pdb"))
        structure_pdb = ""
        if pdb_files:
            with open(pdb_files[0]) as f:
                structure_pdb = f.read()

        # Read confidence
        conf_files = list(output_dir.glob("confidence_*.json"))
        confidence = {}
        if conf_files:
            with open(conf_files[0]) as f:
                confidence = json.load(f)

        # Read pLDDT
        plddt_files = list(output_dir.glob("plddt_*.npz"))
        plddt = []
        if plddt_files:
            data = np.load(plddt_files[0])
            if "plddt" in data:
                plddt = data["plddt"].tolist()

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 1.0
        jobs[job_id]["result"] = {
            "structure_pdb": structure_pdb,
            "confidence": confidence,
            "plddt_per_residue": plddt,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

# ============================================================================
# API Endpoints
# ============================================================================

@app.post("/api/predict")
async def predict(request: PredictionRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "queued", "progress": 0.0, "result": None, "error": None}
    background_tasks.add_task(run_boltz_prediction, job_id, request)
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]

@app.post("/api/random-mutate")
async def random_mutate(sequence: str, num_mutations: int = 1):
    import random
    AA = "ACDEFGHIKLMNPQRSTVWY"
    seq = list(sequence)
    mutations = []
    positions = random.sample(range(len(seq)), min(num_mutations, len(seq)))
    for pos in positions:
        orig = seq[pos]
        new = random.choice([a for a in AA if a != orig])
        mutations.append(f"{orig}{pos+1}{new}")
        seq[pos] = new
    return {"mutated_sequence": "".join(seq), "mutations": mutations}

# ============================================================================
# Frontend (embedded HTML)
# ============================================================================

FRONTEND_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Boltz Studio</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://3dmol.org/build/3Dmol-min.js"></script>
    <style>
        :root {
            --bg: #f5f5f0;
            --surface: #ffffff;
            --border: #e0e0dc;
            --border-dark: #1a1a1a;
            --text: #1a1a1a;
            --text-secondary: #666660;
            --text-tertiary: #999990;
            --accent: #0d9373;
            --accent-light: #e8f5f1;
            --success: #0d9373;
            --warning: #c4841d;
            --error: #c44536;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'JetBrains Mono', monospace;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        /* Header */
        header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 2rem;
            background: var(--bg);
            border-bottom: 1px solid var(--border);
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 600;
            font-size: 1rem;
            color: var(--accent);
        }
        .logo svg { width: 20px; height: 20px; }

        nav {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }
        nav a {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.8rem;
            transition: color 0.2s;
        }
        nav a:hover { color: var(--text); }

        .btn {
            padding: 0.625rem 1.25rem;
            border-radius: 4px;
            font-family: inherit;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
            border: none;
        }
        .btn-outline {
            background: transparent;
            border: 1px solid var(--border-dark);
            color: var(--text);
        }
        .btn-outline:hover {
            background: var(--text);
            color: var(--bg);
        }
        .btn-primary {
            background: var(--accent);
            border: 1px solid var(--accent);
            color: white;
        }
        .btn-primary:hover {
            background: #0b7d63;
        }
        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* Main layout */
        main {
            padding-top: 4rem;
            min-height: 100vh;
            display: grid;
            grid-template-columns: 420px 1fr;
        }

        /* Sidebar */
        .sidebar {
            padding: 2.5rem 2rem;
            border-right: 1px solid var(--border);
            background: var(--bg);
        }

        .section-label {
            font-size: 0.7rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--accent);
            margin-bottom: 1rem;
        }
        .section-label::before {
            content: '[ ';
        }
        .section-label::after {
            content: ' ]';
        }

        h1 {
            font-size: 2rem;
            font-weight: 600;
            line-height: 1.2;
            margin-bottom: 1rem;
            letter-spacing: -0.02em;
        }

        .subtitle {
            color: var(--text-secondary);
            font-size: 0.85rem;
            line-height: 1.7;
            margin-bottom: 2rem;
        }

        /* Sequence input */
        .input-group {
            margin-bottom: 1.5rem;
        }
        .input-label {
            display: block;
            font-size: 0.75rem;
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .sequence-input {
            width: 100%;
            height: 120px;
            background: var(--surface);
            border: 1px solid var(--border);
            padding: 1rem;
            color: var(--text);
            font-family: inherit;
            font-size: 0.85rem;
            letter-spacing: 0.02em;
            line-height: 1.6;
            resize: none;
            transition: all 0.15s;
        }
        .sequence-input:focus {
            outline: none;
            border-color: var(--accent);
        }
        .sequence-input::placeholder {
            color: var(--text-tertiary);
        }

        .input-meta {
            display: flex;
            justify-content: space-between;
            margin-top: 0.5rem;
            font-size: 0.7rem;
            color: var(--text-tertiary);
        }

        /* Action buttons */
        .actions {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
        }
        .actions .btn {
            width: 100%;
            justify-content: center;
            padding: 0.875rem 1.25rem;
        }

        /* Progress */
        .progress-container {
            margin-top: 1rem;
            padding: 1rem;
            background: var(--accent-light);
            border: 1px solid var(--accent);
            display: none;
        }
        .progress-bar-bg {
            height: 4px;
            background: rgba(13,147,115,0.2);
            overflow: hidden;
        }
        .progress-bar {
            height: 100%;
            background: var(--accent);
            transition: width 0.3s ease;
        }
        .progress-text {
            font-size: 0.75rem;
            color: var(--accent);
            margin-top: 0.5rem;
        }

        /* Error */
        .error {
            margin-top: 1rem;
            padding: 1rem;
            background: #fef2f2;
            border: 1px solid var(--error);
            color: var(--error);
            font-size: 0.8rem;
            display: none;
        }

        /* Metrics cards */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.75rem;
            margin-top: 2rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
            opacity: 0;
            transition: opacity 0.3s;
        }
        .metrics-grid.visible { opacity: 1; }

        .metric-card {
            padding: 1rem;
            background: var(--surface);
            border: 1px solid var(--border);
            text-align: center;
        }
        .metric-value {
            font-size: 1.5rem;
            font-weight: 600;
            letter-spacing: -0.02em;
        }
        .metric-value.high { color: var(--success); }
        .metric-value.medium { color: var(--warning); }
        .metric-value.low { color: var(--error); }
        .metric-label {
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-tertiary);
            margin-top: 0.25rem;
        }

        /* Viewer area */
        .viewer-area {
            position: relative;
            background: #c8e6df;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        #viewer {
            position: absolute;
            inset: 0;
        }

        .placeholder {
            text-align: center;
            color: var(--text-secondary);
            z-index: 1;
            pointer-events: none;
        }
        .placeholder-icon {
            width: 64px;
            height: 64px;
            margin-bottom: 1rem;
            opacity: 0.4;
            color: var(--accent);
        }
        .placeholder-text {
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
            color: var(--text);
        }
        .placeholder-hint {
            font-size: 0.75rem;
            color: var(--text-tertiary);
        }

        /* Legend overlay */
        .legend {
            position: absolute;
            bottom: 1.5rem;
            left: 1.5rem;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(8px);
            padding: 1rem;
            font-size: 0.7rem;
            color: var(--text-secondary);
            opacity: 0;
            transition: opacity 0.3s;
            border: 1px solid var(--border);
        }
        .legend.visible { opacity: 1; }
        .legend-title {
            font-weight: 500;
            color: var(--text);
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 0.25rem;
        }
        .legend-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        /* Controls hint */
        .controls-hint {
            position: absolute;
            bottom: 1.5rem;
            right: 1.5rem;
            font-size: 0.7rem;
            color: var(--text-secondary);
            opacity: 0;
            transition: opacity 0.3s;
        }
        .controls-hint.visible { opacity: 1; }

        /* Spinner */
        @keyframes spin { to { transform: rotate(360deg); } }
        .spinner { animation: spin 1s linear infinite; }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                <path d="M2 17l10 5 10-5"/>
                <path d="M2 12l10 5 10-5"/>
            </svg>
            boltz studio
        </div>
        <nav>
            <a href="https://github.com/jwohlwend/boltz" target="_blank">GitHub</a>
            <a href="https://github.com/jwohlwend/boltz#readme" target="_blank">Docs</a>
        </nav>
    </header>

    <main>
        <aside class="sidebar">
            <div class="section-label">Structure Prediction</div>
            <h1>Predict Protein Structure</h1>
            <p class="subtitle">
                Enter a protein sequence to predict its 3D structure using Boltz-2, an open-source diffusion model for biomolecular structure prediction.
            </p>

            <div class="input-group">
                <label class="input-label">Amino Acid Sequence</label>
                <textarea
                    id="sequence"
                    class="sequence-input"
                    placeholder="MKLAVLKAGI..."
                    spellcheck="false"
                >MKLAVLKAGIAQGEVLVN</textarea>
                <div class="input-meta">
                    <span><span id="seq-length">18</span> residues</span>
                    <span id="avg-plddt-display" style="display:none;">avg pLDDT: <span id="avg-plddt">-</span></span>
                </div>
            </div>

            <div class="actions">
                <button class="btn btn-primary" id="predict-btn" onclick="predict()">
                    Predict Structure ->
                </button>
                <button class="btn btn-outline" onclick="randomMutate()">
                    Random Mutation
                </button>
            </div>

            <div class="progress-container" id="progress-container">
                <div class="progress-bar-bg">
                    <div class="progress-bar" id="progress-bar" style="width: 0%"></div>
                </div>
                <div class="progress-text" id="progress-text">Initializing...</div>
            </div>

            <div class="error" id="error"></div>

            <div class="metrics-grid" id="metrics">
                <div class="metric-card">
                    <div class="metric-value" id="metric-confidence">-</div>
                    <div class="metric-label">Confidence</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" id="metric-plddt">-</div>
                    <div class="metric-label">pLDDT</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" id="metric-ptm">-</div>
                    <div class="metric-label">pTM</div>
                </div>
            </div>
        </aside>

        <div class="viewer-area">
            <div id="viewer"></div>

            <div class="placeholder" id="placeholder">
                <svg class="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                    <path d="M2 17l10 5 10-5"/>
                    <path d="M2 12l10 5 10-5"/>
                </svg>
                <p class="placeholder-text">No structure yet</p>
                <p class="placeholder-hint">Enter a sequence and click predict</p>
            </div>

            <div class="legend" id="legend">
                <div class="legend-title">Confidence (pLDDT)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#0053D6"></span> Very high (>90)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#65CBF3"></span> High (70-90)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#FFDB13"></span> Medium (50-70)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#FF7D45"></span> Low (<50)</div>
            </div>

            <div class="controls-hint" id="controls-hint">drag to rotate · scroll to zoom</div>
        </div>
    </main>

    <script>
        let viewer = null;
        let currentJobId = null;
        let pollInterval = null;
        let plddt = [];

        const sequenceInput = document.getElementById('sequence');
        const seqLengthEl = document.getElementById('seq-length');

        sequenceInput.addEventListener('input', (e) => {
            const seq = e.target.value.toUpperCase().replace(/[^ACDEFGHIKLMNPQRSTVWY]/g, '');
            e.target.value = seq;
            seqLengthEl.textContent = seq.length;
        });

        async function predict() {
            const sequence = sequenceInput.value.trim();
            if (sequence.length < 5) return showError('Minimum 5 residues required');
            if (sequence.length > 500) return showError('Maximum 500 residues allowed');

            hideError();
            setLoading(true);
            showProgress(5, 'Queuing prediction...');

            try {
                const res = await fetch('/api/predict', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sequences: [{ id: 'A', sequence, type: 'protein' }],
                        name: 'design',
                        recycling_steps: 1,
                        sampling_steps: 50,
                        diffusion_samples: 1
                    })
                });
                const data = await res.json();
                currentJobId = data.job_id;
                pollInterval = setInterval(pollJob, 2000);
            } catch (err) {
                showError(err.message);
                setLoading(false);
            }
        }

        async function pollJob() {
            if (!currentJobId) return;
            try {
                const res = await fetch(`/api/job/${currentJobId}`);
                const data = await res.json();

                if (data.status === 'running') {
                    const pct = Math.round((data.progress || 0.3) * 100);
                    showProgress(pct, `Generating structure... ${pct}%`);
                }

                if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    setLoading(false);
                    hideProgress();

                    if (data.result) {
                        plddt = data.result.plddt_per_residue || [];
                        showStructure(data.result.structure_pdb);
                        updateMetrics(data.result.confidence);
                    }
                }

                if (data.status === 'failed') {
                    clearInterval(pollInterval);
                    setLoading(false);
                    hideProgress();
                    showError(data.error || 'Prediction failed');
                }
            } catch (err) {
                console.error(err);
            }
        }

        async function randomMutate() {
            const sequence = sequenceInput.value.trim();
            if (sequence.length < 5) return;
            try {
                const res = await fetch(`/api/random-mutate?sequence=${sequence}&num_mutations=1`, { method: 'POST' });
                const data = await res.json();
                sequenceInput.value = data.mutated_sequence;
                seqLengthEl.textContent = data.mutated_sequence.length;
            } catch (err) {
                console.error(err);
            }
        }

        function showStructure(pdbData) {
            document.getElementById('placeholder').style.display = 'none';
            document.getElementById('legend').classList.add('visible');
            document.getElementById('controls-hint').classList.add('visible');
            document.getElementById('metrics').classList.add('visible');

            const container = document.getElementById('viewer');

            if (viewer) {
                viewer.clear();
            } else {
                viewer = $3Dmol.createViewer(container, {
                    backgroundColor: '#c8e6df',
                    antialias: true
                });
            }

            viewer.addModel(pdbData, 'pdb');
            viewer.setStyle({}, {
                cartoon: {
                    colorfunc: (atom) => {
                        const conf = plddt[atom.resi - 1] || 0.5;
                        if (conf > 0.9) return '#0053D6';
                        if (conf > 0.7) return '#65CBF3';
                        if (conf > 0.5) return '#FFDB13';
                        return '#FF7D45';
                    }
                }
            });

            viewer.zoomTo();
            viewer.render();

            // Auto-rotate slowly
            let rotating = true;
            const rotate = () => {
                if (rotating && viewer) {
                    viewer.rotate(0.3, 'y');
                    viewer.render();
                    requestAnimationFrame(rotate);
                }
            };
            rotate();

            container.addEventListener('mousedown', () => { rotating = false; });
            container.addEventListener('wheel', () => { rotating = false; });
        }

        function updateMetrics(confidence) {
            if (!confidence) return;

            const fmt = (v) => v !== undefined ? (v * 100).toFixed(0) + '%' : '-';
            const cls = (v) => v >= 0.8 ? 'high' : v >= 0.5 ? 'medium' : 'low';

            const confEl = document.getElementById('metric-confidence');
            confEl.textContent = fmt(confidence.confidence_score);
            confEl.className = 'metric-value ' + cls(confidence.confidence_score);

            const plddtEl = document.getElementById('metric-plddt');
            plddtEl.textContent = fmt(confidence.complex_plddt);
            plddtEl.className = 'metric-value ' + cls(confidence.complex_plddt);

            const ptmEl = document.getElementById('metric-ptm');
            ptmEl.textContent = fmt(confidence.ptm);
            ptmEl.className = 'metric-value ' + cls(confidence.ptm);

            if (plddt.length > 0) {
                const avg = (plddt.reduce((a, b) => a + b, 0) / plddt.length * 100).toFixed(0);
                document.getElementById('avg-plddt-display').style.display = 'inline';
                document.getElementById('avg-plddt').textContent = avg + '%';
            }
        }

        function setLoading(loading) {
            const btn = document.getElementById('predict-btn');
            btn.disabled = loading;
            btn.innerHTML = loading
                ? '<svg class="spinner" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg> Predicting...'
                : 'Predict Structure ->';
        }

        function showProgress(percent, text) {
            document.getElementById('progress-container').style.display = 'block';
            document.getElementById('progress-bar').style.width = percent + '%';
            document.getElementById('progress-text').textContent = text;
        }

        function hideProgress() {
            document.getElementById('progress-container').style.display = 'none';
        }

        function showError(msg) {
            const el = document.getElementById('error');
            el.style.display = 'block';
            el.textContent = msg;
        }

        function hideError() {
            document.getElementById('error').style.display = 'none';
        }
    </script>
</body>
</html>
'''

@app.get("/", response_class=HTMLResponse)
async def root():
    return FRONTEND_HTML

# ============================================================================
# Main
# ============================================================================

def main():
    print("""

    ██████╗  ██████╗ ██╗  ████████╗███████╗
    ██╔══██╗██╔═══██╗██║  ╚══██╔══╝╚══███╔╝
    ██████╔╝██║   ██║██║     ██║     ███╔╝
    ██╔══██╗██║   ██║██║     ██║    ███╔╝
    ██████╔╝╚██████╔╝███████╗██║   ███████╗
    ╚═════╝  ╚═════╝ ╚══════╝╚═╝   ╚══════╝ STUDIO

    """)
    print(f"Starting BoltzStudio on http://localhost:{PORT}")
    print(f"Boltz root: {BOLTZ_ROOT}")
    print()
    print("Press Ctrl+C to stop")
    print()

    # Open browser after short delay
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{PORT}")

    threading.Thread(target=open_browser, daemon=True).start()

    # Run server
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

if __name__ == "__main__":
    main()

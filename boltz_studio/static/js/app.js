// Boltz Studio - Frontend Application

let viewer = null;
let currentJobId = null;
let currentWebSocket = null;
let plddt = [];

// DOM Elements
const sequenceInput = document.getElementById('sequence');
const seqLengthEl = document.getElementById('seq-length');

// Initialize
sequenceInput.addEventListener('input', (e) => {
    const seq = e.target.value.toUpperCase().replace(/[^ACDEFGHIKLMNPQRSTVWY]/g, '');
    e.target.value = seq;
    seqLengthEl.textContent = seq.length;
});

// WebSocket connection for real-time updates
function connectWebSocket(jobId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${location.host}/ws/job/${jobId}`);

    ws.onopen = () => {
        console.log(`WebSocket connected for job ${jobId}`);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleJobUpdate(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        // Fallback to polling if WebSocket fails
        startPolling(jobId);
    };

    ws.onclose = () => {
        console.log('WebSocket closed');
        currentWebSocket = null;
    };

    return ws;
}

// Handle job status updates (from WebSocket or polling)
function handleJobUpdate(data) {
    if (data.status === 'running') {
        const pct = Math.round((data.progress || 0.3) * 100);
        showProgress(pct, `Generating structure... ${pct}%`);
    }

    if (data.status === 'completed') {
        closeWebSocket();
        setLoading(false);
        hideProgress();

        if (data.result) {
            plddt = data.result.plddt_per_residue || [];
            showStructure(data.result.structure_pdb);
            updateMetrics(data.result.confidence);
        }
    }

    if (data.status === 'failed') {
        closeWebSocket();
        setLoading(false);
        hideProgress();
        showError(data.error || 'Prediction failed');
    }
}

function closeWebSocket() {
    if (currentWebSocket) {
        currentWebSocket.close();
        currentWebSocket = null;
    }
}

// Fallback polling (if WebSocket fails)
let pollInterval = null;

function startPolling(jobId) {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(() => pollJob(jobId), 2000);
}

async function pollJob(jobId) {
    try {
        const res = await fetch(`/api/job/${jobId}`);
        const data = await res.json();
        handleJobUpdate(data);

        if (data.status === 'completed' || data.status === 'failed') {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    } catch (err) {
        console.error(err);
    }
}

// API Functions
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

        // Connect via WebSocket for real-time updates
        closeWebSocket();
        currentWebSocket = connectWebSocket(currentJobId);

    } catch (err) {
        showError(err.message);
        setLoading(false);
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

// 3D Viewer
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

// Metrics
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

// UI Helpers
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

// Boltz Studio - Frontend Application

let viewer = null;
let currentJobId = null;
let currentWebSocket = null;
let plddt = [];

// Global state for saving
window.currentPdbData = null;
window.currentConfidence = null;
window.currentSequence = null;
window.plddt = [];

// Mutation tracking
let originalSequence = '';
let mutations = {}; // {position: {original: 'A', current: 'G'}}
let selectedResidue = null;

// Amino acids
const AMINO_ACIDS = ['A', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'V', 'W', 'Y'];

// Theme management
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('boltz-theme', newTheme);
}

function initTheme() {
    const savedTheme = localStorage.getItem('boltz-theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
}

// Initialize theme immediately (before DOMContentLoaded)
initTheme();

// Confirm modal system
let confirmCallback = null;

function showConfirm(title, message, buttonText = 'Delete') {
    return new Promise((resolve) => {
        document.getElementById('confirm-title').textContent = title;
        document.getElementById('confirm-message').textContent = message;
        document.getElementById('confirm-btn').textContent = buttonText;
        document.getElementById('confirm-modal').classList.add('visible');
        confirmCallback = resolve;
    });
}

function hideConfirmModal() {
    document.getElementById('confirm-modal').classList.remove('visible');
    if (confirmCallback) {
        confirmCallback(false);
        confirmCallback = null;
    }
}

function confirmAction() {
    document.getElementById('confirm-modal').classList.remove('visible');
    if (confirmCallback) {
        confirmCallback(true);
        confirmCallback = null;
    }
}

// Toast notification system
function showToast(message, type = 'success', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>`,
        error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>`,
        info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
        </svg>`
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-icon">${icons[type] || icons.info}</div>
        <div class="toast-message">${message}</div>
    `;

    container.appendChild(toast);

    // Auto remove after duration
    setTimeout(() => {
        toast.classList.add('toast-out');
        setTimeout(() => toast.remove(), 200);
    }, duration);
}

// DOM Elements
const sequenceInput = document.getElementById('sequence');
const seqLengthEl = document.getElementById('seq-length');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Restore active tab from previous session
    restoreActiveTab();

    // Sequence input handling
    sequenceInput.addEventListener('input', handleSequenceInput);
    sequenceInput.addEventListener('focus', () => {
        // Switch to text input mode when focusing
        document.querySelector('.sequence-editor-wrapper')?.classList.remove('edit-mode');
    });

    // Initialize mutation picker
    initMutationPicker();

    // Load library on startup
    loadLibraryDesigns();

    // Close mutation picker when clicking outside
    document.addEventListener('click', (e) => {
        const picker = document.getElementById('mutation-picker');
        if (picker && !picker.contains(e.target) && !e.target.classList.contains('residue')) {
            hideMutationPicker();
        }
    });

    // Initialize with default sequence
    handleSequenceInput({ target: sequenceInput });
});

function handleSequenceInput(e) {
    const seq = e.target.value.toUpperCase().replace(/[^ACDEFGHIKLMNPQRSTVWY]/g, '');
    e.target.value = seq;
    seqLengthEl.textContent = seq.length;

    // Store original sequence if this is a new sequence
    if (seq !== originalSequence && Object.keys(mutations).length === 0) {
        originalSequence = seq;
    }

    // Build interactive sequence editor
    buildSequenceEditor(seq);
}

// Tab switching
function switchTab(tabName, updateUrl = true) {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}-tab`);
    });

    // Save active tab to localStorage
    localStorage.setItem('boltz-active-tab', tabName);

    // Update URL
    if (updateUrl) {
        const url = tabName === 'predict' ? '/' : `/${tabName}`;
        history.pushState({ tab: tabName }, '', url);
    }

    if (tabName === 'community') {
        // Load the current view (all designs by default)
        if (typeof switchCommunityView === 'function') {
            switchCommunityView(currentView || 'all');
        } else {
            loadDesigns();
        }
    }

    if (tabName === 'design') {
        // Load design targets and jobs
        if (typeof loadDesignTargets === 'function') {
            loadDesignTargets();
            loadDesignJobs();
            if (typeof loadSynthesisOrders === 'function') loadSynthesisOrders();
        }
    }
}

// Handle browser back/forward buttons
window.addEventListener('popstate', (event) => {
    if (event.state && event.state.tab) {
        switchTab(event.state.tab, false);
    } else {
        // Parse URL to get tab
        const tab = getTabFromUrl();
        switchTab(tab, false);
    }
});

// Get tab name from current URL
function getTabFromUrl() {
    const path = window.location.pathname;
    if (path === '/design') return 'design';
    if (path === '/community') return 'community';
    return 'predict';
}

// Restore active tab from URL or localStorage
function restoreActiveTab() {
    // URL takes priority over localStorage
    const urlTab = getTabFromUrl();
    if (urlTab !== 'predict' || window.location.pathname !== '/') {
        // URL specifies a tab
        switchTab(urlTab, false);
        return;
    }

    // Fall back to localStorage
    const savedTab = localStorage.getItem('boltz-active-tab');
    if (savedTab && ['predict', 'design', 'community'].includes(savedTab)) {
        switchTab(savedTab);
    }
}

// ============================================
// SEQUENCE EDITOR & MUTATIONS
// ============================================

function buildSequenceEditor(sequence) {
    const editor = document.getElementById('sequence-editor');
    if (!editor) return;

    editor.innerHTML = '';

    for (let i = 0; i < sequence.length; i++) {
        const residue = document.createElement('div');
        residue.className = 'residue';
        residue.dataset.pos = i + 1;
        residue.dataset.aa = sequence[i];
        residue.textContent = sequence[i];

        // Check if this position has a mutation
        if (mutations[i + 1]) {
            residue.classList.add('mutated');
            residue.dataset.orig = mutations[i + 1].original;
        }

        residue.addEventListener('click', (e) => {
            e.stopPropagation();
            showMutationPicker(i + 1, sequence[i], e.target);
        });

        editor.appendChild(residue);
    }

    updateMutationDisplay();
}

function initMutationPicker() {
    const grid = document.getElementById('aa-grid');
    if (!grid) return;

    grid.innerHTML = '';
    AMINO_ACIDS.forEach(aa => {
        const btn = document.createElement('button');
        btn.dataset.aa = aa;
        btn.textContent = aa;
        btn.addEventListener('click', () => selectMutation(aa));
        grid.appendChild(btn);
    });
}

function showMutationPicker(position, currentAA, targetElement) {
    const picker = document.getElementById('mutation-picker');
    if (!picker) return;

    selectedResidue = { position, currentAA, element: targetElement };

    // Update picker header
    document.getElementById('picker-position').textContent = `Position ${position}`;
    document.getElementById('picker-current').textContent = mutations[position]?.original || currentAA;
    document.getElementById('picker-new').textContent = currentAA;

    // Highlight current selection
    document.querySelectorAll('#aa-grid button').forEach(btn => {
        btn.classList.remove('selected', 'original');
        if (btn.dataset.aa === currentAA) {
            btn.classList.add('selected');
        }
        if (btn.dataset.aa === (mutations[position]?.original || currentAA)) {
            btn.classList.add('original');
        }
    });

    // Show/hide reset button
    const resetBtn = document.getElementById('picker-reset');
    if (resetBtn) {
        resetBtn.style.display = mutations[position] ? 'block' : 'none';
    }

    // Position the picker
    const rect = targetElement.getBoundingClientRect();
    picker.style.left = `${rect.left}px`;
    picker.style.top = `${rect.bottom + 8}px`;
    picker.classList.add('visible');

    // Mark residue as selected
    document.querySelectorAll('.residue').forEach(r => r.classList.remove('selected'));
    targetElement.classList.add('selected');
}

function hideMutationPicker() {
    const picker = document.getElementById('mutation-picker');
    if (picker) {
        picker.classList.remove('visible');
    }
    document.querySelectorAll('.residue').forEach(r => r.classList.remove('selected'));
    selectedResidue = null;
}

function selectMutation(newAA) {
    if (!selectedResidue) return;

    const { position, currentAA, element } = selectedResidue;
    const originalAA = mutations[position]?.original || currentAA;

    if (newAA === originalAA) {
        // Reset to original
        delete mutations[position];
        element.classList.remove('mutated');
        element.dataset.aa = originalAA;
        element.textContent = originalAA;
        delete element.dataset.orig;
    } else {
        // Apply mutation
        if (!mutations[position]) {
            mutations[position] = { original: originalAA };
        }
        mutations[position].current = newAA;
        element.classList.add('mutated');
        element.dataset.aa = newAA;
        element.dataset.orig = originalAA;
        element.textContent = newAA;
    }

    // Update sequence input
    updateSequenceFromMutations();
    updateMutationDisplay();
    hideMutationPicker();
}

function resetMutation() {
    if (!selectedResidue) return;

    const { position, element } = selectedResidue;
    const originalAA = mutations[position]?.original;

    if (originalAA) {
        delete mutations[position];
        element.classList.remove('mutated');
        element.dataset.aa = originalAA;
        element.textContent = originalAA;
        delete element.dataset.orig;

        updateSequenceFromMutations();
        updateMutationDisplay();
    }

    hideMutationPicker();
}

function updateSequenceFromMutations() {
    let seq = originalSequence.split('');
    Object.entries(mutations).forEach(([pos, data]) => {
        seq[parseInt(pos) - 1] = data.current;
    });
    sequenceInput.value = seq.join('');
    seqLengthEl.textContent = seq.length;
}

function updateMutationDisplay() {
    const countEl = document.getElementById('mutation-count');
    const listEl = document.getElementById('mutations-list');
    const mutationCount = Object.keys(mutations).length;

    if (countEl) {
        countEl.textContent = `${mutationCount} mutation${mutationCount !== 1 ? 's' : ''}`;
        countEl.style.display = mutationCount > 0 ? 'inline' : 'none';
    }

    if (listEl) {
        if (mutationCount > 0) {
            listEl.style.display = 'flex';
            listEl.innerHTML = Object.entries(mutations).map(([pos, data]) => `
                <div class="mutation-tag">
                    ${data.original}${pos}${data.current}
                    <button onclick="removeMutation(${pos})">&times;</button>
                </div>
            `).join('');
        } else {
            listEl.style.display = 'none';
        }
    }
}

function removeMutation(position) {
    if (mutations[position]) {
        const originalAA = mutations[position].original;
        delete mutations[position];

        // Update the residue in the editor
        const residue = document.querySelector(`.residue[data-pos="${position}"]`);
        if (residue) {
            residue.classList.remove('mutated');
            residue.dataset.aa = originalAA;
            residue.textContent = originalAA;
            delete residue.dataset.orig;
        }

        updateSequenceFromMutations();
        updateMutationDisplay();
    }
}

function clearAllMutations() {
    mutations = {};
    sequenceInput.value = originalSequence;
    seqLengthEl.textContent = originalSequence.length;
    buildSequenceEditor(originalSequence);
    updateMutationDisplay();
}

// ============================================
// LIGAND SECTION
// ============================================

function toggleLigandSection() {
    const section = document.getElementById('ligand-section');
    if (section) {
        section.classList.toggle('expanded');
    }
}

function setLigand(name, smiles) {
    const input = document.getElementById('smiles-input');
    if (input) {
        input.value = smiles;
    }
}

function getLigandSmiles() {
    const input = document.getElementById('smiles-input');
    return input?.value?.trim() || null;
}

// ============================================
// PREDICTION
// ============================================

async function predict() {
    const sequence = sequenceInput.value.trim();
    if (sequence.length < 5) return showError('Minimum 5 residues required');
    if (sequence.length > 500) return showError('Maximum 500 residues allowed');

    hideError();
    setLoading(true);
    showProgress(5, 'Queuing prediction...');

    // Reset state
    window.currentPdbData = null;
    window.currentConfidence = null;
    window.currentSequence = null;
    hideViewerActions();

    // Build sequences array
    const sequences = [{ id: 'A', sequence, type: 'protein' }];

    // Add ligand if provided
    const smiles = getLigandSmiles();
    if (smiles) {
        sequences.push({ id: 'B', smiles, type: 'ligand' });
    }

    try {
        const res = await fetch('/api/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sequences,
                name: 'design',
                recycling_steps: 1,
                sampling_steps: 50,
                diffusion_samples: 1
            })
        });
        const data = await res.json();
        currentJobId = data.job_id;

        closeWebSocket();
        currentWebSocket = connectWebSocket(currentJobId);

    } catch (err) {
        showError(err.message);
        setLoading(false);
    }
}

// WebSocket connection
function connectWebSocket(jobId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${location.host}/ws/job/${jobId}`);

    ws.onopen = () => console.log(`WebSocket connected for job ${jobId}`);
    ws.onmessage = (event) => handleJobUpdate(JSON.parse(event.data));
    ws.onerror = () => startPolling(jobId);
    ws.onclose = () => { currentWebSocket = null; };

    return ws;
}

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
            window.plddt = plddt;
            window.currentPdbData = data.result.structure_pdb;
            window.currentConfidence = data.result.confidence;
            window.currentSequence = sequenceInput.value.trim();
            showStructure(data.result.structure_pdb);
            updateMetrics(data.result.confidence);
            showViewerActions();
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

// Polling fallback
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

// ============================================
// 3D VIEWER
// ============================================

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

    // Auto-rotate
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

    // Show affinity if present
    if (confidence.affinity_probability !== undefined) {
        const affinityCard = document.getElementById('metric-affinity-card');
        const affinityEl = document.getElementById('metric-affinity');
        if (affinityCard && affinityEl) {
            affinityCard.style.display = 'block';
            affinityEl.textContent = fmt(confidence.affinity_probability);
            affinityEl.className = 'metric-value ' + cls(confidence.affinity_probability);
        }
    }
}

// ============================================
// VIEWER ACTIONS
// ============================================

function showViewerActions() {
    const actions = document.getElementById('viewer-actions');
    if (actions) {
        actions.classList.add('visible');
    }
}

function hideViewerActions() {
    const actions = document.getElementById('viewer-actions');
    if (actions) {
        actions.classList.remove('visible');
    }
}

function downloadPdb() {
    if (!window.currentPdbData) {
        showError('No structure to download. Run a prediction first.');
        return;
    }

    const blob = new Blob([window.currentPdbData], { type: 'chemical/x-pdb' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `boltz_structure_${Date.now()}.pdb`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function downloadFasta() {
    if (!window.currentSequence) {
        showError('No sequence to download. Run a prediction first.');
        return;
    }

    const fasta = `>Boltz_Design_${Date.now()}\n${window.currentSequence}`;
    const blob = new Blob([fasta], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `boltz_sequence_${Date.now()}.fasta`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ============================================
// SAVE LOCAL MODAL
// ============================================

function showSaveLocalModal() {
    if (!window.currentPdbData) {
        showError('No structure to save. Run a prediction first.');
        return;
    }

    // Pre-fill with default name
    const nameInput = document.getElementById('save-local-name');
    if (nameInput && !nameInput.value) {
        nameInput.value = `Design ${new Date().toLocaleTimeString()}`;
    }

    document.getElementById('save-local-modal').classList.add('visible');
}

function hideSaveLocalModal() {
    document.getElementById('save-local-modal').classList.remove('visible');
}

function saveDesignLocally() {
    const name = document.getElementById('save-local-name').value.trim();
    const notes = document.getElementById('save-local-notes').value.trim();
    const tags = document.getElementById('save-local-tags').value.split(',').map(t => t.trim()).filter(t => t);

    if (!name) {
        showError('Please enter a name');
        return;
    }

    const design = {
        id: Date.now().toString(),
        name,
        notes,
        tags,
        sequence: window.currentSequence,
        pdb_data: window.currentPdbData,
        plddt: window.currentConfidence?.complex_plddt,
        ptm: window.currentConfidence?.ptm,
        confidence: window.currentConfidence?.confidence_score,
        plddt_per_residue: window.plddt,
        smiles: getLigandSmiles(),
        mutations: Object.keys(mutations).length > 0 ? { ...mutations } : null,
        created_at: new Date().toISOString()
    };

    // Save to localStorage
    const designs = getLocalDesigns();
    designs.unshift(design);
    if (designs.length > 50) designs.pop(); // Limit to 50 designs
    localStorage.setItem('boltz_designs', JSON.stringify(designs));

    hideSaveLocalModal();

    // Clear form
    document.getElementById('save-local-name').value = '';
    document.getElementById('save-local-notes').value = '';
    document.getElementById('save-local-tags').value = '';

    // Refresh library if open
    loadLibraryDesigns();
}

// ============================================
// LIBRARY MODAL
// ============================================

function showLibraryModal() {
    loadLibraryDesigns();
    document.getElementById('library-modal').classList.add('visible');
}

function hideLibraryModal() {
    document.getElementById('library-modal').classList.remove('visible');
}

function getLocalDesigns() {
    try {
        return JSON.parse(localStorage.getItem('boltz_designs') || '[]');
    } catch {
        return [];
    }
}

function loadLibraryDesigns() {
    const designs = getLocalDesigns();
    const grid = document.getElementById('library-grid');
    const empty = document.getElementById('library-empty');

    if (!grid) return;

    grid.innerHTML = '';

    if (designs.length === 0) {
        if (empty) empty.style.display = 'flex';
        return;
    }

    if (empty) empty.style.display = 'none';

    designs.forEach((design, index) => {
        const card = createLibraryCard(design, index);
        grid.appendChild(card);
    });
}

function createLibraryCard(design, index) {
    const card = document.createElement('div');
    card.className = 'library-card';

    const plddt = design.plddt ? (design.plddt * 100).toFixed(0) + '%' : '-';
    const date = new Date(design.created_at).toLocaleDateString();

    card.innerHTML = `
        <div class="library-card-preview">
            <div class="library-card-viewer" id="library-viewer-${index}"></div>
        </div>
        <div class="library-card-info">
            <div class="library-card-name">${escapeHtml(design.name)}</div>
            <div class="library-card-meta">${design.sequence?.length || 0} res | ${plddt} | ${date}</div>
            <div class="library-card-actions">
                <button onclick="loadDesignFromLibrary(${index})">Load</button>
                <button class="delete" onclick="deleteFromLibrary(${index})">Delete</button>
            </div>
        </div>
    `;

    // Load mini 3D viewer
    setTimeout(() => {
        const container = document.getElementById(`library-viewer-${index}`);
        if (container && design.pdb_data) {
            try {
                const miniViewer = $3Dmol.createViewer(container, {
                    backgroundColor: '#c8e6df',
                    antialias: true
                });
                miniViewer.addModel(design.pdb_data, 'pdb');
                miniViewer.setStyle({}, { cartoon: { color: '#0d9373' } });
                miniViewer.zoomTo();
                miniViewer.render();
            } catch (e) {
                console.error('Failed to load mini viewer:', e);
            }
        }
    }, 100);

    return card;
}

function loadDesignFromLibrary(index) {
    const designs = getLocalDesigns();
    const design = designs[index];
    if (!design) return;

    // Load sequence
    sequenceInput.value = design.sequence;
    seqLengthEl.textContent = design.sequence.length;
    originalSequence = design.sequence;

    // Load mutations if present
    mutations = design.mutations || {};
    buildSequenceEditor(design.sequence);

    // Load ligand if present
    if (design.smiles) {
        const smilesInput = document.getElementById('smiles-input');
        if (smilesInput) smilesInput.value = design.smiles;
        document.getElementById('ligand-section')?.classList.add('expanded');
    }

    // Load structure if available
    if (design.pdb_data) {
        window.currentPdbData = design.pdb_data;
        window.currentSequence = design.sequence;
        window.currentConfidence = {
            confidence_score: design.confidence,
            complex_plddt: design.plddt,
            ptm: design.ptm
        };
        plddt = design.plddt_per_residue || [];
        window.plddt = plddt;

        showStructure(design.pdb_data);
        updateMetrics(window.currentConfidence);
        showViewerActions();
    }

    hideLibraryModal();
}

async function deleteFromLibrary(index) {
    const designs = getLocalDesigns();
    const design = designs[index];
    const name = design?.name || 'this design';

    const confirmed = await showConfirm(
        'Delete Design',
        `Are you sure you want to delete "${name}"? This cannot be undone.`,
        'Delete'
    );

    if (!confirmed) return;

    designs.splice(index, 1);
    localStorage.setItem('boltz_designs', JSON.stringify(designs));
    loadLibraryDesigns();
    showToast('Design deleted');
}

// ============================================
// PUBLISH MODAL (Community)
// ============================================

// Capture preview image from 3Dmol viewer
function capturePreviewImage() {
    if (!viewer) return null;

    try {
        // Get the canvas element from the viewer
        const canvas = document.querySelector('#viewer canvas');
        if (!canvas) return null;

        // Create a smaller canvas for the preview (200x200)
        const previewCanvas = document.createElement('canvas');
        const size = 200;
        previewCanvas.width = size;
        previewCanvas.height = size;
        const ctx = previewCanvas.getContext('2d');

        // Draw the viewer canvas scaled down
        ctx.drawImage(canvas, 0, 0, canvas.width, canvas.height, 0, 0, size, size);

        // Return as base64 PNG (without the data:image/png;base64, prefix)
        const dataUrl = previewCanvas.toDataURL('image/png', 0.8);
        return dataUrl.split(',')[1]; // Remove prefix
    } catch (err) {
        console.error('Failed to capture preview:', err);
        return null;
    }
}

function showPublishModal() {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    if (!window.currentPdbData) {
        showError('No structure to publish. Run a prediction first.');
        return;
    }

    // Pre-fill with design name if available
    const nameInput = document.getElementById('publish-name');
    if (nameInput && !nameInput.value) {
        nameInput.value = `Design ${new Date().toLocaleTimeString()}`;
    }

    document.getElementById('publish-modal').classList.add('visible');
}

function hidePublishModal() {
    document.getElementById('publish-modal').classList.remove('visible');
}

async function publishDesign() {
    const name = document.getElementById('publish-name').value.trim();
    const description = document.getElementById('publish-description').value.trim();
    const tagsInput = document.getElementById('publish-tags').value.split(',').map(t => t.trim()).filter(t => t);
    const isPublic = document.getElementById('publish-public').checked;

    if (!name) {
        showError('Please enter a name');
        return;
    }

    // Format tags with default type 'purpose'
    const tags = tagsInput.map(t => ({ tag: t, tag_type: 'purpose' }));

    // Capture preview image from current viewer
    const previewImage = capturePreviewImage();

    try {
        const res = await fetch('/api/designs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                description: description || null,
                tags,
                is_public: isPublic,
                sequence: window.currentSequence,
                structure_pdb: window.currentPdbData,
                preview_image: previewImage,
                confidence_score: window.currentConfidence?.confidence_score,
                complex_plddt: window.currentConfidence?.complex_plddt ? window.currentConfidence.complex_plddt * 100 : null,
                ptm: window.currentConfidence?.ptm,
                plddt_per_residue: window.plddt || null
            })
        });

        if (res.ok) {
            hidePublishModal();
            // Clear form
            document.getElementById('publish-name').value = '';
            document.getElementById('publish-description').value = '';
            document.getElementById('publish-tags').value = '';
            showToast('Design published to community!');
        } else {
            const data = await res.json();
            showError(data.detail || 'Failed to publish design');
        }
    } catch (err) {
        console.error('Failed to publish design:', err);
        showError('Failed to publish design');
    }
}

// ============================================
// PDB MODAL
// ============================================

function showPdbModal() {
    document.getElementById('pdb-modal').classList.add('visible');
}

function hidePdbModal() {
    document.getElementById('pdb-modal').classList.remove('visible');
}

async function loadPdbById() {
    const pdbId = document.getElementById('pdb-id-input').value.trim().toUpperCase();
    if (!pdbId || pdbId.length !== 4) {
        showError('Please enter a valid 4-character PDB ID');
        return;
    }

    try {
        const res = await fetch(`/api/pdb/${pdbId}/structure`);
        if (!res.ok) throw new Error('PDB not found');

        const data = await res.json();

        // Load into viewer
        window.currentPdbData = data.pdb_data;
        showStructure(data.pdb_data);

        // Extract sequence if available
        if (data.sequence) {
            sequenceInput.value = data.sequence;
            seqLengthEl.textContent = data.sequence.length;
            originalSequence = data.sequence;
            buildSequenceEditor(data.sequence);
        }

        hidePdbModal();
        showViewerActions();
    } catch (err) {
        showError(`Failed to load PDB: ${err.message}`);
    }
}

// ============================================
// UI HELPERS
// ============================================

function setLoading(loading) {
    const btn = document.getElementById('predict-btn');
    btn.disabled = loading;
    btn.innerHTML = loading
        ? '<svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg> Predicting...'
        : 'Predict Structure <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>';
}

function showProgress(percent, text) {
    const container = document.getElementById('progress-container');
    container.style.display = 'block';
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// STRUCTURE COMPARISON
// ============================================

let compareViewers = { v1: null, v2: null };
let compareDesigns = [];

function enterCompareMode() {
    // Load designs from localStorage
    compareDesigns = JSON.parse(localStorage.getItem('boltz_designs') || '[]');

    if (compareDesigns.length < 2) {
        showToast('You need at least 2 saved designs to compare', 'info');
        return;
    }

    compareDesigns.sort((a, b) => new Date(b.created_at || b.timestamp) - new Date(a.created_at || a.timestamp));

    // Populate dropdowns
    const select1 = document.getElementById('compare-select-1');
    const select2 = document.getElementById('compare-select-2');

    const options = compareDesigns.map(d => {
        const plddt = d.plddt ? ` (${(d.plddt * 100).toFixed(0)}% pLDDT)` : '';
        return `<option value="${d.id}">${escapeHtml(d.name)}${plddt}</option>`;
    }).join('');

    select1.innerHTML = '<option value="">— Select first design —</option>' + options;
    select2.innerHTML = '<option value="">— Select second design —</option>' + options;

    // Clear viewers
    const v1 = document.getElementById('compare-viewer-1');
    const v2 = document.getElementById('compare-viewer-2');
    v1.innerHTML = '<span>Select a design from the dropdown above</span>';
    v2.innerHTML = '<span>Select a design from the dropdown above</span>';
    document.getElementById('compare-delta').innerHTML = '';

    // Show compare mode, hide single viewer
    document.querySelector('.viewer-area').classList.add('compare-active');
    document.getElementById('compare-mode').classList.add('active');
}

function exitCompareMode() {
    cleanupCompareViewers();
    document.getElementById('compare-mode').classList.remove('active');
    document.querySelector('.viewer-area').classList.remove('compare-active');
}

function onCompareSelectChange() {
    const id1 = document.getElementById('compare-select-1').value;
    const id2 = document.getElementById('compare-select-2').value;

    const d1 = compareDesigns.find(d => d.id === id1);
    const d2 = compareDesigns.find(d => d.id === id2);

    // Clean up old viewers
    cleanupCompareViewers();

    // Viewer 1
    const container1 = document.getElementById('compare-viewer-1');
    container1.innerHTML = '';
    if (d1?.pdb_data) {
        compareViewers.v1 = $3Dmol.createViewer(container1, {
            backgroundColor: '#c8e6df',
            antialias: true
        });
        compareViewers.v1.addModel(d1.pdb_data, 'pdb');
        compareViewers.v1.setStyle({}, { cartoon: { color: '#0d9373' } });
        compareViewers.v1.zoomTo();
        compareViewers.v1.render();
    } else {
        container1.innerHTML = '<span>Select a design from the dropdown above</span>';
    }

    // Viewer 2
    const container2 = document.getElementById('compare-viewer-2');
    container2.innerHTML = '';
    if (d2?.pdb_data) {
        compareViewers.v2 = $3Dmol.createViewer(container2, {
            backgroundColor: '#c8e6df',
            antialias: true
        });
        compareViewers.v2.addModel(d2.pdb_data, 'pdb');
        compareViewers.v2.setStyle({}, { cartoon: { color: '#0d9373' } });
        compareViewers.v2.zoomTo();
        compareViewers.v2.render();
    } else {
        container2.innerHTML = '<span>Select a design from the dropdown above</span>';
    }

    // Update delta
    updateCompareDelta(d1, d2);
}

function updateCompareDelta(d1, d2) {
    const deltaEl = document.getElementById('compare-delta');

    if (d1?.plddt !== undefined && d2?.plddt !== undefined) {
        const delta = ((d2.plddt - d1.plddt) * 100).toFixed(1);
        const sign = delta > 0 ? '+' : '';
        const cls = delta > 0 ? 'positive' : delta < 0 ? 'negative' : '';
        deltaEl.innerHTML = `Δ pLDDT: <span class="${cls}">${sign}${delta}%</span>`;
    } else {
        deltaEl.innerHTML = '';
    }
}

function cleanupCompareViewers() {
    if (compareViewers.v1) {
        try { compareViewers.v1.clear(); } catch (e) {}
        compareViewers.v1 = null;
    }
    if (compareViewers.v2) {
        try { compareViewers.v2.clear(); } catch (e) {}
        compareViewers.v2 = null;
    }
    // Also clear the container innerHTML to avoid stale canvas elements
    const c1 = document.getElementById('compare-viewer-1');
    const c2 = document.getElementById('compare-viewer-2');
    if (c1) c1.innerHTML = '';
    if (c2) c2.innerHTML = '';
}

// ============================================
// KEYBOARD SHORTCUTS
// ============================================

document.addEventListener('keydown', (e) => {
    // Ignore if typing in input/textarea
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        // Ctrl+Enter to predict while in sequence input
        if (e.ctrlKey && e.key === 'Enter' && e.target.id === 'sequence') {
            e.preventDefault();
            submitPrediction();
        }
        return;
    }

    // Global shortcuts (when not typing)
    if (e.ctrlKey || e.metaKey) {
        switch (e.key.toLowerCase()) {
            case 's':
                e.preventDefault();
                if (window.currentPdbData) {
                    showSaveLocalModal();
                }
                break;
            case 'p':
                e.preventDefault();
                submitPrediction();
                break;
            case 'd':
                e.preventDefault();
                if (window.currentPdbData) {
                    downloadPdb();
                }
                break;
            case 'l':
                e.preventDefault();
                showLibraryModal();
                break;
        }
    }

    // Non-modifier shortcuts
    switch (e.key) {
        case 'Escape':
            // Close any open modal
            document.querySelectorAll('.modal.visible').forEach(modal => {
                modal.classList.remove('visible');
            });
            hideMutationPicker();
            break;
        case '1':
            if (!e.ctrlKey && !e.metaKey) switchTab('predict');
            break;
        case '2':
            if (!e.ctrlKey && !e.metaKey) switchTab('community');
            break;
    }
});

// Show keyboard shortcuts help
function showShortcutsHelp() {
    alert(`Keyboard Shortcuts:

Ctrl+P - Run prediction
Ctrl+S - Save locally
Ctrl+D - Download PDB
Ctrl+L - Open library
Ctrl+Enter - Predict (in sequence input)

1 - Switch to Predict tab
2 - Switch to Community tab
Esc - Close modals`);
}

// ============================================
// LINEAGE TRACKING
// ============================================

// Track design lineage (parent-child relationships)
function getDesignLineage(designId) {
    const designs = JSON.parse(localStorage.getItem('boltz_designs') || '[]');
    const design = designs.find(d => d.id === designId);
    if (!design) return [];

    const lineage = [design];
    let current = design;

    while (current.parentId) {
        const parent = designs.find(d => d.id === current.parentId);
        if (parent) {
            lineage.unshift(parent);
            current = parent;
        } else {
            break;
        }
    }

    return lineage;
}

// Fork a design (create child with mutations)
function forkDesignLocally(parentId) {
    const designs = JSON.parse(localStorage.getItem('boltz_designs') || '[]');
    const parent = designs.find(d => d.id === parentId);
    if (!parent) return;

    // Load parent into editor
    sequenceInput.value = parent.sequence;
    seqLengthEl.textContent = parent.sequence.length;
    originalSequence = parent.sequence;
    buildSequenceEditor(parent.sequence);

    // Store parent reference for when saving
    window.pendingParentId = parentId;

    hideLibraryModal();
    switchTab('predict');
}

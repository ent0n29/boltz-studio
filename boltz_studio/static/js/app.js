// Boltz Studio - Frontend Application

// ============================================
// CLIENT-SIDE ROUTER
// ============================================

const Router = {
    routes: {},
    currentRoute: null,

    // Register a route
    on(path, handler) {
        this.routes[path] = handler;
    },

    // Navigate to a path
    navigate(path, params = {}) {
        const hashPath = path.startsWith('#') ? path : '#' + path;
        window.location.hash = hashPath;
    },

    // Parse current hash into path and params
    parseHash() {
        const hash = window.location.hash.slice(1) || '/';
        const [path, queryString] = hash.split('?');
        const params = {};

        if (queryString) {
            queryString.split('&').forEach(pair => {
                const [key, value] = pair.split('=');
                params[key] = decodeURIComponent(value);
            });
        }

        return { path, params };
    },

    // Match path to route (supports :id params)
    matchRoute(path) {
        // Try exact match first
        if (this.routes[path]) {
            return { handler: this.routes[path], params: {} };
        }

        // Try parameterized routes
        for (const routePath of Object.keys(this.routes)) {
            const routeParts = routePath.split('/');
            const pathParts = path.split('/');

            if (routeParts.length !== pathParts.length) continue;

            const params = {};
            let match = true;

            for (let i = 0; i < routeParts.length; i++) {
                if (routeParts[i].startsWith(':')) {
                    params[routeParts[i].slice(1)] = pathParts[i];
                } else if (routeParts[i] !== pathParts[i]) {
                    match = false;
                    break;
                }
            }

            if (match) {
                return { handler: this.routes[routePath], params };
            }
        }

        return null;
    },

    // Handle route change
    handleRoute() {
        const { path, params } = this.parseHash();
        const match = this.matchRoute(path);

        if (match) {
            this.currentRoute = path;
            match.handler({ ...params, ...match.params });
        } else {
            // Default to predict tab
            this.navigate('/');
        }
    },

    // Initialize router
    init() {
        window.addEventListener('hashchange', () => this.handleRoute());

        // Handle initial route
        if (window.location.hash) {
            this.handleRoute();
        }
    }
};

// Route handlers
function routeToPredictTab() {
    switchTab('predict', false);
    hideAllPages();
}

function routeToDesignTab() {
    switchTab('design', false);
    hideAllPages();
}

function routeToCommunityTab() {
    switchTab('community', false);
    hideAllPages();
}

function routeToDesignResults(params) {
    hideAllTabs();
    showPage('results-page', params.id);
}

function routeToCommunityDesign(params) {
    hideAllTabs();
    showPage('design-detail-page', params.id);
    // Load design data directly (don't rely on event which may not be set up yet)
    if (params.id) {
        loadDesignDetailPage(params.id);
    }
}

function routeToLibrary() {
    hideAllTabs();
    showPage('library-page');
}

function routeToProfile(params) {
    hideAllTabs();
    showPage('profile-page', params.id);
    // Load profile data directly (don't rely on event which may not be set up yet)
    if (params.id && typeof loadProfilePage === 'function') {
        loadProfilePage(params.id);
    }
}

// Helper functions for routing
function hideAllTabs() {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
}

function hideAllPages() {
    document.querySelectorAll('.page-container').forEach(page => {
        page.classList.remove('active');
    });
}

function showPage(pageId, params) {
    hideAllPages();
    const page = document.getElementById(pageId);
    if (page) {
        page.classList.add('active');
        // Trigger page-specific initialization
        const event = new CustomEvent('pageshow', { detail: { params } });
        page.dispatchEvent(event);
    }
}

// Navigation helper
function navigateTo(path) {
    Router.navigate(path);
}

function goBack() {
    window.history.back();
}

// Register routes
Router.on('/', routeToPredictTab);
Router.on('/design', routeToDesignTab);
Router.on('/community', routeToCommunityTab);
Router.on('/design/results/:id', routeToDesignResults);
Router.on('/community/:id', routeToCommunityDesign);
Router.on('/library', routeToLibrary);
Router.on('/profile/:id', routeToProfile);

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
function showToast(message, type = 'success', duration = 3000, undoCallback = null) {
    var container = document.getElementById('toast-container');
    if (!container) return;

    var icons = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };

    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;

    var undoButton = undoCallback ? '<button class="toast-undo-btn" onclick="event.stopPropagation();">Undo</button>' : '';

    toast.innerHTML = '<div class="toast-icon">' + (icons[type] || icons.info) + '</div>' +
        '<div class="toast-message">' + message + '</div>' +
        undoButton;

    container.appendChild(toast);

    // Handle undo button click
    if (undoCallback) {
        var undoBtn = toast.querySelector('.toast-undo-btn');
        if (undoBtn) {
            undoBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                undoCallback();
                toast.classList.add('toast-out');
                setTimeout(function() { toast.remove(); }, 200);
            });
        }
    }

    // Auto remove after duration
    var timeoutId = setTimeout(function() {
        toast.classList.add('toast-out');
        setTimeout(function() { toast.remove(); }, 200);
    }, undoCallback ? 5000 : duration); // Longer duration for undo toasts

    return { toast: toast, cancel: function() { clearTimeout(timeoutId); toast.remove(); } };
}

// Toast with undo for destructive actions
function showToastWithUndo(message, actionCallback, undoCallback) {
    var executed = false;

    // Show toast with undo option
    showToast(message, 'info', 5000, function() {
        if (!executed) {
            executed = true;
            undoCallback();
        }
    });

    // Execute the action after a short delay to allow undo
    setTimeout(function() {
        if (!executed) {
            executed = true;
            actionCallback();
        }
    }, 100);
}

// DOM Elements
const sequenceInput = document.getElementById('sequence');
const seqLengthEl = document.getElementById('seq-length');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Initialize router
    Router.init();

    // Tab switching - use router for navigation
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            const tabName = tab.dataset.tab;
            const path = tabName === 'predict' ? '/' : `/${tabName}`;
            navigateTo(path);
        });
    });

    // Restore active tab from URL hash or default
    if (!window.location.hash || window.location.hash === '#' || window.location.hash === '#/') {
        restoreActiveTab();
    }

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
    // Hide all pages first
    hideAllPages();

    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}-tab`);
    });

    // Save active tab to localStorage
    localStorage.setItem('boltz-active-tab', tabName);

    // Update URL hash (router uses hash-based routing)
    if (updateUrl) {
        const path = tabName === 'predict' ? '/' : `/${tabName}`;
        window.location.hash = path;
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
// INLINE SAVE PANEL
// ============================================

function toggleInlineSave() {
    if (!window.currentPdbData) {
        showToast('No structure to save. Run a prediction first.', 'error');
        return;
    }

    const panel = document.getElementById('inline-save-panel');
    const isVisible = panel.style.display !== 'none';

    // Hide other panels
    hideInlinePublish();

    if (isVisible) {
        hideInlineSave();
    } else {
        // Pre-fill name
        const nameInput = document.getElementById('inline-save-name');
        if (nameInput && !nameInput.value) {
            nameInput.value = 'Design ' + new Date().toLocaleTimeString();
        }
        panel.style.display = 'block';
    }
}

function hideInlineSave() {
    document.getElementById('inline-save-panel').style.display = 'none';
}

function saveDesignInline() {
    const name = document.getElementById('inline-save-name').value.trim();
    const notes = document.getElementById('inline-save-notes').value.trim();
    const tags = document.getElementById('inline-save-tags').value.split(',').map(function(t) { return t.trim(); }).filter(function(t) { return t; });

    if (!name) {
        showToast('Please enter a name', 'error');
        return;
    }

    var design = {
        id: Date.now().toString(),
        name: name,
        notes: notes,
        tags: tags,
        sequence: window.currentSequence,
        pdb_data: window.currentPdbData,
        plddt: window.currentConfidence ? window.currentConfidence.complex_plddt : null,
        ptm: window.currentConfidence ? window.currentConfidence.ptm : null,
        confidence: window.currentConfidence ? window.currentConfidence.confidence_score : null,
        plddt_per_residue: window.plddt,
        smiles: getLigandSmiles(),
        mutations: Object.keys(mutations).length > 0 ? Object.assign({}, mutations) : null,
        created_at: new Date().toISOString()
    };

    // Save to localStorage
    var designs = getLocalDesigns();
    designs.unshift(design);
    if (designs.length > 50) designs.pop();
    localStorage.setItem('boltz_designs', JSON.stringify(designs));

    hideInlineSave();

    // Clear form
    document.getElementById('inline-save-name').value = '';
    document.getElementById('inline-save-notes').value = '';
    document.getElementById('inline-save-tags').value = '';

    showToast('Design saved to library!');
    loadLibraryDesigns();
}

// Legacy modal functions (kept for backwards compatibility)
function showSaveLocalModal() {
    toggleInlineSave();
}

function hideSaveLocalModal() {
    hideInlineSave();
}

// ============================================
// INLINE PUBLISH PANEL
// ============================================

function toggleInlinePublish() {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    if (!window.currentPdbData) {
        showToast('No structure to publish. Run a prediction first.', 'error');
        return;
    }

    const panel = document.getElementById('inline-publish-panel');
    const isVisible = panel.style.display !== 'none';

    // Hide other panels
    hideInlineSave();

    if (isVisible) {
        hideInlinePublish();
    } else {
        // Pre-fill name
        const nameInput = document.getElementById('inline-publish-name');
        if (nameInput && !nameInput.value) {
            nameInput.value = 'Design ' + new Date().toLocaleTimeString();
        }
        panel.style.display = 'block';
    }
}

function hideInlinePublish() {
    document.getElementById('inline-publish-panel').style.display = 'none';
}

async function publishDesignInline() {
    const name = document.getElementById('inline-publish-name').value.trim();
    const description = document.getElementById('inline-publish-description').value.trim();
    const tagsInput = document.getElementById('inline-publish-tags').value.split(',').map(function(t) { return t.trim(); }).filter(function(t) { return t; });
    const isPublic = document.getElementById('inline-publish-public').checked;

    if (!name) {
        showToast('Please enter a name', 'error');
        return;
    }

    // Format tags
    const tags = tagsInput.map(function(t) { return { tag: t, tag_type: 'purpose' }; });

    // Capture preview image
    const previewImage = capturePreviewImage();

    try {
        const res = await fetch('/api/designs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                description: description || null,
                tags: tags,
                is_public: isPublic,
                sequence: window.currentSequence,
                structure_pdb: window.currentPdbData,
                preview_image: previewImage,
                confidence_score: window.currentConfidence ? window.currentConfidence.confidence_score : null,
                complex_plddt: window.currentConfidence && window.currentConfidence.complex_plddt ? window.currentConfidence.complex_plddt * 100 : null,
                ptm: window.currentConfidence ? window.currentConfidence.ptm : null,
                plddt_per_residue: window.plddt || null
            })
        });

        if (res.ok) {
            hideInlinePublish();
            // Clear form
            document.getElementById('inline-publish-name').value = '';
            document.getElementById('inline-publish-description').value = '';
            document.getElementById('inline-publish-tags').value = '';
            showToast('Design published to community!');
        } else {
            const data = await res.json();
            showToast(data.detail || 'Failed to publish design', 'error');
        }
    } catch (err) {
        console.error('Failed to publish design:', err);
        showToast('Failed to publish design', 'error');
    }
}

// Legacy modal functions (kept for backwards compatibility)
function showPublishModal() {
    toggleInlinePublish();
}

function hidePublishModal() {
    hideInlinePublish();
}

// ============================================
// INLINE PDB SEARCH
// ============================================

function toggleInlinePdb() {
    const panel = document.getElementById('inline-pdb-panel');
    const isVisible = panel.style.display !== 'none';

    if (isVisible) {
        hideInlinePdb();
    } else {
        panel.style.display = 'block';
    }
}

function hideInlinePdb() {
    document.getElementById('inline-pdb-panel').style.display = 'none';
}

async function loadPdbInline() {
    const pdbId = document.getElementById('inline-pdb-id').value.trim().toUpperCase();
    if (!pdbId || pdbId.length !== 4) {
        showToast('Please enter a valid 4-character PDB ID', 'error');
        return;
    }

    try {
        const res = await fetch('/api/pdb/' + pdbId + '/structure');
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

        hideInlinePdb();
        document.getElementById('inline-pdb-id').value = '';
        showViewerActions();
        showToast('Loaded structure from PDB: ' + pdbId);
    } catch (err) {
        showToast('Failed to load PDB: ' + err.message, 'error');
    }
}

// Legacy modal functions (kept for backwards compatibility)
function showPdbModal() {
    toggleInlinePdb();
}

function hidePdbModal() {
    hideInlinePdb();
}

// ============================================
// LIBRARY FUNCTIONS
// ============================================

function showLibraryModal() {
    // Redirect to library page
    navigateTo('/library');
}

function hideLibraryModal() {
    // No-op - library is now a page, navigation handles this
}

function getLocalDesigns() {
    try {
        return JSON.parse(localStorage.getItem('boltz_designs') || '[]');
    } catch {
        return [];
    }
}

function loadLibraryDesigns() {
    // Refresh the page-based library if it's visible
    const libraryPage = document.getElementById('library-page');
    if (libraryPage && libraryPage.classList.contains('active')) {
        loadLibraryPage();
    }
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
            predict();
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
                predict();
                break;
            case 'd':
                e.preventDefault();
                if (window.currentPdbData) {
                    downloadPdb();
                }
                break;
            case 'l':
                e.preventDefault();
                navigateTo('/library');
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
            // Close inline panels
            hideInlineSave();
            hideInlinePublish();
            hideInlinePdb();
            // Close custom target upload
            if (typeof hideCustomTargetUpload === 'function') {
                hideCustomTargetUpload();
            }
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

// ============================================
// LIBRARY PAGE (Full Page View)
// ============================================

let libraryPageDesigns = [];

// Initialize library page when it becomes visible
document.addEventListener('DOMContentLoaded', () => {
    const libraryPage = document.getElementById('library-page');
    if (libraryPage) {
        libraryPage.addEventListener('pageshow', loadLibraryPage);
    }

    // Search functionality
    const searchInput = document.getElementById('library-page-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterLibraryPage, 300));
    }

    // Filter functionality
    const filterSelect = document.getElementById('library-page-filter');
    if (filterSelect) {
        filterSelect.addEventListener('change', filterLibraryPage);
    }
});

async function loadLibraryPage() {
    // Load from localStorage first
    libraryPageDesigns = JSON.parse(localStorage.getItem('boltz_designs') || '[]');

    // Also try to load from API if user is logged in
    if (window.currentUser) {
        try {
            const response = await fetch('/api/designs/my', { credentials: 'include' });
            if (response.ok) {
                const data = await response.json();
                // Merge with local designs
                data.designs.forEach(d => {
                    if (!libraryPageDesigns.find(ld => ld.id === d.id)) {
                        libraryPageDesigns.push(d);
                    }
                });
            }
        } catch (error) {
            console.error('Error loading designs from API:', error);
        }
    }

    renderLibraryPage();
}

function filterLibraryPage() {
    renderLibraryPage();
}

function renderLibraryPage() {
    const grid = document.getElementById('library-page-grid');
    const empty = document.getElementById('library-page-empty');
    const searchQuery = document.getElementById('library-page-search')?.value?.toLowerCase() || '';
    const filter = document.getElementById('library-page-filter')?.value || 'all';

    let filtered = [...libraryPageDesigns];

    // Apply search filter
    if (searchQuery) {
        filtered = filtered.filter(d =>
            d.name?.toLowerCase().includes(searchQuery) ||
            d.notes?.toLowerCase().includes(searchQuery) ||
            d.tags?.some(t => {
                const tagStr = typeof t === 'string' ? t : (t.tag || '');
                return tagStr.toLowerCase().includes(searchQuery);
            })
        );
    }

    // Apply type filter
    if (filter === 'predictions') {
        filtered = filtered.filter(d => d.type === 'prediction');
    } else if (filter === 'binders') {
        filtered = filtered.filter(d => d.type === 'binder');
    } else if (filter === 'published') {
        filtered = filtered.filter(d => d.is_published);
    }

    // Sort by date (newest first)
    filtered.sort((a, b) => new Date(b.savedAt || b.created_at) - new Date(a.savedAt || a.created_at));

    if (filtered.length === 0) {
        grid.innerHTML = '';
        empty.style.display = 'flex';
        return;
    }

    empty.style.display = 'none';
    grid.innerHTML = filtered.map(design => {
        const name = design.name || 'Unnamed Design';
        const residues = design.sequence?.length || 0;
        const timeAgo = formatTimeAgo(design.savedAt || design.created_at);
        return '<div class="library-design-card" onclick="loadLibraryDesign(\'' + design.id + '\')">' +
            '<div class="library-card-preview">' +
                '<div class="viewer-placeholder">' +
                    '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1">' +
                        '<path d="M12 2L2 7l10 5 10-5-10-5z"/>' +
                        '<path d="M2 17l10 5 10-5"/>' +
                        '<path d="M2 12l10 5 10-5"/>' +
                    '</svg>' +
                '</div>' +
            '</div>' +
            '<div class="library-card-body">' +
                '<div class="library-card-name">' + name + '</div>' +
                '<div class="library-card-meta">' +
                    '<span>' + residues + ' residues</span>' +
                    '<span>' + timeAgo + '</span>' +
                '</div>' +
                '<div class="library-card-actions">' +
                    '<button class="btn btn-outline" onclick="event.stopPropagation(); loadLibraryDesign(\'' + design.id + '\')">Load</button>' +
                    '<button class="btn btn-outline" onclick="event.stopPropagation(); deleteLibraryDesign(\'' + design.id + '\')">Delete</button>' +
                '</div>' +
            '</div>' +
        '</div>';
    }).join('');
}

function loadLibraryDesign(designId) {
    const design = libraryPageDesigns.find(d => d.id === designId);
    if (!design) return;

    // Load into editor
    sequenceInput.value = design.sequence;
    seqLengthEl.textContent = design.sequence.length;
    originalSequence = design.sequence;
    buildSequenceEditor(design.sequence);

    // Navigate to predict tab
    navigateTo('/');
    showToast('Loaded: ' + (design.name || 'Design'), 'success');
}

function deleteLibraryDesign(designId) {
    if (!confirm('Delete this design?')) return;

    libraryPageDesigns = libraryPageDesigns.filter(d => d.id !== designId);
    localStorage.setItem('boltz_designs', JSON.stringify(libraryPageDesigns));
    renderLibraryPage();
    showToast('Design deleted', 'success');
}

// ============================================
// COMMUNITY DESIGN DETAIL PAGE
// ============================================

let currentDetailDesign = null;
let detailViewer = null;

// Initialize design detail page when it becomes visible
document.addEventListener('DOMContentLoaded', () => {
    const detailPage = document.getElementById('design-detail-page');
    if (detailPage) {
        detailPage.addEventListener('pageshow', async (e) => {
            const designId = e.detail?.params;
            if (designId) {
                await loadDesignDetailPage(designId);
            }
        });
    }

    // Initialize profile page when it becomes visible
    const profilePage = document.getElementById('profile-page');
    if (profilePage) {
        profilePage.addEventListener('pageshow', async (e) => {
            const userId = e.detail?.params;
            if (userId && typeof loadProfilePage === 'function') {
                await loadProfilePage(userId);
            }
        });
    }
});

async function loadDesignDetailPage(designId) {
    try {
        const response = await fetch('/api/designs/' + designId);
        if (!response.ok) throw new Error('Failed to load design');

        currentDetailDesign = await response.json();
        renderDesignDetailPage();

        // Load comments
        loadDetailComments();
    } catch (error) {
        console.error('Error loading design:', error);
        showToast('Failed to load design', 'error');
    }
}

function renderDesignDetailPage() {
    const design = currentDetailDesign;
    if (!design) return;

    document.getElementById('design-detail-title').textContent = design.name || 'Unnamed Design';
    document.getElementById('design-detail-author-link').textContent = design.author?.display_name || 'Unknown';
    document.getElementById('design-detail-author-link').href = '#/profile/' + (design.author?.id || '');
    document.getElementById('design-detail-date').textContent = formatDate(design.created_at);
    document.getElementById('design-detail-description').textContent = design.description || 'No description provided.';

    // Tags - tags are objects with { tag, tag_type } structure
    const tagsContainer = document.getElementById('design-detail-tags');
    tagsContainer.innerHTML = (design.tags || []).map(function(t) {
        const tagName = typeof t === 'string' ? t : (t.tag || '');
        if (!tagName) return '';
        return '<span class="tag">' + escapeHtml(tagName) + '</span>';
    }).filter(Boolean).join('');

    // Stats
    document.getElementById('design-detail-stars').textContent = design.star_count || 0;
    document.getElementById('design-detail-forks').textContent = design.fork_count || 0;
    document.getElementById('design-detail-downloads').textContent = design.download_count || 0;
    document.getElementById('design-detail-views').textContent = design.view_count || 0;

    // Metrics
    document.getElementById('design-detail-plddt').textContent = design.complex_plddt ? design.complex_plddt.toFixed(1) : '-';
    document.getElementById('design-detail-ptm').textContent = design.ptm ? design.ptm.toFixed(2) : '-';

    // Star button
    const starBtn = document.getElementById('design-detail-star-btn');
    if (design.is_starred) {
        starBtn.classList.add('starred');
    } else {
        starBtn.classList.remove('starred');
    }
    document.getElementById('design-detail-star-count').textContent = design.star_count || 0;

    // Comment form (show if logged in)
    const commentForm = document.getElementById('design-detail-comment-form');
    if (window.currentUser) {
        commentForm.style.display = 'block';
    }

    // Load 3D structure
    loadDetailStructure(design);
}

async function loadDetailStructure(design) {
    const viewerDiv = document.getElementById('design-detail-viewer-3d');

    // Get theme-appropriate background color
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const bgColor = isDark ? '#0d3d38' : '#f0fdfa';

    // Always recreate viewer to handle theme changes and container resize
    if (detailViewer) {
        detailViewer.clear();
    }
    detailViewer = $3Dmol.createViewer(viewerDiv, {
        backgroundColor: bgColor
    });

    if (design.structure_pdb) {
        console.log('Loading structure, PDB length:', design.structure_pdb.length);
        detailViewer.addModel(design.structure_pdb, 'pdb');
        detailViewer.setStyle({}, {
            cartoon: {
                colorfunc: function(atom) {
                    var b = atom.b;
                    if (b > 90) return '#0053D6';
                    if (b > 70) return '#65CBF3';
                    if (b > 50) return '#FFDB13';
                    return '#FF7D45';
                }
            }
        });
        detailViewer.zoomTo();
        detailViewer.render();

        // Resize after a brief delay to ensure container is fully rendered
        setTimeout(function() {
            detailViewer.resize();
            detailViewer.render();
        }, 100);
    } else {
        console.warn('No structure_pdb data for design:', design.id);
    }
}

async function loadDetailComments() {
    if (!currentDetailDesign) return;

    try {
        const response = await fetch('/api/designs/' + currentDetailDesign.id + '/comments');
        if (!response.ok) return;

        const data = await response.json();
        // API returns { comments: [...], total, offset, limit }
        const comments = data.comments || [];
        document.getElementById('design-detail-comments-count').textContent = data.total || comments.length;

        const list = document.getElementById('design-detail-comments-list');
        if (comments.length === 0) {
            list.innerHTML = '<div style="padding: 1rem; text-align: center; color: var(--text-tertiary);">No comments yet</div>';
            return;
        }

        list.innerHTML = comments.map(function(comment) {
            // API uses 'author' not 'user'
            var avatar = comment.author?.avatar_url || '/img/default-avatar.png';
            var authorName = comment.author?.display_name || 'Anonymous';
            var timeAgo = formatTimeAgo(comment.created_at);
            var content = escapeHtml(comment.content);
            return '<div class="comment-item">' +
                '<div class="comment-item-header">' +
                    '<img class="comment-item-avatar" src="' + avatar + '" alt="">' +
                    '<span class="comment-item-author">' + authorName + '</span>' +
                    '<span class="comment-item-date">' + timeAgo + '</span>' +
                '</div>' +
                '<div class="comment-item-content">' + content + '</div>' +
            '</div>';
        }).join('');
    } catch (error) {
        console.error('Error loading comments:', error);
    }
}

async function submitDetailComment() {
    if (!currentDetailDesign || !window.currentUser) return;

    const textarea = document.getElementById('design-detail-comment-text');
    const content = textarea.value.trim();
    if (!content) return;

    try {
        const response = await fetch('/api/designs/' + currentDetailDesign.id + '/comments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ content: content })
        });

        if (!response.ok) throw new Error('Failed to post comment');

        textarea.value = '';
        showToast('Comment posted!', 'success');
        loadDetailComments();
    } catch (error) {
        console.error('Error posting comment:', error);
        showToast('Failed to post comment', 'error');
    }
}

async function toggleDetailStar() {
    if (!currentDetailDesign || !window.currentUser) {
        showLoginModal();
        return;
    }

    try {
        // Use DELETE to unstar, POST to star
        const isCurrentlyStarred = currentDetailDesign.is_starred;
        const response = await fetch('/api/designs/' + currentDetailDesign.id + '/star', {
            method: isCurrentlyStarred ? 'DELETE' : 'POST',
            credentials: 'include'
        });

        if (!response.ok) throw new Error('Failed to toggle star');

        const data = await response.json();
        currentDetailDesign.is_starred = data.starred;
        currentDetailDesign.star_count = data.star_count;

        const starBtn = document.getElementById('design-detail-star-btn');
        if (data.starred) {
            starBtn.classList.add('starred');
        } else {
            starBtn.classList.remove('starred');
        }
        document.getElementById('design-detail-star-count').textContent = data.star_count;
        document.getElementById('design-detail-stars').textContent = data.star_count;
    } catch (error) {
        console.error('Error toggling star:', error);
    }
}

function forkDetailDesign() {
    if (!currentDetailDesign) return;

    // Load design into editor
    sequenceInput.value = currentDetailDesign.sequence || '';
    handleSequenceInput({ target: sequenceInput });

    navigateTo('/');
    showToast('Design forked! Make your changes and save.', 'success');
}

function downloadDetailPdb() {
    if (!currentDetailDesign?.pdb_data) {
        showToast('No structure available', 'error');
        return;
    }

    const blob = new Blob([currentDetailDesign.pdb_data], { type: 'chemical/x-pdb' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (currentDetailDesign.name || 'design') + '.pdb';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Note: Utility functions (debounce, formatDate, formatTimeAgo, escapeHtml)
// are now in utils.js

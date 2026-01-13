/**
 * Binder Design Module - BoltzGen Integration
 * Handles target selection, design job submission, results viewing, and synthesis ordering
 */

// State
let designTargets = [];
let selectedTarget = null;
let designJobs = [];
let currentCategory = 'all';
let jobProgressEventSource = null;
let targetViewer = null;
let resultViewer = null;
let currentTargetDetail = null;
let currentResults = [];
let currentResultIndex = 0;
let bindingSiteVisible = false;

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    // Load targets when design tab is clicked
    document.querySelectorAll('.tab[data-tab="design"]').forEach(btn => {
        btn.addEventListener('click', () => {
            loadDesignTargets();
            loadDesignJobs();
            loadSynthesisOrders();
        });
    });
});

// ===========================================
// TARGET LISTING
// ===========================================

async function loadDesignTargets() {
    const grid = document.getElementById('targets-grid');
    grid.innerHTML = '<div class="loading">Loading targets...</div>';

    try {
        const params = currentCategory !== 'all' ? `?category=${currentCategory}` : '';
        const response = await fetch(`/api/design/targets${params}`);

        if (!response.ok) throw new Error('Failed to load targets');

        const data = await response.json();
        designTargets = data.targets;

        renderTargets();
    } catch (error) {
        console.error('Error loading targets:', error);
        grid.innerHTML = '<div class="error">Failed to load targets</div>';
    }
}

function renderTargets() {
    const grid = document.getElementById('targets-grid');

    if (designTargets.length === 0) {
        grid.innerHTML = '<div class="empty">No targets found</div>';
        return;
    }

    grid.innerHTML = designTargets.map(target => `
        <div class="target-card ${selectedTarget?.id === target.id ? 'selected' : ''}"
             onclick="showTargetDetail('${target.id}')">
            <div class="target-header">
                <span class="target-category-badge ${target.category}">${formatCategory(target.category)}</span>
                ${target.is_curated ? '<span class="curated-badge">Curated</span>' : ''}
            </div>
            <h3 class="target-name">${target.name}</h3>
            <p class="target-description">${target.description || ''}</p>
            <div class="target-meta">
                ${target.pdb_id ? `<span class="pdb-id">PDB: ${target.pdb_id}</span>` : ''}
                <span class="difficulty ${target.difficulty}">${target.difficulty}</span>
            </div>
            <div class="target-stats">
                <span>${target.design_count} designs</span>
                <span>${target.successful_designs} successful</span>
            </div>
        </div>
    `).join('');
}

function formatCategory(category) {
    const names = {
        'cancer': 'Cancer',
        'infectious_disease': 'Infectious Disease',
        'autoimmune': 'Autoimmune',
        'neurology': 'Neurology',
        'metabolic': 'Metabolic',
        'custom': 'Custom'
    };
    return names[category] || category;
}

function filterTargets(category) {
    currentCategory = category;

    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.category === category);
    });

    loadDesignTargets();
}

// ===========================================
// TARGET DETAIL MODAL
// ===========================================

async function showTargetDetail(targetId) {
    const modal = document.getElementById('target-modal');
    modal.classList.add('visible');

    // Show loading state
    document.getElementById('target-modal-name').textContent = 'Loading...';

    try {
        const response = await fetch(`/api/design/targets/${targetId}`);
        if (!response.ok) throw new Error('Failed to load target');

        currentTargetDetail = await response.json();

        // Update modal content
        document.getElementById('target-modal-name').textContent = currentTargetDetail.name;
        document.getElementById('target-modal-category').textContent = formatCategory(currentTargetDetail.category);
        document.getElementById('target-modal-category').className = `target-category-badge ${currentTargetDetail.category}`;
        document.getElementById('target-modal-difficulty').textContent = currentTargetDetail.difficulty;
        document.getElementById('target-modal-difficulty').className = `difficulty ${currentTargetDetail.difficulty}`;
        document.getElementById('target-modal-description').textContent = currentTargetDetail.description || '';

        // Details
        document.getElementById('target-modal-pdb').innerHTML = currentTargetDetail.pdb_id
            ? `<a href="https://www.rcsb.org/structure/${currentTargetDetail.pdb_id}" target="_blank">${currentTargetDetail.pdb_id}</a>`
            : '-';
        document.getElementById('target-modal-uniprot').innerHTML = currentTargetDetail.uniprot_id
            ? `<a href="https://www.uniprot.org/uniprotkb/${currentTargetDetail.uniprot_id}" target="_blank">${currentTargetDetail.uniprot_id}</a>`
            : '-';
        document.getElementById('target-modal-organism').textContent = currentTargetDetail.organism || '-';
        document.getElementById('target-modal-therapeutic').textContent = currentTargetDetail.therapeutic_area || '-';

        // Stats
        document.getElementById('target-modal-designs').textContent = currentTargetDetail.design_count || 0;
        document.getElementById('target-modal-success').textContent = currentTargetDetail.successful_designs || 0;

        // Load 3D structure
        await loadTargetStructure(currentTargetDetail);

    } catch (error) {
        console.error('Error loading target detail:', error);
        showToast('Failed to load target details', 'error');
    }
}

async function loadTargetStructure(target) {
    const viewerDiv = document.getElementById('target-viewer-3d');

    // Initialize 3Dmol viewer if needed
    if (!targetViewer) {
        targetViewer = $3Dmol.createViewer(viewerDiv, {
            backgroundColor: '#1a1a1a'
        });
    }

    targetViewer.clear();

    let pdbData = target.structure_pdb;

    // If no structure stored, fetch from RCSB
    if (!pdbData && target.pdb_id) {
        try {
            const response = await fetch(`https://files.rcsb.org/download/${target.pdb_id}.pdb`);
            if (response.ok) {
                pdbData = await response.text();
            }
        } catch (error) {
            console.error('Failed to fetch PDB:', error);
        }
    }

    if (pdbData) {
        targetViewer.addModel(pdbData, 'pdb');
        targetViewer.setStyle({}, { cartoon: { color: 'spectrum' } });
        targetViewer.zoomTo();
        targetViewer.render();
        bindingSiteVisible = false;
        document.getElementById('binding-site-toggle-text').textContent = 'Show Binding Site';
    } else {
        viewerDiv.innerHTML = '<div style="color:#666;text-align:center;padding-top:150px;">No structure available</div>';
    }
}

function resetTargetView() {
    if (targetViewer) {
        targetViewer.zoomTo();
        targetViewer.render();
    }
}

function toggleBindingSite() {
    if (!targetViewer || !currentTargetDetail) return;

    bindingSiteVisible = !bindingSiteVisible;

    if (bindingSiteVisible && currentTargetDetail.binding_site_residues) {
        // Highlight binding site residues
        targetViewer.setStyle({}, { cartoon: { color: 'white', opacity: 0.7 } });
        targetViewer.setStyle(
            { resi: currentTargetDetail.binding_site_residues },
            { cartoon: { color: '#0d9373' }, stick: { color: '#0d9373' } }
        );
        document.getElementById('binding-site-toggle-text').textContent = 'Hide Binding Site';
    } else {
        targetViewer.setStyle({}, { cartoon: { color: 'spectrum' } });
        document.getElementById('binding-site-toggle-text').textContent = 'Show Binding Site';
    }

    targetViewer.render();
}

function hideTargetModal() {
    document.getElementById('target-modal').classList.remove('visible');
}

function selectTargetFromModal() {
    if (!currentTargetDetail) return;

    selectedTarget = currentTargetDetail;
    hideTargetModal();

    // Update card selection
    document.querySelectorAll('.target-card').forEach(card => {
        card.classList.remove('selected');
    });

    // Show design parameters
    const paramsSection = document.getElementById('design-params-section');
    paramsSection.style.display = 'block';
    document.getElementById('design-job-name').placeholder = `${selectedTarget.name} binder`;

    paramsSection.scrollIntoView({ behavior: 'smooth' });

    showToast(`Selected: ${selectedTarget.name}`, 'success');
}

function selectTarget(targetId) {
    // Direct selection from card (fallback)
    showTargetDetail(targetId);
}

// ===========================================
// DESIGN JOB SUBMISSION
// ===========================================

async function startDesignJob() {
    if (!selectedTarget) {
        showToast('Please select a target first', 'error');
        return;
    }

    if (!window.currentUser) {
        showLoginModal();
        return;
    }

    const protocol = document.getElementById('design-protocol').value;
    const binderMin = parseInt(document.getElementById('binder-length-min').value);
    const binderMax = parseInt(document.getElementById('binder-length-max').value);
    const numDesigns = parseInt(document.getElementById('num-designs').value);
    const jobName = document.getElementById('design-job-name').value || `${selectedTarget.name} binder`;

    if (binderMin > binderMax) {
        showToast('Minimum length must be less than maximum', 'error');
        return;
    }

    const btn = document.getElementById('start-design-btn');
    btn.disabled = true;
    btn.innerHTML = 'Starting...';

    try {
        const response = await fetch('/api/design/jobs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                name: jobName,
                target_id: selectedTarget.id,
                protocol: protocol,
                num_designs: numDesigns,
                binder_length_min: binderMin,
                binder_length_max: binderMax
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start job');
        }

        const job = await response.json();
        showToast('Design job started!', 'success');

        loadDesignJobs();
        subscribeToJobProgress(job.id);

    } catch (error) {
        console.error('Error starting job:', error);
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `
            Start Design
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="5" y1="12" x2="19" y2="12"/>
                <polyline points="12 5 19 12 12 19"/>
            </svg>
        `;
    }
}

// ===========================================
// DESIGN JOBS
// ===========================================

async function loadDesignJobs() {
    if (!window.currentUser) return;

    try {
        const response = await fetch('/api/design/jobs', { credentials: 'include' });
        if (!response.ok) throw new Error('Failed to load jobs');

        const data = await response.json();
        designJobs = data.jobs;

        renderDesignJobs();
    } catch (error) {
        console.error('Error loading jobs:', error);
    }
}

function renderDesignJobs() {
    const list = document.getElementById('design-jobs-list');
    const empty = document.getElementById('jobs-empty');

    if (!designJobs || designJobs.length === 0) {
        if (empty) empty.style.display = 'flex';
        list.innerHTML = `
            <div class="jobs-empty" id="jobs-empty">
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                    <path d="M2 17l10 5 10-5"/>
                    <path d="M2 12l10 5 10-5"/>
                </svg>
                <p>No design jobs yet</p>
                <p class="hint">Select a target above to start designing binders</p>
            </div>
        `;
        return;
    }

    list.innerHTML = designJobs.map(job => `
        <div class="job-card" data-job-id="${job.id}">
            <div class="job-header">
                <h4 class="job-name">${job.name}</h4>
                <span class="job-status ${job.status}">${formatStatus(job.status)}</span>
            </div>
            <div class="job-meta">
                <span>Protocol: ${formatProtocol(job.protocol)}</span>
                <span>${job.num_designs} designs</span>
                <span>${formatDate(job.created_at)}</span>
            </div>
            ${job.status === 'generating' || job.status === 'queued' || job.status === 'folding' ? `
                <div class="job-progress">
                    <div class="job-progress-bar" style="width: ${job.progress * 100}%"></div>
                </div>
                <div class="job-progress-text">${job.current_step || 'Starting...'} (${Math.round(job.progress * 100)}%)</div>
            ` : ''}
            ${job.status === 'completed' ? `
                <div class="job-results-preview">
                    <span class="results-count">${job.total_passed || 0} results</span>
                    <button class="btn btn-outline btn-small" onclick="viewJobResults('${job.id}')">View Results</button>
                </div>
            ` : ''}
            ${job.status === 'failed' ? `
                <div class="job-error">${job.error || 'Job failed'}</div>
            ` : ''}
        </div>
    `).join('');
}

function formatStatus(status) {
    const names = {
        'queued': 'Queued',
        'downloading_models': 'Downloading',
        'generating': 'Generating',
        'folding': 'Folding',
        'analyzing': 'Analyzing',
        'filtering': 'Filtering',
        'completed': 'Completed',
        'failed': 'Failed',
        'cancelled': 'Cancelled'
    };
    return names[status] || status;
}

function formatProtocol(protocol) {
    const names = {
        'nanobody-anything': 'Nanobody',
        'antibody-anything': 'Antibody',
        'peptide-anything': 'Peptide',
        'protein-anything': 'Protein',
        'protein-small_molecule': 'Small Molecule'
    };
    return names[protocol] || protocol;
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function subscribeToJobProgress(jobId) {
    if (jobProgressEventSource) {
        jobProgressEventSource.close();
    }

    jobProgressEventSource = new EventSource(`/api/design/jobs/${jobId}/progress`);

    jobProgressEventSource.addEventListener('progress', (event) => {
        const progress = JSON.parse(event.data);
        updateJobProgress(progress);
    });

    jobProgressEventSource.addEventListener('error', () => {
        jobProgressEventSource.close();
        jobProgressEventSource = null;
        loadDesignJobs();
    });
}

function updateJobProgress(progress) {
    const jobCard = document.querySelector(`.job-card[data-job-id="${progress.job_id}"]`);
    if (!jobCard) return;

    const statusEl = jobCard.querySelector('.job-status');
    statusEl.textContent = formatStatus(progress.status);
    statusEl.className = `job-status ${progress.status}`;

    if (progress.status === 'completed' || progress.status === 'failed') {
        loadDesignJobs();
    } else {
        let progressDiv = jobCard.querySelector('.job-progress');
        if (progressDiv) {
            progressDiv.querySelector('.job-progress-bar').style.width = `${progress.progress * 100}%`;
            jobCard.querySelector('.job-progress-text').textContent =
                `${progress.message || progress.current_step || 'Processing...'} (${Math.round(progress.progress * 100)}%)`;
        }
    }
}

// ===========================================
// RESULTS VIEWER
// ===========================================

async function viewJobResults(jobId) {
    const modal = document.getElementById('design-results-modal');
    modal.classList.add('visible');

    try {
        const response = await fetch(`/api/design/jobs/${jobId}/results?limit=50`);
        if (!response.ok) throw new Error('Failed to load results');

        const data = await response.json();
        currentResults = data.results;

        renderResultsList();

        if (currentResults.length > 0) {
            selectResult(0);
        }
    } catch (error) {
        console.error('Error loading results:', error);
        showToast('Failed to load results', 'error');
    }
}

function renderResultsList() {
    const list = document.getElementById('design-results-list');

    list.innerHTML = currentResults.map((result, index) => `
        <div class="result-item ${index === currentResultIndex ? 'active' : ''}"
             onclick="selectResult(${index})">
            <div class="result-item-header">
                <span class="result-item-rank">Rank #${result.rank}</span>
                <span class="result-item-score">${result.plddt_score ? result.plddt_score.toFixed(1) : '-'}</span>
            </div>
            <div class="result-item-sequence">${result.sequence.substring(0, 30)}...</div>
        </div>
    `).join('');
}

async function selectResult(index) {
    currentResultIndex = index;
    const result = currentResults[index];

    // Update list selection
    document.querySelectorAll('.result-item').forEach((item, i) => {
        item.classList.toggle('active', i === index);
    });

    // Show detail section
    document.getElementById('result-detail-section').style.display = 'flex';

    // Update result info
    document.getElementById('result-detail-rank').textContent = result.rank;
    document.getElementById('result-detail-plddt').textContent = result.plddt_score ? result.plddt_score.toFixed(1) : '-';
    document.getElementById('result-detail-ptm').textContent = result.ptm_score ? result.ptm_score.toFixed(2) : '-';
    document.getElementById('result-detail-confidence').textContent = result.confidence_score ? result.confidence_score.toFixed(2) : '-';
    document.getElementById('result-detail-sequence').textContent = result.sequence;
    document.getElementById('result-detail-length').textContent = result.sequence.length;

    // Update publish button
    const publishBtn = document.getElementById('publish-result-btn');
    if (result.is_published) {
        publishBtn.disabled = true;
        publishBtn.innerHTML = 'Published';
    } else {
        publishBtn.disabled = false;
        publishBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>
                <polyline points="16 6 12 2 8 6"/>
                <line x1="12" y1="2" x2="12" y2="15"/>
            </svg>
            Publish to Community
        `;
    }

    // Load 3D structure
    await loadResultStructure(result);
}

async function loadResultStructure(result) {
    const viewerDiv = document.getElementById('result-viewer-3d');

    if (!resultViewer) {
        resultViewer = $3Dmol.createViewer(viewerDiv, {
            backgroundColor: '#1a1a1a'
        });
    }

    resultViewer.clear();

    // Fetch full result with structure
    try {
        const response = await fetch(`/api/design/results/${result.id}`);
        if (response.ok) {
            const fullResult = await response.json();

            if (fullResult.structure_pdb) {
                resultViewer.addModel(fullResult.structure_pdb, 'pdb');

                // Color by pLDDT (AlphaFold coloring)
                resultViewer.setStyle({}, {
                    cartoon: {
                        colorfunc: (atom) => {
                            const b = atom.b;
                            if (b > 90) return '#0053D6';      // Very high
                            if (b > 70) return '#65CBF3';      // High
                            if (b > 50) return '#FFDB13';      // Medium
                            return '#FF7D45';                   // Low
                        }
                    }
                });

                resultViewer.zoomTo();
                resultViewer.render();
            }
        }
    } catch (error) {
        console.error('Error loading result structure:', error);
    }
}

function hideDesignResultsModal() {
    document.getElementById('design-results-modal').classList.remove('visible');
}

function downloadCurrentResultPdb() {
    const result = currentResults[currentResultIndex];
    if (result) {
        window.open(`/api/design/results/${result.id}/pdb`, '_blank');
    }
}

async function publishCurrentResult() {
    const result = currentResults[currentResultIndex];
    if (!result || result.is_published) return;

    try {
        const response = await fetch(`/api/design/results/${result.id}/publish`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Failed to publish');

        const data = await response.json();
        showToast('Design published to community!', 'success');

        result.is_published = true;
        document.getElementById('publish-result-btn').disabled = true;
        document.getElementById('publish-result-btn').innerHTML = 'Published';

    } catch (error) {
        console.error('Error publishing:', error);
        showToast('Failed to publish design', 'error');
    }
}

// ===========================================
// SYNTHESIS ORDERING
// ===========================================

let currentSynthesisResultId = null;

function showOrderSynthesisModal() {
    const result = currentResults[currentResultIndex];
    if (!result) return;

    currentSynthesisResultId = result.id;
    document.getElementById('synthesis-modal').classList.add('visible');

    // Update cost estimate based on selections
    updateSynthesisCost();
}

function hideSynthesisModal() {
    document.getElementById('synthesis-modal').classList.remove('visible');
    currentSynthesisResultId = null;
}

function updateSynthesisCost() {
    const type = document.getElementById('synthesis-type').value;
    const costs = {
        'dna': '$100-200',
        'plasmid': '$200-400',
        'protein': '$500-2000'
    };
    document.getElementById('synthesis-cost').textContent = costs[type] || '$200-400';
}

// Add event listener for cost updates
document.addEventListener('DOMContentLoaded', () => {
    const typeSelect = document.getElementById('synthesis-type');
    if (typeSelect) {
        typeSelect.addEventListener('change', updateSynthesisCost);
    }
});

async function submitSynthesisOrder() {
    if (!currentSynthesisResultId) return;

    const provider = document.getElementById('synthesis-provider').value;
    const orderType = document.getElementById('synthesis-type').value;
    const codonOptimized = document.getElementById('synthesis-codon').value;
    const notes = document.getElementById('synthesis-notes').value;

    try {
        const response = await fetch(`/api/design/results/${currentSynthesisResultId}/order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                design_result_id: currentSynthesisResultId,
                provider: provider,
                order_type: orderType,
                codon_optimized_for: codonOptimized,
                notes: notes
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to place order');
        }

        showToast('Synthesis order placed!', 'success');
        hideSynthesisModal();
        loadSynthesisOrders();  // Refresh orders list

    } catch (error) {
        console.error('Error placing order:', error);
        showToast(error.message, 'error');
    }
}

// ===========================================
// SYNTHESIS ORDERS DASHBOARD
// ===========================================

let synthesisOrders = [];

async function loadSynthesisOrders() {
    const ordersList = document.getElementById('orders-list');
    const ordersEmpty = document.getElementById('orders-empty');

    if (!ordersList) return;

    try {
        const response = await fetch('/api/design/orders', { credentials: 'include' });

        if (!response.ok) {
            if (response.status === 401) {
                // User not logged in, show empty state
                ordersEmpty.style.display = 'flex';
                return;
            }
            throw new Error('Failed to load orders');
        }

        synthesisOrders = await response.json();
        renderOrders();
    } catch (error) {
        console.error('Error loading orders:', error);
        ordersEmpty.style.display = 'flex';
    }
}

function renderOrders() {
    const ordersList = document.getElementById('orders-list');
    const ordersEmpty = document.getElementById('orders-empty');

    if (synthesisOrders.length === 0) {
        ordersEmpty.style.display = 'flex';
        ordersList.querySelectorAll('.order-card').forEach(el => el.remove());
        return;
    }

    ordersEmpty.style.display = 'none';

    // Remove existing cards
    ordersList.querySelectorAll('.order-card').forEach(el => el.remove());

    // Add order cards
    synthesisOrders.forEach(order => {
        const card = document.createElement('div');
        card.className = 'order-card';
        card.innerHTML = `
            <div class="order-header">
                <span class="order-provider ${order.provider}">${formatProvider(order.provider)}</span>
                <span class="order-status ${order.status}">${formatStatus(order.status)}</span>
            </div>
            <div class="order-details">
                <div class="order-type">${formatOrderType(order.order_type)}</div>
                <div class="order-cost">Est. $${(order.estimated_cost || 0).toFixed(2)}</div>
            </div>
            <div class="order-meta">
                <span>Created ${formatDate(order.created_at)}</span>
                ${order.tracking_url ? `<a href="${order.tracking_url}" target="_blank" class="tracking-link">Track</a>` : ''}
            </div>
            <div class="order-actions">
                ${getOrderActions(order)}
            </div>
        `;
        ordersList.appendChild(card);
    });
}

function formatProvider(provider) {
    const names = {
        'twist': 'Twist Bioscience',
        'idt': 'IDT',
        'genscript': 'GenScript',
        'other': 'Other'
    };
    return names[provider] || provider;
}

function formatStatus(status) {
    const names = {
        'pending': 'Pending',
        'ordered': 'Ordered',
        'in_production': 'In Production',
        'shipped': 'Shipped',
        'delivered': 'Delivered',
        'failed': 'Failed'
    };
    return names[status] || status;
}

function formatOrderType(type) {
    const names = {
        'dna': 'DNA Synthesis',
        'plasmid': 'Plasmid Construction',
        'protein': 'Protein Expression'
    };
    return names[type] || type;
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

function getOrderActions(order) {
    switch (order.status) {
        case 'pending':
            return `<button class="btn btn-small btn-primary" onclick="updateOrderStatus('${order.id}', 'ordered')">Mark Ordered</button>`;
        case 'ordered':
            return `<button class="btn btn-small" onclick="updateOrderStatus('${order.id}', 'in_production')">In Production</button>`;
        case 'in_production':
            return `<button class="btn btn-small" onclick="updateOrderStatus('${order.id}', 'shipped')">Shipped</button>`;
        case 'shipped':
            return `<button class="btn btn-small btn-primary" onclick="updateOrderStatus('${order.id}', 'delivered')">Delivered</button>`;
        case 'delivered':
            return `<button class="btn btn-small" onclick="recordValidation('${order.id}')">Record Validation</button>`;
        default:
            return '';
    }
}

async function updateOrderStatus(orderId, newStatus) {
    try {
        const response = await fetch(`/api/design/orders/${orderId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });

        if (!response.ok) {
            throw new Error('Failed to update order');
        }

        showToast(`Order status updated to ${formatStatus(newStatus)}`, 'success');
        loadSynthesisOrders();
    } catch (error) {
        console.error('Error updating order:', error);
        showToast('Failed to update order', 'error');
    }
}

let currentValidationOrderId = null;
let validationResult = null;

function recordValidation(orderId) {
    currentValidationOrderId = orderId;
    validationResult = null;

    // Reset form
    document.getElementById('validation-type').value = 'binding_assay';
    document.getElementById('validation-result').value = '';
    document.getElementById('validation-kd').value = '';
    document.getElementById('validation-kd-unit').value = 'nM';
    document.getElementById('validation-notes').value = '';

    // Reset result button states
    document.querySelectorAll('.result-btn').forEach(btn => btn.classList.remove('selected'));

    // Show modal
    document.getElementById('validation-modal').classList.add('visible');
}

function hideValidationModal() {
    document.getElementById('validation-modal').classList.remove('visible');
    currentValidationOrderId = null;
}

function setValidationResult(result) {
    validationResult = result;
    document.getElementById('validation-result').value = result;

    // Update button states
    document.querySelectorAll('.result-btn').forEach(btn => {
        btn.classList.remove('selected');
        if (btn.classList.contains(result)) {
            btn.classList.add('selected');
        }
    });
}

async function submitValidation() {
    if (!validationResult) {
        showToast('Please select a result (Success, Partial, or Failure)', 'error');
        return;
    }

    // Find the order to get the design_result_id
    const order = synthesisOrders.find(o => o.id === currentValidationOrderId);
    if (!order) {
        showToast('Order not found', 'error');
        return;
    }

    // Get the design_id from the result (if published)
    try {
        const resultResponse = await fetch(`/api/design/results/${order.design_result_id}`);
        if (!resultResponse.ok) {
            showToast('Could not fetch design result', 'error');
            return;
        }

        const result = await resultResponse.json();
        if (!result.design_id) {
            showToast('Design must be published before recording validation. Please publish the design first.', 'error');
            return;
        }

        // Get form values
        const validationType = document.getElementById('validation-type').value;
        const kdValue = document.getElementById('validation-kd').value;
        const kdUnit = document.getElementById('validation-kd-unit').value;
        const notes = document.getElementById('validation-notes').value;

        // Build affinity string if provided
        let affinity = null;
        if (kdValue) {
            affinity = `${kdValue} ${kdUnit}`;
        }

        // Submit validation
        const response = await fetch(`/api/validations/designs/${result.design_id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                validation_type: validationType,
                result: validationResult,
                affinity: affinity,
                notes: notes
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to submit validation');
        }

        showToast('Validation recorded!', 'success');
        hideValidationModal();

    } catch (error) {
        console.error('Error submitting validation:', error);
        showToast(error.message, 'error');
    }
}

// ===========================================
// UTILITIES
// ===========================================

function showCustomTargetModal() {
    showToast('Custom target upload coming soon!', 'info');
}

function showToast(message, type = 'info') {
    // Use existing toast system if available
    if (typeof window.showToast === 'function' && window.showToast !== showToast) {
        window.showToast(message, type);
        return;
    }

    // Fallback toast
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

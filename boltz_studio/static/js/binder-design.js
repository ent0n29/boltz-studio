/**
 * Binder Design Module - BoltzGen Integration
 * Handles target selection, design job submission, results viewing, and synthesis ordering
 */

// State
let designTargets = [];
let selectedTarget = null;
let designJobs = [];
let currentCategory = 'all';
let currentJobFilter = 'all';
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
        // Build request body - use custom_target_pdb if no target_id
        const requestBody = {
            name: jobName,
            protocol: protocol,
            num_designs: numDesigns,
            binder_length_min: binderMin,
            binder_length_max: binderMax
        };

        if (selectedTarget.id) {
            requestBody.target_id = selectedTarget.id;
        } else if (selectedTarget.custom_pdb) {
            requestBody.custom_target_pdb = selectedTarget.custom_pdb;
        }

        const response = await fetch('/api/design/jobs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(requestBody)
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
    const filteredJobs = getFilteredJobs();

    if (!filteredJobs || filteredJobs.length === 0) {
        const emptyMessage = currentJobFilter === 'all'
            ? 'No design jobs yet'
            : `No ${currentJobFilter} jobs`;
        const emptyHint = currentJobFilter === 'all'
            ? 'Select a target above to start designing binders'
            : 'Try a different filter';

        list.innerHTML = `
            <div class="jobs-empty">
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                    <path d="M2 17l10 5 10-5"/>
                    <path d="M2 12l10 5 10-5"/>
                </svg>
                <p>${emptyMessage}</p>
                <p class="hint">${emptyHint}</p>
            </div>
        `;
        return;
    }

    const isRunning = (status) => ['queued', 'generating', 'folding', 'analyzing', 'filtering', 'downloading_models'].includes(status);

    list.innerHTML = filteredJobs.map(job => `
        <div class="job-card" data-job-id="${job.id}">
            <div class="job-header">
                <h4 class="job-name">${escapeHtml(job.name)}</h4>
                <div class="job-header-actions">
                    <span class="job-status ${job.status}">${formatJobStatus(job.status)}</span>
                    ${isRunning(job.status) ? `
                        <button class="btn-icon btn-cancel" onclick="cancelJob('${job.id}')" title="Cancel job">
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"/>
                                <path d="M15 9l-6 6M9 9l6 6"/>
                            </svg>
                        </button>
                    ` : `
                        <button class="btn-icon btn-delete" onclick="deleteJob('${job.id}')" title="Delete job">
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                            </svg>
                        </button>
                    `}
                </div>
            </div>
            <div class="job-meta">
                <span>Protocol: ${formatProtocol(job.protocol)}</span>
                <span>${job.num_designs} designs</span>
                <span>${formatDateTime(job.created_at)}</span>
            </div>
            ${isRunning(job.status) ? `
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
                <div class="job-error-compact">
                    ${job.error ? `<button class="btn-link" onclick="toggleJobError('${job.id}')">Show error details</button>` : ''}
                </div>
                <div class="job-error-details" id="error-${job.id}" style="display:none;">
                    ${escapeHtml(job.error || 'Unknown error')}
                </div>
            ` : ''}
        </div>
    `).join('');
}

// Job filter functions
function setJobFilter(filter) {
    currentJobFilter = filter;
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.filter === filter);
    });
    renderDesignJobs();
}

function getFilteredJobs() {
    if (!designJobs) return [];
    if (currentJobFilter === 'all') return designJobs;

    const statusMap = {
        'running': ['queued', 'generating', 'folding', 'analyzing', 'filtering', 'downloading_models'],
        'completed': ['completed'],
        'failed': ['failed', 'cancelled']
    };

    return designJobs.filter(job => statusMap[currentJobFilter]?.includes(job.status));
}

function toggleJobError(jobId) {
    const el = document.getElementById(`error-${jobId}`);
    if (el) {
        el.style.display = el.style.display === 'none' ? 'block' : 'none';
    }
}

async function cancelJob(jobId) {
    if (!confirm('Cancel this running job?')) return;

    try {
        const res = await fetch(`/api/design/jobs/${jobId}/cancel`, {
            method: 'POST',
            credentials: 'include'
        });

        if (res.ok) {
            // Update local job status
            const job = designJobs.find(j => j.id === jobId);
            if (job) job.status = 'cancelled';
            renderDesignJobs();
            if (window.showToast) showToast('Job cancelled');
        } else {
            // Cancel failed - job might be stuck, offer force delete
            if (confirm('Could not cancel job (it may be stuck). Force delete it?')) {
                await forceDeleteJob(jobId);
            }
        }
    } catch (err) {
        console.error('Failed to cancel job:', err);
        if (confirm('Could not cancel job. Force delete it?')) {
            await forceDeleteJob(jobId);
        }
    }
}

async function forceDeleteJob(jobId) {
    try {
        const res = await fetch(`/api/design/jobs/${jobId}?force=true`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (res.ok) {
            designJobs = designJobs.filter(j => j.id !== jobId);
            renderDesignJobs();
            if (window.showToast) showToast('Job force deleted');
        } else {
            const data = await res.json();
            if (window.showToast) showToast(data.detail || 'Failed to delete job', 'error');
        }
    } catch (err) {
        console.error('Failed to force delete job:', err);
        if (window.showToast) showToast('Failed to delete job', 'error');
    }
}

async function deleteJob(jobId) {
    if (!confirm('Delete this job?')) return;

    try {
        const res = await fetch(`/api/design/jobs/${jobId}`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (res.ok) {
            designJobs = designJobs.filter(j => j.id !== jobId);
            renderDesignJobs();
            if (window.showToast) showToast('Job deleted');
        } else {
            const data = await res.json();
            if (window.showToast) showToast(data.detail || 'Failed to delete job', 'error');
        }
    } catch (err) {
        console.error('Failed to delete job:', err);
        if (window.showToast) showToast('Failed to delete job', 'error');
    }
}

function formatJobStatus(status) {
    const names = {
        'queued': 'Queued',
        'downloading_models': 'Downloading',
        'generating': 'Generating',
        'folding': 'Running',
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
// RESULTS PAGE (Full Page View)
// ===========================================

async function viewJobResults(jobId) {
    navigateTo(`/design/results/${jobId}`);
}

let pageResultViewer = null;
let pageResults = [];
let pageResultIndex = 0;
let currentPageJobId = null;

// Initialize results page when it becomes visible
document.addEventListener('DOMContentLoaded', () => {
    const resultsPage = document.getElementById('results-page');
    if (resultsPage) {
        resultsPage.addEventListener('pageshow', async (e) => {
            const jobId = e.detail?.params;
            if (jobId) {
                await loadResultsPage(jobId);
            }
        });
    }
});

async function loadResultsPage(jobId) {
    currentPageJobId = jobId;

    try {
        // Load job info
        const jobResponse = await fetch(`/api/design/jobs/${jobId}`, { credentials: 'include' });
        if (jobResponse.ok) {
            const job = await jobResponse.json();
            document.getElementById('results-job-name').textContent = job.name || 'Design Results';
        }

        // Load results
        const response = await fetch(`/api/design/jobs/${jobId}/results?limit=50`);
        if (!response.ok) throw new Error('Failed to load results');

        const data = await response.json();
        pageResults = data.results;

        document.getElementById('results-total-count').textContent = pageResults.length;

        renderPageResultsList();

        if (pageResults.length > 0) {
            selectPageResult(0);
        }
    } catch (error) {
        console.error('Error loading results page:', error);
        showToast('Failed to load results', 'error');
    }
}

function renderPageResultsList() {
    const list = document.getElementById('results-page-list');

    if (pageResults.length === 0) {
        list.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-secondary);">No results found</div>';
        return;
    }

    list.innerHTML = pageResults.map((result, index) => `
        <div class="result-list-item ${index === pageResultIndex ? 'active' : ''}"
             onclick="selectPageResult(${index})">
            <div class="result-rank-badge">#${result.rank}</div>
            <div class="result-list-info">
                <div class="result-list-score">${result.plddt_score ? result.plddt_score.toFixed(1) : '-'} pLDDT</div>
                <div class="result-list-meta">${result.sequence?.length || 0} residues</div>
            </div>
        </div>
    `).join('');
}

async function selectPageResult(index) {
    pageResultIndex = index;
    const result = pageResults[index];

    // Update list selection
    document.querySelectorAll('.result-list-item').forEach((item, i) => {
        item.classList.toggle('active', i === index);
    });

    // Update detail panel
    const plddtValue = result.plddt_score ? result.plddt_score.toFixed(1) : '-';
    const plddtEl = document.getElementById('result-page-plddt');
    plddtEl.textContent = plddtValue;
    plddtEl.className = 'score-card-value ' + getScoreClass(result.plddt_score, 90, 70);

    document.getElementById('result-page-ptm').textContent = result.ptm_score ? result.ptm_score.toFixed(2) : '-';
    document.getElementById('result-page-confidence').textContent = result.confidence_score ? result.confidence_score.toFixed(2) : '-';
    document.getElementById('result-page-length').textContent = result.sequence?.length || '-';
    document.getElementById('result-page-sequence').textContent = result.sequence || '-';

    // Update publish button
    const publishBtn = document.getElementById('publish-page-result-btn');
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
    await loadPageResultStructure(result);
}

function getScoreClass(score, highThreshold, mediumThreshold) {
    if (!score) return '';
    if (score >= highThreshold) return 'high';
    if (score >= mediumThreshold) return 'medium';
    return 'low';
}

async function loadPageResultStructure(result) {
    const viewerDiv = document.getElementById('result-page-viewer');

    if (!pageResultViewer) {
        pageResultViewer = $3Dmol.createViewer(viewerDiv, {
            backgroundColor: '#f0fdfa'
        });
    }

    pageResultViewer.clear();

    // Fetch full result with structure
    try {
        const response = await fetch(`/api/design/results/${result.id}`);
        if (response.ok) {
            const fullResult = await response.json();

            if (fullResult.structure_pdb) {
                pageResultViewer.addModel(fullResult.structure_pdb, 'pdb');

                // Color by pLDDT (AlphaFold coloring)
                pageResultViewer.setStyle({}, {
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

                pageResultViewer.zoomTo();
                pageResultViewer.render();
            }
        }
    } catch (error) {
        console.error('Error loading result structure:', error);
    }
}

function sortPageResults() {
    const sortBy = document.getElementById('results-page-sort').value;

    const sortedResults = [...pageResults].sort((a, b) => {
        switch (sortBy) {
            case 'plddt':
                return (b.plddt_score || 0) - (a.plddt_score || 0);
            case 'length':
                return (b.sequence?.length || 0) - (a.sequence?.length || 0);
            case 'confidence':
                return (b.confidence_score || 0) - (a.confidence_score || 0);
            case 'rank':
            default:
                return a.rank - b.rank;
        }
    });

    pageResults = sortedResults;
    renderPageResultsList();
}

function downloadPageResultPdb() {
    const result = pageResults[pageResultIndex];
    if (result) {
        window.open(`/api/design/results/${result.id}/pdb`, '_blank');
    }
}

function copyPageSequence() {
    const result = pageResults[pageResultIndex];
    if (result?.sequence) {
        navigator.clipboard.writeText(result.sequence).then(() => {
            showToast('Sequence copied to clipboard', 'success');
        }).catch(() => {
            showToast('Failed to copy sequence', 'error');
        });
    }
}

async function publishPageResult() {
    const result = pageResults[pageResultIndex];
    if (!result || result.is_published) return;

    try {
        const response = await fetch(`/api/design/results/${result.id}/publish`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Failed to publish');

        showToast('Design published to community!', 'success');

        result.is_published = true;
        document.getElementById('publish-page-result-btn').disabled = true;
        document.getElementById('publish-page-result-btn').innerHTML = 'Published';

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
                <span>Created ${formatDateShort(order.created_at)}</span>
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

// Note: formatDate functions moved to utils.js (formatDateTime, formatDateShort)

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
// CUSTOM TARGET UPLOAD (Inline)
// ===========================================

var inlineTargetViewer = null;
var inlineTargetPdb = null;

function toggleCustomTargetUpload() {
    var zone = document.getElementById('custom-target-upload-zone');
    if (zone.style.display === 'none') {
        showCustomTargetUpload();
    } else {
        hideCustomTargetUpload();
    }
}

function showCustomTargetUpload() {
    var zone = document.getElementById('custom-target-upload-zone');
    zone.style.display = 'block';
    // Reset state
    inlineTargetPdb = null;
    document.getElementById('inline-pdb-filename').textContent = 'Drop PDB/CIF file or click to browse';
    document.getElementById('inline-target-preview').style.display = 'none';
    document.getElementById('inline-use-target-btn').disabled = true;
    var dropZone = document.getElementById('inline-pdb-drop-zone');
    if (dropZone) dropZone.classList.remove('has-file');
}

function hideCustomTargetUpload() {
    document.getElementById('custom-target-upload-zone').style.display = 'none';
    if (inlineTargetViewer) {
        inlineTargetViewer.clear();
    }
}

function handleInlineCustomPdbDrop(event) {
    event.preventDefault();
    event.target.classList.remove('dragover');
    var file = event.dataTransfer.files[0];
    if (file) {
        processInlineCustomPdbFile(file);
    }
}

function handleInlineCustomPdbSelect(event) {
    var file = event.target.files[0];
    if (file) {
        processInlineCustomPdbFile(file);
    }
}

async function processInlineCustomPdbFile(file) {
    var validExtensions = ['.pdb', '.cif', '.ent'];
    var ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));

    if (validExtensions.indexOf(ext) === -1) {
        showToast('Please upload a .pdb or .cif file', 'error');
        return;
    }

    document.getElementById('inline-pdb-filename').textContent = file.name;
    var dropZone = document.getElementById('inline-pdb-drop-zone');
    if (dropZone) dropZone.classList.add('has-file');

    try {
        var content = await file.text();
        inlineTargetPdb = content;

        // Parse basic info from PDB/CIF
        var chains = new Set();
        var residueCount = 0;

        if (ext === '.cif') {
            var chainMatches = content.match(/label_asym_id\s+(\w+)/g);
            if (chainMatches) {
                chainMatches.forEach(function(m) { chains.add(m.split(/\s+/)[1]); });
            }
            residueCount = (content.match(/^ATOM\s/gm) || []).length / 10;
        } else {
            var lines = content.split('\n');
            var seenResidues = new Set();
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i];
                if (line.indexOf('ATOM') === 0 || line.indexOf('HETATM') === 0) {
                    var chain = line.charAt(21);
                    var resNum = line.substring(22, 26).trim();
                    chains.add(chain);
                    seenResidues.add(chain + ':' + resNum);
                }
            }
            residueCount = seenResidues.size;
        }

        // Update preview info
        document.getElementById('inline-target-chains').textContent = 'Chains: ' + Array.from(chains).join(', ');
        document.getElementById('inline-target-residues').textContent = 'Residues: ~' + residueCount;

        // Show preview and enable button
        document.getElementById('inline-target-preview').style.display = 'block';
        document.getElementById('inline-use-target-btn').disabled = false;

        // Initialize 3D viewer
        var viewerDiv = document.getElementById('inline-target-viewer');
        if (!inlineTargetViewer) {
            inlineTargetViewer = $3Dmol.createViewer(viewerDiv, {
                backgroundColor: '#f0fdfa'
            });
        }
        inlineTargetViewer.clear();

        var format = ext === '.cif' ? 'cif' : 'pdb';
        inlineTargetViewer.addModel(content, format);
        inlineTargetViewer.setStyle({}, {cartoon: {color: 'spectrum'}});
        inlineTargetViewer.zoomTo();
        inlineTargetViewer.render();

    } catch (error) {
        console.error('Error processing file:', error);
        showToast('Failed to parse structure file', 'error');
    }
}

function useInlineCustomTarget() {
    if (!inlineTargetPdb) {
        showToast('Please upload a structure file first', 'error');
        return;
    }

    // Store custom target for design job
    selectedTarget = {
        id: null,
        name: 'Custom Target',
        custom_pdb: inlineTargetPdb
    };

    hideCustomTargetUpload();

    // Show design params section
    document.getElementById('design-params-section').style.display = 'block';

    // Update UI to show custom target selected
    document.querySelectorAll('.target-card').forEach(function(card) { card.classList.remove('selected'); });
    showToast('Custom target loaded! Configure your design parameters.', 'success');
}

// Legacy modal function redirect
function showCustomTargetModal() {
    toggleCustomTargetUpload();
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

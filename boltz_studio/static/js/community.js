// Community features - browse and discover designs
// OPTIMIZED: Static preview images, 3D viewer on hover only

let designsPage = 0;
let designsLoading = false;
let currentFilters = {};
let currentView = 'all';

// Performance: Only one active 3D viewer at a time (on hover)
let activeHoverViewer = null;
let activeHoverDesignId = null;
const pdbCache = new Map(); // design_id -> pdb_data

// View switching
function switchCommunityView(view) {
    currentView = view;

    // Update active tab
    document.querySelectorAll('.view-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.view === view);
    });

    // Show/hide views
    const designsView = document.getElementById('designs-view');
    const collectionsView = document.getElementById('collections-view');
    const filters = document.getElementById('community-filters');

    if (view === 'collections') {
        designsView.style.display = 'none';
        collectionsView.style.display = 'block';
        filters.style.display = 'none';
        loadCollections();
    } else {
        designsView.style.display = 'block';
        collectionsView.style.display = 'none';
        filters.style.display = 'flex';

        // Cleanup hover viewer
        cleanupHoverViewer();

        if (view === 'starred') {
            loadStarredDesigns();
        } else if (view === 'mine') {
            loadMyDesigns();
        } else {
            loadDesigns(currentFilters);
        }
    }
}

async function loadMyDesigns() {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    designsLoading = true;
    const grid = document.getElementById('designs-grid');
    grid.innerHTML = '<div class="loading">Loading your designs...</div>';

    try {
        const res = await fetch('/api/designs/mine');
        const designs = await res.json();

        grid.innerHTML = '';

        if (designs && designs.length > 0) {
            designs.forEach(design => {
                grid.appendChild(createDesignCard(design));
            });
        } else {
            grid.innerHTML = '<div class="empty-state">You haven\'t published any designs yet</div>';
        }

        document.getElementById('load-more').style.display = 'none';
    } catch (err) {
        console.error('Failed to load my designs:', err);
        grid.innerHTML = '<div class="error-state">Failed to load your designs</div>';
    }

    designsLoading = false;
}

async function loadDesigns(filters = {}) {
    if (designsLoading) return;
    designsLoading = true;

    currentFilters = filters;
    designsPage = 0;

    const grid = document.getElementById('designs-grid');
    grid.innerHTML = '<div class="loading">Loading designs...</div>';

    // Cleanup old viewers
    cleanupHoverViewer();

    try {
        const params = new URLSearchParams({
            page: '0',
            limit: '12',
            sort: filters.sort || 'recent',
            ...filters
        });

        const res = await fetch(`/api/designs?${params}`);
        const data = await res.json();

        grid.innerHTML = '';

        if (data.designs && data.designs.length > 0) {
            data.designs.forEach(design => {
                grid.appendChild(createDesignCard(design));
            });

            // Show/hide load more button
            const loadMore = document.getElementById('load-more');
            loadMore.style.display = data.has_more ? 'block' : 'none';
        } else {
            grid.innerHTML = '<div class="empty-state">No designs found</div>';
        }
    } catch (err) {
        console.error('Failed to load designs:', err);
        grid.innerHTML = '<div class="error-state">Failed to load designs</div>';
    }

    designsLoading = false;
}

async function loadMoreDesigns() {
    if (designsLoading) return;
    designsLoading = true;

    designsPage++;

    try {
        const params = new URLSearchParams({
            page: designsPage.toString(),
            limit: '12',
            sort: currentFilters.sort || 'recent',
            ...currentFilters
        });

        const res = await fetch(`/api/designs?${params}`);
        const data = await res.json();

        const grid = document.getElementById('designs-grid');

        if (data.designs && data.designs.length > 0) {
            data.designs.forEach(design => {
                grid.appendChild(createDesignCard(design));
            });
        }

        // Show/hide load more button
        const loadMore = document.getElementById('load-more');
        loadMore.style.display = data.has_more ? 'block' : 'none';
    } catch (err) {
        console.error('Failed to load more designs:', err);
        designsPage--;
    }

    designsLoading = false;
}

function createDesignCard(design) {
    const card = document.createElement('div');
    card.className = 'design-card';
    card.dataset.designId = design.id;
    card.onclick = () => showDesignModal(design.id);

    const plddt = design.plddt ? (design.plddt * 100).toFixed(0) + '%' : '-';
    const plddtClass = design.plddt >= 0.8 ? 'high' : design.plddt >= 0.5 ? 'medium' : 'low';

    // Show lineage indicator if this is a fork
    const lineageIndicator = design.parent_design_id
        ? '<span class="fork-badge" title="Forked design">Fork</span>'
        : '';

    // Use static preview image if available, otherwise show placeholder
    const previewContent = design.preview_image
        ? `<img src="data:image/png;base64,${design.preview_image}" alt="${escapeHtml(design.name)}" class="preview-image" />`
        : `<div class="viewer-placeholder">
                <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                    <path d="M2 17l10 5 10-5"/>
                    <path d="M2 12l10 5 10-5"/>
                </svg>
           </div>`;

    card.innerHTML = `
        <div class="design-card-preview" id="card-preview-${design.id}">
            ${previewContent}
            <div class="hover-viewer" id="card-viewer-${design.id}" style="display:none;"></div>
        </div>
        <div class="design-card-info">
            <h3 class="design-card-title">${escapeHtml(design.name)} ${lineageIndicator}</h3>
            <div class="design-card-meta">
                <span class="design-card-author">${escapeHtml(design.author_name || 'Anonymous')}</span>
                <span class="design-card-date">${formatDate(design.created_at)}</span>
            </div>
            <div class="design-card-stats">
                <span class="stat">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    ${design.star_count || 0}
                </span>
                <span class="stat">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="18" r="3"/>
                        <circle cx="6" cy="6" r="3"/>
                        <circle cx="18" cy="6" r="3"/>
                        <path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9"/>
                        <path d="M12 12v3"/>
                    </svg>
                    ${design.fork_count || 0}
                </span>
                <span class="stat metric-${plddtClass}">${plddt}</span>
            </div>
        </div>
    `;

    // Add hover handlers for 3D viewer (only if we have preview - meaning PDB is available)
    const previewEl = card.querySelector('.design-card-preview');
    previewEl.addEventListener('mouseenter', () => showHoverViewer(design.id));
    previewEl.addEventListener('mouseleave', () => hideHoverViewer(design.id));

    return card;
}

// Show 3D viewer on hover (lazy load PDB)
async function showHoverViewer(designId) {
    // Clean up any existing hover viewer first
    cleanupHoverViewer();

    const preview = document.getElementById(`card-preview-${designId}`);
    const viewerContainer = document.getElementById(`card-viewer-${designId}`);
    if (!preview || !viewerContainer) return;

    activeHoverDesignId = designId;

    // Check PDB cache first
    let pdbData = pdbCache.get(designId);

    if (!pdbData) {
        // Fetch PDB data
        try {
            const res = await fetch(`/api/designs/${designId}/preview`);
            if (!res.ok) return;

            const data = await res.json();
            if (data.pdb_data) {
                pdbData = data.pdb_data;
                pdbCache.set(designId, pdbData);
            }
        } catch (err) {
            console.error(`Failed to load preview for ${designId}:`, err);
            return;
        }
    }

    // Make sure we're still hovering over this card
    if (activeHoverDesignId !== designId) return;

    // Show the viewer container, hide static image
    const img = preview.querySelector('.preview-image');
    const placeholder = preview.querySelector('.viewer-placeholder');
    if (img) img.style.display = 'none';
    if (placeholder) placeholder.style.display = 'none';
    viewerContainer.style.display = 'block';

    // Create 3D viewer
    try {
        activeHoverViewer = $3Dmol.createViewer(viewerContainer, {
            backgroundColor: '#c8e6df',
            antialias: true
        });

        activeHoverViewer.addModel(pdbData, 'pdb');
        activeHoverViewer.setStyle({}, { cartoon: { color: '#0d9373' } });
        activeHoverViewer.zoomTo();
        activeHoverViewer.render();

        // Start rotation
        startHoverRotation();
    } catch (err) {
        console.error('Failed to create hover viewer:', err);
    }
}

function hideHoverViewer(designId) {
    if (activeHoverDesignId !== designId) return;

    const preview = document.getElementById(`card-preview-${designId}`);
    const viewerContainer = document.getElementById(`card-viewer-${designId}`);

    // Show static image again
    if (preview) {
        const img = preview.querySelector('.preview-image');
        const placeholder = preview.querySelector('.viewer-placeholder');
        if (img) img.style.display = 'block';
        if (placeholder) placeholder.style.display = 'flex';
    }

    // Hide and cleanup viewer
    if (viewerContainer) {
        viewerContainer.style.display = 'none';
    }

    cleanupHoverViewer();
}

let hoverRotationId = null;

function startHoverRotation() {
    if (hoverRotationId) cancelAnimationFrame(hoverRotationId);

    const rotate = () => {
        if (activeHoverViewer) {
            activeHoverViewer.rotate(0.5, 'y');
            activeHoverViewer.render();
            hoverRotationId = requestAnimationFrame(rotate);
        }
    };
    rotate();
}

function cleanupHoverViewer() {
    if (hoverRotationId) {
        cancelAnimationFrame(hoverRotationId);
        hoverRotationId = null;
    }

    if (activeHoverViewer) {
        try {
            activeHoverViewer.clear();
        } catch (e) {}
        activeHoverViewer = null;
    }

    // Clear the container HTML to remove canvas
    if (activeHoverDesignId) {
        const container = document.getElementById(`card-viewer-${activeHoverDesignId}`);
        if (container) container.innerHTML = '';
    }

    activeHoverDesignId = null;
}

async function loadStarredDesigns() {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    const grid = document.getElementById('designs-grid');
    grid.innerHTML = '<div class="loading">Loading starred designs...</div>';

    cleanupHoverViewer();

    try {
        const res = await fetch('/api/users/me/starred');
        const data = await res.json();

        grid.innerHTML = '';

        if (data.designs && data.designs.length > 0) {
            data.designs.forEach(design => {
                grid.appendChild(createDesignCard(design));
            });
        } else {
            grid.innerHTML = '<div class="empty-state">No starred designs yet</div>';
        }

        document.getElementById('load-more').style.display = 'none';
    } catch (err) {
        console.error('Failed to load starred designs:', err);
        grid.innerHTML = '<div class="error-state">Failed to load starred designs</div>';
    }
}

// Search and filter handlers - DEBOUNCED
let searchTimeout;
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const sortSelect = document.getElementById('sort-select');

    searchInput?.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            if (currentView === 'all') {
                loadDesigns({ ...currentFilters, search: e.target.value });
            }
        }, 300);
    });

    sortSelect?.addEventListener('change', (e) => {
        if (currentView === 'all') {
            loadDesigns({ ...currentFilters, sort: e.target.value });
        }
    });
});

// Cleanup on page unload
window.addEventListener('beforeunload', cleanupHoverViewer);

// Helper functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

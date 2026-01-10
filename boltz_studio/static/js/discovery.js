// Discovery features - trending, leaderboards, and recommendations

let trendingPage = 0;
let trendingLoading = false;
let currentTrendingWindow = 'week';
let leaderboardPage = 0;
let leaderboardLoading = false;
let currentLeaderboardMetric = 'reputation';

// ============================================================================
// Trending Designs
// ============================================================================

async function loadTrending(window = 'week', reset = true) {
    if (trendingLoading) return;
    trendingLoading = true;

    if (reset) {
        trendingPage = 0;
        currentTrendingWindow = window;
    }

    const grid = document.getElementById('trending-grid');
    if (!grid) {
        trendingLoading = false;
        return;
    }

    if (reset) {
        grid.innerHTML = '<div class="loading">Loading trending designs...</div>';
    }

    try {
        const params = new URLSearchParams({
            window: currentTrendingWindow,
            offset: (trendingPage * 12).toString(),
            limit: '12'
        });

        const res = await fetch(`/api/trending?${params}`);
        const data = await res.json();

        if (reset) {
            grid.innerHTML = '';
        }

        if (data.designs && data.designs.length > 0) {
            data.designs.forEach(item => {
                grid.appendChild(createTrendingCard(item));
            });

            // Show/hide load more button
            const loadMore = document.getElementById('load-more-trending');
            if (loadMore) {
                loadMore.style.display = data.has_more ? 'block' : 'none';
            }
        } else if (reset) {
            grid.innerHTML = '<div class="empty-state">No trending designs yet</div>';
        }
    } catch (err) {
        console.error('Failed to load trending:', err);
        if (reset) {
            grid.innerHTML = '<div class="error-state">Failed to load trending designs</div>';
        }
    }

    trendingLoading = false;
}

async function loadMoreTrending() {
    trendingPage++;
    await loadTrending(currentTrendingWindow, false);
}

function createTrendingCard(item) {
    const design = item.design;
    const card = document.createElement('div');
    card.className = 'design-card trending-card';
    card.dataset.designId = design.id;
    card.onclick = () => showDesignModal(design.id);

    const plddt = design.confidence_score ? (design.confidence_score * 100).toFixed(0) + '%' : '-';
    const plddtClass = design.confidence_score >= 0.8 ? 'high' : design.confidence_score >= 0.5 ? 'medium' : 'low';

    // Trending rank badge
    const rankBadge = `<span class="trending-rank">#${item.trending_rank}</span>`;

    // Use static preview image if available
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
        <div class="design-card-preview">
            ${rankBadge}
            ${previewContent}
        </div>
        <div class="design-card-info">
            <h3 class="design-card-title">${escapeHtml(design.name)}</h3>
            <div class="design-card-meta">
                <span class="design-card-author" data-author-id="${design.author_id}">${escapeHtml(design.author_name || 'Anonymous')}</span>
                <span class="design-card-date">${formatDate(design.created_at)}</span>
            </div>
            <div class="design-card-stats">
                <span class="stat trending-stat" title="Recent stars">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    +${item.recent_stars}
                </span>
                <span class="stat trending-stat" title="Recent downloads">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    +${item.recent_downloads}
                </span>
                <span class="stat trending-stat" title="Recent forks">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="18" r="3"/>
                        <circle cx="6" cy="6" r="3"/>
                        <circle cx="18" cy="6" r="3"/>
                        <path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9"/>
                        <path d="M12 12v3"/>
                    </svg>
                    +${item.recent_forks}
                </span>
                <span class="stat metric-${plddtClass}">${plddt}</span>
            </div>
        </div>
    `;

    return card;
}

function switchTrendingWindow(window) {
    // Update active button
    document.querySelectorAll('.trending-window-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.window === window);
    });

    loadTrending(window);
}

// ============================================================================
// Leaderboard
// ============================================================================

async function loadLeaderboard(metric = 'reputation', reset = true) {
    if (leaderboardLoading) return;
    leaderboardLoading = true;

    if (reset) {
        leaderboardPage = 0;
        currentLeaderboardMetric = metric;
    }

    const container = document.getElementById('leaderboard-list');
    if (!container) {
        leaderboardLoading = false;
        return;
    }

    if (reset) {
        container.innerHTML = '<div class="loading">Loading leaderboard...</div>';
    }

    try {
        const params = new URLSearchParams({
            metric: currentLeaderboardMetric,
            offset: (leaderboardPage * 20).toString(),
            limit: '20'
        });

        const res = await fetch(`/api/leaderboard?${params}`);
        const data = await res.json();

        if (reset) {
            container.innerHTML = '';
        }

        if (data.entries && data.entries.length > 0) {
            data.entries.forEach(entry => {
                container.appendChild(createLeaderboardEntry(entry));
            });

            // Show/hide load more button
            const loadMore = document.getElementById('load-more-leaderboard');
            if (loadMore) {
                loadMore.style.display = data.has_more ? 'block' : 'none';
            }
        } else if (reset) {
            container.innerHTML = '<div class="empty-state">No users on the leaderboard yet</div>';
        }
    } catch (err) {
        console.error('Failed to load leaderboard:', err);
        if (reset) {
            container.innerHTML = '<div class="error-state">Failed to load leaderboard</div>';
        }
    }

    leaderboardLoading = false;
}

async function loadMoreLeaderboard() {
    leaderboardPage++;
    await loadLeaderboard(currentLeaderboardMetric, false);
}

function createLeaderboardEntry(entry) {
    const div = document.createElement('div');
    div.className = 'leaderboard-entry';
    div.onclick = () => showProfileModal(entry.user.id);

    const rankClass = entry.rank <= 3 ? `rank-${entry.rank}` : '';

    div.innerHTML = `
        <div class="leaderboard-rank ${rankClass}">${entry.rank}</div>
        <img src="${entry.user.avatar_url || ''}" alt="" class="leaderboard-avatar">
        <div class="leaderboard-info">
            <span class="leaderboard-name">${escapeHtml(entry.user.display_name)}</span>
            <span class="leaderboard-stats">
                ${entry.total_designs} designs
            </span>
        </div>
        <div class="leaderboard-metrics">
            <span class="leaderboard-metric" title="Stars">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                </svg>
                ${entry.total_stars}
            </span>
            <span class="leaderboard-metric" title="Forks">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="18" r="3"/>
                    <circle cx="6" cy="6" r="3"/>
                    <circle cx="18" cy="6" r="3"/>
                    <path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9"/>
                    <path d="M12 12v3"/>
                </svg>
                ${entry.total_forks}
            </span>
            <span class="leaderboard-metric" title="Downloads">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                ${entry.total_downloads}
            </span>
            <span class="leaderboard-reputation" title="Reputation Score">
                ${Math.round(entry.reputation_score)}
            </span>
        </div>
    `;

    return div;
}

function switchLeaderboardMetric(metric) {
    // Update active button
    document.querySelectorAll('.leaderboard-metric-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.metric === metric);
    });

    loadLeaderboard(metric);
}

// ============================================================================
// Similar Designs
// ============================================================================

async function loadSimilarDesigns(designId) {
    const container = document.getElementById('similar-designs');
    if (!container) return;

    container.innerHTML = '<div class="loading">Finding similar designs...</div>';

    try {
        const res = await fetch(`/api/designs/${designId}/similar?limit=4`);
        const data = await res.json();

        if (data && data.length > 0) {
            container.innerHTML = '<h4>Similar Designs</h4><div class="similar-grid"></div>';
            const grid = container.querySelector('.similar-grid');

            data.forEach(item => {
                const card = createSimilarDesignCard(item);
                grid.appendChild(card);
            });
        } else {
            container.innerHTML = '';
        }
    } catch (err) {
        console.error('Failed to load similar designs:', err);
        container.innerHTML = '';
    }
}

function createSimilarDesignCard(item) {
    const design = item.design;
    const div = document.createElement('div');
    div.className = 'similar-design-card';
    div.onclick = (e) => {
        e.stopPropagation();
        showDesignModal(design.id);
    };

    const reasonText = {
        'same_tags': 'Similar tags',
        'same_author': 'Same author',
        'same_target': 'Same target',
        'sequence_similarity': 'Similar sequence'
    }[item.similarity_reason] || 'Related';

    div.innerHTML = `
        <div class="similar-preview">
            ${design.preview_image
                ? `<img src="data:image/png;base64,${design.preview_image}" alt="">`
                : '<div class="mini-placeholder"></div>'}
        </div>
        <div class="similar-info">
            <span class="similar-name">${escapeHtml(design.name)}</span>
            <span class="similar-reason">${reasonText}</span>
        </div>
    `;

    return div;
}

// ============================================================================
// Event Tracking
// ============================================================================

async function recordDesignView(designId) {
    try {
        await fetch(`/api/designs/${designId}/view`, { method: 'POST' });
    } catch (err) {
        // Silent fail - not critical
    }
}

async function recordDesignDownload(designId) {
    try {
        await fetch(`/api/designs/${designId}/download`, { method: 'POST' });
    } catch (err) {
        // Silent fail - not critical
    }
}

// ============================================================================
// View Switching
// ============================================================================

function switchToTrending() {
    // Hide other views
    const designsView = document.getElementById('designs-view');
    const collectionsView = document.getElementById('collections-view');
    const trendingView = document.getElementById('trending-view');
    const leaderboardView = document.getElementById('leaderboard-view');
    const filters = document.getElementById('community-filters');

    if (designsView) designsView.style.display = 'none';
    if (collectionsView) collectionsView.style.display = 'none';
    if (trendingView) trendingView.style.display = 'block';
    if (leaderboardView) leaderboardView.style.display = 'none';
    if (filters) filters.style.display = 'none';

    // Update tabs
    document.querySelectorAll('.view-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.view === 'trending');
    });

    loadTrending();
}

function switchToLeaderboard() {
    // Hide other views
    const designsView = document.getElementById('designs-view');
    const collectionsView = document.getElementById('collections-view');
    const trendingView = document.getElementById('trending-view');
    const leaderboardView = document.getElementById('leaderboard-view');
    const filters = document.getElementById('community-filters');

    if (designsView) designsView.style.display = 'none';
    if (collectionsView) collectionsView.style.display = 'none';
    if (trendingView) trendingView.style.display = 'none';
    if (leaderboardView) leaderboardView.style.display = 'block';
    if (filters) filters.style.display = 'none';

    // Update tabs
    document.querySelectorAll('.view-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.view === 'leaderboard');
    });

    loadLeaderboard();
}

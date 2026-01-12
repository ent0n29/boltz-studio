/**
 * Reputation and badges module for Boltz Studio.
 */

// Badge tier colors
const TIER_COLORS = {
    bronze: '#cd7f32',
    silver: '#c0c0c0',
    gold: '#ffd700',
    platinum: '#e5e4e2'
};

/**
 * Initialize reputation display in user profile.
 */
function initReputation() {
    // Check for badges on page load if logged in
    checkNewBadges();
}

/**
 * Check if user has earned any new badges.
 */
async function checkNewBadges() {
    try {
        const response = await fetch('/api/reputation/check-badges', {
            method: 'POST',
            credentials: 'include'
        });

        if (response.ok) {
            const newBadges = await response.json();
            if (newBadges && newBadges.length > 0) {
                showNewBadgeNotification(newBadges);
            }
        }
    } catch (error) {
        console.error('Error checking badges:', error);
    }
}

/**
 * Show notification for newly earned badges.
 * @param {Array} badges - List of newly earned badges
 */
function showNewBadgeNotification(badges) {
    badges.forEach(badge => {
        if (window.showToast) {
            window.showToast(
                `Badge earned: ${badge.icon || ''} ${badge.name}`,
                'success'
            );
        }
    });
}

/**
 * Load user's reputation summary.
 * @param {string} userId - User ID (optional, defaults to current user)
 * @returns {Promise<Object>} Reputation data
 */
async function loadReputation(userId = null) {
    try {
        const endpoint = userId
            ? `/api/reputation/user/${userId}`
            : '/api/reputation/me';

        const response = await fetch(endpoint, {
            credentials: 'include'
        });

        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Error loading reputation:', error);
        return null;
    }
}

/**
 * Load user's badges.
 * @param {string} userId - User ID (optional, defaults to current user)
 * @returns {Promise<Object>} Badges data
 */
async function loadBadges(userId = null) {
    try {
        const endpoint = userId
            ? `/api/reputation/badges/user/${userId}`
            : '/api/reputation/badges/me';

        const response = await fetch(endpoint, {
            credentials: 'include'
        });

        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Error loading badges:', error);
        return null;
    }
}

/**
 * Load badge progress for current user.
 * @returns {Promise<Object>} Progress data
 */
async function loadBadgeProgress() {
    try {
        const response = await fetch('/api/reputation/progress', {
            credentials: 'include'
        });

        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Error loading badge progress:', error);
        return null;
    }
}

/**
 * Load reputation breakdown for current user.
 * @returns {Promise<Object>} Breakdown data
 */
async function loadReputationBreakdown() {
    try {
        const response = await fetch('/api/reputation/breakdown', {
            credentials: 'include'
        });

        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Error loading reputation breakdown:', error);
        return null;
    }
}

/**
 * Load reputation leaderboard.
 * @param {number} offset - Pagination offset
 * @param {number} limit - Max results
 * @returns {Promise<Object>} Leaderboard data
 */
async function loadReputationLeaderboard(offset = 0, limit = 20) {
    try {
        const response = await fetch(
            `/api/reputation/leaderboard?offset=${offset}&limit=${limit}`,
            { credentials: 'include' }
        );

        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Error loading leaderboard:', error);
        return null;
    }
}

/**
 * Render reputation score badge.
 * @param {number} score - Reputation score
 * @param {number} rank - User rank (optional)
 * @returns {string} HTML string
 */
function renderReputationBadge(score, rank = null) {
    const rankHtml = rank ? `<span class="reputation-rank">#${rank}</span>` : '';
    return `
        <div class="reputation-badge">
            <span class="reputation-score">${formatNumber(score)}</span>
            <span class="reputation-label">reputation</span>
            ${rankHtml}
        </div>
    `;
}

/**
 * Render a single badge.
 * @param {Object} badge - Badge data
 * @param {Date} earnedAt - When badge was earned (optional)
 * @returns {string} HTML string
 */
function renderBadge(badge, earnedAt = null) {
    const tierClass = badge.tier ? `badge-tier-${badge.tier}` : '';
    const tierColor = badge.tier ? TIER_COLORS[badge.tier] : '#888';
    const earnedHtml = earnedAt
        ? `<span class="badge-earned-date">Earned ${formatDate(earnedAt)}</span>`
        : '';

    return `
        <div class="badge-item ${tierClass}" title="${badge.description}">
            <span class="badge-icon" style="border-color: ${tierColor}">${badge.icon || '?'}</span>
            <div class="badge-info">
                <span class="badge-name">${badge.name}</span>
                ${earnedHtml}
            </div>
        </div>
    `;
}

/**
 * Render badge progress bar.
 * @param {Object} progress - Progress data
 * @returns {string} HTML string
 */
function renderBadgeProgress(progress) {
    const tierColor = progress.badge.tier ? TIER_COLORS[progress.badge.tier] : '#888';

    return `
        <div class="badge-progress-item">
            <div class="badge-progress-header">
                <span class="badge-icon-small">${progress.badge.icon || '?'}</span>
                <span class="badge-progress-name">${progress.badge.name}</span>
            </div>
            <div class="badge-progress-bar-container">
                <div class="badge-progress-bar" style="width: ${progress.progress_percent}%; background-color: ${tierColor}"></div>
            </div>
            <span class="badge-progress-text">${progress.current_value} / ${progress.target_value}</span>
        </div>
    `;
}

/**
 * Render badges section in profile.
 * @param {Array} badges - User's earned badges
 * @returns {string} HTML string
 */
function renderBadgesSection(badges) {
    if (!badges || badges.length === 0) {
        return `
            <div class="badges-empty">
                <p>No badges earned yet</p>
                <p class="badges-hint">Complete activities to earn badges!</p>
            </div>
        `;
    }

    const badgeHtml = badges.map(b => renderBadge(b.badge, b.earned_at)).join('');

    return `
        <div class="badges-grid">
            ${badgeHtml}
        </div>
    `;
}

/**
 * Render reputation breakdown.
 * @param {Object} breakdown - Breakdown data
 * @returns {string} HTML string
 */
function renderReputationBreakdown(breakdown) {
    return `
        <div class="reputation-breakdown">
            <div class="breakdown-item">
                <span class="breakdown-label">Designs</span>
                <span class="breakdown-value">${breakdown.designs_published} x 10 = ${breakdown.designs_points}</span>
            </div>
            <div class="breakdown-item">
                <span class="breakdown-label">Stars received</span>
                <span class="breakdown-value">${breakdown.stars_received} x 5 = ${breakdown.stars_points}</span>
            </div>
            <div class="breakdown-item">
                <span class="breakdown-label">Forks received</span>
                <span class="breakdown-value">${breakdown.forks_received} x 10 = ${breakdown.forks_points}</span>
            </div>
            <div class="breakdown-item">
                <span class="breakdown-label">Comments received</span>
                <span class="breakdown-value">${breakdown.comments_received} x 2 = ${breakdown.comments_points}</span>
            </div>
            <div class="breakdown-item">
                <span class="breakdown-label">Downloads</span>
                <span class="breakdown-value">${breakdown.downloads_received} x 1 = ${breakdown.downloads_points}</span>
            </div>
            <div class="breakdown-item">
                <span class="breakdown-label">Badge bonuses</span>
                <span class="breakdown-value">${breakdown.badge_points}</span>
            </div>
            <div class="breakdown-total">
                <span class="breakdown-label">Total</span>
                <span class="breakdown-value">${breakdown.total_points}</span>
            </div>
        </div>
    `;
}

/**
 * Render leaderboard entry.
 * @param {Object} entry - Leaderboard entry
 * @returns {string} HTML string
 */
function renderLeaderboardEntry(entry) {
    const rankClass = entry.rank <= 3 ? `leaderboard-rank-${entry.rank}` : '';
    const avatar = entry.avatar_url || '/api/placeholder/40/40';

    return `
        <div class="leaderboard-entry ${rankClass}" onclick="showUserProfile('${entry.user_id}')">
            <span class="leaderboard-rank">#${entry.rank}</span>
            <img class="leaderboard-avatar" src="${avatar}" alt="${entry.display_name}" />
            <div class="leaderboard-user-info">
                <span class="leaderboard-name">${entry.display_name}</span>
                <span class="leaderboard-badges">${entry.badge_count} badges</span>
            </div>
            <span class="leaderboard-score">${formatNumber(entry.reputation_score)}</span>
        </div>
    `;
}

/**
 * Render full leaderboard.
 * @param {Object} leaderboard - Leaderboard data
 * @returns {string} HTML string
 */
function renderLeaderboard(leaderboard) {
    if (!leaderboard || leaderboard.entries.length === 0) {
        return '<p class="leaderboard-empty">No entries yet</p>';
    }

    const entriesHtml = leaderboard.entries.map(renderLeaderboardEntry).join('');

    return `
        <div class="leaderboard-list">
            ${entriesHtml}
        </div>
    `;
}

/**
 * Show reputation modal for a user.
 * @param {string} userId - User ID
 */
async function showReputationModal(userId = null) {
    const modal = document.getElementById('reputation-modal');
    if (!modal) return;

    // Load data
    const [reputation, badges, breakdown] = await Promise.all([
        loadReputation(userId),
        loadBadges(userId),
        userId ? null : loadReputationBreakdown()
    ]);

    if (!reputation) {
        if (window.showToast) {
            window.showToast('Failed to load reputation', 'error');
        }
        return;
    }

    // Update modal content
    const content = modal.querySelector('.modal-content');
    if (content) {
        content.innerHTML = `
            <div class="modal-header">
                <h2>Reputation & Badges</h2>
                <button class="modal-close" onclick="closeReputationModal()">&times;</button>
            </div>
            <div class="reputation-modal-body">
                <div class="reputation-summary">
                    ${renderReputationBadge(reputation.reputation_score, reputation.rank)}
                    <div class="reputation-stats">
                        <span>${reputation.total_badges} badges earned</span>
                    </div>
                </div>

                <h3>Badges</h3>
                ${renderBadgesSection(badges ? badges.badges : [])}

                ${breakdown ? `
                    <h3>Points Breakdown</h3>
                    ${renderReputationBreakdown(breakdown)}
                ` : ''}
            </div>
        `;
    }

    modal.style.display = 'flex';
}

/**
 * Close reputation modal.
 */
function closeReputationModal() {
    const modal = document.getElementById('reputation-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Format large numbers with K/M suffix.
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

/**
 * Format date for display.
 * @param {string|Date} date - Date to format
 * @returns {string} Formatted date
 */
function formatDate(date) {
    const d = new Date(date);
    return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
}

// Export functions for global access
window.initReputation = initReputation;
window.checkNewBadges = checkNewBadges;
window.loadReputation = loadReputation;
window.loadBadges = loadBadges;
window.loadBadgeProgress = loadBadgeProgress;
window.loadReputationBreakdown = loadReputationBreakdown;
window.loadReputationLeaderboard = loadReputationLeaderboard;
window.renderReputationBadge = renderReputationBadge;
window.renderBadge = renderBadge;
window.renderBadgesSection = renderBadgesSection;
window.renderLeaderboard = renderLeaderboard;
window.showReputationModal = showReputationModal;
window.closeReputationModal = closeReputationModal;

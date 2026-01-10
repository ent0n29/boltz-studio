// Profile features - user profiles, following, followers

let profileModalUser = null;
let isEditingProfile = false;

// Show user profile modal
async function showProfileModal(userId) {
    const modal = document.getElementById('profile-modal');
    modal.classList.add('visible');

    const content = document.getElementById('profile-content');
    content.innerHTML = '<div class="loading">Loading profile...</div>';

    try {
        const res = await fetch(`/api/users/${userId}`);
        if (!res.ok) throw new Error('User not found');

        profileModalUser = await res.json();
        renderProfileContent();
    } catch (err) {
        console.error('Failed to load profile:', err);
        content.innerHTML = '<div class="error-state">Failed to load profile</div>';
    }
}

function hideProfileModal() {
    document.getElementById('profile-modal').classList.remove('visible');
    profileModalUser = null;
    isEditingProfile = false;
}

function renderProfileContent() {
    const user = profileModalUser;
    const isOwnProfile = currentUser && currentUser.id === user.id;
    const content = document.getElementById('profile-content');

    const verifiedBadge = user.is_verified
        ? '<span class="verified-badge" title="Verified Researcher"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg></span>'
        : '';

    const orcidLink = user.orcid
        ? `<a href="https://orcid.org/${user.orcid}" target="_blank" class="orcid-link">
             <img src="https://orcid.org/assets/vectors/orcid.logo.icon.svg" alt="ORCID" width="16" height="16">
             ${user.orcid}
           </a>`
        : '';

    const websiteLink = user.website
        ? `<a href="${escapeHtml(user.website)}" target="_blank" class="profile-website">${escapeHtml(user.website)}</a>`
        : '';

    const followButton = !isOwnProfile && currentUser
        ? `<button class="btn ${user.is_following ? 'btn-outline following' : 'btn-primary'}"
                   id="follow-btn" onclick="toggleFollow('${user.id}')">
             ${user.is_following ? 'Following' : 'Follow'}
           </button>`
        : '';

    const editButton = isOwnProfile
        ? `<button class="btn btn-outline" onclick="showEditProfile()">Edit Profile</button>`
        : '';

    content.innerHTML = `
        <div class="profile-header">
            <img src="${user.avatar_url || ''}" alt="" class="profile-avatar">
            <div class="profile-info">
                <h2 class="profile-name">${escapeHtml(user.display_name)} ${verifiedBadge}</h2>
                ${user.affiliation ? `<p class="profile-affiliation">${escapeHtml(user.affiliation)}</p>` : ''}
                ${user.location ? `<p class="profile-location"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg> ${escapeHtml(user.location)}</p>` : ''}
                ${orcidLink}
                ${websiteLink}
            </div>
            <div class="profile-actions">
                ${followButton}
                ${editButton}
            </div>
        </div>

        ${user.bio ? `<p class="profile-bio">${escapeHtml(user.bio)}</p>` : ''}

        <div class="profile-stats">
            <div class="stat-item" onclick="showFollowers('${user.id}')">
                <span class="stat-value">${user.follower_count}</span>
                <span class="stat-label">Followers</span>
            </div>
            <div class="stat-item" onclick="showFollowing('${user.id}')">
                <span class="stat-value">${user.following_count}</span>
                <span class="stat-label">Following</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${user.design_count}</span>
                <span class="stat-label">Designs</span>
            </div>
        </div>

        <div class="profile-section">
            <h3>Member since</h3>
            <p>${formatDate(user.created_at)}</p>
        </div>
    `;
}

async function toggleFollow(userId) {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    const btn = document.getElementById('follow-btn');
    const isFollowing = profileModalUser.is_following;

    try {
        const res = await fetch(`/api/users/${userId}/follow`, {
            method: isFollowing ? 'DELETE' : 'POST'
        });

        if (res.ok) {
            profileModalUser.is_following = !isFollowing;
            profileModalUser.follower_count += isFollowing ? -1 : 1;
            renderProfileContent();
            showToast(isFollowing ? 'Unfollowed user' : 'Following user');
        } else {
            const data = await res.json();
            showToast(data.detail || 'Failed to update follow status', 'error');
        }
    } catch (err) {
        console.error('Failed to toggle follow:', err);
        showToast('Failed to update follow status', 'error');
    }
}

function showEditProfile() {
    if (!currentUser) return;

    const content = document.getElementById('profile-content');
    const user = profileModalUser;

    content.innerHTML = `
        <div class="edit-profile-form">
            <h2>Edit Profile</h2>

            <div class="form-group">
                <label>Display Name</label>
                <input type="text" id="edit-display-name" value="${escapeHtml(user.display_name)}" maxlength="100">
            </div>

            <div class="form-group">
                <label>Bio</label>
                <textarea id="edit-bio" placeholder="Tell us about yourself..." maxlength="500">${escapeHtml(user.bio || '')}</textarea>
            </div>

            <div class="form-group">
                <label>Affiliation</label>
                <input type="text" id="edit-affiliation" placeholder="University, Company, Lab..." value="${escapeHtml(user.affiliation || '')}" maxlength="200">
            </div>

            <div class="form-group">
                <label>Location</label>
                <input type="text" id="edit-location" placeholder="City, Country" value="${escapeHtml(user.location || '')}" maxlength="100">
            </div>

            <div class="form-group">
                <label>Website</label>
                <input type="url" id="edit-website" placeholder="https://..." value="${escapeHtml(user.website || '')}" maxlength="200">
            </div>

            <div class="form-group">
                <label>ORCID</label>
                <input type="text" id="edit-orcid" placeholder="0000-0000-0000-0000" value="${escapeHtml(user.orcid || '')}" pattern="\\d{4}-\\d{4}-\\d{4}-\\d{3}[\\dX]">
                <small>Your ORCID identifier (e.g., 0000-0002-1825-0097)</small>
            </div>

            <div class="form-actions">
                <button class="btn btn-outline" onclick="cancelEditProfile()">Cancel</button>
                <button class="btn btn-primary" onclick="saveProfile()">Save Changes</button>
            </div>
        </div>
    `;

    isEditingProfile = true;
}

function cancelEditProfile() {
    isEditingProfile = false;
    renderProfileContent();
}

async function saveProfile() {
    const updates = {
        display_name: document.getElementById('edit-display-name').value.trim(),
        bio: document.getElementById('edit-bio').value.trim() || null,
        affiliation: document.getElementById('edit-affiliation').value.trim() || null,
        location: document.getElementById('edit-location').value.trim() || null,
        website: document.getElementById('edit-website').value.trim() || null,
        orcid: document.getElementById('edit-orcid').value.trim() || null
    };

    if (!updates.display_name) {
        showToast('Display name is required', 'error');
        return;
    }

    // Validate ORCID format if provided
    if (updates.orcid && !/^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(updates.orcid)) {
        showToast('Invalid ORCID format. Use: 0000-0000-0000-0000', 'error');
        return;
    }

    try {
        const res = await fetch('/api/users/me/profile', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        if (res.ok) {
            // Update local user data
            Object.assign(profileModalUser, updates);
            if (currentUser) {
                currentUser.display_name = updates.display_name;
                updateAuthUI();
            }

            isEditingProfile = false;
            renderProfileContent();
            showToast('Profile updated successfully');
        } else {
            const data = await res.json();
            showToast(data.detail || 'Failed to update profile', 'error');
        }
    } catch (err) {
        console.error('Failed to save profile:', err);
        showToast('Failed to update profile', 'error');
    }
}

// Followers/Following lists
async function showFollowers(userId) {
    const content = document.getElementById('profile-content');
    content.innerHTML = '<div class="loading">Loading followers...</div>';

    try {
        const res = await fetch(`/api/users/${userId}/followers`);
        const data = await res.json();

        renderFollowList('Followers', data, userId);
    } catch (err) {
        console.error('Failed to load followers:', err);
        content.innerHTML = '<div class="error-state">Failed to load followers</div>';
    }
}

async function showFollowing(userId) {
    const content = document.getElementById('profile-content');
    content.innerHTML = '<div class="loading">Loading following...</div>';

    try {
        const res = await fetch(`/api/users/${userId}/following`);
        const data = await res.json();

        renderFollowList('Following', data, userId);
    } catch (err) {
        console.error('Failed to load following:', err);
        content.innerHTML = '<div class="error-state">Failed to load following</div>';
    }
}

function renderFollowList(title, data, originalUserId) {
    const content = document.getElementById('profile-content');

    const userItems = data.users.map(item => `
        <div class="follow-item" onclick="showProfileModal('${item.user.id}')">
            <img src="${item.user.avatar_url || ''}" alt="" class="follow-avatar">
            <div class="follow-info">
                <span class="follow-name">${escapeHtml(item.user.display_name)}</span>
                <span class="follow-date">Since ${formatDate(item.created_at)}</span>
            </div>
        </div>
    `).join('');

    content.innerHTML = `
        <div class="follow-list-header">
            <button class="btn btn-outline btn-small" onclick="showProfileModal('${originalUserId}')">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="15 18 9 12 15 6"/>
                </svg>
                Back
            </button>
            <h3>${title} (${data.total})</h3>
        </div>
        <div class="follow-list">
            ${userItems || '<div class="empty-state">No users yet</div>'}
        </div>
        ${data.has_more ? '<button class="btn btn-outline load-more">Load More</button>' : ''}
    `;
}

// View own profile
function viewMyProfile() {
    if (currentUser) {
        showProfileModal(currentUser.id);
    }
}

// Click on author name to view profile
function setupAuthorLinks() {
    document.addEventListener('click', (e) => {
        const authorLink = e.target.closest('[data-author-id]');
        if (authorLink) {
            e.preventDefault();
            e.stopPropagation();
            showProfileModal(authorLink.dataset.authorId);
        }
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    setupAuthorLinks();
});

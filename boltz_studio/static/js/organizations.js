/**
 * Organizations module for Boltz Studio.
 * Handles organization creation, management, and member operations.
 */

let currentOrg = null;
let orgMembers = [];
let orgMembersPage = 0;

// ============================================================================
// Organization CRUD
// ============================================================================

/**
 * Show create organization modal.
 */
function showCreateOrgModal() {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    const modal = document.getElementById('org-modal');
    if (!modal) return;

    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>Create Organization</h2>
                <button class="modal-close" onclick="hideOrgModal()">&times;</button>
            </div>
            <div class="modal-body">
                <form id="create-org-form" onsubmit="createOrganization(event)">
                    <div class="form-group">
                        <label for="org-name">Organization Name *</label>
                        <input type="text" id="org-name" required maxlength="100"
                               placeholder="My Research Lab">
                    </div>
                    <div class="form-group">
                        <label for="org-slug">URL Slug *</label>
                        <input type="text" id="org-slug" required maxlength="50"
                               pattern="[a-z0-9-]+" placeholder="my-research-lab"
                               oninput="this.value = this.value.toLowerCase().replace(/[^a-z0-9-]/g, '')">
                        <small>Only lowercase letters, numbers, and hyphens. This will be your organization's URL.</small>
                    </div>
                    <div class="form-group">
                        <label for="org-description">Description</label>
                        <textarea id="org-description" maxlength="500" rows="3"
                                  placeholder="What does your organization do?"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="org-website">Website</label>
                        <input type="url" id="org-website" placeholder="https://example.com">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn btn-outline" onclick="hideOrgModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Create Organization</button>
                    </div>
                </form>
            </div>
        </div>
    `;

    modal.style.display = 'flex';

    // Auto-generate slug from name
    document.getElementById('org-name').addEventListener('input', (e) => {
        const slug = e.target.value
            .toLowerCase()
            .replace(/[^a-z0-9\s-]/g, '')
            .replace(/\s+/g, '-')
            .substring(0, 50);
        document.getElementById('org-slug').value = slug;
    });
}

/**
 * Create a new organization.
 */
async function createOrganization(event) {
    event.preventDefault();

    const data = {
        name: document.getElementById('org-name').value.trim(),
        slug: document.getElementById('org-slug').value.trim(),
        description: document.getElementById('org-description').value.trim() || null,
        website: document.getElementById('org-website').value.trim() || null
    };

    if (!data.name || !data.slug) {
        showToast('Name and slug are required', 'error');
        return;
    }

    try {
        const res = await fetch('/api/organizations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (res.ok) {
            const result = await res.json();
            showToast('Organization created successfully!');
            hideOrgModal();
            // Show the new org
            showOrgProfile(data.slug);
        } else {
            const error = await res.json();
            showToast(error.detail || 'Failed to create organization', 'error');
        }
    } catch (err) {
        console.error('Failed to create organization:', err);
        showToast('Failed to create organization', 'error');
    }
}

/**
 * Show organization profile page.
 */
async function showOrgProfile(slug) {
    const modal = document.getElementById('org-modal');
    if (!modal) return;

    modal.innerHTML = `
        <div class="modal-content org-profile-modal">
            <div class="modal-header">
                <button class="modal-close" onclick="hideOrgModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="loading">Loading organization...</div>
            </div>
        </div>
    `;
    modal.style.display = 'flex';

    try {
        const res = await fetch(`/api/organizations/${slug}`);
        if (!res.ok) throw new Error('Organization not found');

        currentOrg = await res.json();
        renderOrgProfile();
    } catch (err) {
        console.error('Failed to load organization:', err);
        modal.querySelector('.modal-body').innerHTML =
            '<div class="error-state">Organization not found</div>';
    }
}

/**
 * Render organization profile content.
 */
function renderOrgProfile() {
    const org = currentOrg;
    const modal = document.getElementById('org-modal');
    const body = modal.querySelector('.modal-body');

    const verifiedBadge = org.is_verified
        ? '<span class="verified-badge" title="Verified Organization"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg></span>'
        : '';

    body.innerHTML = `
        <div class="org-header">
            <div class="org-avatar">
                ${org.avatar_url
                    ? `<img src="${org.avatar_url}" alt="${escapeHtml(org.name)}">`
                    : `<span class="org-avatar-placeholder">${org.name.charAt(0).toUpperCase()}</span>`
                }
            </div>
            <div class="org-info">
                <h2 class="org-name">${escapeHtml(org.name)} ${verifiedBadge}</h2>
                <span class="org-slug">@${escapeHtml(org.slug)}</span>
                ${org.website ? `<a href="${escapeHtml(org.website)}" target="_blank" class="org-website">${escapeHtml(org.website)}</a>` : ''}
            </div>
        </div>

        ${org.description ? `<p class="org-description">${escapeHtml(org.description)}</p>` : ''}

        <div class="org-stats">
            <div class="stat-item">
                <span class="stat-value">${org.member_count}</span>
                <span class="stat-label">Members</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${org.design_count}</span>
                <span class="stat-label">Designs</span>
            </div>
        </div>

        <div class="org-tabs">
            <button class="org-tab active" onclick="showOrgMembers()">Members</button>
            <button class="org-tab" onclick="showOrgSettings()">Settings</button>
        </div>

        <div id="org-tab-content">
            <div class="loading">Loading members...</div>
        </div>
    `;

    // Load members by default
    showOrgMembers();
}

/**
 * Show organization members tab.
 */
async function showOrgMembers() {
    // Update active tab
    document.querySelectorAll('.org-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelector('.org-tab:first-child')?.classList.add('active');

    const content = document.getElementById('org-tab-content');
    content.innerHTML = '<div class="loading">Loading members...</div>';

    try {
        const res = await fetch(`/api/organizations/${currentOrg.slug}/members`);
        if (!res.ok) throw new Error('Failed to load members');

        const data = await res.json();
        orgMembers = data.members;

        renderOrgMembers(data);
    } catch (err) {
        console.error('Failed to load members:', err);
        content.innerHTML = '<div class="error-state">Failed to load members</div>';
    }
}

/**
 * Render organization members list.
 */
function renderOrgMembers(data) {
    const content = document.getElementById('org-tab-content');

    const memberItems = data.members.map(member => {
        const roleClass = `member-role-${member.role}`;
        const roleBadge = member.role !== 'member'
            ? `<span class="role-badge ${roleClass}">${member.role}</span>`
            : '';

        return `
            <div class="member-item" onclick="showProfileModal('${member.user.id}')">
                <img src="${member.user.avatar_url || ''}" alt="" class="member-avatar">
                <div class="member-info">
                    <span class="member-name">${escapeHtml(member.user.display_name)}</span>
                    ${roleBadge}
                </div>
                <span class="member-joined">Joined ${formatDate(member.joined_at)}</span>
            </div>
        `;
    }).join('');

    const canManageMembers = currentUser && checkOrgPermission('admin');
    const addMemberBtn = canManageMembers
        ? `<button class="btn btn-primary btn-small" onclick="showAddMemberModal()">Add Member</button>`
        : '';

    content.innerHTML = `
        <div class="members-header">
            <span class="members-count">${data.total} members</span>
            ${addMemberBtn}
        </div>
        <div class="members-list">
            ${memberItems || '<div class="empty-state">No members yet</div>'}
        </div>
    `;
}

/**
 * Show organization settings tab.
 */
function showOrgSettings() {
    // Update active tab
    document.querySelectorAll('.org-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelector('.org-tab:last-child')?.classList.add('active');

    const content = document.getElementById('org-tab-content');
    const canEdit = currentUser && checkOrgPermission('admin');

    if (!canEdit) {
        content.innerHTML = '<div class="empty-state">You don\'t have permission to edit settings</div>';
        return;
    }

    const org = currentOrg;

    content.innerHTML = `
        <form id="org-settings-form" onsubmit="saveOrgSettings(event)">
            <div class="form-group">
                <label>Organization Name</label>
                <input type="text" id="settings-name" value="${escapeHtml(org.name)}" maxlength="100">
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea id="settings-description" maxlength="500" rows="3">${escapeHtml(org.description || '')}</textarea>
            </div>
            <div class="form-group">
                <label>Website</label>
                <input type="url" id="settings-website" value="${escapeHtml(org.website || '')}">
            </div>
            <div class="form-actions">
                <button type="submit" class="btn btn-primary">Save Changes</button>
            </div>
        </form>

        ${checkOrgPermission('owner') ? `
            <div class="danger-zone">
                <h4>Danger Zone</h4>
                <button class="btn btn-danger" onclick="confirmDeleteOrg()">Delete Organization</button>
            </div>
        ` : ''}
    `;
}

/**
 * Save organization settings.
 */
async function saveOrgSettings(event) {
    event.preventDefault();

    const updates = {
        name: document.getElementById('settings-name').value.trim(),
        description: document.getElementById('settings-description').value.trim() || null,
        website: document.getElementById('settings-website').value.trim() || null
    };

    try {
        const res = await fetch(`/api/organizations/${currentOrg.slug}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        if (res.ok) {
            Object.assign(currentOrg, updates);
            showToast('Settings saved');
            renderOrgProfile();
        } else {
            const error = await res.json();
            showToast(error.detail || 'Failed to save settings', 'error');
        }
    } catch (err) {
        console.error('Failed to save settings:', err);
        showToast('Failed to save settings', 'error');
    }
}

/**
 * Confirm and delete organization.
 */
async function confirmDeleteOrg() {
    if (!confirm(`Are you sure you want to delete "${currentOrg.name}"? This cannot be undone.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/organizations/${currentOrg.slug}`, {
            method: 'DELETE'
        });

        if (res.ok) {
            showToast('Organization deleted');
            hideOrgModal();
        } else {
            const error = await res.json();
            showToast(error.detail || 'Failed to delete organization', 'error');
        }
    } catch (err) {
        console.error('Failed to delete organization:', err);
        showToast('Failed to delete organization', 'error');
    }
}

// ============================================================================
// Member Management
// ============================================================================

/**
 * Show add member modal.
 */
function showAddMemberModal() {
    const content = document.getElementById('org-tab-content');

    content.innerHTML = `
        <div class="add-member-form">
            <h4>Add Member</h4>
            <div class="form-group">
                <label>User ID</label>
                <input type="text" id="add-member-id" placeholder="Enter user ID">
                <small>You can find a user's ID on their profile page</small>
            </div>
            <div class="form-group">
                <label>Role</label>
                <select id="add-member-role">
                    <option value="member">Member</option>
                    ${checkOrgPermission('owner') ? '<option value="admin">Admin</option>' : ''}
                </select>
            </div>
            <div class="form-actions">
                <button class="btn btn-outline" onclick="showOrgMembers()">Cancel</button>
                <button class="btn btn-primary" onclick="addOrgMember()">Add Member</button>
            </div>
        </div>
    `;
}

/**
 * Add a member to the organization.
 */
async function addOrgMember() {
    const userId = document.getElementById('add-member-id').value.trim();
    const role = document.getElementById('add-member-role').value;

    if (!userId) {
        showToast('User ID is required', 'error');
        return;
    }

    try {
        const res = await fetch(`/api/organizations/${currentOrg.slug}/members`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, role: role })
        });

        if (res.ok) {
            showToast('Member added successfully');
            showOrgMembers();
        } else {
            const error = await res.json();
            showToast(error.detail || 'Failed to add member', 'error');
        }
    } catch (err) {
        console.error('Failed to add member:', err);
        showToast('Failed to add member', 'error');
    }
}

/**
 * Remove a member from the organization.
 */
async function removeOrgMember(userId) {
    if (!confirm('Are you sure you want to remove this member?')) {
        return;
    }

    try {
        const res = await fetch(`/api/organizations/${currentOrg.slug}/members/${userId}`, {
            method: 'DELETE'
        });

        if (res.ok) {
            showToast('Member removed');
            showOrgMembers();
        } else {
            const error = await res.json();
            showToast(error.detail || 'Failed to remove member', 'error');
        }
    } catch (err) {
        console.error('Failed to remove member:', err);
        showToast('Failed to remove member', 'error');
    }
}

// ============================================================================
// User's Organizations
// ============================================================================

/**
 * Load user's organizations for the profile/menu.
 */
async function loadMyOrganizations() {
    try {
        const res = await fetch('/api/organizations/me/list');
        if (res.ok) {
            return await res.json();
        }
        return [];
    } catch (err) {
        console.error('Failed to load organizations:', err);
        return [];
    }
}

/**
 * Render organizations list in user menu.
 */
async function renderMyOrganizations(container) {
    const orgs = await loadMyOrganizations();

    if (orgs.length === 0) {
        container.innerHTML = `
            <div class="empty-state-small">
                <p>No organizations yet</p>
                <button class="btn btn-small btn-primary" onclick="showCreateOrgModal()">Create One</button>
            </div>
        `;
        return;
    }

    const orgItems = orgs.map(org => `
        <div class="org-item" onclick="showOrgProfile('${org.slug}')">
            <div class="org-item-avatar">
                ${org.avatar_url
                    ? `<img src="${org.avatar_url}" alt="">`
                    : `<span>${org.name.charAt(0).toUpperCase()}</span>`
                }
            </div>
            <div class="org-item-info">
                <span class="org-item-name">${escapeHtml(org.name)}</span>
                <span class="org-item-members">${org.member_count} members</span>
            </div>
        </div>
    `).join('');

    container.innerHTML = `
        <div class="org-list">
            ${orgItems}
        </div>
        <button class="btn btn-small btn-outline" onclick="showCreateOrgModal()">Create Organization</button>
    `;
}

// ============================================================================
// Utilities
// ============================================================================

/**
 * Check if current user has permission for org action.
 */
function checkOrgPermission(requiredRole) {
    if (!currentUser || !currentOrg) return false;

    // Find current user in members
    const member = orgMembers.find(m => m.user.id === currentUser.id);
    if (!member) return false;

    if (requiredRole === 'owner') {
        return member.role === 'owner';
    }
    if (requiredRole === 'admin') {
        return member.role === 'owner' || member.role === 'admin';
    }
    return true; // member
}

/**
 * Hide organization modal.
 */
function hideOrgModal() {
    const modal = document.getElementById('org-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentOrg = null;
    orgMembers = [];
}

/**
 * Browse all organizations.
 */
async function browseOrganizations() {
    const modal = document.getElementById('org-modal');
    if (!modal) return;

    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>Organizations</h2>
                <button class="modal-close" onclick="hideOrgModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="loading">Loading organizations...</div>
            </div>
        </div>
    `;
    modal.style.display = 'flex';

    try {
        const res = await fetch('/api/organizations?limit=50');
        if (!res.ok) throw new Error('Failed to load organizations');

        const orgs = await res.json();
        const body = modal.querySelector('.modal-body');

        if (orgs.length === 0) {
            body.innerHTML = `
                <div class="empty-state">
                    <p>No organizations yet</p>
                    <button class="btn btn-primary" onclick="showCreateOrgModal()">Create the first one</button>
                </div>
            `;
            return;
        }

        const orgItems = orgs.map(org => `
            <div class="org-browse-item" onclick="showOrgProfile('${org.slug}')">
                <div class="org-browse-avatar">
                    ${org.avatar_url
                        ? `<img src="${org.avatar_url}" alt="">`
                        : `<span>${org.name.charAt(0).toUpperCase()}</span>`
                    }
                </div>
                <div class="org-browse-info">
                    <span class="org-browse-name">${escapeHtml(org.name)}</span>
                    <span class="org-browse-members">${org.member_count} members</span>
                </div>
                ${org.is_verified ? '<span class="verified-badge">✓</span>' : ''}
            </div>
        `).join('');

        body.innerHTML = `
            <div class="org-browse-actions">
                <button class="btn btn-primary" onclick="showCreateOrgModal()">Create Organization</button>
            </div>
            <div class="org-browse-list">
                ${orgItems}
            </div>
        `;
    } catch (err) {
        console.error('Failed to load organizations:', err);
        modal.querySelector('.modal-body').innerHTML =
            '<div class="error-state">Failed to load organizations</div>';
    }
}

// Export functions
window.showCreateOrgModal = showCreateOrgModal;
window.createOrganization = createOrganization;
window.showOrgProfile = showOrgProfile;
window.hideOrgModal = hideOrgModal;
window.showOrgMembers = showOrgMembers;
window.showOrgSettings = showOrgSettings;
window.saveOrgSettings = saveOrgSettings;
window.confirmDeleteOrg = confirmDeleteOrg;
window.showAddMemberModal = showAddMemberModal;
window.addOrgMember = addOrgMember;
window.removeOrgMember = removeOrgMember;
window.loadMyOrganizations = loadMyOrganizations;
window.renderMyOrganizations = renderMyOrganizations;
window.browseOrganizations = browseOrganizations;

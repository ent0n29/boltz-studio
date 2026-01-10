// Authentication management
let currentUser = null;

// Check auth status on page load
async function checkAuth() {
    try {
        const res = await fetch('/auth/me');
        if (res.ok) {
            currentUser = await res.json();
            updateAuthUI();
        }
    } catch (err) {
        console.error('Auth check failed:', err);
    }
}

function updateAuthUI() {
    const authContainer = document.getElementById('auth-container');
    const notificationContainer = document.getElementById('notification-container');
    const saveBtn = document.getElementById('save-btn');
    const commentForm = document.getElementById('comment-form');

    if (currentUser) {
        authContainer.innerHTML = `
            <div class="user-menu">
                <button class="user-button" onclick="toggleUserMenu()">
                    <img src="${currentUser.avatar_url || ''}" alt="${currentUser.display_name}" class="user-avatar">
                    <span class="user-name">${currentUser.display_name}</span>
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"/>
                    </svg>
                </button>
                <div class="user-dropdown" id="user-dropdown">
                    <a href="#" onclick="viewMyProfile(); return false;">My Profile</a>
                    <a href="#" onclick="switchTab('collections'); return false;">My Collections</a>
                    <a href="#" onclick="viewMyDesigns(); return false;">My Designs</a>
                    <a href="#" onclick="viewStarred(); return false;">Starred</a>
                    <hr>
                    <a href="#" onclick="logout(); return false;">Sign Out</a>
                </div>
            </div>
        `;

        // Show notification bell
        if (notificationContainer) {
            notificationContainer.style.display = 'block';
        }

        // Initialize notifications
        if (typeof initNotifications === 'function') {
            initNotifications();
        }

        // Show save button if there's a prediction
        if (saveBtn && window.currentPdbData) {
            saveBtn.style.display = 'block';
        }

        // Show comment form
        if (commentForm) {
            commentForm.style.display = 'block';
        }
    } else {
        authContainer.innerHTML = `
            <button class="btn btn-outline" id="login-btn" onclick="showLoginModal()">Sign In</button>
        `;

        // Hide notification bell
        if (notificationContainer) {
            notificationContainer.style.display = 'none';
        }

        // Hide save button
        if (saveBtn) {
            saveBtn.style.display = 'none';
        }

        // Hide comment form
        if (commentForm) {
            commentForm.style.display = 'none';
        }
    }
}

function toggleUserMenu() {
    const dropdown = document.getElementById('user-dropdown');
    dropdown.classList.toggle('visible');
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const userMenu = document.querySelector('.user-menu');
    const dropdown = document.getElementById('user-dropdown');
    if (userMenu && dropdown && !userMenu.contains(e.target)) {
        dropdown.classList.remove('visible');
    }
});

function showLoginModal() {
    document.getElementById('login-modal').classList.add('visible');
}

function hideLoginModal() {
    document.getElementById('login-modal').classList.remove('visible');
}

async function logout() {
    try {
        await fetch('/auth/logout', { method: 'POST' });
        currentUser = null;
        updateAuthUI();
    } catch (err) {
        console.error('Logout failed:', err);
    }
}

function viewMyDesigns() {
    switchTab('community');
    // Filter to show only user's designs
    loadDesigns({ user_id: currentUser.id });
}

function viewStarred() {
    switchTab('community');
    loadStarredDesigns();
}

// Initialize auth on page load
document.addEventListener('DOMContentLoaded', checkAuth);

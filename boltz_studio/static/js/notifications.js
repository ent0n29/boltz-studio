// Notifications system

let notificationsOpen = false;
let notificationsLoading = false;
let unreadCount = 0;

// Initialize notifications (called after auth check)
async function initNotifications() {
    if (!currentUser) return;

    // Initial count check
    await updateUnreadCount();

    // Poll for new notifications every 30 seconds
    setInterval(updateUnreadCount, 30000);
}

// Update unread count
async function updateUnreadCount() {
    if (!currentUser) return;

    try {
        const res = await fetch('/api/notifications/unread-count');
        if (res.ok) {
            const data = await res.json();
            unreadCount = data.count;
            updateNotificationBadge();
        }
    } catch (err) {
        console.error('Failed to get unread count:', err);
    }
}

// Update the badge in the UI
function updateNotificationBadge() {
    const badge = document.getElementById('notification-badge');
    if (badge) {
        if (unreadCount > 0) {
            badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }
}

// Toggle notifications panel
function toggleNotifications() {
    const panel = document.getElementById('notifications-panel');
    if (!panel) return;

    notificationsOpen = !notificationsOpen;

    if (notificationsOpen) {
        panel.classList.add('visible');
        loadNotifications();
    } else {
        panel.classList.remove('visible');
    }
}

// Close notifications when clicking outside
document.addEventListener('click', (e) => {
    if (notificationsOpen) {
        const panel = document.getElementById('notifications-panel');
        const bell = document.getElementById('notification-bell');
        if (panel && bell && !panel.contains(e.target) && !bell.contains(e.target)) {
            notificationsOpen = false;
            panel.classList.remove('visible');
        }
    }
});

// Load notifications
async function loadNotifications() {
    if (notificationsLoading) return;
    notificationsLoading = true;

    const list = document.getElementById('notifications-list');
    if (!list) return;

    list.innerHTML = '<div class="loading">Loading notifications...</div>';

    try {
        const res = await fetch('/api/notifications?limit=20');
        const data = await res.json();

        if (data.notifications && data.notifications.length > 0) {
            list.innerHTML = '';
            data.notifications.forEach(notification => {
                list.appendChild(createNotificationItem(notification));
            });
        } else {
            list.innerHTML = '<div class="empty-state">No notifications yet</div>';
        }

        // Update unread count
        unreadCount = data.unread_count;
        updateNotificationBadge();
    } catch (err) {
        console.error('Failed to load notifications:', err);
        list.innerHTML = '<div class="error-state">Failed to load notifications</div>';
    }

    notificationsLoading = false;
}

// Create notification item
function createNotificationItem(notification) {
    const div = document.createElement('div');
    div.className = `notification-item ${notification.is_read ? '' : 'unread'}`;
    div.onclick = () => handleNotificationClick(notification);

    const iconMap = {
        star: `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="none">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
               </svg>`,
        fork: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="18" r="3"/>
                <circle cx="6" cy="6" r="3"/>
                <circle cx="18" cy="6" r="3"/>
                <path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9"/>
                <path d="M12 12v3"/>
               </svg>`,
        comment: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                   <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>`,
        follow: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                  <circle cx="8.5" cy="7" r="4"/>
                  <line x1="20" y1="8" x2="20" y2="14"/>
                  <line x1="23" y1="11" x2="17" y2="11"/>
                 </svg>`,
    };

    const actorAvatar = notification.actor?.avatar_url
        ? `<img src="${notification.actor.avatar_url}" alt="" class="notification-avatar">`
        : '';

    div.innerHTML = `
        <div class="notification-icon notification-icon-${notification.type}">
            ${iconMap[notification.type] || ''}
        </div>
        <div class="notification-content">
            ${actorAvatar}
            <p class="notification-message">${escapeHtml(notification.message)}</p>
            <span class="notification-time">${formatTimeAgo(notification.created_at)}</span>
        </div>
        ${!notification.is_read ? '<span class="notification-unread-dot"></span>' : ''}
    `;

    return div;
}

// Handle notification click
async function handleNotificationClick(notification) {
    // Mark as read
    if (!notification.is_read) {
        try {
            await fetch(`/api/notifications/${notification.id}/read`, { method: 'POST' });
            notification.is_read = true;
            unreadCount = Math.max(0, unreadCount - 1);
            updateNotificationBadge();
        } catch (err) {
            console.error('Failed to mark notification as read:', err);
        }
    }

    // Navigate to target
    if (notification.target_type === 'design' && notification.target_id) {
        toggleNotifications();
        showDesignModal(notification.target_id);
    } else if (notification.target_type === 'user' && notification.actor?.id) {
        toggleNotifications();
        showProfileModal(notification.actor.id);
    }
}

// Mark all as read
async function markAllNotificationsRead() {
    try {
        const res = await fetch('/api/notifications/read-all', { method: 'POST' });
        if (res.ok) {
            unreadCount = 0;
            updateNotificationBadge();

            // Update UI
            document.querySelectorAll('.notification-item.unread').forEach(item => {
                item.classList.remove('unread');
                const dot = item.querySelector('.notification-unread-dot');
                if (dot) dot.remove();
            });

            showToast('All notifications marked as read');
        }
    } catch (err) {
        console.error('Failed to mark all as read:', err);
        showToast('Failed to mark notifications as read', 'error');
    }
}

// Format time ago
function formatTimeAgo(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

    return formatDate(dateStr);
}

// Show notification preferences modal
function showNotificationPreferences() {
    // TODO: Implement preferences modal
    showToast('Notification preferences coming soon');
}

// Initialize on auth state change
document.addEventListener('DOMContentLoaded', () => {
    // Will be called after auth check in auth.js
});

/**
 * Boltz Studio - Shared Utilities
 * Common utility functions used across the application
 */

// ============================================
// STRING UTILITIES
// ============================================

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} text - Raw text to escape
 * @returns {string} HTML-safe string
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// DATE FORMATTING
// ============================================

/**
 * Format a date string with month, day, and year
 * Example: "Jan 13, 2026"
 * @param {string|Date} dateStr - Date string or Date object
 * @returns {string} Formatted date
 */
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
}

/**
 * Format a date string with month, day, and time
 * Example: "Jan 13, 3:21 PM"
 * @param {string|Date} dateStr - Date string or Date object
 * @returns {string} Formatted date with time
 */
function formatDateTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });
}

/**
 * Format a date string as simple locale date
 * Example: "1/13/2026"
 * @param {string|Date} dateStr - Date string or Date object
 * @returns {string} Locale formatted date
 */
function formatDateShort(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

/**
 * Format a date as relative time ago
 * Examples: "Today", "Yesterday", "3d ago", "2w ago", "1mo ago", "1y ago"
 * @param {string|Date} dateStr - Date string or Date object
 * @returns {string} Relative time string
 */
function formatTimeAgo(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return diffDays + 'd ago';
    if (diffDays < 30) return Math.floor(diffDays / 7) + 'w ago';
    if (diffDays < 365) return Math.floor(diffDays / 30) + 'mo ago';
    return Math.floor(diffDays / 365) + 'y ago';
}

// ============================================
// FUNCTION UTILITIES
// ============================================

/**
 * Debounce a function to limit how often it's called
 * @param {Function} func - Function to debounce
 * @param {number} wait - Milliseconds to wait
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle a function to only run once per time period
 * @param {Function} func - Function to throttle
 * @param {number} limit - Minimum milliseconds between calls
 * @returns {Function} Throttled function
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ============================================
// DOM UTILITIES
// ============================================

/**
 * Safely get an element by ID
 * @param {string} id - Element ID
 * @returns {HTMLElement|null} Element or null
 */
function $(id) {
    return document.getElementById(id);
}

/**
 * Query selector shorthand
 * @param {string} selector - CSS selector
 * @param {HTMLElement} [parent=document] - Parent element to search within
 * @returns {HTMLElement|null} First matching element or null
 */
function $q(selector, parent = document) {
    return parent.querySelector(selector);
}

/**
 * Query selector all shorthand
 * @param {string} selector - CSS selector
 * @param {HTMLElement} [parent=document] - Parent element to search within
 * @returns {NodeList} All matching elements
 */
function $qa(selector, parent = document) {
    return parent.querySelectorAll(selector);
}

// ============================================
// CLIPBOARD UTILITIES
// ============================================

/**
 * Copy text to clipboard with toast notification
 * @param {string} text - Text to copy
 * @param {string} [successMessage='Copied to clipboard'] - Success message
 * @returns {Promise<boolean>} Success status
 */
async function copyToClipboard(text, successMessage = 'Copied to clipboard') {
    try {
        await navigator.clipboard.writeText(text);
        if (typeof showToast === 'function') {
            showToast(successMessage, 'success');
        }
        return true;
    } catch (err) {
        console.error('Failed to copy:', err);
        if (typeof showToast === 'function') {
            showToast('Failed to copy', 'error');
        }
        return false;
    }
}

// ============================================
// VALIDATION UTILITIES
// ============================================

/**
 * Check if a string is a valid protein sequence (amino acids only)
 * @param {string} sequence - Sequence to validate
 * @returns {boolean} True if valid
 */
function isValidProteinSequence(sequence) {
    if (!sequence) return false;
    const validAminoAcids = /^[ACDEFGHIKLMNPQRSTVWY]+$/i;
    return validAminoAcids.test(sequence.replace(/\s/g, ''));
}

/**
 * Check if a string is a valid SMILES notation
 * @param {string} smiles - SMILES string to validate
 * @returns {boolean} True if valid (basic check)
 */
function isValidSmiles(smiles) {
    if (!smiles) return false;
    // Basic SMILES validation - contains valid characters
    const validSmiles = /^[A-Za-z0-9@+\-\[\]\(\)\\\/=#%\.\$:]+$/;
    return validSmiles.test(smiles);
}

// ============================================
// NUMBER FORMATTING
// ============================================

/**
 * Format a number with k/M/B suffixes
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
function formatNumber(num) {
    if (num >= 1000000000) return (num / 1000000000).toFixed(1) + 'B';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return num.toString();
}

/**
 * Format a percentage
 * @param {number} value - Value between 0 and 1 (or 0 and 100)
 * @param {number} [decimals=0] - Decimal places
 * @returns {string} Formatted percentage with % symbol
 */
function formatPercent(value, decimals = 0) {
    if (value === null || value === undefined) return '-';
    // Handle both 0-1 and 0-100 ranges
    const pct = value <= 1 ? value * 100 : value;
    return pct.toFixed(decimals) + '%';
}

// ============================================
// URL UTILITIES
// ============================================

/**
 * Get URL query parameters as an object
 * @returns {Object} Query parameters
 */
function getQueryParams() {
    const params = {};
    const search = window.location.search.substring(1);
    if (search) {
        search.split('&').forEach(pair => {
            const [key, value] = pair.split('=');
            params[decodeURIComponent(key)] = decodeURIComponent(value || '');
        });
    }
    return params;
}

/**
 * Build a query string from an object
 * @param {Object} params - Parameters object
 * @returns {string} Query string (without leading ?)
 */
function buildQueryString(params) {
    return Object.entries(params)
        .filter(([_, v]) => v !== null && v !== undefined && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&');
}

// ============================================
// LOCAL STORAGE UTILITIES
// ============================================

/**
 * Safely get item from localStorage with JSON parsing
 * @param {string} key - Storage key
 * @param {*} [defaultValue=null] - Default value if not found
 * @returns {*} Parsed value or default
 */
function getStorageItem(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch {
        return defaultValue;
    }
}

/**
 * Safely set item in localStorage with JSON stringification
 * @param {string} key - Storage key
 * @param {*} value - Value to store
 * @returns {boolean} Success status
 */
function setStorageItem(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch {
        return false;
    }
}

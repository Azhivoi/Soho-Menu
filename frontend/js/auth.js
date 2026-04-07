/**
 * Unified Auth System for SOHO Cafe
 * Handles: customers (phone+pass), employees (PIN), admins (email+pass)
 */

const AUTH_CONFIG = {
    tokenKey: 'soho_auth_token',
    userKey: 'soho_auth',
    apiUrl: '/api'
};

// Check if user is authenticated
function isAuthenticated() {
    return !!localStorage.getItem(AUTH_CONFIG.tokenKey);
}

// Get current user info
function getCurrentUser() {
    const userJson = localStorage.getItem(AUTH_CONFIG.userKey);
    return userJson ? JSON.parse(userJson) : null;
}

// Get auth token
function getAuthToken() {
    return localStorage.getItem(AUTH_CONFIG.tokenKey);
}

// Set auth data
function setAuth(token, user) {
    localStorage.setItem(AUTH_CONFIG.tokenKey, token);
    localStorage.setItem(AUTH_CONFIG.userKey, JSON.stringify(user));
}

// Clear auth (logout)
function clearAuth() {
    localStorage.removeItem(AUTH_CONFIG.tokenKey);
    localStorage.removeItem(AUTH_CONFIG.userKey);
}

// Check permission
function hasPermission(permission) {
    const user = getCurrentUser();
    if (!user) return false;
    
    // Admin has all permissions
    if (user.type === 'admin' || user.role === 'admin') return true;
    
    // Check specific permission
    const perms = user.permissions || {};
    const parts = permission.split('.');
    let current = perms;
    
    for (const part of parts) {
        if (current && typeof current === 'object' && part in current) {
            current = current[part];
        } else {
            return false;
        }
    }
    
    return !!current;
}

// Redirect to login if not authenticated
function requireAuth(allowedTypes = ['admin', 'employee', 'customer']) {
    const user = getCurrentUser();
    
    if (!user || !allowedTypes.includes(user.type)) {
        redirectToLogin();
        return false;
    }
    
    return true;
}

// Redirect to appropriate login page
function redirectToLogin() {
    const currentPage = window.location.pathname;
    
    // Already on login page - don't redirect
    if (currentPage === '/login.html' || currentPage === '/terminal.html') {
        return;
    }
    
    // CRM pages -> terminal login
    if (currentPage.includes('/crm-')) {
        window.location.href = '/terminal.html?redirect=' + encodeURIComponent(currentPage);
    }
    // Admin pages -> login
    else if (currentPage.includes('/admin')) {
        window.location.href = '/login.html?redirect=' + encodeURIComponent(currentPage);
    }
    // Customer pages -> login
    else {
        window.location.href = '/login.html?redirect=' + encodeURIComponent(currentPage);
    }
}

// API request with auth header
async function apiRequest(url, options = {}) {
    const token = getAuthToken();
    
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(url, {
        ...options,
        headers
    });
    
    if (response.status === 401) {
        clearAuth();
        redirectToLogin();
        throw new Error('Unauthorized');
    }
    
    return response;
}

// Logout
function logout() {
    clearAuth();
    window.location.href = '/login.html';
}

// Check auth on page load
function initAuth() {
    const currentPage = window.location.pathname;
    
    // Don't redirect on login/terminal pages
    if (currentPage === '/login.html' || currentPage === '/terminal.html') {
        return;
    }
    
    const user = getCurrentUser();
    
    if (!user) {
        redirectToLogin();
        return;
    }
    
    // Update UI with user info
    const userNameEl = document.getElementById('userName');
    if (userNameEl && user.name) {
        userNameEl.textContent = user.name;
    }
    
    // Check permissions and hide/show elements
    document.querySelectorAll('[data-permission]').forEach(el => {
        const perm = el.dataset.permission;
        if (!hasPermission(perm)) {
            el.style.display = 'none';
        }
    });
}

// Auto-init on load - disabled to prevent conflicts with page-specific auth checks
// Pages should call initAuth() manually if needed

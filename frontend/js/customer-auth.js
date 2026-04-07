/**
 * Customer Auth Module - отдельная авторизация для клиентов
 * Не пересекается с авторизацией сотрудников (auth.js)
 */

const CUSTOMER_AUTH_KEY = 'soho_customer_auth';

// Check if customer is authenticated
function isCustomerAuthenticated() {
    return !!localStorage.getItem(CUSTOMER_AUTH_KEY);
}

// Get current customer info
function getCurrentCustomer() {
    const customerJson = localStorage.getItem(CUSTOMER_AUTH_KEY);
    return customerJson ? JSON.parse(customerJson) : null;
}

// Get customer auth token
function getCustomerToken() {
    const auth = getCurrentCustomer();
    return auth ? auth.token : null;
}

// Set customer auth data
function setCustomerAuth(token, customer) {
    localStorage.setItem(CUSTOMER_AUTH_KEY, JSON.stringify({
        token: token,
        customer: customer,
        type: 'customer'
    }));
}

// Clear customer auth (logout)
function clearCustomerAuth() {
    localStorage.removeItem(CUSTOMER_AUTH_KEY);
}

// Redirect to customer login if not authenticated
function requireCustomerAuth() {
    const currentPage = window.location.pathname;
    
    // Already on login page - don't redirect
    if (currentPage === '/login.html' || currentPage === '/customer-login.html') {
        return true;
    }
    
    const customer = getCurrentCustomer();
    
    if (!customer) {
        window.location.href = '/login.html?redirect=' + encodeURIComponent(currentPage);
        return false;
    }
    
    return true;
}

// API request with customer auth header
async function customerApiRequest(url, options = {}) {
    const token = getCustomerToken();
    
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
        clearCustomerAuth();
        requireCustomerAuth();
        throw new Error('Unauthorized');
    }
    
    return response;
}

// Logout customer
function customerLogout() {
    clearCustomerAuth();
    window.location.href = '/login.html';
}

// Check auth on page load (for customer pages)
function initCustomerAuth() {
    const currentPage = window.location.pathname;
    
    // Don't check on login page
    if (currentPage === '/login.html' || currentPage === '/customer-login.html') {
        return;
    }
    
    // Only check on customer pages
    const customerPages = ['/menu.html', '/profile.html', '/cart.html', '/orders.html', '/checkout.html'];
    if (!customerPages.some(page => currentPage.includes(page))) {
        return; // Not a customer page, don't check
    }
    
    const customer = getCurrentCustomer();
    
    if (!customer) {
        window.location.href = '/login.html?redirect=' + encodeURIComponent(currentPage);
    }
}

// Auto-init on load
document.addEventListener('DOMContentLoaded', initCustomerAuth);

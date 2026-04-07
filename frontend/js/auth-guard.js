// Auth guard with role-based access control
(function() {
    const AUTH_KEY = 'soho_auth';
    
    // Page access rules
    const PAGE_RULES = {
        // Public pages - no auth needed
        public: [
            '/login.html',
            '/register.html', 
            '/forgot-password.html',
            '/',
            '/index.html',
            '/menu.html',
            '/about.html',
            '/contacts.html'
        ],
        
        // Customer pages - only customers (type: 'customer')
        customer: [
            '/profile.html',
            '/orders.html',
            '/cart.html',
            '/checkout.html'
        ],
        
        // Terminal page - anyone can access, but shows different UI based on role
        terminal: ['/terminal.html'],
        
        // Employee pages - require employee auth (type: 'terminal')
        employee: {
            // All employees can access
            all: [
                '/crm-dashboard.html',
                '/crm-settings.html',
                '/crm-settings-general.html',
                '/crm-settings-receipt.html',
                '/crm-settings-marks.html',
                '/crm-settings-access.html'
            ],
            
            // By role
            operator: [
                '/crm-operator-workplace.html',
                '/crm-new-order.html',
                '/crm-orders.html',
                '/crm-order.html',
                '/crm-customers.html',
                '/crm-payments.html',
                '/crm-receipts.html',
                '/crm-reviews.html'
            ],
            
            kitchen: [
                '/crm-kds.html',
                '/crm-menu.html',
                '/crm-menu-products.html',
                '/crm-ingredients.html',
                '/crm-recipes.html'
            ],
            
            manager: [
                '/crm-stats.html',
                '/crm-stats-sales.html',
                '/crm-stats-products.html',
                '/crm-stats-customers.html',
                '/crm-stats-departments.html',
                '/crm-stats-abc.html',
                '/crm-stats-categories.html',
                '/crm-stats-payments.html',
                '/crm-stats-receipts.html',
                '/crm-stats-reviews.html',
                '/crm-stats-types.html',
                '/crm-employees.html',
                '/crm-roles.html',
                '/crm-departments.html',
                '/crm-timesheet.html',
                '/admin-marketing.html'
            ],
            
            warehouse: [
                '/crm-warehouse.html',
                '/crm-warehouse-inventory.html',
                '/crm-warehouse-movements.html',
                '/crm-warehouse-transfers.html',
                '/crm-warehouse-writeoffs.html',
                '/crm-warehouse-suppliers.html',
                '/crm-warehouse-invoices.html',
                '/crm-warehouse-rd.html',
                '/crm-inventory.html',
                '/crm-products.html',
                '/crm-products2.html',
                '/crm-product-depts.html'
            ],
            
            admin: [
                '/admin.html',
                '/admin-panel.html',
                '/admin-panel-new.html',
                '/admin-panel-v2.html',
                '/admin-panel-v3.html',
                '/admin-content.html',
                '/admin-new.html',
                '/admin-marketing.html',
                '/crm-menu-categories.html',
                '/crm-menu-ingredients.html',
                '/crm-menu-semi.html',
                '/crm-courier-template.html',
                '/crm-receipt-template.html'
            ]
        }
    };
    
    const currentPath = window.location.pathname;
    
    // Check if public page
    if (PAGE_RULES.public.some(p => currentPath.includes(p))) {
        return; // No auth needed
    }
    
    // Check auth
    const auth = localStorage.getItem(AUTH_KEY);
    if (!auth) {
        console.log('Auth guard: no auth data, redirecting to login');
        redirectToLogin();
        return;
    }
    
    console.log('Auth guard: auth data found:', auth.substring(0, 100));
    
    let authData;
    try {
        authData = JSON.parse(auth);
        if (!authData.token) {
            redirectToLogin();
            return;
        }
    } catch (e) {
        redirectToLogin();
        return;
    }
    
    // Determine user type
    const userType = authData.type; // 'customer', 'terminal', etc.
    const userRole = authData.employee?.role || authData.user?.role || 'unknown';
    
    // Check access based on page type
    
    // 1. Customer pages - only for customers
    if (PAGE_RULES.customer.some(p => currentPath.includes(p))) {
        if (userType !== 'customer') {
            // Employee trying to access customer page - redirect to workplace
            window.location.href = '/terminal.html';
            return;
        }
        // Customer accessing customer page - OK
        setupAuth(authData);
        return;
    }
    
    // 2. Employee pages - only for employees
    const isEmployeePage = Object.values(PAGE_RULES.employee).flat().some(p => currentPath.includes(p));
    
    if (isEmployeePage) {
        if (userType !== 'terminal' && userType !== 'employee') {
            // Customer trying to access employee page - redirect to profile
            window.location.href = '/profile.html';
            return;
        }
        
        // Check role-based access
        const allowedPages = [
            ...PAGE_RULES.employee.all,
            ...(PAGE_RULES.employee[userRole] || [])
        ];
        
        // Admin can access everything
        if (userRole === 'admin') {
            setupAuth(authData);
            return;
        }
        
        // Check if current page is allowed for this role
        const isAllowed = allowedPages.some(p => currentPath.includes(p));
        
        if (!isAllowed) {
            // Page not allowed for this role
            if (userRole === 'operator') {
                window.location.href = '/crm-operator-workplace.html';
            } else if (userRole === 'kitchen') {
                window.location.href = '/crm-kds.html';
            } else {
                window.location.href = '/terminal.html';
            }
            return;
        }
        
        setupAuth(authData);
        return;
    }
    
    // Terminal page - accessible to all, shows different UI
    if (PAGE_RULES.terminal.some(p => currentPath.includes(p))) {
        setupAuth(authData);
        return;
    }
    
    // Unknown page - allow but with auth
    setupAuth(authData);
    
    function redirectToLogin() {
        const currentUrl = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = '/login.html?redirect=' + currentUrl;
    }
    
    function setupAuth(authData) {
        // Add auth headers to fetch
        const originalFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            options.headers = options.headers || {};
            if (authData.token) {
                options.headers['Authorization'] = 'Bearer ' + authData.token;
            }
            return originalFetch(url, options);
        };
        
        // Expose auth globally
        window.sohoAuth = {
            data: authData,
            getUser: () => authData.user || authData.employee || null,
            getToken: () => authData.token,
            getRole: () => authData.employee?.role || authData.user?.role || null,
            getType: () => authData.type,
            logout: () => {
                localStorage.removeItem(AUTH_KEY);
                window.location.href = '/login.html';
            }
        };
    }
})();

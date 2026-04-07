// Helper script for pages loaded in iframe
// Hides sidebar/header when loaded inside admin panel iframe
(function() {
    function hideElements() {
        // Hide sidebars
        const sidebars = document.querySelectorAll('.sidebar, aside, nav.sidebar, .crm-sidebar, .menu-sidebar');
        sidebars.forEach(sb => {
            sb.style.display = 'none';
        });
        
        // Hide headers
        const headers = document.querySelectorAll('.header, header, .crm-header, .page-header');
        headers.forEach(h => {
            if (!h.closest('.content') && !h.closest('main')) {
                h.style.display = 'none';
            }
        });
        
        // Adjust main content margins
        const mains = document.querySelectorAll('.main, main, .content-wrapper, .page-content');
        mains.forEach(m => {
            m.style.marginLeft = '0';
            m.style.marginTop = '0';
            m.style.width = '100%';
        });
        
        // Add padding to body
        document.body.style.padding = '20px';
        document.body.style.background = '#0f0f1a';
    }
    
    // Check if loaded in iframe
    if (window.self !== window.top) {
        // Try immediately
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', hideElements);
        } else {
            // DOM already loaded, run immediately
            hideElements();
        }
        
        // Also run after a short delay to catch late-rendered elements
        setTimeout(hideElements, 100);
        setTimeout(hideElements, 500);
    }
})();

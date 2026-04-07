// Theme manager for all pages
(function() {
    function applyTheme() {
        const theme = localStorage.getItem('soho_theme') || 'dark';
        
        if (theme === 'light') {
            document.documentElement.setAttribute('data-theme', 'light');
            // Apply inline styles for immediate effect
            if (document.body) {
                document.body.style.background = '#f5f5f5';
                document.body.style.color = '#333';
            }
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
            if (document.body) {
                document.body.style.background = '#0f0f1a';
                document.body.style.color = '#fff';
            }
        }
    }
    
    // Apply immediately
    applyTheme();
    
    // Also apply when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyTheme);
    }
})();

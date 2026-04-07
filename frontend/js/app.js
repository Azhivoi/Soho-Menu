// SOHO Cafe Frontend Application
const API_URL = '/api';

class SOHOApp {
    constructor() {
        this.cart = JSON.parse(localStorage.getItem('soho_cart') || '[]');
        this.favorites = JSON.parse(localStorage.getItem('soho_favorites') || '[]');
        this.theme = localStorage.getItem('soho_theme') || 'dark';
        this.menuData = [];
        this.currentCategory = null;
        this.currentProduct = null;
        this.selectedVariant = null;
        this.quantity = 1;
        
        this.init();
    }
    
    init() {
        this.applyTheme();
        this.bindEvents();
        this.loadMenu();
        this.updateCartBadge();
    }
    
    // Theme Management
    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        const icon = document.querySelector('.theme-icon');
        if (icon) {
            icon.textContent = this.theme === 'dark' ? '☀️' : '🌙';
        }
    }
    
    toggleTheme() {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('soho_theme', this.theme);
        this.applyTheme();
    }
    
    // API Calls
    async fetchMenu() {
        try {
            const response = await fetch(`${API_URL}/menu/public/menu`);
            return await response.json();
        } catch (error) {
            console.error('Failed to load menu:', error);
            this.showToast('Ошибка загрузки меню');
            return [];
        }
    }
    
    async searchProducts(query) {
        try {
            const response = await fetch(`${API_URL}/menu/products/search?q=${encodeURIComponent(query)}`);
            return await response.json();
        } catch (error) {
            console.error('Search failed:', error);
            return [];
        }
    }
    
    // Menu Rendering
    async loadMenu() {
        const loading = document.getElementById('loading');
        loading.style.display = 'flex';
        
        try {
            this.menuData = await this.fetchMenu();
            console.log('Menu data loaded:', this.menuData);
            
            if (!this.menuData || this.menuData.length === 0) {
                console.warn('No menu data received');
                this.showToast('Меню пустое или недоступно');
            } else {
                this.renderCategories();
                this.renderMenu();
                this.updateFavoriteButtons();
            }
            
            // Check if we need to open a product from favorites
            this.checkOpenProductFromFavorites();
        } catch (error) {
            console.error('Error in loadMenu:', error);
            this.showToast('Ошибка загрузки меню');
        } finally {
            loading.style.display = 'none';
        }
    }
    
    checkOpenProductFromFavorites() {
        const urlParams = new URLSearchParams(window.location.search);
        const productId = urlParams.get('openProduct') || localStorage.getItem('soho_open_product');
        
        if (productId) {
            localStorage.removeItem('soho_open_product');
            // Clean URL
            if (urlParams.has('openProduct')) {
                window.history.replaceState({}, '', '/');
            }
            
            // Find product in menu data
            for (const category of this.menuData) {
                const product = category.products.find(p => p.id == productId);
                if (product) {
                    setTimeout(() => this.openProductModal(product), 500);
                    break;
                }
            }
        }
    }
    
    renderCategories() {
        const scrollContainer = document.getElementById('categoriesScroll');
        const sidebarMenu = document.getElementById('sidebarMenu');
        
        scrollContainer.innerHTML = this.menuData.map((cat, index) => `
            <button class="category-chip ${index === 0 ? 'active' : ''}" 
                    data-category="${cat.slug}">
                ${cat.name_ru}
            </button>
        `).join('');
        
        sidebarMenu.innerHTML = this.menuData.map(cat => `
            <li data-category="${cat.slug}">${cat.name_ru}</li>
        `).join('');
        
        // Bind category clicks
        scrollContainer.querySelectorAll('.category-chip').forEach(chip => {
            chip.addEventListener('click', (e) => this.selectCategory(e.target.dataset.category));
        });
        
        sidebarMenu.querySelectorAll('li').forEach(item => {
            item.addEventListener('click', (e) => {
                this.selectCategory(e.target.dataset.category);
                this.toggleSidebar();
            });
        });
    }
    
    renderMenu() {
        const mainContent = document.getElementById('mainContent');
        
        mainContent.innerHTML = this.menuData.map(category => `
            <section class="category-section" id="cat-${category.slug}">
                <h2 class="category-title">${category.name_ru}</h2>
                <div class="products-grid">
                    ${category.products.map(product => this.renderProductCard(product)).join('')}
                </div>
            </section>
        `).join('');
        
        // Bind product clicks
        mainContent.querySelectorAll('.product-card').forEach(card => {
            card.addEventListener('click', (e) => {
                const productId = parseInt(e.currentTarget.dataset.productId);
                this.openProductModal(productId);
            });
        });
    }
    
    renderProductCard(product) {
        // Calculate price display
        let priceDisplay = '';
        const variations = product.variations || [];
        
        if (product.is_variable && variations.length > 0) {
            const prices = variations.map(v => v.price);
            const minPrice = Math.min(...prices);
            const maxPrice = Math.max(...prices);
            if (minPrice === maxPrice) {
                priceDisplay = `${minPrice.toFixed(2)} BYN`;
            } else {
                priceDisplay = `от ${minPrice.toFixed(2)} до ${maxPrice.toFixed(2)} BYN`;
            }
        } else {
            priceDisplay = `${(product.price || 0).toFixed(2)} BYN`;
        }
        
        const badges = [];
        if (product.is_new) badges.push('<span class="product-badge badge-new">Новинка</span>');
        if (product.is_spicy) badges.push('<span class="product-badge badge-spicy">Острое</span>');
        const isFav = this.isFavorite(product.id);
        
        return `
            <div class="product-card" data-product-id="${product.id}">
                <div class="product-image">
                    <img src="${product.image_url || '/images/placeholder.jpg'}" 
                         alt="${product.name_ru}" 
                         loading="lazy">
                    ${badges.join('')}
                    <button class="favorite-btn ${isFav ? 'active' : ''}" 
                            data-product-id="${product.id}"
                            onclick="event.stopPropagation(); app.toggleFavorite(${product.id})">
                        ${isFav ? '❤️' : '🤍'}
                    </button>
                </div>
                <div class="product-info">
                    <h3 class="product-name">${product.name_ru}</h3>
                    ${product.weight_grams ? `<p class="product-weight">${product.weight_grams}г</p>` : ''}
                    <div class="product-price">
                        <span class="price-value">${priceDisplay}</span>
                        <button class="add-btn">+</button>
                    </div>
                </div>
            </div>
        `;
    }
    
    selectCategory(slug) {
        this.currentCategory = slug;
        
        // Update active states
        document.querySelectorAll('.category-chip').forEach(chip => {
            chip.classList.toggle('active', chip.dataset.category === slug);
        });
        
        // Scroll to category
        const section = document.getElementById(`cat-${slug}`);
        if (section) {
            const offset = 180; // header + categories
            const top = section.offsetTop - offset;
            window.scrollTo({ top, behavior: 'smooth' });
        }
    }
    
    // Product Modal
    async openProductModal(productId) {
        // Find product in menu data
        let product = null;
        const searchId = parseInt(productId);
        for (const cat of this.menuData) {
            product = cat.products.find(p => parseInt(p.id) === searchId);
            if (product) break;
        }
        
        if (!product) {
            console.error('Product not found:', productId);
            return;
        }
        
        // Debug
        console.log('Opening product:', product.name_ru, 'variants:', product.variants);
        
        this.currentProduct = product;
        const variations = product.variations || [];
        
        // If product has no variations, create a default one
        if (variations.length === 0) {
            this.selectedVariant = {
                id: product.id,
                name: 'Стандарт',
                price: product.price || 0
            };
            // Hide variants section
            document.getElementById('modalVariants').style.display = 'none';
        } else {
            this.selectedVariant = variations[0];
            document.getElementById('modalVariants').style.display = 'block';
        }
        this.quantity = 1;
        
        // Fill modal
        document.getElementById('modalImg').src = product.image_url || '/images/placeholder.jpg';
        document.getElementById('modalTitle').textContent = product.name_ru;
        
        // Description + Composition
        let descHtml = '';
        if (product.description) {
            // Replace \n with <br> for proper line breaks
            const cleanDesc = product.description.replace(/\\n/g, '<br>').replace(/\n/g, '<br>');
            descHtml += `<div style="margin-bottom: 10px; color: #ccc; font-size: 14px; line-height: 1.4;">${cleanDesc}</div>`;
        }
        if (product.composition) {
            const cleanComp = product.composition.replace(/\\n/g, '<br>').replace(/\n/g, '<br>');
            descHtml += `<div style="color: #888; font-size: 12px;"><strong>Состав:</strong> ${cleanComp}</div>`;
        }
        document.getElementById('modalComposition').innerHTML = descHtml;
        
        // Render variations
        if (variations.length > 0) {
            const variantsHtml = variations.map((v, i) => `
                <div class="variant-option ${i === 0 ? 'selected' : ''}" 
                     data-variant-id="${v.id}"
                     data-price="${v.price}">
                    <span>${v.name || 'Стандарт'} ${v.weight_grams ? `(${v.weight_grams}г)` : ''}</span>
                    <span>${v.price.toFixed(2)} BYN</span>
                </div>
            `).join('');
            document.getElementById('modalVariants').innerHTML = variantsHtml;
            document.getElementById('modalVariants').style.display = 'block';
            
            // Bind variant selection
            document.querySelectorAll('.variant-option').forEach(opt => {
                opt.addEventListener('click', (e) => this.selectVariant(e.currentTarget));
            });
        } else {
            document.getElementById('modalVariants').innerHTML = '';
            document.getElementById('modalVariants').style.display = 'none';
        }
        
        this.updateQtyDisplay();
        
        // Show modal
        document.getElementById('productModal').classList.add('active');
    }
    
    selectVariant(element) {
        document.querySelectorAll('.variant-option').forEach(opt => {
            opt.classList.remove('selected');
        });
        element.classList.add('selected');
        
        const variantId = parseInt(element.dataset.variantId);
        const variations = this.currentProduct.variations || [];
        this.selectedVariant = variations.find(v => v.id === variantId);
    }
    
    updateQtyDisplay() {
        document.getElementById('qtyValue').textContent = this.quantity;
    }
    
    changeQty(delta) {
        this.quantity = Math.max(1, this.quantity + delta);
        this.updateQtyDisplay();
    }
    
    addToCartFromModal() {
        if (!this.currentProduct || !this.selectedVariant) return;
        
        const cartItem = {
            product_id: this.currentProduct.id,
            variant_id: this.selectedVariant.id,
            name: this.currentProduct.name_ru,
            variant_name: this.selectedVariant.name,
            image: this.currentProduct.image_url,
            price: this.selectedVariant.price,
            quantity: this.quantity,
            category_id: this.currentProduct.category_id || this.selectedVariant.category_id
        };
        
        this.addToCart(cartItem);
        this.closeModal();
        this.showToast('Добавлено в корзину');
    }
    
    // Cart Management
    addToCart(item) {
        const existing = this.cart.find(i => 
            i.product_id === item.product_id && i.variant_id === item.variant_id
        );
        
        if (existing) {
            existing.quantity += item.quantity;
        } else {
            this.cart.push(item);
        }
        
        this.saveCart();
        this.updateCartBadge();
    }
    
    removeFromCart(index) {
        this.cart.splice(index, 1);
        this.saveCart();
        this.updateCartBadge();
        this.renderCart();
    }
    
    updateCartItemQty(index, delta) {
        this.cart[index].quantity = Math.max(1, this.cart[index].quantity + delta);
        this.saveCart();
        this.renderCart();
    }
    
    saveCart() {
        localStorage.setItem('soho_cart', JSON.stringify(this.cart));
    }
    
    updateCartBadge() {
        const total = this.cart.reduce((sum, item) => sum + item.quantity, 0);
        const badge = document.getElementById('cartBadge');
        badge.textContent = total;
        badge.style.display = total > 0 ? 'block' : 'none';
    }
    
    renderCart() {
        const container = document.getElementById('cartItems');
        
        if (this.cart.length === 0) {
            container.innerHTML = '<p class="empty-cart">Корзина пуста</p>';
        } else {
            container.innerHTML = this.cart.map((item, index) => `
                <div class="cart-item">
                    <img src="${item.image || '/images/placeholder.jpg'}" 
                         alt="${item.name}" class="cart-item-image">
                    <div class="cart-item-info">
                        <div class="cart-item-name">${item.name}</div>
                        <div class="cart-item-variant">${item.variant_name || ''}</div>
                        <div class="quantity-control">
                            <button class="qty-btn minus" onclick="app.updateCartItemQty(${index}, -1)">−</button>
                            <span class="qty-value">${item.quantity}</span>
                            <button class="qty-btn plus" onclick="app.updateCartItemQty(${index}, 1)">+</button>
                        </div>
                    </div>
                    <div>
                        <div class="cart-item-price">${(item.price * item.quantity).toFixed(2)} BYN</div>
                        <button onclick="app.removeFromCart(${index})" style="background:none;border:none;color:#e53935;cursor:pointer;">Удалить</button>
                    </div>
                </div>
            `).join('');
        }
        
        // Update total
        const total = this.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        document.getElementById('cartTotal').textContent = `${total.toFixed(2)} BYN`;
    }
    
    // Favorites Management
    toggleFavorite(productId) {
        const index = this.favorites.indexOf(productId);
        if (index > -1) {
            this.favorites.splice(index, 1);
            this.showToast('Удалено из избранного');
        } else {
            this.favorites.push(productId);
            this.showToast('Добавлено в избранное');
        }
        this.saveFavorites();
        this.updateFavoriteButtons();
    }
    
    isFavorite(productId) {
        return this.favorites.includes(productId);
    }
    
    saveFavorites() {
        localStorage.setItem('soho_favorites', JSON.stringify(this.favorites));
    }
    
    updateFavoriteButtons() {
        document.querySelectorAll('.favorite-btn').forEach(btn => {
            const productId = parseInt(btn.dataset.productId);
            const isFav = this.isFavorite(productId);
            btn.textContent = isFav ? '❤️' : '🤍';
            btn.classList.toggle('active', isFav);
        });
    }
    
    // UI Actions
    toggleSidebar() {
        document.getElementById('sidebar').classList.toggle('open');
        document.getElementById('overlay').classList.toggle('active');
    }
    
    toggleCart() {
        this.renderCart();
        document.getElementById('cartContainer').classList.toggle('open');
    }
    
    closeModal() {
        document.getElementById('productModal').classList.remove('active');
    }
    
    showToast(message) {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3000);
    }
    
    // Search
    async handleSearch(query) {
        if (!query.trim()) {
            document.getElementById('searchResults').style.display = 'none';
            return;
        }
        
        const results = await this.searchProducts(query);
        const grid = document.getElementById('searchResultsGrid');
        
        if (results.length === 0) {
            grid.innerHTML = '<p style="text-align:center;color:var(--text-secondary);">Ничего не найдено</p>';
        } else {
            grid.innerHTML = results.map(product => this.renderProductCard(product)).join('');
        }
        
        document.getElementById('searchResults').style.display = 'block';
    }
    
    // Event Bindings
    bindEvents() {
        // Theme toggle
        document.getElementById('themeToggle')?.addEventListener('click', () => this.toggleTheme());
        
        // Sidebar
        document.getElementById('menuBtn')?.addEventListener('click', () => this.toggleSidebar());
        document.getElementById('overlay')?.addEventListener('click', () => this.toggleSidebar());
        
        // Cart
        document.getElementById('cartNavItem')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.toggleCart();
        });
        document.getElementById('closeCart')?.addEventListener('click', () => this.toggleCart());
        
        // Modal
        document.getElementById('modalClose')?.addEventListener('click', () => this.closeModal());
        document.getElementById('qtyMinus')?.addEventListener('click', () => this.changeQty(-1));
        document.getElementById('qtyPlus')?.addEventListener('click', () => this.changeQty(1));
        document.getElementById('addToCartBtn')?.addEventListener('click', () => this.addToCartFromModal());
        
        // Search
        const searchInput = document.getElementById('searchInput');
        let searchTimeout;
        searchInput?.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => this.handleSearch(e.target.value), 300);
        });
        
        document.getElementById('closeSearch')?.addEventListener('click', () => {
            document.getElementById('searchResults').style.display = 'none';
            searchInput.value = '';
        });
        
        // Checkout button
        document.getElementById('checkoutBtn')?.addEventListener('click', () => {
            if (this.cart.length === 0) {
                this.showToast('Корзина пуста');
                return;
            }
            window.location.href = '/checkout.html';
        });
    }
}

// Initialize app
const app = new SOHOApp();

// Register Service Worker for PWA
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js')
        .then(reg => console.log('SW registered'))
        .catch(err => console.log('SW registration failed'));
}

// SOHO Menu PWA - Main Application
const API_BASE = '/api';

// State
let categories = [];
let products = [];
let cart = [];
let currentCategory = null;
let isOnline = navigator.onLine;

// DOM Elements
const loadingOverlay = document.getElementById('loadingOverlay');
const categoriesSidebar = document.getElementById('categoriesSidebar');
const productsGrid = document.getElementById('productsGrid');
const cartItems = document.getElementById('cartItems');
const cartBadge = document.getElementById('cartBadge');
const cartTotal = document.getElementById('cartTotal');
const checkoutBtn = document.getElementById('checkoutBtn');
const offlineBadge = document.getElementById('offlineBadge');

// Initialize
async function init() {
    // Register Service Worker
    if ('serviceWorker' in navigator) {
        try {
            await navigator.serviceWorker.register('/pwa/sw.js');
            console.log('Service Worker registered');
        } catch (err) {
            console.error('Service Worker registration failed:', err);
        }
    }
    
    // Load data
    await loadCategories();
    await loadProducts();
    
    // Hide loading
    loadingOverlay.style.display = 'none';
    
    // Setup event listeners
    setupEventListeners();
    
    // Check online status
    updateOnlineStatus();
}

// Load Categories
async function loadCategories() {
    try {
        const response = await fetch(`${API_BASE}/menu/categories`);
        if (response.ok) {
            categories = await response.json();
            renderCategories();
            
            // Cache for offline
            localStorage.setItem('cachedCategories', JSON.stringify(categories));
        } else {
            // Use cached data
            const cached = localStorage.getItem('cachedCategories');
            if (cached) {
                categories = JSON.parse(cached);
                renderCategories();
            }
        }
    } catch (err) {
        console.error('Error loading categories:', err);
        // Use cached data
        const cached = localStorage.getItem('cachedCategories');
        if (cached) {
            categories = JSON.parse(cached);
            renderCategories();
        }
    }
}

// Render Categories
function renderCategories() {
    categoriesSidebar.innerHTML = categories.map((cat, index) => `
        <div class="category-item ${index === 0 ? 'active' : ''}" 
             onclick="selectCategory(${cat.id})" 
             data-id="${cat.id}">
            <span class="category-icon">${cat.icon || '🍽️'}</span>
            <span class="category-name">${cat.name}</span>
        </div>
    `).join('');
    
    if (categories.length > 0) {
        currentCategory = categories[0].id;
    }
}

// Select Category
function selectCategory(categoryId) {
    currentCategory = categoryId;
    
    // Update active state
    document.querySelectorAll('.category-item').forEach(item => {
        item.classList.toggle('active', parseInt(item.dataset.id) === categoryId);
    });
    
    // Filter products
    renderProducts();
}

// Load Products
async function loadProducts() {
    try {
        const response = await fetch(`${API_BASE}/menu/products`);
        if (response.ok) {
            products = await response.json();
            renderProducts();
            
            // Cache for offline
            localStorage.setItem('cachedProducts', JSON.stringify(products));
        } else {
            // Use cached data
            const cached = localStorage.getItem('cachedProducts');
            if (cached) {
                products = JSON.parse(cached);
                renderProducts();
            }
        }
    } catch (err) {
        console.error('Error loading products:', err);
        // Use cached data
        const cached = localStorage.getItem('cachedProducts');
        if (cached) {
            products = JSON.parse(cached);
            renderProducts();
        }
    }
}

// Render Products (only once, no re-render on cart update)
let productsRendered = false;

function renderProducts() {
    if (productsRendered) return; // Prevent re-rendering
    
    const filteredProducts = currentCategory 
        ? products.filter(p => p.category_id === currentCategory)
        : products;
    
    productsGrid.innerHTML = filteredProducts.map(product => {
        // Get price (handle variants)
        let price = product.price;
        if (!price && product.variants && product.variants.length > 0) {
            price = Math.min(...product.variants.map(v => v.price));
        }
        if (!price) price = 0;
        
        // Get image
        let image = product.image;
        if (!image && product.variants && product.variants.length > 0) {
            image = product.variants[0].image;
        }
        
        return `
        <div class="product-card" draggable="true" 
             ondragstart="dragStart(event, ${product.id})"
             onclick="addToCart(${product.id})">
            <img class="product-image" 
                 src="${image || '/pwa/placeholder-food.png'}" 
                 alt="${product.name}"
                 loading="lazy"
                 onerror="this.onerror=null; this.src='/pwa/placeholder-food.png'">
            <div class="product-info">
                <div class="product-name">${product.name}</div>
                <div class="product-description">${product.description || ''}</div>
                <div class="product-footer">
                    <div class="product-price">
                        ${price > 0 ? price : 'от ' + (product.variants ? Math.min(...product.variants.map(v => v.price)) : 0)} <span class="currency">BYN</span>
                    </div>
                    <button class="add-btn" onclick="event.stopPropagation(); addToCart(${product.id})">
                        +
                    </button>
                </div>
            </div>
        </div>
    `}).join('');
    
    productsRendered = true;
    
    // Setup drag and drop
    setupDragAndDrop();
}

// Drag and Drop
function dragStart(event, productId) {
    event.dataTransfer.setData('productId', productId);
    event.target.classList.add('dragging');
}

function setupDragAndDrop() {
    const cartSidebar = document.getElementById('cartSidebar');
    
    cartSidebar.addEventListener('dragover', (e) => {
        e.preventDefault();
        cartSidebar.style.background = '#2d2d45';
    });
    
    cartSidebar.addEventListener('dragleave', () => {
        cartSidebar.style.background = '';
    });
    
    cartSidebar.addEventListener('drop', (e) => {
        e.preventDefault();
        cartSidebar.style.background = '';
        const productId = parseInt(e.dataTransfer.getData('productId'));
        if (productId) {
            addToCart(productId);
        }
        document.querySelectorAll('.product-card.dragging').forEach(card => {
            card.classList.remove('dragging');
        });
    });
}

// Add to Cart
function addToCart(productId) {
    const product = products.find(p => p.id === productId);
    if (!product) return;
    
    // Get price (handle variants)
    let price = product.price;
    let image = product.image;
    let variantName = '';
    
    if (!price && product.variants && product.variants.length > 0) {
        // Use first variant by default
        const variant = product.variants[0];
        price = variant.price;
        image = variant.image || product.image;
        variantName = variant.name;
    }
    
    if (!price) price = 0;
    
    const existingItem = cart.find(item => item.product_id === productId && item.variant_name === variantName);
    
    if (existingItem) {
        existingItem.quantity++;
    } else {
        cart.push({
            product_id: productId,
            name: product.name + (variantName ? ` (${variantName})` : ''),
            price: price,
            image: image,
            variant_name: variantName,
            quantity: 1
        });
    }
    
    updateCart();
    
    // Haptic feedback
    if (navigator.vibrate) {
        navigator.vibrate(50);
    }
}

// Update Quantity
function updateQuantity(productId, delta) {
    const item = cart.find(item => item.product_id === productId);
    if (!item) return;
    
    item.quantity += delta;
    
    if (item.quantity <= 0) {
        cart = cart.filter(item => item.product_id !== productId);
    }
    
    updateCart();
}

// Remove from Cart
function removeFromCart(productId) {
    cart = cart.filter(item => item.product_id !== productId);
    updateCart();
}

// Update Cart UI
function updateCart() {
    // Update badge
    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    cartBadge.textContent = totalItems;
    cartBadge.style.display = totalItems > 0 ? 'flex' : 'none';
    
    // Update items
    if (cart.length === 0) {
        cartItems.innerHTML = `
            <div class="cart-empty">
                <div class="cart-empty-icon">🛒</div>
                <div>Корзина пуста</div>
                <div style="font-size: 13px; margin-top: 8px;">Добавьте товары из меню</div>
            </div>
        `;
    } else {
        cartItems.innerHTML = cart.map(item => `
            <div class="cart-item">
                <img class="cart-item-image" 
                     src="${item.image || '/pwa/placeholder-food.png'}" 
                     alt="${item.name}"
                     onerror="this.src='/pwa/placeholder-food.png'">
                <div class="cart-item-info">
                    <div class="cart-item-name">${item.name}</div>
                    <div class="cart-item-price">${item.price} BYN</div>
                    <div class="cart-item-controls">
                        <button class="qty-btn" onclick="updateQuantity(${item.product_id}, -1)">−</button>
                        <span class="qty-value">${item.quantity}</span>
                        <button class="qty-btn" onclick="updateQuantity(${item.product_id}, 1)">+</button>
                        <button class="cart-item-remove" onclick="removeFromCart(${item.product_id})">🗑</button>
                    </div>
                </div>
            </div>
        `).join('');
    }
    
    // Update total
    const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    cartTotal.textContent = total.toFixed(2);
    
    // Update checkout button
    checkoutBtn.disabled = cart.length === 0;
}

// Toggle Cart (mobile)
function toggleCart() {
    document.getElementById('cartSidebar').classList.toggle('open');
}

// Checkout
async function checkout() {
    if (cart.length === 0) return;
    
    checkoutBtn.disabled = true;
    checkoutBtn.textContent = 'Оформление...';
    
    try {
        const orderData = {
            items: cart.map(item => ({
                product_id: item.product_id,
                quantity: item.quantity,
                price: item.price
            })),
            total: cart.reduce((sum, item) => sum + (item.price * item.quantity), 0),
            source: 'pwa'
        };
        
        const response = await fetch(`${API_BASE}/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Clear cart
            cart = [];
            updateCart();
            
            // Show success
            alert(`✅ Заказ #${result.order_id} оформлен!`);
            
            // Haptic feedback
            if (navigator.vibrate) {
                navigator.vibrate([100, 50, 100]);
            }
        } else {
            throw new Error('Order failed');
        }
    } catch (err) {
        console.error('Checkout error:', err);
        alert('❌ Ошибка оформления заказа. Попробуйте ещё раз.');
    } finally {
        checkoutBtn.disabled = false;
        checkoutBtn.textContent = 'Оформить заказ';
    }
}

// Online/Offline Status
function updateOnlineStatus() {
    isOnline = navigator.onLine;
    offlineBadge.classList.toggle('show', !isOnline);
}

function setupEventListeners() {
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
}

// Start
init();
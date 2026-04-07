/**
 * Checkout Page Logic with Delivery Calculation
 */

// Delivery Configuration
const DELIVERY_CONFIG = {
    MIN_ORDER_AMOUNT: 20,
    FREE_DELIVERY_THRESHOLD: 40,
    STANDARD_DELIVERY_FEE: 5,
    ZONES: {
        'center': { name: 'Центр города', fee: 0, minOrder: 20, freeThreshold: 20 },
        'city': { name: 'В пределах города', fee: 5, minOrder: 20, freeThreshold: 40 },
        'suburb': { name: 'Пригород', fee: 10, minOrder: 40, freeThreshold: 60 }
    }
};

// Load cart from localStorage
function getCart() {
    return JSON.parse(localStorage.getItem('soho_cart') || '[]');
}

// Format price
function formatPrice(price) {
    const numPrice = parseFloat(price);
    if (isNaN(numPrice) || numPrice === null || numPrice === undefined) {
        return '0.00 BYN';
    }
    return numPrice.toFixed(2) + ' BYN';
}

// Safe price calculation
function safePrice(item) {
    const price = parseFloat(item.price);
    const qty = parseInt(item.quantity) || 1;
    if (isNaN(price)) return 0;
    return price * qty;
}

// Calculate delivery fee based on order total and zone
function calculateDelivery(subtotal, zone = 'city') {
    const zoneConfig = DELIVERY_CONFIG.ZONES[zone] || DELIVERY_CONFIG.ZONES['city'];
    
    // If order is below minimum order amount for this zone
    if (subtotal < zoneConfig.minOrder) {
        return { fee: null, message: `Минимальный заказ для этой зоны: ${zoneConfig.minOrder} BYN` };
    }
    
    // Free delivery if above threshold
    if (subtotal >= zoneConfig.freeThreshold) {
        return { fee: 0, message: 'Бесплатно' };
    }
    
    // Paid delivery
    return { fee: zoneConfig.fee, message: `${zoneConfig.fee} BYN` };
}

// Update order summary
function updateOrderSummary() {
    const cart = getCart();
    const subtotal = cart.reduce((sum, item) => sum + (safePrice(item)), 0);
    
    // Get selected delivery type and zone
    const deliveryType = document.querySelector('.delivery-option.active')?.dataset.type || 'delivery';
    const zoneSelect = document.getElementById('deliveryZone');
    const zone = zoneSelect ? zoneSelect.value : 'city';
    
    // Calculate delivery
    let deliveryFee = 0;
    let deliveryMessage = 'Бесплатно';
    
    if (deliveryType === 'delivery') {
        const delivery = calculateDelivery(subtotal, zone);
        deliveryFee = delivery.fee !== null ? delivery.fee : DELIVERY_CONFIG.STANDARD_DELIVERY_FEE;
        deliveryMessage = delivery.message;
    } else {
        deliveryMessage = 'Бесплатно';
    }
    
    // Calculate discount (appliedDiscount can be percentage or amount)
    const discountAmount = appliedDiscount > 0 ? 
        (appliedDiscountIsAmount ? appliedDiscount : (subtotal * appliedDiscount / 100)) : 0;
    console.log('updateOrderSummary:', { appliedDiscount, appliedDiscountIsAmount, discountAmount, subtotal });
    const total = subtotal + deliveryFee - discountAmount;
    
    // Update DOM
    const subtotalEl = document.getElementById('subtotalAmount');
    const deliveryEl = document.getElementById('deliveryAmount');
    const totalEl = document.getElementById('totalAmount');
    
    if (subtotalEl) subtotalEl.textContent = formatPrice(subtotal);
    if (deliveryEl) deliveryEl.textContent = deliveryMessage;
    if (totalEl) totalEl.textContent = formatPrice(total);
    
    // Show discount if applied
    let discountRow = document.getElementById('discountRow');
    if (appliedDiscount > 0) {
        if (!discountRow) {
            discountRow = document.createElement('div');
            discountRow.id = 'discountRow';
            discountRow.className = 'summary-row';
            const summary = document.querySelector('.order-summary');
            if (summary && totalEl.parentElement) {
                summary.insertBefore(discountRow, totalEl.parentElement);
            }
        }
        const discountLabel = appliedDiscountIsAmount ? 'Скидка' : `Скидка ${appliedDiscount}%`;
        discountRow.innerHTML = `<span>${discountLabel}</span><span style="color: #27ae60;">-${formatPrice(discountAmount)}</span>`;
        discountRow.style.display = 'flex';
    } else if (discountRow) {
        discountRow.style.display = 'none';
    }
    
    // Update place order button
    const placeOrderBtn = document.getElementById('placeOrderBtn');
    if (placeOrderBtn) {
        const timeType = document.querySelector('input[name="deliveryTime"]:checked')?.value || 'asap';
        const btnText = timeType === 'scheduled' ? 'Оформить предзаказ' : 'Оформить заказ';
        placeOrderBtn.textContent = `${btnText} на ${formatPrice(total)}`;
    }
    
    // Show/hide minimum order warning
    const minOrderWarning = document.getElementById('minOrderWarning');
    if (minOrderWarning) {
        if (deliveryType === 'delivery' && subtotal < DELIVERY_CONFIG.MIN_ORDER_AMOUNT) {
            minOrderWarning.style.display = 'block';
            minOrderWarning.innerHTML = `⚠️ Минимальная сумма заказа для доставки: ${DELIVERY_CONFIG.MIN_ORDER_AMOUNT} BYN. Добавьте товаров на ${formatPrice(DELIVERY_CONFIG.MIN_ORDER_AMOUNT - subtotal)}`;
            if (placeOrderBtn) placeOrderBtn.disabled = true;
        } else {
            minOrderWarning.style.display = 'none';
            if (placeOrderBtn) placeOrderBtn.disabled = false;
        }
    }
    
    return { subtotal, deliveryFee, total };
}

// Render checkout page
function renderCheckout() {
    const cart = getCart();
    const container = document.getElementById('checkoutContent');
    
    if (cart.length === 0) {
        container.innerHTML = `
            <div class="empty-cart-message">
                <div class="icon">🛒</div>
                <h2>Корзина пуста</h2>
                <p>Добавьте товары из меню, чтобы оформить заказ</p>
                <a href="/" class="go-menu-btn">Перейти в меню</a>
            </div>
        `;
        return;
    }
    
    const subtotal = cart.reduce((sum, item) => sum + (safePrice(item)), 0);
    
    container.innerHTML = `
        <!-- Order Items -->
        <div class="checkout-section">
            <h2 class="section-title">Ваш заказ</h2>
            <div class="order-items">
                ${cart.map(item => `
                    <div class="order-item">
                        <div class="order-item-info">
                            <div class="order-item-name">${item.name}</div>
                            ${item.variant_name ? `<div class="order-item-variant">${item.variant_name}</div>` : ''}
                        </div>
                        <div style="display: flex; align-items: center;">
                            <span class="order-item-qty">×${item.quantity || 1}</span>
                            <span class="order-item-price">${formatPrice((item.price || 0) * (item.quantity || 1))}</span>
                        </div>
                    </div>
                `).join('')}
            </div>
            <div class="order-summary">
                <div class="summary-row">
                    <span>Сумма заказа</span>
                    <span id="subtotalAmount">${formatPrice(subtotal)}</span>
                </div>
                <div class="summary-row">
                    <span>Доставка</span>
                    <span id="deliveryAmount">Рассчитывается...</span>
                </div>
                <div class="summary-row total">
                    <span>Итого к оплате</span>
                    <span id="totalAmount">${formatPrice(subtotal)}</span>
                </div>
            </div>
            <div id="minOrderWarning" class="note-box" style="display: none; margin-top: 16px;"></div>
        </div>
        
        <!-- Contact Info -->
        <div class="checkout-section">
            <h2 class="section-title">Контактные данные</h2>
            <div class="form-group">
                <label>Имя *</label>
                <input type="text" id="customerName" placeholder="Ваше имя" required>
            </div>
            <div class="form-group">
                <label>Телефон *</label>
                <input type="tel" id="customerPhone" placeholder="+375 (XX) XXX-XX-XX" required>
            </div>
            <div class="form-group">
                <label>Email</label>
                <input type="email" id="customerEmail" placeholder="email@example.com">
            </div>
        </div>
        
        <!-- Saved Address (for logged-in users) -->
        <div class="checkout-section" id="savedAddressSection" style="display: none;">
            <h2 class="section-title">Сохраненный адрес</h2>
            <div id="savedAddressDisplay" style="background: var(--bg-secondary); padding: 16px; border-radius: 12px; margin-bottom: 12px;">
                <!-- Filled dynamically -->
            </div>
            <div style="display: flex; gap: 12px;">
                <button type="button" onclick="useSavedAddress()" style="flex: 1; padding: 12px; background: var(--accent-color); color: white; border: none; border-radius: 8px; font-size: 14px; cursor: pointer;">✓ Использовать этот адрес</button>
                <button type="button" onclick="showNewAddressForm()" style="flex: 1; padding: 12px; background: transparent; border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 8px; font-size: 14px; cursor: pointer;">+ Другой адрес</button>
            </div>
        </div>
        
        <!-- Delivery Method -->
        <div class="checkout-section">
            <h2 class="section-title">Способ получения</h2>
            <div class="delivery-options">
                <div class="delivery-option active" data-type="delivery" onclick="selectDeliveryType('delivery')">
                    <div class="icon">🚚</div>
                    <div class="label">Доставка</div>
                </div>
                <div class="delivery-option" data-type="pickup" onclick="selectDeliveryType('pickup')">
                    <div class="icon">🏪</div>
                    <div class="label">Самовывоз</div>
                </div>
            </div>
            
            <!-- Delivery Zone Selection -->
            <div id="deliveryZoneSection" style="margin-top: 20px;">
                <div class="form-group">
                    <label>Зона доставки</label>
                    <select id="deliveryZone" class="form-select" onchange="updateOrderSummary()">
                        <option value="center">Центр города (бесплатно от 20 BYN)</option>
                        <option value="city" selected>В пределах города (бесплатно от 40 BYN)</option>
                        <option value="suburb">Пригород (бесплатно от 60 BYN)</option>
                    </select>
                </div>
                <div class="note-box" style="margin-top: 12px;">
                    <p style="font-size: 13px;">💡 До порога бесплатной доставки стоимость: Центр — 0 BYN, Город — 5 BYN, Пригород — 10 BYN</p>
                </div>
            </div>
        </div>

        <!-- Delivery Time -->
        <div class="checkout-section">
            <h2 class="section-title">Время получения</h2>
            <div style="display: flex; gap: 12px; margin-bottom: 16px;">
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; flex: 1; padding: 12px; background: var(--bg-secondary); border-radius: 12px; border: 2px solid var(--accent-color);">
                    <input type="radio" name="deliveryTime" value="asap" checked onchange="toggleScheduledTime(false)" style="width: 20px; height: 20px;">
                    <div>
                        <div style="font-weight: 600;">⚡ Как можно скорее</div>
                        <div style="font-size: 12px; color: var(--text-secondary);">Доставим в кратчайшие сроки</div>
                    </div>
                </label>
            </div>
            <div style="display: flex; gap: 12px;">
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; flex: 1; padding: 12px; background: var(--bg-secondary); border-radius: 12px; border: 2px solid transparent;">
                    <input type="radio" name="deliveryTime" value="scheduled" onchange="toggleScheduledTime(true)" style="width: 20px; height: 20px;">
                    <div>
                        <div style="font-weight: 600;">📅 Предзаказ на время</div>
                        <div style="font-size: 12px; color: var(--text-secondary);">Выберите удобное время</div>
                    </div>
                </label>
            </div>
            
            <div id="scheduledTimeSection" style="margin-top: 16px; display: none;">
                <div class="form-group">
                    <label>Дата и время *</label>
                    <input type="datetime-local" id="scheduledTime" class="form-select" onchange="validateScheduledTime()">
                    <p id="timeError" style="color: #e74c3c; font-size: 12px; margin-top: 8px; display: none;">❌ Минимальное время предзаказа — через 1 час от текущего</p>
                </div>
            </div>
        </div>
        
        <!-- Delivery Address -->
        <div class="checkout-section" id="deliveryAddress">
            <h2 class="section-title">Адрес доставки</h2>
            <div class="form-group">
                <label>Улица *</label>
                <input type="text" id="street" placeholder="Название улицы">
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                <div class="form-group">
                    <label>Дом *</label>
                    <input type="text" id="house" placeholder="Дом">
                </div>
                <div class="form-group">
                    <label>Квартира</label>
                    <input type="text" id="apartment" placeholder="Кв.">
                </div>
            </div>
            <div class="form-group">
                <label>Подъезд / Этаж / Домофон</label>
                <input type="text" id="entrance" placeholder="Подъезд 2, этаж 5, код 123">
            </div>
        </div>
        
        <!-- Pickup Point (hidden by default) -->
        <div class="checkout-section" id="pickupPoint" style="display: none;">
            <h2 class="section-title">Пункт самовывоза</h2>
            <p style="color: var(--text-secondary); margin-bottom: 16px;">
                г. Смолевичи, ул. Лявданского, д. 1, пав. 114<br>
                первый этаж, Кафе "Soho.by"<br><br>
                Вс-Чт: 11:00 - 22:00<br>
                Пт-Сб: 11:00 - 23:00
            </p>
        </div>
        
        <!-- Promo Code -->
        <div class="checkout-section">
            <h2 class="section-title">Промокод</h2>
            <div style="display: flex; gap: 12px;">
                <input type="text" id="promoCode" placeholder="Введите промокод (например, ДЕНЬРОЖДЕНИЯ)" style="flex: 1; padding: 14px 16px; border: 1px solid var(--border-color); border-radius: 12px; background: var(--bg-secondary); color: var(--text-primary); font-size: 16px;">
                <button onclick="applyPromoCode()" style="padding: 14px 24px; background: var(--accent-color); color: white; border: none; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer;">Применить</button>
            </div>
            <p id="promoMessage" style="margin-top: 8px; font-size: 14px; display: none;"></p>
        </div>

        <!-- Payment Method -->
        <div class="checkout-section">
            <h2 class="section-title">Способ оплаты</h2>
            <div class="payment-options">
                <div class="payment-option active" data-payment="cash" onclick="selectPayment('cash')">
                    <div class="radio"></div>
                    <div class="icon">💵</div>
                    <div class="info">
                        <div class="name">Наличными</div>
                        <div class="desc">Оплата при получении</div>
                    </div>
                </div>
                <div class="payment-option" data-payment="card" onclick="selectPayment('card')">
                    <div class="radio"></div>
                    <div class="icon">💳</div>
                    <div class="info">
                        <div class="name">Картой онлайн</div>
                        <div class="desc">Безопасная оплата картой</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Comments -->
        <div class="checkout-section">
            <h2 class="section-title">Комментарий к заказу</h2>
            <div class="form-group">
                <textarea id="orderComment" placeholder="Особые пожелания, аллергии, уточнения по адресу..."></textarea>
            </div>
        </div>
        
        <!-- Place Order Button -->
        <div class="place-order-btn">
            <button id="placeOrderBtn" onclick="submitOrder()">
                Оформить заказ
            </button>
        </div>
    `;
    
    // Initial calculation
    setTimeout(updateOrderSummary, 0);
}

// Select delivery type
function selectDeliveryType(type) {
    document.querySelectorAll('.delivery-option').forEach(opt => {
        opt.classList.remove('active');
        if (opt.dataset.type === type) {
            opt.classList.add('active');
        }
    });
    
    const deliveryZoneSection = document.getElementById('deliveryZoneSection');
    const deliveryAddress = document.getElementById('deliveryAddress');
    const pickupPoint = document.getElementById('pickupPoint');
    
    if (type === 'delivery') {
        if (deliveryZoneSection) deliveryZoneSection.style.display = 'block';
        if (deliveryAddress) deliveryAddress.style.display = 'block';
        if (pickupPoint) pickupPoint.style.display = 'none';
    } else {
        if (deliveryZoneSection) deliveryZoneSection.style.display = 'none';
        if (deliveryAddress) deliveryAddress.style.display = 'none';
        if (pickupPoint) pickupPoint.style.display = 'block';
    }
    
    updateOrderSummary();
}

// Toggle scheduled time section
function toggleScheduledTime(show) {
    const section = document.getElementById('scheduledTimeSection');
    const timeInput = document.getElementById('scheduledTime');
    
    if (section) {
        section.style.display = show ? 'block' : 'none';
    }
    
    if (show && timeInput) {
        // Set minimum time to 1 hour from now
        const now = new Date();
        now.setHours(now.getHours() + 1);
        now.setMinutes(0, 0, 0);
        const minDateTime = now.toISOString().slice(0, 16);
        timeInput.min = minDateTime;
        timeInput.value = minDateTime;
    }
    
    // Update radio button styling
    document.querySelectorAll('input[name="deliveryTime"]').forEach(radio => {
        const label = radio.closest('label');
        if (radio.checked) {
            label.style.borderColor = 'var(--accent-color)';
        } else {
            label.style.borderColor = 'transparent';
        }
    });
}

// Validate scheduled time
function validateScheduledTime() {
    const timeInput = document.getElementById('scheduledTime');
    const errorMsg = document.getElementById('timeError');
    
    if (!timeInput || !timeInput.value) return false;
    
    const selectedTime = new Date(timeInput.value);
    const minTime = new Date();
    minTime.setHours(minTime.getHours() + 1);
    
    if (selectedTime < minTime) {
        if (errorMsg) errorMsg.style.display = 'block';
        return false;
    } else {
        if (errorMsg) errorMsg.style.display = 'none';
        return true;
    }
}

// Promo code state
let appliedDiscount = 0;
let appliedDiscountIsAmount = false;

// Apply promo code - using API validation
async function applyPromoCode() {
    const promoInput = document.getElementById('promoCode');
    const promoMessage = document.getElementById('promoMessage');
    const code = promoInput.value.trim().toUpperCase();
    
    if (!code) {
        promoMessage.textContent = '❌ Введите промокод';
        promoMessage.style.color = '#e74c3c';
        promoMessage.style.display = 'block';
        return;
    }
    
    // Get cart items for validation
    const cart = getCart();
    // Get unique product IDs that need category lookup
    const productIdsNeedingCategory = [...new Set(
        cart.filter(item => !item.category_id && item.product_id)
            .map(item => item.product_id)
    )];
    console.log('Products needing category:', productIdsNeedingCategory);
    
    // Fetch categories for products missing them
    const categoryMap = {};
    if (productIdsNeedingCategory.length > 0) {
        try {
            const res = await fetch('/api/menu/products?limit=1000');
            console.log('Fetch categories status:', res.status);
            if (res.ok) {
                const data = await res.json();
                const products = Array.isArray(data) ? data : (data.products || []);
                console.log('Loaded products:', products.length);
                products.forEach(p => {
                    if (productIdsNeedingCategory.includes(p.id)) {
                        categoryMap[p.id] = p.category_id;
                        console.log('Mapped category:', p.id, '->', p.category_id);
                    }
                });
            }
        } catch (e) {
            console.log('Failed to fetch categories:', e);
        }
    }
    console.log('Category map:', categoryMap);
    
    const items = cart.map(item => ({
        product_id: item.product_id || item.id,
        variant_id: item.variant_id || null,
        name: item.name || 'Товар',
        price: parseFloat(item.price) || 0,
        quantity: parseInt(item.quantity || item.qty) || 1,
        category_id: item.category_id || categoryMap[item.product_id] || null
    }));
    
    // Debug: log what we're sending
    console.log('Sending promo code request:', { code, items });
    
    try {
        console.log('Starting fetch...');
        const response = await fetch('/api/marketing/validate-promo-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code: code,
                items: items,
                source: 'site',
                delivery_type: document.querySelector('.delivery-option.active')?.dataset.type || 'pickup',
                zone_id: null  // TODO: get from address
            })
        });
        
        console.log('Response received, status:', response.status);
        const text = await response.text();
        console.log('Response text:', text);
        const result = JSON.parse(text);
        console.log('API response:', result);
        
        if (result.valid) {
            // Используем discount_amount (сумма), а не discount (процент)
            appliedDiscount = result.discount_amount || result.discount || 0;
            appliedDiscountIsAmount = true;  // Флаг что это сумма, не процент
            console.log('Promo applied:', { appliedDiscount, appliedDiscountIsAmount, result });
            promoMessage.textContent = `✅ Промокод применен! Скидка: ${appliedDiscount} BYN`;
            promoMessage.style.color = '#27ae60';
            promoMessage.style.display = 'block';
            updateOrderSummary();
        } else {
            appliedDiscount = 0;
            appliedDiscountIsAmount = false;
            promoMessage.textContent = '❌ ' + (result.message || 'Неверный промокод');
            promoMessage.style.color = '#e74c3c';
            promoMessage.style.display = 'block';
            updateOrderSummary();
        }
    } catch (err) {
        console.error('Error validating promo code:', err);
        appliedDiscount = 0;
        appliedDiscountIsAmount = false;
        promoMessage.textContent = '❌ Ошибка проверки промокода';
        promoMessage.style.color = '#e74c3c';
        promoMessage.style.display = 'block';
        updateOrderSummary();
    }
}

// Select payment method
function selectPayment(type) {
    document.querySelectorAll('.payment-option').forEach(opt => {
        opt.classList.remove('active');
        if (opt.dataset.payment === type) {
            opt.classList.add('active');
        }
    });
}

// Submit order
async function submitOrder() {
    console.log('submitOrder START');
    const cart = getCart();
    if (cart.length === 0) return;
    
    // Get form values
    const name = document.getElementById('customerName').value.trim();
    const phone = document.getElementById('customerPhone').value.trim();
    const email = document.getElementById('customerEmail').value.trim();
    const deliveryType = document.querySelector('.delivery-option.active')?.dataset.type || 'delivery';
    const paymentType = document.querySelector('.payment-option.active')?.dataset.payment || 'cash';
    const comment = document.getElementById('orderComment')?.value.trim() || '';
    
    // Validation
    if (!name) {
        alert('Пожалуйста, укажите ваше имя');
        return;
    }
    if (!phone) {
        alert('Пожалуйста, укажите номер телефона');
        return;
    }
    
    // Check delivery time
    const timeType = document.querySelector('input[name="deliveryTime"]:checked')?.value || 'asap';
    let scheduledTime = null;
    
    if (timeType === 'scheduled') {
        const timeInput = document.getElementById('scheduledTime');
        if (!timeInput || !timeInput.value) {
            alert('Пожалуйста, выберите время доставки');
            return;
        }
        if (!validateScheduledTime()) {
            alert('Выбранное время недоступно. Минимальное время предзаказа — через 1 час.');
            return;
        }
        scheduledTime = timeInput.value;
    }
    
    // Get zone for delivery
    let zone = 'city';
    let zoneName = 'В пределах города';
    if (deliveryType === 'delivery') {
        const zoneSelect = document.getElementById('deliveryZone');
        zone = zoneSelect ? zoneSelect.value : 'city';
        zoneName = DELIVERY_CONFIG.ZONES[zone]?.name || 'В пределах города';
    }
    
    // Get promo code early
    const promoCode = document.getElementById('promoCode')?.value.trim() || null;
    
    // Calculate totals
    const { subtotal, deliveryFee, total } = updateOrderSummary();
    
    // Debug promo discount before sending
    console.log('SubmitOrder - Promo state:', { appliedDiscount, appliedDiscountIsAmount, promoCode });
    
    // Validate minimum order for delivery
    if (deliveryType === 'delivery' && subtotal < DELIVERY_CONFIG.MIN_ORDER_AMOUNT) {
        alert(`Минимальная сумма заказа для доставки: ${DELIVERY_CONFIG.MIN_ORDER_AMOUNT} BYN`);
        return;
    }
    
    // Build address
    let address = '';
    if (deliveryType === 'delivery') {
        const street = document.getElementById('street').value.trim();
        const house = document.getElementById('house').value.trim();
        const apartment = document.getElementById('apartment')?.value.trim() || '';
        const entrance = document.getElementById('entrance')?.value.trim() || '';
        
        if (!street || !house) {
            alert('Пожалуйста, укажите полный адрес доставки');
            return;
        }
        
        address = `${zoneName}, ул. ${street}, д. ${house}`;
        if (apartment) address += `, кв. ${apartment}`;
        if (entrance) address += ` (${entrance})`;
    } else {
        address = 'Самовывоз: г. Смолевичи, ул. Лявданского, д. 1, пав. 114, первый этаж, Кафе "Soho.by"';
    }
    
    // Calculate discount amount
    const discountAmount = appliedDiscount > 0 ? (subtotal * appliedDiscount / 100) : 0;
    
    // Build order data
    const orderData = {
        customer_name: name,
        customer_phone: phone,
        customer_email: email || null,
        delivery_type: deliveryType,
        delivery_zone: zone,
        delivery_time_type: timeType,
        scheduled_time: scheduledTime,
        address: address,
        payment_type: paymentType,
        comment: comment || null,
        promo_code: promoCode,
        discount_percent: 0,  // Will be calculated by backend
        discount_amount: appliedDiscountIsAmount ? appliedDiscount : 0,  // Use promo discount amount directly
        promo_discount: appliedDiscountIsAmount ? appliedDiscount : 0,  // For backend tracking
        items: cart.map(item => ({
            product_id: item.product_id,
            variant_id: item.variant_id,
            quantity: item.quantity || 1,
            price: item.price
        })),
        subtotal_amount: subtotal,
        delivery_fee: deliveryFee,
        total_amount: total - discountAmount
    };
    
    // Save user data for logged-in users
    const user = JSON.parse(localStorage.getItem('soho_user') || '{}');
    if (user.name) {
        saveUserPhone(phone);
        if (deliveryType === 'delivery') {
            const street = document.getElementById('street').value.trim();
            const house = document.getElementById('house').value.trim();
            const apartment = document.getElementById('apartment')?.value.trim() || '';
            const entrance = document.getElementById('entrance')?.value.trim() || '';
            saveUserAddress(street, house, apartment, entrance);
        }
    }
    
    // Disable button
    const btn = document.getElementById('placeOrderBtn');
    btn.disabled = true;
    btn.textContent = 'Оформление...';
    
    try {
        const response = await fetch('/api/orders/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(orderData)
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Clear cart
            localStorage.removeItem('soho_cart');
            
            // Show success
            alert(`Заказ №${result.order_id} успешно оформлен! Мы свяжемся с вами для подтверждения.`);
            
            // Redirect to home
            window.location.href = '/';
        } else {
            const error = await response.json();
            alert('Ошибка: ' + (error.detail || 'Не удалось оформить заказ'));
            btn.disabled = false;
            btn.textContent = `Оформить заказ на ${formatPrice(total)}`;
        }
    } catch (err) {
        console.error('Order error:', err);
        alert('Ошибка соединения. Пожалуйста, попробуйте позже.');
        btn.disabled = false;
        const btnText = timeType === 'scheduled' ? 'Оформить предзаказ' : 'Оформить заказ';
        btn.textContent = `${btnText} на ${formatPrice(total)}`;
    }
}

// Load user data if logged in
function loadUserData() {
    const user = JSON.parse(localStorage.getItem('soho_user') || '{}');
    
    if (user.name) {
        // Pre-fill contact info
        const nameInput = document.getElementById('customerName');
        const phoneInput = document.getElementById('customerPhone');
        
        if (nameInput && user.name) nameInput.value = user.name;
        if (phoneInput && user.phone) phoneInput.value = user.phone;
        
        // Load saved address
        const savedAddress = JSON.parse(localStorage.getItem('soho_saved_address') || '{}');
        if (savedAddress.street) {
            const savedSection = document.getElementById('savedAddressSection');
            const savedDisplay = document.getElementById('savedAddressDisplay');
            
            if (savedSection && savedDisplay) {
                savedSection.style.display = 'block';
                savedDisplay.innerHTML = `
                    <div style="font-weight: 600; margin-bottom: 8px;">${savedAddress.street}, ${savedAddress.house}</div>
                    <div style="font-size: 14px; color: var(--text-secondary);">
                        ${savedAddress.apartment ? 'кв. ' + savedAddress.apartment + ', ' : ''}
                        ${savedAddress.entrance || ''}
                    </div>
                `;
                
                // Auto-fill address fields with saved address
                setTimeout(() => useSavedAddress(), 100);
            }
        }
    }
}

// Use saved address
function useSavedAddress() {
    const savedAddress = JSON.parse(localStorage.getItem('soho_saved_address') || '{}');
    
    const streetInput = document.getElementById('street');
    const houseInput = document.getElementById('house');
    const apartmentInput = document.getElementById('apartment');
    const entranceInput = document.getElementById('entrance');
    
    if (streetInput) streetInput.value = savedAddress.street || '';
    if (houseInput) houseInput.value = savedAddress.house || '';
    if (apartmentInput) apartmentInput.value = savedAddress.apartment || '';
    if (entranceInput) entranceInput.value = savedAddress.entrance || '';
}

// Show new address form
function showNewAddressForm() {
    // Clear address fields
    const streetInput = document.getElementById('street');
    const houseInput = document.getElementById('house');
    const apartmentInput = document.getElementById('apartment');
    const entranceInput = document.getElementById('entrance');
    
    if (streetInput) streetInput.value = '';
    if (houseInput) houseInput.value = '';
    if (apartmentInput) apartmentInput.value = '';
    if (entranceInput) entranceInput.value = '';
    
    // Focus on street field
    if (streetInput) streetInput.focus();
}

// Save address after order
function saveUserAddress(street, house, apartment, entrance) {
    const addressData = { street, house, apartment, entrance };
    localStorage.setItem('soho_saved_address', JSON.stringify(addressData));
}

// Save user phone
function saveUserPhone(phone) {
    const user = JSON.parse(localStorage.getItem('soho_user') || '{}');
    user.phone = phone;
    localStorage.setItem('soho_user', JSON.stringify(user));
}

// Phone mask +375(XX) XXX-XX-XX
function formatPhoneNumber(input) {
    // Remove all non-digits
    let value = input.value.replace(/\D/g, '');
    
    // Check if starts with 80 (old format) - reject
    if (value.startsWith('80')) {
        value = value.substring(2); // Remove 80
    }
    
    // Add +375 prefix if needed
    if (value.length > 0 && !value.startsWith('375')) {
        if (value.startsWith('8')) {
            value = value.substring(1);
        }
    }
    
    // Format as +375(XX) XXX-XX-XX
    let formatted = '';
    if (value.length > 0) {
        formatted = '+375';
        if (value.length > 3) {
            formatted += '(' + value.substring(3, 5) + ')';
        } else if (value.length > 3) {
            formatted += '(' + value.substring(3);
        }
        if (value.length > 5) {
            formatted += ' ' + value.substring(5, 8);
        }
        if (value.length > 8) {
            formatted += '-' + value.substring(8, 10);
        }
        if (value.length > 10) {
            formatted += '-' + value.substring(10, 12);
        }
    }
    
    input.value = formatted;
}

// Setup phone mask on input
function setupPhoneMask() {
    const phoneInput = document.getElementById('customerPhone');
    if (phoneInput) {
        phoneInput.addEventListener('input', function(e) {
            formatPhoneNumber(e.target);
        });
        
        phoneInput.addEventListener('focus', function() {
            if (!this.value) {
                this.value = '+375(';
            }
        });
    }
}

// Validate phone format
function validatePhone(phone) {
    const phoneRegex = /^\+375\(\d{2}\)\s\d{3}-\d{2}-\d{2}$/;
    return phoneRegex.test(phone);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        renderCheckout();
        setTimeout(() => {
            loadUserData();
            setupPhoneMask();
        }, 100);
    });
} else {
    renderCheckout();
    setTimeout(() => {
        loadUserData();
        setupPhoneMask();
    }, 100);
}

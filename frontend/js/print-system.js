// print-system.js - Unified print system for SOHO Cafe

const PrintSystem = {
    // Configuration
    config: {
        kitchenMode: 'screen', // 'screen', 'printer', 'none'
        kitchenPrinterIp: '192.168.1.100',
        kitchenPrinterPort: 9100,
        receiptMode: 'browser', // 'browser', 'local_agent', 'web_serial'
        receiptPrinterIp: '192.168.1.100',
        receiptPrinterPort: 9100
    },

    // Load config from localStorage or CRM settings
    loadConfig() {
        // Try CRM settings first (set by crm-settings-general.html)
        const crmSettings = localStorage.getItem('crm_settings');
        if (crmSettings) {
            try {
                const data = JSON.parse(crmSettings);
                if (data.printMode) {
                    this.config.receiptMode = data.printMode;
                }
                if (data.printers) {
                    if (data.printers.receipt) {
                        this.config.receiptPrinterIp = data.printers.receipt.ip;
                        this.config.receiptPrinterPort = data.printers.receipt.port;
                    }
                    if (data.printers.kitchen) {
                        this.config.kitchenPrinterIp = data.printers.kitchen.ip;
                        this.config.kitchenPrinterPort = data.printers.kitchen.port;
                    }
                }
                return;
            } catch (e) {
                console.error('Error parsing CRM settings:', e);
            }
        }
        
        // Fallback to local print settings
        const saved = localStorage.getItem('printSettings');
        if (saved) {
            this.config = {...this.config, ...JSON.parse(saved)};
        }
    },

    // Print kitchen runner
    async printKitchenRunner(order) {
        this.loadConfig();
        
        const runnerData = {
            id: order.id || order.orderNumber,
            typeLabel: order.typeLabel || order.delivery_type || 'Заказ',
            order_type: order.order_type || order.delivery_type,
            table_number: order.table_number,
            time: order.time || new Date().toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'}),
            scheduled_time: order.scheduled_time || order.preorder_time,
            items: order.items || [],
            comment: order.comment || ''
        };

        // Always print to browser window for kitchen
        await this.printKitchenBrowser(runnerData);
    },

    // Print kitchen runner for specific kitchen (цех)
    async printKitchenRunnerForKitchen(runnerData) {
        this.loadConfig();
        
        // runnerData contains: id, kitchenName, kitchenIcon, kitchenColor, items, comment, time, typeLabel
        await this.printKitchenRunnerBrowser(runnerData);
    },

    // Browser print for specific kitchen runner
    async printKitchenRunnerBrowser(runnerData) {
        const printWindow = window.open('', '_blank');
        if (!printWindow) {
            alert('Блокировщик всплывающих окон');
            return;
        }

        // Load runner font settings
        const fontSettings = JSON.parse(localStorage.getItem('runnerFontSettings') || '{}');
        const fonts = {
            orderNum: { size: (fontSettings.orderNum?.size || '42px'), bold: fontSettings.orderNum?.bold !== false },
            kitchen: { size: (fontSettings.type?.size || '28px'), bold: fontSettings.type?.bold !== false },
            time: { size: (fontSettings.time?.size || '18px'), bold: fontSettings.time?.bold === true },
            items: { size: (fontSettings.items?.size || '22px'), bold: fontSettings.items?.bold !== false },
            qty: { size: (fontSettings.qty?.size || '18px'), bold: fontSettings.qty?.bold === true },
            comment: { size: (fontSettings.comment?.size || '16px'), bold: fontSettings.comment?.bold === true }
        };
        
        // Load top margin setting
        const runnerSettings = JSON.parse(localStorage.getItem('runnerSettings') || '{}');
        const topMargin = runnerSettings.topMargin || '25mm';

        const kitchen = runnerData.kitchen || {};
        const kitchenName = kitchen.name || runnerData.kitchenName || 'Кухня';
        const kitchenIcon = kitchen.icon || runnerData.kitchenIcon || '🍽️';
        const kitchenColor = kitchen.color || runnerData.kitchenColor || '#ff6b35';

        // Build items list
        let itemsHtml = '';
        (runnerData.items || []).forEach(item => {
            const qty = item.quantity || item.qty || 1;
            const name = item.name || item.product_name || 'Товар';
            itemsHtml += `<div style="margin: 6px 0; line-height: 1.3;"><span class="item-name">${name}</span> <span class="item-qty">(${qty}шт)</span></div>`;
        });

        const html = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page { size: 80mm auto; margin: 0; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            width: 80mm;
            margin: 0;
            padding: 4mm;
            padding-top: ${topMargin};
            font-family: 'Courier New', monospace;
            font-size: 16px;
            font-weight: bold;
        }
        .order-num { font-size: ${fonts.orderNum.size}; text-align: center; font-weight: ${fonts.orderNum.bold ? '900' : 'normal'}; margin-bottom: 8px; }
        .kitchen { font-size: ${fonts.kitchen.size}; text-align: center; font-weight: ${fonts.kitchen.bold ? 'bold' : 'normal'}; margin-bottom: 8px; color: ${kitchenColor}; }
        .time-section { font-size: ${fonts.time.size}; text-align: center; margin: 8px 0; line-height: 1.4; }
        .time-label { font-size: 14px; color: #666; }
        .time-value { font-size: ${fonts.time.size}; font-weight: ${fonts.time.bold ? 'bold' : 'normal'}; }
        .items { margin: 12px 0; }
        .item-name { font-size: ${fonts.items.size}; font-weight: ${fonts.items.bold ? 'bold' : 'normal'}; }
        .item-qty { font-size: ${fonts.qty.size}; font-weight: ${fonts.qty.bold ? 'bold' : 'normal'}; color: #666; }
        .divider { border: none; border-top: 2px dashed #000; margin: 12px 0; }
        .comment { margin-top: 12px; padding: 10px; background: #f5f5f5; border: 2px solid #000; font-size: ${fonts.comment.size}; font-weight: ${fonts.comment.bold ? 'bold' : 'normal'}; }
        .comment-label { font-size: 14px; color: #666; margin-bottom: 4px; }
        @media print { body { width: 80mm !important; } }
    </style>
</head>
<body>
    <div class="order-num">#${runnerData.id}</div>
    <div class="kitchen">${kitchenIcon} ${kitchenName}</div>
    
    <div class="time-section">
        <div class="time-label">Время:</div>
        <div class="time-value">${runnerData.time || new Date().toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'})}</div>
    </div>
    
    <div class="divider"></div>
    
    <div class="items">${itemsHtml}</div>
    
    ${runnerData.comment ? `
    <div class="divider"></div>
    <div class="comment">
        <div class="comment-label">💬 Комментарий:</div>
        <div>${runnerData.comment}</div>
    </div>
    ` : ''}
    
    <script>
        window.onload = function() { 
            setTimeout(function() { window.print(); }, 250); 
        };
    <\/script>
</body>
</html>`;

        printWindow.document.write(html);
        printWindow.document.close();
    },

    // Show on kitchen screen (TV/display)
    async showKitchenScreen(runnerData) {
        // Send to kitchen WebSocket
        if (window.kitchenSocket && window.kitchenSocket.readyState === WebSocket.OPEN) {
            window.kitchenSocket.send(JSON.stringify({
                type: 'new_order',
                order: runnerData
            }));
        }
        
        // Also open kitchen display in new window if not already open
        if (!window.kitchenWindow || window.kitchenWindow.closed) {
            window.kitchenWindow = window.open('/crm-kitchen-display.html', 'kitchen', 'width=800,height=600');
        }
        
        // Store in localStorage for kitchen display
        const orders = JSON.parse(localStorage.getItem('kitchenOrders') || '[]');
        orders.push({...runnerData, receivedAt: new Date().toISOString()});
        localStorage.setItem('kitchenOrders', JSON.stringify(orders));
    },

    // Print to kitchen printer
    async printKitchenToPrinter(runnerData) {
        const printData = {
            oper: 'printKitchen',
            printer_ip: this.config.kitchenPrinterIp,
            printer_port: this.config.kitchenPrinterPort,
            order: runnerData
        };

        try {
            const response = await fetch('http://localhost:8765', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(printData)
            });
            
            if (!response.ok) throw new Error('Printer error');
        } catch (err) {
            console.error('Kitchen printer error:', err);
            // Fallback to screen
            await this.showKitchenScreen(runnerData);
        }
    },

    // Print receipt
    async printReceipt(order) {
        this.loadConfig();
        
        const receiptData = {
            orderNumber: order.id || order.orderNumber,
            date: order.date || new Date().toLocaleDateString('ru-RU'),
            time: order.time || new Date().toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'}),
            orderType: order.typeLabel || order.delivery_type || 'Заказ',
            customer: order.customer || order.customer_name || '',
            phone: order.phone || order.customer_phone || '',
            address: order.address || order.delivery_address || '',
            items: (order.items || []).map(i => ({
                name: i.name || 'Товар',
                qty: i.quantity || i.qty || 1,
                price: parseFloat(i.price) || 0,
                total: parseFloat(i.total_price) || parseFloat(i.total) || (parseFloat(i.price) || 0) * (i.quantity || i.qty || 1)
            })),
            total: parseFloat(order.total || order.total_amount || order.totalStr) || 0,
            totalStr: (parseFloat(order.total || order.total_amount || order.totalStr) || 0).toFixed(2),
            discount_percent: order.discount_percent || order.discount || 0,
            comment: order.comment || '',
            payment_method: this.getPaymentMethod(order.payment_type || order.payment_method),
            bonus_earned: order.bonus_earned || 0
        };

        switch (this.config.receiptMode) {
            case 'browser':
                await this.printReceiptBrowser(receiptData);
                break;
            case 'local_agent':
                await this.printReceiptAgent(receiptData);
                break;
            case 'web_serial':
                await this.printReceiptWebSerial(receiptData);
                break;
        }
    },

    getPaymentMethod(type) {
        const methods = {
            'cash': 'Наличные',
            'card': 'Карта',
            'online': 'Онлайн'
        };
        return methods[type] || type || 'Наличные';
    },

    // Browser print
    async printReceiptBrowser(order) {
        // Load receipt settings
        const settings = JSON.parse(localStorage.getItem('sohoReceiptSettings') || '{}');
        const fonts = settings.fonts || {};
        
        const receiptWidth = this.config.receiptWidth || '80';
        const widthMm = receiptWidth + 'mm';
        
        // Font sizes from settings or defaults
        const fontShopName = ((fonts.shopName && fonts.shopName.size) || 24) + 'px';
        const fontShopInfo = ((fonts.shopInfo && fonts.shopInfo.size) || 12) + 'px';
        const fontDateTime = ((fonts.dateTime && fonts.dateTime.size) || 14) + 'px';
        const fontOrderNum = ((fonts.orderNum && fonts.orderNum.size) || 18) + 'px';
        const fontItems = ((fonts.items && fonts.items.size) || 14) + 'px';
        const fontTotal = ((fonts.total && fonts.total.size) || 16) + 'px';
        const fontClient = ((fonts.client && fonts.client.size) || 12) + 'px';
        const fontFooter = ((fonts.footer && fonts.footer.size) || 11) + 'px';
        
        // Font weights
        const boldShopName = (fonts.shopName && fonts.shopName.bold) ? 'bold' : 'normal';
        const boldShopInfo = (fonts.shopInfo && fonts.shopInfo.bold) ? 'bold' : 'normal';
        const boldDateTime = (fonts.dateTime && fonts.dateTime.bold) ? 'bold' : 'normal';
        const boldOrderNum = (fonts.orderNum && fonts.orderNum.bold) ? 'bold' : 'normal';
        const boldItems = (fonts.items && fonts.items.bold) ? 'bold' : 'normal';
        const boldTotal = (fonts.total && fonts.total.bold) ? 'bold' : 'normal';
        const boldClient = (fonts.client && fonts.client.bold) ? 'bold' : 'normal';
        const boldFooter = (fonts.footer && fonts.footer.bold) ? 'bold' : 'normal';

        const printWindow = window.open('', '_blank');
        if (!printWindow) {
            alert('Блокировщик всплывающих окон');
            return;
        }

        // Build items table
        let itemsHtml = '<table style="width:100%;font-size:' + fontItems + ';border-collapse:collapse;">';
        itemsHtml += '<tr style="border-bottom:1px solid #000;font-weight:' + boldItems + ';"><th style="text-align:left;">Наименование</th><th style="text-align:center;">Кол.</th><th style="text-align:right;">Сумма</th></tr>';
        
        const items = order.items || [];
        items.forEach(item => {
            const qty = item.qty || item.quantity || 1;
            const name = item.name || 'Товар';
            const price = parseFloat(item.price) || 0;
            const total = parseFloat(item.total) || (price * qty);
            itemsHtml += `<tr><td style="padding:2px 0;">${name}</td><td style="text-align:center;">${qty}</td><td style="text-align:right;">${total.toFixed(0)}</td></tr>`;
        });
        itemsHtml += '</table>';

        // Calculate discount and final total
        const subtotal = parseFloat(order.total) || 0;
        const discountPercent = order.discount_percent || 0;
        const discountAmount = subtotal * (discountPercent / 100);
        const finalTotal = subtotal - discountAmount;

        // Header with logo
        let logoHtml = '';
        if (settings.logo) {
            logoHtml = `<div style="text-align:center;margin-bottom:8px;"><img src="${settings.logo}" style="max-width:180px;max-height:80px;"></div>`;
        } else {
            logoHtml = `<div style="text-align:center;font-size:${fontShopName};font-weight:${boldShopName};margin-bottom:8px;">${settings.shopName || 'SOHO.by'}</div>`;
        }

        // Shop info
        const shopName = settings.shopName || 'SOHO.by';
        const shopAddress = settings.shopAddress || '';
        const shopPhone = settings.shopPhone || '';
        const shopExtra = settings.shopExtra || '';

        // Date and order number
        const now = new Date();
        const dateStr = order.date || now.toLocaleDateString('ru-RU');
        const timeStr = order.time || now.toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'});
        const orderNum = order.orderNumber || order.id || '---';

        // Preorder time
        let preorderHtml = '';
        if (order.scheduled_time && settings.showPreorderTime !== false) {
            preorderHtml = `<div style="font-size:${fontDateTime};font-weight:${boldDateTime};margin:4px 0;"><b>Предзаказ на:</b> ${order.scheduled_time}</div>`;
        }

        // Client info section - only show if there is a customer
        let clientInfoHtml = '';
        const hasCustomer = order.customer && order.customer.trim() !== '' && order.customer !== 'Гость';
        
        if (hasCustomer) {
            if (settings.showClientName !== false && order.customer) {
                clientInfoHtml += `<tr><td>Клиент:</td><td>${order.customer}</td></tr>`;
            }
            if (settings.showBonusInfo !== false && order.bonus_earned !== undefined) {
                clientInfoHtml += `<tr><td>Баллы:</td><td>${order.bonus_earned || 0}, за заказ: 0</td></tr>`;
            }
            // Only show address and phone if there is a customer
            if (settings.showAddress !== false && order.address) {
                // Parse address components
                const addrParts = order.address.split(',');
                const street = addrParts[0] || order.address;
                const house = addrParts.find(p => p.includes('д.')) || '';
                const entrance = addrParts.find(p => p.includes('пд.')) || '';
                const floor = addrParts.find(p => p.includes('эт.')) || '';
                const apartment = addrParts.find(p => p.includes('кв.')) || '';
                
                clientInfoHtml += `<tr><td>Улица:</td><td>${street}</td></tr>`;
                if (house) clientInfoHtml += `<tr><td>Дом:</td><td>${house.replace('д.', '').trim()}</td></tr>`;
                if (entrance) clientInfoHtml += `<tr><td>Подъезд:</td><td>${entrance.replace('пд.', '').trim()}</td></tr>`;
                if (floor) clientInfoHtml += `<tr><td>Этаж:</td><td>${floor.replace('эт.', '').trim()}</td></tr>`;
                if (apartment) clientInfoHtml += `<tr><td>Кв. (офис):</td><td>${apartment.replace('кв.', '').trim()}</td></tr>`;
            }
            if (settings.showPhone !== false && order.phone) {
                clientInfoHtml += `<tr><td>Телефон:</td><td>${order.phone}</td></tr>`;
            }
        }
        // Comment can be shown regardless of customer presence
        if (settings.showComment !== false && order.comment) {
            clientInfoHtml += `<tr><td>Примечание:</td><td>${order.comment}</td></tr>`;
        }

        const clientSection = clientInfoHtml ? `
            <div class="line" style="border-top:1px dashed #000;margin:8px 0;"></div>
            <table style="width:100%;font-size:${fontClient};font-weight:${boldClient};">${clientInfoHtml}</table>
        ` : '';

        // Footer
        const footerText = settings.footerText || 'Спасибо за заказ!';

        const html = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page { size: ${widthMm} auto; margin: 0; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            width: ${widthMm};
            margin: 0;
            padding: 8px;
            font-family: 'Courier New', monospace;
            font-size: ${fontItems};
            line-height: 1.3;
            color: #000;
        }
        .line { border-top: 1px dashed #000; margin: 6px 0; }
        .center { text-align: center; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 2px 0; }
        .total-row { font-weight: bold; border-top: 1px solid #000; }
        @media print { body { width: ${widthMm} !important; } }
    </style>
</head>
<body>
    ${logoHtml}
    <div class="center" style="font-size:${fontShopInfo};font-weight:${boldShopInfo};">${shopName}</div>
    ${shopAddress ? `<div class="center" style="font-size:${fontShopInfo};font-weight:${boldShopInfo};">${shopAddress}</div>` : ''}
    ${shopPhone ? `<div class="center" style="font-size:${fontShopInfo};font-weight:${boldShopInfo};">${shopPhone}</div>` : ''}
    ${shopExtra ? `<div class="center" style="font-size:${fontShopInfo};font-weight:${boldShopInfo};">${shopExtra}</div>` : ''}
    <div class="line"></div>
    <div style="font-size:${fontDateTime};font-weight:${boldDateTime};">${dateStr} ${timeStr}</div>
    <div style="font-size:${fontOrderNum};font-weight:${boldOrderNum};">## ${orderNum}</div>
    ${preorderHtml}
    <div class="line"></div>
    ${itemsHtml}
    <div class="line"></div>
    <table style="font-size:${fontTotal};">
        <tr style="font-weight:${boldTotal};"><td>ИТОГО</td><td></td><td style="text-align:right;">${subtotal.toFixed(0)}</td></tr>
        ${discountPercent > 0 ? `<tr><td>Скидка</td><td></td><td style="text-align:right;">${discountPercent}%</td></tr>` : ''}
        <tr style="font-weight:${boldTotal};"><td>К ОПЛАТЕ</td><td></td><td style="text-align:right;">${finalTotal.toFixed(0)}</td></tr>
    </table>
    ${clientSection}
    <div class="line"></div>
    <div class="center" style="font-size:${fontFooter};font-weight:${boldFooter};margin-top:8px;">${footerText}</div>
    <script>
        window.onload = function() { setTimeout(function() { window.print(); }, 250); };
    </script>
</body>
</html>`;

        printWindow.document.write(html);
        printWindow.document.close();
    },

    // Local agent print
    async printReceiptAgent(order) {
        const printData = {
            oper: 'printReceipt',
            printer_ip: this.config.receiptPrinterIp,
            printer_port: this.config.receiptPrinterPort,
            order: order
        };

        try {
            const response = await fetch('http://localhost:8765', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(printData)
            });
            
            if (!response.ok) throw new Error('Printer error');
            
            const result = await response.json();
            if (result.status !== 'ok') throw new Error(result.message || 'Print failed');
        } catch (err) {
            console.error('Receipt printer error:', err);
            // Fallback to browser
            await this.printReceiptBrowser(order);
        }
    },

    // Web Serial print
    async printReceiptWebSerial(order) {
        if (!window.webSerialPrinter) {
            alert('USB принтер не подключен');
            return;
        }
        await window.webSerialPrinter.printReceipt(order);
    },

    // Browser print for kitchen runner
    // Format preorder time to HH:MM DD-MM-YYYY
    formatPreorderTime(timeStr) {
        if (!timeStr) return '';
        try {
            // If timeStr is already in HH:MM format, just return it
            if (/^\d{1,2}:\d{2}$/.test(timeStr)) {
                return timeStr;
            }
            // If it's a date string, parse it
            const date = new Date(timeStr);
            if (isNaN(date.getTime())) return timeStr;
            
            const hours = date.getHours().toString().padStart(2, '0');
            const minutes = date.getMinutes().toString().padStart(2, '0');
            const day = date.getDate().toString().padStart(2, '0');
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            const year = date.getFullYear();
            
            return `${hours}:${minutes} ${day}-${month}-${year}`;
        } catch (e) {
            return timeStr;
        }
    },

    async printKitchenBrowser(order) {
        const printWindow = window.open('', '_blank');
        if (!printWindow) {
            alert('Блокировщик вспрывающих окон');
            return;
        }

        // Load runner font settings
        const fontSettings = JSON.parse(localStorage.getItem('runnerFontSettings') || '{}');
        const fonts = {
            orderNum: { size: (fontSettings.orderNum?.size || '42px'), bold: fontSettings.orderNum?.bold !== false },
            type: { size: (fontSettings.type?.size || '28px'), bold: fontSettings.type?.bold !== false },
            time: { size: (fontSettings.time?.size || '18px'), bold: fontSettings.time?.bold === true },
            items: { size: (fontSettings.items?.size || '22px'), bold: fontSettings.items?.bold !== false },
            qty: { size: (fontSettings.qty?.size || '18px'), bold: fontSettings.qty?.bold === true },
            comment: { size: (fontSettings.comment?.size || '16px'), bold: fontSettings.comment?.bold === true }
        };
        
        // Load top margin setting
        const runnerSettings = JSON.parse(localStorage.getItem('runnerSettings') || '{}');
        const topMargin = runnerSettings.topMargin || '25mm';

        const isPreorder = order.scheduled_time && order.scheduled_time !== order.time;
        
        // Build items list: name first, then quantity
        let itemsHtml = '';
        (order.items || []).forEach(item => {
            const qty = item.quantity || item.qty || 1;
            const name = item.name || 'Товар';
            // Name first, then quantity on the same line with CSS classes
            itemsHtml += `<div style="margin: 6px 0; line-height: 1.3;"><span class="item-name">${name}</span> <span class="item-qty">(${qty}шт)</span></div>`;
        });

        // Format order type with table number if dine-in
        const typeNames = {
            'delivery': 'Доставка',
            'pickup': 'Самовывоз',
            'dine_in': 'Зал',
            'Зал': 'Зал',
            'Доставка': 'Доставка',
            'Самовывоз': 'Самовывоз'
        };
        let typeLabel = typeNames[order.typeLabel] || typeNames[order.order_type] || order.typeLabel || 'Заказ';
        if ((order.order_type === 'dine_in' || order.typeLabel === 'Зал') && order.table_number) {
            typeLabel += ` (Стол ${order.table_number})`;
        }

        const html = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page { size: 80mm auto; margin: 0; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            width: 80mm;
            margin: 0;
            padding: 4mm;
            padding-top: ${topMargin};
            font-family: 'Courier New', monospace;
            font-size: 16px;
            font-weight: bold;
        }
        .order-num { font-size: ${fonts.orderNum.size}; text-align: center; font-weight: ${fonts.orderNum.bold ? '900' : 'normal'}; margin-bottom: 8px; }
        .type { font-size: ${fonts.type.size}; text-align: center; font-weight: ${fonts.type.bold ? 'bold' : 'normal'}; margin-bottom: 8px; }
        .time-section { font-size: ${fonts.time.size}; text-align: center; margin: 8px 0; line-height: 1.4; }
        .time-label { font-size: 14px; color: #666; }
        .time-value { font-size: ${fonts.time.size}; font-weight: ${fonts.time.bold ? 'bold' : 'normal'}; }
        .preorder { color: #d32f2f; font-weight: 900; }
        .items { margin: 12px 0; }
        .item-name { font-size: ${fonts.items.size}; font-weight: ${fonts.items.bold ? 'bold' : 'normal'}; }
        .item-qty { font-size: ${fonts.qty.size}; font-weight: ${fonts.qty.bold ? 'bold' : 'normal'}; color: #666; }
        .divider { border: none; border-top: 2px dashed #000; margin: 12px 0; }
        .comment { margin-top: 12px; padding: 10px; background: #f5f5f5; border: 2px solid #000; font-size: ${fonts.comment.size}; font-weight: ${fonts.comment.bold ? 'bold' : 'normal'}; }
        .comment-label { font-size: 14px; color: #666; margin-bottom: 4px; }
        @media print { body { width: 80mm !important; } }
    </style>
</head>
<body>
    <div class="order-num">#${order.id}</div>
    <div class="type">${typeLabel}</div>
    
    <div class="time-section">
        <div class="time-label">Принят:</div>
        <div class="time-value">${order.time}</div>
    </div>
    
    ${isPreorder ? `
    <div class="time-section">
        <div class="time-label">Предзаказ на:</div>
        <div class="time-value preorder">${this.formatPreorderTime(order.scheduled_time)}</div>
    </div>
    ` : ''}
    
    <div class="divider"></div>
    
    <div class="items">${itemsHtml}</div>
    
    ${order.comment ? `
    <div class="divider"></div>
    <div class="comment">
        <div class="comment-label">💬 Комментарий:</div>
        <div>${order.comment}</div>
    </div>
    ` : ''}
    
    <script>
        window.onload = function() { 
            setTimeout(function() { window.print(); }, 250); 
        };
    <\/script>
</body>
</html>`;

        printWindow.document.write(html);
        printWindow.document.close();
    },

    // Get agent URL from settings
    getAgentUrl() {
        const crmSettings = localStorage.getItem('crm_settings');
        if (crmSettings) {
            try {
                const data = JSON.parse(crmSettings);
                if (data.agentIp) {
                    return `http://${data.agentIp}:8889`;
                }
            } catch (e) {}
        }
        return 'http://localhost:8889';
    },

    // Print via local agent (HTTP API on port 8889)
    async printViaAgent(type, data) {
        try {
            const agentUrl = this.getAgentUrl();
            const response = await fetch(agentUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    command: 'print',
                    type: type,
                    order: data
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                console.log(`[Agent] ${type} printed successfully`);
                return {success: true};
            } else {
                console.error(`[Agent] Print failed:`, result.error);
                return {success: false, error: result.error};
            }
        } catch (e) {
            console.error('[Agent] Connection failed:', e);
            return {success: false, error: 'Agent not running'};
        }
    },

    // Check if local agent is available
    async checkAgent() {
        try {
            const agentUrl = this.getAgentUrl();
            const response = await fetch(agentUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: 'status'})
            });
            const result = await response.json();
            return result.success && result.connected;
        } catch (e) {
            return false;
        }
    },

    // Print receipt via browser (always, to avoid encoding issues)
    async printReceiptViaAgent(order) {
        // Always use browser print for receipts to avoid encoding issues
        await this.printReceiptBrowser(order);
        return {success: true, mode: 'browser'};
    },

    // Print kitchen runner via agent (with fallback to browser)
    async printKitchenRunnerViaAgent(runnerData) {
        const agentAvailable = await this.checkAgent();
        
        if (agentAvailable) {
            const result = await this.printViaAgent('kitchen', {
                order_number: runnerData.id,
                order_type: runnerData.order_type || 'inside',
                table: runnerData.table_number,
                items: runnerData.items || [],
                client_comment: runnerData.comment
            });
            
            if (result.success) {
                return result;
            }
            console.log('[Agent] Failed, falling back to browser print');
        }
        
        // Fallback: browser print
        await this.printKitchenRunnerBrowser(runnerData);
        return {success: true, mode: 'browser'};
    }

};

// Make available globally
window.PrintSystem = PrintSystem;

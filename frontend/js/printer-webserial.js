/**
 * Web Serial API Printer Support for SOHO Cafe
 * Allows direct USB printing from browser (Chrome/Edge only)
 */

class WebSerialPrinter {
    constructor() {
        this.ports = {
            receipt: null,
            kitchen: null
        };
        this.encoders = new TextEncoder();
    }

    /**
     * Check if Web Serial API is supported
     */
    isSupported() {
        return 'serial' in navigator;
    }

    /**
     * Connect to a USB printer
     * @param {string} type - 'receipt' or 'kitchen'
     * @returns {Promise<boolean>}
     */
    async connect(type) {
        if (!this.isSupported()) {
            throw new Error('Web Serial API not supported. Use Chrome or Edge.');
        }

        try {
            const port = await navigator.serial.requestPort({
                filters: [
                    { usbVendorId: 0x0483 }, // STMicroelectronics
                    { usbVendorId: 0x067b }, // Prolific
                    { usbVendorId: 0x0403 }, // FTDI
                    { usbVendorId: 0x1a86 }, // QinHeng (CH340)
                ]
            });

            await port.open({ baudRate: 9600 });
            this.ports[type] = port;

            // Handle disconnect
            port.addEventListener('disconnect', () => {
                this.ports[type] = null;
                console.log(`Printer ${type} disconnected`);
            });

            return true;
        } catch (err) {
            if (err.name === 'NotFoundError') {
                return false; // User cancelled
            }
            throw err;
        }
    }

    /**
     * Disconnect printer
     * @param {string} type - 'receipt' or 'kitchen'
     */
    async disconnect(type) {
        const port = this.ports[type];
        if (port) {
            try {
                await port.close();
            } catch (e) {
                // Port might already be closed
            }
            this.ports[type] = null;
        }
    }

    /**
     * Check if printer is connected
     * @param {string} type - 'receipt' or 'kitchen'
     */
    isConnected(type) {
        return this.ports[type] !== null;
    }

    /**
     * Print a client receipt
     * @param {Object} order - Order data
     */
    async printReceipt(order) {
        if (!this.ports.receipt) {
            throw new Error('Receipt printer not connected');
        }

        const data = this.buildReceiptData(order);
        await this.sendToPrinter('receipt', data);
    }

    /**
     * Print a kitchen runner
     * @param {Object} order - Order data
     */
    async printKitchenRunner(order) {
        if (!this.ports.kitchen) {
            throw new Error('Kitchen printer not connected');
        }

        const data = this.buildKitchenRunnerData(order);
        await this.sendToPrinter('kitchen', data);
    }

    /**
     * Send raw data to printer
     */
    async sendToPrinter(type, data) {
        const port = this.ports[type];
        if (!port) {
            throw new Error('Printer not connected');
        }

        const writer = port.writable.getWriter();
        try {
            await writer.write(data);
        } finally {
            writer.releaseLock();
        }
    }

    /**
     * Build ESC/POS receipt data
     */
    buildReceiptData(order) {
        const e = this.encoders;
        const commands = [];

        // Initialize
        commands.push(new Uint8Array([0x1B, 0x40]));

        // Header
        commands.push(new Uint8Array([0x1B, 0x61, 0x01])); // Center
        commands.push(e.encode(`${order.venueName || 'SOHO Cafe'}\n`));
        commands.push(e.encode('================\n'));
        if (order.venueAddress) {
            commands.push(e.encode(`${order.venueAddress}\n`));
        }
        if (order.venuePhone) {
            commands.push(e.encode(`Тел: ${order.venuePhone}\n`));
        }
        commands.push(e.encode('\n'));

        // Order info
        commands.push(new Uint8Array([0x1B, 0x61, 0x00])); // Left
        commands.push(e.encode(`Чек № ${order.orderNumber}\n`));
        commands.push(e.encode(`${order.date}\n`));
        if (order.orderType) {
            commands.push(e.encode(`Тип: ${order.orderType}\n`));
        }
        if (order.waiter) {
            commands.push(e.encode(`Официант: ${order.waiter}\n`));
        }
        commands.push(e.encode('----------------\n'));

        // Items
        order.items.forEach(item => {
            const line = `${item.qty} x ${item.name}`;
            const price = item.total.toFixed(2);
            const spaces = 32 - line.length - price.length;
            commands.push(e.encode(`${line}${' '.repeat(Math.max(0, spaces))}${price}\n`));
            
            if (item.modifiers && item.modifiers.length > 0) {
                item.modifiers.forEach(mod => {
                    commands.push(e.encode(`   + ${mod}\n`));
                });
            }
        });

        commands.push(e.encode('----------------\n'));

        // Totals
        commands.push(new Uint8Array([0x1B, 0x61, 0x02])); // Right
        commands.push(e.encode(`ИТОГО: ${order.total.toFixed(2)} ${order.currency || 'BYN'}\n`));
        if (order.vat) {
            commands.push(e.encode(`НДС (${order.vatRate}%): ${order.vat.toFixed(2)}\n`));
        }

        // Payment methods
        if (order.payments && order.payments.length > 0) {
            commands.push(e.encode('\n'));
            commands.push(new Uint8Array([0x1B, 0x61, 0x00])); // Left
            commands.push(e.encode('Оплата:\n'));
            order.payments.forEach(payment => {
                commands.push(e.encode(`${payment.method}: ${payment.amount.toFixed(2)}\n`));
            });
            if (order.change) {
                commands.push(e.encode(`Сдача: ${order.change.toFixed(2)}\n`));
            }
        }

        // Footer
        commands.push(e.encode('\n'));
        commands.push(new Uint8Array([0x1B, 0x61, 0x01])); // Center
        commands.push(e.encode('================\n'));
        if (order.footer) {
            commands.push(e.encode(`${order.footer}\n`));
        } else {
            commands.push(e.encode('Спасибо за покупку!\n'));
            commands.push(e.encode('Ждем вас снова!\n'));
        }

        // Cut paper
        commands.push(e.encode('\n\n\n'));
        commands.push(new Uint8Array([0x1D, 0x56, 0x00]));

        return this.combineCommands(commands);
    }

    /**
     * Build ESC/POS kitchen runner data
     */
    buildKitchenRunnerData(order) {
        const e = this.encoders;
        const commands = [];

        // Initialize
        commands.push(new Uint8Array([0x1B, 0x40]));

        // 3cm top margin for ticket holder
        commands.push(new Uint8Array([0x1B, 0x64, 0x10]));

        // Large order number
        commands.push(new Uint8Array([0x1B, 0x61, 0x01])); // Center
        commands.push(new Uint8Array([0x1D, 0x21, 0x11])); // Double height & width
        commands.push(e.encode(`#${order.orderNumber}\n`));
        commands.push(new Uint8Array([0x1D, 0x21, 0x00])); // Normal
        commands.push(e.encode('\n'));

        // Order info
        commands.push(new Uint8Array([0x1B, 0x61, 0x00])); // Left
        commands.push(e.encode(`${order.orderType || '🍽️ Зал'} • ${order.table || 'Стол ?'}\n`));
        commands.push(e.encode(`Время: ${order.time}\n`));
        if (order.waiter) {
            commands.push(e.encode(`Официант: ${order.waiter}\n`));
        }
        commands.push(e.encode('----------------\n'));

        // Items
        order.items.forEach(item => {
            commands.push(new Uint8Array([0x1B, 0x45, 0x01])); // Bold on
            commands.push(e.encode(`${item.qty} x ${item.name}\n`));
            commands.push(new Uint8Array([0x1B, 0x45, 0x00])); // Bold off
            
            if (item.modifiers && item.modifiers.length > 0) {
                item.modifiers.forEach(mod => {
                    commands.push(e.encode(`   + ${mod}\n`));
                });
            }
            if (item.comment) {
                commands.push(e.encode(`   💬 ${item.comment}\n`));
            }
        });

        // Client comment
        if (order.comment) {
            commands.push(e.encode('----------------\n'));
            commands.push(new Uint8Array([0x1B, 0x45, 0x01])); // Bold
            commands.push(e.encode('💬 Комментарий:\n'));
            commands.push(new Uint8Array([0x1B, 0x45, 0x00])); // Normal
            commands.push(e.encode(`${order.comment}\n`));
        }

        // Cooking time
        if (order.cookingTime) {
            commands.push(e.encode('----------------\n'));
            commands.push(e.encode(`⏱️ Время приготовления: ${order.cookingTime} мин\n`));
        }

        // Cut paper
        commands.push(e.encode('\n\n\n'));
        commands.push(new Uint8Array([0x1D, 0x56, 0x00]));

        return this.combineCommands(commands);
    }

    /**
     * Print test page
     */
    async printTest(type) {
        const testOrder = {
            orderNumber: 'TEST',
            date: new Date().toLocaleString(),
            orderType: '🚚 Доставка',
            table: 'Тест',
            waiter: 'Тест',
            items: [
                { qty: 1, name: 'Тестовый товар', total: 10.00, modifiers: ['Дополнение'] }
            ],
            total: 10.00,
            currency: 'BYN',
            venueName: 'SOHO Cafe (Тест)'
        };

        if (type === 'receipt') {
            await this.printReceipt(testOrder);
        } else {
            await this.printKitchenRunner(testOrder);
        }
    }

    /**
     * Combine command arrays into single Uint8Array
     */
    combineCommands(commands) {
        const totalLength = commands.reduce((sum, cmd) => sum + cmd.length, 0);
        const result = new Uint8Array(totalLength);
        let offset = 0;
        
        for (const cmd of commands) {
            result.set(cmd instanceof Uint8Array ? cmd : this.encoders.encode(cmd), offset);
            offset += cmd.length;
        }
        
        return result;
    }

    /**
     * Open cash drawer (if connected to receipt printer)
     */
    async openCashDrawer() {
        if (!this.ports.receipt) {
            throw new Error('Receipt printer not connected');
        }

        // ESC/POS command to open cash drawer
        const command = new Uint8Array([0x1B, 0x70, 0x00, 0x32, 0x32]);
        await this.sendToPrinter('receipt', command);
    }
}

// Create global instance
window.webSerialPrinter = new WebSerialPrinter();

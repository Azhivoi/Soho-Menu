"""
ESC/POS Printer Driver for SOHO Cafe
Supports thermal printers via TCP (Ethernet)
"""

import socket
import time
from typing import Optional, List, Tuple
from PIL import Image, ImageOps
import io

# ESC/POS Commands
ESC = b'\x1b'
GS = b'\x1d'
FS = b'\x1c'

# Initialize printer
ESC_INIT = ESC + b'@'

# Alignment
ESC_ALIGN_LEFT = ESC + b'a\x00'
ESC_ALIGN_CENTER = ESC + b'a\x01'
ESC_ALIGN_RIGHT = ESC + b'a\x02'

# Font styles
ESC_FONT_NORMAL = ESC + b'!\x00'
ESC_FONT_BOLD = ESC + b'!\x08'
ESC_FONT_DOUBLE_HEIGHT = ESC + b'!\x10'
ESC_FONT_DOUBLE_WIDTH = ESC + b'!\x20'
ESC_FONT_DOUBLE = ESC + b'!\x30'  # Both height and width
ESC_FONT_BOLD_DOUBLE = ESC + b'!\x38'  # Bold + double

# Line spacing
ESC_LINE_SPACING_DEFAULT = ESC + b'2'
ESC_LINE_SPACING_SET = ESC + b'3'

# Cut paper
GS_CUT_FULL = GS + b'V\x00'
GS_CUT_PARTIAL = GS + b'V\x01'

# Feed paper
ESC_FEED_LINES = ESC + b'd'
ESC_FEED_UNITS = ESC + b'J'

# Beep
ESC_BEEP = ESC + b'\x07'

# Open cash drawer
ESC_DRAWER = ESC + b'p\x00\x19\xfa'

# Barcode
GS_BARCODE_HEIGHT = GS + b'h\x50'  # Height 80 dots
GS_BARCODE_WIDTH = GS + b'w\x02'   # Width 2
GS_BARCODE_PRINT = GS + b'k'        # Print barcode

# QR Code
GS_QR_MODEL = GS + b'(k\x04\x00\x31\x41\x32\x00'
GS_QR_SIZE = GS + b'(k\x03\x00\x31\x43\x03'
GS_QR_ERROR = GS + b'(k\x03\x00\x31\x45\x30'
GS_QR_STORE = GS + b'(k'  # + len + data
GS_QR_PRINT = GS + b'(k\x03\x00\x31\x51\x30'

# Character code tables
ESC_CODE_TABLE = ESC + b't'
CODE_TABLE_CP866 = b'\x11'  # Russian DOS
CODE_TABLE_CP1251 = b'\x2e'  # Russian Windows


class ESCPOSPrinter:
    """ESC/POS Thermal Printer Driver"""
    
    def __init__(self, ip: str, port: int = 9100, timeout: int = 5):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.socket: Optional[socket.socket] = None
        self.paper_width = 80  # mm (58 or 80)
        self.max_chars = 48    # Default for 80mm
        
    def connect(self) -> bool:
        """Connect to printer"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.ip, self.port))
            return True
        except Exception as e:
            print(f"Failed to connect to printer {self.ip}:{self.port}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from printer"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
    
    def send(self, data: bytes):
        """Send raw bytes to printer"""
        if self.socket:
            try:
                self.socket.sendall(data)
            except Exception as e:
                print(f"Failed to send data: {e}")
    
    def init(self):
        """Initialize printer"""
        self.send(ESC_INIT)
        self.send(ESC_CODE_TABLE + CODE_TABLE_CP1251)  # Russian Windows
        time.sleep(0.1)
    
    def set_paper_width(self, width_mm: int):
        """Set paper width (58 or 80 mm)"""
        self.paper_width = width_mm
        if width_mm == 58:
            self.max_chars = 32
        elif width_mm == 80:
            self.max_chars = 48
        else:
            self.max_chars = 48
    
    def align_left(self):
        self.send(ESC_ALIGN_LEFT)
    
    def align_center(self):
        self.send(ESC_ALIGN_CENTER)
    
    def align_right(self):
        self.send(ESC_ALIGN_RIGHT)
    
    def font_normal(self):
        self.send(ESC_FONT_NORMAL)
    
    def font_bold(self):
        self.send(ESC_FONT_BOLD)
    
    def font_double_height(self):
        self.send(ESC_FONT_DOUBLE_HEIGHT)
    
    def font_double_width(self):
        self.send(ESC_FONT_DOUBLE_WIDTH)
    
    def font_double(self):
        self.send(ESC_FONT_DOUBLE)
    
    def font_bold_double(self):
        self.send(ESC_FONT_BOLD_DOUBLE)
    
    def text(self, text: str, encoding: str = 'cp1251'):
        """Print text"""
        try:
            data = text.encode(encoding)
        except:
            data = text.encode('utf-8').decode('cp1251', 'ignore').encode('cp1251')
        self.send(data)
    
    def text_ln(self, text: str = ""):
        """Print text with newline"""
        self.text(text + '\n')
    
    def line(self, char: str = '-'):
        """Print horizontal line"""
        self.text_ln(char * self.max_chars)
    
    def feed(self, lines: int = 1):
        """Feed paper by lines"""
        self.send(ESC_FEED_LINES + bytes([lines]))
    
    def feed_units(self, units: int = 30):
        """Feed paper by units"""
        self.send(ESC_FEED_UNITS + bytes([units]))
    
    def beep(self):
        """Beep"""
        self.send(ESC_BEEP)
    
    def cut(self, partial: bool = False):
        """Cut paper"""
        if partial:
            self.send(GS_CUT_PARTIAL)
        else:
            self.send(GS_CUT_FULL)
    
    def open_drawer(self):
        """Open cash drawer"""
        self.send(ESC_DRAWER)
    
    def print_image(self, image_path: str, max_width: int = 512):
        """Print image (logo)"""
        try:
            img = Image.open(image_path)
            
            # Convert to grayscale and resize
            img = img.convert('L')
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Dither to black and white
            img = ImageOps.invert(img)
            img = img.convert('1')
            
            # Get image data
            width, height = img.size
            data = img.tobytes()
            
            # ESC/POS image command
            # GS v 0 m xL xH yL yH d1...dk
            bytes_per_row = (width + 7) // 8
            
            self.align_center()
            self.send(GS + b'v0\x00')
            self.send(bytes([bytes_per_row % 256, bytes_per_row // 256]))
            self.send(bytes([height % 256, height // 256]))
            
            # Send image data row by row
            for y in range(height):
                row_start = y * bytes_per_row
                row_data = data[row_start:row_start + bytes_per_row]
                self.send(row_data)
            
            self.feed(1)
            
        except Exception as e:
            print(f"Failed to print image: {e}")
    
    def print_qr(self, data: str, size: int = 3):
        """Print QR code"""
        # Set model
        self.send(GS_QR_MODEL)
        # Set size
        self.send(GS + b'(k\x03\x00\x31\x43' + bytes([size]))
        # Set error correction
        self.send(GS_QR_ERROR)
        
        # Store data
        data_bytes = data.encode('utf-8')
        length = len(data_bytes) + 3
        pL = length % 256
        pH = length // 256
        self.send(GS_QR_STORE + bytes([pL, pH]) + b'\x31\x50\x30' + data_bytes)
        
        # Print
        self.send(GS_QR_PRINT)
        time.sleep(0.5)
    
    def print_barcode(self, data: str, barcode_type: int = 73):
        """Print barcode (Code128 by default)"""
        self.send(GS_BARCODE_HEIGHT)
        self.send(GS_BARCODE_WIDTH)
        self.align_center()
        data_bytes = data.encode('ascii', 'ignore')
        self.send(GS_BARCODE_PRINT + bytes([barcode_type, len(data_bytes)]) + data_bytes)
        self.feed(1)


class KitchenReceiptPrinter(ESCPOSPrinter):
    """Specialized printer for kitchen receipts"""
    
    def print_kitchen_receipt(self, order_data: dict, template: dict):
        """
        Print kitchen receipt
        
        order_data: {
            'order_num': 'K-001',
            'department': 'Пицца',
            'items': [
                {'name': 'Пепперони', 'variant': '30см', 'quantity': 1, 'notes': ''},
            ]
        }
        template: {
            'header_text': '*** {DEPT_NAME} ***',
            'footer_text': '',
            'font_size': 12,
            'paper_width': 80,
            'header_style': 'bold',
            'items_style': 'normal',
            'cut_paper': True,
            'beep': True,
            'show_logo': False,
            'logo_url': ''
        }
        """
        if not self.connect():
            return False
        
        try:
            self.init()
            self.set_paper_width(template.get('paper_width', 80))
            
            # Beep if enabled
            if template.get('beep', True):
                self.beep()
            
            # Header
            self.align_center()
            header_style = template.get('header_style', 'bold')
            if header_style == 'bold':
                self.font_bold()
            elif header_style == 'double':
                self.font_double()
            elif header_style == 'bold_double':
                self.font_bold_double()
            
            header_text = template.get('header_text', '*** {DEPT_NAME} ***')
            header_text = header_text.replace('{ORDER_NUM}', order_data.get('order_num', ''))
            header_text = header_text.replace('{DEPT_NAME}', order_data.get('department', ''))
            
            for line in header_text.split('\n'):
                self.text_ln(line.strip())
            
            self.font_normal()
            self.align_left()
            self.line()
            
            # Items
            items_style = template.get('items_style', 'normal')
            if items_style == 'bold':
                self.font_bold()
            
            for item in order_data.get('items', []):
                name = item.get('name', '')
                variant = item.get('variant', '')
                qty = item.get('quantity', 1)
                notes = item.get('notes', '')
                
                # Format: 2x Пепперони 30см
                line = f"{qty}x {name}"
                if variant:
                    line += f" {variant}"
                
                self.text_ln(line)
                
                if notes:
                    self.text_ln(f"   > {notes}")
            
            self.font_normal()
            self.line()
            
            # Footer
            footer_text = template.get('footer_text', '')
            if footer_text:
                self.align_center()
                footer_text = footer_text.replace('{ITEMS_COUNT}', str(len(order_data.get('items', []))))
                for line in footer_text.split('\n'):
                    self.text_ln(line.strip())
            
            # Feed and cut
            self.feed(3)
            if template.get('cut_paper', True):
                self.cut()
            
            self.disconnect()
            return True
            
        except Exception as e:
            print(f"Failed to print kitchen receipt: {e}")
            self.disconnect()
            return False


class CourierReceiptPrinter(ESCPOSPrinter):
    """Specialized printer for courier receipts"""
    
    def print_courier_receipt(self, order_data: dict, template: dict):
        """
        Print courier receipt
        
        order_data: {
            'order_num': '62229',
            'date': '05.03.2026',
            'time': '13:27',
            'client_name': 'Ирина',
            'client_phone': '+375...',
            'bonus_current': 0,
            'bonus_earned': 0,
            'address': {
                'street': 'левандского',
                'house': '1',
                'entrance': '7',
                'floor': '7',
                'apartment': '25'
            },
            'comment': 'код 7789',
            'delivery_mark': '2.Доставка',
            'payment_method': 'Б/нал.',
            'total': 71,
            'items': [...]
        }
        """
        if not self.connect():
            return False
        
        try:
            self.init()
            self.set_paper_width(template.get('paper_width', 80))
            
            # Shop info
            self.align_center()
            self.font_bold_double()
            self.text_ln(template.get('shop_name', 'SOHO.by'))
            self.font_normal()
            
            if template.get('shop_address'):
                self.text_ln(template.get('shop_address'))
            if template.get('shop_phone'):
                self.text_ln(template.get('shop_phone'))
            
            self.line()
            
            # Order info
            order_header = template.get('order_header', '{DATE} {TIME}\n№ {ORDER_NUM}')
            order_header = order_header.replace('{DATE}', order_data.get('date', ''))
            order_header = order_header.replace('{TIME}', order_data.get('time', ''))
            order_header = order_header.replace('{ORDER_NUM}', order_data.get('order_num', ''))
            
            for line in order_header.split('\n'):
                self.text_ln(line.strip())
            
            self.line()
            
            # Table header
            self.align_left()
            self.font_bold()
            self.text("Наименование".ljust(self.max_chars - 10))
            self.text("Кол. ")
            self.text_ln("Сумма")
            self.font_normal()
            
            # Items
            for item in order_data.get('items', []):
                name = item.get('name', '')[:self.max_chars - 10]
                qty = str(item.get('quantity', 1)).rjust(3)
                price = str(item.get('price', 0)).rjust(5)
                
                self.text(name.ljust(self.max_chars - 10))
                self.text(qty + " ")
                self.text_ln(price)
            
            self.line()
            
            # Total
            self.font_bold()
            self.text("К ОПЛАТЕ:".ljust(self.max_chars - 5))
            self.text_ln(str(order_data.get('total', 0)).rjust(5))
            self.font_normal()
            
            if order_data.get('payment_method'):
                self.text_ln(f"Способ оплаты: {order_data['payment_method']}")
            
            self.line()
            
            # Client info
            if template.get('show_client_name', True) and order_data.get('client_name'):
                self.text_ln(f"Клиент: {order_data['client_name']}")
            
            if template.get('show_bonus_info', True):
                bonus = f"Баллы: {order_data.get('bonus_current', 0)}, за заказ: {order_data.get('bonus_earned', 0)}"
                self.text_ln(bonus)
            
            if template.get('show_address', True) and order_data.get('address'):
                addr = order_data['address']
                if addr.get('street'):
                    self.text_ln(f"Улица: {addr['street']}")
                if addr.get('house'):
                    self.text_ln(f"Дом: {addr['house']}")
                if addr.get('entrance'):
                    self.text_ln(f"Подъезд: {addr['entrance']}")
                if addr.get('floor'):
                    self.text_ln(f"Этаж: {addr['floor']}")
                if addr.get('apartment'):
                    self.text_ln(f"Кв (офис): {addr['apartment']}")
            
            if template.get('show_client_phone', True) and order_data.get('client_phone'):
                self.text_ln(f"Телефон: {order_data['client_phone']}")
            
            if template.get('show_comment', True) and order_data.get('comment'):
                self.text_ln(f"Примечание: {order_data['comment']}")
            
            if template.get('show_delivery_mark', True) and order_data.get('delivery_mark'):
                self.text_ln(f"Отметки: {order_data['delivery_mark']}")
            
            # Footer
            if template.get('footer_text'):
                self.align_center()
                self.text_ln(template.get('footer_text'))
            
            self.feed(3)
            if template.get('cut_paper', True):
                self.cut()
            
            self.disconnect()
            return True
            
        except Exception as e:
            print(f"Failed to print courier receipt: {e}")
            self.disconnect()
            return False


# Test function
if __name__ == '__main__':
    # Example usage
    printer = KitchenReceiptPrinter('192.168.1.100', 9100)
    
    order = {
        'order_num': 'K-001',
        'department': 'Пицца',
        'items': [
            {'name': 'Пепперони', 'variant': '30см', 'quantity': 2, 'notes': 'Без лука'},
            {'name': 'Маргарита', 'variant': '25см', 'quantity': 1, 'notes': ''},
        ]
    }
    
    template = {
        'header_text': '*** {DEPT_NAME} ***\nЗаказ: {ORDER_NUM}',
        'footer_text': 'Всего позиций: {ITEMS_COUNT}',
        'paper_width': 80,
        'header_style': 'bold_double',
        'items_style': 'normal',
        'cut_paper': True,
        'beep': True
    }
    
    printer.print_kitchen_receipt(order, template)

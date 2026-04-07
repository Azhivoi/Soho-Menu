from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.database import get_db
from app import models

router = APIRouter()

# Delivery configuration model
class DeliveryZone(BaseModel):
    id: str
    name: str
    fee: float
    min_order: float
    free_threshold: float
    time: str
    description: str

class DeliveryConfig(BaseModel):
    min_order_amount: float
    free_delivery_threshold: float
    standard_delivery_fee: float
    pickup_discount: float
    zones: List[DeliveryZone]

# Default configuration
DEFAULT_CONFIG = {
    "min_order_amount": 20.0,
    "free_delivery_threshold": 40.0,
    "standard_delivery_fee": 5.0,
    "pickup_discount": 10,
    "zones": [
        {
            "id": "center",
            "name": "Центр города",
            "fee": 0.0,
            "min_order": 20.0,
            "free_threshold": 20.0,
            "time": "30-45 минут",
            "description": "Бесплатная доставка от 20 BYN"
        },
        {
            "id": "city",
            "name": "В пределах города",
            "fee": 5.0,
            "min_order": 20.0,
            "free_threshold": 40.0,
            "time": "45-60 минут",
            "description": "При заказе от 40 BYN доставка бесплатно"
        },
        {
            "id": "suburb",
            "name": "Пригород",
            "fee": 10.0,
            "min_order": 40.0,
            "free_threshold": 60.0,
            "time": "60-90 минут",
            "description": "При заказе от 60 BYN доставка бесплатно"
        }
    ]
}

@router.get("/delivery", response_model=DeliveryConfig)
async def get_delivery_config():
    """Get current delivery configuration"""
    return DEFAULT_CONFIG

@router.get("/site")
async def get_site_config():
    """Get general site configuration (address, phone, working hours)"""
    return {
        "name": "SOHO.by",
        "address": "г. Минск, ул. Лявданского, 1, пав. 114",
        "phone": "+375 (29) 116-77-55",
        "working_hours": "10:00 - 23:00",
        "email": "info@soho.by",
        "social": {
            "instagram": "@soho.pizza",
            "telegram": "@soho_pizza_bot"
        }
    }

@router.get("/delivery/calculate")
async def calculate_delivery(
    subtotal: float,
    zone: str = "city",
    delivery_type: str = "delivery"
):
    """Calculate delivery fee based on order total and zone"""
    
    if delivery_type == "pickup":
        return {
            "fee": 0.0,
            "message": "Бесплатно (скидка 10% на самовывоз)",
            "free": True,
            "discount_percent": 10
        }
    
    zone_config = next(
        (z for z in DEFAULT_CONFIG["zones"] if z["id"] == zone),
        DEFAULT_CONFIG["zones"][1]  # Default to city
    )
    
    # Check minimum order
    if subtotal < zone_config["min_order"]:
        return {
            "fee": None,
            "message": f"Минимальный заказ для этой зоны: {zone_config['min_order']} BYN",
            "free": False,
            "min_order_required": zone_config["min_order"]
        }
    
    # Check free delivery threshold
    if subtotal >= zone_config["free_threshold"]:
        return {
            "fee": 0.0,
            "message": "Бесплатно",
            "free": True,
            "zone": zone_config["name"]
        }
    
    # Paid delivery
    return {
        "fee": zone_config["fee"],
        "message": f"{zone_config['fee']} BYN",
        "free": False,
        "zone": zone_config["name"],
        "amount_until_free": zone_config["free_threshold"] - subtotal
    }


# ========== SITE SETTINGS ==========

DEFAULT_SITE_SETTINGS = {
    "general": {
        "site_name": "SOHO.by",
        "site_slogan": "Итальянская пицца и суши",
        "site_description": "Доставка итальянской пиццы и японских роллов в Минске.",
        "site_email": "info@soho.by",
        "currency": "BYN"
    },
    "contacts": {
        "phone_main": "+375 (29) 116-77-55",
        "phone_alt": "+375 (33) 116-77-55",
        "address": "г. Минск, ул. Лявданского, 1, пав. 114",
        "coords": "53.9045, 27.5615",
        "social": {
            "instagram": "@soho.pizza",
            "telegram": "@soho_pizza_bot",
            "facebook": "",
            "vk": ""
        }
    },
    "delivery": {
        "min_order": 25,
        "free_delivery_from": 60,
        "delivery_cost": 5,
        "delivery_time": "60-90",
        "allow_pickup": True,
        "allow_delivery": True
    },
    "payment": {
        "cash": True,
        "card": True,
        "online": True,
        "bonus": True
    },
    "bonus": {
        "percent": 5,
        "value": 0.1,
        "min_order": 20
    },
    "seo": {
        "title": "SOHO.by — Доставка пиццы и суши в Минске",
        "description": "Быстрая доставка итальянской пиццы и японских роллов в Минске.",
        "keywords": "доставка пиццы минск, заказать суши, итальянская пицца",
        "head_code": ""
    },
    "schedule": {
        "mon": {"open": "10:00", "close": "23:00", "closed": False},
        "tue": {"open": "10:00", "close": "23:00", "closed": False},
        "wed": {"open": "10:00", "close": "23:00", "closed": False},
        "thu": {"open": "10:00", "close": "23:00", "closed": False},
        "fri": {"open": "10:00", "close": "23:00", "closed": False},
        "sat": {"open": "10:00", "close": "23:00", "closed": False},
        "sun": {"open": "10:00", "close": "23:00", "closed": False}
    },
    "design": {
        "primary_color": "#e94560",
        "dark_mode": True
    }
}

@router.get("/settings")
async def get_settings(db: Session = Depends(get_db)):
    """Get all site settings"""
    settings = {}
    for setting in db.query(models.Config).all():
        try:
            import json
            settings[setting.key] = json.loads(setting.value)
        except:
            settings[setting.key] = setting.value
    
    # Merge with defaults
    result = DEFAULT_SITE_SETTINGS.copy()
    result.update(settings)
    return result

@router.post("/settings")
async def save_settings(data: Dict[str, Any], db: Session = Depends(get_db)):
    """Save site settings"""
    import json
    
    for key, value in data.items():
        # Check if setting exists
        setting = db.query(models.Config).filter(models.Config.key == key).first()
        
        if setting:
            setting.value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            setting.updated_at = datetime.utcnow()
        else:
            setting = models.Config(
                key=key,
                value=json.dumps(value) if isinstance(value, (dict, list)) else str(value),
                type="json" if isinstance(value, (dict, list)) else "text"
            )
            db.add(setting)
    
    db.commit()
    return {"status": "saved"}


# ========== CRM SETTINGS ==========

DEFAULT_CRM_SETTINGS = {
    "venue": {
        "name": "SOHO Cafe",
        "address": "г. Минск, ул. Примерная, 1",
        "phone": "+375 (29) 123-45-67",
        "email": "info@soho.by"
    },
    "hours": {
        "mon": {"enabled": True, "open": "10:00", "close": "23:00", "roundTheClock": False},
        "tue": {"enabled": True, "open": "10:00", "close": "23:00", "roundTheClock": False},
        "wed": {"enabled": True, "open": "10:00", "close": "23:00", "roundTheClock": False},
        "thu": {"enabled": True, "open": "10:00", "close": "23:00", "roundTheClock": False},
        "fri": {"enabled": True, "open": "10:00", "close": "23:00", "roundTheClock": False},
        "sat": {"enabled": True, "open": "10:00", "close": "23:00", "roundTheClock": False},
        "sun": {"enabled": True, "open": "10:00", "close": "23:00", "roundTheClock": False}
    },
    "sameHoursAllDays": False,
    "currency": {
        "code": "BYN",
        "symbol": "BYN",
        "vat": "20",
        "includesVat": True
    },
    "receipts": {
        "header": "SOHO Cafe",
        "subheader": "Добро пожаловать!\\nСпасибо, что выбрали нас!",
        "footer": "Спасибо за покупку!\\nЖдем вас снова!",
        "width": "80",
        "showQr": True,
        "showWifi": True,
        "wifiPassword": "soho2024",
        "showPaymentMethods": True,
        "showOrderType": True
    },
    "printers": {
        "receipt": {
            "driver": "escpos",
            "ip": "192.168.1.100",
            "port": 9100,
            "enabled": True
        },
        "kitchen": {
            "driver": "escpos",
            "ip": "192.168.1.101",
            "port": 9100,
            "enabled": True
        }
    },
    "kitchen": {
        "confirmBeforeSend": True,
        "allowResend": True,
        "markAddedItems": True,
        "separateSendAdded": True,
        "kdsMode": False,
        "allowReprintRunner": True
    },
    "security": {
        "level": "medium",
        "confirmDeletePrinted": True,
        "confirmDeleteSent": True,
        "confirmReprint": True,
        "logAllChanges": True
    }
}

@router.get("/crm/settings")
async def get_crm_settings(db: Session = Depends(get_db)):
    """Get CRM general settings"""
    import json
    
    setting = db.query(models.Config).filter(models.Config.key == "crm_settings").first()
    
    if setting:
        try:
            saved = json.loads(setting.value)
            # Merge with defaults to ensure all fields exist
            result = DEFAULT_CRM_SETTINGS.copy()
            result.update(saved)
            return result
        except:
            pass
    
    return DEFAULT_CRM_SETTINGS

@router.post("/crm/settings")
async def save_crm_settings(data: Dict[str, Any], db: Session = Depends(get_db)):
    """Save CRM general settings"""
    import json
    from datetime import datetime
    
    setting = db.query(models.Config).filter(models.Config.key == "crm_settings").first()
    
    if setting:
        setting.value = json.dumps(data)
        setting.updated_at = datetime.utcnow()
    else:
        setting = models.Config(
            key="crm_settings",
            value=json.dumps(data),
            type="json"
        )
        db.add(setting)
    
    db.commit()
    return {"status": "saved", "message": "Настройки сохранены"}


# ========== PRINTER TEST ==========

from pydantic import BaseModel

class PrinterTestRequest(BaseModel):
    printer_type: str  # "receipt" or "kitchen"
    ip: str
    port: int
    driver: str = "escpos"

@router.post("/crm/printer/test")
async def test_printer(data: PrinterTestRequest):
    """Test printer connection and print test page"""
    import socket
    import datetime
    
    try:
        # ESC/POS test receipt commands
        ESC = b'\x1b'
        GS = b'\x1d'
        
        # Initialize printer
        init = ESC + b'@'
        
        # Center alignment
        center = ESC + b'a\x01'
        left = ESC + b'a\x00'
        
        # Bold on/off
        bold_on = ESC + b'E\x01'
        bold_off = ESC + b'E\x00'
        
        # Double height/width
        double_on = GS + b'!\x11'
        double_off = GS + b'!\x00'
        
        # Cut paper
        cut = GS + b'V\x00'
        
        # Line feed
        lf = b'\n'
        
        # Build test receipt
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        receipt = b''
        receipt += init
        receipt += center
        receipt += double_on
        receipt += bold_on
        receipt += 'ТЕСТ ПРИНТЕРА'.encode('cp866')
        receipt += double_off
        receipt += bold_off
        receipt += lf + lf
        receipt += left
        receipt += f'Тип: {data.printer_type}'.encode('cp866')
        receipt += lf
        receipt += f'IP: {data.ip}:{data.port}'.encode('cp866')
        receipt += lf
        receipt += f'Время: {now}'.encode('cp866')
        receipt += lf + lf
        receipt += center
        receipt += '================'.encode('cp866')
        receipt += lf
        receipt += 'Принтер работает!'.encode('cp866')
        receipt += lf
        receipt += '================'.encode('cp866')
        receipt += lf + lf + lf
        receipt += cut
        
        # Send to printer
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((data.ip, data.port))
        sock.sendall(receipt)
        sock.close()
        
        return {
            "status": "success",
            "message": f"Тестовая печать отправлена на {data.ip}:{data.port}",
            "printer_type": data.printer_type
        }
        
    except socket.timeout:
        raise HTTPException(status_code=408, detail="Таймаут подключения к принтеру")
    except ConnectionRefused:
        raise HTTPException(status_code=503, detail="Принтер недоступен (connection refused)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка печати: {str(e)}")

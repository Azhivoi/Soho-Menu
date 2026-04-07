from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.database import get_db
from app import models

router = APIRouter()

class PrinterSettings(BaseModel):
    kitchen_mode: str = 'screen'  # 'screen', 'printer', 'none'
    kitchen_printer_ip: Optional[str] = '192.168.1.100'
    kitchen_printer_port: int = 9100
    receipt_mode: str = 'browser'  # 'browser', 'local_agent', 'web_serial'
    receipt_printer_ip: Optional[str] = '192.168.1.100'
    receipt_printer_port: int = 9100
    receipt_printer_name: Optional[str] = None
    auto_print_receipt: bool = False
    auto_print_runner: bool = False

class ReceiptSettings(BaseModel):
    logo: Optional[str] = None
    shopName: str = ''
    shopAddress: str = ''
    shopPhone: str = ''
    shopExtra: str = ''
    footerText: str = ''
    fonts: Dict[str, Any] = {}
    showClientName: bool = True
    showBonusInfo: bool = True
    showAddress: bool = True
    showPhone: bool = True
    showComment: bool = True
    showPreorderTime: bool = True

@router.get("/settings/printer")
async def get_printer_settings(db: Session = Depends(get_db)):
    """Get printer settings from database"""
    # Get first company (in multi-company setup, would filter by company)
    settings = db.query(models.Config).filter(
        models.Config.key == 'printer_settings'
    ).first()
    
    if settings and settings.value:
        import json
        return json.loads(settings.value)
    
    # Return defaults
    return {
        "kitchen_mode": "screen",
        "kitchen_printer_ip": "192.168.1.100",
        "kitchen_printer_port": 9100,
        "receipt_mode": "browser",
        "receipt_printer_ip": "192.168.1.100",
        "receipt_printer_port": 9100,
        "receipt_printer_name": None,
        "auto_print_receipt": False,
        "auto_print_runner": False
    }

@router.put("/settings/printer")
async def update_printer_settings(data: PrinterSettings, db: Session = Depends(get_db)):
    """Update printer settings in database"""
    import json
    
    settings = db.query(models.Config).filter(
        models.Config.key == 'printer_settings'
    ).first()
    
    if settings:
        settings.value = json.dumps(data.dict())
        settings.type = 'json'
    else:
        settings = models.Config(
            key='printer_settings',
            value=json.dumps(data.dict()),
            type='json'
        )
        db.add(settings)

    db.commit()
    return {"status": "ok"}

@router.get("/settings/receipt")
async def get_receipt_settings(db: Session = Depends(get_db)):
    """Get receipt settings from database"""
    settings = db.query(models.Config).filter(
        models.Config.key == 'receipt_settings'
    ).first()
    
    if settings and settings.value:
        import json
        return json.loads(settings.value)
    
    # Return defaults
    return {
        "logo": None,
        "shopName": "SOHO Cafe",
        "shopAddress": "",
        "shopPhone": "",
        "shopExtra": "",
        "footerText": "Спасибо за заказ!",
        "fonts": {
            "shopName": {"size": 24, "bold": True},
            "shopInfo": {"size": 12, "bold": False},
            "dateTime": {"size": 14, "bold": False},
            "orderNum": {"size": 18, "bold": True},
            "items": {"size": 14, "bold": False},
            "total": {"size": 16, "bold": True},
            "client": {"size": 12, "bold": False},
            "footer": {"size": 11, "bold": False}
        },
        "showClientName": True,
        "showBonusInfo": True,
        "showAddress": True,
        "showPhone": True,
        "showComment": True,
        "showPreorderTime": True
    }

@router.put("/settings/receipt")
async def update_receipt_settings(data: ReceiptSettings, db: Session = Depends(get_db)):
    """Update receipt settings in database"""
    import json
    
    settings = db.query(models.Config).filter(
        models.Config.key == 'receipt_settings'
    ).first()
    
    if settings:
        settings.value = json.dumps(data.dict())
        settings.type = 'json'
    else:
        settings = models.Config(
            key='receipt_settings',
            value=json.dumps(data.dict()),
            type='json'
        )
        db.add(settings)

    db.commit()
    return {"status": "ok"}

# Runner font settings
@router.get("/settings/runner-fonts")
async def get_runner_font_settings(db: Session = Depends(get_db)):
    """Get runner font settings from database"""
    settings = db.query(models.Config).filter(
        models.Config.key == 'runner_font_settings'
    ).first()
    
    if settings and settings.value:
        import json
        return json.loads(settings.value)
    
    # Return defaults
    return {
        "orderNum": {"size": "42px", "bold": "900"},
        "type": {"size": "20px", "bold": "bold"},
        "time": {"size": "16px", "bold": "normal"},
        "items": {"size": "18px", "bold": "bold"},
        "qty": {"size": "14px", "bold": "normal"},
        "comment": {"size": "16px", "bold": "normal"},
        "topMargin": "25mm"
    }

@router.put("/settings/runner-fonts")
async def update_runner_font_settings(data: dict, db: Session = Depends(get_db)):
    """Update runner font settings in database"""
    import json
    
    settings = db.query(models.Config).filter(
        models.Config.key == 'runner_font_settings'
    ).first()
    
    if settings:
        settings.value = json.dumps(data)
        settings.type = 'json'
    else:
        settings = models.Config(
            key='runner_font_settings',
            value=json.dumps(data),
            type='json'
        )
        db.add(settings)
    
    db.commit()
    return {"status": "ok"}


# ===== UNIFIED PRINT SETTINGS =====

DEFAULT_PRINT_SETTINGS = {
    "printer": {
        "kitchen_mode": "screen",
        "kitchen_printer_ip": "192.168.1.100",
        "kitchen_printer_port": 9100,
        "receipt_mode": "browser",
        "receipt_printer_ip": "192.168.1.100",
        "receipt_printer_port": 9100,
        "receipt_printer_name": None,
        "auto_print_receipt": False,
        "auto_print_runner": False
    },
    "receipt": {
        "logo": None,
        "shopName": "SOHO Cafe",
        "shopAddress": "",
        "shopPhone": "",
        "shopExtra": "",
        "footerText": "Спасибо за заказ!",
        "fonts": {
            "shopName": {"size": 24, "bold": True},
            "shopInfo": {"size": 12, "bold": False},
            "dateTime": {"size": 14, "bold": False},
            "orderNum": {"size": 18, "bold": True},
            "items": {"size": 14, "bold": False},
            "total": {"size": 16, "bold": True},
            "client": {"size": 12, "bold": False},
            "footer": {"size": 11, "bold": False}
        },
        "showClientName": True,
        "showBonusInfo": True,
        "showAddress": True,
        "showPhone": True,
        "showComment": True,
        "showPreorderTime": True
    },
    "runner": {
        "fonts": {
            "orderNum": {"size": "42px", "bold": "900"},
            "type": {"size": "20px", "bold": "bold"},
            "time": {"size": "16px", "bold": "normal"},
            "items": {"size": "18px", "bold": "bold"},
            "qty": {"size": "14px", "bold": "normal"},
            "comment": {"size": "16px", "bold": "normal"}
        },
        "topMargin": "25mm"
    }
}

@router.get("/settings/print-all")
async def get_all_print_settings(db: Session = Depends(get_db)):
    """Get all print settings (printer, receipt, runner) in one request"""
    import json
    
    result = DEFAULT_PRINT_SETTINGS.copy()
    
    # Load printer settings
    printer = db.query(models.Config).filter(models.Config.key == 'printer_settings').first()
    if printer and printer.value:
        result["printer"] = {**result["printer"], **json.loads(printer.value)}
    
    # Load receipt settings
    receipt = db.query(models.Config).filter(models.Config.key == 'receipt_settings').first()
    if receipt and receipt.value:
        result["receipt"] = {**result["receipt"], **json.loads(receipt.value)}
    
    # Load runner settings
    runner = db.query(models.Config).filter(models.Config.key == 'runner_font_settings').first()
    if runner and runner.value:
        runner_data = json.loads(runner.value)
        result["runner"]["fonts"] = runner_data
        if "topMargin" in runner_data:
            result["runner"]["topMargin"] = runner_data["topMargin"]
    
    return result

@router.put("/settings/print-all")
async def update_all_print_settings(data: dict, db: Session = Depends(get_db)):
    """Update all print settings (printer, receipt, runner) in one request"""
    import json
    from datetime import datetime
    
    # Save printer settings
    if "printer" in data:
        printer = db.query(models.Config).filter(models.Config.key == 'printer_settings').first()
        if printer:
            printer.value = json.dumps(data["printer"])
            printer.type = 'json'
            printer.updated_at = datetime.utcnow()
        else:
            db.add(models.Config(key='printer_settings', value=json.dumps(data["printer"]), type='json'))
    
    # Save receipt settings
    if "receipt" in data:
        receipt = db.query(models.Config).filter(models.Config.key == 'receipt_settings').first()
        if receipt:
            receipt.value = json.dumps(data["receipt"])
            receipt.type = 'json'
            receipt.updated_at = datetime.utcnow()
        else:
            db.add(models.Config(key='receipt_settings', value=json.dumps(data["receipt"]), type='json'))
    
    # Save runner settings
    if "runner" in data:
        runner_data = data["runner"].copy()
        if "fonts" in runner_data:
            runner_data.update(runner_data["fonts"])
            del runner_data["fonts"]
        
        runner = db.query(models.Config).filter(models.Config.key == 'runner_font_settings').first()
        if runner:
            runner.value = json.dumps(runner_data)
            runner.type = 'json'
            runner.updated_at = datetime.utcnow()
        else:
            db.add(models.Config(key='runner_font_settings', value=json.dumps(runner_data), type='json'))
    
    db.commit()
    return {"status": "ok", "message": "Все настройки печати сохранены"}

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import Config

router = APIRouter()

class PrintSettings(BaseModel):
    allow_reprint_kitchen: bool = True
    allow_reprint_receipt: bool = True
    reprint_block_time: int = 5

@router.get("/settings/print")
def get_print_settings(db: Session = Depends(get_db)):
    """Get print settings"""
    settings = db.query(Config).filter(Config.key == 'print_settings').first()
    if settings and settings.value:
        import json
        return json.loads(settings.value)
    
    # Return defaults
    return {
        "allow_reprint_kitchen": True,
        "allow_reprint_receipt": True,
        "reprint_block_time": 5
    }

@router.post("/settings/print")
def save_print_settings(settings: PrintSettings, db: Session = Depends(get_db)):
    """Save print settings"""
    import json
    
    config = db.query(Config).filter(Config.key == 'print_settings').first()
    if config:
        config.value = json.dumps(settings.dict())
    else:
        config = Config(key='print_settings', value=json.dumps(settings.dict()))
        db.add(config)
    
    db.commit()
    return {"ok": True}

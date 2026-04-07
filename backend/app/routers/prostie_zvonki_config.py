from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app import models

router = APIRouter()

# PZ Settings schemas
class PZSettings(BaseModel):
    server_url: str = "https://interaction.prostiezvonki.ru"
    api_token: str = ""
    crm_token: str = "soho-crm-token"
    is_active: bool = False
    test_mode: bool = True

class PZExtensionCreate(BaseModel):
    employee_id: str
    extension: str

class PZExtensionResponse(BaseModel):
    id: int
    employee_id: str
    extension: str
    name: str

# Settings endpoints
@router.get("/settings")
async def get_pz_settings(db: Session = Depends(get_db)):
    """Get Prostie Zvonki settings"""
    settings = db.query(models.PZSetting).first()
    if not settings:
        # Return defaults
        return {
            "server_url": "https://interaction.prostiezvonki.ru",
            "api_token": "",
            "crm_token": "soho-crm-token",
            "is_active": False,
            "test_mode": True
        }
    return {
        "server_url": settings.server_url,
        "api_token": settings.api_token,
        "crm_token": settings.crm_token,
        "is_active": settings.is_active,
        "test_mode": settings.test_mode
    }

@router.post("/settings")
async def save_pz_settings(data: PZSettings, db: Session = Depends(get_db)):
    """Save Prostie Zvonki settings"""
    settings = db.query(models.PZSetting).first()
    if not settings:
        settings = models.PZSetting()
        db.add(settings)
    
    settings.server_url = data.server_url
    settings.api_token = data.api_token
    settings.crm_token = data.crm_token
    settings.is_active = data.is_active
    settings.test_mode = data.test_mode
    settings.updated_at = datetime.utcnow()
    
    db.commit()
    return {"status": "saved"}

# Extension endpoints
@router.get("/extensions")
async def get_pz_extensions(db: Session = Depends(get_db)):
    """Get PZ extensions (employees with internal numbers)"""
    extensions = db.query(models.PZExtension).all()
    result = []
    for ext in extensions:
        # Get employee name if not stored in extension
        name = ext.name
        if not name:
            emp = db.query(models.Employee).filter(
                models.Employee.extension == ext.employee_id
            ).first()
            name = emp.name if emp else ext.employee_id
        
        result.append({
            "id": ext.id,
            "employee_id": ext.employee_id,
            "extension": ext.extension,
            "name": name,
            "employee_name": name  # For backward compatibility
        })
    return result

@router.post("/extensions")
async def add_pz_extension(data: PZExtensionCreate, db: Session = Depends(get_db)):
    """Add PZ extension for employee"""
    # Check if extension already exists
    existing = db.query(models.PZExtension).filter(
        models.PZExtension.employee_id == data.employee_id
    ).first()
    
    if existing:
        # Update existing
        existing.extension = data.extension
    else:
        # Get employee name
        emp = db.query(models.Employee).filter(
            models.Employee.extension == data.employee_id
        ).first()
        
        ext = models.PZExtension(
            employee_id=data.employee_id,
            extension=data.extension,
            name=emp.name if emp else ""
        )
        db.add(ext)
    
    db.commit()
    return {"status": "added"}

@router.delete("/extensions/{ext_id}")
async def delete_pz_extension(ext_id: int, db: Session = Depends(get_db)):
    """Delete PZ extension"""
    ext = db.query(models.PZExtension).filter(models.PZExtension.id == ext_id).first()
    if not ext:
        raise HTTPException(status_code=404, detail="Extension not found")
    
    db.delete(ext)
    db.commit()
    return {"status": "deleted"}

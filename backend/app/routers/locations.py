from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db
from app import models

router = APIRouter()

# ========== SCHEMAS ==========

class LocationCreate(BaseModel):
    name: str
    type: str = "cafe"
    address: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class LocationResponse(BaseModel):
    id: int
    name: str
    type: str
    address: Optional[str]
    phone: Optional[str]
    is_active: bool

# ========== ENDPOINTS ==========

@router.get("/locations", response_model=List[LocationResponse])
async def get_locations(db: Session = Depends(get_db)):
    """Get all locations for current company"""
    # Get current company (from auth in real implementation)
    company = db.query(models.Company).filter(models.Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    locations = db.query(models.Location).filter(
        models.Location.company_id == company.id
    ).order_by(models.Location.name).all()
    
    return locations

@router.post("/locations")
async def create_location(data: LocationCreate, db: Session = Depends(get_db)):
    """Create new location"""
    company = db.query(models.Company).filter(models.Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    location = models.Location(
        company_id=company.id,
        name=data.name,
        type=data.type,
        address=data.address,
        phone=data.phone,
        is_active=data.is_active
    )
    
    db.add(location)
    db.commit()
    db.refresh(location)
    
    return {
        "id": location.id,
        "name": location.name,
        "type": location.type,
        "address": location.address,
        "phone": location.phone,
        "is_active": location.is_active
    }

@router.put("/locations/{location_id}")
async def update_location(location_id: int, data: LocationUpdate, db: Session = Depends(get_db)):
    """Update location"""
    location = db.query(models.Location).filter(models.Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    if data.name is not None:
        location.name = data.name
    if data.type is not None:
        location.type = data.type
    if data.address is not None:
        location.address = data.address
    if data.phone is not None:
        location.phone = data.phone
    if data.is_active is not None:
        location.is_active = data.is_active
    
    db.commit()
    db.refresh(location)
    
    return {
        "id": location.id,
        "name": location.name,
        "type": location.type,
        "address": location.address,
        "phone": location.phone,
        "is_active": location.is_active
    }

@router.delete("/locations/{location_id}")
async def delete_location(location_id: int, db: Session = Depends(get_db)):
    """Delete location (soft delete by setting inactive)"""
    location = db.query(models.Location).filter(models.Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    # Soft delete
    location.is_active = False
    db.commit()
    
    return {"status": "ok"}

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app import models

router = APIRouter()

class StatusCreate(BaseModel):
    status_id: str
    name: str
    color: str = "#e94560"
    icon: str = "📋"
    sort_order: int = 0
    is_default: bool = False
    is_final: bool = False

class StatusUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_default: Optional[bool] = None
    is_final: Optional[bool] = None

@router.get("/statuses")
async def get_statuses(db: Session = Depends(get_db)):
    """Get all order statuses"""
    statuses = db.query(models.OrderStatus).order_by(models.OrderStatus.sort_order).all()
    return [{"status_id": s.status_id, "name": s.name, "color": s.color, 
             "icon": s.icon, "sort_order": s.sort_order, 
             "is_default": s.is_default, "is_final": s.is_final} for s in statuses]

@router.post("/statuses")
async def create_status(data: StatusCreate, db: Session = Depends(get_db)):
    """Create new status"""
    # Check if status_id exists
    existing = db.query(models.OrderStatus).filter(models.OrderStatus.status_id == data.status_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Status with this ID already exists")
    
    status = models.OrderStatus(
        status_id=data.status_id,
        name=data.name,
        color=data.color,
        icon=data.icon,
        sort_order=data.sort_order,
        is_default=data.is_default,
        is_final=data.is_final,
        created_at=datetime.utcnow()
    )
    db.add(status)
    db.commit()
    db.refresh(status)
    return {"status": "created", "status_id": status.status_id}

@router.put("/statuses/{status_id}")
async def update_status(status_id: str, data: StatusUpdate, db: Session = Depends(get_db)):
    """Update status"""
    status = db.query(models.OrderStatus).filter(models.OrderStatus.status_id == status_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="Status not found")
    
    if data.name is not None:
        status.name = data.name
    if data.color is not None:
        status.color = data.color
    if data.icon is not None:
        status.icon = data.icon
    if data.sort_order is not None:
        status.sort_order = data.sort_order
    if data.is_default is not None:
        status.is_default = data.is_default
    if data.is_final is not None:
        status.is_final = data.is_final
    
    status.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(status)
    return {"status": "updated", "status_id": status.status_id}

@router.delete("/statuses/{status_id}")
async def delete_status(status_id: str, db: Session = Depends(get_db)):
    """Delete status"""
    status = db.query(models.OrderStatus).filter(models.OrderStatus.status_id == status_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="Status not found")
    
    db.delete(status)
    db.commit()
    return {"status": "deleted", "status_id": status_id}

@router.post("/statuses/reorder")
async def reorder_statuses(data: dict, db: Session = Depends(get_db)):
    """Reorder statuses - update sort_order for multiple statuses"""
    try:
        statuses = data.get('statuses', [])
        for item in statuses:
            status = db.query(models.OrderStatus).filter(models.OrderStatus.status_id == item['status_id']).first()
            if status:
                status.sort_order = item['sort_order']
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

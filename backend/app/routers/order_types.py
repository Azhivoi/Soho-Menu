from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app import models

router = APIRouter()

class OrderTypeCreate(BaseModel):
    type_id: str
    name: str
    color: str = "#e94560"
    icon: str = "🍽️"
    sort_order: int = 0
    is_default: bool = False

class OrderTypeUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_default: Optional[bool] = None

@router.get("/order-types")
async def get_order_types(db: Session = Depends(get_db)):
    """Get all order types"""
    types = db.query(models.OrderType).order_by(models.OrderType.sort_order).all()
    return [{"type_id": t.type_id, "name": t.name, "color": t.color, 
             "icon": t.icon, "sort_order": t.sort_order, "is_default": t.is_default} for t in types]

@router.post("/order-types")
async def create_order_type(data: OrderTypeCreate, db: Session = Depends(get_db)):
    """Create new order type"""
    existing = db.query(models.OrderType).filter(models.OrderType.type_id == data.type_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Order type with this ID already exists")
    
    order_type = models.OrderType(
        type_id=data.type_id,
        name=data.name,
        color=data.color,
        icon=data.icon,
        sort_order=data.sort_order,
        is_default=data.is_default,
        created_at=datetime.utcnow()
    )
    db.add(order_type)
    db.commit()
    db.refresh(order_type)
    return {"status": "created", "type_id": order_type.type_id}

@router.put("/order-types/{type_id}")
async def update_order_type(type_id: str, data: OrderTypeUpdate, db: Session = Depends(get_db)):
    """Update order type"""
    order_type = db.query(models.OrderType).filter(models.OrderType.type_id == type_id).first()
    if not order_type:
        raise HTTPException(status_code=404, detail="Order type not found")
    
    if data.name is not None:
        order_type.name = data.name
    if data.color is not None:
        order_type.color = data.color
    if data.icon is not None:
        order_type.icon = data.icon
    if data.sort_order is not None:
        order_type.sort_order = data.sort_order
    if data.is_default is not None:
        order_type.is_default = data.is_default
    
    order_type.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order_type)
    return {"status": "updated", "type_id": order_type.type_id}

@router.delete("/order-types/{type_id}")
async def delete_order_type(type_id: str, db: Session = Depends(get_db)):
    """Delete order type"""
    order_type = db.query(models.OrderType).filter(models.OrderType.type_id == type_id).first()
    if not order_type:
        raise HTTPException(status_code=404, detail="Order type not found")
    
    db.delete(order_type)
    db.commit()
    return {"status": "deleted", "type_id": type_id}

@router.post("/order-types/reorder")
async def reorder_order_types(data: dict, db: Session = Depends(get_db)):
    """Reorder order types"""
    try:
        types = data.get('types', [])
        for item in types:
            order_type = db.query(models.OrderType).filter(models.OrderType.type_id == item['type_id']).first()
            if order_type:
                order_type.sort_order = item['sort_order']
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

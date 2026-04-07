from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app import models

router = APIRouter()

# Discount/Promo schemas
class DiscountCreate(BaseModel):
    name: str
    value: float
    discount_type: str = "percent"  # percent, fixed
    applies_to: str = "order"  # order, item, category
    min_order_amount: Optional[float] = None
    max_discount: Optional[float] = None
    is_active: bool = True

class DiscountResponse(BaseModel):
    id: int
    name: str
    value: float
    discount_type: str
    applies_to: str
    is_active: bool

# Discount endpoints
@router.get("/discounts", response_model=List[DiscountResponse])
async def get_discounts(db: Session = Depends(get_db)):
    """Get all discounts/promos"""
    discounts = db.query(models.Discount).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "value": float(d.value) if d.value else 0,
            "discount_type": d.discount_type or "percent",
            "applies_to": d.applies_to or "order",
            "is_active": d.is_active
        }
        for d in discounts
    ]

@router.post("/discounts")
async def create_discount(data: DiscountCreate, db: Session = Depends(get_db)):
    """Create new discount"""
    discount = models.Discount(
        name=data.name,
        value=data.value,
        discount_type=data.discount_type,
        applies_to=data.applies_to,
        min_order_amount=data.min_order_amount,
        max_discount=data.max_discount,
        is_active=data.is_active
    )
    db.add(discount)
    db.commit()
    db.refresh(discount)
    return {"id": discount.id, "status": "created"}

@router.put("/discounts/{discount_id}")
async def update_discount(discount_id: int, data: DiscountCreate, db: Session = Depends(get_db)):
    """Update discount"""
    discount = db.query(models.Discount).filter(models.Discount.id == discount_id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    
    discount.name = data.name
    discount.value = data.value
    discount.discount_type = data.discount_type
    discount.applies_to = data.applies_to
    discount.min_order_amount = data.min_order_amount
    discount.max_discount = data.max_discount
    discount.is_active = data.is_active
    
    db.commit()
    return {"status": "updated"}

@router.delete("/discounts/{discount_id}")
async def delete_discount(discount_id: int, db: Session = Depends(get_db)):
    """Delete discount"""
    discount = db.query(models.Discount).filter(models.Discount.id == discount_id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    
    db.delete(discount)
    db.commit()
    return {"status": "deleted"}

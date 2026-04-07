from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app import models

router = APIRouter()

class CustomerCreate(BaseModel):
    phone: str
    name: Optional[str] = None
    address: Optional[str] = None
    discount_percent: Optional[int] = 0
    birthday: Optional[str] = None
    comment: Optional[str] = None

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    discount_percent: Optional[int] = None
    birthday: Optional[str] = None
    comment: Optional[str] = None

@router.get("/")
async def get_customers(phone: Optional[str] = None, db: Session = Depends(get_db)):
    """Get all customers or filter by phone"""
    query = db.query(models.Customer)
    
    if phone:
        # Normalize phone for search
        phone_clean = phone.replace(r'\D', '', regex=True)
        query = query.filter(models.Customer.phone.contains(phone_clean))
    
    customers = query.order_by(models.Customer.name).all()
    
    return [
        {
            "id": c.id,
            "phone": c.phone,
            "name": c.name,
            "address": c.address,
            "discount_percent": c.discount_percent,
            "birthday": c.birthday.isoformat() if c.birthday else None,
            "comment": c.comment,
            "bonus_points": c.bonus_points,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in customers
    ]

@router.get("/{phone}")
async def get_customer_by_phone(phone: str, db: Session = Depends(get_db)):
    """Get customer by phone number"""
    # Try exact match first
    customer = db.query(models.Customer).filter(models.Customer.phone == phone).first()
    
    if not customer:
        # Try normalized phone
        phone_clean = ''.join(filter(str.isdigit, phone))
        customer = db.query(models.Customer).filter(models.Customer.phone.contains(phone_clean)).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get customer stats from orders
    orders = db.query(models.Order).filter(
        (models.Order.delivery_phone == phone) | 
        (models.Order.delivery_phone == phone)
    ).all()
    
    total_orders = len(orders)
    total_amount = sum(float(o.total_amount) for o in orders)
    total_bonus = sum(int(o.bonus_earned or 0) for o in orders)
    
    return {
        "id": customer.id,
        "phone": customer.phone,
        "name": customer.name,
        "address": customer.address,
        "discount_percent": customer.discount_percent,
        "birthday": customer.birthday.isoformat() if customer.birthday else None,
        "comment": customer.comment,
        "bonus_points": customer.bonus_points,
        "stats": {
            "total_orders": total_orders,
            "total_amount": total_amount,
            "total_bonus": total_bonus,
            "avg_check": total_amount / total_orders if total_orders > 0 else 0
        }
    }

@router.post("/")
async def create_customer(data: CustomerCreate, db: Session = Depends(get_db)):
    """Create new customer"""
    # Normalize phone
    phone_clean = ''.join(filter(str.isdigit, data.phone))
    
    existing = db.query(models.Customer).filter(models.Customer.phone == phone_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail="Customer with this phone already exists")
    
    customer = models.Customer(
        phone=phone_clean,
        name=data.name,
        address=data.address,
        discount_percent=data.discount_percent or 0,
        birthday=datetime.strptime(data.birthday, '%Y-%m-%d').date() if data.birthday else None,
        comment=data.comment,
        created_at=datetime.utcnow()
    )
    
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    return {"status": "created", "id": customer.id}

@router.put("/{phone}")
async def update_customer(phone: str, data: CustomerUpdate, db: Session = Depends(get_db)):
    """Update customer by phone"""
    # Normalize phone
    phone_clean = ''.join(filter(str.isdigit, phone))
    
    customer = db.query(models.Customer).filter(models.Customer.phone == phone_clean).first()
    
    if not customer:
        # Create new customer if not exists
        customer = models.Customer(phone=phone_clean)
        db.add(customer)
    
    if data.name is not None:
        customer.name = data.name
    if data.address is not None:
        customer.address = data.address
    if data.discount_percent is not None:
        customer.discount_percent = data.discount_percent
    if data.birthday is not None:
        customer.birthday = datetime.strptime(data.birthday, '%Y-%m-%d').date() if data.birthday else None
    if data.comment is not None:
        customer.comment = data.comment
    
    customer.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(customer)
    
    return {"status": "updated", "id": customer.id}

@router.get("/{phone}/orders")
async def get_customer_orders(phone: str, limit: int = 50, db: Session = Depends(get_db)):
    """Get customer order history"""
    orders = db.query(models.Order).filter(
        (models.Order.delivery_phone == phone) | 
        (models.Order.delivery_phone == phone)
    ).order_by(models.Order.created_at.desc()).limit(limit).all()
    
    return [
        {
            "id": o.id,
            "order_number": o.order_number,
            "total_amount": float(o.total_amount),
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "items": [
                {
                    "name": i.name or f"Товар #{i.product_id}",
                    "quantity": i.quantity,
                    "price": float(i.price)
                }
                for i in o.items
            ]
        }
        for o in orders
    ]

class CustomerImportItem(BaseModel):
    phone: str
    name: Optional[str] = None
    email: Optional[str] = None
    bonus_points: Optional[int] = 0

@router.delete("/{customer_id}")
async def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    """Delete customer by ID"""
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    db.delete(customer)
    db.commit()
    return {"status": "deleted", "id": customer_id}

@router.post("/import")
async def import_customers(data: List[CustomerImportItem], db: Session = Depends(get_db)):
    """Bulk import customers"""
    imported = 0
    updated = 0
    
    for item in data:
        # Normalize phone
        phone_clean = ''.join(filter(str.isdigit, item.phone))
        if not phone_clean:
            continue
            
        existing = db.query(models.Customer).filter(models.Customer.phone == phone_clean).first()
        
        if existing:
            # Update existing
            if item.name:
                existing.name = item.name
            if item.bonus_points:
                existing.bonus_points = item.bonus_points
            updated += 1
        else:
            # Create new
            customer = models.Customer(
                phone=phone_clean,
                name=item.name,
                bonus_points=item.bonus_points or 0,
                created_at=datetime.utcnow()
            )
            db.add(customer)
            imported += 1
    
    db.commit()
    return {"imported": imported, "updated": updated}

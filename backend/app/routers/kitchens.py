from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models import Kitchen, Category

router = APIRouter()

class KitchenCreate(BaseModel):
    kitchen_id: str
    name: str
    icon: str = '🍽️'
    color: str = '#ff6b35'
    print_runner: bool = True
    is_active: bool = True
    sort_order: int = 0

class KitchenUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    print_runner: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

class KitchenResponse(BaseModel):
    kitchen_id: str
    name: str
    icon: str
    color: str
    print_runner: bool
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True

@router.get("/kitchens", response_model=List[KitchenResponse])
def get_kitchens(db: Session = Depends(get_db)):
    """Get all kitchens ordered by sort_order"""
    kitchens = db.query(Kitchen).order_by(Kitchen.sort_order).all()
    return kitchens

@router.post("/kitchens", response_model=KitchenResponse)
def create_kitchen(kitchen: KitchenCreate, db: Session = Depends(get_db)):
    """Create a new kitchen"""
    db_kitchen = Kitchen(**kitchen.dict())
    db.add(db_kitchen)
    db.commit()
    db.refresh(db_kitchen)
    return db_kitchen

@router.put("/kitchens/{kitchen_id}", response_model=KitchenResponse)
def update_kitchen(kitchen_id: str, kitchen: KitchenUpdate, db: Session = Depends(get_db)):
    """Update a kitchen"""
    db_kitchen = db.query(Kitchen).filter(Kitchen.kitchen_id == kitchen_id).first()
    if not db_kitchen:
        raise HTTPException(status_code=404, detail="Kitchen not found")
    
    for key, value in kitchen.dict(exclude_unset=True).items():
        setattr(db_kitchen, key, value)
    
    db.commit()
    db.refresh(db_kitchen)
    return db_kitchen

@router.delete("/kitchens/{kitchen_id}")
def delete_kitchen(kitchen_id: str, db: Session = Depends(get_db)):
    """Delete a kitchen and unassign categories"""
    db_kitchen = db.query(Kitchen).filter(Kitchen.kitchen_id == kitchen_id).first()
    if not db_kitchen:
        raise HTTPException(status_code=404, detail="Kitchen not found")
    
    # Unassign categories from this kitchen
    db.query(Category).filter(Category.kitchen_id == kitchen_id).update({"kitchen_id": None})
    
    db.delete(db_kitchen)
    db.commit()
    return {"status": "ok"}

@router.post("/kitchens/reorder")
def reorder_kitchens(order: List[str], db: Session = Depends(get_db)):
    """Reorder kitchens"""
    for idx, kitchen_id in enumerate(order):
        db.query(Kitchen).filter(Kitchen.kitchen_id == kitchen_id).update({"sort_order": idx})
    db.commit()
    return {"status": "ok"}

# Categories endpoint for frontend compatibility
@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """Get all categories with kitchen assignment"""
    from app.models import Category
    
    cats = db.query(Category).order_by(Category.sort_order).all()
    result = []
    for cat in cats:
        result.append({
            "id": cat.id,
            "category_id": cat.category_id or str(cat.id),
            "name": cat.name_ru or cat.name_en or f"Category {cat.id}",
            "slug": cat.slug,
            "kitchen_id": cat.kitchen_id,
            "sort_order": cat.sort_order,
            "is_active": cat.is_active
        })
    return result

# Category kitchen assignment
@router.put("/categories/{category_id}/kitchen")
def assign_category_kitchen(category_id: str, data: dict, db: Session = Depends(get_db)):
    """Assign or unassign a category to/from a kitchen"""
    kitchen_id = data.get("kitchen_id")
    
    category = db.query(Category).filter(
        (Category.category_id == category_id) | (Category.id == category_id)
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Validate kitchen if provided
    if kitchen_id:
        kitchen = db.query(Kitchen).filter(Kitchen.kitchen_id == kitchen_id).first()
        if not kitchen:
            raise HTTPException(status_code=404, detail="Kitchen not found")
    
    category.kitchen_id = kitchen_id
    db.commit()
    
    return {"status": "ok", "category_id": category_id, "kitchen_id": kitchen_id}

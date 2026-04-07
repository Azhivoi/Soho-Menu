from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app import models

router = APIRouter()

class MarkCreate(BaseModel):
    name: str
    color: str
    icon: str
    mark_type: str = "order"  # order, client, product
    options: Optional[List[dict]] = None

class MarkUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    mark_type: Optional[str] = None
    options: Optional[List[dict]] = None

class MarkResponse(BaseModel):
    mark_id: str
    name: str
    color: str
    icon: str
    mark_type: str
    options: Optional[List[dict]] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

@router.get("")
async def get_marks(db: Session = Depends(get_db)):
    """Get all marks"""
    import json
    marks = db.query(models.Mark).order_by(models.Mark.sort_order).all()
    result = []
    for m in marks:
        result.append({
            "mark_id": m.mark_id,
            "name": m.name,
            "color": m.color,
            "icon": m.icon,
            "mark_type": m.mark_type,
            "options": json.loads(m.options) if m.options else None,
            "sort_order": m.sort_order,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })
    return result

@router.post("")
async def create_mark(data: MarkCreate, db: Session = Depends(get_db)):
    """Create new mark"""
    import uuid
    import json
    
    mark = models.Mark(
        mark_id=str(uuid.uuid4())[:8],
        name=data.name,
        color=data.color,
        icon=data.icon,
        mark_type=data.mark_type,
        options=json.dumps(data.options) if data.options else None,
        created_at=datetime.utcnow()
    )
    db.add(mark)
    db.commit()
    db.refresh(mark)
    return {
        "mark_id": mark.mark_id,
        "name": mark.name,
        "color": mark.color,
        "icon": mark.icon,
        "mark_type": mark.mark_type,
        "options": data.options,
        "sort_order": mark.sort_order,
        "created_at": mark.created_at.isoformat() if mark.created_at else None
    }

@router.put("/{mark_id}")
async def update_mark(mark_id: str, data: MarkUpdate, db: Session = Depends(get_db)):
    """Update mark"""
    import json
    
    mark = db.query(models.Mark).filter(models.Mark.mark_id == mark_id).first()
    if not mark:
        raise HTTPException(status_code=404, detail="Mark not found")
    
    if data.name is not None:
        mark.name = data.name
    if data.color is not None:
        mark.color = data.color
    if data.icon is not None:
        mark.icon = data.icon
    if data.mark_type is not None:
        mark.mark_type = data.mark_type
    if data.options is not None:
        mark.options = json.dumps(data.options)
    
    mark.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(mark)
    return {
        "mark_id": mark.mark_id,
        "name": mark.name,
        "color": mark.color,
        "icon": mark.icon,
        "mark_type": mark.mark_type,
        "options": data.options,
        "sort_order": mark.sort_order,
        "created_at": mark.created_at.isoformat() if mark.created_at else None
    }

@router.delete("/{mark_id}")
async def delete_mark(mark_id: str, db: Session = Depends(get_db)):
    """Delete mark"""
    mark = db.query(models.Mark).filter(models.Mark.mark_id == mark_id).first()
    if not mark:
        raise HTTPException(status_code=404, detail="Mark not found")
    
    db.delete(mark)
    db.commit()
    return {"status": "deleted", "mark_id": mark_id}

class ReorderRequest(BaseModel):
    order: List[str]

@router.post("/reorder")
async def reorder_marks(data: ReorderRequest, db: Session = Depends(get_db)):
    """Reorder marks by updating sort_order"""
    for idx, mark_id in enumerate(data.order):
        mark = db.query(models.Mark).filter(models.Mark.mark_id == mark_id).first()
        if mark:
            mark.sort_order = idx
    db.commit()
    return {"status": "reordered"}

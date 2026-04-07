from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
import json

from app.database import get_db
from app import models

router = APIRouter()

# ========== SUPPLIERS (ПОСТАВЩИКИ) ==========

class SupplierCreate(BaseModel):
    name: str
    full_name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    inn: Optional[str] = None
    kpp: Optional[str] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    bik: Optional[str] = None
    contract_number: Optional[str] = None
    contract_date: Optional[date] = None

@router.get("/suppliers")
async def list_suppliers(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """List all suppliers"""
    query = db.query(models.Supplier)
    if active_only:
        query = query.filter(models.Supplier.is_active == True)
    return query.order_by(models.Supplier.name).all()

@router.post("/suppliers")
async def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db)
):
    """Create new supplier"""
    supplier = models.Supplier(**data.dict())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return {"id": supplier.id, "status": "created"}

@router.post("/suppliers/import")
async def import_suppliers(
    suppliers: List[SupplierCreate],
    db: Session = Depends(get_db)
):
    """Import suppliers from file"""
    created = 0
    for data in suppliers:
        supplier = models.Supplier(**data.dict())
        db.add(supplier)
        created += 1
    db.commit()
    return {"imported": created}

@router.get("/suppliers/export")
async def export_suppliers(db: Session = Depends(get_db)):
    """Export all suppliers"""
    suppliers = db.query(models.Supplier).filter(
        models.Supplier.is_active == True
    ).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "full_name": s.full_name,
            "contact_person": s.contact_person,
            "phone": s.phone,
            "email": s.email,
            "address": s.address,
            "inn": s.inn,
            "kpp": s.kpp
        }
        for s in suppliers
    ]

# ========== INVOICES (НАКЛАДНЫЕ) ==========

class InvoiceItemCreate(BaseModel):
    original_name: str
    ingredient_id: Optional[int] = None
    quantity: float
    unit: str
    price_per_unit: float
    total_price: float

class InvoiceCreate(BaseModel):
    invoice_number: str
    supplier_id: int
    invoice_date: date
    notes: Optional[str] = None
    items: List[InvoiceItemCreate]

@router.get("/invoices")
async def list_invoices(
    supplier_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List warehouse invoices"""
    query = db.query(models.WarehouseInvoice)
    
    if supplier_id:
        query = query.filter(models.WarehouseInvoice.supplier_id == supplier_id)
    if date_from:
        query = query.filter(models.WarehouseInvoice.invoice_date >= date_from)
    if date_to:
        query = query.filter(models.WarehouseInvoice.invoice_date <= date_to)
    if status:
        query = query.filter(models.WarehouseInvoice.status == status)
    
    invoices = query.order_by(models.WarehouseInvoice.created_at.desc()).all()
    
    result = []
    for inv in invoices:
        supplier = db.query(models.Supplier).get(inv.supplier_id)
        item_count = db.query(models.WarehouseInvoiceItem).filter(
            models.WarehouseInvoiceItem.invoice_id == inv.id
        ).count()
        
        result.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "supplier_name": supplier.name if supplier else None,
            "invoice_date": inv.invoice_date.isoformat(),
            "total_amount": float(inv.total_amount) if inv.total_amount else 0,
            "status": inv.status,
            "item_count": item_count,
            "created_at": inv.created_at.isoformat()
        })
    
    return result

@router.post("/invoices")
async def create_invoice(
    data: InvoiceCreate,
    db: Session = Depends(get_db)
):
    """Create new invoice with items"""
    # Calculate total
    total = sum(item.total_price for item in data.items)
    
    # Create invoice
    invoice = models.WarehouseInvoice(
        invoice_number=data.invoice_number,
        supplier_id=data.supplier_id,
        invoice_date=data.invoice_date,
        total_amount=total,
        status='draft',
        notes=data.notes
    )
    db.add(invoice)
    db.flush()
    
    # Add items
    for item_data in data.items:
        item = models.WarehouseInvoiceItem(
            invoice_id=invoice.id,
            **item_data.dict()
        )
        db.add(item)
        
        # If ingredient matched, update stock
        if item_data.ingredient_id:
            update_stock_on_receipt(
                db, item_data.ingredient_id, 
                item_data.quantity, item_data.unit
            )
    
    db.commit()
    return {"id": invoice.id, "status": "created", "total": total}

def update_stock_on_receipt(db: Session, ingredient_id: int, quantity: float, unit: str):
    """Update stock when receiving goods"""
    stock = db.query(models.WarehouseStock).filter(
        models.WarehouseStock.ingredient_id == ingredient_id
    ).first()
    
    if not stock:
        stock = models.WarehouseStock(
            ingredient_id=ingredient_id,
            quantity=quantity,
            unit=unit
        )
        db.add(stock)
    else:
        stock.quantity += quantity
        stock.last_updated = datetime.utcnow()
    
    # Add movement record
    movement = models.WarehouseMovement(
        ingredient_id=ingredient_id,
        movement_type='receipt',
        quantity=quantity,
        unit=unit,
        notes='Приход по накладной'
    )
    db.add(movement)

@router.post("/invoices/{invoice_id}/process")
async def process_invoice(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """Process invoice (confirm receipt)"""
    invoice = db.query(models.WarehouseInvoice).get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice.status = 'processed'
    invoice.processed_at = datetime.utcnow()
    
    db.commit()
    return {"status": "processed"}

# ========== OCR & NAME MATCHING ==========

@router.post("/invoices/{invoice_id}/scan")
async def scan_invoice(
    invoice_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and scan invoice image for OCR"""
    # Save file
    file_path = f"/tmp/invoice_{invoice_id}_{file.filename}"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Create OCR record
    ocr_doc = models.OcrDocument(
        invoice_id=invoice_id,
        original_image_url=file_path,
        status='pending'
    )
    db.add(ocr_doc)
    db.commit()
    
    # TODO: Call OCR service here
    # For now, return placeholder
    return {
        "ocr_id": ocr_doc.id,
        "status": "pending",
        "message": "Document queued for OCR processing"
    }

@router.post("/ingredients/match-name")
async def match_ingredient_name(
    original_name: str,
    supplier_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Match original name from invoice to ingredient"""
    
    # 1. Check exact mapping
    mapping = db.query(models.IngredientNameMapping).filter(
        models.IngredientNameMapping.original_name.ilike(original_name),
        models.IngredientNameMapping.is_active == True
    ).first()
    
    if mapping:
        return {
            "matched": True,
            "ingredient_id": mapping.ingredient_id,
            "method": "mapping",
            "confidence": 100
        }
    
    # 2. Try fuzzy match with ingredient names
    ingredients = db.query(models.Ingredient).filter(
        models.Ingredient.is_active == True
    ).all()
    
    best_match = None
    best_score = 0
    
    for ing in ingredients:
        score = calculate_similarity(original_name.lower(), ing.name_ru.lower())
        if score > best_score and score > 60:  # Threshold 60%
            best_score = score
            best_match = ing
    
    if best_match:
        return {
            "matched": True,
            "ingredient_id": best_match.id,
            "ingredient_name": best_match.name_ru,
            "method": "fuzzy",
            "confidence": best_score
        }
    
    return {
        "matched": False,
        "suggestions": [ing.name_ru for ing in ingredients[:5]]
    }

def calculate_similarity(s1: str, s2: str) -> float:
    """Calculate string similarity (Levenshtein-based)"""
    # Simple implementation - can be replaced with more sophisticated algorithm
    if s1 == s2:
        return 100.0
    
    # Check if one contains the other
    if s1 in s2 or s2 in s1:
        return 80.0
    
    # Word-based similarity
    words1 = set(s1.split())
    words2 = set(s2.split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return (len(intersection) / len(union)) * 100

# ========== STOCK & MOVEMENTS ==========

@router.get("/stock")
async def get_stock(
    ingredient_id: Optional[int] = None,
    low_stock: bool = False,
    db: Session = Depends(get_db)
):
    """Get current stock levels"""
    query = db.query(models.WarehouseStock)
    
    if ingredient_id:
        query = query.filter(models.WarehouseStock.ingredient_id == ingredient_id)
    
    if low_stock:
        query = query.filter(
            models.WarehouseStock.quantity <= models.WarehouseStock.min_stock_level
        )
    
    stock_items = query.all()
    
    result = []
    for item in stock_items:
        ingredient = db.query(models.Ingredient).get(item.ingredient_id)
        result.append({
            "ingredient_id": item.ingredient_id,
            "ingredient_name": ingredient.name_ru if ingredient else None,
            "quantity": float(item.quantity),
            "unit": item.unit,
            "min_level": float(item.min_stock_level) if item.min_stock_level else 0,
            "max_level": float(item.max_stock_level) if item.max_stock_level else None,
            "last_updated": item.last_updated.isoformat() if item.last_updated else None
        })
    
    return result

@router.get("/movements")
async def get_movements(
    ingredient_id: Optional[int] = None,
    movement_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get stock movements history"""
    query = db.query(models.WarehouseMovement)
    
    if ingredient_id:
        query = query.filter(models.WarehouseMovement.ingredient_id == ingredient_id)
    if movement_type:
        query = query.filter(models.WarehouseMovement.movement_type == movement_type)
    if date_from:
        query = query.filter(models.WarehouseMovement.created_at >= date_from)
    if date_to:
        query = query.filter(models.WarehouseMovement.created_at <= date_to)
    
    movements = query.order_by(models.WarehouseMovement.created_at.desc()).limit(100).all()
    
    return [
        {
            "id": m.id,
            "ingredient_id": m.ingredient_id,
            "movement_type": m.movement_type,
            "quantity": float(m.quantity),
            "unit": m.unit,
            "reference_type": m.reference_type,
            "notes": m.notes,
            "created_at": m.created_at.isoformat()
        }
        for m in movements
    ]

# ========== INGREDIENTS (ИНГРЕДИЕНТЫ) ==========

class IngredientCreate(BaseModel):
    name_ru: str
    name_en: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = 'кг'

@router.get("/ingredients")
async def list_ingredients(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """List all ingredients"""
    query = db.query(models.Ingredient)
    if active_only:
        query = query.filter(models.Ingredient.is_active == True)
    return query.order_by(models.Ingredient.name_ru).all()

@router.post("/ingredients")
async def create_ingredient(
    data: IngredientCreate,
    db: Session = Depends(get_db)
):
    """Create new ingredient"""
    ingredient = models.Ingredient(**data.dict())
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return {"id": ingredient.id, "status": "created"}


# ========== NAME MAPPINGS (СОПОСТАВЛЕНИЕ НАЗВАНИЙ) ==========

@router.get("/name-mappings")
async def list_name_mappings(
    db: Session = Depends(get_db)
):
    """List all ingredient name mappings"""
    mappings = db.query(models.IngredientNameMapping).filter(
        models.IngredientNameMapping.is_active == True
    ).all()
    
    return [
        {
            "id": m.id,
            "original_name": m.original_name,
            "ingredient_id": m.ingredient_id,
            "supplier_id": m.supplier_id
        }
        for m in mappings
    ]


# ========== INVENTORY (ИНВЕНТАРИЗАЦИИ) ==========

@router.post("/inventory/start")
async def start_inventory_check(
    db: Session = Depends(get_db)
):
    """Start new inventory check"""
    # Get all ingredients with stock
    stock_items = db.query(models.WarehouseStock).all()
    
    inventory = models.InventoryCheck(
        check_date=date.today(),
        status='in_progress'
    )
    db.add(inventory)
    db.flush()
    
    # Create check items
    for stock in stock_items:
        item = models.InventoryCheckItem(
            inventory_id=inventory.id,
            ingredient_id=stock.ingredient_id,
            expected_quantity=stock.quantity,
            actual_quantity=0,  # Will be filled during check
            unit=stock.unit
        )
        db.add(item)
    
    db.commit()
    return {"inventory_id": inventory.id, "items_count": len(stock_items)}

@router.post("/inventory/{inventory_id}/complete")
async def complete_inventory(
    inventory_id: int,
    db: Session = Depends(get_db)
):
    """Complete inventory and apply adjustments"""
    inventory = db.query(models.InventoryCheck).get(inventory_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    items = db.query(models.InventoryCheckItem).filter(
        models.InventoryCheckItem.inventory_id == inventory_id
    ).all()
    
    for item in items:
        if item.actual_quantity != item.expected_quantity:
            difference = item.actual_quantity - item.expected_quantity
            
            # Update stock
            stock = db.query(models.WarehouseStock).filter(
                models.WarehouseStock.ingredient_id == item.ingredient_id
            ).first()
            
            if stock:
                stock.quantity = item.actual_quantity
                stock.last_updated = datetime.utcnow()
            
            # Add movement record
            movement = models.WarehouseMovement(
                ingredient_id=item.ingredient_id,
                movement_type='inventory',
                quantity=difference,
                unit=item.unit,
                reference_id=inventory_id,
                reference_type='inventory',
                notes=f'Инвентаризация #{inventory_id}'
            )
            db.add(movement)
    
    inventory.status = 'completed'
    inventory.completed_at = datetime.utcnow()
    db.commit()
    
    return {"status": "completed"}

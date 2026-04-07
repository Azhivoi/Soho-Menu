from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app import models

router = APIRouter()

class OrderItemCreate(BaseModel):
    product_id: int
    variant_id: int
    quantity: int = 1
    modifiers: List[dict] = []

class OrderCreate(BaseModel):
    customer_id: Optional[int] = None
    customer_name: str
    delivery_phone: str
    delivery_address: Optional[str] = None
    order_type: str = "delivery"  # delivery, pickup, dine_in
    items: List[OrderItemCreate]
    comment: Optional[str] = None
    bonus_used: int = 0
    scheduled_time: Optional[str] = None

# Frontend order format
class FrontendOrderItem(BaseModel):
    product_id: int
    variant_id: int
    quantity: int = 1
    price: float
    category_id: Optional[int] = None

class FrontendOrderCreate(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    delivery_type: str = "delivery"
    delivery_zone: str = "city"
    delivery_time_type: str = "asap"
    scheduled_time: Optional[str] = None
    address: str
    payment_type: str = "cash"
    comment: Optional[str] = None
    promo_code: Optional[str] = None
    promo_discount: float = 0
    discount_percent: float = 0
    discount_amount: float = 0
    items: List[FrontendOrderItem]
    subtotal_amount: float
    delivery_fee: float
    total_amount: float
    marks: Optional[List[str]] = []

@router.post("/")
async def create_order_frontend(order_data: FrontendOrderCreate, db: Session = Depends(get_db)):
    """Create order from frontend (website)"""
    
    # ===== ПЕРЕСЧЁТ СКИДКИ ЧЕРЕЗ PROMOTION SERVICE =====
    from app.routers.promotions_v2 import PromotionService, CalculateOrderRequest, CalculateOrderItem
    
    service = PromotionService(db)
    
    # Формируем items для расчёта с правильными ценами из БД
    calc_items = []
    for item in order_data.items:
        # Получаем актуальную цену из БД (безопасность!)
        product = db.query(models.MenuProduct).filter(
            models.MenuProduct.id == item.variant_id
        ).first()
        
        actual_price = float(product.price) if product else item.price
        
        calc_items.append(CalculateOrderItem(
            product_id=item.product_id,
            variant_id=item.variant_id,
            name=product.name if product else (item.name or f"Товар #{item.product_id}"),
            price=actual_price,
            quantity=item.quantity,
            category_id=item.category_id or (product.category_id if product else None)
        ))
    
    # Рассчитываем скидку через сервис (НЕ доверяем фронту!)
    calc_request = CalculateOrderRequest(
        items=calc_items,
        delivery_cost=order_data.delivery_fee,
        promo_code=order_data.promo_code,
        source="site",
        delivery_type=order_data.delivery_type
    )
    
    calc_result = service.apply_promotions(calc_request)
    
    # Используем ПЕРЕСЧИТАННЫЕ значения
    final_subtotal = calc_result.subtotal
    final_discount = calc_result.discount
    final_delivery_discount = calc_result.delivery_discount
    final_total = calc_result.total
    final_free_delivery = calc_result.free_delivery
    applied_promos = calc_result.applied_promos
    # ================================================================

    # Generate simple sequential order number
    last_order = db.query(models.Order).order_by(models.Order.id.desc()).first()
    next_number = (last_order.id + 1) if last_order else 1
    order_number = str(next_number)

    # Create order с ПЕРЕСЧИТАННЫМИ значениями
    # Parse scheduled_time if provided
    scheduled_time = None
    if order_data.scheduled_time:
        try:
            from datetime import datetime
            scheduled_time = datetime.fromisoformat(order_data.scheduled_time.replace('Z', '+00:00'))
        except:
            pass
    
    order = models.Order(
        order_number=order_number,
        customer_name=order_data.customer_name,
        delivery_phone=order_data.customer_phone,
        delivery_address=order_data.address,
        order_type=order_data.delivery_type,
        total_amount=max(0, final_total),
        bonus_used=0,
        bonus_earned=int(final_subtotal * 0.05),  # 5% от subtotal
        status="new",
        comment=order_data.comment,
        promo_code=order_data.promo_code,
        promo_discount=final_discount,
        promo_promotion_id=applied_promos[0].promotion_id if applied_promos else None,
        delivery_fee=0 if final_free_delivery else order_data.delivery_fee,
        scheduled_time=scheduled_time
    )
    db.add(order)
    db.flush()

    # Create order items
    for i, item_data in enumerate(order_data.items):
        calc_item = calc_items[i]
        
        item_total = calc_item.price * item_data.quantity
        
        # Проверяем, есть ли скидка на этот товар
        item_discount = 0
        for promo in applied_promos:
            for applied_item in promo.applied_items:
                if applied_item.product_id == item_data.product_id:
                    item_discount += applied_item.discount
        
        order_item = models.OrderItem(
            order_id=order.id,
            product_id=item_data.product_id,
            variant_id=item_data.variant_id,
            name=calc_item.name,
            quantity=item_data.quantity,
            price=calc_item.price,
            modifiers=[],
            total_price=item_total - item_discount,
            discount=item_discount
        )
        db.add(order_item)

    # Save order marks
    if order_data.marks:
        for mark_id in order_data.marks:
            order_mark = models.OrderMark(order_id=order.id, mark_id=mark_id)
            db.add(order_mark)

    db.commit()
    db.refresh(order)

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "total_amount": float(order.total_amount),
        "subtotal": final_subtotal,
        "discount": final_discount,
        "bonus_earned": order.bonus_earned,
        "status": order.status,
        "applied_promos": [
            {
                "id": p.promotion_id,
                "name": p.name,
                "discount": p.discount
            } for p in applied_promos
        ]
    }

@router.post("/create")
async def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    """Create new order (CRM/Admin)"""
    
    from app.routers.promotions_v2 import PromotionService, CalculateOrderRequest, CalculateOrderItem
    
    service = PromotionService(db)
    calc_items = []
    
    # Generate order number (SOHO-YYYYMMDD-XXXX)
    today = datetime.now().strftime("%Y%m%d")
    count_today = db.query(models.Order).filter(
        models.Order.created_at >= datetime.now().replace(hour=0, minute=0)
    ).count()
    order_number = f"SOHO-{today}-{count_today + 1:04d}"
    
    # Calculate items
    for item_data in order_data.items:
        product = db.query(models.MenuProduct).filter(
            models.MenuProduct.id == item_data.variant_id
        ).first()
        
        actual_price = float(product.price) if product else 0
        
        calc_items.append(CalculateOrderItem(
            product_id=item_data.product_id,
            variant_id=item_data.variant_id,
            name=product.name if product else f"Товар #{item_data.product_id}",
            price=actual_price,
            quantity=item_data.quantity,
            category_id=product.category_id if product else None
        ))
    
    # Рассчитываем скидку
    final_discount = 0
    final_total = 0
    applied_promos = []
    
    if calc_items:
        calc_request = CalculateOrderRequest(
            items=calc_items,
            promo_code=order_data.promo_code,
            source="posterix",
            delivery_type=order_data.order_type
        )
        calc_result = service.apply_promotions(calc_request)
        final_discount = calc_result.discount
        final_total = calc_result.total
        applied_promos = calc_result.applied_promos
    
    # Parse scheduled_time if provided
    scheduled_time = None
    if order_data.scheduled_time:
        try:
            scheduled_time = datetime.fromisoformat(order_data.scheduled_time.replace('Z', '+00:00'))
        except:
            pass
    
    # Create order
    order = models.Order(
        order_number=order_number,
        customer_name=order_data.customer_name,
        delivery_phone=order_data.delivery_phone,
        delivery_address=order_data.delivery_address,
        order_type=order_data.order_type,
        total_amount=max(0, final_total),
        promo_code=order_data.promo_code,
        promo_discount=final_discount,
        promo_promotion_id=applied_promos[0].promotion_id if applied_promos else None,
        status="new",
        comment=order_data.comment,
        scheduled_time=scheduled_time
    )
    db.add(order)
    db.flush()
    
    # Create order items
    for i, item_data in enumerate(order_data.items):
        if i >= len(calc_items):
            continue
        
        calc_item = calc_items[i]
        item_total = calc_item.price * item_data.quantity
        
        # Проверяем скидку на товар
        item_discount = 0
        for promo in applied_promos:
            for applied_item in promo.applied_items:
                if applied_item.product_id == item_data.product_id:
                    item_discount += applied_item.discount
        
        order_item = models.OrderItem(
            order_id=order.id,
            product_id=item_data.product_id,
            variant_id=item_data.variant_id,
            name=calc_item.name,
            quantity=item_data.quantity,
            price=calc_item.price,
            modifiers=item_data.modifiers,
            total_price=item_total - item_discount,
            discount=item_discount
        )
        db.add(order_item)
    
    db.commit()
    db.refresh(order)
    
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "total_amount": float(order.total_amount),
        "discount": final_discount,
        "status": order.status
    }

# Legacy function - kept for compatibility
async def create_order_legacy(order_data: OrderCreate, db: Session = Depends(get_db)):
    """Create new order (legacy version without promotions)"""
    
    # Generate order number (SOHO-YYYYMMDD-XXXX)
    today = datetime.now().strftime("%Y%m%d")
    count_today = db.query(models.Order).filter(
        models.Order.created_at >= datetime.now().replace(hour=0, minute=0)
    ).count()
    order_number = f"SOHO-{today}-{count_today + 1:04d}"
    
    # Calculate total
    total_amount = 0
    bonus_earned = 0
    
    # Create order
    order = models.Order(
        order_number=order_number,
        customer_name=order_data.customer_name,
        delivery_phone=order_data.delivery_phone,
        delivery_address=order_data.delivery_address,
        order_type=order_data.order_type,
        total_amount=0,  # Will update after items
        bonus_used=order_data.bonus_used,
        status="new"
    )
    db.add(order)
    db.flush()
    
    # Create order items
    for item_data in order_data.items:
        variant = db.query(models.ProductVariant).filter(
            models.ProductVariant.id == item_data.variant_id
        ).first()
        
        if not variant:
            continue
            
        item_total = float(variant.price) * item_data.quantity
        total_amount += item_total
        
        # 5% bonus from order
        bonus_earned += int(item_total * 0.05)
        
        # Get product name
        product = db.query(models.MenuProduct).filter(models.MenuProduct.id == item_data.variant_id).first()
        product_name = product.name if product else f"Товар #{item_data.product_id}"
        
        order_item = models.OrderItem(
            order_id=order.id,
            product_id=item_data.product_id,
            variant_id=item_data.variant_id,
            name=product_name,
            quantity=item_data.quantity,
            price=variant.price,
            modifiers=item_data.modifiers,
            total_price=item_total
        )
        db.add(order_item)
    
    # Update order totals
    order.total_amount = total_amount
    order.bonus_earned = bonus_earned
    
    # Update customer bonus points
    if order_data.customer_id:
        customer = db.query(models.Customer).filter(
            models.Customer.id == order_data.customer_id
        ).first()
        if customer:
            customer.bonus_points -= order_data.bonus_used
            customer.bonus_points += bonus_earned
    
    db.commit()
    db.refresh(order)
    
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "total_amount": float(order.total_amount),
        "bonus_earned": bonus_earned,
        "status": order.status
    }

@router.get("/next-number")
async def get_next_order_number(db: Session = Depends(get_db)):
    """Get next order number for frontend"""
    last_order = db.query(models.Order).order_by(models.Order.id.desc()).first()
    next_number = (last_order.id + 1) if last_order else 1
    return {"next_number": str(next_number)}

@router.get("/list")
async def list_orders(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List orders (for CRM)"""
    query = db.query(models.Order)
    
    if status:
        query = query.filter(models.Order.status == status)
    
    orders = query.order_by(models.Order.created_at.desc()).limit(limit).all()
    
    result = []
    for o in orders:
        items_with_category = []
        for i in o.items:
            # Get product category_id from MenuProduct
            product = db.query(models.MenuProduct).filter(
                models.MenuProduct.id == i.variant_id
            ).first()
            
            category_id = None
            if product and product.category_id:
                category = db.query(models.Category).filter(
                    models.Category.id == product.category_id
                ).first()
                if category:
                    category_id = category.category_id or str(category.id)
            
            items_with_category.append({
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "name": i.name or f"Товар #{i.product_id}",
                "quantity": i.quantity,
                "price": float(i.price),
                "total_price": float(i.total_price),
                "category_id": category_id
            })
        
        result.append({
            "id": o.id,
            "order_number": o.order_number,
            "customer_name": o.customer_name,
            "delivery_phone": o.delivery_phone,
            "delivery_address": o.delivery_address,
            "status": o.status,
            "order_type": o.order_type or 'delivery',
            "payment_type": o.payment_type or 'cash',
            "assignee": o.assignee or '',
            "total_amount": float(o.total_amount),
            "created_at": o.created_at.isoformat() + 'Z',
            "scheduled_time": o.scheduled_time.isoformat() + 'Z' if o.scheduled_time else None,
            "items": items_with_category,
            "marks": [m.mark_id for m in o.marks] if o.marks else [],
            "discount": float(o.discount_percent) if hasattr(o, 'discount_percent') and o.discount_percent else 0,
            "promo_discount": float(o.promo_discount) if o.promo_discount else 0,
            "promo_code": o.promo_code or ''
        })
    
    return result

@router.get("/{order_id}")
async def get_order(order_id: int, db: Session = Depends(get_db)):
    """Get order details"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get product names for items
    items_with_names = []
    for item in order.items:
        # Use item.name if available (saved during order creation), otherwise fetch from product
        if item.name:
            full_name = item.name
        else:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            variant = db.query(models.ProductVariant).filter(models.ProductVariant.id == item.variant_id).first()
            
            product_name = product.name_ru if product else f"Товар #{item.product_id}"
            variant_name = variant.name_ru if variant else ""
            
            # Full name: "Пепперони 30см" or just "Пепперони" if no variant name
            full_name = f"{product_name} - {variant_name}" if variant_name and variant_name != "Стандарт" else product_name
        
        items_with_names.append({
            "product_id": item.product_id,
            "variant_id": item.variant_id,
            "name": full_name,
            "quantity": item.quantity,
            "price": float(item.price),
            "total_price": float(item.total_price)
        })
    
    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "delivery_phone": order.delivery_phone,
        "delivery_address": order.delivery_address,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "bonus_used": order.bonus_used,
        "bonus_earned": order.bonus_earned,
        "comment": order.comment,
        "promo_code": order.promo_code,
        "promo_discount": float(order.promo_discount) if order.promo_discount else 0,
        "created_at": order.created_at.isoformat() + 'Z',
        "items": items_with_names
    }

class StatusUpdate(BaseModel):
    status: str

@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: int,
    data: StatusUpdate,
    db: Session = Depends(get_db)
):
    """Update order status"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.status = data.status
    db.commit()
    
    return {"status": "ok", "new_status": data.status}

@router.patch("/{order_id}/payment")
async def update_payment_type(
    order_id: int,
    payment_type: str,
    db: Session = Depends(get_db)
):
    """Update order payment type"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.payment_type = payment_type
    db.commit()
    
    return {"status": "updated", "payment_type": payment_type}

@router.patch("/{order_id}/assignee")
async def update_assignee(
    order_id: int,
    assignee: str,
    db: Session = Depends(get_db)
):
    """Update order assignee (staff member)"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.assignee = assignee
    db.commit()
    
    return {"status": "updated", "assignee": assignee}

@router.patch("/{order_id}")
async def update_order(
    order_id: int,
    order_data: dict,
    db: Session = Depends(get_db)
):
    """Update order details (name, phone, comment, etc.)"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update fields if provided
    if 'customer_name' in order_data:
        order.customer_name = order_data['customer_name']
    if 'customer_phone' in order_data:
        order.delivery_phone = order_data['customer_phone']
    if 'comment' in order_data:
        order.comment = order_data['comment']
    if 'delivery_address' in order_data:
        order.delivery_address = order_data['delivery_address']
    if 'assignee' in order_data:
        order.assignee = order_data['assignee']
    if 'scheduled_time' in order_data:
        if order_data['scheduled_time']:
            try:
                order.scheduled_time = datetime.fromisoformat(order_data['scheduled_time'].replace('Z', '+00:00'))
            except:
                pass
        else:
            order.scheduled_time = None
    
    db.commit()
    
    return {"status": "updated", "order_id": order_id}

@router.patch("/{order_id}/add-items")
async def add_items_to_order(
    order_id: int,
    order_data: FrontendOrderCreate,
    db: Session = Depends(get_db)
):
    """Add items to existing order"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Add new items
    total_amount = float(order.total_amount)
    bonus_earned = order.bonus_earned
    
    for item_data in order_data.items:
        variant = db.query(models.ProductVariant).filter(
            models.ProductVariant.id == item_data.variant_id
        ).first()
        
        if not variant:
            continue
        
        item_total = float(variant.price) * item_data.quantity
        total_amount += item_total
        bonus_earned += int(item_total * 0.05)
        
        # Get product name
        product = db.query(models.MenuProduct).filter(models.MenuProduct.id == item_data.variant_id).first()
        product_name = product.name if product else f"Товар #{item_data.product_id}"
        
        order_item = models.OrderItem(
            order_id=order.id,
            product_id=item_data.product_id,
            variant_id=item_data.variant_id,
            name=product_name,
            quantity=item_data.quantity,
            price=variant.price,
            modifiers=[],
            total_price=item_total
        )
        db.add(order_item)
    
    # Update order totals
    order.total_amount = total_amount
    order.bonus_earned = bonus_earned
    
    db.commit()
    db.refresh(order)
    
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "total_amount": float(order.total_amount),
        "bonus_earned": bonus_earned,
        "status": order.status
    }


@router.post("/{order_id}/send-to-kitchen")
async def send_order_to_kitchen(order_id: int, db: Session = Depends(get_db)):
    """Manually send order notification to Telegram (kitchen)"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Заказ не найден")
    
    # Get order items with product names
    items = []
    for item in order.items:
        product = db.query(models.MenuProduct).filter(models.MenuProduct.id == item.product_id).first()
        items.append({
            "product_name": product.name if product else "Товар",
            "quantity": item.quantity,
            "total_price": float(item.total_price)
        })
    
    # Prepare notification
    order_notification = {
        "id": order.id,
        "order_number": order.order_number,
        "total_amount": float(order.total_amount),
        "customer_name": order.customer_name,
        "delivery_phone": order.delivery_phone,
        "delivery_address": order.delivery_address,
        "payment_type": "cash",  # Default, should be stored in order
        "order_type": order.order_type,
        "items": items
    }
    
    # Send to bot
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://bot:8080/webhook/new-order",
                json=order_notification,
                timeout=5.0
            )
            if response.status_code == 200:
                # Update order status to cooking
                order.status = "cooking"
                db.commit()
                return {"status": "sent", "message": "Заказ отправлен на кухню"}
            else:
                return {"status": "error", "message": "Ошибка отправки"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class OrderMarksUpdate(BaseModel):
    marks: List[str]

@router.post("/{order_id}/marks")
async def update_order_marks(order_id: int, data: OrderMarksUpdate, db: Session = Depends(get_db)):
    """Update order marks"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Delete existing marks
    db.query(models.OrderMark).filter(models.OrderMark.order_id == order_id).delete()
    
    # Add new marks
    for mark_id in data.marks:
        order_mark = models.OrderMark(order_id=order_id, mark_id=mark_id)
        db.add(order_mark)
    
    db.commit()
    return {"status": "updated", "marks": data.marks}

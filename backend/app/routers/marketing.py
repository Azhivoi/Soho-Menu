"""
Marketing module for SOHO Cafe
Promotions, discounts, loyalty points, and referral program
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from zoneinfo import ZoneInfo
from enum import Enum
import os
import uuid
import json
import logging

logger = logging.getLogger(__name__)

from app.database import get_db
from app import models

router = APIRouter(prefix="/marketing", tags=["marketing"])

# ========== UTILS ==========
def transliterate(text):
    """Транслитерация латиницы в кириллицу для промокодов"""
    translit_map = {
        'A': 'А', 'B': 'В', 'C': 'С', 'E': 'Е', 'H': 'Н', 'K': 'К',
        'M': 'М', 'O': 'О', 'P': 'Р', 'T': 'Т', 'X': 'Х', 'Y': 'У',
        'a': 'а', 'b': 'в', 'c': 'с', 'e': 'е', 'h': 'н', 'k': 'к',
        'm': 'м', 'o': 'о', 'p': 'р', 't': 'т', 'x': 'х', 'y': 'у',
    }
    return ''.join(translit_map.get(c, c) for c in text)

# ========== ENUMS ==========
class PromoType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    N_PLUS_GIFT = "n_plus_gift"
    GIFT_WITH_PURCHASE = "gift_with_purchase"
    SAME_PRODUCT_GIFT = "same_product_gift"
    FIXED_PRICE_SECOND = "fixed_price_second"
    FREE_DELIVERY = "free_delivery"
    SUM_GIFT = "sum_gift"
    SUM_DISCOUNT = "sum_discount"
    DISH_DISCOUNT = "dish_discount"
    COMBO_FIXED_PRICE = "combo_fixed_price"
    NTH_DISCOUNT = "nth_discount"
    AMOUNT_GIFT = "amount_gift"
    AMOUNT_GIFT_CHOICE = "amount_gift_choice"

class PromoStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"

# ========== SCHEMAS ==========
class PromoConfig(BaseModel):
    # N+M параметры
    buy_n: Optional[int] = 1
    get_n: Optional[int] = 1
    
    # Подарки
    gift_product_id: Optional[int] = None  # Один подарок (для совместимости)
    gift_product_ids: Optional[List[int]] = None  # Список подарков
    gift_quantity: Optional[int] = 1
    
    # Скидки
    discount_percent: Optional[float] = 100  # % скидки на подарок (100 = бесплатно)
    discount_n: Optional[float] = None
    
    # Фиксированная цена
    fixed_price: Optional[float] = None  # "вторая за 99₽"
    fix_price: Optional[float] = None  # Для обратной совместимости
    
    # Пороги сумм
    sum_threshold: Optional[float] = None
    sum_discount: Optional[float] = None
    
    # Комбо
    combo_quantity: Optional[int] = None
    combo_fixed_price: Optional[float] = None
    
    # N-е со скидкой
    every_n: Optional[int] = None
    
    # Лимиты
    max_gifts: Optional[int] = None
    
    # Флаги
    same_product_gift: Optional[bool] = False
    
    # UI
    badge_text: Optional[str] = None
    badge_color: Optional[str] = None
    
    class Config:
        extra = "allow"

class PromoCreate(BaseModel):
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    type: str = "percentage"
    target: Optional[str] = "all"
    value: float = 0
    config: Optional[PromoConfig] = None
    min_order_amount: Optional[float] = None
    max_discount: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    code: Optional[str] = None
    promo_code: Optional[str] = None  # Alias for code
    auto_apply: bool = True
    status: Optional[str] = "draft"
    category_ids: Optional[List[int]] = None
    product_ids: Optional[List[int]] = None
    excluded_products: Optional[List[int]] = None
    usage_limit: Optional[int] = None
    per_customer_limit: Optional[int] = None
    first_order_only: bool = False
    is_featured: bool = False
    show_on_main: bool = False
    show_in_app: bool = True
    banner_color: Optional[str] = "#e94560"
    banner_mobile: Optional[str] = None
    banner_tablet: Optional[str] = None
    banner_web: Optional[str] = None
    app_enabled: bool = True
    site_enabled: bool = True
    posterix_enabled: bool = False
    pickup_enabled: bool = True
    courier_enabled: bool = True
    inside_enabled: bool = True
    cross_off: bool = True
    discount_addition_off: bool = False
    auth_required: bool = False

class PromoUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    type: Optional[str] = None
    target: Optional[str] = None
    value: Optional[float] = None
    config: Optional[PromoConfig] = None
    min_order_amount: Optional[float] = None
    max_discount: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    code: Optional[str] = None
    promo_code: Optional[str] = None  # Alias for code
    auto_apply: Optional[bool] = None
    status: Optional[str] = None
    category_ids: Optional[List[int]] = None
    product_ids: Optional[List[int]] = None
    excluded_products: Optional[List[int]] = None
    usage_limit: Optional[int] = None
    per_customer_limit: Optional[int] = None
    first_order_only: Optional[bool] = None
    is_featured: Optional[bool] = None
    show_on_main: Optional[bool] = None
    show_in_app: Optional[bool] = None
    banner_color: Optional[str] = None
    banner_mobile: Optional[str] = None
    banner_tablet: Optional[str] = None
    banner_web: Optional[str] = None
    app_enabled: Optional[bool] = None
    site_enabled: Optional[bool] = None
    posterix_enabled: Optional[bool] = None
    pickup_enabled: Optional[bool] = None
    courier_enabled: Optional[bool] = None
    inside_enabled: Optional[bool] = None
    cross_off: Optional[bool] = None
    discount_addition_off: Optional[bool] = None
    auth_required: Optional[bool] = None

class PromoResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    type: str
    target: Optional[str] = "all"
    value: Optional[float] = 0
    config: Optional[Dict[str, Any]] = None
    min_order_amount: Optional[float] = None
    max_discount: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    code: Optional[str] = None
    promo_code: Optional[str] = None  # Alias
    auto_apply: Optional[bool] = True
    status: str
    category_ids: Optional[List[int]] = None
    product_ids: Optional[List[int]] = None
    excluded_products: Optional[List[int]] = None
    usage_count: Optional[int] = 0
    usage_limit: Optional[int] = None
    per_customer_limit: Optional[int] = None
    first_order_only: Optional[bool] = False
    is_featured: Optional[bool] = False
    show_on_main: Optional[bool] = False
    show_in_app: Optional[bool] = True
    banner_color: Optional[str] = "#e94560"
    banner_mobile: Optional[str] = None
    banner_tablet: Optional[str] = None
    banner_web: Optional[str] = None
    image_mobile: Optional[str] = None  # Alias
    image_tablet: Optional[str] = None  # Alias
    image_web: Optional[str] = None  # Alias
    app_enabled: Optional[bool] = True
    site_enabled: Optional[bool] = True
    posterix_enabled: Optional[bool] = False
    pickup_enabled: Optional[bool] = True
    courier_enabled: Optional[bool] = True
    inside_enabled: Optional[bool] = True
    sort_order: Optional[int] = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ========== PROMOTIONS ENDPOINTS ==========

@router.get("/promotions", response_model=List[PromoResponse])
async def get_promotions(
    status: Optional[str] = None,
    show_on_main: Optional[bool] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all promotions with optional filters"""
    query = db.query(models.Promotion)
    
    if status:
        query = query.filter(models.Promotion.status == status)
    if show_on_main is not None:
        query = query.filter(models.Promotion.show_on_main == show_on_main)
    if type:
        query = query.filter(models.Promotion.type == type)
    
    promos = query.order_by(models.Promotion.sort_order.desc(), models.Promotion.created_at.desc()).all()
    
    # Add aliases for frontend compatibility
    for promo in promos:
        promo.image_mobile = promo.banner_mobile
        promo.image_tablet = promo.banner_tablet
        promo.image_web = promo.banner_web
        promo.promo_code = promo.code
    
    return promos

@router.get("/promotions/active/now", response_model=List[PromoResponse])
async def get_active_promotions_now(db: Session = Depends(get_db)):
    """Get promotions active right now (for frontend)"""
    # Use Minsk timezone (UTC+3)
    now = datetime.now(ZoneInfo('Europe/Minsk'))
    current_weekday = now.weekday() + 1  # 1-7 (Пн-Вс)
    current_time = now.strftime("%H:%M")
    
    promos = db.query(models.Promotion).filter(
        models.Promotion.status == PromoStatus.ACTIVE,
        models.Promotion.site_enabled == True
    ).order_by(models.Promotion.sort_order.desc()).all()
    
    # Filter by time conditions
    active_promos = []
    for promo in promos:
        # Check date
        if promo.start_date and promo.start_date > now.date():
            continue
        if promo.end_date and promo.end_date < now.date():
            continue
        
        # Check time
        if promo.start_time and promo.end_time:
            if not (promo.start_time <= current_time <= promo.end_time):
                continue
        
        # Check days of week
        if promo.days_of_week:
            if isinstance(promo.days_of_week, str):
                try:
                    days = json.loads(promo.days_of_week)
                except:
                    days = []
            else:
                days = promo.days_of_week
            if current_weekday not in days:
                continue
        
        # Add aliases
        promo.image_mobile = promo.banner_mobile
        promo.image_tablet = promo.banner_tablet
        promo.image_web = promo.banner_web
        promo.promo_code = promo.code
        
        active_promos.append(promo)
    
    return active_promos

@router.get("/promotions/featured/main", response_model=List[PromoResponse])
async def get_featured_promotions(db: Session = Depends(get_db)):
    """Get featured promotions for main page"""
    promos = db.query(models.Promotion).filter(
        models.Promotion.status == PromoStatus.ACTIVE,
        models.Promotion.show_on_main == True
    ).order_by(models.Promotion.sort_order.desc()).limit(5).all()
    
    # Add aliases
    for promo in promos:
        promo.image_mobile = promo.banner_mobile
        promo.image_tablet = promo.banner_tablet
        promo.image_web = promo.banner_web
        promo.promo_code = promo.code
    
    return promos

@router.put("/promotions/sort-order")
async def update_promotions_sort_order(
    sort_data: List[Dict[str, Any]],  # [{"id": 1, "sort_order": 10}, ...]
    db: Session = Depends(get_db)
):
    """Update sort order for multiple promotions (drag & drop)"""
    updated = 0
    for item in sort_data:
        try:
            promo_id = int(item.get("id")) if item.get("id") is not None else None
            sort_order = int(item.get("sort_order")) if item.get("sort_order") is not None else None
            if promo_id is not None and sort_order is not None:
                db_promo = db.query(models.Promotion).filter(models.Promotion.id == promo_id).first()
                if db_promo:
                    db_promo.sort_order = sort_order
                    updated += 1
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid sort data item: {item}, error: {e}")
            continue
    
    db.commit()
    return {"status": "updated", "count": updated}

@router.get("/promotions/{promo_id}", response_model=PromoResponse)
async def get_promotion(promo_id: int, db: Session = Depends(get_db)):
    """Get promotion by ID"""
    promo = db.query(models.Promotion).filter(models.Promotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    # Add aliases
    promo.image_mobile = promo.banner_mobile
    promo.image_tablet = promo.banner_tablet
    promo.image_web = promo.banner_web
    promo.promo_code = promo.code
    
    return promo

@router.post("/promotions", response_model=PromoResponse)
async def create_promotion(promo: PromoCreate, db: Session = Depends(get_db)):
    """Create new promotion"""
    # Проверяем уникальность кода
    code_value = promo.code or promo.promo_code
    if code_value:
        existing = db.query(models.Promotion).filter(
            models.Promotion.code.ilike(code_value)
        ).first()
        if existing:
            raise HTTPException(
                status_code=400, 
                detail=f"Промокод '{code_value}' уже используется в акции '{existing.name}' (ID: {existing.id})"
            )
    
    # Конвертируем config в dict
    promo_data = promo.dict(exclude_unset=True)
    if promo_data.get('config'):
        promo_data['config'] = promo_data['config'].dict() if hasattr(promo_data['config'], 'dict') else promo_data['config']
    
    # Синхронизируем code и promo_code (в модели только code)
    if promo_data.get('promo_code') and not promo_data.get('code'):
        promo_data['code'] = promo_data['promo_code']
    
    # Удаляем promo_code — его нет в модели
    promo_data.pop('promo_code', None)
    
    db_promo = models.Promotion(**promo_data)
    db.add(db_promo)
    db.commit()
    db.refresh(db_promo)
    return db_promo

@router.put("/promotions/{promo_id}", response_model=PromoResponse)
async def update_promotion(promo_id: int, promo_update: PromoUpdate, db: Session = Depends(get_db)):
    """Update promotion"""
    db_promo = db.query(models.Promotion).filter(models.Promotion.id == promo_id).first()
    if not db_promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    update_data = promo_update.dict(exclude_unset=True)
    
    # Проверяем уникальность кода при изменении
    if 'code' in update_data and update_data['code']:
        existing = db.query(models.Promotion).filter(
            models.Promotion.code.ilike(update_data['code']),
            models.Promotion.id != promo_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=400, 
                detail=f"Промокод '{update_data['code']}' уже используется в акции '{existing.name}' (ID: {existing.id})"
            )
    
    # Конвертируем config в dict если нужно
    if 'config' in update_data and update_data['config']:
        update_data['config'] = update_data['config'].dict() if hasattr(update_data['config'], 'dict') else update_data['config']
    
    # Синхронизируем code и promo_code (в модели только code)
    if 'promo_code' in update_data:
        update_data['code'] = update_data['promo_code']
    
    # Удаляем promo_code — его нет в модели
    update_data.pop('promo_code', None)
    
    for field, value in update_data.items():
        setattr(db_promo, field, value)
    
    db.commit()
    db.refresh(db_promo)
    return db_promo

@router.delete("/promotions/{promo_id}")
async def delete_promotion(promo_id: int, db: Session = Depends(get_db)):
    """Delete promotion (hard delete from database)"""
    db_promo = db.query(models.Promotion).filter(models.Promotion.id == promo_id).first()
    if not db_promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    # Hard delete
    db.delete(db_promo)
    db.commit()
    return {"status": "deleted", "id": promo_id}

@router.put("/promotions/{promo_id}/status")
async def update_promotion_status(
    promo_id: int,
    status_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Update promotion status"""
    db_promo = db.query(models.Promotion).filter(models.Promotion.id == promo_id).first()
    if not db_promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    new_status = status_data.get("status")
    if new_status and new_status in ["draft", "active", "paused", "expired"]:
        db_promo.status = new_status
    
    # Обновление sort_order если передан
    if "sort_order" in status_data:
        db_promo.sort_order = status_data["sort_order"]
    
    db.commit()
    return {"status": "updated", "new_status": db_promo.status, "sort_order": db_promo.sort_order}

@router.put("/promotions/{promo_id}/visibility")
async def update_promotion_visibility(
    promo_id: int,
    visibility: Dict[str, bool],
    db: Session = Depends(get_db)
):
    """Toggle promotion visibility"""
    db_promo = db.query(models.Promotion).filter(models.Promotion.id == promo_id).first()
    if not db_promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    if "show_on_main" in visibility:
        db_promo.show_on_main = visibility["show_on_main"]
    if "show_in_app" in visibility:
        db_promo.show_in_app = visibility["show_in_app"]
    
    db.commit()
    return {
        "status": "updated",
        "show_on_main": db_promo.show_on_main,
        "show_in_app": db_promo.show_in_app
    }

# ========== IMAGE UPLOAD ==========

UPLOAD_DIR = "/opt/soho/uploads/promotions"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/promotions/{promo_id}/images")
async def upload_promotion_image(
    promo_id: int,
    type: str = Form(...),  # 'mobile', 'tablet', 'web'
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload promotion banner image"""
    promo = db.query(models.Promotion).filter(models.Promotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    if type not in ["mobile", "tablet", "web"]:
        raise HTTPException(status_code=400, detail="Invalid image type")
    
    # Generate unique filename
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    # Save file
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Update promo
    image_url = f"/uploads/promotions/{filename}"
    if type == "mobile":
        promo.banner_mobile = image_url
    elif type == "tablet":
        promo.banner_tablet = image_url
    else:
        promo.banner_web = image_url
    
    db.commit()
    return {"status": "uploaded", "url": image_url, "type": type}

# ========== PROMO CODE VALIDATION ==========

class PromoCodeItem(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    name: Optional[str] = None
    price: float
    quantity: int = 1
    category_id: Optional[int] = None

class PromoCodeValidation(BaseModel):
    code: str
    order_amount: Optional[float] = None
    customer_id: Optional[int] = None
    items: List[PromoCodeItem]
    source: str = "site"
    delivery_type: str = "delivery"
    zone_id: Optional[int] = None

class PromoCodeResponse(BaseModel):
    valid: bool
    discount_amount: float = 0
    discount_percent: float = 0
    promotion_id: Optional[int] = None
    promotion_name: Optional[str] = None
    message: Optional[str] = None
    applied_items: Optional[List[Dict]] = None

@router.post("/validate-promo-code", response_model=PromoCodeResponse)
async def validate_promo_code(data: PromoCodeValidation, db: Session = Depends(get_db)):
    """Validate promo code and calculate discount using PromotionService"""
    
    from app.routers.promotions_v2 import PromotionService, CalculateOrderRequest, CalculateOrderItem
    
    service = PromotionService(db)
    
    # Находим промо по коду (ищем как есть + транслитерированный)
    search_codes = [data.code.lower()]
    translit_code = transliterate(data.code).lower()
    if translit_code != data.code.lower():
        search_codes.append(translit_code)
    
    promo = None
    for code in search_codes:
        promo = db.query(models.Promotion).filter(
            func.lower(models.Promotion.code) == code
        ).first()
        if promo:
            break
    
    if not promo:
        return PromoCodeResponse(
            valid=False,
            message="Промокод не найден"
        )
    
    if promo.status != "active":
        return PromoCodeResponse(
            valid=False,
            message="Акция не активна"
        )
    
    # Формируем items для расчета
    items = []
    for item in data.items:
        items.append(CalculateOrderItem(
            product_id=item.product_id,
            variant_id=item.variant_id,
            name=item.name or "",
            price=item.price,
            quantity=item.quantity,
            category_id=item.category_id
        ))
    
    if not items:
        return PromoCodeResponse(
            valid=False,
            message="Нет товаров для применения акции"
        )
    
    # Создаем запрос
    request = CalculateOrderRequest(
        items=items,
        promo_code=data.code,
        source=data.source,
        delivery_type=data.delivery_type,
        zone_id=data.zone_id
    )
    
    # Проверяем может ли примениться
    can_apply, reason = service.can_apply_promo(promo, request)
    
    if not can_apply:
        return PromoCodeResponse(
            valid=False,
            message=f"Условия не выполнены: {reason}"
        )
    
    # Рассчитываем скидку
    subtotal = sum(item.price * item.quantity for item in items)
    print(f"DEBUG MARKETING: subtotal={subtotal}, items={[(i.product_id, i.quantity) for i in items]}", flush=True)
    discount, applied_items = service.calculate_discount(promo, items, subtotal, request)
    print(f"DEBUG MARKETING: discount={discount}, applied_items={applied_items}", flush=True)
    
    # Определяем процент скидки
    discount_percent = 0
    if subtotal > 0:
        discount_percent = (discount / subtotal) * 100
    
    return PromoCodeResponse(
        valid=True,
        discount_amount=round(discount, 2),
        discount_percent=round(discount_percent, 2),
        promotion_id=promo.id,
        promotion_name=promo.name,
        message=f"Промокод применен! Скидка: {discount} BYN",
        applied_items=applied_items
    )

# ========== ANALYTICS ==========

@router.get("/analytics/promotions/{promo_id}")
async def get_promotion_analytics(promo_id: int, db: Session = Depends(get_db)):
    """Get analytics for a specific promotion"""
    promo = db.query(models.Promotion).filter(models.Promotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    # Count orders with this promotion
    orders_count = db.query(models.Order).filter(
        models.Order.promo_promotion_id == promo_id
    ).count()
    
    total_discount = db.query(func.sum(models.Order.promo_discount)).filter(
        models.Order.promo_promotion_id == promo_id
    ).scalar() or 0
    
    total_revenue = db.query(func.sum(models.Order.total_amount)).filter(
        models.Order.promo_promotion_id == promo_id
    ).scalar() or 0
    
    return {
        "promotion_id": promo_id,
        "promotion_name": promo.name,
        "orders_count": orders_count,
        "total_discount": float(total_discount),
        "total_revenue": float(total_revenue),
        "usage_rate": (orders_count / promo.usage_limit * 100) if promo.usage_limit else None
    }
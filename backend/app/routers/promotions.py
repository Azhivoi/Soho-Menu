"""
Promotion calculation service (FoodPicasso style)
"""
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException

from .. import models
from ..database import get_db

router = APIRouter()


class CalculateOrderItem(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    name: str
    price: float
    quantity: int = 1
    category_id: Optional[int] = None


class CalculateOrderRequest(BaseModel):
    items: List[CalculateOrderItem]
    promo_code: Optional[str] = None
    zone_id: Optional[int] = None
    restaurant_id: Optional[int] = None
    order_type: str = "delivery"
    source: str = "site"
    user_id: Optional[int] = None
    is_authenticated: bool = False
    is_third_party_delivery: bool = False


class AppliedPromoDetail(BaseModel):
    promotion_id: int
    name: str
    type: str
    discount: float
    applied_items: List[Dict[str, Any]]


class CalculateOrderResponse(BaseModel):
    subtotal: float
    discount: float
    total: float
    applied_promos: List[AppliedPromoDetail]
    item_breakdown: List[Dict[str, Any]]


class PromotionService:
    def __init__(self, db: Session):
        self.db = db

    def check_period(self, promo, current_dt: datetime) -> bool:
        """Проверка периода действия акции"""
        current_date = current_dt.date()
        current_time = current_dt.strftime("%H:%M")
        current_weekday = current_dt.weekday()

        if promo.start_date and current_date < promo.start_date:
            return False
        if promo.end_date and current_date > promo.end_date:
            return False

        if promo.start_time and promo.end_time:
            if not (promo.start_time <= current_time <= promo.end_time):
                return False

        # Конвертируем weekday (0-6) в формат БД (1-7)
        if promo.days_of_week:
            db_weekday = current_weekday + 1
            if db_weekday not in promo.days_of_week:
                return False

        return True

    def check_promo_code(self, promo, code: Optional[str]) -> bool:
        """Проверка промокода"""
        if not promo.code:
            return True
        if not code:
            return False
        return promo.code.upper() == code.upper()

    def check_channel(self, promo, source: str) -> bool:
        """Проверка канала (app/site/posterix)"""
        app_only = getattr(promo, 'app_only', False)
        site_only = getattr(promo, 'site_only', False)
        posterix_only = getattr(promo, 'posterix_only', False)
        if not any([app_only, site_only, posterix_only]):
            return True
        if app_only and source == "app":
            return True
        if site_only and source == "site":
            return True
        if posterix_only and source == "posterix":
            return True
        return False

    def check_delivery_type(self, promo, order_type: str) -> bool:
        """Проверка типа доставки"""
        pickup_only = getattr(promo, 'pickup_only', False)
        courier_only = getattr(promo, 'courier_only', False)
        inside_only = getattr(promo, 'inside_only', False)
        restrictions = [pickup_only, courier_only, inside_only]
        if not any(restrictions):
            return True
        if pickup_only and order_type == "pickup":
            return True
        if courier_only and order_type == "delivery":
            return True
        if inside_only and order_type == "inside":
            return True
        return False

    def check_geo(self, promo, zone_id: Optional[int], restaurant_id: Optional[int]) -> bool:
        """Проверка географических ограничений"""
        delivery_zones = getattr(promo, 'delivery_zones', None)
        restaurants = getattr(promo, 'restaurants', None)
        if delivery_zones:
            if zone_id is None or zone_id not in delivery_zones:
                return False
        if restaurants:
            if restaurant_id is None or restaurant_id not in restaurants:
                return False
        return True

    def check_user_limits(self, promo, user_id: Optional[int]) -> Tuple[bool, str]:
        """Проверка лимитов пользователя"""
        usage_limit = getattr(promo, 'usage_limit', None)
        usage_count = getattr(promo, 'usage_count', 0)
        auth_required = getattr(promo, 'auth_required', False)
        per_customer_limit = getattr(promo, 'per_customer_limit', None)

        if usage_limit is not None and usage_count >= usage_limit:
            return False, "global_limit_exceeded"
        if auth_required and not user_id:
            return False, "auth_required"
        if per_customer_limit and user_id:
            customer_usage = self.db.query(models.PromotionUsage).filter(
                models.PromotionUsage.promotion_id == promo.id,
                models.PromotionUsage.user_id == user_id
            ).count()
            if customer_usage >= per_customer_limit:
                return False, "customer_limit_exceeded"
        return True, ""

    def can_apply_promo(self, promo, data: CalculateOrderRequest,
                       subtotal: float, current_dt: Optional[datetime] = None) -> Tuple[bool, str]:
        """Проверка может ли акция быть применена"""
        if current_dt is None:
            current_dt = datetime.now()

        if promo.status != "active":
            return False, "inactive"
        if not self.check_period(promo, current_dt):
            return False, "period"
        if promo.min_order_amount and subtotal < float(promo.min_order_amount):
            return False, "min_amount"
        if not self.check_promo_code(promo, data.promo_code):
            return False, "promo_code"
        if not self.check_channel(promo, data.source):
            return False, "channel"
        if not self.check_delivery_type(promo, data.order_type):
            return False, "delivery_type"
        if not self.check_geo(promo, data.zone_id, data.restaurant_id):
            return False, "geo"

        can_apply, reason = self.check_user_limits(promo, data.user_id)
        if not can_apply:
            return False, reason

        return True, ""

    def calculate_discount(self, promo, items: List[CalculateOrderItem],
                          subtotal: float) -> Tuple[float, List[Dict]]:
        """Расчет скидки для акции"""
        discount = 0.0
        applied_items = []

        promo_product_ids = promo.product_ids or []
        if promo_product_ids:
            applicable_items = [item for item in items if item.product_id in promo_product_ids]
        else:
            applicable_items = items

        if not applicable_items:
            return 0, []

        base_amount = sum(item.price * item.quantity for item in applicable_items)

        # Разворачиваем товары по количеству
        expanded = []
        for item in applicable_items:
            for i in range(item.quantity):
                expanded.append({
                    'product_id': item.product_id,
                    'name': item.name,
                    'price': float(item.price),
                    'category_id': item.category_id
                })

        if promo.type == "percentage":
            # Процентная скидка
            discount = base_amount * (float(promo.value) / 100)
            for item in applicable_items:
                item_discount = (item.price * item.quantity) * (float(promo.value) / 100)
                if item_discount > 0:
                    applied_items.append({
                        'product_id': item.product_id,
                        'name': item.name,
                        'discount': round(item_discount, 2),
                        'type': 'percentage',
                        'value': float(promo.value)
                    })

        elif promo.type == "fixed_amount":
            # Фиксированная сумма
            discount = min(float(promo.value), base_amount)
            if base_amount > 0:
                for item in applicable_items:
                    ratio = (item.price * item.quantity) / base_amount
                    item_discount = discount * ratio
                    applied_items.append({
                        'product_id': item.product_id,
                        'name': item.name,
                        'discount': round(item_discount, 2),
                        'type': 'fixed_amount'
                    })

        elif promo.type in ["n_plus_gift", "sum_gift"]:
            # N+1 акция
            config = promo.config or {}
            buy_n = config.get('buy_n', 2)
            get_n = config.get('get_n', 1)
            discount_percent = float(promo.value) if promo.value else 100

            # Сортируем по цене (дорогие первыми)
            expanded.sort(key=lambda x: x['price'], reverse=True)

            total_items = len(expanded)
            gift_discounts = []

            i = 0
            while i < total_items:
                paid_end = min(i + buy_n, total_items)
                gift_start = paid_end
                gift_end = min(gift_start + get_n, total_items)

                for j in range(gift_start, gift_end):
                    item = expanded[j]
                    item_discount = item['price'] * (discount_percent / 100)
                    gift_discounts.append({
                        'product_id': item['product_id'],
                        'name': item['name'],
                        'discount': round(item_discount, 2),
                        'type': 'n_plus_gift',
                        'price': item['price']
                    })
                    discount += item_discount

                i = gift_end

            applied_items = gift_discounts

        # Проверка максимальной скидки
        if promo.max_discount and discount > float(promo.max_discount):
            ratio = float(promo.max_discount) / discount
            discount = float(promo.max_discount)
            for item in applied_items:
                item['discount'] = round(item['discount'] * ratio, 2)

        return round(discount, 2), applied_items

    def apply_promotions(self, data: CalculateOrderRequest) -> CalculateOrderResponse:
        """Применение всех активных акций"""
        subtotal = sum(item.price * item.quantity for item in data.items)

        promos = self.db.query(models.Promotion).filter(
            models.Promotion.status == "active"
        ).all()

        applied_promos = []
        total_discount = 0.0
        item_discounts_map = {}
        has_non_crossable = False

        for promo in promos:
            can_apply, reason = self.can_apply_promo(promo, data, subtotal)
            if not can_apply:
                continue

            # Проверка на совместимость
            cross_off = getattr(promo, 'cross_off', True)
            discount_addition_off = getattr(promo, 'discount_addition_off', False)

            if has_non_crossable and not cross_off:
                continue
            if not cross_off and len(applied_promos) > 0:
                continue

            # Сброс других акций если нужно
            if discount_addition_off and applied_promos:
                applied_promos.clear()
                total_discount = 0
                item_discounts_map.clear()
                has_non_crossable = False

            discount, items_detail = self.calculate_discount(promo, data.items, subtotal)

            if discount > 0 or items_detail:
                # Проверка не превышает ли скидка сумму заказа
                if total_discount + discount > subtotal:
                    discount = subtotal - total_discount
                    if items_detail and discount > 0:
                        diff = sum(item['discount'] for item in items_detail) - discount
                        if diff > 0 and items_detail:
                            items_detail[-1]['discount'] -= diff

                if discount > 0 or items_detail:
                    applied_promo = AppliedPromoDetail(
                        promotion_id=promo.id,
                        name=promo.name,
                        type=promo.type,
                        discount=round(discount, 2),
                        applied_items=items_detail
                    )
                    applied_promos.append(applied_promo)
                    total_discount += discount

                    for item in items_detail:
                        pid = item['product_id']
                        if pid not in item_discounts_map:
                            item_discounts_map[pid] = []
                        item_discounts_map[pid].append(item)

                if not cross_off:
                    has_non_crossable = True

        # Формируем детализацию по товарам
        item_breakdown = []
        for item in data.items:
            pid = item.product_id
            item_total = item.price * item.quantity
            item_discounts = item_discounts_map.get(pid, [])
            item_discount_sum = sum(d['discount'] for d in item_discounts)

            item_breakdown.append({
                'product_id': pid,
                'name': item.name,
                'quantity': item.quantity,
                'unit_price': item.price,
                'original_total': item_total,
                'discount': round(item_discount_sum, 2),
                'final_total': round(item_total - item_discount_sum, 2),
                'discounts': item_discounts
            })

        return CalculateOrderResponse(
            subtotal=round(subtotal, 2),
            discount=round(total_discount, 2),
            total=round(subtotal - total_discount, 2),
            applied_promos=applied_promos,
            item_breakdown=item_breakdown
        )


@router.post("/calculate", response_model=CalculateOrderResponse)
async def calculate_order(data: CalculateOrderRequest, db: Session = Depends(get_db)):
    """Calculate order total with promotions (FoodPicasso style)"""
    service = PromotionService(db)
    return service.apply_promotions(data)

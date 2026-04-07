"""
Promotion calculation service - ИСПРАВЛЕННАЯ версия
"""
import json
import logging
from datetime import datetime, time
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException
from collections import defaultdict

from app.database import get_db
from app import models

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["promotions"])


class CalculateOrderItem(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    name: str = ""
    price: float
    quantity: int = Field(default=1, gt=0)
    category_id: Optional[int] = None
    weight: Optional[float] = None


class CalculateOrderRequest(BaseModel):
    items: List[CalculateOrderItem]
    delivery_cost: Optional[float] = 0
    promo_code: Optional[str] = None
    source: str = "site"
    delivery_type: str = "delivery"
    zone_id: Optional[int] = None
    restaurant_id: Optional[int] = None
    user_id: Optional[int] = None
    is_authenticated: bool = False


class AppliedPromoItem(BaseModel):
    product_id: Optional[int] = None
    name: Optional[str] = None
    discount: float = 0
    final_price: Optional[float] = None
    type: str = "percentage"
    original_price: Optional[float] = None
    fixed_price: Optional[float] = None


class AppliedPromoDetail(BaseModel):
    promotion_id: int
    name: str
    type: str
    discount: float
    description: Optional[str] = None
    applied_items: List[AppliedPromoItem] = []


class CalculateOrderResponse(BaseModel):
    subtotal: float
    discount: float
    delivery_discount: float = 0
    total: float
    applied_promos: List[AppliedPromoDetail] = []
    free_delivery: bool = False


class PromotionService:
    def __init__(self, db: Session):
        self.db = db
        from app import models
        self.models = models
    
    def check_date_conditions(self, promo, current_dt: datetime = None) -> bool:
        """Проверка временных условий акции"""
        if current_dt is None:
            current_dt = datetime.now()
        
        current_date = current_dt.date()
        current_time = current_dt.time()
        current_weekday = current_dt.weekday() + 1  # 1-7 (Пн-Вс)
        
        # Проверка дат
        start_date = getattr(promo, 'start_date', None)
        end_date = getattr(promo, 'end_date', None)
        
        if start_date and isinstance(start_date, datetime):
            start_date = start_date.date()
        if end_date and isinstance(end_date, datetime):
            end_date = end_date.date()
        
        if start_date and current_date < start_date:
            return False
        if end_date and current_date > end_date:
            return False
        
        # Проверка времени
        start_time = getattr(promo, 'start_time', None)
        end_time = getattr(promo, 'end_time', None)
        
        if start_time and end_time:
            if isinstance(start_time, str):
                start_time = datetime.strptime(start_time, "%H:%M").time()
            if isinstance(end_time, str):
                end_time = datetime.strptime(end_time, "%H:%M").time()
            
            if not (start_time <= current_time <= end_time):
                return False
        
        # Проверка дней недели
        days_of_week = getattr(promo, 'days_of_week', None)
        if days_of_week:
            if isinstance(days_of_week, str):
                try:
                    days_of_week = json.loads(days_of_week)
                except:
                    pass
            if isinstance(days_of_week, list) and current_weekday not in days_of_week:
                return False
        
        return True
    
    def check_channel(self, promo, source: str) -> bool:
        """Проверка канала"""
        app_enabled = getattr(promo, 'app_enabled', True)
        site_enabled = getattr(promo, 'site_enabled', True)
        posterix_enabled = getattr(promo, 'posterix_enabled', False)
        
        if source == "app" and not app_enabled:
            return False
        if source == "site" and not site_enabled:
            return False
        if source == "posterix" and not posterix_enabled:
            return False
        
        return True
    
    def check_delivery_type(self, promo, delivery_type: str) -> bool:
        """Проверка типа доставки"""
        pickup_enabled = getattr(promo, 'pickup_enabled', True)
        courier_enabled = getattr(promo, 'courier_enabled', True)
        inside_enabled = getattr(promo, 'inside_enabled', True)
        
        if delivery_type == "pickup" and not pickup_enabled:
            return False
        if delivery_type == "delivery" and not courier_enabled:
            return False
        if delivery_type == "inside" and not inside_enabled:
            return False
        
        return True
    
    def check_geo(self, promo, zone_id: Optional[int], restaurant_id: Optional[int]) -> bool:
        """Проверка географических ограничений"""
        zones = getattr(promo, 'delivery_zones', None) or []
        restaurants = getattr(promo, 'restaurants', None) or []
        
        if not zones and not restaurants:
            return True
        
        if zones and zone_id and zone_id in zones:
            return True
        if restaurants and restaurant_id and restaurant_id in restaurants:
            return True
        
        return False
    
    def check_products(self, promo, items: List[CalculateOrderItem]) -> bool:
        """Проверка применимости к товарам"""
        product_ids = getattr(promo, 'product_ids', None) or []
        category_ids = getattr(promo, 'category_ids', None) or []
        excluded_products = getattr(promo, 'excluded_products', None) or []
        
        # Если нет привязки к товарам/категориям - применяется ко всему
        if not product_ids and not category_ids:
            # Но проверяем исключения
            for item in items:
                if item.product_id not in excluded_products:
                    return True
            return False
        
        # Проверяем наличие подходящих товаров
        for item in items:
            if item.product_id in excluded_products:
                continue
            if product_ids and item.product_id in product_ids:
                return True
            if category_ids and item.category_id in category_ids:
                return True
        
        return False
    
    def _filter_items_by_promo(self, promo, items: List[CalculateOrderItem]) -> List[CalculateOrderItem]:
        """Фильтрация товаров по условиям акции"""
        product_ids = getattr(promo, 'product_ids', None) or []
        category_ids = getattr(promo, 'category_ids', None) or []
        excluded_products = getattr(promo, 'excluded_products', None) or []
        
        # Поддержка buy_items и buy_category_id из config
        config = getattr(promo, 'config', None) or {}
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except:
                config = {}
        
        if config.get('buy_items'):
            for item in config['buy_items']:
                if item.get('product_id') and item['product_id'] not in product_ids:
                    product_ids.append(item['product_id'])
        
        if config.get('buy_category_id'):
            cat_id = int(config['buy_category_id']) if isinstance(config['buy_category_id'], str) else config['buy_category_id']
            if cat_id not in category_ids:
                category_ids.append(cat_id)
        
        # Исключаем исключённые товары
        items = [item for item in items if item.product_id not in excluded_products]
        
        if not product_ids and not category_ids:
            return items
        
        result = []
        for item in items:
            if product_ids and item.product_id in product_ids:
                result.append(item)
            elif category_ids and item.category_id in category_ids:
                result.append(item)
        
        return result
    
    def can_apply_promo(self, promo, data: CalculateOrderRequest) -> Tuple[bool, str]:
        """Полная проверка может ли акция быть применена"""
        status = getattr(promo, 'status', 'draft')
        if status != "active":
            return False, "inactive"
        
        if not self.check_date_conditions(promo):
            return False, "period"
        
        subtotal = sum(item.price * item.quantity for item in data.items)
        min_order_amount = getattr(promo, 'min_order_amount', 0) or 0
        if min_order_amount > 0 and subtotal < min_order_amount:
            return False, "min_amount"
        
        promo_code = getattr(promo, 'code', None) or getattr(promo, 'promo_code', None)
        if promo_code:
            if not data.promo_code:
                return False, "promo_code_required"
            if promo_code.upper() != data.promo_code.upper():
                return False, "wrong_promo_code"
        
        if not self.check_channel(promo, data.source):
            return False, "channel"
        
        if not self.check_delivery_type(promo, data.delivery_type):
            return False, "delivery_type"
        
        if not self.check_geo(promo, data.zone_id, data.restaurant_id):
            return False, "geo"
        
        if not self.check_products(promo, data.items):
            return False, "products"
        
        return True, ""
    
    def calculate_discount(self, promo, items: List[CalculateOrderItem], 
                          subtotal: float, data: CalculateOrderRequest) -> Tuple[float, List[Dict]]:
        """Расчет скидки для акции - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        logger.warning(f"=== calculate_discount START ===")
        logger.warning(f"Promo: {getattr(promo, 'name', 'Unknown')} (ID: {getattr(promo, 'id', 'N/A')})")
        logger.warning(f"Promo type: {getattr(promo, 'type', 'Unknown')}")
        logger.warning(f"Items: {[(i.product_id, i.variant_id, i.quantity) for i in items]}")
        
        discount = 0.0
        applied_items = []
        
        eligible_items = self._filter_items_by_promo(promo, items)
        logger.warning(f"Eligible items: {len(eligible_items)} - {[(i.product_id, i.variant_id) for i in eligible_items]}")
        
        if not eligible_items:
            return 0, []
        
        eligible_subtotal = sum(item.price * item.quantity for item in eligible_items)
        promo_type = getattr(promo, 'type', 'percentage')
        value = float(getattr(promo, 'value', 0) or 0)
        max_discount = float(getattr(promo, 'max_discount', None) or float('inf'))
        
        # Получаем config как dict
        config = getattr(promo, 'config', None) or {}
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except:
                config = {}
        
        # ========== ОБЫЧНЫЕ СКИДКИ ==========
        if promo_type in ["percentage", "PERCENTAGE"]:
            discount = eligible_subtotal * (value / 100)
            discount = min(discount, max_discount)
            
            for item in eligible_items:
                item_discount = item.price * item.quantity * (value / 100)
                if max_discount < float('inf'):
                    ratio = (item.price * item.quantity) / eligible_subtotal
                    item_discount = min(item_discount, max_discount * ratio)
                
                applied_items.append({
                    'product_id': item.product_id,
                    'name': item.name,
                    'discount': round(item_discount, 2),
                    'type': 'percentage',
                    'original_price': item.price * item.quantity
                })
        
        elif promo_type in ["fixed", "fixed_amount", "FIXED_AMOUNT"]:
            discount = min(value, eligible_subtotal)
            
            for item in eligible_items:
                ratio = (item.price * item.quantity) / eligible_subtotal
                item_discount = discount * ratio
                applied_items.append({
                    'product_id': item.product_id,
                    'name': item.name,
                    'discount': round(item_discount, 2),
                    'type': 'fixed',
                    'original_price': item.price * item.quantity
                })
        
        elif promo_type in ["free_delivery", "FREE_DELIVERY"]:
            applied_items = [{'type': 'free_delivery'}]
        
        # ========== АКЦИИ 1+1 И ПОДАРКИ ==========
        elif promo_type in ["gift", "GIFT", "n_plus_gift", "N_PLUS_GIFT", 
                           "gift_with_purchase", "GIFT_WITH_PURCHASE",
                           "same_product_gift", "SAME_PRODUCT_GIFT",
                           "fixed_price_second", "FIXED_PRICE_SECOND"]:
            
            buy_n = config.get('buy_n', 1)
            get_n = config.get('get_n', 1)
            discount_percent = config.get('discount_percent', 100)
            
            # Получаем ID подарков
            gift_product_ids = config.get('gift_product_ids', [])
            if not gift_product_ids:
                single_gift = config.get('gift_product_id')
                if single_gift:
                    gift_product_ids = [single_gift]
            
            # Поддержка gift_items из админки
            if not gift_product_ids and config.get('gift_items'):
                for item in config['gift_items']:
                    if item.get('product_id'):
                        gift_product_ids.append(item['product_id'])
                    if item.get('variant_ids'):
                        gift_product_ids.extend(item['variant_ids'])
            
            # Проверяем buy_items — если совпадает с gift_items, это same_product_gift
            buy_items_from_config = []
            if config.get('buy_items'):
                for item in config['buy_items']:
                    if item.get('product_id'):
                        buy_items_from_config.append(item['product_id'])
            
            # Если buy_items и gift_items совпадают — это 1+1 на тот же товар
            same_product_gift = config.get('same_product_gift', False)
            if not same_product_gift and buy_items_from_config and gift_product_ids:
                if set(buy_items_from_config) == set(gift_product_ids):
                    same_product_gift = True
                    gift_product_ids = []  # Сбрасываем чтобы не попасть в gift_with_purchase
            fixed_price = config.get('fixed_price', None) or config.get('fix_price', None)
            max_gifts_limit = config.get('max_gifts', None)
            
            # ===== ВАРИАНТ 1: Второй за фиксированную цену =====
            if fixed_price is not None:
                discount, applied_items = self._calculate_fixed_price_second(
                    eligible_items, buy_n, get_n, fixed_price, same_product_gift
                )
            
            # ===== ВАРИАНТ 2: Такой же товар (1+1, 2+1 на тот же товар) =====
            elif same_product_gift:
                # Для same_product_gift: buy_items = триггеры, gift_items = акционные
                # Но gift_product_ids был сброшен выше, восстанавливаем из config
                gift_product_ids_for_same = []
                if config.get('gift_items'):
                    for item in config['gift_items']:
                        if item.get('product_id'):
                            gift_product_ids_for_same.append(item['product_id'])
                        if item.get('variant_ids'):
                            gift_product_ids_for_same.extend(item['variant_ids'])
                
                discount, applied_items = self._calculate_same_product_gift_v2(
                    eligible_items, buy_n, get_n, discount_percent,
                    buy_product_ids=buy_items_from_config if buy_items_from_config else None,
                    gift_product_ids=gift_product_ids_for_same if gift_product_ids_for_same else None
                )
                print(f"DEBUG calculate_discount: same_product_gift returned discount={discount}, items={len(applied_items)}", flush=True)
            
            # ===== ВАРИАНТ 3: Конкретный подарок (купи X, получи Y) =====
            elif gift_product_ids and len(gift_product_ids) > 0:
                # Передаём все товары (items), не только eligible_items
                # чтобы находить подарки даже если они не в категории триггера
                discount, applied_items = self._calculate_gift_with_purchase(
                    items, gift_product_ids, buy_n, get_n, 
                    discount_percent, max_gifts_limit, eligible_items
                )
            
            # ===== ВАРИАНТ 4: Самый дешёвый товар в подарок (вторая пицца бесплатно) =====
            elif config.get('cheapest_item_as_gift', False):
                discount, applied_items = self._calculate_cheapest_item_gift(
                    eligible_items, buy_n, get_n, discount_percent, max_gifts_limit
                )
            
            # ===== ВАРИАНТ 5: Смешанный (каждый n-й из общего списка) =====
            else:
                discount, applied_items = self._calculate_n_plus_gift(
                    eligible_items, buy_n, get_n, discount_percent
                )
        
        # ========== СКИДКА ОТ СУММЫ ЗАКАЗА ==========
        elif promo_type in ["sum_discount", "SUM_DISCOUNT", "sum_gift", "SUM_GIFT"]:
            sum_threshold = config.get('sum_threshold', 0)
            sum_discount_value = config.get('sum_discount', 0)
            
            if eligible_subtotal >= sum_threshold:
                discount = min(sum_discount_value, eligible_subtotal)
                
                for item in eligible_items:
                    ratio = (item.price * item.quantity) / eligible_subtotal
                    item_discount = discount * ratio
                    applied_items.append({
                        'product_id': item.product_id,
                        'name': item.name,
                        'discount': round(item_discount, 2),
                        'type': 'sum_discount',
                        'original_price': item.price * item.quantity
                    })
        
        # ========== КОМБО-НАБОР ==========
        elif promo_type in ["combo", "COMBO", "combo_fixed_price", "COMBO_FIXED_PRICE"]:
            combo_quantity = config.get('combo_quantity', 2)
            combo_fixed_price = config.get('combo_fixed_price', 0)
            
            discount, applied_items = self._calculate_combo(
                eligible_items, combo_quantity, combo_fixed_price
            )
        
        # ========== КАЖДОЕ N-Е СО СКИДКОЙ ==========
        elif promo_type in ["nth_discount", "NTH_DISCOUNT"]:
            every_n = config.get('every_n', 3)
            nth_discount_percent = config.get('discount_percent', 50)
            
            discount, applied_items = self._calculate_nth_discount(
                eligible_items, every_n, nth_discount_percent
            )
        
        logger.debug(f"=== calculate_discount END: discount={round(discount, 2)} ===")
        return round(discount, 2), applied_items
    
    def _calculate_fixed_price_second(self, eligible_items, buy_n, get_n, fixed_price, same_product_gift):
        """Расчет 'второй за фикс. цену'"""
        discount = 0.0
        applied_items = []
        
        if same_product_gift:
            # Группируем по product_id
            product_groups = defaultdict(list)
            for item in eligible_items:
                for _ in range(item.quantity):
                    product_groups[item.product_id].append({
                        'product_id': item.product_id,
                        'name': item.name,
                        'price': item.price
                    })
            
            for pid, units in product_groups.items():
                if len(units) <= buy_n:
                    continue
                
                # Сортируем: дорогие первые (по полной цене)
                units.sort(key=lambda x: x['price'], reverse=True)
                
                idx = 0
                while idx < len(units):
                    # Пропускаем buy_n по полной цене
                    idx += buy_n
                    
                    # Следующие get_n за фиксированную цену
                    discounted = 0
                    while discounted < get_n and idx < len(units):
                        unit = units[idx]
                        
                        if unit['price'] > fixed_price:
                            item_discount = unit['price'] - fixed_price
                            discount += item_discount
                            
                            applied_items.append({
                                'product_id': unit['product_id'],
                                'name': unit['name'],
                                'discount': round(item_discount, 2),
                                'type': 'fixed_price_second',
                                'original_price': unit['price'],
                                'fixed_price': fixed_price
                            })
                        
                        idx += 1
                        discounted += 1
        else:
            # Общий список
            expanded = []
            for item in eligible_items:
                for _ in range(item.quantity):
                    expanded.append({
                        'product_id': item.product_id,
                        'name': item.name,
                        'price': item.price
                    })
            
            if len(expanded) > buy_n:
                expanded.sort(key=lambda x: x['price'], reverse=True)
                
                idx = buy_n
                discounted = 0
                while discounted < get_n and idx < len(expanded):
                    unit = expanded[idx]
                    
                    if unit['price'] > fixed_price:
                        item_discount = unit['price'] - fixed_price
                        discount += item_discount
                        
                        applied_items.append({
                            'product_id': unit['product_id'],
                            'name': unit['name'],
                            'discount': round(item_discount, 2),
                            'type': 'fixed_price_second',
                            'original_price': unit['price'],
                            'fixed_price': fixed_price
                        })
                    
                    idx += 1
                    discounted += 1
        
        return discount, applied_items
    
    def _calculate_gift_with_purchase(self, all_items, gift_product_ids, buy_n, get_n, 
                                     discount_percent, max_gifts_limit, eligible_items=None):
        """Расчет 'подарок за покупку' (конкретный товар в подарок)"""
        discount = 0.0
        applied_items = []
        
        # eligible_items - товары по категории (триггеры), all_items - все товары (включая подарки)
        if eligible_items is None:
            eligible_items = all_items
        
        # Триггеры - товары по категории, МИНУС подарки (чтобы не дублировать)
        # Оставшиеся подарки станут триггерами через каскадную логику
        buy_items = [
            item for item in eligible_items 
            if item.product_id not in gift_product_ids 
            and (item.variant_id not in gift_product_ids if item.variant_id else True)
        ]
        
        # Подарки - ищем во ВСЕХ товарах (не только eligible_items)
        gift_items_available = [
            item for item in all_items 
            if item.product_id in gift_product_ids
            or (item.variant_id in gift_product_ids if item.variant_id else False)
        ]
        
        # Если нет отдельных покупок, но есть подарки - 
        # считаем что покупаем подарки и получаем их же бесплатно (1+1 на тот же товар)
        if not buy_items and gift_items_available:
            buy_items = gift_items_available
        
        # КАСКАДНАЯ ЛОГИКА:
        # 1. Сначала обычные триггеры дают подарки
        # 2. Оставшиеся подарки становятся триггерами для следующих подарков
        # 3. Повторяем пока есть пары
        
        total_buy_qty = sum(item.quantity for item in buy_items)
        total_gift_qty = sum(item.quantity for item in gift_items_available)
        
        # Общее количество товаров (триггеры + подарки)
        total_items = total_buy_qty + total_gift_qty
        
        # Каждые buy_n + get_n товаров = get_n подарков
        # Но подарок должен быть из gift_items_available
        group_size = buy_n + get_n
        
        # Сколько полных групп (каскадно)
        # Например: 7 товаров, buy_n=1, get_n=1 → 7 // 2 = 3 подарка
        allowed_gifts = (total_items // group_size) * get_n
        
        # Не больше чем есть подарков в корзине
        allowed_gifts = min(allowed_gifts, total_gift_qty)
        
        # Лимит из конфига
        if max_gifts_limit is not None:
            allowed_gifts = min(allowed_gifts, max_gifts_limit)
        
        # Применяем скидку к подаркам
        if gift_items_available and allowed_gifts > 0:
            # Разворачиваем в единицы
            gift_units = []
            for item in gift_items_available:
                for _ in range(item.quantity):
                    gift_units.append({
                        'product_id': item.product_id,
                        'name': item.name,
                        'price': item.price
                    })
            
            # Применяем скидку к min(положено, доступно)
            actual_gifts = min(allowed_gifts, len(gift_units))
            
            for i in range(actual_gifts):
                unit = gift_units[i]
                item_discount = unit['price'] * (discount_percent / 100)
                discount += item_discount
                
                applied_items.append({
                    'product_id': unit['product_id'],
                    'name': unit['name'],
                    'discount': round(item_discount, 2),
                    'type': 'gift_with_purchase',
                    'original_price': unit['price'],
                    'final_price': unit['price'] - item_discount if discount_percent < 100 else 0
                })
        
        return discount, applied_items
    
    def _calculate_same_product_gift_v2(self, eligible_items, buy_n, get_n, discount_percent, buy_product_ids=None, gift_product_ids=None):
        """Расчет 'N+M на тот же товар' v2 - с разделением по buy/gift items
        
        Логика:
        - Если есть отдельные триггеры (buy_product_ids) и акционные (gift_product_ids):
          * Пары: триггер + акционный = 100% скидка на акционный
          * Остаток акционных: чётные = 50%, нечётный = полная цена
        - Если только акционные (без отдельных триггеров):
          * Каждая нечётная = триггер, каждая чётная = акционная (50%)
        """
        print(f"DEBUG same_product_gift_v2: buy_n={buy_n}, get_n={get_n}", flush=True)
        print(f"DEBUG same_product_gift_v2: buy_product_ids={buy_product_ids}", flush=True)
        print(f"DEBUG same_product_gift_v2: gift_product_ids={gift_product_ids}", flush=True)
        print(f"DEBUG same_product_gift_v2: eligible_items={[(i.product_id, i.quantity, i.price) for i in eligible_items]}", flush=True)
        
        discount = 0.0
        applied_items = []
        
        # Разделяем товары на триггеры и акционные
        trigger_units = []  # Все товары НЕ из gift_product_ids
        gift_units = []     # Товары из gift_product_ids
        
        for item in eligible_items:
            # Проверяем по product_id и variant_id
            item_ids = [item.product_id]
            if item.variant_id:
                item_ids.append(item.variant_id)
            
            is_gift = False
            if gift_product_ids:
                if any(iid in gift_product_ids for iid in item_ids):
                    is_gift = True
            
            for _ in range(item.quantity):
                unit = {
                    'product_id': item.product_id,
                    'variant_id': item.variant_id,
                    'name': item.name,
                    'price': item.price
                }
                if is_gift:
                    gift_units.append(unit)
                else:
                    # Не gift = trigger (все остальные из eligible_items)
                    trigger_units.append(unit)
        
        logger.warning(f"DEBUG same_product_gift_v2: trigger_units={len(trigger_units)}, gift_units={len(gift_units)}")
        
        # === ЛОГИКА 1+1 ===
        if buy_n == 1 and get_n == 1:
            # Сортируем: дорогие первые
            trigger_units.sort(key=lambda x: x['price'], reverse=True)
            gift_units.sort(key=lambda x: x['price'], reverse=True)
            
            # Есть отдельные триггеры и акционные
            if len(trigger_units) > 0 and len(gift_units) > 0:
                # Пары: каждый триггер + каждый акционный (1:1)
                pairs_count = min(len(trigger_units), len(gift_units))
                
                used_gift_indices = set()  # Отслеживаем использованные акционные
                
                for i in range(pairs_count):
                    # Акционный товар в паре = 100% скидка (бесплатно)
                    gift = gift_units[i]
                    item_discount = gift['price']
                    discount += item_discount
                    used_gift_indices.add(i)
                    
                    applied_items.append({
                        'product_id': gift['product_id'],
                        'name': gift['name'],
                        'discount': round(item_discount, 2),
                        'type': 'same_product_gift_paired',
                        'original_price': gift['price'],
                        'final_price': 0
                    })
                
                # Оставшиеся акционные (без пары): каждая третья = полная, первые две = 50%
                remaining_gifts = [gift_units[i] for i in range(len(gift_units)) if i not in used_gift_indices]
                for i, unit in enumerate(remaining_gifts):
                    # i = 0, 1, 2, 3, 4... → группы по 3: (0,1=50%), (2=полная), (3,4=50%), (5=полная)...
                    if i % 3 != 2:  # не каждая третья (индексы 0,1,3,4,6,7...)
                        item_discount = unit['price'] * 0.5  # 50% скидка
                        discount += item_discount
                        
                        applied_items.append({
                            'product_id': unit['product_id'],
                            'name': unit['name'],
                            'discount': round(item_discount, 2),
                            'type': 'same_product_gift_unpaired',
                            'original_price': unit['price'],
                            'final_price': unit['price'] - item_discount
                        })
            
            # Только акционные (без отдельных триггеров)
            elif len(gift_units) > 0:
                # Каждая нечётная = триггер, каждая чётная = акционная (100% бесплатно)
                for i, unit in enumerate(gift_units):
                    if i % 2 == 1:  # чётные индексы (1, 3, 5...) = акционные
                        item_discount = unit['price']  # 100% скидка
                        discount += item_discount
                        
                        applied_items.append({
                            'product_id': unit['product_id'],
                            'name': unit['name'],
                            'discount': round(item_discount, 2),
                            'type': 'same_product_gift_only',
                            'original_price': unit['price'],
                            'final_price': 0
                        })
            
            print(f"DEBUG same_product_gift_v2: final discount={discount}", flush=True)
            return discount, applied_items
        
        # Другие варианты (2+1 и т.д.) — пока не реализованы
        return 0, []
    
    def _calculate_same_product_gift(self, eligible_items, buy_n, get_n, discount_percent, buy_product_ids=None):
        """Расчет 'N+M на тот же товар' (включая 1+1)
        
        Логика:
        - Триггеры = товары из buy_product_ids (полная цена)
        - Акционные = товары из gift_items (скидка)
        - Для same_product_gift: buy_items = gift_items, но разделяем по правилам:
          1. Пары (триггер + акционный): акционный = 100% скидка
          2. Оставшиеся акционные без триггера: чётные = 50%, нечётный = полная цена
        """
        print(f"DEBUG same_product_gift: buy_n={buy_n}, get_n={get_n}, buy_product_ids={buy_product_ids}", flush=True)
        print(f"DEBUG same_product_gift: eligible_items={[(i.product_id, i.quantity, i.price) for i in eligible_items]}", flush=True)
        
        discount = 0.0
        applied_items = []
        
        # Собираем все единицы товаров (разворачиваем quantity)
        all_units = []
        for item in eligible_items:
            for _ in range(item.quantity):
                all_units.append({
                    'product_id': item.product_id,
                    'variant_id': item.variant_id,
                    'name': item.name,
                    'price': item.price
                })
        
        print(f"DEBUG same_product_gift: all_units count={len(all_units)}", flush=True)
        
        if len(all_units) == 0:
            return 0, []
        
        # === ЛОГИКА 1+1 ===
        if buy_n == 1 and get_n == 1:
            # Сортируем: дорогие первые
            all_units.sort(key=lambda x: x['price'], reverse=True)
            
            # Разделяем: половина = триггеры, половина = акционные
            # Триггеры = первые 50% (округляем вверх)
            # Акционные = оставшиеся 50%
            total = len(all_units)
            trigger_count = (total + 1) // 2  # округляем вверх: 7→4, 6→3, 5→3, 4→2, 3→2, 2→1
            
            trigger_items = all_units[:trigger_count]
            gift_items = all_units[trigger_count:]
            
            print(f"DEBUG same_product_gift: total={total}, triggers={len(trigger_items)}, gifts={len(gift_items)}", flush=True)
            
            # Пары: каждый триггер + каждый акционный (1:1)
            pairs_count = min(len(trigger_items), len(gift_items))
            
            for i in range(pairs_count):
                # Акционный товар в паре = 100% скидка (бесплатно)
                gift = gift_items[i]
                item_discount = gift['price']
                discount += item_discount
                
                applied_items.append({
                    'product_id': gift['product_id'],
                    'name': gift['name'],
                    'discount': round(item_discount, 2),
                    'type': 'same_product_gift_paired',
                    'original_price': gift['price'],
                    'final_price': 0
                })
            
            # Оставшиеся триггеры (без пары) = полная цена (нет скидки)
            # Оставшиеся акционные (без пары) = 50% скидка
            remaining_gifts = gift_items[pairs_count:]
            for unit in remaining_gifts:
                item_discount = unit['price'] * 0.5
                discount += item_discount
                
                applied_items.append({
                    'product_id': unit['product_id'],
                    'name': unit['name'],
                    'discount': round(item_discount, 2),
                    'type': 'same_product_gift_unpaired',
                    'original_price': unit['price'],
                    'final_price': unit['price'] - item_discount
                })
            
            print(f"DEBUG same_product_gift: final discount={discount}", flush=True)
            return discount, applied_items
        
        # === ЛОГИКА 2+1, 3+3 и т.д. ===
        # Группируем триггеры по product_id
        product_groups = defaultdict(list)
        for unit in trigger_items:
            product_groups[unit['product_id']].append(unit)
        
        for pid, units in product_groups.items():
            total_units = len(units)
            
            if total_units < buy_n + 1:
                continue
            
            # Сортируем: дорогие первые (платные), дешевые в конец (подарки)
            units.sort(key=lambda x: x['price'], reverse=True)
            
            group_size = buy_n + get_n
            
            for group_start in range(0, len(units), group_size):
                for gift_idx in range(group_start + buy_n, 
                                      min(group_start + group_size, len(units))):
                    unit = units[gift_idx]
                    item_discount = unit['price'] * (discount_percent / 100)
                    discount += item_discount
                    
                    applied_items.append({
                        'product_id': unit['product_id'],
                        'name': unit['name'],
                        'discount': round(item_discount, 2),
                        'type': 'same_product_gift',
                        'original_price': unit['price'],
                        'final_price': unit['price'] - item_discount if discount_percent < 100 else 0
                    })
        
        return discount, applied_items
    
    def _calculate_n_plus_gift(self, eligible_items, buy_n, get_n, discount_percent):
        """Расчет 'каждый n-й со скидкой' из общего списка"""
        discount = 0.0
        applied_items = []
        
        expanded = []
        for item in eligible_items:
            for _ in range(item.quantity):
                expanded.append({
                    'product_id': item.product_id,
                    'name': item.name,
                    'price': item.price
                })
        
        if len(expanded) >= buy_n + 1:
            expanded.sort(key=lambda x: x['price'], reverse=True)
            
            group_size = buy_n + get_n
            
            for group_start in range(0, len(expanded), group_size):
                for gift_idx in range(group_start + buy_n, 
                                      min(group_start + group_size, len(expanded))):
                    unit = expanded[gift_idx]
                    item_discount = unit['price'] * (discount_percent / 100)
                    discount += item_discount
                    
                    applied_items.append({
                        'product_id': unit['product_id'],
                        'name': unit['name'],
                        'discount': round(item_discount, 2),
                        'type': 'n_plus_gift',
                        'original_price': unit['price']
                    })
        
        return discount, applied_items
    
    def _calculate_combo(self, eligible_items, combo_quantity, combo_fixed_price):
        """Расчет комбо-набора"""
        discount = 0.0
        applied_items = []
        
        expanded = []
        for item in eligible_items:
            for _ in range(item.quantity):
                expanded.append({
                    'product_id': item.product_id,
                    'name': item.name,
                    'price': item.price
                })
        
        # Сколько полных комбо набирается
        num_combos = len(expanded) // combo_quantity
        
        if num_combos > 0:
            # Сортируем по цене
            expanded.sort(key=lambda x: x['price'], reverse=True)
            
            # Берем самые дорогие товары для комбо
            combo_items = expanded[:num_combos * combo_quantity]
            combo_total = sum(item['price'] for item in combo_items)
            combo_discounted_total = num_combos * combo_fixed_price
            
            discount = combo_total - combo_discounted_total
            
            # Распределяем скидку по товарам
            for item in combo_items:
                item_discount = discount * (item['price'] / combo_total)
                applied_items.append({
                    'product_id': item['product_id'],
                    'name': item['name'],
                    'discount': round(item_discount, 2),
                    'type': 'combo',
                    'original_price': item['price']
                })
        
        return discount, applied_items
    
    def _calculate_nth_discount(self, eligible_items, every_n, discount_percent):
        """Расчет 'каждое n-е со скидкой'"""
        discount = 0.0
        applied_items = []
        
        expanded = []
        for item in eligible_items:
            for _ in range(item.quantity):
                expanded.append({
                    'product_id': item.product_id,
                    'name': item.name,
                    'price': item.price
                })
        
        # Сортируем по цене (дешевые будут со скидкой)
        expanded.sort(key=lambda x: x['price'])
        
        # Каждый every_n-й товар со скидкой
        for i in range(len(expanded)):
            if (i + 1) % every_n == 0:  # every_n, 2*every_n, 3*every_n...
                unit = expanded[i]
                item_discount = unit['price'] * (discount_percent / 100)
                discount += item_discount
                
                applied_items.append({
                    'product_id': unit['product_id'],
                    'name': unit['name'],
                    'discount': round(item_discount, 2),
                    'type': 'nth_discount',
                    'original_price': unit['price']
                })
        
        return discount, applied_items
    
    def _calculate_cheapest_item_gift(self, eligible_items, buy_n, get_n, discount_percent, max_gifts_limit):
        """Расчет 'самый дешёвый товар в подарок' (вторая пицца бесплатно)"""
        discount = 0.0
        applied_items = []
        
        # Разворачиваем все товары в единицы
        expanded = []
        for item in eligible_items:
            for _ in range(item.quantity):
                expanded.append({
                    'product_id': item.product_id,
                    'name': item.name,
                    'price': item.price
                })
        
        total_items = len(expanded)
        
        # Нужно минимум buy_n + 1 товаров (например, для 1+1 нужно 2)
        if total_items < buy_n + 1:
            return discount, applied_items
        
        # Сортируем: дорогие первые (платные), дешевые в конец (подарки)
        expanded.sort(key=lambda x: x['price'], reverse=True)
        
        # Сколько подарков положено
        # Формула: на каждые buy_n покупок - get_n подарков
        # Например: 1+1 с 4 товарами = 4//(1+1) * 1 = 2 подарка
        allowed_gifts = (total_items // (buy_n + get_n)) * get_n
        if max_gifts_limit is not None:
            allowed_gifts = min(allowed_gifts, max_gifts_limit)
        
        # Применяем скидку к самым дешевым (они в конце после сортировки)
        actual_gifts = min(allowed_gifts, total_items - buy_n)
        
        for i in range(actual_gifts):
            # Берем с конца (самые дешевые)
            unit = expanded[total_items - 1 - i]
            item_discount = unit['price'] * (discount_percent / 100)
            discount += item_discount
            
            applied_items.append({
                'product_id': unit['product_id'],
                'name': unit['name'],
                'discount': round(item_discount, 2),
                'type': 'cheapest_item_gift',
                'original_price': unit['price'],
                'final_price': unit['price'] - item_discount if discount_percent < 100 else 0
            })
        
        return discount, applied_items
    
    def apply_promotions(self, data: CalculateOrderRequest) -> CalculateOrderResponse:
        """Применение всех активных акций"""
        logger.warning(f"=== apply_promotions START ===")
        logger.warning(f"promo_code={data.promo_code}, items={[(i.product_id, i.quantity) for i in data.items]}")
        
        subtotal = sum(item.price * item.quantity for item in data.items)
        logger.warning(f"subtotal={subtotal}")
        
        # Получаем все активные акции
        Promo = self.models.Promotion
        promos = self.db.query(Promo).filter(
            Promo.status == "active"
        ).order_by(Promo.sort_order.desc()).all()
        logger.warning(f"Found {len(promos)} active promos")
        
        total_discount = 0.0
        delivery_discount = 0.0
        applied_promos = []
        free_delivery = False
        
        # Обработка промокода
        if data.promo_code:
            code_promo = None
            for promo in promos:
                promo_code = getattr(promo, 'code', None) or getattr(promo, 'promo_code', None)
                if promo_code and promo_code.upper() == data.promo_code.upper():
                    code_promo = promo
                    break
            
            logger.warning(f"code_promo={code_promo}")
            if code_promo:
                can_apply, reason = self.can_apply_promo(code_promo, data)
                logger.warning(f"can_apply={can_apply}, reason={reason}")
                if can_apply:
                    discount, items_detail = self.calculate_discount(
                        code_promo, data.items, subtotal, data
                    )
                    logger.warning(f"discount={discount}, items_detail={items_detail}")
                    
                    promo_type = getattr(code_promo, 'type', '')
                    if promo_type in ['free_delivery', 'FREE_DELIVERY']:
                        free_delivery = True
                        delivery_discount = data.delivery_cost or 0
                    
                    total_discount += discount
                    
                    applied_promos.append(AppliedPromoDetail(
                        promotion_id=code_promo.id,
                        name=code_promo.name,
                        type=str(promo_type),
                        discount=discount,
                        description=getattr(code_promo, 'short_description', None),
                        applied_items=[AppliedPromoItem(**i) for i in items_detail if i.get('product_id')]
                    ))
        
        # Обработка авто-акций
        for promo in promos:
            # Пропускаем если уже применили по промокоду
            if data.promo_code:
                promo_code = getattr(promo, 'code', None) or getattr(promo, 'promo_code', None)
                if promo_code and promo_code.upper() == data.promo_code.upper():
                    continue
            
            # Пропускаем если требуется промокод но не введен
            if getattr(promo, 'code', None) or getattr(promo, 'promo_code', None):
                if not data.promo_code:
                    continue
            
            if not getattr(promo, 'auto_apply', True):
                continue
            
            can_apply, _ = self.can_apply_promo(promo, data)
            if not can_apply:
                continue
            
            remaining = subtotal - total_discount
            discount, items_detail = self.calculate_discount(
                promo, data.items, remaining, data
            )
            
            if discount <= 0 and not items_detail:
                continue
            
            # Cross-off логика
            cross_off = getattr(promo, 'cross_off', False)
            if not cross_off:  # Если акция НЕ совместима - сбрасываем предыдущие
                total_discount = 0
                delivery_discount = 0
                free_delivery = False
                applied_promos = []
            
            promo_type = getattr(promo, 'type', '')
            if promo_type in ['free_delivery', 'FREE_DELIVERY']:
                free_delivery = True
                delivery_discount = data.delivery_cost or 0
            
            total_discount += discount
            
            applied_promos.append(AppliedPromoDetail(
                promotion_id=promo.id,
                name=promo.name,
                type=str(promo_type),
                discount=discount,
                description=getattr(promo, 'short_description', None),
                applied_items=[AppliedPromoItem(**i) for i in items_detail if i.get('product_id')]
            ))
            
            # Если акция сбрасывает другие - прерываем
            if getattr(promo, 'discount_addition_off', False):
                break
        
        total = subtotal - total_discount + (data.delivery_cost or 0) - delivery_discount
        
        return CalculateOrderResponse(
            subtotal=round(subtotal, 2),
            discount=round(total_discount, 2),
            delivery_discount=round(delivery_discount, 2),
            total=round(total, 2),
            applied_promos=applied_promos,
            free_delivery=free_delivery
        )


@router.post("/calculate", response_model=CalculateOrderResponse)
def calculate_order(data: CalculateOrderRequest, db: Session = Depends(get_db)):
    """Calculate order total with promotions"""
    service = PromotionService(db)
    return service.apply_promotions(data)


@router.post("/validate-code")
def validate_promo_code(
    code: str,
    items: List[CalculateOrderItem],
    source: str = "site",
    delivery_type: str = "delivery",
    db: Session = Depends(get_db)
):
    """Проверка промокода без применения"""
    from app import models
    
    promo = db.query(models.Promotion).filter(
        (models.Promotion.code.ilike(code)) | 
        (models.Promotion.promo_code.ilike(code))
    ).first()
    
    if not promo:
        return {"valid": False, "error": "Промокод не найден"}
    
    if promo.status != "active":
        return {"valid": False, "error": "Акция не активна"}
    
    service = PromotionService(db)
    
    request = CalculateOrderRequest(
        items=items,
        promo_code=code,
        source=source,
        delivery_type=delivery_type
    )
    
    can_apply, reason = service.can_apply_promo(promo, request)
    
    if not can_apply:
        return {"valid": False, "error": f"Условия не выполнены: {reason}"}
    
    # Рассчитываем скидку для отображения
    subtotal = sum(item.price * item.quantity for item in items)
    logger.warning(f"validate-code: subtotal={subtotal}, calling calculate_discount")
    discount, applied_items = service.calculate_discount(promo, items, subtotal, request)
    logger.warning(f"validate-code: discount={discount}, applied_items={applied_items}")
    
    return {
        "valid": True,
        "promo": {
            "id": promo.id,
            "name": promo.name,
            "type": promo.type,
            "description": getattr(promo, 'short_description', None)
        },
        "discount": discount,
        "applied_items": applied_items
    }
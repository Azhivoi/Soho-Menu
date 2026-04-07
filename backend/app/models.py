from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DECIMAL, Text, DateTime, Date, Time, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(String(50), unique=True, nullable=True)
    name_ru = Column(String(100), nullable=False)
    name_en = Column(String(100))
    slug = Column(String(50), unique=True, nullable=False)
    kitchen_id = Column(String(50), ForeignKey("kitchens.kitchen_id"), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    products = relationship("Product", back_populates="category")


class Kitchen(Base):
    __tablename__ = "kitchens"
    
    id = Column(Integer, primary_key=True, index=True)
    kitchen_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    icon = Column(String(10), default='🍽️')
    color = Column(String(7), default='#ff6b35')
    print_runner = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    name_ru = Column(String(200), nullable=False)
    name_en = Column(String(200))
    description_ru = Column(Text)
    composition_ru = Column(Text)
    weight_grams = Column(Integer)
    image_url = Column(String(500))
    is_new = Column(Boolean, default=False)
    is_spicy = Column(Boolean, default=False)
    is_hit = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    discounts_disabled = Column(Boolean, default=False)  # If True, discounts don't apply to this product
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    category = relationship("Category", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product")

class ProductVariant(Base):
    __tablename__ = "product_variants"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    name_ru = Column(String(100))
    price = Column(DECIMAL(10, 2), nullable=False)
    weight_grams = Column(Integer)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    product = relationship("Product", back_populates="variants")

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True)
    phone = Column(String(20), unique=True)
    name = Column(String(100))
    email = Column(String(100))
    address = Column(Text)
    password_hash = Column(String(255))  # For phone/password login
    auth_token = Column(String(255))  # For session management
    discount_percent = Column(Integer, default=0)
    birthday = Column(Date)
    comment = Column(Text)
    bonus_points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    order_number = Column(String(20), unique=True)
    status = Column(String(20), default='new')
    order_type = Column(String(20), default='delivery')
    payment_type = Column(String(20), default='cash')
    assignee = Column(String(100))
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    bonus_used = Column(Integer, default=0)
    bonus_earned = Column(Integer, default=0)
    delivery_address = Column(Text)
    delivery_phone = Column(String(20))
    customer_name = Column(String(100))
    comment = Column(Text)
    scheduled_time = Column(String(10))  # Format: HH:MM for pre-orders
    delivery_fee = Column(DECIMAL(10, 2), default=0)
    promo_code = Column(String(50))
    promo_discount = Column(DECIMAL(10, 2), default=0)
    promo_promotion_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    customer = relationship("Customer")
    items = relationship("OrderItem", back_populates="order")
    marks = relationship("OrderMark", back_populates="order")


class OrderMark(Base):
    __tablename__ = "order_marks"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"))
    mark_id = Column(String(20), ForeignKey("marks.mark_id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    order = relationship("Order", back_populates="marks")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("menu_products.id"))
    variant_id = Column(Integer, ForeignKey("menu_products.id"))
    name = Column(String(255))
    quantity = Column(Integer, default=1)
    price = Column(DECIMAL(10, 2), nullable=False)
    modifiers = Column(JSONB, default=[])
    total_price = Column(DECIMAL(10, 2), nullable=False)
    discount = Column(DECIMAL(10, 2), default=0)
    
    order = relationship("Order", back_populates="items")


# ========== INGREDIENTS & RECIPES ==========

class Ingredient(Base):
    __tablename__ = "ingredients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    name_ru = Column(String(255), nullable=False)
    name_en = Column(String(255))
    category = Column(String(100))
    unit = Column(String(50), default='г')
    cost_per_unit = Column(DECIMAL(10, 4))
    supplier = Column(String(255))
    shelf_life_days = Column(Integer)
    processing_loss_percent = Column(DECIMAL(5, 2), default=0)
    storage_conditions = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SemiProduct(Base):
    __tablename__ = "semi_products"
    
    id = Column(Integer, primary_key=True, index=True)
    name_ru = Column(String(255), nullable=False)
    name_en = Column(String(255))
    category = Column(String(100))
    output_weight = Column(DECIMAL(10, 2))
    cost_per_100g = Column(DECIMAL(10, 2))
    shelf_life_days = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Recipe(Base):
    __tablename__ = "recipes"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    name = Column(String(255))
    output_weight = Column(DECIMAL(10, 2))
    cooking_time_minutes = Column(Integer)
    instructions = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RecipeItem(Base):
    __tablename__ = "recipe_items"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    semi_product_id = Column(Integer, ForeignKey("semi_products.id"))
    quantity = Column(DECIMAL(10, 2))
    unit = Column(String(50))
    cost = Column(DECIMAL(10, 2))


# ========== PRODUCTION DEPARTMENTS ==========

class ProductionDepartment(Base):
    __tablename__ = "production_departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True)
    description = Column(Text)
    printer_ip = Column(String(50))
    printer_port = Column(Integer, default=9100)
    printer_model = Column(String(100))
    paper_width = Column(Integer, default=80)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProductDepartment(Base):
    __tablename__ = "product_departments"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    department_id = Column(Integer, ForeignKey("production_departments.id"))
    is_primary = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class KitchenOrder(Base):
    __tablename__ = "kitchen_orders"

    id = Column(Integer, primary_key=True, index=True)
    main_order_id = Column(Integer, ForeignKey("orders.id"))
    department_id = Column(Integer, ForeignKey("production_departments.id"))
    kitchen_order_number = Column(String(50))
    status = Column(String(20), default='pending')
    printed_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class KitchenOrderItem(Base):
    __tablename__ = "kitchen_order_items"

    id = Column(Integer, primary_key=True, index=True)
    kitchen_order_id = Column(Integer, ForeignKey("kitchen_orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    variant_id = Column(Integer, ForeignKey("product_variants.id"))
    quantity = Column(Integer, nullable=False)
    product_name = Column(String(255))
    variant_name = Column(String(255))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class DepartmentReceiptTemplate(Base):
    __tablename__ = "department_receipt_templates"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("production_departments.id"))
    template_name = Column(String(255))
    header_text = Column(Text)
    footer_text = Column(Text)
    show_logo = Column(Boolean, default=True)
    logo_url = Column(String(500))
    font_size = Column(Integer, default=12)
    paper_width = Column(Integer, default=80)
    header_style = Column(String(50), default='bold')  # normal, bold, double, bold_double
    items_style = Column(String(50), default='normal')  # normal, bold
    cut_paper = Column(Boolean, default=True)
    beep = Column(Boolean, default=True)
    open_drawer = Column(Boolean, default=False)
    print_barcode = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CourierReceiptTemplate(Base):
    __tablename__ = "courier_receipt_templates"

    id = Column(Integer, primary_key=True, index=True)
    shop_name = Column(String(255), default='SOHO.by')
    shop_address = Column(String(500))
    shop_phone = Column(String(50))
    order_header = Column(Text, default='{DATE} {TIME}\n№ {ORDER_NUM}')
    footer_text = Column(Text, default='Спасибо за заказ!')
    font_size = Column(Integer, default=12)
    paper_width = Column(Integer, default=80)
    show_client_name = Column(Boolean, default=True)
    show_bonus_info = Column(Boolean, default=True)
    show_address = Column(Boolean, default=True)
    show_client_phone = Column(Boolean, default=True)
    show_comment = Column(Boolean, default=True)
    show_delivery_mark = Column(Boolean, default=True)
    cut_paper = Column(Boolean, default=True)
    print_duplicates = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrinterSetting(Base):
    __tablename__ = "printer_settings"

    id = Column(Integer, primary_key=True, index=True)
    setting_name = Column(String(255), nullable=False)
    setting_value = Column(Text)
    setting_type = Column(String(50))
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ========== WAREHOUSE ==========

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    full_name = Column(String(500))
    contact_person = Column(String(255))
    phone = Column(String(50))
    email = Column(String(255))
    address = Column(Text)
    inn = Column(String(20))
    kpp = Column(String(20))
    bank_account = Column(String(50))
    bank_name = Column(String(255))
    bik = Column(String(20))
    contract_number = Column(String(100))
    contract_date = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WarehouseInvoice(Base):
    __tablename__ = "warehouse_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(100), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    invoice_date = Column(Date, nullable=False)
    received_date = Column(DateTime, default=datetime.utcnow)
    total_amount = Column(DECIMAL(12, 2), default=0)
    status = Column(String(20), default='draft')
    notes = Column(Text)
    scanned_image_url = Column(String(500))
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)


class WarehouseInvoiceItem(Base):
    __tablename__ = "warehouse_invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("warehouse_invoices.id"))
    original_name = Column(String(500))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    quantity = Column(DECIMAL(10, 3), nullable=False)
    unit = Column(String(50))
    price_per_unit = Column(DECIMAL(10, 2))
    total_price = Column(DECIMAL(10, 2))
    matched_by = Column(String(20))
    confidence_score = Column(DECIMAL(5, 2))
    created_at = Column(DateTime, default=datetime.utcnow)


class IngredientNameMapping(Base):
    __tablename__ = "ingredient_name_mappings"

    id = Column(Integer, primary_key=True, index=True)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    original_name = Column(String(500), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WarehouseStock(Base):
    __tablename__ = "warehouse_stock"

    id = Column(Integer, primary_key=True, index=True)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    quantity = Column(DECIMAL(10, 3), default=0)
    unit = Column(String(50))
    min_stock_level = Column(DECIMAL(10, 3), default=0)
    max_stock_level = Column(DECIMAL(10, 3))
    last_updated = Column(DateTime, default=datetime.utcnow)


class WarehouseMovement(Base):
    __tablename__ = "warehouse_movements"

    id = Column(Integer, primary_key=True, index=True)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    movement_type = Column(String(50), nullable=False)  # receipt, consumption, adjustment, inventory
    quantity = Column(DECIMAL(10, 3), nullable=False)
    unit = Column(String(50))
    reference_id = Column(Integer)
    reference_type = Column(String(50))
    notes = Column(Text)
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class InventoryCheck(Base):
    __tablename__ = "inventory_checks"

    id = Column(Integer, primary_key=True, index=True)
    check_date = Column(Date, nullable=False)
    status = Column(String(20), default='in_progress')
    notes = Column(Text)
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class InventoryCheckItem(Base):
    __tablename__ = "inventory_check_items"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory_checks.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    expected_quantity = Column(DECIMAL(10, 3))
    actual_quantity = Column(DECIMAL(10, 3))
    difference = Column(DECIMAL(10, 3))
    unit = Column(String(50))
    notes = Column(Text)
    checked_at = Column(DateTime)


# ========== SITE CONFIG ==========

class Config(Base):
    __tablename__ = "site_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    type = Column(String(20), default='text')  # text, json, number, boolean
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Unit(Base):
    __tablename__ = "units"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    abbreviation = Column(String(10), nullable=False)
    type = Column(String(20), nullable=False)  # weight, volume, piece


# ========== MENU MODULE ==========

class IngredientCategory(Base):
    __tablename__ = "ingredient_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_visible_on_site = Column(Boolean, default=True)
    is_visible_in_menu = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    kitchen_id = Column(String(50), ForeignKey("kitchens.kitchen_id"), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_visible_on_site = Column(Boolean, default=True)
    is_visible_in_menu = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SemiFinishedProduct(Base):
    __tablename__ = "semi_finished_products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    unit = Column(String(50))
    department_id = Column(Integer, ForeignKey("production_departments.id"), nullable=True)
    preparation_time_minutes = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SemiFinishedComposition(Base):
    __tablename__ = "semi_finished_composition"
    
    id = Column(Integer, primary_key=True, index=True)
    semi_finished_id = Column(Integer, ForeignKey("semi_finished_products.id"), nullable=False)
    item_type = Column(String(20), nullable=False)
    item_id = Column(Integer, nullable=False)
    quantity = Column(DECIMAL(10, 3), nullable=False)
    unit = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


class MenuProduct(Base):
    __tablename__ = "menu_products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    sku = Column(String(50), unique=True, nullable=True)
    barcode = Column(String(50), nullable=True)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("production_departments.id"), nullable=True)
    
    # For variable products (parent with variations)
    is_variable = Column(Boolean, default=False)
    parent_id = Column(Integer, ForeignKey("menu_products.id"), nullable=True)
    woo_id = Column(String(50), nullable=True)  # Original WooCommerce ID
    
    price = Column(DECIMAL(10, 2), default=0)
    cost_price = Column(DECIMAL(10, 2), default=0)
    image_url = Column(Text)
    description = Column(Text)
    weight_grams = Column(Integer)
    is_visible_on_site = Column(Boolean, default=True)
    is_visible_in_menu = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    discounts_disabled = Column(Boolean, default=False)  # If True, discounts don't apply to this product
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TechCard(Base):
    __tablename__ = "tech_cards"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("menu_products.id"), nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    preparation_method = Column(Text)
    cooking_time_minutes = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TechCardItem(Base):
    __tablename__ = "tech_card_items"
    
    id = Column(Integer, primary_key=True, index=True)
    tech_card_id = Column(Integer, ForeignKey("tech_cards.id"), nullable=False)
    item_type = Column(String(20), nullable=False)
    item_id = Column(Integer, nullable=False)
    quantity = Column(DECIMAL(10, 3), nullable=False)
    unit = Column(String(50))
    is_optional = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProductHistory(Base):
    __tablename__ = "product_history"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("menu_products.id"), nullable=False)
    field_name = Column(String(50), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    changed_by = Column(Integer, nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)


class Mark(Base):
    __tablename__ = "marks"
    
    id = Column(Integer, primary_key=True, index=True)
    mark_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#e94560")
    icon = Column(String(10), default='🏷️')
    mark_type = Column(String(20), default="order")  # order, client, product
    options = Column(Text, nullable=True)  # JSON array
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderStatus(Base):
    __tablename__ = "order_statuses"
    
    id = Column(Integer, primary_key=True, index=True)
    status_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#e94560")
    icon = Column(String(10), default="📋")
    sort_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    is_final = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderType(Base):
    __tablename__ = "order_types"
    
    id = Column(Integer, primary_key=True, index=True)
    type_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#e94560")
    icon = Column(String(10), default="🍽️")
    sort_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ========== COMPANY & LOCATIONS ==========

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255))
    email = Column(String(255), unique=True)  # Admin login email
    password_hash = Column(String(255))  # Admin password
    phone = Column(String(50))
    address = Column(Text)
    inn = Column(String(50))
    bank_details = Column(Text)
    timezone = Column(String(50), default="Europe/Minsk")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Terminal access
    terminal_login = Column(String(255), nullable=True)
    terminal_password_hash = Column(String(255), nullable=True)


class Location(Base):
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    name = Column(String(255), nullable=False)  # "SOHO Cafe - Центр"
    type = Column(String(50), default="cafe")  # cafe, warehouse, office
    address = Column(Text)
    phone = Column(String(50))
    timezone = Column(String(50), default="Europe/Minsk")
    is_active = Column(Boolean, default=True)
    settings = Column(JSONB, default={})  # Location-specific settings
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ========== EMPLOYEES & ROLES ==========

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)  # null = system role
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(10), default="👤")
    color = Column(String(20), default="#e94560")
    permissions = Column(JSONB, default={})
    is_system = Column(Boolean, default=False)  # System roles cannot be deleted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)  # Primary location
    
    # Personal Info
    name = Column(String(255))  # Full name (auto-generated from first_name + last_name)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    middle_name = Column(String(100))
    phone = Column(String(50))
    email = Column(String(255))
    birth_date = Column(Date)
    address = Column(Text)
    
    # Work Info
    role_id = Column(Integer, ForeignKey("roles.id"))
    hire_date = Column(Date)
    termination_date = Column(Date, nullable=True)
    
    # Login Credentials
    pin_code = Column(String(10))  # Display PIN (last 2 digits masked)
    pin_hash = Column(String(255))  # Hashed PIN for security
    password_hash = Column(String(255))  # Hashed password for admin panel login
    extension = Column(String(10))  # Internal number for Prostie Zvonki
    
    # Payroll
    hourly_rate = Column(DECIMAL(10, 2))  # Hourly wage
    salary = Column(DECIMAL(10, 2))  # Fixed salary (if applicable)
    payment_type = Column(String(20), default="hourly")  # hourly, salary, mixed
    
    # Work Schedule (JSON)
    work_schedule = Column(JSONB, default={})  # {"mon": {"start": "09:00", "end": "18:00"}, ...}
    
    # Status
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    can_access_terminal = Column(Boolean, default=False)
    can_access_crm = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_full_name(self):
        """Generate full name from parts"""
        parts = [p for p in [self.last_name, self.first_name, self.middle_name] if p]
        return " ".join(parts) if parts else (self.first_name or "Без имени")


class EmployeeWorkHours(Base):
    __tablename__ = "employee_work_hours"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    work_date = Column(Date, nullable=False)
    start_time = Column(Time)
    end_time = Column(Time)
    break_minutes = Column(Integer, default=0)
    total_hours = Column(DECIMAL(5, 2))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmployeeAdvance(Base):
    __tablename__ = "employee_advances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    advance_date = Column(Date, nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    description = Column(Text)
    is_deducted = Column(Boolean, default=False)
    deduction_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmployeePayroll(Base):
    __tablename__ = "employee_payroll"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    base_amount = Column(DECIMAL(10, 2), nullable=False)
    bonus_amount = Column(DECIMAL(10, 2), default=0)
    deduction_amount = Column(DECIMAL(10, 2), default=0)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    hours_worked = Column(DECIMAL(6, 2))
    advance_deduction = Column(DECIMAL(10, 2), default=0)
    final_amount = Column(DECIMAL(10, 2), nullable=False)
    is_paid = Column(Boolean, default=False)
    paid_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)


# ========== DISCOUNTS & PROMOS ==========

class Discount(Base):
    __tablename__ = "discounts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    value = Column(DECIMAL(10, 2), default=0)
    discount_type = Column(String(20), default="percent")  # percent, fixed
    applies_to = Column(String(20), default="order")  # order, item, category
    min_order_amount = Column(DECIMAL(10, 2))
    max_discount = Column(DECIMAL(10, 2))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ========== PROSTIE ZVONKI ==========

class PZSetting(Base):
    __tablename__ = "pz_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    server_url = Column(String(255), default="https://interaction.prostiezvonki.ru")
    api_token = Column(String(255))
    crm_token = Column(String(255), default="soho-crm-token")
    is_active = Column(Boolean, default=False)
    test_mode = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PZExtension(Base):
    __tablename__ = "pz_extensions"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), nullable=False)
    extension = Column(String(20), nullable=False)
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)



# ========== PROMOTIONS ==========

class Promotion(Base):
    __tablename__ = "promotions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    short_description = Column(String(200))  # Краткое описание для слайдера
    type = Column(String(50), default="percentage")  # percentage, fixed_amount, n_plus_gift, etc.
    target = Column(String(50), default="all")  # all, new, loyal, vip, birthday
    value = Column(DECIMAL(10, 2), default=0)
    
    # Type-specific config (JSON)
    config = Column(JSONB, default={})  # Доп. параметры: buy_n, get_n, gift_product_ids, etc.
    
    # Conditions
    min_order_amount = Column(DECIMAL(10, 2))
    max_discount = Column(DECIMAL(10, 2))
    
    # Time restrictions
    start_date = Column(Date)
    end_date = Column(Date)
    start_time = Column(String(10))  # "10:00"
    end_time = Column(String(10))  # "22:00"
    days_of_week = Column(JSONB, default=[])  # [1,2,3,4,5] - будни (1=Пн, 7=Вс)
    
    # Visual - 3 banner sizes
    banner_mobile = Column(String(500))  # 1080x1920
    banner_tablet = Column(String(500))  # 1920x1080
    banner_web = Column(String(500))  # 1920x600
    banner_color = Column(String(20), default="#e94560")
    
    # Display options
    is_featured = Column(Boolean, default=False)  # Важная акция
    show_on_main = Column(Boolean, default=False)  # Показывать на главной
    show_in_app = Column(Boolean, default=True)  # Показывать в приложении
    
    # Status
    status = Column(String(20), default="draft")  # draft, active, paused, expired
    
    # Usage limits
    usage_count = Column(Integer, default=0)  # Сколько раз использована
    usage_limit = Column(Integer)  # Общий лимит
    per_customer_limit = Column(Integer, default=0)  # Лимит на клиента
    first_order_only = Column(Boolean, default=False)  # Только для первого заказа
    
    # Promo code
    code = Column(String(50), index=True)  # Промокод (если нужен)
    auto_apply = Column(Boolean, default=True)  # Автоприменение
    
    # Menu binding
    category_ids = Column(JSONB, default=[])  # Привязка к категориям
    product_ids = Column(JSONB, default=[])  # Привязка к товарам
    excluded_products = Column(JSONB, default=[])  # Исключённые товары
    
    # Channel restrictions (new style - enabled flags)
    app_enabled = Column(Boolean, default=True)
    site_enabled = Column(Boolean, default=True)
    posterix_enabled = Column(Boolean, default=False)
    
    # Delivery type restrictions (new style - enabled flags)
    pickup_enabled = Column(Boolean, default=True)
    courier_enabled = Column(Boolean, default=True)
    inside_enabled = Column(Boolean, default=True)
    
    # Geo restrictions
    delivery_zones = Column(JSONB, default=[])  # ID зон доставки
    restaurants = Column(JSONB, default=[])  # ID ресторанов
    
    # Cross-promotion settings
    cross_off = Column(Boolean, default=True)  # Совместима с другими акциями
    discount_addition_off = Column(Boolean, default=False)  # Сбрасывать другие скидки
    
    # User restrictions
    auth_required = Column(Boolean, default=False)
    
    # Ordering
    sort_order = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ========== PRINT PROTECTION MODELS ==========

class PrintJob(Base):
    __tablename__ = "print_jobs"
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    print_type = Column(String(20), nullable=False)  # receipt, kitchen, precheck
    kitchen_id = Column(String(50), nullable=True)
    status = Column(String(20), default="pending")
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    print_data = Column(JSONB, nullable=False)
    printed_at = Column(DateTime, nullable=True)
    printed_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    printer_name = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    is_reprint = Column(Boolean, default=False)
    original_job_id = Column(Integer, ForeignKey("print_jobs.id"), nullable=True)
    reprint_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderPrintStatus(Base):
    __tablename__ = "order_print_status"
    
    order_id = Column(Integer, ForeignKey("orders.id"), primary_key=True)
    receipt_printed = Column(Boolean, default=False)
    receipt_printed_at = Column(DateTime, nullable=True)
    receipt_print_count = Column(Integer, default=0)
    kitchen_runners = Column(JSONB, default=dict)
    last_printed_at = Column(DateTime, nullable=True)
    last_print_type = Column(String(20), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ========== SETTINGS MODEL ==========

class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

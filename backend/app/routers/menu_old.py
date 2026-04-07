from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
import os
import uuid

from ..database import get_db
from ..models import (
    IngredientCategory, ProductCategory,
    SemiFinishedProduct, SemiFinishedComposition,
    MenuProduct, TechCard, TechCardItem, ProductHistory,
    ProductionDepartment
)
from ..auth import get_current_user

# Используем существующую модель Ingredient из recipes/warehouse
from ..models import Ingredient

router = APIRouter(prefix="/menu", tags=["menu"])

# СХЕМЫ
class IngredientCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None

class IngredientCategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True

class ProductCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sort_order: int = 0

class ProductCategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    sort_order: int
    is_active: bool
    class Config:
        from_attributes = True

class UnitResponse(BaseModel):
    id: int
    name: str
    abbreviation: str
    type: str
    class Config:
        from_attributes = True

class IngredientCreate(BaseModel):
    name: str
    category_id: Optional[int] = None
    unit_id: int
    processing_loss_percent: Decimal = Decimal('0.00')
    storage_conditions: Optional[str] = None
    shelf_life_days: Optional[int] = None

class IngredientResponse(BaseModel):
    id: int
    name: str
    category_id: Optional[int]
    category_name: Optional[str]
    unit_id: int
    unit_name: Optional[str]
    unit_abbreviation: Optional[str]
    processing_loss_percent: Decimal
    is_active: bool
    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    barcode: Optional[str] = None
    category_id: Optional[int] = None
    department_id: Optional[int] = None
    price: Decimal = Decimal('0.00')
    description: Optional[str] = None
    weight_grams: Optional[int] = None
    is_visible_on_site: bool = True
    is_visible_in_menu: bool = True

class ProductResponse(BaseModel):
    id: int
    name: str
    sku: Optional[str]
    barcode: Optional[str]
    category_id: Optional[int]
    category_name: Optional[str]
    department_id: Optional[int]
    department_name: Optional[str]
    price: Decimal
    cost_price: Decimal
    image_url: Optional[str]
    description: Optional[str]
    weight_grams: Optional[int]
    is_visible_on_site: bool
    is_visible_in_menu: bool
    is_active: bool
    class Config:
        from_attributes = True

# КАТЕГОРИИ ИНГРЕДИЕНТОВ
@router.get("/ingredient-categories", response_model=List[IngredientCategoryResponse])
def get_ingredient_categories(db: Session = Depends(get_db)):
    return db.query(IngredientCategory).order_by(IngredientCategory.name).all()

@router.post("/ingredient-categories", response_model=IngredientCategoryResponse)
def create_ingredient_category(
    data: IngredientCategoryCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    category = IngredientCategory(**data.dict())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

@router.put("/ingredient-categories/{category_id}", response_model=IngredientCategoryResponse)
def update_ingredient_category(
    category_id: int,
    data: IngredientCategoryCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    category = db.query(IngredientCategory).filter(IngredientCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    for key, value in data.dict().items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return category

@router.delete("/ingredient-categories/{category_id}")
def delete_ingredient_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    category = db.query(IngredientCategory).filter(IngredientCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    ingredients_count = db.query(Ingredient).filter(Ingredient.category_id == category_id).count()
    if ingredients_count > 0:
        raise HTTPException(status_code=400, detail=f"Нельзя удалить категорию. В ней {ingredients_count} ингредиентов")
    db.delete(category)
    db.commit()
    return {"message": "Категория удалена"}

# КАТЕГОРИИ ТОВАРОВ
@router.get("/product-categories", response_model=List[ProductCategoryResponse])
def get_product_categories(db: Session = Depends(get_db)):
    return db.query(ProductCategory).order_by(ProductCategory.sort_order).all()

@router.post("/product-categories", response_model=ProductCategoryResponse)
def create_product_category(
    data: ProductCategoryCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    category = ProductCategory(**data.dict())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

@router.put("/product-categories/{category_id}", response_model=ProductCategoryResponse)
def update_product_category(
    category_id: int,
    data: ProductCategoryCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    category = db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    for key, value in data.dict().items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return category

@router.delete("/product-categories/{category_id}")
def delete_product_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    category = db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    products_count = db.query(MenuProduct).filter(MenuProduct.category_id == category_id).count()
    if products_count > 0:
        raise HTTPException(status_code=400, detail=f"Нельзя удалить категорию. В ней {products_count} товаров")
    db.delete(category)
    db.commit()
    return {"message": "Категория удалена"}

# ЕДИНИЦЫ ИЗМЕРЕНИЯ
@router.get("/units", response_model=List[UnitResponse])
def get_units(db: Session = Depends(get_db)):
    return db.query(Unit).all()

# ИНГРЕДИЕНТЫ
@router.get("/ingredients", response_model=List[IngredientResponse])
def get_ingredients(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        Ingredient,
        IngredientCategory.name.label('category_name'),
        Unit.name.label('unit_name'),
        Unit.abbreviation.label('unit_abbreviation')
    ).outerjoin(IngredientCategory, Ingredient.category_id == IngredientCategory.id
    ).outerjoin(Unit, Ingredient.unit_id == Unit.id)
    if category_id:
        query = query.filter(Ingredient.category_id == category_id)
    if search:
        query = query.filter(Ingredient.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.filter(Ingredient.is_active == is_active)
    results = query.order_by(Ingredient.name).all()
    response = []
    for ingredient, cat_name, unit_name, unit_abbr in results:
        response.append(IngredientResponse(
            id=ingredient.id,
            name=ingredient.name,
            category_id=ingredient.category_id,
            category_name=cat_name,
            unit_id=ingredient.unit_id,
            unit_name=unit_name,
            unit_abbreviation=unit_abbr,
            processing_loss_percent=ingredient.processing_loss_percent,
            is_active=ingredient.is_active
        ))
    return response

@router.get("/ingredients/{ingredient_id}", response_model=IngredientResponse)
def get_ingredient(ingredient_id: int, db: Session = Depends(get_db)):
    result = db.query(
        Ingredient,
        IngredientCategory.name.label('category_name'),
        Unit.name.label('unit_name'),
        Unit.abbreviation.label('unit_abbreviation')
    ).outerjoin(IngredientCategory, Ingredient.category_id == IngredientCategory.id
    ).outerjoin(Unit, Ingredient.unit_id == Unit.id
    ).filter(Ingredient.id == ingredient_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Ингредиент не найден")
    ingredient, cat_name, unit_name, unit_abbr = result
    return IngredientResponse(
        id=ingredient.id, name=ingredient.name, category_id=ingredient.category_id,
        category_name=cat_name, unit_id=ingredient.unit_id, unit_name=unit_name,
        unit_abbreviation=unit_abbr, processing_loss_percent=ingredient.processing_loss_percent,
        is_active=ingredient.is_active
    )

@router.post("/ingredients", response_model=IngredientResponse)
def create_ingredient(
    data: IngredientCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    ingredient = Ingredient(**data.dict())
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return get_ingredient(ingredient.id, db)

@router.put("/ingredients/{ingredient_id}", response_model=IngredientResponse)
def update_ingredient(
    ingredient_id: int,
    data: IngredientCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ингредиент не найден")
    for key, value in data.dict().items():
        setattr(ingredient, key, value)
    db.commit()
    db.refresh(ingredient)
    return get_ingredient(ingredient.id, db)

@router.delete("/ingredients/{ingredient_id}")
def delete_ingredient(
    ingredient_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ингредиент не найден")
    db.delete(ingredient)
    db.commit()
    return {"message": "Ингредиент удален"}

# ПОЛУФАБРИКАТЫ
@router.get("/semi-finished")
def get_semi_finished(
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(SemiFinishedProduct)
    if search:
        query = query.filter(SemiFinishedProduct.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.filter(SemiFinishedProduct.is_active == is_active)
    return query.order_by(SemiFinishedProduct.name).all()

# ТОВАРЫ
@router.get("/products", response_model=List[ProductResponse])
def get_products(
    category_id: Optional[int] = None,
    department_id: Optional[int] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_visible_on_site: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        MenuProduct,
        ProductCategory.name.label('category_name'),
        ProductionDepartment.name.label('department_name')
    ).outerjoin(ProductCategory, MenuProduct.category_id == ProductCategory.id
    ).outerjoin(ProductionDepartment, MenuProduct.department_id == ProductionDepartment.id)
    if category_id:
        query = query.filter(MenuProduct.category_id == category_id)
    if department_id:
        query = query.filter(MenuProduct.department_id == department_id)
    if search:
        query = query.filter((MenuProduct.name.ilike(f"%{search}%")) | (MenuProduct.sku.ilike(f"%{search}%")))
    if is_active is not None:
        query = query.filter(MenuProduct.is_active == is_active)
    if is_visible_on_site is not None:
        query = query.filter(MenuProduct.is_visible_on_site == is_visible_on_site)
    results = query.order_by(MenuProduct.name).all()
    response = []
    for product, cat_name, dept_name in results:
        response.append(ProductResponse(
            id=product.id, name=product.name, sku=product.sku, barcode=product.barcode,
            category_id=product.category_id, category_name=cat_name,
            department_id=product.department_id, department_name=dept_name,
            price=product.price, cost_price=product.cost_price, image_url=product.image_url,
            description=product.description, weight_grams=product.weight_grams,
            is_visible_on_site=product.is_visible_on_site, is_visible_in_menu=product.is_visible_in_menu,
            is_active=product.is_active
        ))
    return response

@router.get("/products/{product_id}")
def get_product_detail(product_id: int, db: Session = Depends(get_db)):
    result = db.query(
        MenuProduct, ProductCategory.name.label('category_name'),
        ProductionDepartment.name.label('department_name')
    ).outerjoin(ProductCategory, MenuProduct.category_id == ProductCategory.id
    ).outerjoin(ProductionDepartment, MenuProduct.department_id == ProductionDepartment.id
    ).filter(MenuProduct.id == product_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Товар не найден")
    product, cat_name, dept_name = result
    tech_card = db.query(TechCard).filter(
        TechCard.product_id == product_id, TechCard.is_active == True
    ).first()
    tech_card_data = None
    if tech_card:
        items = db.query(TechCardItem, Unit.abbreviation.label('unit_abbr')
        ).outerjoin(Unit, TechCardItem.unit_id == Unit.id
        ).filter(TechCardItem.tech_card_id == tech_card.id).all()
        items_data = []
        for item, unit_abbr in items:
            if item.item_type == 'ingredient':
                source = db.query(Ingredient).filter(Ingredient.id == item.item_id).first()
            elif item.item_type == 'semi_finished':
                source = db.query(SemiFinishedProduct).filter(SemiFinishedProduct.id == item.item_id).first()
            else:
                source = db.query(MenuProduct).filter(MenuProduct.id == item.item_id).first()
            items_data.append({
                "id": item.id, "item_type": item.item_type, "item_id": item.item_id,
                "item_name": source.name if source else "Unknown",
                "quantity": item.quantity, "unit_abbreviation": unit_abbr,
                "is_optional": item.is_optional
            })
        tech_card_data = {
            "id": tech_card.id, "version": tech_card.version,
            "preparation_method": tech_card.preparation_method,
            "cooking_time_minutes": tech_card.cooking_time_minutes, "items": items_data
        }
    return {
        "id": product.id, "name": product.name, "sku": product.sku, "barcode": product.barcode,
        "category_id": product.category_id, "category_name": cat_name,
        "department_id": product.department_id, "department_name": dept_name,
        "price": product.price, "cost_price": product.cost_price,
        "image_url": product.image_url, "description": product.description,
        "weight_grams": product.weight_grams, "is_visible_on_site": product.is_visible_on_site,
        "is_visible_in_menu": product.is_visible_in_menu, "is_active": product.is_active,
        "tech_card": tech_card_data
    }

@router.post("/products")
def create_product(
    data: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    product = MenuProduct(
        name=data['name'], sku=data.get('sku'), barcode=data.get('barcode'),
        category_id=data.get('category_id'), department_id=data.get('department_id'),
        price=data.get('price', 0), description=data.get('description'),
        weight_grams=data.get('weight_grams'),
        is_visible_on_site=data.get('is_visible_on_site', True),
        is_visible_in_menu=data.get('is_visible_in_menu', True)
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    if 'tech_card' in data:
        tech_card = TechCard(
            product_id=product.id,
            preparation_method=data['tech_card'].get('preparation_method'),
            cooking_time_minutes=data['tech_card'].get('cooking_time_minutes')
        )
        db.add(tech_card)
        db.commit()
        db.refresh(tech_card)
        for item in data['tech_card'].get('items', []):
            if item['item_type'] == 'product' and item['item_id'] == product.id:
                continue
            tc_item = TechCardItem(
                tech_card_id=tech_card.id, item_type=item['item_type'],
                item_id=item['item_id'], quantity=item['quantity'],
                unit_id=item['unit_id'], is_optional=item.get('is_optional', False)
            )
            db.add(tc_item)
        db.commit()
    return get_product_detail(product.id, db)

@router.put("/products/{product_id}")
def update_product(
    product_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    product = db.query(MenuProduct).filter(MenuProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    old_price = product.price
    old_name = product.name
    product.name = data['name']
    product.sku = data.get('sku')
    product.barcode = data.get('barcode')
    product.category_id = data.get('category_id')
    product.department_id = data.get('department_id')
    product.price = data.get('price', 0)
    product.description = data.get('description')
    product.weight_grams = data.get('weight_grams')
    product.is_visible_on_site = data.get('is_visible_on_site', True)
    product.is_visible_in_menu = data.get('is_visible_in_menu', True)
    db.commit()
    if old_price != product.price:
        history = ProductHistory(
            product_id=product.id, field_name='price',
            old_value=str(old_price), new_value=str(product.price),
            changed_by=current_user.id if current_user else None
        )
        db.add(history)
    if old_name != product.name:
        history = ProductHistory(
            product_id=product.id, field_name='name',
            old_value=old_name, new_value=product.name,
            changed_by=current_user.id if current_user else None
        )
        db.add(history)
    if 'tech_card' in data:
        old_card = db.query(TechCard).filter(
            TechCard.product_id == product_id, TechCard.is_active == True
        ).first()
        if old_card:
            old_card.is_active = False
            db.commit()
        tech_card = TechCard(
            product_id=product.id,
            preparation_method=data['tech_card'].get('preparation_method'),
            cooking_time_minutes=data['tech_card'].get('cooking_time_minutes')
        )
        db.add(tech_card)
        db.commit()
        db.refresh(tech_card)
        for item in data['tech_card'].get('items', []):
            if item['item_type'] == 'product' and item['item_id'] == product_id:
                continue
            tc_item = TechCardItem(
                tech_card_id=tech_card.id, item_type=item['item_type'],
                item_id=item['item_id'], quantity=item['quantity'],
                unit_id=item['unit_id'], is_optional=item.get('is_optional', False)
            )
            db.add(tc_item)
        db.commit()
    db.commit()
    return get_product_detail(product_id, db)

@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    product = db.query(MenuProduct).filter(MenuProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    product.is_active = False
    db.commit()
    return {"message": "Товар деактивирован"}

@router.post("/products/{product_id}/image")
def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    product = db.query(MenuProduct).filter(MenuProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    ext = file.filename.split('.')[-1].lower()
    if ext not in ['jpg', 'jpeg', 'png', 'webp']:
        raise HTTPException(status_code=400, detail="Неподдерживаемый формат файла")
    filename = f"{uuid.uuid4()}.{ext}"
    upload_dir = "/opt/soho/uploads/products"
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(file.file.read())
    product.image_url = f"/uploads/products/{filename}"
    db.commit()
    return {"image_url": product.image_url}

# PUBLIC API для сайта и бота
@router.get("/public/products")
def get_public_products(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        MenuProduct, ProductCategory.name.label('category_name')
    ).join(ProductCategory, MenuProduct.category_id == ProductCategory.id
    ).filter(
        MenuProduct.is_active == True,
        MenuProduct.is_visible_on_site == True
    )
    if category_id:
        query = query.filter(MenuProduct.category_id == category_id)
    if search:
        query = query.filter(MenuProduct.name.ilike(f"%{search}%"))
    results = query.order_by(ProductCategory.sort_order, MenuProduct.name).all()
    products_by_category = {}
    for product, cat_name in results:
        if cat_name not in products_by_category:
            products_by_category[cat_name] = []
        products_by_category[cat_name].append({
            "id": product.id, "name": product.name, "sku": product.sku,
            "price": product.price, "image_url": product.image_url,
            "description": product.description, "weight_grams": product.weight_grams
        })
    return products_by_category

@router.get("/public/products/{product_id}")
def get_public_product_detail(product_id: int, db: Session = Depends(get_db)):
    product = db.query(MenuProduct).filter(
        MenuProduct.id == product_id,
        MenuProduct.is_active == True,
        MenuProduct.is_visible_on_site == True
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return {
        "id": product.id, "name": product.name, "sku": product.sku,
        "price": product.price, "image_url": product.image_url,
        "description": product.description, "weight_grams": product.weight_grams
    }

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
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

router = APIRouter(tags=["menu"])

# ============ КАТЕГОРИИ ИНГРЕДИЕНТОВ ============

class CatCreate(BaseModel):
    name: str
    description: Optional[str] = None

@router.get("/ingredient-categories")
def get_ing_cats(db: Session = Depends(get_db)):
    return db.query(IngredientCategory).order_by(IngredientCategory.name).all()

@router.post("/ingredient-categories")
def create_ing_cat(data: CatCreate, db: Session = Depends(get_db)):
    cat = IngredientCategory(**data.dict())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

@router.put("/ingredient-categories/{id}")
def update_ing_cat(id: int, data: dict, db: Session = Depends(get_db)):
    cat = db.query(IngredientCategory).filter(IngredientCategory.id == id).first()
    if not cat:
        raise HTTPException(404, "Category not found")
    
    if "name" in data:
        cat.name = data["name"]
    if "description" in data:
        cat.description = data["description"]
    if "is_visible_on_site" in data:
        cat.is_visible_on_site = data["is_visible_on_site"]
    if "is_visible_in_menu" in data:
        cat.is_visible_in_menu = data["is_visible_in_menu"]
    
    db.commit()
    db.refresh(cat)
    return cat

@router.delete("/ingredient-categories/{id}")
def delete_ing_cat(id: int, db: Session = Depends(get_db)):
    cat = db.query(IngredientCategory).filter(IngredientCategory.id == id).first()
    if cat:
        db.delete(cat)
        db.commit()
    return {"ok": True}

# ============ ЕДИНИЦЫ ИЗМЕРЕНИЯ ============

@router.get("/units")
def get_units(db: Session = Depends(get_db)):
    from ..models import Unit
    return db.query(Unit).all()


# ============ ИНГРЕДИЕНТЫ ============

@router.get("/ingredients")
def get_ingredients(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    from ..models import Ingredient, IngredientCategory
    query = db.query(Ingredient)
    
    if category_id:
        # Get category name by ID and filter by name
        cat = db.query(IngredientCategory).filter(IngredientCategory.id == category_id).first()
        if cat:
            query = query.filter(Ingredient.category == cat.name)
    
    if search:
        query = query.filter(Ingredient.name.ilike(f"%{search}%"))
    
    return query.order_by(Ingredient.name).all()


@router.post("/ingredients")
def create_ingredient(data: dict, db: Session = Depends(get_db)):
    from ..models import Ingredient, IngredientCategory, Unit
    
    # Get category name from ID
    category = None
    if data.get("category_id"):
        cat = db.query(IngredientCategory).filter(IngredientCategory.id == int(data["category_id"])).first()
        if cat:
            category = cat.name
    
    # Get unit from ID
    unit = "г"
    if data.get("unit_id"):
        u = db.query(Unit).filter(Unit.id == int(data["unit_id"])).first()
        if u:
            unit = u.abbreviation
    
    ing = Ingredient(
        name=data["name"],
        name_ru=data["name"],
        category=category,
        unit=unit,
        processing_loss_percent=data.get("processing_loss_percent", 0),
        storage_conditions=data.get("storage_conditions"),
        shelf_life_days=data.get("shelf_life_days"),
        cost_per_unit=data.get("cost_per_unit"),
        is_active=data.get("is_active", True)
    )
    db.add(ing)
    db.commit()
    db.refresh(ing)
    return {"id": ing.id, "name": ing.name}


@router.put("/ingredients/{id}")
def update_ingredient(id: int, data: dict, db: Session = Depends(get_db)):
    from ..models import Ingredient, IngredientCategory, Unit
    ing = db.query(Ingredient).filter(Ingredient.id == id).first()
    if not ing:
        raise HTTPException(404, "Not found")
    
    ing.name = data.get("name", ing.name)
    ing.name_ru = data.get("name", ing.name_ru)
    
    # Get category name from ID
    if "category_id" in data:
        if data["category_id"]:
            cat = db.query(IngredientCategory).filter(IngredientCategory.id == int(data["category_id"])).first()
            if cat:
                ing.category = cat.name
        else:
            ing.category = None
    
    # Get unit from ID
    if "unit_id" in data:
        if data["unit_id"]:
            u = db.query(Unit).filter(Unit.id == int(data["unit_id"])).first()
            if u:
                ing.unit = u.abbreviation
        else:
            ing.unit = "г"
    
    if "processing_loss_percent" in data:
        ing.processing_loss_percent = data["processing_loss_percent"]
    if "storage_conditions" in data:
        ing.storage_conditions = data["storage_conditions"]
    if "shelf_life_days" in data:
        ing.shelf_life_days = data["shelf_life_days"]
    if "is_active" in data:
        ing.is_active = data["is_active"]
    if "cost_per_unit" in data:
        ing.cost_per_unit = data["cost_per_unit"]
    
    db.commit()
    db.refresh(ing)
    return {"id": ing.id, "name": ing.name}


@router.delete("/ingredients/{id}")
def delete_ingredient(id: int, db: Session = Depends(get_db)):
    from ..models import Ingredient
    ing = db.query(Ingredient).filter(Ingredient.id == id).first()
    if ing:
        db.delete(ing)
        db.commit()
    return {"ok": True}


# ============ КАТЕГОРИИ ТОВАРОВ ============

@router.get("/categories")
def get_categories_public(db: Session = Depends(get_db)):
    """Публичный endpoint для клиентского меню"""
    cats = db.query(ProductCategory).filter(
        ProductCategory.is_active == True,
        ProductCategory.is_visible_on_site == True
    ).order_by(ProductCategory.sort_order).all()
    return [{"id": c.id, "name": c.name, "description": c.description, "sort_order": c.sort_order} for c in cats]


@router.get("/pwa/menu")
def get_pwa_menu(db: Session = Depends(get_db)):
    """Полное меню для PWA планшетного меню с иерархией категорий"""
    from ..models import Ingredient
    import logging
    logger = logging.getLogger(__name__)
    
    # Get all visible categories
    all_categories = db.query(ProductCategory).filter(
        ProductCategory.is_active == True,
        ProductCategory.is_visible_in_menu == True
    ).order_by(ProductCategory.sort_order).all()
    
    logger.info(f"Total categories in PWA menu: {len(all_categories)}")
    parent_cats = [c for c in all_categories if c.parent_id is None]
    child_cats = [c for c in all_categories if c.parent_id is not None]
    logger.info(f"Parent categories: {len(parent_cats)}, Child categories: {len(child_cats)}")
    
    # Build category tree - only parent categories at root level
    def build_category_tree(parent_id=None):
        result = []
        for cat in all_categories:
            # For root level (parent_id=None), show only parent categories (parent_id IS NULL)
            # For child levels, match the parent_id
            if parent_id is None:
                if cat.parent_id is not None:
                    continue  # Skip child categories at root level
            elif cat.parent_id != parent_id:
                continue
            
            # Get products for this category (only parent products, not variations)
            products = db.query(MenuProduct).filter(
                MenuProduct.category_id == cat.id,
                MenuProduct.is_active == True,
                MenuProduct.is_visible_in_menu == True,
                MenuProduct.parent_id == None  # Only parent products, not variations
            ).order_by(MenuProduct.sort_order, MenuProduct.name).all()
            
            products_data = []
            for p in products:
                # Get tech card composition
                tc = db.query(TechCard).filter(TechCard.product_id == p.id, TechCard.is_active == True).first()
                composition = []
                if tc:
                    items = db.query(TechCardItem).filter(TechCardItem.tech_card_id == tc.id).all()
                    for item in items:
                        if item.item_type == 'ingredient':
                            ing = db.query(Ingredient).filter(Ingredient.id == item.item_id).first()
                            if ing:
                                composition.append(ing.name)
                
                product_data = {
                    "id": p.id,
                    "name": p.name,
                    "name_ru": p.name,
                    "price": float(p.price),
                    "image_url": p.image_url or "/images/placeholder.jpg",
                    "description": p.description or "",
                    "composition": ", ".join(composition) if composition else "",
                    "weight": p.weight_grams,
                    "is_variable": p.is_variable,
                    "variations": []
                }
                
                # Add variations for variable products
                if p.is_variable:
                    variations = db.query(MenuProduct).filter(
                        MenuProduct.parent_id == p.id,
                        MenuProduct.is_active == True
                    ).order_by(MenuProduct.price).all()
                    
                    for var in variations:
                        product_data["variations"].append({
                            "id": var.id,
                            "name": var.name,
                            "price": float(var.price),
                            "sku": var.sku
                        })
                
                products_data.append(product_data)
            
            # Build category data
            cat_data = {
                "id": cat.id,
                "slug": f"cat-{cat.id}",
                "name": cat.name,
                "name_ru": cat.name,
                "products": products_data,
                "children": build_category_tree(cat.id)  # Recursive call for subcategories
            }
            
            # Only add category if it has products or children (for parent categories, children are enough)
            has_products = len(products_data) > 0
            has_children = len(cat_data["children"]) > 0
            has_children_with_products = any(len(child.get("products", [])) > 0 or len(child.get("children", [])) > 0 for child in cat_data["children"])
            
            # Debug logging for specific categories
            if cat.id in [32, 33]:
                logger.info(f"DEBUG Category {cat.name} (ID {cat.id}): parent_id={parent_id}, has_products={has_products}, has_children={has_children}, products_count={len(products_data)}")
            
            # For parent categories (root level), show if they have children
            # For child categories, show if they have products
            if parent_id is None:
                # Parent category: show if has children (even without products)
                if has_children or has_products:
                    result.append(cat_data)
            else:
                # Child category: show if has products or nested children
                if has_products or has_children_with_products:
                    if cat.id in [32, 33]:
                        logger.info(f"DEBUG Category {cat.name} ADDED to result")
                    result.append(cat_data)
                else:
                    if cat.id in [32, 33]:
                        logger.info(f"DEBUG Category {cat.name} SKIPPED (no products or children with products)")
        
        return result
    
    return build_category_tree()


@router.get("/public/menu")
def get_public_menu(db: Session = Depends(get_db)):
    """Полное меню для клиентского сайта - только дочерние категории (с parent_id)"""
    from ..models import Ingredient
    
    # Get only child categories (with parent_id) for website display
    # Parent categories are only for PWA menu organization
    # Sort by parent's sort_order first, then by child's sort_order
    from ..models import ProductCategory as ParentCat
    from sqlalchemy.orm import aliased
    
    ParentAlias = aliased(ProductCategory)
    categories = db.query(ProductCategory).join(
        ParentAlias, ProductCategory.parent_id == ParentAlias.id
    ).filter(
        ProductCategory.is_active == True,
        ProductCategory.parent_id != None,  # Only child categories
        ProductCategory.is_visible_on_site == True
    ).order_by(ParentAlias.sort_order, ProductCategory.sort_order).all()
    
    result = []
    
    for cat in categories:
        products = db.query(MenuProduct).filter(
            MenuProduct.category_id == cat.id,
            MenuProduct.is_active == True,
            MenuProduct.is_visible_on_site == True,
            MenuProduct.parent_id == None  # Only parent products, not variations
        ).order_by(MenuProduct.name).all()
        
        products_data = []
        for p in products:
            # Получаем техкарту для состава
            tc = db.query(TechCard).filter(TechCard.product_id == p.id, TechCard.is_active == True).first()
            composition = []
            if tc:
                items = db.query(TechCardItem).filter(TechCardItem.tech_card_id == tc.id).all()
                for item in items:
                    if item.item_type == 'ingredient':
                        ing = db.query(Ingredient).filter(Ingredient.id == item.item_id).first()
                        if ing:
                            composition.append(ing.name)
            
            # Build product data
            product_data = {
                "id": p.id,
                "name": p.name,
                "name_ru": p.name,
                "price": float(p.price),
                "image_url": p.image_url or "/images/placeholder.jpg",
                "description": p.description or "",
                "composition": ", ".join(composition) if composition else "",
                "weight": p.weight_grams,
                "is_variable": p.is_variable,
                "variations": []
            }
            
            # If variable product, add variations
            if p.is_variable:
                variations = db.query(MenuProduct).filter(
                    MenuProduct.parent_id == p.id,
                    MenuProduct.is_active == True
                ).order_by(MenuProduct.price).all()
                
                for var in variations:
                    product_data["variations"].append({
                        "id": var.id,
                        "name": var.name,
                        "price": float(var.price),
                        "sku": var.sku
                    })
            
            products_data.append(product_data)
        
        if products_data:  # Only add category if it has products
            result.append({
                "id": cat.id,
                "slug": f"cat-{cat.id}",
                "name": cat.name,
                "name_ru": cat.name,
                "products": products_data
            })
    
    return result


@router.get("/product-categories")
def get_prod_cats(parent_id: Optional[int] = None, include_all: bool = False, db: Session = Depends(get_db)):
    """Get product categories with optional parent filter"""
    query = db.query(ProductCategory)
    
    if parent_id is not None:
        query = query.filter(ProductCategory.parent_id == parent_id)
    elif not include_all:
        # Return only root categories (no parent) by default
        query = query.filter(ProductCategory.parent_id == None)
    
    return query.order_by(ProductCategory.sort_order).all()


@router.get("/product-categories/tree")
def get_prod_cats_tree(db: Session = Depends(get_db)):
    """Get full category tree with nested children"""
    def build_tree(parent_id=None):
        cats = db.query(ProductCategory).filter(
            ProductCategory.parent_id == parent_id,
            ProductCategory.is_active == True
        ).order_by(ProductCategory.sort_order).all()
        
        result = []
        for cat in cats:
            cat_data = {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "sort_order": cat.sort_order,
                "is_visible_on_site": cat.is_visible_on_site,
                "is_visible_in_menu": cat.is_visible_in_menu,
                "children": build_tree(cat.id)
            }
            result.append(cat_data)
        return result
    
    return build_tree()

@router.post("/product-categories")
def create_prod_cat(data: dict, db: Session = Depends(get_db)):
    cat = ProductCategory(
        name=data.get("name"),
        description=data.get("description"),
        parent_id=data.get("parent_id"),
        kitchen_id=data.get("kitchen_id"),
        sort_order=data.get("sort_order", 0),
        is_active=data.get("is_active", True),
        is_visible_on_site=data.get("is_visible_on_site", True),
        is_visible_in_menu=data.get("is_visible_in_menu", True)
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

@router.put("/product-categories/{id}")
def update_prod_cat(id: int, data: dict, db: Session = Depends(get_db)):
    cat = db.query(ProductCategory).filter(ProductCategory.id == id).first()
    if not cat:
        raise HTTPException(404, "Category not found")
    
    if "name" in data:
        cat.name = data["name"]
    if "description" in data:
        cat.description = data["description"]
    if "parent_id" in data:
        cat.parent_id = data["parent_id"]
    if "kitchen_id" in data:
        cat.kitchen_id = data["kitchen_id"]
    if "sort_order" in data:
        cat.sort_order = data["sort_order"]
    if "is_active" in data:
        cat.is_active = data["is_active"]
    if "is_visible_on_site" in data:
        cat.is_visible_on_site = data["is_visible_on_site"]
    if "is_visible_in_menu" in data:
        cat.is_visible_in_menu = data["is_visible_in_menu"]
    
    db.commit()
    db.refresh(cat)
    return cat

@router.delete("/product-categories/{id}")
def delete_prod_cat(id: int, db: Session = Depends(get_db)):
    cat = db.query(ProductCategory).filter(ProductCategory.id == id).first()
    if cat:
        db.delete(cat)
        db.commit()
    return {"ok": True}


class BatchSortOrder(BaseModel):
    items: List[dict]  # [{"id": 1, "sort_order": 10}, ...]

@router.post("/product-categories/reorder")
def reorder_product_categories(data: BatchSortOrder, db: Session = Depends(get_db)):
    """Batch update sort_order for multiple categories"""
    try:
        for item in data.items:
            cat_id = item.get("id")
            sort_order = item.get("sort_order")
            if cat_id is not None and sort_order is not None:
                cat = db.query(ProductCategory).filter(ProductCategory.id == cat_id).first()
                if cat:
                    cat.sort_order = sort_order
        db.commit()
        return {"ok": True, "updated": len(data.items)}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to reorder: {str(e)}")

# ============ ПОЛУФАБРИКАТЫ ============

@router.get("/semi-finished")
def get_semi(db: Session = Depends(get_db)):
    items = db.query(SemiFinishedProduct).all()
    result = []
    for sf in items:
        comp = db.query(SemiFinishedComposition).filter(
            SemiFinishedComposition.semi_finished_id == sf.id
        ).all()
        result.append({
            "id": sf.id,
            "name": sf.name,
            "description": sf.description,
            "unit": sf.unit,
            "department_id": sf.department_id,
            "preparation_time_minutes": sf.preparation_time_minutes,
            "is_active": sf.is_active,
            "composition": [{"item_type": c.item_type, "item_id": c.item_id, 
                           "quantity": c.quantity, "unit": c.unit} for c in comp]
        })
    return result

@router.post("/semi-finished")
def create_semi(data: dict, db: Session = Depends(get_db)):
    sf = SemiFinishedProduct(
        name=data["name"],
        description=data.get("description"),
        unit=data.get("unit"),
        department_id=data.get("department_id"),
        preparation_time_minutes=data.get("preparation_time_minutes"),
        is_active=data.get("is_active", True)
    )
    db.add(sf)
    db.commit()
    db.refresh(sf)
    
    for item in data.get("composition", []):
        comp = SemiFinishedComposition(
            semi_finished_id=sf.id,
            item_type=item["item_type"],
            item_id=item["item_id"],
            quantity=item["quantity"],
            unit=item.get("unit")
        )
        db.add(comp)
    db.commit()
    return {"id": sf.id}

@router.delete("/semi-finished/{id}")
def delete_semi(id: int, db: Session = Depends(get_db)):
    db.query(SemiFinishedComposition).filter(SemiFinishedComposition.semi_finished_id == id).delete()
    sf = db.query(SemiFinishedProduct).filter(SemiFinishedProduct.id == id).first()
    if sf:
        db.delete(sf)
        db.commit()
    return {"ok": True}

# ============ ТОВАРЫ ============

@router.get("/products")
def get_products(
    category_id: int = None,
    search: str = None,
    db: Session = Depends(get_db)
):
    # Build query
    query = db.query(MenuProduct).filter(
        (MenuProduct.parent_id == None) | (MenuProduct.is_variable == True)
    )
    
    # Filter by category
    if category_id:
        query = query.filter(MenuProduct.category_id == category_id)
    
    # Filter by search
    if search:
        query = query.filter(MenuProduct.name.ilike(f"%{search}%"))
    
    prods = query.order_by(MenuProduct.name).all()
    result = []
    for p in prods:
        cat = db.query(ProductCategory).filter(ProductCategory.id == p.category_id).first()
        dept = db.query(ProductionDepartment).filter(ProductionDepartment.id == p.department_id).first()
        
        # Get variations for variable products
        variations = []
        if p.is_variable:
            var_query = db.query(MenuProduct).filter(MenuProduct.parent_id == p.id, MenuProduct.is_active == True).all()
            for var in var_query:
                variations.append({
                    "id": var.id,
                    "name": var.name,
                    "price": float(var.price),
                    "sku": var.sku
                })
        
        result.append({
            "id": p.id, "name": p.name, "sku": p.sku, "barcode": p.barcode,
            "category_id": p.category_id, "category_name": cat.name if cat else None,
            "department_id": p.department_id, "department_name": dept.name if dept else None,
            "price": p.price, "cost_price": p.cost_price,
            "image_url": p.image_url, "description": p.description,
            "weight_grams": p.weight_grams,
            "is_visible_on_site": p.is_visible_on_site,
            "is_visible_in_menu": p.is_visible_in_menu,
            "is_active": p.is_active,
            "is_variable": p.is_variable,
            "sort_order": p.sort_order,
            "variations": variations
        })
    return result

def calculate_product_cost(product_id: int, db: Session):
    """Расчет себестоимости товара по техкарте"""
    from ..models import Ingredient
    
    tc = db.query(TechCard).filter(TechCard.product_id == product_id, TechCard.is_active == True).first()
    if not tc:
        return 0
    
    items = db.query(TechCardItem).filter(TechCardItem.tech_card_id == tc.id).all()
    total_cost = 0
    
    for item in items:
        if item.item_type == 'ingredient':
            ing = db.query(Ingredient).filter(Ingredient.id == item.item_id).first()
            if ing and ing.cost_per_unit:
                # Переводим стоимость в зависимости от единиц измерения
                quantity = float(item.quantity) if item.quantity else 0
                cost_per_unit = float(ing.cost_per_unit)
                
                # Учитываем потери при обработке
                loss_percent = float(ing.processing_loss_percent) if ing.processing_loss_percent else 0
                quantity_with_loss = quantity * (1 + loss_percent / 100)
                
                total_cost += quantity_with_loss * cost_per_unit
    
    return round(total_cost, 2)


# ============ ПОИСК ПРОДУКТОВ (должен быть до /products/{id}) ============

@router.get("/products/search")
def search_products(q: str = "", db: Session = Depends(get_db)):
    """Поиск продуктов для клиентского меню"""
    from ..models import Ingredient
    
    if not q or len(q) < 2:
        return []
    
    query = f"%{q}%"
    
    products = db.query(MenuProduct).filter(
        MenuProduct.is_active == True,
        MenuProduct.is_visible_on_site == True,
        MenuProduct.parent_id == None,  # Only parent products, not variations
        (MenuProduct.name.ilike(query) | 
         MenuProduct.description.ilike(query))
    ).limit(20).all()
    
    result = []
    for p in products:
        # Получаем техкарту для состава
        tc = db.query(TechCard).filter(TechCard.product_id == p.id, TechCard.is_active == True).first()
        composition = []
        if tc:
            items = db.query(TechCardItem).filter(TechCardItem.tech_card_id == tc.id).all()
            for item in items:
                if item.item_type == 'ingredient':
                    ing = db.query(Ingredient).filter(Ingredient.id == item.item_id).first()
                    if ing:
                        composition.append(ing.name)
        
        # Get variations (child products)
        variations = db.query(MenuProduct).filter(
            MenuProduct.parent_id == p.id,
            MenuProduct.is_active == True
        ).all()
        
        is_variable = len(variations) > 0
        
        # Build variations data
        variations_data = []
        for v in variations:
            variations_data.append({
                "id": v.id,
                "name": v.name,
                "price": float(v.price) if v.price else 0,
                "weight_grams": v.weight_grams
            })
        
        # Calculate price display
        if is_variable and variations_data:
            prices = [v["price"] for v in variations_data]
            min_price = min(prices)
            max_price = max(prices)
        else:
            min_price = max_price = float(p.price)
        
        result.append({
            "id": p.id,
            "name": p.name,
            "name_ru": p.name,
            "price": float(p.price),
            "min_price": min_price,
            "max_price": max_price,
            "is_variable": is_variable,
            "variations": variations_data,
            "image_url": p.image_url or "/images/placeholder.jpg",
            "description": p.description or "",
            "composition": ", ".join(composition) if composition else "",
            "weight": p.weight_grams
        })
    
    return result


# ============ ЭКСПОРТ / ИМПОРТ ТОВАРОВ (должен быть до /products/{id}) ============

@router.get("/products/export")
def export_products(db: Session = Depends(get_db)):
    """Экспорт всех товаров в CSV"""
    import csv
    import io
    
    products = db.query(MenuProduct).filter(MenuProduct.is_active == True).order_by(MenuProduct.name).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Заголовки
    writer.writerow([
        "id", "name", "sku", "barcode", "category_id", "category_name", "department_id",
        "price", "cost_price", "description", "weight_grams",
        "is_visible_on_site", "is_visible_in_menu", "is_active", "image_url"
    ])
    
    for p in products:
        cat = db.query(ProductCategory).filter(ProductCategory.id == p.category_id).first()
        writer.writerow([
            p.id,
            p.name,
            p.sku or "",
            p.barcode or "",
            p.category_id or "",
            cat.name if cat else "",
            p.department_id or "",
            p.price,
            p.cost_price,
            p.description or "",
            p.weight_grams or "",
            "1" if p.is_visible_on_site else "0",
            "1" if p.is_visible_in_menu else "0",
            "1" if p.is_active else "0",
            p.image_url or ""
        ])
    
    output.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"}
    )


@router.post("/products/import")
def import_products(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Импорт товаров из CSV"""
    import csv
    import io
    
    content = file.file.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))
    
    imported = 0
    updated = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):
        try:
            name = row.get("name", "").strip()
            if not name:
                continue
            
            # Ищем существующий товар по имени или SKU
            existing = None
            if row.get("sku"):
                existing = db.query(MenuProduct).filter(MenuProduct.sku == row.get("sku")).first()
            if not existing:
                existing = db.query(MenuProduct).filter(MenuProduct.name == name).first()
            
            # Получаем или создаем категорию
            category_id = None
            cat_name = row.get("category_name", "").strip()
            if cat_name:
                cat = db.query(ProductCategory).filter(ProductCategory.name == cat_name).first()
                if cat:
                    category_id = cat.id
                elif row.get("category_id"):
                    category_id = int(row.get("category_id")) if row.get("category_id").isdigit() else None
            
            data = {
                "name": name,
                "sku": row.get("sku", "").strip() or None,
                "barcode": row.get("barcode", "").strip() or None,
                "category_id": category_id,
                "department_id": int(row.get("department_id")) if row.get("department_id") and row.get("department_id").isdigit() else None,
                "price": float(row.get("price", 0) or 0),
                "cost_price": float(row.get("cost_price", 0) or 0),
                "description": row.get("description", "").strip() or None,
                "weight_grams": int(row.get("weight_grams")) if row.get("weight_grams") and row.get("weight_grams").isdigit() else None,
                "is_visible_on_site": row.get("is_visible_on_site", "1") == "1",
                "is_visible_in_menu": row.get("is_visible_in_menu", "1") == "1",
                "is_active": row.get("is_active", "1") == "1",
                "image_url": row.get("image_url", "").strip() or None
            }
            
            if existing:
                # Обновляем
                for key, value in data.items():
                    if value is not None:
                        setattr(existing, key, value)
                updated += 1
            else:
                # Создаем новый
                prod = MenuProduct(**data)
                db.add(prod)
                imported += 1
                
        except Exception as e:
            errors.append(f"Строка {row_num}: {str(e)}")
    
    db.commit()
    return {
        "imported": imported,
        "updated": updated,
        "errors": errors
    }


@router.get("/products/{id}")
def get_product(id: int, db: Session = Depends(get_db)):
    p = db.query(MenuProduct).filter(MenuProduct.id == id).first()
    if not p:
        raise HTTPException(404, "Not found")
    
    # Расчитываем себестоимость
    calculated_cost = calculate_product_cost(id, db)
    
    tc = db.query(TechCard).filter(TechCard.product_id == id, TechCard.is_active == True).first()
    tc_data = None
    if tc:
        items = db.query(TechCardItem).filter(TechCardItem.tech_card_id == tc.id).all()
        items_data = []
        for item in items:
            item_cost = 0
            if item.item_type == 'ingredient':
                from ..models import Ingredient
                ing = db.query(Ingredient).filter(Ingredient.id == item.item_id).first()
                if ing and ing.cost_per_unit:
                    quantity = float(item.quantity) if item.quantity else 0
                    cost_per_unit = float(ing.cost_per_unit)
                    loss_percent = float(ing.processing_loss_percent) if ing.processing_loss_percent else 0
                    quantity_with_loss = quantity * (1 + loss_percent / 100)
                    item_cost = round(quantity_with_loss * cost_per_unit, 2)
            
            items_data.append({
                "item_type": item.item_type, 
                "item_id": item.item_id,
                "quantity": item.quantity, 
                "unit": item.unit, 
                "is_optional": item.is_optional,
                "item_cost": item_cost
            })
        
        tc_data = {
            "id": tc.id,
            "cooking_time_minutes": tc.cooking_time_minutes,
            "preparation_method": tc.preparation_method,
            "calculated_cost": calculated_cost,
            "items": items_data
        }
    
    # Get variations for variable products
    variations = []
    if p.is_variable:
        var_query = db.query(MenuProduct).filter(MenuProduct.parent_id == p.id, MenuProduct.is_active == True).all()
        for var in var_query:
            variations.append({
                "id": var.id,
                "name": var.name,
                "price": float(var.price),
                "sku": var.sku
            })
    
    return {
        "id": p.id, "name": p.name, "sku": p.sku,
        "category_id": p.category_id,
        "department_id": p.department_id,
        "price": p.price, 
        "cost_price": calculated_cost if calculated_cost > 0 else p.cost_price,
        "description": p.description,
        "is_visible_on_site": p.is_visible_on_site,
        "is_visible_in_menu": p.is_visible_in_menu,
        "is_active": p.is_active,
        "is_variable": p.is_variable,
        "sort_order": p.sort_order,
        "variations": variations,
        "tech_card": tc_data
    }

@router.post("/products")
def create_product(data: dict, db: Session = Depends(get_db)):
    is_variable = data.get("is_variable", False)
    # Auto-detect variable product if variations provided
    if "variations" in data and len(data.get("variations", [])) > 0:
        is_variable = True
    
    p = MenuProduct(
        name=data["name"],
        sku=data.get("sku"),
        price=data.get("price", 0),
        description=data.get("description"),
        category_id=data.get("category_id"),
        department_id=data.get("department_id"),
        is_visible_on_site=data.get("is_visible_on_site", True),
        is_visible_in_menu=data.get("is_visible_in_menu", True),
        is_active=data.get("is_active", True),
        discounts_disabled=data.get("discounts_disabled", False),
        is_variable=is_variable
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    
    # Create variations for variable products
    if is_variable and "variations" in data:
        for var_data in data["variations"]:
            var = MenuProduct(
                name=var_data["name"],
                sku=var_data.get("sku"),
                price=var_data.get("price", 0),
                description=data.get("description"),  # Inherit from parent
                category_id=data.get("category_id"),  # Inherit from parent
                department_id=data.get("department_id"),  # Inherit from parent
                parent_id=p.id,
                is_visible_on_site=data.get("is_visible_on_site", True),
                is_visible_in_menu=data.get("is_visible_in_menu", True),
                is_active=data.get("is_active", True),
                is_variable=False
            )
            db.add(var)
            db.commit()
            db.refresh(var)
            
            # Create tech card for variation if provided
            if var_data.get("tech_card"):
                tc = TechCard(
                    product_id=var.id,
                    cooking_time_minutes=var_data["tech_card"].get("cooking_time_minutes"),
                    preparation_method=var_data["tech_card"].get("preparation_method")
                )
                db.add(tc)
                db.commit()
                db.refresh(tc)
                
                for item in var_data["tech_card"].get("items", []):
                    tci = TechCardItem(
                        tech_card_id=tc.id,
                        item_type=item["item_type"],
                        item_id=item["item_id"],
                        quantity=item["quantity"],
                        unit=item.get("unit"),
                        is_optional=item.get("is_optional", False)
                    )
                    db.add(tci)
                db.commit()
    
    # Create main tech card for simple products
    elif "tech_card" in data:
        tc = TechCard(
            product_id=p.id,
            cooking_time_minutes=data["tech_card"].get("cooking_time_minutes"),
            preparation_method=data["tech_card"].get("preparation_method")
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        
        for item in data["tech_card"].get("items", []):
            tci = TechCardItem(
                tech_card_id=tc.id,
                item_type=item["item_type"],
                item_id=item["item_id"],
                quantity=item["quantity"],
                unit=item.get("unit"),
                is_optional=item.get("is_optional", False)
            )
            db.add(tci)
        db.commit()
    
    return {"id": p.id}

@router.put("/products/{id}")
def update_product(id: int, data: dict, db: Session = Depends(get_db)):
    p = db.query(MenuProduct).filter(MenuProduct.id == id).first()
    if not p:
        raise HTTPException(404, "Товар не найден")
    
    p.name = data.get("name", p.name)
    p.sku = data.get("sku", p.sku)
    p.barcode = data.get("barcode", p.barcode)
    p.price = data.get("price", p.price)
    p.description = data.get("description", p.description)
    
    # Handle category_id - empty string should set to None
    if "category_id" in data:
        cat_id = data["category_id"]
        p.category_id = int(cat_id) if cat_id and str(cat_id).isdigit() else None
    
    # Handle department_id - empty string should set to None
    if "department_id" in data:
        dept_id = data["department_id"]
        p.department_id = int(dept_id) if dept_id and str(dept_id).isdigit() else None
    
    p.weight_grams = data.get("weight_grams", p.weight_grams)
    p.is_visible_on_site = data.get("is_visible_on_site", p.is_visible_on_site)
    p.is_visible_in_menu = data.get("is_visible_in_menu", p.is_visible_in_menu)
    p.is_active = data.get("is_active", p.is_active)
    p.discounts_disabled = data.get("discounts_disabled", p.discounts_disabled)
    
    # Handle sort_order
    if "sort_order" in data:
        p.sort_order = data["sort_order"]
    
    # Handle variable product mode
    if "is_variable" in data:
        p.is_variable = data["is_variable"]
    
    db.commit()
    db.refresh(p)
    
    # Update variations for variable products
    # Auto-enable variable mode if variations provided
    if "variations" in data and len(data.get("variations", [])) > 0:
        p.is_variable = True
        db.commit()
    
    if p.is_variable and "variations" in data:
        existing_var_ids = set()
        for var_data in data["variations"]:
            var_id = var_data.get("id")
            
            if var_id:
                # Update existing variation
                var = db.query(MenuProduct).filter(MenuProduct.id == var_id, MenuProduct.parent_id == p.id).first()
                if var:
                    var.name = var_data.get("name", var.name)
                    var.price = var_data.get("price", var.price)
                    var.sku = var_data.get("sku", var.sku)
                    var.is_active = True
                    db.commit()
                    existing_var_ids.add(var_id)
            else:
                # Create new variation
                var = MenuProduct(
                    name=var_data["name"],
                    sku=var_data.get("sku"),
                    price=var_data.get("price", 0),
                    description=p.description,
                    category_id=p.category_id,
                    department_id=p.department_id,
                    parent_id=p.id,
                    is_visible_on_site=p.is_visible_on_site,
                    is_visible_in_menu=p.is_visible_in_menu,
                    is_active=True,
                    is_variable=False
                )
                db.add(var)
                db.commit()
                db.refresh(var)
                existing_var_ids.add(var.id)
                var_id = var.id
            
            # Update tech card for variation if provided
            if var_id and var_data.get("tech_card"):
                # Deactivate old tech card
                old_tc = db.query(TechCard).filter(TechCard.product_id == var_id, TechCard.is_active == True).first()
                if old_tc:
                    old_tc.is_active = False
                    db.commit()
                
                # Create new tech card
                tc = TechCard(
                    product_id=var_id,
                    cooking_time_minutes=var_data["tech_card"].get("cooking_time_minutes"),
                    preparation_method=var_data["tech_card"].get("preparation_method")
                )
                db.add(tc)
                db.commit()
                db.refresh(tc)
                
                for item in var_data["tech_card"].get("items", []):
                    tci = TechCardItem(
                        tech_card_id=tc.id,
                        item_type=item["item_type"],
                        item_id=item["item_id"],
                        quantity=item["quantity"],
                        unit=item.get("unit"),
                        is_optional=item.get("is_optional", False)
                    )
                    db.add(tci)
                db.commit()
        
        # Remove variations not in the list (soft delete)
        all_vars = db.query(MenuProduct).filter(MenuProduct.parent_id == p.id).all()
        for var in all_vars:
            if var.id not in existing_var_ids:
                var.is_active = False
        db.commit()
    
    # Обновляем техкарту если передана (for simple products)
    elif "tech_card" in data:
        # Деактивируем старую техкарту
        old_tc = db.query(TechCard).filter(TechCard.product_id == id, TechCard.is_active == True).first()
        if old_tc:
            old_tc.is_active = False
            db.commit()
        
        # Создаем новую
        tc = TechCard(
            product_id=p.id,
            cooking_time_minutes=data["tech_card"].get("cooking_time_minutes"),
            preparation_method=data["tech_card"].get("preparation_method")
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        
        for item in data["tech_card"].get("items", []):
            tci = TechCardItem(
                tech_card_id=tc.id,
                item_type=item["item_type"],
                item_id=item["item_id"],
                quantity=item["quantity"],
                unit=item.get("unit"),
                is_optional=item.get("is_optional", False)
            )
            db.add(tci)
        db.commit()
        
        # Пересчитываем себестоимость
        cost = calculate_product_cost(p.id, db)
        p.cost_price = cost
        db.commit()
    
    return {"id": p.id, "cost_price": float(p.cost_price) if p.cost_price else 0}


@router.delete("/products/{id}")
def delete_product(id: int, db: Session = Depends(get_db)):
    """Полное удаление товара из базы данных"""
    from sqlalchemy import text
    
    p = db.query(MenuProduct).filter(MenuProduct.id == id).first()
    if not p:
        return {"ok": True}
    
    try:
        # Use raw SQL to delete in correct order
        # 1. Delete order items for this product and its children
        db.execute(text("DELETE FROM order_items WHERE product_id = :id OR variant_id = :id"), {"id": id})
        
        # 2. Delete tech card items for this product
        db.execute(text("""
            DELETE FROM tech_card_items 
            WHERE tech_card_id IN (SELECT id FROM tech_cards WHERE product_id = :id)
        """), {"id": id})
        
        # 3. Delete tech cards for this product
        db.execute(text("DELETE FROM tech_cards WHERE product_id = :id"), {"id": id})
        
        # 4. Handle child products (variations)
        child_ids = db.execute(text("SELECT id FROM menu_products WHERE parent_id = :id"), {"id": id}).fetchall()
        for (child_id,) in child_ids:
            # Delete order items for child
            db.execute(text("DELETE FROM order_items WHERE product_id = :id OR variant_id = :id"), {"id": child_id})
            # Delete tech card items for child
            db.execute(text("""
                DELETE FROM tech_card_items 
                WHERE tech_card_id IN (SELECT id FROM tech_cards WHERE product_id = :id)
            """), {"id": child_id})
            # Delete tech cards for child
            db.execute(text("DELETE FROM tech_cards WHERE product_id = :id"), {"id": child_id})
            # Delete child product
            db.execute(text("DELETE FROM menu_products WHERE id = :id"), {"id": child_id})
        
        # 5. Finally delete the parent product
        db.execute(text("DELETE FROM menu_products WHERE id = :id"), {"id": id})
        
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка удаления: {str(e)}")


# ============ ЭКСПОРТ / ИМПОРТ ИНГРЕДИЕНТОВ ============

@router.get("/ingredients/export")
def export_ingredients(db: Session = Depends(get_db)):
    """Экспорт всех ингредиентов в CSV"""
    from ..models import Ingredient
    import csv
    import io
    
    ingredients = db.query(Ingredient).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Заголовки
    writer.writerow([
        "id", "name", "category", "unit", "processing_loss_percent",
        "storage_conditions", "shelf_life_days", "is_active"
    ])
    
    for ing in ingredients:
        writer.writerow([
            ing.id,
            ing.name,
            ing.category or "",
            ing.unit or "г",
            ing.processing_loss_percent or 0,
            ing.storage_conditions or "",
            ing.shelf_life_days or "",
            "1" if ing.is_active else "0"
        ])
    
    output.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ingredients.csv"}
    )


@router.post("/ingredients/import")
def import_ingredients(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Импорт ингредиентов из CSV"""
    from ..models import Ingredient
    import csv
    import io
    
    content = file.file.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))
    
    imported = 0
    updated = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):
        try:
            name = row.get("name", "").strip()
            if not name:
                continue
            
            # Ищем существующий ингредиент по имени
            existing = db.query(Ingredient).filter(Ingredient.name == name).first()
            
            data = {
                "name": name,
                "category": row.get("category", "").strip() or None,
                "unit": row.get("unit", "г").strip(),
                "processing_loss_percent": float(row.get("processing_loss_percent", 0) or 0),
                "storage_conditions": row.get("storage_conditions", "").strip() or None,
                "shelf_life_days": int(row.get("shelf_life_days", 0) or 0) if row.get("shelf_life_days") else None,
                "is_active": row.get("is_active", "1") == "1"
            }
            
            if existing:
                # Обновляем
                for key, value in data.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                # Создаем новый
                ing = Ingredient(**data)
                db.add(ing)
                imported += 1
                
        except Exception as e:
            errors.append(f"Строка {row_num}: {str(e)}")
    
    db.commit()
    
    return {
        "imported": imported,
        "updated": updated,
        "errors": errors
    }


# ============ ЗАГРУЗКА ФОТО ТОВАРА ============

@router.post("/products/{product_id}/image")
def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Загрузка фото товара"""
    import os
    import uuid
    from pathlib import Path
    
    # Проверяем существование товара
    p = db.query(MenuProduct).filter(MenuProduct.id == product_id).first()
    if not p:
        raise HTTPException(404, "Товар не найден")
    
    # Проверяем расширение файла
    ext = file.filename.split('.')[-1].lower()
    if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
        raise HTTPException(400, "Неподдерживаемый формат файла. Разрешены: jpg, jpeg, png, webp, gif")
    
    # Создаем директорию если не существует
    upload_dir = Path("/opt/soho/uploads/products")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Генерируем уникальное имя файла
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = upload_dir / filename
    
    # Сохраняем файл
    with open(filepath, "wb") as f:
        f.write(file.file.read())
    
    # Обновляем URL в базе
    image_url = f"/uploads/products/{filename}"
    p.image_url = image_url
    db.commit()
    
    return {"image_url": image_url, "message": "Фото загружено"}


@router.delete("/products/{product_id}/image")
def delete_product_image(
    product_id: int,
    db: Session = Depends(get_db)
):
    """Удаление фото товара"""
    import os
    from pathlib import Path
    
    p = db.query(MenuProduct).filter(MenuProduct.id == product_id).first()
    if not p:
        raise HTTPException(404, "Товар не найден")
    
    # Удаляем файл если есть
    if p.image_url:
        filepath = Path("/opt/soho") / p.image_url.lstrip('/')
        if filepath.exists():
            os.remove(filepath)
        p.image_url = None
        db.commit()
    
    return {"message": "Фото удалено"}


# ============ КАТЕГОРИИ С КУХНЯМИ ============

@router.get("/categories/with-kitchens")
def get_categories_with_kitchens(db: Session = Depends(get_db)):
    """Get all product categories with kitchen assignment"""
    from ..models import ProductCategory, Kitchen

    cats = db.query(ProductCategory).order_by(ProductCategory.sort_order).all()
    result = []
    for cat in cats:
        result.append({
            "id": cat.id,
            "category_id": str(cat.id),
            "name": cat.name or f"Category {cat.id}",
            "description": cat.description,
            "kitchen_id": cat.kitchen_id,
            "sort_order": cat.sort_order,
            "is_active": cat.is_active
        })
    return result


@router.put("/categories/{category_id}/kitchen")
def assign_category_to_kitchen(
    category_id: str,
    data: dict,
    db: Session = Depends(get_db)
):
    """Assign or unassign a category to/from a kitchen"""
    from ..models import ProductCategory, Kitchen
    
    kitchen_id = data.get("kitchen_id")
    
    # Find category by id
    cat = db.query(ProductCategory).filter(ProductCategory.id == int(category_id)).first()
    
    if not cat:
        raise HTTPException(404, "Category not found")
    
    # Validate kitchen if provided
    if kitchen_id:
        kitchen = db.query(Kitchen).filter(Kitchen.kitchen_id == kitchen_id).first()
        if not kitchen:
            raise HTTPException(404, "Kitchen not found")
    
    cat.kitchen_id = kitchen_id
    db.commit()
    
    return {
        "status": "ok",
        "category_id": category_id,
        "kitchen_id": kitchen_id
    }


# ============ НАСТРОЙКИ PWA ============

from ..models import Settings

class PWASettings(BaseModel):
    bgColor: Optional[str] = "#0f0f1a"
    accentColor: Optional[str] = "#e94560"
    cardBgColor: Optional[str] = "#1a1a2e"
    textColor: Optional[str] = "#ffffff"
    textSecondaryColor: Optional[str] = "#a0a0b8"
    borderColor: Optional[str] = "#333333"
    bottomBarColor: Optional[str] = "#1a1a2e"
    heroImage: Optional[str] = None
    placeholderImage: Optional[str] = None

@router.get("/pwa/settings")
def get_pwa_settings(db: Session = Depends(get_db)):
    """Получить настройки PWA (CSS цвета и изображения)"""
    settings = db.query(Settings).filter(Settings.key == "pwa_config").first()
    if settings and settings.value:
        import json
        return json.loads(settings.value)
    return {
        "bgColor": "#0f0f1a",
        "accentColor": "#e94560",
        "cardBgColor": "#1a1a2e",
        "textColor": "#ffffff",
        "textSecondaryColor": "#a0a0b8",
        "borderColor": "#333333",
        "bottomBarColor": "#1a1a2e",
        "heroImage": None,
        "placeholderImage": None
    }

@router.post("/pwa/settings")
def save_pwa_settings(data: PWASettings, db: Session = Depends(get_db)):
    """Сохранить настройки PWA на сервере"""
    import json
    
    settings = db.query(Settings).filter(Settings.key == "pwa_config").first()
    if settings:
        settings.value = json.dumps(data.dict())
    else:
        settings = Settings(key="pwa_config", value=json.dumps(data.dict()))
        db.add(settings)
    
    db.commit()
    return {"status": "ok", "message": "Settings saved"}


@router.post("/products/generate-skus")
def generate_skus(db: Session = Depends(get_db)):
    """Генерация артикулов для товаров без SKU"""
    import re
    
    products = db.query(MenuProduct).filter(
        (MenuProduct.sku == None) | (MenuProduct.sku == '')
    ).all()
    
    updated = 0
    errors = []
    
    for product in products:
        try:
            # Generate SKU from name: transliterate and uppercase
            name = product.name or f"PRODUCT{product.id}"
            
            # Simple transliteration
            translit_map = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
                ' ': '_', '-': '_', '/': '_', '\\': '_', '.': '', ',': '',
                '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
                '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
            }
            
            # Transliterate
            sku_base = ''
            for char in name.lower()[:20]:  # First 20 chars
                if char in translit_map:
                    sku_base += translit_map[char]
                elif char.isalnum():
                    sku_base += char
            
            # Clean up
            sku_base = re.sub(r'_+', '_', sku_base).strip('_')
            
            # Ensure uniqueness by adding ID
            sku = f"{sku_base}_{product.id}".upper()
            
            # Check if SKU already exists
            existing = db.query(MenuProduct).filter(MenuProduct.sku == sku).first()
            if existing and existing.id != product.id:
                sku = f"{sku_base}_{product.id}_{uuid.uuid4().hex[:4]}".upper()
            
            product.sku = sku
            updated += 1
            
        except Exception as e:
            errors.append(f"Product {product.id}: {str(e)}")
    
    db.commit()
    
    return {
        "status": "ok",
        "updated": updated,
        "errors": errors
    }

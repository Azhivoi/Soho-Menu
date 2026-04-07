from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app import models

router = APIRouter()

# ========== INGREDIENTS ==========

class IngredientCreate(BaseModel):
    name_ru: str
    name_en: Optional[str] = None
    category: Optional[str] = None
    unit: str = "г"
    cost_per_unit: Optional[float] = 0
    supplier: Optional[str] = None
    shelf_life_days: Optional[int] = None

class IngredientResponse(BaseModel):
    id: int
    name_ru: str
    name_en: Optional[str]
    category: Optional[str]
    unit: str
    cost_per_unit: Optional[float]
    supplier: Optional[str]
    shelf_life_days: Optional[int]
    is_active: bool

@router.get("/ingredients", response_model=List[IngredientResponse])
async def list_ingredients(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all ingredients"""
    query = db.query(models.Ingredient)
    if category:
        query = query.filter(models.Ingredient.category == category)
    return query.all()

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

@router.post("/ingredients/import")
async def import_ingredients(
    ingredients: List[IngredientCreate],
    db: Session = Depends(get_db)
):
    """Import ingredients from CSV/Excel"""
    created = 0
    for data in ingredients:
        ingredient = models.Ingredient(**data.dict())
        db.add(ingredient)
        created += 1
    db.commit()
    return {"imported": created}

@router.get("/ingredients/export")
async def export_ingredients(db: Session = Depends(get_db)):
    """Export all ingredients"""
    ingredients = db.query(models.Ingredient).all()
    return [
        {
            "id": i.id,
            "name_ru": i.name_ru,
            "name_en": i.name_en,
            "category": i.category,
            "unit": i.unit,
            "cost_per_unit": float(i.cost_per_unit) if i.cost_per_unit else 0,
            "supplier": i.supplier,
            "shelf_life_days": i.shelf_life_days
        }
        for i in ingredients
    ]

# ========== SEMI-PRODUCTS ==========

class SemiProductCreate(BaseModel):
    name_ru: str
    name_en: Optional[str] = None
    category: Optional[str] = None
    output_weight: float
    cost_per_100g: Optional[float] = 0
    shelf_life_days: Optional[int] = None

@router.get("/semi-products")
async def list_semi_products(db: Session = Depends(get_db)):
    """List all semi-products"""
    return db.query(models.SemiProduct).all()

@router.post("/semi-products")
async def create_semi_product(
    data: SemiProductCreate,
    db: Session = Depends(get_db)
):
    """Create new semi-product"""
    semi = models.SemiProduct(**data.dict())
    db.add(semi)
    db.commit()
    db.refresh(semi)
    return {"id": semi.id, "status": "created"}

@router.post("/semi-products/import")
async def import_semi_products(
    items: List[SemiProductCreate],
    db: Session = Depends(get_db)
):
    """Import semi-products"""
    created = 0
    for data in items:
        semi = models.SemiProduct(**data.dict())
        db.add(semi)
        created += 1
    db.commit()
    return {"imported": created}

@router.get("/semi-products/export")
async def export_semi_products(db: Session = Depends(get_db)):
    """Export semi-products"""
    items = db.query(models.SemiProduct).all()
    return [
        {
            "id": i.id,
            "name_ru": i.name_ru,
            "category": i.category,
            "output_weight": i.output_weight,
            "cost_per_100g": float(i.cost_per_100g) if i.cost_per_100g else 0
        }
        for i in items
    ]

# ========== RECIPES ==========

class RecipeItemCreate(BaseModel):
    ingredient_id: Optional[int] = None
    semi_product_id: Optional[int] = None
    quantity: float
    unit: str
    cost: Optional[float] = 0

class RecipeCreate(BaseModel):
    product_id: int
    name: Optional[str] = None
    output_weight: float
    cooking_time_minutes: Optional[int] = None
    instructions: Optional[str] = None
    items: List[RecipeItemCreate]

@router.get("/recipes")
async def list_recipes(
    product_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """List recipes with items"""
    query = db.query(models.Recipe)
    if product_id:
        query = query.filter(models.Recipe.product_id == product_id)
    
    recipes = query.all()
    result = []
    for recipe in recipes:
        items = db.query(models.RecipeItem).filter(
            models.RecipeItem.recipe_id == recipe.id
        ).all()
        result.append({
            "id": recipe.id,
            "product_id": recipe.product_id,
            "name": recipe.name,
            "output_weight": recipe.output_weight,
            "cooking_time_minutes": recipe.cooking_time_minutes,
            "instructions": recipe.instructions,
            "items": [
                {
                    "id": item.id,
                    "ingredient_id": item.ingredient_id,
                    "semi_product_id": item.semi_product_id,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "cost": float(item.cost) if item.cost else 0
                }
                for item in items
            ]
        })
    return result

@router.post("/recipes")
async def create_recipe(
    data: RecipeCreate,
    db: Session = Depends(get_db)
):
    """Create new recipe with items"""
    # Create recipe
    recipe = models.Recipe(
        product_id=data.product_id,
        name=data.name,
        output_weight=data.output_weight,
        cooking_time_minutes=data.cooking_time_minutes,
        instructions=data.instructions
    )
    db.add(recipe)
    db.flush()
    
    # Add items
    for item_data in data.items:
        item = models.RecipeItem(
            recipe_id=recipe.id,
            **item_data.dict()
        )
        db.add(item)
    
    db.commit()
    return {"id": recipe.id, "status": "created"}

@router.post("/recipes/import")
async def import_recipes(
    recipes: List[RecipeCreate],
    db: Session = Depends(get_db)
):
    """Import recipes from file"""
    created = 0
    for data in recipes:
        recipe = models.Recipe(
            product_id=data.product_id,
            name=data.name,
            output_weight=data.output_weight,
            cooking_time_minutes=data.cooking_time_minutes,
            instructions=data.instructions
        )
        db.add(recipe)
        db.flush()
        
        for item_data in data.items:
            item = models.RecipeItem(
                recipe_id=recipe.id,
                **item_data.dict()
            )
            db.add(item)
        created += 1
    
    db.commit()
    return {"imported": created}

@router.get("/recipes/export")
async def export_recipes(db: Session = Depends(get_db)):
    """Export all recipes"""
    recipes = db.query(models.Recipe).all()
    result = []
    for recipe in recipes:
        items = db.query(models.RecipeItem).filter(
            models.RecipeItem.recipe_id == recipe.id
        ).all()
        result.append({
            "product_id": recipe.product_id,
            "name": recipe.name,
            "output_weight": recipe.output_weight,
            "cooking_time_minutes": recipe.cooking_time_minutes,
            "instructions": recipe.instructions,
            "items": [
                {
                    "ingredient_id": item.ingredient_id,
                    "semi_product_id": item.semi_product_id,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "cost": float(item.cost) if item.cost else 0
                }
                for item in items
            ]
        })
    return result

# Calculate recipe cost
@router.get("/recipes/{recipe_id}/cost")
async def calculate_recipe_cost(
    recipe_id: int,
    db: Session = Depends(get_db)
):
    """Calculate total cost of recipe"""
    items = db.query(models.RecipeItem).filter(
        models.RecipeItem.recipe_id == recipe_id
    ).all()
    
    total_cost = 0
    for item in items:
        if item.ingredient_id:
            ingredient = db.query(models.Ingredient).get(item.ingredient_id)
            if ingredient and ingredient.cost_per_unit:
                total_cost += float(item.quantity) * float(ingredient.cost_per_unit)
        elif item.semi_product_id:
            semi = db.query(models.SemiProduct).get(item.semi_product_id)
            if semi and semi.cost_per_100g:
                quantity_100g = float(item.quantity) / 100
                total_cost += quantity_100g * float(semi.cost_per_100g)
    
    return {
        "recipe_id": recipe_id,
        "total_cost": round(total_cost, 2)
    }

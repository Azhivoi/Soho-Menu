"""
Content Management API for SOHO Cafe
Handles pages, SEO settings, and content
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import json
from datetime import datetime

from ..database import get_db
from .. import models

router = APIRouter(tags=["content"])

# Pydantic models
class PageContent(BaseModel):
    id: str
    title: str
    slug: str
    h1: Optional[str] = ""
    content: Optional[str] = ""
    metaTitle: Optional[str] = ""
    metaDescription: Optional[str] = ""
    metaKeywords: Optional[str] = ""
    published: bool = True
    inMenu: bool = True
    indexed: bool = True
    template: Optional[str] = "default"
    classes: Optional[str] = ""
    script: Optional[str] = ""
    updatedAt: Optional[str] = None

class PageListItem(BaseModel):
    id: str
    title: str
    slug: str
    published: bool
    inMenu: bool
    updatedAt: Optional[str] = None

# Get page content
@router.get("/pages/{page_id}")
async def get_page(page_id: str, db: Session = Depends(get_db)):
    """Get page content by ID"""
    page = db.query(models.Config).filter(
        models.Config.key == f'page_{page_id}'
    ).first()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    try:
        data = json.loads(page.value)
        return data
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid page data")

# Save page content
@router.post("/pages")
async def save_page(page: PageContent, db: Session = Depends(get_db)):
    """Save or update page content"""
    
    # Prepare data
    data = page.dict()
    data['updatedAt'] = datetime.utcnow().isoformat()
    
    # Check if page exists
    existing = db.query(models.Config).filter(
        models.Config.key == f'page_{page.id}'
    ).first()
    
    if existing:
        # Update existing
        existing.value = json.dumps(data)
        existing.type = 'json'
    else:
        # Create new
        new_page = models.Config(
            key=f'page_{page.id}',
            value=json.dumps(data),
            type='json'
        )
        db.add(new_page)
    
    db.commit()
    return {"status": "ok", "message": "Page saved successfully"}

# List all pages
@router.get("/pages", response_model=List[PageListItem])
async def list_pages(db: Session = Depends(get_db)):
    """List all pages"""
    pages = db.query(models.Config).filter(
        models.Config.key.like('page_%')
    ).all()
    
    result = []
    for page in pages:
        try:
            data = json.loads(page.value)
            result.append({
                'id': data.get('id', page.key.replace('page_', '')),
                'title': data.get('title', 'Untitled'),
                'slug': data.get('slug', ''),
                'published': data.get('published', True),
                'inMenu': data.get('inMenu', True),
                'updatedAt': data.get('updatedAt')
            })
        except json.JSONDecodeError:
            continue
    
    return result

# Delete page
@router.delete("/pages/{page_id}")
async def delete_page(page_id: str, db: Session = Depends(get_db)):
    """Delete page by ID"""
    page = db.query(models.Config).filter(
        models.Config.key == f'page_{page_id}'
    ).first()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    db.delete(page)
    db.commit()
    return {"status": "ok", "message": "Page deleted successfully"}

# Get page by slug (for frontend)
@router.get("/page-by-slug/{slug}")
async def get_page_by_slug(slug: str, db: Session = Depends(get_db)):
    """Get page by slug (for frontend rendering)"""
    pages = db.query(models.Config).filter(
        models.Config.key.like('page_%')
    ).all()
    
    for page in pages:
        try:
            data = json.loads(page.value)
            if data.get('slug') == slug and data.get('published'):
                return data
        except json.JSONDecodeError:
            continue
    
    raise HTTPException(status_code=404, detail="Page not found")

# Get site settings
@router.get("/site-settings")
async def get_site_settings(db: Session = Depends(get_db)):
    """Get global site settings"""
    settings = db.query(models.Config).filter(
        models.Config.key == 'site_settings'
    ).first()
    
    if settings:
        try:
            return json.loads(settings.value)
        except json.JSONDecodeError:
            pass
    
    # Return defaults
    return {
        'siteName': 'SOHO Cafe',
        'siteDescription': 'Доставка еды в Минске',
        'contactPhone': '+375 (29) 116-77-55',
        'contactEmail': 'info@soho.by',
        'address': 'г. Минск',
        'socialLinks': {}
    }

# Save site settings
@router.post("/site-settings")
async def save_site_settings(settings: dict, db: Session = Depends(get_db)):
    """Save global site settings"""
    
    existing = db.query(models.Config).filter(
        models.Config.key == 'site_settings'
    ).first()
    
    if existing:
        existing.value = json.dumps(settings)
        existing.type = 'json'
    else:
        new_settings = models.Config(
            key='site_settings',
            value=json.dumps(settings),
            type='json'
        )
        db.add(new_settings)
    
    db.commit()
    return {"status": "ok", "message": "Settings saved successfully"}

# Upload favicon
@router.post("/upload-favicon")
async def upload_favicon(
    file: UploadFile = File(...),
    type: str = "favicon",
    db: Session = Depends(get_db)
):
    """Upload favicon or Apple Touch Icon"""
    import os
    import shutil
    from fastapi import UploadFile
    
    # Validate file type
    allowed_types = ['image/x-icon', 'image/vnd.microsoft.icon', 'image/png', 'image/jpeg']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Use .ico, .png or .jpg")
    
    # Create uploads directory if not exists
    upload_dir = "/opt/soho/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Determine filename based on type
    if type == "apple-icon":
        filename = "icon-192x192.png"
    else:
        filename = "favicon.ico"
    
    filepath = os.path.join(upload_dir, filename)
    
    # Save file
    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "status": "ok",
            "url": f"/uploads/{filename}",
            "message": f"{'Apple Touch Icon' if type == 'apple-icon' else 'Favicon'} uploaded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")


# Custom field model
class CustomField(BaseModel):
    name: str
    value: str
    type: Optional[str] = "text"
    url: Optional[str] = None

# Promo page content model
class PromoContent(BaseModel):
    logo: Optional[str] = "/uploads/logo.png"
    title: Optional[str] = "Кафе и Доставка Soho.By"
    description: Optional[str] = "Выбирайте: сайт или приложение! Посетите наш Instagram"
    app_url: Optional[str] = "https://foodpicasso.com/x/2307x621"
    site_url: Optional[str] = "https://soho.by/"
    instagram_url: Optional[str] = "https://www.instagram.com/cafe_soho.by"
    custom_css: Optional[str] = ""
    custom_fields: Optional[List[CustomField]] = []

# Get promo page content
@router.get("/promo")
async def get_promo_content(db: Session = Depends(get_db)):
    """Get promo page content"""
    config = db.query(models.Config).filter(
        models.Config.key == 'promo_content'
    ).first()
    
    if config and config.value:
        return json.loads(config.value)
    
    # Return defaults
    return PromoContent().dict()

# Update promo page content
@router.put("/promo")
async def update_promo_content(data: PromoContent, db: Session = Depends(get_db)):
    """Update promo page content"""
    config = db.query(models.Config).filter(
        models.Config.key == 'promo_content'
    ).first()
    
    if config:
        config.value = json.dumps(data.dict())
        config.type = 'json'
    else:
        config = models.Config(
            key='promo_content',
            value=json.dumps(data.dict()),
            type='json'
        )
        db.add(config)
    
    db.commit()
    return {"status": "ok", "data": data.dict()}


# SEO Settings Models
class MainPageSEO(BaseModel):
    title: Optional[str] = "Soho.By - Кафе и Доставка"
    description: Optional[str] = ""
    keywords: Optional[str] = ""

class GlobalSEO(BaseModel):
    site_name: Optional[str] = "Soho.By"
    city: Optional[str] = ""
    region: Optional[str] = ""
    address: Optional[str] = ""
    phone: Optional[str] = ""

# Get SEO settings
@router.get("/seo")
async def get_seo_settings(db: Session = Depends(get_db)):
    """Get SEO settings"""
    config = db.query(models.Config).filter(
        models.Config.key == 'seo_settings'
    ).first()
    
    if config and config.value:
        return json.loads(config.value)
    
    # Return defaults
    return {
        "main": {
            "title": "Soho.By - Кафе и Доставка",
            "description": "Закажите вкусную еду с доставкой. Суши, пицца, бургеры и многое другое.",
            "keywords": "доставка еды, кафе, суши, пицца, бургеры"
        },
        "global": {
            "site_name": "Soho.By",
            "city": "",
            "region": "",
            "address": "",
            "phone": ""
        }
    }

# Update SEO settings
@router.put("/seo")
async def update_seo_settings(data: dict, db: Session = Depends(get_db)):
    """Update SEO settings"""
    import json
    
    # Get existing settings
    config = db.query(models.Config).filter(
        models.Config.key == 'seo_settings'
    ).first()
    
    if config and config.value:
        existing = json.loads(config.value)
    else:
        existing = {
            "main": {"title": "", "description": "", "keywords": ""},
            "global": {"site_name": "", "city": "", "region": "", "address": "", "phone": ""}
        }
    
    # Merge new data
    if "main" in data:
        existing["main"].update(data["main"])
    if "global" in data:
        existing["global"].update(data["global"])
    
    if config:
        config.value = json.dumps(existing)
        config.type = 'json'
    else:
        config = models.Config(
            key='seo_settings',
            value=json.dumps(existing),
            type='json'
        )
        db.add(config)
    
    db.commit()
    return {"status": "ok", "data": existing}

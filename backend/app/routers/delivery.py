"""
Delivery settings and zones API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict
from app.database import get_db
from app import models
import requests
import math

router = APIRouter(prefix="/delivery", tags=["delivery"])

class DeliverySettingsResponse(BaseModel):
    min_order_free_delivery: float
    default_delivery_fee: float
    max_delivery_distance: float

class DeliveryZoneCreate(BaseModel):
    name: str
    fee: float = 5.0
    min_order: float = 0.0
    free_delivery_from: Optional[float] = None
    coordinates: List[List[float]] = []  # [[lat, lon], ...]
    color: str = "#e94560"

class DeliveryZoneResponse(DeliveryZoneCreate):
    id: int
    is_active: bool

@router.get("/settings", response_model=DeliverySettingsResponse)
async def get_delivery_settings(db: Session = Depends(get_db)):
    """Get delivery settings"""
    settings = db.query(models.DeliverySettings).first()
    if not settings:
        # Create default
        settings = models.DeliverySettings()
        db.add(settings)
        db.commit()
    return settings

@router.put("/settings")
async def update_delivery_settings(
    min_order_free_delivery: float,
    default_delivery_fee: float,
    max_delivery_distance: float = 10.0,
    yandex_api_key: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update delivery settings"""
    settings = db.query(models.DeliverySettings).first()
    if not settings:
        settings = models.DeliverySettings()
        db.add(settings)
    
    settings.min_order_free_delivery = min_order_free_delivery
    settings.default_delivery_fee = default_delivery_fee
    settings.max_delivery_distance = max_delivery_distance
    if yandex_api_key:
        settings.yandex_api_key = yandex_api_key
    
    db.commit()
    return {"status": "updated"}

@router.get("/zones", response_model=List[DeliveryZoneResponse])
async def get_delivery_zones(db: Session = Depends(get_db)):
    """Get all delivery zones"""
    zones = db.query(models.DeliveryZone).filter(
        models.DeliveryZone.is_active == True
    ).order_by(models.DeliveryZone.sort_order).all()
    return zones

@router.post("/zones", response_model=DeliveryZoneResponse)
async def create_zone(zone: DeliveryZoneCreate, db: Session = Depends(get_db)):
    """Create delivery zone"""
    db_zone = models.DeliveryZone(**zone.dict())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    return db_zone

@router.put("/zones/{zone_id}", response_model=DeliveryZoneResponse)
async def update_zone(zone_id: int, zone: DeliveryZoneCreate, db: Session = Depends(get_db)):
    """Update delivery zone"""
    db_zone = db.query(models.DeliveryZone).filter(models.DeliveryZone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(404, "Zone not found")
    
    for k, v in zone.dict().items():
        setattr(db_zone, k, v)
    
    db.commit()
    return db_zone

@router.delete("/zones/{zone_id}")
async def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    """Delete delivery zone (soft)"""
    db_zone = db.query(models.DeliveryZone).filter(models.DeliveryZone.id == zone_id).first()
    if db_zone:
        db_zone.is_active = False
        db.commit()
    return {"status": "deleted"}

@router.post("/calculate")
async def calculate_delivery(
    address: str,
    order_amount: float = 0,
    db: Session = Depends(get_db)
):
    """
    Calculate delivery fee for address
    Uses Yandex Maps API if key is configured, otherwise returns default
    """
    settings = db.query(models.DeliverySettings).first()
    if not settings:
        settings = models.DeliverySettings()
    
    # Check for free delivery
    if order_amount >= settings.min_order_free_delivery:
        return {
            "fee": 0,
            "free_delivery": True,
            "min_order_for_free": settings.min_order_free_delivery,
            "message": f"Бесплатная доставка от {settings.min_order_free_delivery} BYN"
        }
    
    # If no API key — return default
    if not settings.yandex_api_key:
        return {
            "fee": settings.default_delivery_fee,
            "free_delivery": False,
            "min_order_for_free": settings.min_order_free_delivery,
            "message": f"Доставка {settings.default_delivery_fee} BYN, бесплатно от {settings.min_order_free_delivery} BYN"
        }
    
    # TODO: Implement Yandex Maps geocoding and distance calculation
    # For now return default with message
    return {
        "fee": settings.default_delivery_fee,
        "free_delivery": False,
        "min_order_for_free": settings.min_order_free_delivery,
        "message": "Расчёт по карте в разработке"
    }

@router.post("/check-address")
async def check_address_in_zone(
    lat: float,
    lon: float,
    db: Session = Depends(get_db)
):
    """Check if coordinates are in any delivery zone"""
    zones = db.query(models.DeliveryZone).filter(
        models.DeliveryZone.is_active == True
    ).all()
    
    for zone in zones:
        if zone.coordinates and is_point_in_polygon(lat, lon, zone.coordinates):
            return {
                "in_zone": True,
                "zone_id": zone.id,
                "zone_name": zone.name,
                "fee": zone.fee,
                "free_delivery_from": zone.free_delivery_from
            }
    
    return {
        "in_zone": False,
        "message": "Адрес вне зоны доставки"
    }

def is_point_in_polygon(lat, lon, polygon):
    """Ray casting algorithm to check if point is in polygon"""
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if lon > min(p1y, p2y):
            if lon <= max(p1y, p2y):
                if lat <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (lon - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lat <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside

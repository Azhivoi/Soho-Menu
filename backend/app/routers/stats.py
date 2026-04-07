from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from typing import Optional, List
from datetime import datetime, timedelta

from app.database import get_db
from app import models

router = APIRouter()

@router.get("/abc-analysis")
async def get_abc_analysis(
    period: str = 'month',
    db: Session = Depends(get_db)
):
    """ABC analysis of products by revenue"""
    
    # Calculate period start
    now = datetime.now()
    if period == 'week':
        start = now - timedelta(days=7)
    elif period == 'month':
        start = now - timedelta(days=30)
    elif period == 'quarter':
        start = now - timedelta(days=90)
    elif period == 'year':
        start = now - timedelta(days=365)
    else:
        start = now - timedelta(days=30)
    
    # Get product sales data
    product_sales = db.query(
        models.OrderItem.product_id,
        models.Product.name_ru,
        models.Category.name_ru.label('category_name'),
        func.sum(models.OrderItem.quantity).label('quantity_sold'),
        func.sum(models.OrderItem.total_price).label('revenue')
    ).join(
        models.Order, models.OrderItem.order_id == models.Order.id
    ).join(
        models.Product, models.OrderItem.product_id == models.Product.id
    ).join(
        models.Category, models.Product.category_id == models.Category.id
    ).filter(
        models.Order.created_at >= start,
        models.Order.status != 'cancelled'
    ).group_by(
        models.OrderItem.product_id,
        models.Product.name_ru,
        models.Category.name_ru
    ).order_by(func.sum(models.OrderItem.total_price).desc()).all()
    
    # Calculate total revenue
    total_revenue = sum(float(s.revenue) for s in product_sales)
    
    # Assign ABC groups
    cumulative = 0
    result = []
    
    for i, product in enumerate(product_sales):
        revenue = float(product.revenue)
        cumulative += revenue
        percentage = (cumulative / total_revenue) * 100 if total_revenue > 0 else 0
        
        # ABC classification
        if percentage <= 80:
            group = 'A'
        elif percentage <= 95:
            group = 'B'
        else:
            group = 'C'
        
        result.append({
            'rank': i + 1,
            'product_id': product.product_id,
            'name': product.name_ru,
            'category': product.category_name,
            'quantity_sold': int(product.quantity_sold),
            'revenue': round(revenue, 2),
            'share_percent': round((revenue / total_revenue) * 100, 1),
            'cumulative_percent': round(percentage, 1),
            'group': group
        })
    
    # Summary by group
    group_a = [p for p in result if p['group'] == 'A']
    group_b = [p for p in result if p['group'] == 'B']
    group_c = [p for p in result if p['group'] == 'C']
    
    return {
        'period': period,
        'total_revenue': round(total_revenue, 2),
        'total_products': len(result),
        'groups': {
            'A': {
                'count': len(group_a),
                'revenue': round(sum(p['revenue'] for p in group_a), 2),
                'percentage': round((len(group_a) / len(result)) * 100, 1) if result else 0
            },
            'B': {
                'count': len(group_b),
                'revenue': round(sum(p['revenue'] for p in group_b), 2),
                'percentage': round((len(group_b) / len(result)) * 100, 1) if result else 0
            },
            'C': {
                'count': len(group_c),
                'revenue': round(sum(p['revenue'] for p in group_c), 2),
                'percentage': round((len(group_c) / len(result)) * 100, 1) if result else 0
            }
        },
        'products': result
    }

@router.get("/customers")
async def get_customers_stats(
    min_orders: Optional[int] = None,
    max_orders: Optional[int] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get customers with filters"""
    
    # Base query
    query = db.query(
        models.Customer,
        func.count(models.Order.id).label('orders_count'),
        func.sum(models.Order.total_amount).label('total_amount'),
        func.max(models.Order.created_at).label('last_order'),
        func.avg(models.Order.total_amount).label('avg_check')
    ).join(
        models.Order, models.Customer.id == models.Order.customer_id
    ).group_by(models.Customer.id)
    
    # Apply filters
    if date_from:
        query = query.filter(models.Order.created_at >= date_from)
    if date_to:
        query = query.filter(models.Order.created_at <= date_to)
    
    # Having filters
    if min_orders:
        query = query.having(func.count(models.Order.id) >= min_orders)
    if max_orders:
        query = query.having(func.count(models.Order.id) <= max_orders)
    if min_amount:
        query = query.having(func.sum(models.Order.total_amount) >= min_amount)
    if max_amount:
        query = query.having(func.sum(models.Order.total_amount) <= max_amount)
    
    results = query.order_by(func.sum(models.Order.total_amount).desc()).limit(limit).all()
    
    return [
        {
            'id': r.Customer.id,
            'name': r.Customer.name or 'Гость',
            'phone': r.Customer.phone or '—',
            'telegram_id': r.Customer.telegram_id,
            'orders_count': r.orders_count,
            'total_amount': round(float(r.total_amount), 2) if r.total_amount else 0,
            'avg_check': round(float(r.avg_check), 2) if r.avg_check else 0,
            'last_order': r.last_order.isoformat() if r.last_order else None,
            'status': 'VIP' if r.orders_count >= 20 else ('Regular' if r.orders_count >= 5 else 'New')
        }
        for r in results
    ]

@router.get("/payment-methods")
async def get_payment_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get payment method statistics"""
    
    query = db.query(
        models.Order.payment_type,
        func.count(models.Order.id).label('count'),
        func.sum(models.Order.total_amount).label('amount')
    ).filter(models.Order.status != 'cancelled')
    
    if date_from:
        query = query.filter(models.Order.created_at >= date_from)
    if date_to:
        query = query.filter(models.Order.created_at <= date_to)
    
    results = query.group_by(models.Order.payment_type).all()
    
    total = sum(r.count for r in results)
    
    return [
        {
            'method': r.payment_type,
            'count': r.count,
            'amount': round(float(r.amount), 2) if r.amount else 0,
            'percentage': round((r.count / total) * 100, 1) if total > 0 else 0
        }
        for r in results
    ]

@router.get("/order-types")
async def get_order_type_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get order type statistics (delivery, pickup, dine-in)"""
    
    query = db.query(
        models.Order.order_type,
        func.count(models.Order.id).label('count'),
        func.sum(models.Order.total_amount).label('amount')
    ).filter(models.Order.status != 'cancelled')
    
    if date_from:
        query = query.filter(models.Order.created_at >= date_from)
    if date_to:
        query = query.filter(models.Order.created_at <= date_to)
    
    results = query.group_by(models.Order.order_type).all()
    
    return [
        {
            'type': r.order_type,
            'count': r.count,
            'amount': round(float(r.amount), 2) if r.amount else 0
        }
        for r in results
    ]

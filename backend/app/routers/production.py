from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app import models

router = APIRouter()

# ========== PRODUCTION DEPARTMENTS ==========

class DepartmentCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    printer_ip: Optional[str] = None
    printer_port: int = 9100
    paper_width: int = 80

@router.get("/departments")
async def list_departments(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """List all production departments"""
    query = db.query(models.ProductionDepartment)
    if active_only:
        query = query.filter(models.ProductionDepartment.is_active == True)
    return query.order_by(models.ProductionDepartment.sort_order).all()

@router.post("/departments")
async def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db)
):
    """Create new department"""
    dept = models.ProductionDepartment(**data.dict())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return {"id": dept.id, "status": "created"}

@router.put("/departments/{dept_id}")
async def update_department(
    dept_id: int,
    data: DepartmentCreate,
    db: Session = Depends(get_db)
):
    """Update department"""
    dept = db.query(models.ProductionDepartment).get(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    
    for key, value in data.dict().items():
        setattr(dept, key, value)
    
    db.commit()
    return {"status": "updated"}

# ========== PRODUCT-DEPARTMENT LINKS ==========

@router.get("/products/{product_id}/departments")
async def get_product_departments(
    product_id: int,
    db: Session = Depends(get_db)
):
    """Get departments for product"""
    links = db.query(models.ProductDepartment).filter(
        models.ProductDepartment.product_id == product_id
    ).all()
    
    result = []
    for link in links:
        dept = db.query(models.ProductionDepartment).get(link.department_id)
        if dept:
            result.append({
                "department_id": dept.id,
                "department_name": dept.name,
                "department_code": dept.code,
                "is_primary": link.is_primary
            })
    return result

@router.post("/products/{product_id}/departments")
async def set_product_departments(
    product_id: int,
    department_ids: List[int],
    db: Session = Depends(get_db)
):
    """Set departments for product"""
    # Remove old links
    db.query(models.ProductDepartment).filter(
        models.ProductDepartment.product_id == product_id
    ).delete()
    
    # Add new links
    for i, dept_id in enumerate(department_ids):
        link = models.ProductDepartment(
            product_id=product_id,
            department_id=dept_id,
            is_primary=(i == 0)  # First is primary
        )
        db.add(link)
    
    db.commit()
    return {"status": "updated", "departments": len(department_ids)}

# ========== KITCHEN ORDERS (TICKETS) ==========

class KitchenOrderCreate(BaseModel):
    main_order_id: int
    department_id: int
    items: List[dict]

@router.post("/kitchen-orders/create")
async def create_kitchen_orders(
    main_order_id: int,
    db: Session = Depends(get_db)
):
    """Create kitchen orders from main order, split by departments"""
    main_order = db.query(models.Order).get(main_order_id)
    if not main_order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get order items with their departments
    kitchen_orders_created = []
    
    # Group items by department
    dept_items = {}
    
    for item in main_order.items:
        # Get product departments
        product_depts = db.query(models.ProductDepartment).filter(
            models.ProductDepartment.product_id == item.product_id
        ).all()
        
        if not product_depts:
            # Default to first department if not set
            default_dept = db.query(models.ProductionDepartment).filter(
                models.ProductionDepartment.is_active == True
            ).first()
            if default_dept:
                product_depts = [default_dept]
        
        for pd in product_depts:
            if pd.department_id not in dept_items:
                dept_items[pd.department_id] = []
            
            dept_items[pd.department_id].append({
                "product_id": item.product_id,
                "variant_id": item.variant_id,
                "quantity": item.quantity,
                "notes": ""
            })
    
    # Create kitchen order for each department
    for dept_id, items in dept_items.items():
        dept = db.query(models.ProductionDepartment).get(dept_id)
        if not dept or not dept.is_active:
            continue
        
        # Generate kitchen order number
        last_ko = db.query(models.KitchenOrder).order_by(
            models.KitchenOrder.id.desc()
        ).first()
        ko_number = f"K{(last_ko.id + 1) if last_ko else 1:04d}"
        
        kitchen_order = models.KitchenOrder(
            main_order_id=main_order_id,
            department_id=dept_id,
            kitchen_order_number=ko_number,
            status='pending'
        )
        db.add(kitchen_order)
        db.flush()
        
        # Add items
        for item_data in items:
            product = db.query(models.Product).get(item_data["product_id"])
            variant = db.query(models.ProductVariant).get(item_data["variant_id"]) if item_data["variant_id"] else None
            
            ko_item = models.KitchenOrderItem(
                kitchen_order_id=kitchen_order.id,
                product_id=item_data["product_id"],
                variant_id=item_data["variant_id"],
                quantity=item_data["quantity"],
                product_name=product.name_ru if product else "Unknown",
                variant_name=variant.name_ru if variant else None,
                notes=item_data.get("notes", "")
            )
            db.add(ko_item)
        
        kitchen_orders_created.append({
            "kitchen_order_id": kitchen_order.id,
            "department": dept.name,
            "department_code": dept.code,
            "kitchen_order_number": ko_number,
            "items_count": len(items)
        })
    
    db.commit()
    return {
        "main_order_id": main_order_id,
        "kitchen_orders": kitchen_orders_created
    }

@router.get("/kitchen-orders")
async def list_kitchen_orders(
    status: Optional[str] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """List kitchen orders"""
    query = db.query(models.KitchenOrder)
    
    if status:
        query = query.filter(models.KitchenOrder.status == status)
    if department_id:
        query = query.filter(models.KitchenOrder.department_id == department_id)
    
    orders = query.order_by(models.KitchenOrder.created_at.desc()).limit(50).all()
    
    result = []
    for ko in orders:
        dept = db.query(models.ProductionDepartment).get(ko.department_id)
        main_order = db.query(models.Order).get(ko.main_order_id)
        
        items = db.query(models.KitchenOrderItem).filter(
            models.KitchenOrderItem.kitchen_order_id == ko.id
        ).all()
        
        result.append({
            "id": ko.id,
            "kitchen_order_number": ko.kitchen_order_number,
            "main_order_id": ko.main_order_id,
            "main_order_number": main_order.order_number if main_order else None,
            "department": dept.name if dept else None,
            "department_code": dept.code if dept else None,
            "status": ko.status,
            "items_count": len(items),
            "created_at": ko.created_at.isoformat()
        })
    
    return result

@router.post("/kitchen-orders/{ko_id}/print")
async def print_kitchen_order(
    ko_id: int,
    db: Session = Depends(get_db)
):
    """Print kitchen order to physical printer"""
    from app.printer_driver import KitchenReceiptPrinter
    
    # Get kitchen order
    ko = db.query(models.KitchenOrder).get(ko_id)
    if not ko:
        raise HTTPException(status_code=404, detail="Kitchen order not found")
    
    dept = db.query(models.ProductionDepartment).get(ko.department_id)
    if not dept or not dept.printer_ip:
        raise HTTPException(status_code=400, detail="Printer not configured for department")
    
    # Get template
    template = db.query(models.DepartmentReceiptTemplate).filter(
        models.DepartmentReceiptTemplate.department_id == ko.department_id
    ).first()
    
    template_data = {
        'header_text': template.header_text if template else f"*** {dept.name} ***",
        'footer_text': template.footer_text if template else "",
        'font_size': template.font_size if template else 12,
        'paper_width': template.paper_width if template else 80,
        'header_style': getattr(template, 'header_style', 'bold'),
        'items_style': getattr(template, 'items_style', 'normal'),
        'cut_paper': template.cut_paper if template else True,
        'beep': getattr(template, 'beep', True),
        'show_logo': getattr(template, 'show_logo', False),
        'logo_url': getattr(template, 'logo_url', '')
    }
    
    # Get items
    items = db.query(models.KitchenOrderItem).filter(
        models.KitchenOrderItem.kitchen_order_id == ko.id
    ).all()
    
    order_data = {
        'order_num': ko.kitchen_order_number,
        'department': dept.name,
        'items': [
            {
                'name': item.product_name,
                'variant': item.variant_name or '',
                'quantity': item.quantity,
                'notes': item.notes or ''
            }
            for item in items
        ]
    }
    
    # Print
    printer = KitchenReceiptPrinter(dept.printer_ip, dept.printer_port or 9100)
    success = printer.print_kitchen_receipt(order_data, template_data)
    
    if success:
        # Mark as printed
        ko.status = 'printed'
        ko.printed_at = datetime.utcnow()
        db.commit()
        return {"status": "printed", "printer": f"{dept.printer_ip}:{dept.printer_port}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to print")


@router.post("/orders/{order_id}/print-courier")
async def print_courier_receipt(
    order_id: int,
    db: Session = Depends(get_db)
):
    """Print courier receipt"""
    from app.printer_driver import CourierReceiptPrinter
    
    # Get main order
    order = db.query(models.Order).get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get courier template
    from app.models import CourierReceiptTemplate
    template = db.query(CourierReceiptTemplate).first()
    
    template_data = {
        'shop_name': template.shop_name if template else 'SOHO.by',
        'shop_address': template.shop_address if template else '',
        'shop_phone': template.shop_phone if template else '',
        'order_header': template.order_header if template else '{DATE} {TIME}\n№ {ORDER_NUM}',
        'footer_text': template.footer_text if template else '',
        'font_size': template.font_size if template else 12,
        'paper_width': template.paper_width if template else 80,
        'show_client_name': getattr(template, 'show_client_name', True),
        'show_bonus_info': getattr(template, 'show_bonus_info', True),
        'show_address': getattr(template, 'show_address', True),
        'show_client_phone': getattr(template, 'show_client_phone', True),
        'show_comment': getattr(template, 'show_comment', True),
        'show_delivery_mark': getattr(template, 'show_delivery_mark', True),
        'cut_paper': template.cut_paper if template else True
    }
    
    # Parse address
    address = {}
    if order.delivery_address:
        # Simple parsing - can be improved
        addr_parts = order.delivery_address.split(',')
        if len(addr_parts) >= 1:
            address['street'] = addr_parts[0].strip()
        if len(addr_parts) >= 2:
            address['house'] = addr_parts[1].strip()
    
    # Get items with prices
    items = []
    for item in order.items:
        product = db.query(models.Product).get(item.product_id)
        items.append({
            'name': product.name_ru if product else 'Unknown',
            'quantity': item.quantity,
            'price': float(item.total_price)
        })
    
    order_data = {
        'order_num': order.order_number,
        'date': order.created_at.strftime('%d.%m.%Y'),
        'time': order.created_at.strftime('%H:%M'),
        'client_name': order.customer_name or '',
        'client_phone': order.delivery_phone or '',
        'bonus_current': order.bonus_used,
        'bonus_earned': order.bonus_earned,
        'address': address,
        'comment': order.comment or '',
        'delivery_mark': '2.Доставка' if order.order_type == 'delivery' else '1.Самовывоз',
        'payment_method': 'Б/нал.' if order.payment_type == 'card' else 'Наличные',
        'total': float(order.total_amount),
        'items': items
    }
    
    # Find printer (first active department printer or use default)
    dept = db.query(models.ProductionDepartment).filter(
        models.ProductionDepartment.is_active == True
    ).filter(
        (models.ProductionDepartment.printer_ip != None) & 
        (models.ProductionDepartment.printer_ip != '')
    ).first()
    
    if not dept or not dept.printer_ip:
        raise HTTPException(status_code=400, detail="No printer configured")
    
    printer = CourierReceiptPrinter(dept.printer_ip, dept.printer_port or 9100)
    success = printer.print_courier_receipt(order_data, template_data)
    
    if success:
        return {"status": "printed", "printer": f"{dept.printer_ip}:{dept.printer_port}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to print")

@router.get("/kitchen-orders/{ko_id}/receipt")
async def get_kitchen_receipt(
    ko_id: int,
    db: Session = Depends(get_db)
):
    """Get receipt data for kitchen printer"""
    ko = db.query(models.KitchenOrder).get(ko_id)
    if not ko:
        raise HTTPException(status_code=404, detail="Kitchen order not found")
    
    dept = db.query(models.ProductionDepartment).get(ko.department_id)
    main_order = db.query(models.Order).get(ko.main_order_id)
    
    items = db.query(models.KitchenOrderItem).filter(
        models.KitchenOrderItem.kitchen_order_id == ko.id
    ).all()
    
    # Get template
    template = db.query(models.DepartmentReceiptTemplate).filter(
        models.DepartmentReceiptTemplate.department_id == ko.department_id
    ).first()
    
    receipt_data = {
        "kitchen_order_number": ko.kitchen_order_number,
        "main_order_number": main_order.order_number if main_order else None,
        "department": dept.name if dept else None,
        "printed_at": datetime.now().isoformat(),
        "template": {
            "header": template.header_text if template else f"*** {dept.name if dept else 'КУХНЯ'} ***",
            "footer": template.footer_text if template else "",
            "font_size": template.font_size if template else 12,
            "paper_width": template.paper_width if template else 80
        },
        "items": [
            {
                "name": item.product_name,
                "variant": item.variant_name,
                "quantity": item.quantity,
                "notes": item.notes
            }
            for item in items
        ]
    }
    
    return receipt_data

# ========== PRINTER SETTINGS ==========

@router.get("/printer-settings")
async def get_printer_settings(db: Session = Depends(get_db)):
    """Get general printer settings"""
    settings = db.query(models.PrinterSetting).filter(
        models.PrinterSetting.is_active == True
    ).all()
    
    return {s.setting_name: s.setting_value for s in settings}

@router.put("/printer-settings")
async def update_printer_settings(
    settings: dict,
    db: Session = Depends(get_db)
):
    """Update printer settings"""
    for name, value in settings.items():
        setting = db.query(models.PrinterSetting).filter(
            models.PrinterSetting.setting_name == name
        ).first()
        
        if setting:
            setting.setting_value = str(value)
            setting.updated_at = datetime.utcnow()
        else:
            setting = models.PrinterSetting(
                setting_name=name,
                setting_value=str(value),
                setting_type='text'
            )
            db.add(setting)
    
    db.commit()
    return {"status": "updated"}

# ========== COURIER TEMPLATE ==========

@router.get("/templates/courier")
async def get_courier_template(db: Session = Depends(get_db)):
    """Get courier receipt template"""
    from app.models import CourierReceiptTemplate
    template = db.query(CourierReceiptTemplate).first()
    
    if not template:
        return {
            "shop_name": "SOHO.by",
            "shop_address": "Лявданского 1, пав. 114",
            "shop_phone": "+375(29) 116-77-55",
            "order_header": "{DATE} {TIME}\n№ {ORDER_NUM}",
            "footer_text": "Спасибо за заказ!",
            "font_size": 12,
            "paper_width": 80,
            "show_client_name": True,
            "show_bonus_info": True,
            "show_address": True,
            "show_client_phone": True,
            "show_comment": True,
            "show_delivery_mark": True,
            "cut_paper": True,
            "print_duplicates": True
        }
    
    return {
        "shop_name": template.shop_name,
        "shop_address": template.shop_address,
        "shop_phone": template.shop_phone,
        "order_header": template.order_header,
        "footer_text": template.footer_text,
        "font_size": template.font_size,
        "paper_width": template.paper_width,
        "show_client_name": template.show_client_name,
        "show_bonus_info": template.show_bonus_info,
        "show_address": template.show_address,
        "show_client_phone": template.show_client_phone,
        "show_comment": template.show_comment,
        "show_delivery_mark": template.show_delivery_mark,
        "cut_paper": template.cut_paper,
        "print_duplicates": template.print_duplicates
    }

@router.put("/templates/courier")
async def update_courier_template(template_data: dict, db: Session = Depends(get_db)):
    """Update courier receipt template"""
    from app.models import CourierReceiptTemplate
    template = db.query(CourierReceiptTemplate).first()
    
    if template:
        for key, value in template_data.items():
            if hasattr(template, key):
                setattr(template, key, value)
    else:
        template = CourierReceiptTemplate(**template_data)
        db.add(template)
    
    db.commit()
    return {"status": "updated"}

# ========== RECEIPT TEMPLATES ==========

@router.get("/departments/{dept_id}/template")
async def get_department_template(
    dept_id: int,
    db: Session = Depends(get_db)
):
    """Get receipt template for department"""
    template = db.query(models.DepartmentReceiptTemplate).filter(
        models.DepartmentReceiptTemplate.department_id == dept_id
    ).first()
    
    if not template:
        # Return default
        dept = db.query(models.ProductionDepartment).get(dept_id)
        return {
            "header_text": f"*** {dept.name if dept else 'КУХНЯ'} ***",
            "footer_text": "",
            "show_logo": True,
            "logo_url": "",
            "font_size": 12,
            "paper_width": 80,
            "header_style": "bold",
            "items_style": "normal",
            "cut_paper": True,
            "beep": True,
            "open_drawer": False,
            "print_barcode": False
        }
    
    return {
        "header_text": template.header_text,
        "footer_text": template.footer_text,
        "show_logo": template.show_logo if template.show_logo is not None else True,
        "logo_url": template.logo_url,
        "font_size": template.font_size or 12,
        "paper_width": template.paper_width or 80,
        "header_style": getattr(template, 'header_style', 'bold'),
        "items_style": getattr(template, 'items_style', 'normal'),
        "cut_paper": template.cut_paper if template.cut_paper is not None else True,
        "beep": getattr(template, 'beep', True),
        "open_drawer": getattr(template, 'open_drawer', False),
        "print_barcode": getattr(template, 'print_barcode', False)
    }

@router.put("/departments/{dept_id}/template")
async def update_department_template(
    dept_id: int,
    template_data: dict,
    db: Session = Depends(get_db)
):
    """Update receipt template for department"""
    template = db.query(models.DepartmentReceiptTemplate).filter(
        models.DepartmentReceiptTemplate.department_id == dept_id
    ).first()
    
    if template:
        for key, value in template_data.items():
            if hasattr(template, key):
                setattr(template, key, value)
    else:
        template = models.DepartmentReceiptTemplate(
            department_id=dept_id,
            **template_data
        )
        db.add(template)
    
    db.commit()
    return {"status": "updated"}

"""
Auth middleware for frontend pages
"""
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import hashlib
import secrets
from app.database import get_db
from app import models

security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current user from token"""
    # Try header first
    token = None
    if credentials:
        token = credentials.credentials
    
    # Try cookie
    if not token:
        token = request.cookies.get("auth_token")
    
    # Try query param
    if not token:
        token = request.query_params.get("token")
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check company/admin token
    company = db.query(models.Company).filter(
        models.Company.auth_token == token,
        models.Company.is_active == True
    ).first()
    if company:
        return {
            "type": "admin",
            "id": company.id,
            "name": company.name,
            "email": company.email,
            "role": "admin",
            "permissions": {}  # Admin has all permissions
        }
    
    # Check employee token
    employee = db.query(models.Employee).filter(
        models.Employee.auth_token == token,
        models.Employee.is_active == True
    ).first()
    if employee:
        role_perms = employee.role.permissions if employee.role else {}
        return {
            "type": "employee",
            "id": employee.id,
            "name": employee.name,
            "email": employee.email,
            "role": employee.role.name if employee.role else "employee",
            "role_id": employee.role_id,
            "permissions": role_perms,
            "can_access_terminal": employee.can_access_terminal
        }
    
    # Check customer token
    customer = db.query(models.Customer).filter(
        models.Customer.auth_token == token
    ).first()
    if customer:
        return {
            "type": "customer",
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email
        }
    
    raise HTTPException(status_code=401, detail="Invalid token")

async def require_admin(user = Depends(get_current_user)):
    """Require admin access"""
    if user["type"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def require_employee(user = Depends(get_current_user)):
    """Require employee access"""
    if user["type"] not in ["admin", "employee"]:
        raise HTTPException(status_code=403, detail="Employee access required")
    return user

async def require_customer(user = Depends(get_current_user)):
    """Require customer access"""
    if user["type"] != "customer":
        raise HTTPException(status_code=403, detail="Customer access required")
    return user

async def check_permission(permission: str, user = Depends(get_current_user)):
    """Check specific permission"""
    if user["type"] == "admin":
        return user  # Admin has all permissions
    
    perms = user.get("permissions", {})
    # Parse permission path like "orders.create"
    parts = permission.split(".")
    current = perms
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
    
    if not current:
        raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
    
    return user

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import hashlib
import secrets

from app.database import get_db
from app import models

router = APIRouter()

# ========== SCHEMAS ==========

class CompanyLogin(BaseModel):
    email: str
    password: str

class CompanyResponse(BaseModel):
    id: int
    name: str
    email: str
    timezone: str

class LocationResponse(BaseModel):
    id: int
    name: str
    type: str
    address: Optional[str]
    phone: Optional[str]

class EmployeePinLogin(BaseModel):
    location_id: int
    pin_code: str

class EmployeeLoginResponse(BaseModel):
    id: int
    name: str
    role_id: int
    role_name: str
    role_permissions: dict
    location_id: Optional[int]
    location_name: Optional[str]
    token: str

class AuthCheckResponse(BaseModel):
    authenticated: bool
    employee: Optional[dict] = None
    company: Optional[dict] = None
    location: Optional[dict] = None

# ========== HELPERS ==========

def hash_pin(pin: str) -> str:
    """Hash PIN code for secure storage"""
    return hashlib.sha256(pin.encode()).hexdigest()

def generate_token() -> str:
    """Generate secure session token"""
    return secrets.token_urlsafe(32)

def verify_pin(pin: str, pin_hash: str) -> bool:
    """Verify PIN against hash"""
    return hash_pin(pin) == pin_hash

# ========== COMPANY AUTH (Admin) ==========

@router.post("/company/login")
async def company_login(data: CompanyLogin, db: Session = Depends(get_db)):
    """Admin/Terminal login by email/password"""
    # First check if it's terminal login
    company = db.query(models.Company).filter(
        models.Company.terminal_login == data.email,
        models.Company.is_active == True
    ).first()
    
    if company and company.terminal_password_hash:
        # Check terminal password
        password_hash = hashlib.sha256(data.password.encode()).hexdigest()
        if company.terminal_password_hash == password_hash:
            token = generate_token()
            return {
                "token": token,
                "user_id": company.id,
                "email": company.terminal_login,
                "role": "admin",
                "name": company.name,
                "type": "company",
                "can_access_terminal": True,
                "company": {
                    "id": company.id,
                    "name": company.name,
                    "email": company.email,
                    "timezone": company.timezone
                }
            }
    
    # Check employee login (admin/manager)
    employee = db.query(models.Employee).filter(
        models.Employee.email == data.email,
        models.Employee.is_active == True
    ).first()
    
    if employee and employee.password_hash:
        password_hash = hashlib.sha256(data.password.encode()).hexdigest()
        if employee.password_hash == password_hash:
            # Get role info
            role = db.query(models.Role).filter(models.Role.id == employee.role_id).first()
            
            token = generate_token()
            return {
                "token": token,
                "user_id": employee.id,
                "email": employee.email,
                "role": role.name if role else "employee",
                "name": employee.name,
                "type": "employee",
                "can_access_terminal": employee.can_access_terminal or False,
                "employee": {
                    "id": employee.id,
                    "name": employee.name,
                    "role_id": employee.role_id,
                    "role_name": role.name if role else "employee"
                }
            }
    
    # Check main company login (owner)
    company = db.query(models.Company).filter(
        models.Company.email == data.email,
        models.Company.is_active == True
    ).first()
    
    if not company:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    # Check password
    password_hash = hashlib.sha256(data.password.encode()).hexdigest()
    if company.password_hash != password_hash:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    # Generate token
    token = generate_token()
    
    return {
        "token": token,
        "user_id": company.id,
        "email": company.email,
        "role": "owner",
        "name": company.name,
        "type": "company",
        "can_access_terminal": True,
        "company": {
            "id": company.id,
            "name": company.name,
            "email": company.email,
            "timezone": company.timezone
        }
    }

@router.get("/company/locations", response_model=List[LocationResponse])
async def get_company_locations(
    db: Session = Depends(get_db)
):
    """Get all locations for current company"""
    # In real implementation, get company_id from auth token
    company = db.query(models.Company).filter(models.Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    locations = db.query(models.Location).filter(
        models.Location.company_id == company.id
    ).order_by(models.Location.name).all()
    
    return locations

# ========== EMPLOYEE AUTH (Terminal) ==========

@router.post("/terminal/login")
async def terminal_login(data: EmployeePinLogin, db: Session = Depends(get_db)):
    """Employee login by location + PIN"""
    # Find location
    location = db.query(models.Location).filter(
        models.Location.id == data.location_id,
        models.Location.is_active == True
    ).first()
    
    if not location:
        raise HTTPException(status_code=404, detail="Точка не найдена")
    
    # Find employee by PIN (check all employees in this company)
    employees = db.query(models.Employee).filter(
        models.Employee.company_id == location.company_id,
        models.Employee.is_active == True
    ).all()
    
    employee = None
    for emp in employees:
        if emp.pin_hash and verify_pin(data.pin_code, emp.pin_hash):
            employee = emp
            break
    
    if not employee:
        raise HTTPException(status_code=401, detail="Неверный PIN-код")
    
    # Get role info
    role = db.query(models.Role).filter(models.Role.id == employee.role_id).first()
    
    # Update last login
    employee.last_login = datetime.utcnow()
    db.commit()
    
    # Generate token
    token = generate_token()
    
    return {
        "token": token,
        "can_access_crm": employee.can_access_crm,
        "employee": {
            "id": employee.id,
            "name": employee.name,
            "role_id": role.id if role else None,
            "role_name": role.name if role else "Без роли",
            "role_permissions": role.permissions if role else {},
            "location_id": location.id,
            "location_name": location.name,
            "can_access_crm": employee.can_access_crm
        }
    }

@router.get("/terminal/locations")
async def get_terminal_locations(db: Session = Depends(get_db)):
    """Get all active locations for terminal selection"""
    locations = db.query(models.Location).filter(
        models.Location.is_active == True
    ).all()
    
    return [
        {
            "id": loc.id,
            "name": loc.name,
            "type": loc.type,
            "address": loc.address
        }
        for loc in locations
    ]

# ========== SESSION ==========

@router.get("/check")
async def check_auth(request: Request, db: Session = Depends(get_db)):
    """Check if user is authenticated"""
    # In real implementation, verify token from header/cookie
    # For now, return demo response
    return {
        "authenticated": False,
        "employee": None,
        "company": None,
        "location": None
    }

@router.post("/logout")
async def logout():
    """Logout and invalidate token"""
    return {"status": "ok"}

# ========== COMPANY PROFILE ==========

@router.get("/company")
async def get_company(db: Session = Depends(get_db)):
    """Get current company info"""
    # In real implementation, get company from auth token
    # For now, return first active company
    company = db.query(models.Company).filter(models.Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return {
        "id": company.id,
        "name": company.name,
        "legal_name": company.legal_name,
        "email": company.email,
        "phone": company.phone,
        "address": company.address,
        "timezone": company.timezone
    }

@router.put("/company")
async def update_company(data: dict, db: Session = Depends(get_db)):
    """Update company info"""
    company = db.query(models.Company).filter(models.Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    if "name" in data:
        company.name = data["name"]
    if "email" in data:
        # Check email uniqueness
        existing = db.query(models.Company).filter(
            models.Company.email == data["email"],
            models.Company.id != company.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        company.email = data["email"]
    if "phone" in data:
        company.phone = data["phone"]
    if "address" in data:
        company.address = data["address"]
    
    db.commit()
    return {"status": "ok"}

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/company/change-password")
async def change_company_password(data: ChangePasswordRequest, db: Session = Depends(get_db)):
    """Change company admin password"""
    company = db.query(models.Company).filter(models.Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Verify current password
    current_hash = hashlib.sha256(data.current_password.encode()).hexdigest()
    if company.password_hash != current_hash:
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    
    # Validate new password
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Новый пароль должен быть минимум 6 символов")
    
    # Update password
    company.password_hash = hashlib.sha256(data.new_password.encode()).hexdigest()
    db.commit()
    
    return {"status": "ok", "message": "Пароль успешно изменен"}

# ========== EMPLOYEE SESSION TRACKING ==========

class SessionStartRequest(BaseModel):
    employee_id: int
    location_id: Optional[int] = None

class SessionEndRequest(BaseModel):
    employee_id: int

# Store active sessions (in production use Redis)
active_sessions = {}

@router.post("/employee/session/start")
async def start_employee_session(data: SessionStartRequest, db: Session = Depends(get_db)):
    """Start work session for employee (called on login)"""
    employee = db.query(models.Employee).filter(models.Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if already has active session
    if data.employee_id in active_sessions:
        return {"status": "already_active", "session_start": active_sessions[data.employee_id]}
    
    # Start new session
    now = datetime.utcnow()
    active_sessions[data.employee_id] = {
        "start_time": now,
        "location_id": data.location_id
    }
    
    # Update last login
    employee.last_login = now
    db.commit()
    
    return {
        "status": "started",
        "session_start": now.isoformat(),
        "employee_name": employee.name
    }

@router.post("/employee/session/end")
async def end_employee_session(data: SessionEndRequest, db: Session = Depends(get_db)):
    """End work session and calculate hours (called on logout)"""
    employee = db.query(models.Employee).filter(models.Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if data.employee_id not in active_sessions:
        return {"status": "no_active_session"}
    
    session = active_sessions[data.employee_id]
    start_time = session["start_time"]
    end_time = datetime.utcnow()
    
    # Calculate worked hours
    total_seconds = (end_time - start_time).total_seconds()
    total_hours = total_seconds / 3600
    
    # Get employee schedule for today
    today = end_time.date()
    day_of_week = today.weekday()
    day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    schedule = employee.work_schedule.get(day_names[day_of_week]) if employee.work_schedule else None
    
    # Validate hours (not earlier than 1 hour before shift start, not later than 1 hour after shift end)
    valid_hours = total_hours
    if schedule:
        # This is simplified - in production validate against actual schedule
        pass
    
    # Cap at reasonable maximum (12 hours)
    valid_hours = min(valid_hours, 12)
    
    # Create work hours record
    work_record = models.EmployeeWorkHours(
        employee_id=data.employee_id,
        work_date=today,
        start_time=start_time.time(),
        end_time=end_time.time(),
        break_minutes=0,  # Could be calculated from session data
        total_hours=round(valid_hours, 2),
        notes=f"Auto-tracked session"
    )
    
    db.add(work_record)
    db.commit()
    
    # Remove from active sessions
    del active_sessions[data.employee_id]
    
    return {
        "status": "ended",
        "session_start": start_time.isoformat(),
        "session_end": end_time.isoformat(),
        "total_hours": round(valid_hours, 2),
        "work_record_id": work_record.id
    }

@router.get("/employee/session/active")
async def get_active_sessions():
    """Get list of currently active employee sessions"""
    result = []
    for emp_id, session in active_sessions.items():
        result.append({
            "employee_id": emp_id,
            "start_time": session["start_time"].isoformat(),
            "location_id": session.get("location_id"),
            "duration_hours": round((datetime.utcnow() - session["start_time"]).total_seconds() / 3600, 2)
        })
    return result

# ========== PERMISSIONS ==========

@router.get("/permissions")
async def get_available_permissions():
    """Get list of all available permissions"""
    return {
        "orders": {
            "view": "Просмотр заказов",
            "create": "Создание заказов",
            "edit": "Редактирование заказов",
            "delete": "Удаление заказов",
            "cancel": "Отмена заказов"
        },
        "kitchen": {
            "view": "Просмотр кухни",
            "manage": "Управление кухней",
            "print": "Печать бегунков"
        },
        "menu": {
            "view": "Просмотр меню",
            "edit": "Редактирование меню",
            "categories": "Управление категориями"
        },
        "reports": {
            "view": "Просмотр отчетов",
            "export": "Экспорт отчетов"
        },
        "settings": {
            "view": "Просмотр настроек",
            "edit": "Редактирование настроек"
        },
        "employees": {
            "view": "Просмотр сотрудников",
            "edit": "Управление сотрудниками"
        },
        "finance": {
            "view": "Просмотр финансов",
            "edit": "Управление финансами"
        }
    }


# ========== CUSTOMER AUTH ==========

class CustomerLogin(BaseModel):
    phone: str
    password: str

class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: str
    email: Optional[str] = None

@router.post("/customer/login")
async def customer_login(data: CustomerLogin, db: Session = Depends(get_db)):
    """Customer login by phone and password"""
    customer = db.query(models.Customer).filter(models.Customer.phone == data.phone).first()
    if not customer:
        raise HTTPException(status_code=401, detail="Неверный телефон или пароль")
    
    password_hash = hashlib.sha256(data.password.encode()).hexdigest()
    if customer.password_hash != password_hash:
        raise HTTPException(status_code=401, detail="Неверный телефон или пароль")
    
    token = secrets.token_urlsafe(32)
    customer.auth_token = token
    db.commit()
    
    return {
        "token": token,
        "user": {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "role": "customer"
        },
        "type": "customer"
    }


# ========== TERMINAL CREDENTIALS ==========

class TerminalCredentials(BaseModel):
    login: str
    password: Optional[str] = None

@router.get("/company/terminal-credentials")
async def get_terminal_credentials(db: Session = Depends(get_db)):
    """Get terminal login (without password)"""
    company = db.query(models.Company).filter(models.Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return {
        "login": company.terminal_login or company.email
    }

@router.post("/company/terminal-credentials")
async def save_terminal_credentials(data: TerminalCredentials, db: Session = Depends(get_db)):
    """Save terminal login and password"""
    company = db.query(models.Company).filter(models.Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Save login
    company.terminal_login = data.login
    
    # Hash and save password if provided
    if data.password:
        password_hash = hashlib.sha256(data.password.encode()).hexdigest()
        company.terminal_password_hash = password_hash
    
    db.commit()
    return {"status": "ok", "message": "Terminal credentials saved"}

class CustomerRegister(BaseModel):
    name: str
    phone: str
    password: str

@router.post("/customer/register")
async def customer_register(data: CustomerRegister, db: Session = Depends(get_db)):
    """Register new customer"""
    # Check if phone already exists
    existing = db.query(models.Customer).filter(models.Customer.phone == data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким телефоном уже существует")
    
    # Create customer
    password_hash = hashlib.sha256(data.password.encode()).hexdigest()
    
    customer = models.Customer(
        name=data.name,
        phone=data.phone,
        password_hash=password_hash,
        created_at=datetime.utcnow()
    )
    
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    # Generate token
    token = secrets.token_urlsafe(32)
    customer.auth_token = token
    db.commit()
    
    return {
        "token": token,
        "user": {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "role": "customer"
        },
        "type": "customer"
    }

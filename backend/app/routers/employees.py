from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
import hashlib

from app.database import get_db
from app import models

router = APIRouter()

# ========== ROLE SCHEMAS ==========

class RolePermissions(BaseModel):
    orders: dict = {}
    kitchen: dict = {}
    menu: dict = {}
    reports: dict = {}
    settings: dict = {}
    employees: dict = {}
    finance: dict = {}

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = "👤"
    color: Optional[str] = "#e94560"
    permissions: Optional[dict] = {}

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    permissions: Optional[dict] = None

class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    icon: Optional[str]
    color: Optional[str]
    permissions: dict
    employee_count: int

# ========== EMPLOYEE SCHEMAS ==========

class WorkSchedule(BaseModel):
    mon: Optional[dict] = None
    tue: Optional[dict] = None
    wed: Optional[dict] = None
    thu: Optional[dict] = None
    fri: Optional[dict] = None
    sat: Optional[dict] = None
    sun: Optional[dict] = None

class EmployeeCreate(BaseModel):
    # Personal Info
    first_name: str
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None  # Password for admin panel login
    birth_date: Optional[date] = None
    address: Optional[str] = None
    
    # Work Info
    role_id: int
    location_id: Optional[int] = None
    hire_date: Optional[date] = None
    
    # Login
    pin_code: Optional[str] = None
    extension: Optional[str] = None
    
    # Payroll
    hourly_rate: Optional[float] = None
    salary: Optional[float] = None
    payment_type: Optional[str] = "hourly"  # hourly, salary, mixed
    work_schedule: Optional[dict] = None
    
    is_active: bool = True

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None  # Password for admin panel login
    birth_date: Optional[date] = None
    address: Optional[str] = None
    role_id: Optional[int] = None
    location_id: Optional[int] = None
    hire_date: Optional[date] = None
    termination_date: Optional[date] = None
    pin_code: Optional[str] = None
    extension: Optional[str] = None
    hourly_rate: Optional[float] = None
    salary: Optional[float] = None
    payment_type: Optional[str] = None
    work_schedule: Optional[dict] = None
    is_active: Optional[bool] = None

class EmployeeResponse(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str]
    middle_name: Optional[str]
    name: str  # Computed full name
    phone: Optional[str]
    email: Optional[str]
    birth_date: Optional[date]
    address: Optional[str]
    role_id: int
    role_name: str
    location_id: Optional[int]
    location_name: Optional[str]
    hire_date: Optional[date]
    pin_code: Optional[str]
    extension: Optional[str]
    hourly_rate: Optional[float]
    salary: Optional[float]
    payment_type: str
    work_schedule: dict
    is_active: bool
    created_at: Optional[str]

# ========== WORK HOURS SCHEMAS ==========

class WorkHoursCreate(BaseModel):
    employee_id: int
    work_date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    break_minutes: int = 0
    total_hours: Optional[float] = None
    notes: Optional[str] = None

class WorkHoursResponse(BaseModel):
    id: int
    employee_id: int
    work_date: date
    start_time: Optional[str]
    end_time: Optional[str]
    break_minutes: int
    total_hours: Optional[float]
    notes: Optional[str]

# ========== ADVANCE SCHEMAS ==========

class AdvanceCreate(BaseModel):
    employee_id: int
    advance_date: date
    amount: float
    description: Optional[str] = None

class AdvanceResponse(BaseModel):
    id: int
    employee_id: int
    advance_date: date
    amount: float
    description: Optional[str]
    is_deducted: bool

# ========== PAYROLL SCHEMAS ==========

class PayrollCreate(BaseModel):
    employee_id: int
    period_start: date
    period_end: date
    base_amount: float
    bonus_amount: float = 0
    deduction_amount: float = 0
    hours_worked: Optional[float] = None

# ========== ROLE ENDPOINTS ==========

@router.get("/roles", response_model=List[RoleResponse])
async def get_roles(db: Session = Depends(get_db)):
    """Get all roles with employee count"""
    roles = db.query(models.Role).all()
    result = []
    for role in roles:
        emp_count = db.query(models.Employee).filter(models.Employee.role_id == role.id).count()
        result.append({
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "icon": role.icon,
            "color": role.color,
            "permissions": role.permissions or {},
            "employee_count": emp_count
        })
    return result

@router.post("/roles")
async def create_role(data: RoleCreate, db: Session = Depends(get_db)):
    """Create new role"""
    role = models.Role(
        name=data.name,
        description=data.description,
        icon=data.icon,
        color=data.color,
        permissions=data.permissions
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return {"id": role.id, "status": "created"}

@router.put("/roles/{role_id}")
async def update_role(role_id: int, data: RoleUpdate, db: Session = Depends(get_db)):
    """Update role"""
    role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if data.name:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.icon:
        role.icon = data.icon
    if data.color:
        role.color = data.color
    if data.permissions:
        role.permissions = data.permissions
    
    db.commit()
    return {"status": "updated"}

@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, db: Session = Depends(get_db)):
    """Delete role"""
    role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if role is system role
    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system role")
    
    # Check if employees use this role
    emp_count = db.query(models.Employee).filter(models.Employee.role_id == role_id).count()
    if emp_count > 0:
        raise HTTPException(status_code=400, detail=f"Role is assigned to {emp_count} employees")
    
    db.delete(role)
    db.commit()
    return {"status": "deleted"}

# ========== EMPLOYEE ENDPOINTS ==========

def hash_pin(pin: str) -> str:
    """Hash PIN code"""
    return hashlib.sha256(pin.encode()).hexdigest()

@router.get("/employees", response_model=List[EmployeeResponse])
async def get_employees(db: Session = Depends(get_db)):
    """Get all employees"""
    employees = db.query(models.Employee).all()
    result = []
    for emp in employees:
        role = db.query(models.Role).filter(models.Role.id == emp.role_id).first()
        location = db.query(models.Location).filter(models.Location.id == emp.location_id).first()
        
        result.append({
            "id": emp.id,
            "first_name": emp.first_name,
            "last_name": emp.last_name,
            "middle_name": emp.middle_name,
            "name": emp.name,
            "phone": emp.phone,
            "email": emp.email,
            "birth_date": emp.birth_date,
            "address": emp.address,
            "role_id": emp.role_id,
            "role_name": role.name if role else "Unknown",
            "location_id": emp.location_id,
            "location_name": location.name if location else None,
            "hire_date": emp.hire_date,
            "pin_code": emp.pin_code,
            "extension": emp.extension,
            "hourly_rate": float(emp.hourly_rate) if emp.hourly_rate else None,
            "salary": float(emp.salary) if emp.salary else None,
            "payment_type": emp.payment_type,
            "work_schedule": emp.work_schedule or {},
            "is_active": emp.is_active,
            "created_at": emp.created_at.isoformat() if emp.created_at else None
        })
    return result

@router.post("/employees")
async def create_employee(data: EmployeeCreate, db: Session = Depends(get_db)):
    """Create new employee"""
    # Validate PIN
    pin_hash = None
    if data.pin_code:
        if len(data.pin_code) != 4 or not data.pin_code.isdigit():
            raise HTTPException(status_code=400, detail="PIN must be 4 digits")
        pin_hash = hash_pin(data.pin_code)
    
    # Generate full name from parts
    full_name = data.first_name
    if data.last_name:
        full_name += " " + data.last_name
    
    # Hash password if provided
    password_hash = None
    if data.password:
        password_hash = hashlib.sha256(data.password.encode()).hexdigest()
    
    employee = models.Employee(
        name=full_name,
        first_name=data.first_name,
        last_name=data.last_name,
        middle_name=data.middle_name,
        phone=data.phone,
        email=data.email,
        password_hash=password_hash,
        birth_date=data.birth_date,
        address=data.address,
        role_id=data.role_id,
        location_id=data.location_id,
        hire_date=data.hire_date or date.today(),
        pin_code=data.pin_code,
        pin_hash=pin_hash,
        extension=data.extension,
        hourly_rate=data.hourly_rate,
        salary=data.salary,
        payment_type=data.payment_type,
        work_schedule=data.work_schedule or {},
        is_active=data.is_active
    )
    
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return {"id": employee.id, "status": "created"}

@router.get("/employees/{employee_id}")
async def get_employee(employee_id: int, db: Session = Depends(get_db)):
    """Get single employee details"""
    emp = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    role = db.query(models.Role).filter(models.Role.id == emp.role_id).first()
    location = db.query(models.Location).filter(models.Location.id == emp.location_id).first()
    
    return {
        "id": emp.id,
        "first_name": emp.first_name,
        "last_name": emp.last_name,
        "middle_name": emp.middle_name,
        "name": emp.name,
        "phone": emp.phone,
        "email": emp.email,
        "birth_date": emp.birth_date,
        "address": emp.address,
        "role_id": emp.role_id,
        "role_name": role.name if role else "Unknown",
        "location_id": emp.location_id,
        "location_name": location.name if location else None,
        "hire_date": emp.hire_date,
        "termination_date": emp.termination_date,
        "pin_code": emp.pin_code,
        "extension": emp.extension,
        "hourly_rate": float(emp.hourly_rate) if emp.hourly_rate else None,
        "salary": float(emp.salary) if emp.salary else None,
        "payment_type": emp.payment_type,
        "work_schedule": emp.work_schedule or {},
        "is_active": emp.is_active,
        "created_at": emp.created_at.isoformat() if emp.created_at else None
    }

@router.put("/employees/{employee_id}")
async def update_employee(employee_id: int, data: EmployeeUpdate, db: Session = Depends(get_db)):
    """Update employee"""
    emp = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Update fields
    if data.first_name:
        emp.first_name = data.first_name
    if data.last_name is not None:
        emp.last_name = data.last_name
    if data.middle_name is not None:
        emp.middle_name = data.middle_name
    if data.phone is not None:
        emp.phone = data.phone
    if data.email is not None:
        emp.email = data.email
    if data.birth_date is not None:
        emp.birth_date = data.birth_date
    if data.address is not None:
        emp.address = data.address
    if data.role_id:
        emp.role_id = data.role_id
    if data.location_id is not None:
        emp.location_id = data.location_id
    if data.hire_date is not None:
        emp.hire_date = data.hire_date
    if data.termination_date is not None:
        emp.termination_date = data.termination_date
    if data.pin_code:
        if len(data.pin_code) != 4 or not data.pin_code.isdigit():
            raise HTTPException(status_code=400, detail="PIN must be 4 digits")
        emp.pin_code = data.pin_code
        emp.pin_hash = hash_pin(data.pin_code)
    if data.extension is not None:
        emp.extension = data.extension
    if data.hourly_rate is not None:
        emp.hourly_rate = data.hourly_rate
    if data.salary is not None:
        emp.salary = data.salary
    if data.payment_type:
        emp.payment_type = data.payment_type
    if data.work_schedule is not None:
        emp.work_schedule = data.work_schedule
    if data.is_active is not None:
        emp.is_active = data.is_active
    
    # Update password if provided
    if data.password:
        emp.password_hash = hashlib.sha256(data.password.encode()).hexdigest()
    
    # Update full name if first_name or last_name changed
    if data.first_name or data.last_name is not None:
        full_name = emp.first_name
        if emp.last_name:
            full_name += " " + emp.last_name
        emp.name = full_name
    
    db.commit()
    return {"status": "updated"}

@router.delete("/employees/{employee_id}")
async def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    """Soft delete employee (set inactive)"""
    emp = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    emp.is_active = False
    emp.termination_date = date.today()
    db.commit()
    return {"status": "deleted"}

# ========== WORK HOURS ENDPOINTS ==========

@router.get("/employees/{employee_id}/work-hours")
async def get_employee_work_hours(
    employee_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get employee work hours"""
    query = db.query(models.EmployeeWorkHours).filter(
        models.EmployeeWorkHours.employee_id == employee_id
    )
    
    if start_date:
        query = query.filter(models.EmployeeWorkHours.work_date >= start_date)
    if end_date:
        query = query.filter(models.EmployeeWorkHours.work_date <= end_date)
    
    hours = query.order_by(models.EmployeeWorkHours.work_date.desc()).all()
    
    return [
        {
            "id": h.id,
            "work_date": h.work_date,
            "start_time": h.start_time.isoformat() if h.start_time else None,
            "end_time": h.end_time.isoformat() if h.end_time else None,
            "break_minutes": h.break_minutes,
            "total_hours": float(h.total_hours) if h.total_hours else None,
            "notes": h.notes
        }
        for h in hours
    ]

@router.post("/employees/{employee_id}/work-hours")
async def add_work_hours(employee_id: int, data: WorkHoursCreate, db: Session = Depends(get_db)):
    """Add work hours record"""
    # Use provided total_hours or calculate from time
    total_hours = data.total_hours
    
    if total_hours is None and data.start_time and data.end_time:
        from datetime import datetime, time
        start = datetime.combine(data.work_date, datetime.strptime(data.start_time, "%H:%M").time())
        end = datetime.combine(data.work_date, datetime.strptime(data.end_time, "%H:%M").time())
        diff = (end - start).total_seconds() / 3600
        total_hours = max(0, diff - (data.break_minutes / 60))
    
    record = models.EmployeeWorkHours(
        employee_id=employee_id,
        work_date=data.work_date,
        start_time=data.start_time,
        end_time=data.end_time,
        break_minutes=data.break_minutes,
        total_hours=total_hours,
        notes=data.notes
    )
    
    db.add(record)
    db.commit()
    db.refresh(record)
    
    return {"id": record.id, "status": "created"}

# ========== ADVANCE ENDPOINTS ==========

@router.get("/employees/{employee_id}/advances")
async def get_employee_advances(employee_id: int, db: Session = Depends(get_db)):
    """Get employee advances"""
    advances = db.query(models.EmployeeAdvance).filter(
        models.EmployeeAdvance.employee_id == employee_id
    ).order_by(models.EmployeeAdvance.advance_date.desc()).all()
    
    return [
        {
            "id": a.id,
            "advance_date": a.advance_date,
            "amount": float(a.amount),
            "description": a.description,
            "is_deducted": a.is_deducted
        }
        for a in advances
    ]

@router.post("/employees/{employee_id}/advances")
async def add_advance(employee_id: int, data: AdvanceCreate, db: Session = Depends(get_db)):
    """Add advance payment"""
    advance = models.EmployeeAdvance(
        employee_id=employee_id,
        advance_date=data.advance_date,
        amount=data.amount,
        description=data.description
    )
    
    db.add(advance)
    db.commit()
    db.refresh(advance)
    
    return {"id": advance.id, "status": "created"}

# ========== PAYROLL ENDPOINTS ==========

@router.get("/employees/{employee_id}/payroll")
async def get_employee_payroll(
    employee_id: int,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get employee payroll records"""
    query = db.query(models.EmployeePayroll).filter(
        models.EmployeePayroll.employee_id == employee_id
    )
    
    if year and month:
        from datetime import date
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)
        query = query.filter(
            models.EmployeePayroll.period_start >= start,
            models.EmployeePayroll.period_start < end
        )
    
    payroll = query.order_by(models.EmployeePayroll.period_start.desc()).all()
    
    return [
        {
            "id": p.id,
            "period_start": p.period_start,
            "period_end": p.period_end,
            "base_amount": float(p.base_amount),
            "bonus_amount": float(p.bonus_amount),
            "deduction_amount": float(p.deduction_amount),
            "total_amount": float(p.total_amount),
            "hours_worked": float(p.hours_worked) if p.hours_worked else None,
            "advance_deduction": float(p.advance_deduction),
            "final_amount": float(p.final_amount),
            "is_paid": p.is_paid,
            "paid_date": p.paid_date
        }
        for p in payroll
    ]

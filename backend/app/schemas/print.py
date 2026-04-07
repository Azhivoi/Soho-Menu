"""
Pydantic schemas for print API
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class PrintRequest(BaseModel):
    order_id: int
    print_type: str  # receipt, kitchen, precheck
    kitchen_id: Optional[str] = None
    data: Dict[str, Any]
    is_reprint: bool = False
    reprint_reason: Optional[str] = None

class PrintResponse(BaseModel):
    job_id: int
    status: str
    message: str
    estimated_time: Optional[str] = None
    is_reprint: bool = False

class ReprintRequest(BaseModel):
    order_id: int
    print_type: str
    kitchen_id: Optional[str] = None
    reason: str

class PrintCheckResponse(BaseModel):
    can_print: bool
    reason: str
    message: str
    warning: bool = False
    job_id: Optional[int] = None
    status: Optional[str] = None
    original_print_time: Optional[datetime] = None
    print_count: Optional[int] = None

class PrintJobInfo(BaseModel):
    id: int
    print_type: str
    status: str
    created_at: datetime
    is_reprint: bool

class PrintStatusResponse(BaseModel):
    order_id: int
    receipt_printed: bool
    receipt_printed_at: Optional[datetime]
    kitchen_runners: Dict[str, Any]
    recent_jobs: List[PrintJobInfo]
    can_print_receipt: bool
    pending_jobs: List[PrintJobInfo]

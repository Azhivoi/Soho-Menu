"""
Print API with duplicate protection
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
import json
import asyncio

from app.database import get_db
from app.models import PrintJob, OrderPrintStatus, Config
from app.schemas.print import (
    PrintRequest, PrintResponse, ReprintRequest, 
    PrintCheckResponse, PrintStatusResponse, PrintJobInfo
)

router = APIRouter(tags=["print"])


def get_print_settings(db: Session):
    """Get print settings from config"""
    config = db.query(Config).filter(Config.key == 'crm_settings').first()
    if config and config.value:
        try:
            data = json.loads(config.value)
            return data.get('kitchen', {})
        except:
            pass
    return {}

def check_before_print(
    order_id: int,
    print_type: str,
    kitchen_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Проверка перед печатью — можно ли печатать?"""
    status = db.query(OrderPrintStatus).filter(
        OrderPrintStatus.order_id == order_id
    ).first()
    
    # Проверяем недавние job'ы
    recent_job = db.query(PrintJob).filter(
        PrintJob.order_id == order_id,
        PrintJob.print_type == print_type,
        PrintJob.kitchen_id == kitchen_id,
        PrintJob.status.in_(["pending", "printing"]),
        PrintJob.created_at > datetime.now() - timedelta(minutes=5)
    ).first()
    
    if recent_job:
        return PrintCheckResponse(
            can_print=False,
            reason="printing_now",
            message="Печать уже выполняется, подождите...",
            job_id=recent_job.id,
            status=recent_job.status
        )
    
    # Проверяем уже напечатанное
    if print_type == "receipt" and status and status.receipt_printed:
        return PrintCheckResponse(
            can_print=True,
            reason="already_printed",
            warning=True,
            message=f"Чек уже печатался {status.receipt_printed_at}. Это будет перепечатка.",
            original_print_time=status.receipt_printed_at,
            print_count=status.receipt_print_count
        )
    
    # Для бегунков проверяем конкретную кухню
    if print_type == "kitchen" and kitchen_id and status:
        kitchen_status = status.kitchen_runners.get(kitchen_id, {})
        if kitchen_status.get("printed"):
            # Check if reprint is allowed
            kitchen_settings = get_print_settings(db)
            allow_reprint = kitchen_settings.get('allowReprintRunner', True)
            
            if not allow_reprint:
                return PrintCheckResponse(
                    can_print=False,
                    reason="reprint_not_allowed",
                    warning=False,
                    message="Повторная печать бегунков запрещена в настройках",
                    original_print_time=kitchen_status.get("at")
                )
            
            return PrintCheckResponse(
                can_print=True,
                reason="kitchen_already_printed",
                warning=True,
                message="Бегунок для этой кухни уже печатался. Перепечатать?",
                original_print_time=kitchen_status.get("at")
            )
    
    return PrintCheckResponse(
        can_print=True,
        reason="first_print",
        warning=False,
        message="Можно печатать"
    )

@router.get("/check-before-print", response_model=PrintCheckResponse)
def check_before_print_endpoint(
    order_id: int,
    print_type: str,
    kitchen_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Проверка перед печатью — можно ли печатать?"""
    return check_before_print(order_id, print_type, kitchen_id, db)

@router.post("/execute", response_model=PrintResponse)
def execute_print(
    request: PrintRequest,
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """Выполнение печати с защитой от дублей"""
    if not force:
        check = check_before_print(
            request.order_id, 
            request.print_type, 
            request.kitchen_id, 
            db
        )
        if not check.can_print:
            raise HTTPException(status_code=409, detail=check.message)
    
    # Создаем job
    job = PrintJob(
        order_id=request.order_id,
        print_type=request.print_type,
        kitchen_id=request.kitchen_id,
        print_data=request.data,
        status="pending",
        is_reprint=request.is_reprint,
        reprint_reason=request.reprint_reason
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return PrintResponse(
        job_id=job.id,
        status="pending",
        message="Печать поставлена в очередь",
        estimated_time="5-10 сек",
        is_reprint=request.is_reprint
    )


@router.post("/reprint", response_model=PrintResponse)
def reprint(
    request: ReprintRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Повторная печать с обязательным указанием причины"""
    original = db.query(PrintJob).filter(
        PrintJob.order_id == request.order_id,
        PrintJob.print_type == request.print_type,
        PrintJob.kitchen_id == request.kitchen_id,
        PrintJob.status == "completed"
    ).order_by(PrintJob.printed_at.desc()).first()
    
    if not original:
        raise HTTPException(status_code=404, detail="Оригинальная печать не найдена")
    
    reprint_job = PrintJob(
        order_id=request.order_id,
        print_type=request.print_type,
        kitchen_id=request.kitchen_id,
        print_data=original.print_data,
        status="pending",
        is_reprint=True,
        original_job_id=original.id,
        reprint_reason=request.reason
    )
    db.add(reprint_job)
    db.commit()
    
    return PrintResponse(
        job_id=reprint_job.id,
        status="pending",
        message=f"Перепечатка создана. Причина: {request.reason}",
        is_reprint=True
    )


@router.get("/status/{order_id}", response_model=PrintStatusResponse)
def get_print_status(
    order_id: int,
    db: Session = Depends(get_db)
):
    """Получить полный статус печати заказа для UI"""
    status = db.query(OrderPrintStatus).filter(
        OrderPrintStatus.order_id == order_id
    ).first()
    
    recent_jobs = db.query(PrintJob).filter(
        PrintJob.order_id == order_id,
        PrintJob.created_at > datetime.now() - timedelta(hours=24)
    ).order_by(PrintJob.created_at.desc()).all()
    
    jobs_info = [
        PrintJobInfo(
            id=j.id,
            print_type=j.print_type,
            status=j.status,
            created_at=j.created_at,
            is_reprint=j.is_reprint
        ) for j in recent_jobs
    ]
    
    pending = [j for j in jobs_info if j.status in ("pending", "printing")]
    
    return PrintStatusResponse(
        order_id=order_id,
        receipt_printed=status.receipt_printed if status else False,
        receipt_printed_at=status.receipt_printed_at if status else None,
        kitchen_runners=status.kitchen_runners if status else {},
        recent_jobs=jobs_info,
        can_print_receipt=not (status and status.receipt_printed),
        pending_jobs=pending
    )


# ========== WEBSOCKET FOR PRINT AGENT ==========

connected_agents = {}

@router.websocket("/ws/agent/{agent_id}")
async def print_agent_websocket(websocket: WebSocket, agent_id: str):
    """WebSocket для локального агента печати"""
    await websocket.accept()
    connected_agents[agent_id] = websocket
    print(f"🖨️ Print agent connected: {agent_id}")
    
    try:
        # Send current printer settings from CRM
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            settings = db.query(Config).filter(Config.key == "crm_settings").first()
            if settings and settings.value:
                data = json.loads(settings.value)
                printers = data.get("printers", {})
                config = {
                    "type": "config",
                    "receipt_printer_ip": printers.get("receipt", {}).get("ip", "192.168.1.100"),
                    "receipt_printer_port": printers.get("receipt", {}).get("port", 9100),
                    "kitchen_printer_ip": printers.get("kitchen", {}).get("ip", "192.168.1.101"),
                    "kitchen_printer_port": printers.get("kitchen", {}).get("port", 9100),
                }
                await websocket.send_json(config)
                print(f"📤 Sent printer config to {agent_id}")
        finally:
            db.close()
        
        # Keep connection alive and handle messages
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=30)
                # Handle agent messages (status updates, etc.)
                if message.get("type") == "status":
                    print(f"📥 Agent {agent_id} status: {message}")
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_json({"type": "ping"})
            except Exception as e:
                print(f"❌ Agent {agent_id} message error: {e}")
                break
    except WebSocketDisconnect:
        print(f"🖨️ Print agent disconnected: {agent_id}")
    except Exception as e:
        print(f"❌ Agent {agent_id} error: {e}")
    finally:
        if agent_id in connected_agents:
            del connected_agents[agent_id]


# ========== HTTP PRINT ENDPOINTS FOR WEB AGENT ==========

import socket
from pydantic import BaseModel

class PrintTestRequest(BaseModel):
    printer_type: str  # 'receipt' or 'kitchen'

@router.post("/agent/print-test")
def print_test(request: PrintTestRequest, db: Session = Depends(get_db)):
    """Print test page to network printer"""
    # Get printer settings from CRM
    settings = db.query(Config).filter(Config.key == "crm_settings").first()
    if not settings or not settings.value:
        raise HTTPException(status_code=400, detail="Printer settings not found")
    
    data = json.loads(settings.value)
    printers = data.get("printers", {})
    
    if request.printer_type == "receipt":
        printer = printers.get("receipt", {})
        ip = printer.get("ip", "192.168.1.100")
        port = printer.get("port", 9100)
        print_data = build_test_receipt()
    else:
        printer = printers.get("kitchen", {})
        ip = printer.get("ip", "192.168.1.101")
        port = printer.get("port", 9100)
        print_data = build_test_runner()
    
    # Send to printer via TCP socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, port))
        sock.send(print_data)
        sock.close()
        return {"success": True, "message": f"Printed to {ip}:{port}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Printer error: {str(e)}")

def build_test_receipt() -> bytes:
    """Build ESC/POS test receipt"""
    ESC = b'\x1b'
    GS = b'\x1d'
    CMD_INIT = ESC + b'@'
    CMD_CENTER = ESC + b'a\x01'
    CMD_LEFT = ESC + b'a\x00'
    CMD_BOLD_ON = ESC + b'E\x01'
    CMD_BOLD_OFF = ESC + b'E\x00'
    CMD_DOUBLE = GS + b'!\x11'
    CMD_NORMAL = GS + b'!\x00'
    CMD_CUT = GS + b'V\x01'
    LF = b'\n'
    
    data = CMD_INIT
    data += CMD_CENTER
    data += CMD_BOLD_ON
    data += CMD_DOUBLE
    data += "SOHO Cafe".encode('cp866', errors='replace') + LF
    data += CMD_NORMAL
    data += CMD_BOLD_OFF
    data += b'=' * 32 + LF
    data += "TEST RECEIPT".encode('cp866', errors='replace') + LF
    data += b'=' * 32 + LF
    data += CMD_LEFT
    data += "1x Test item           10.00".encode('cp866', errors='replace') + LF
    data += b'=' * 32 + LF
    data += CMD_CENTER
    data += CMD_BOLD_ON
    data += "TOTAL: 10.00".encode('cp866', errors='replace') + LF
    data += CMD_BOLD_OFF
    data += LF + LF + LF
    data += CMD_CUT
    return data

def build_test_runner() -> bytes:
    """Build ESC/POS test kitchen runner"""
    ESC = b'\x1b'
    GS = b'\x1d'
    CMD_INIT = ESC + b'@'
    CMD_CENTER = ESC + b'a\x01'
    CMD_LEFT = ESC + b'a\x00'
    CMD_BOLD_ON = ESC + b'E\x01'
    CMD_BOLD_OFF = ESC + b'E\x00'
    CMD_DOUBLE = GS + b'!\x11'
    CMD_HIGH = GS + b'!\x01'
    CMD_NORMAL = GS + b'!\x00'
    CMD_CUT = GS + b'V\x01'
    LF = b'\n'
    
    data = CMD_INIT
    data += CMD_CENTER
    data += CMD_BOLD_ON
    data += CMD_DOUBLE
    data += "#TEST".encode('cp866', errors='replace') + LF
    data += CMD_NORMAL
    data += CMD_BOLD_OFF
    data += b'=' * 32 + LF
    data += CMD_BOLD_ON
    data += CMD_HIGH
    data += "TABLE 99".encode('cp866', errors='replace') + LF
    data += CMD_NORMAL
    data += CMD_BOLD_OFF
    data += b'=' * 32 + LF
    data += CMD_LEFT
    data += "1x Test dish".encode('cp866', errors='replace') + LF
    data += LF + LF + LF
    data += CMD_CUT
    return data

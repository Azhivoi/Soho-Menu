from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
import logging
from datetime import datetime

router = APIRouter(prefix="/api/frontpad", tags=["frontpad"])

# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logging.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

manager = ConnectionManager()

# Pydantic models
class FrontpadCall(BaseModel):
    phone: str
    type: str  # 'incoming' or 'outgoing'
    timestamp: Optional[str] = None
    line: Optional[str] = "main"
    call_id: Optional[str] = None

class CustomerInfo(BaseModel):
    id: int
    name: str
    phone: str
    orders_count: int = 0
    total_spent: float = 0.0
    last_order: Optional[str] = None
    vip: bool = False

# Mock database - replace with real DB queries
MOCK_CUSTOMERS = {
    "+375291234567": {
        "id": 1,
        "name": "Иван Петров",
        "phone": "+375291234567",
        "orders_count": 15,
        "total_spent": 4500.50,
        "last_order": "2026-03-01",
        "vip": True
    },
    "+375339876543": {
        "id": 2,
        "name": "Мария Сидорова",
        "phone": "+375339876543",
        "orders_count": 8,
        "total_spent": 2100.00,
        "last_order": "2026-02-28",
        "vip": False
    }
}

def find_customer_by_phone(phone: str) -> Optional[dict]:
    """Find customer by phone number"""
    # Clean phone number
    clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # Try exact match first
    if phone in MOCK_CUSTOMERS:
        return MOCK_CUSTOMERS[phone]
    
    # Try clean phone
    for key, customer in MOCK_CUSTOMERS.items():
        clean_key = key.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if clean_key == clean_phone:
            return customer
    
    return None

@router.post("/callback")
async def frontpad_callback(
    request: Request,
    x_token: Optional[str] = Header(None)
):
    """
    FrontPad webhook endpoint - Prostie Zvonki sends call data here
    """
    try:
        body = await request.body()
        logging.info(f"FrontPad callback raw: {body}")
        
        data = await request.json()
        logging.info(f"FrontPad callback parsed: {data}")
        
        # Extract data
        phone = data.get('phone') or data.get('number')
        call_type = data.get('type') or data.get('direction', 'incoming')
        timestamp = data.get('timestamp') or data.get('moment') or datetime.now().isoformat()
        line = data.get('line', 'main')
        call_id = data.get('call_id') or data.get('id')
        
        if not phone:
            logging.error("No phone number in FrontPad callback")
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Phone number required"}
            )
        
        # Find customer in database
        customer = find_customer_by_phone(phone)
        
        # Prepare notification
        notification = {
            "type": "incoming_call" if call_type in ['incoming', 'in'] else "outgoing_call",
            "data": {
                "call_id": call_id,
                "phone": phone,
                "line": line,
                "timestamp": timestamp,
                "customer": customer
            }
        }
        
        # Broadcast to all connected CRM clients
        await manager.broadcast(notification)
        
        logging.info(f"Call notification sent: {phone}, customer: {customer['name'] if customer else 'new'}")
        
        # Return FrontPad-compatible response
        return JSONResponse({
            "status": "ok",
            "client": {
                "id": customer['id'] if customer else None,
                "name": customer['name'] if customer else None,
                "phone": phone
            }
        })
        
    except Exception as e:
        logging.error(f"FrontPad callback error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.get("/client/{phone}")
async def frontpad_get_client(phone: str):
    """
    Get client info by phone - Prostie Zvonki queries this before showing popup
    """
    try:
        logging.info(f"FrontPad client lookup: {phone}")
        
        customer = find_customer_by_phone(phone)
        
        if not customer:
            return JSONResponse({
                "status": "not_found",
                "phone": phone,
                "client": None
            })
        
        return JSONResponse({
            "status": "ok",
            "client": {
                "id": customer['id'],
                "name": customer['name'],
                "phone": customer['phone'],
                "orders_count": customer['orders_count'],
                "total_spent": customer['total_spent'],
                "last_order": customer['last_order'],
                "vip": customer['vip']
            }
        })
        
    except Exception as e:
        logging.error(f"FrontPad client lookup error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.get("/test/{phone}")
async def test_call(phone: str):
    """
    Test endpoint - simulate incoming call
    """
    customer = find_customer_by_phone(phone)
    
    notification = {
        "type": "incoming_call",
        "data": {
            "call_id": "test_" + datetime.now().strftime("%Y%m%d%H%M%S"),
            "phone": phone,
            "line": "test",
            "timestamp": datetime.now().isoformat(),
            "customer": customer
        }
    }
    
    await manager.broadcast(notification)
    
    return {
        "status": "ok",
        "message": "Test call sent",
        "sent_to": len(manager.active_connections),
        "customer": customer
    }

# WebSocket endpoint for CRM frontend
@router.websocket("/ws/calls")
async def websocket_calls(websocket: WebSocket):
    """
    WebSocket for real-time call notifications to CRM
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle ping/pong
            if message.get('action') == 'ping':
                await websocket.send_json({"type": "pong"})
            
            # Handle call answered
            elif message.get('action') == 'call_answered':
                logging.info(f"Call answered: {message.get('call_id')}")
                # TODO: Update call status in database
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)

# Debug endpoint
@router.post("/debug")
async def debug_callback(request: Request):
    """
    Debug endpoint - log everything that comes in
    """
    headers = dict(request.headers)
    body = await request.body()
    
    try:
        json_body = await request.json()
    except:
        json_body = None
    
    logging.info(f"FrontPad DEBUG headers: {headers}")
    logging.info(f"FrontPad DEBUG body: {body}")
    
    return {
        "headers": headers,
        "body_raw": body.decode() if body else None,
        "body_json": json_body
    }
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

from app.database import get_db
from app import models

router = APIRouter(tags=['prostie_zvonki'])

# Expected CRM token - should match what's set in PZ dashboard
CRM_TOKEN = "soho-crm-token"

# WebSocket connections to CRM frontend
class CRMConnectionManager:
    def __init__(self):
        self.active_connections: list = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"CRM client connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

crm_manager = CRMConnectionManager()

# Mock customer database
MOCK_CUSTOMERS = {
    "375291234567": {
        "id": 1,
        "name": "Иван Петров",
        "phone": "375291234567",
        "orders_count": 15,
        "total_spent": 4500.50,
        "last_order": "2026-03-01",
        "vip": True
    }
}

def find_customer_by_phone(phone: str) -> Optional[dict]:
    if not phone:
        return None
    clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").lstrip('+')
    
    for key, customer in MOCK_CUSTOMERS.items():
        if key == clean_phone or key == clean_phone.lstrip('+'):
            return customer
    
    return None

# CORS preflight handler
@router.options("/pbxapi/{account_id}/")
async def pz_cors_preflight(account_id: str):
    return JSONResponse(
        content={"status": "ok"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@router.post("/pbxapi/{account_id}/")
async def prostie_zvonki_webhook(account_id: str, request: Request):
    """
    Prostie Zvonki webhook - receives call events
    Formats:
    - cmd=event, type=INCOMING/OUTGOING/ACCEPTED - call started/answered
    - cmd=history - call ended with history
    - cmd=contact - smart transfer request
    """
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "").lower()
        
        logging.info(f"PZ webhook received: {body.decode()}")
        
        # Parse JSON body
        try:
            if "json" in content_type:
                data = await request.json()
            else:
                data = json.loads(body.decode())
        except Exception as e:
            logging.error(f"Failed to parse JSON: {e}")
            return JSONResponse(
                {"status": "error", "message": "Invalid JSON"},
                headers={"Access-Control-Allow-Origin": "*"},
                status_code=400
            )
        
        # Verify CRM token (optional for now)
        crm_token = data.get("crm_token", "")
        # if crm_token != CRM_TOKEN:
        #     return JSONResponse(
        #         {"status": "error", "message": "Invalid token"},
        #         headers={"Access-Control-Allow-Origin": "*"},
        #         status_code=401
        #     )
        
        cmd = data.get("cmd", "")
        
        if cmd == "event":
            # Call started or answered
            event_type = data.get("type", "")  # INCOMING, OUTGOING, ACCEPTED
            phone = data.get("phone", "")
            user = data.get("user", "")  # extension
            callid = data.get("callid", "")
            direction = data.get("direction", "")  # in, out
            
            # Find customer
            customer = find_customer_by_phone(phone)
            
            # Map to our format
            if event_type == "ACCEPTED":
                notification_type = "call_answered"
            elif event_type == "INCOMING" or direction == "in":
                notification_type = "call_started"
            else:
                notification_type = "call_started"
            
            notification = {
                "type": notification_type,
                "data": {
                    "call_id": callid,
                    "phone": phone,
                    "extension": user,
                    "direction": direction if direction else ("incoming" if event_type == "INCOMING" else "outgoing"),
                    "customer": customer,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            await crm_manager.broadcast(notification)
            logging.info(f"PZ event: {notification_type} from {phone}")
            
        elif cmd == "history":
            # Call ended with history
            phone = data.get("phone", "")
            callid = data.get("callid", "")
            duration = data.get("duration", 0)
            status = data.get("status", "")  # success, missed
            record_link = data.get("link", "")
            
            notification = {
                "type": "call_ended",
                "data": {
                    "call_id": callid,
                    "phone": phone,
                    "duration": duration,
                    "status": status,
                    "record_link": record_link,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            await crm_manager.broadcast(notification)
            logging.info(f"PZ history: call ended {phone}, duration {duration}s")
            
        elif cmd == "contact":
            # Smart transfer request
            phone = data.get("phone", "")
            customer = find_customer_by_phone(phone)
            
            # Return responsible user if found
            responsible = ""  # Default - no responsible
            if customer and customer.get("responsible_id"):
                responsible = str(customer["responsible_id"])
            
            return JSONResponse(
                {"responsible": responsible},
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        return JSONResponse(
            {"status": "ok", "result": "ok"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
        
    except Exception as e:
        logging.error(f"PZ webhook error: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            headers={"Access-Control-Allow-Origin": "*"},
            status_code=500
        )

@router.get("/api/pz/test")
async def test_incoming_call(
    phone: str = Query("375291234567"),
    extension: str = Query("100")
):
    """Test endpoint - simulate PZ event"""
    customer = find_customer_by_phone(phone)
    
    notification = {
        "type": "call_started",
        "data": {
            "call_id": "test_" + datetime.now().strftime("%Y%m%d%H%M%S"),
            "phone": phone,
            "extension": extension,
            "direction": "incoming",
            "customer": customer,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    await crm_manager.broadcast(notification)
    
    return {
        "status": "ok",
        "clients_count": len(crm_manager.active_connections),
        "notification": notification
    }

@router.get("/api/pz/status")
async def get_status():
    return {
        "status": "active",
        "crm_clients_connected": len(crm_manager.active_connections),
        "timestamp": datetime.now().isoformat()
    }

@router.post("/api/pz/call")
async def make_call(request: Request):
    """Initiate click-to-call via Prostie Zvonki"""
    # Определяем переменные ЗДЕСЬ, до всех try-блоков
    payload = None
    user = None
    phone = None
    clean_phone = None
    
    try:
        # 1. Get data
        data = await request.json()
        phone = data.get('phone', '').strip()
        user = data.get('user', data.get('extension', '100'))
        
        # 2. Validate
        if not phone:
            return JSONResponse(status_code=400, content={"status": "error", "error": "Phone required"})
        if not user:
            return JSONResponse(status_code=400, content={"status": "error", "error": "User required"})
        
        # 3. Clean phone
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # 4. Create payload ЗДЕСЬ, гарантированно до использования
        payload = {
            "user": str(user),
            "phone": clean_phone
        }
        print(f"Payload created: {payload}")
        
        # 5. Get settings - используем токен напрямую
        api_token = os.environ.get('PZ_API_TOKEN', 'cf547c5a-4ffd-4f77-9b5d-b4bb3bc11aa9')
        
        if not api_token:
            return JSONResponse(status_code=400, content={"status": "error", "error": "PZ not configured"})
        
        # 6. Request to PZ
        url = "https://interaction.prostiezvonki.ru/httpapiinteg/crmapi/v1/makecall"
        headers = {
            "X-API-KEY": api_token,
            "Content-Type": "application/json"
        }
        
        print(f"Sending to {url}")
        
        # Try with aiohttp or urllib
        result = None
        resp_status = None
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                    resp_status = resp.status
                    result = await resp.json()
                    print(f"PZ response: {resp_status}, {result}")
                    
                    if resp_status == 200 and result.get("result") == "ok":
                        call_id = f"pz_{int(time.time())}"
                        return {"status": "ok", "call_id": call_id, "message": "Call initiated"}
                    else:
                        # PZ error - use simulated mode with notification
                        error = result.get("error", "PZ error")
                        logging.warning(f"PZ error, using simulated mode: {error}")
                        call_id = f"test_{int(time.time())}"
                        
                        # Broadcast to CRM
                        try:
                            await crm_manager.broadcast({
                                "type": "outgoing_call_initiated",
                                "data": {
                                    "phone": phone,
                                    "extension": user,
                                    "call_id": call_id,
                                    "test_mode": True,
                                    "timestamp": datetime.now().isoformat()
                                }
                            })
                        except Exception as broadcast_err:
                            print(f"Broadcast error: {broadcast_err}")
                        
                        return {
                            "status": "ok",
                            "message": f"[ТЕСТОВЫЙ РЕЖИМ] Вызов на {phone} (ПЗ недоступен: {error})",
                            "call_id": call_id,
                            "extension": user,
                            "test_mode": True
                        }
        
        except ImportError:
            # Fallback to urllib
            print("aiohttp not found, using urllib")
            import urllib.request
            import urllib.error
            import json as json_mod  # локальный импорт json
            
            req = urllib.request.Request(
                url, 
                data=json_mod.dumps(payload).encode('utf-8'), 
                headers=headers, 
                method='POST'
            )
            
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json_mod.loads(resp.read().decode('utf-8'))
                    if result.get("result") == "ok":
                        return {"status": "ok", "call_id": f"pz_{int(time.time())}"}
                    else:
                        return JSONResponse(
                            status_code=502, 
                            content={"status": "error", "error": result.get("error", "PZ error")}
                        )
            except urllib.error.URLError as url_err:
                print(f"urllib error: {url_err}")
                return JSONResponse(
                    status_code=502,
                    content={"status": "error", "error": f"Connection failed: {str(url_err)}"}
                )
                    
    except Exception as e:
        import traceback
        print(f"Error in make_call: {e}")
        print(f"Payload at error time: {payload}")  # теперь payload всегда определен (может быть None)
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500, 
            content={"status": "error", "error": str(e), "detail": "Internal server error"}
        )

@router.websocket("/ws/pz/calls")
async def websocket_crm(websocket: WebSocket):
    """WebSocket for CRM frontend clients"""
    await crm_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get("action") == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg.get("action") == "call_answered":
                logging.info(f"Call answered: {msg.get('call_id')}")
                
    except WebSocketDisconnect:
        crm_manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        crm_manager.disconnect(websocket)

@router.post("/pbxapi/catchall")
@router.get("/pbxapi/catchall")
@router.api_route("/pbxapi/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def catch_all(request: Request, path: str = ""):
    """Catch-all for debugging - logs everything"""
    body = await request.body()
    log_data = {
        "method": request.method,
        "url": str(request.url),
        "path": path,
        "headers": dict(request.headers),
        "body": body.decode() if body else None,
        "query": dict(request.query_params)
    }
    logging.error(f"CATCHALL: {json.dumps(log_data)}")
    return JSONResponse({"status": "caught", "path": path}, headers={"Access-Control-Allow-Origin": "*"})

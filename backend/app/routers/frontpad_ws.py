from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/frontpad", tags=["frontpad"])

# WebSocket connection to Prostie Zvonki server
# Trying different endpoints - FrontPad uses HTTP callbacks, not WebSocket client
# But let's try common WebSocket paths
PZ_WS_URL = "wss://mobile.prostiezvonki.ru/ws"
PZ_USER = "crm"
PZ_PASSWORD = "71VI34"
PZ_EXTENSION = "291190303"

# Connection to CRM frontend clients
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

# WebSocket client to Prostie Zvonki
pz_websocket = None
pz_connected = False

async def connect_to_prostie_zvonki():
    """
    Connect to Prostie Zvonki WebSocket server as client
    """
    global pz_websocket, pz_connected
    
    while True:
        try:
            logging.info(f"Connecting to Prostie Zvonki: {PZ_WS_URL}")
            
            # Build URL with authentication parameters
            auth_url = f"{PZ_WS_URL}?login={PZ_USER}&password={PZ_PASSWORD}&extension={PZ_EXTENSION}"
            
            async with websockets.connect(auth_url) as ws:
                pz_websocket = ws
                pz_connected = True
                logging.info("Connected to Prostie Zvonki server")
                
                # Send authentication
                auth_msg = {
                    "action": "auth",
                    "login": PZ_USER,
                    "password": PZ_PASSWORD,
                    "extension": PZ_EXTENSION
                }
                await ws.send(json.dumps(auth_msg))
                
                # Listen for messages
                async for message in ws:
                    try:
                        data = json.loads(message)
                        logging.info(f"Received from PZ: {data}")
                        
                        # Process incoming call
                        if data.get('event') == 'incoming_call' or data.get('type') == 'call':
                            await handle_incoming_call(data)
                        
                        # Process call ended
                        elif data.get('event') == 'call_ended':
                            await handle_call_ended(data)
                            
                    except json.JSONDecodeError:
                        logging.error(f"Invalid JSON from PZ: {message}")
                    except Exception as e:
                        logging.error(f"Error processing PZ message: {e}")
                        
        except websockets.exceptions.ConnectionClosed:
            logging.warning("Prostie Zvonki connection closed, reconnecting in 10s...")
            pz_connected = False
            await asyncio.sleep(10)
        except Exception as e:
            logging.error(f"Prostie Zvonki connection error: {e}")
            pz_connected = False
            await asyncio.sleep(10)

async def handle_incoming_call(data: dict):
    """
    Process incoming call from Prostie Zvonki
    """
    phone = data.get('phone') or data.get('number') or data.get('call_src')
    call_id = data.get('call_id') or data.get('id')
    
    if not phone:
        logging.error("No phone number in call data")
        return
    
    # Find customer in database
    customer = find_customer_by_phone(phone)
    
    # Prepare notification
    notification = {
        "type": "incoming_call",
        "data": {
            "call_id": call_id,
            "phone": phone,
            "timestamp": datetime.now().isoformat(),
            "customer": customer,
            "raw_data": data  # For debugging
        }
    }
    
    # Broadcast to all CRM clients
    await crm_manager.broadcast(notification)
    logging.info(f"Incoming call broadcasted: {phone}, customer: {customer['name'] if customer else 'new'}")

async def handle_call_ended(data: dict):
    """
    Process call ended event
    """
    notification = {
        "type": "call_ended",
        "data": {
            "call_id": data.get('call_id'),
            "duration": data.get('duration'),
            "timestamp": datetime.now().isoformat()
        }
    }
    
    await crm_manager.broadcast(notification)
    logging.info(f"Call ended broadcasted: {data.get('call_id')}")

def find_customer_by_phone(phone: str) -> Optional[dict]:
    """Find customer by phone number in database"""
    # TODO: Replace with real DB query
    # For now using mock data
    
    clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
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
        },
        "291190303": {  # Internal extension
            "id": 3,
            "name": "Оператор",
            "phone": "291190303",
            "orders_count": 0,
            "total_spent": 0,
            "last_order": None,
            "vip": False
        }
    }
    
    # Try exact match
    if phone in MOCK_CUSTOMERS:
        return MOCK_CUSTOMERS[phone]
    
    # Try clean phone
    for key, customer in MOCK_CUSTOMERS.items():
        clean_key = key.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if clean_key == clean_phone:
            return customer
    
    return None

# WebSocket endpoint for CRM frontend
@router.websocket("/ws/calls")
async def websocket_crm(websocket: WebSocket):
    """
    WebSocket for CRM frontend clients to receive call notifications
    """
    await crm_manager.connect(websocket)
    try:
        while True:
            # Handle ping from client
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get('action') == 'ping':
                await websocket.send_json({"type": "pong"})
            elif msg.get('action') == 'call_answered':
                logging.info(f"Call answered by operator: {msg.get('call_id')}")
                # TODO: Update call status in database
                
    except WebSocketDisconnect:
        crm_manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"CRM WebSocket error: {e}")
        crm_manager.disconnect(websocket)

# HTTP endpoints for testing and compatibility
@router.get("/status")
async def get_status():
    """
    Get connection status to Prostie Zvonki
    """
    return {
        "prostie_zvonki_connected": pz_connected,
        "crm_clients_connected": len(crm_manager.active_connections),
        "server_url": PZ_WS_URL,
        "extension": PZ_EXTENSION
    }

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
            "timestamp": datetime.now().isoformat(),
            "customer": customer
        }
    }
    
    await crm_manager.broadcast(notification)
    
    return {
        "status": "ok",
        "message": "Test call sent to all CRM clients",
        "clients_count": len(crm_manager.active_connections),
        "customer": customer
    }

@router.post("/webhook")
async def webhook_fallback(request: Request):
    """
    Fallback webhook endpoint (if Prostie Zvonki sends webhooks instead of WS)
    """
    try:
        data = await request.json()
        logging.info(f"Webhook received: {data}")
        
        # Process same as WebSocket message
        if data.get('event') == 'incoming_call' or data.get('type') == 'call':
            await handle_incoming_call(data)
        
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# Note: startup event is now in main.py lifespan
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import json
import logging

from app.database import engine, Base
from app.routers import menu, orders, customers, config, recipes, warehouse, production, frontpad, frontpad_ws, prostie_zvonki, marks, statuses, order_types, employees, discounts, prostie_zvonki_config, kitchens, auth, locations, content, marketing, print, promotions_v2, settings, pwa_auth, printer_settings
from app.routers.frontpad_ws import connect_to_prostie_zvonki

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    
    # Start Prostie Zvonki WebSocket client
    import asyncio
    asyncio.create_task(connect_to_prostie_zvonki())
    
    yield
    # Shutdown
    engine.dispose()

app = FastAPI(
    title="SOHO Cafe API",
    description="API для кафе SOHO - меню, заказы, CRM",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(menu.router, prefix="/api/menu", tags=["menu"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(recipes.router, prefix="/api/recipes", tags=["recipes"])
app.include_router(warehouse.router, prefix="/api/warehouse", tags=["warehouse"])
app.include_router(production.router, prefix="/api/production", tags=["production"])
app.include_router(frontpad.router, tags=["frontpad"])
app.include_router(frontpad_ws.router, tags=["frontpad_ws"])
app.include_router(prostie_zvonki.router, tags=["prostie_zvonki"])
app.include_router(marks.router, prefix="/api/marks", tags=["marks"])
app.include_router(marks.router, prefix="/api/crm-settings", tags=["marks"])
app.include_router(statuses.router, prefix="/api/crm-settings", tags=["statuses"])
app.include_router(order_types.router, prefix="/api/crm-settings", tags=["order_types"])
app.include_router(discounts.router, prefix="/api/crm-settings", tags=["discounts"])
app.include_router(employees.router, prefix="/api/employees", tags=["employees"])
app.include_router(prostie_zvonki_config.router, prefix="/api/pz", tags=["prostie_zvonki_config"])
app.include_router(kitchens.router, prefix="/api", tags=["kitchens"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(content.router, prefix="/api/content", tags=["content"])
app.include_router(marketing.router, prefix="/api", tags=["marketing"])
app.include_router(promotions_v2.router, prefix="/api/v2/promotions", tags=["promotions"])
app.include_router(print.router, prefix="/api/print", tags=["print"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(pwa_auth.router, prefix="/api", tags=["pwa-auth"])
app.include_router(locations.router, prefix="/api", tags=["locations"])
app.include_router(printer_settings.router, prefix="/api", tags=["printer-settings"])

# WebSocket endpoint for Prostie Zvonki (must be added directly to app)
from app.routers.prostie_zvonki import crm_manager

@app.websocket("/ws/pz/calls")
async def websocket_pz_calls(websocket: WebSocket):
    await crm_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get('action') == 'ping':
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        crm_manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        crm_manager.disconnect(websocket)

@app.get("/")
async def root():
    return {
        "message": "SOHO Cafe API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

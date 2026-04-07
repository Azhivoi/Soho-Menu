from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import secrets
import hashlib
from datetime import datetime, timedelta

router = APIRouter(prefix="/auth/pwa", tags=["pwa-auth"])

# In-memory token storage (in production use Redis or DB)
active_tokens = {}

class PwaLoginRequest(BaseModel):
    pin: str

class PwaValidateRequest(BaseModel):
    token: str

class PwaLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[dict] = None
    error: Optional[str] = None

# Default PIN for testing (in production load from DB)
DEFAULT_PWA_PIN = "123456"

def generate_token() -> str:
    """Generate secure random token"""
    return secrets.token_urlsafe(32)

def hash_pin(pin: str) -> str:
    """Hash PIN for storage"""
    return hashlib.sha256(pin.encode()).hexdigest()

@router.post("/login", response_model=PwaLoginResponse)
def pwa_login(request: PwaLoginRequest):
    """Login to PWA with 6-digit PIN"""
    
    # Validate PIN format
    if not request.pin or len(request.pin) != 6 or not request.pin.isdigit():
        return PwaLoginResponse(success=False, error="Invalid PIN format")
    
    # Check PIN (in production: check against database)
    # For now using default PIN
    if request.pin != DEFAULT_PWA_PIN:
        return PwaLoginResponse(success=False, error="Invalid PIN")
    
    # Generate token
    token = generate_token()
    
    # Store token with expiration (24 hours)
    active_tokens[token] = {
        "user_id": "pwa_user",
        "user_name": "Tablet User",
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=24)
    }
    
    return PwaLoginResponse(
        success=True,
        token=token,
        user={
            "id": "pwa_user",
            "name": "Tablet User",
            "role": "operator"
        }
    )

@router.post("/validate")
def pwa_validate(request: PwaValidateRequest):
    """Validate PWA auth token"""
    
    if not request.token:
        return {"valid": False, "error": "No token provided"}
    
    token_data = active_tokens.get(request.token)
    
    if not token_data:
        return {"valid": False, "error": "Invalid token"}
    
    # Check expiration
    if datetime.utcnow() > token_data["expires_at"]:
        del active_tokens[request.token]
        return {"valid": False, "error": "Token expired"}
    
    return {
        "valid": True,
        "user": {
            "id": token_data["user_id"],
            "name": token_data["user_name"]
        }
    }

@router.post("/logout")
def pwa_logout(request: PwaValidateRequest):
    """Logout and invalidate token"""
    
    if request.token in active_tokens:
        del active_tokens[request.token]
    
    return {"success": True}

@router.get("/status")
def pwa_status(token: str):
    """Check token status"""
    
    token_data = active_tokens.get(token)
    
    if not token_data:
        return {"authenticated": False}
    
    if datetime.utcnow() > token_data["expires_at"]:
        del active_tokens[request.token]
        return {"authenticated": False, "error": "Token expired"}
    
    return {
        "authenticated": True,
        "user": {
            "id": token_data["user_id"],
            "name": token_data["user_name"]
        },
        "expires_at": token_data["expires_at"].isoformat()
    }

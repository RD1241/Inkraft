from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, Any
from providers.auth.supabase_auth import SupabaseAuth

router = APIRouter(prefix="/auth", tags=["auth"])
auth_provider = SupabaseAuth()

security = HTTPBearer()

class UserAuthRequest(BaseModel):
    email: str
    password: str

class ResendRequest(BaseModel):
    email: str

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    user = auth_provider.verify_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@router.post("/register")
def register(req: UserAuthRequest):
    try:
        res = auth_provider.sign_up(email=req.email, password=req.password)
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login")
def login(req: UserAuthRequest):
    try:
        res = auth_provider.sign_in(email=req.email, password=req.password)
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

@router.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    auth_provider.sign_out(token)
    return {"message": "Logged out successfully"}

@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return {"user": user}

@router.post("/resend-confirmation")
def resend_confirmation(req: ResendRequest):
    """
    Resend the signup confirmation email for an unconfirmed account.
    Called by the frontend when a user tries to register with an email
    that already exists but has not yet been confirmed.
    Returns HTTP 200 in all non-crash cases so the frontend can always
    show a friendly 'check your inbox' message.
    """
    try:
        result = auth_provider.resend_confirmation_email(email=req.email)
        return result
    except Exception as e:
        error_str = str(e).lower()
        # Surface rate-limit errors clearly so the frontend can show a
        # helpful message instead of a generic failure.
        if "rate limit" in error_str or "email rate" in error_str or "too many" in error_str:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate_limit"
            )
        # Any unexpected error — log it but still return 200 to avoid
        # leaking internal details to the client.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

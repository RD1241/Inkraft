from fastapi import APIRouter, Header, Query, HTTPException
from typing import Optional
from services.credits_service import credits_service

router = APIRouter(prefix="/credits", tags=["credits"])

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000"

@router.get("/balance")
def get_balance(
    user_id: Optional[str] = Query(None, description="Optional user UUID or text"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID", description="Optional user UUID or text from header"),
    authorization: Optional[str] = Header(None, description="Bearer token")
):
    """
    Exposes secure endpoint to get current credits balance of a user.
    If user_id is not provided, falls back to the default UUID.
    """
    target_user_id = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            from providers.auth.supabase_auth import SupabaseAuth
            auth_provider = SupabaseAuth()
            user = auth_provider.verify_token(token)
            if user and "id" in user:
                target_user_id = user["id"]
        except Exception as e:
            print(f"[Warning] Failed to verify token in get_balance: {e}")

    if not target_user_id:
        target_user_id = user_id or x_user_id or DEFAULT_USER_ID

    try:
        balance = credits_service.get_balance(target_user_id)
        return {
            "status": "success",
            "user_id": target_user_id,
            "balance": balance
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history")
def get_history(
    user_id: Optional[str] = Query(None, description="Optional user UUID or text"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID", description="Optional user UUID or text from header"),
    authorization: Optional[str] = Header(None, description="Bearer token")
):
    """
    Exposes secure endpoint to retrieve the credits transaction history of a user.
    If user_id is not provided, falls back to the default UUID.
    """
    target_user_id = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            from providers.auth.supabase_auth import SupabaseAuth
            auth_provider = SupabaseAuth()
            user = auth_provider.verify_token(token)
            if user and "id" in user:
                target_user_id = user["id"]
        except Exception as e:
            print(f"[Warning] Failed to verify token in get_history: {e}")

    if not target_user_id:
        target_user_id = user_id or x_user_id or DEFAULT_USER_ID

    try:
        history = credits_service.get_history(target_user_id)
        return {
            "status": "success",
            "user_id": target_user_id,
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

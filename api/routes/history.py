from fastapi import APIRouter, HTTPException, Query, Header
from services.history_service import history_service
from typing import Optional

router = APIRouter()

@router.get("/history")
def get_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    user_id: Optional[str] = Query(None, description="Optional user identification UUID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID", description="Optional user identification in header"),
    authorization: Optional[str] = Header(None, description="Bearer token")
):
    """
    Get paginated collection of comic generation history.
    """
    uid = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            from providers.auth.supabase_auth import SupabaseAuth
            auth_provider = SupabaseAuth()
            user = auth_provider.verify_token(token)
            if user and "id" in user:
                uid = user["id"]
        except Exception as e:
            print(f"[Warning] Failed to verify token in get_history: {e}")

    if not uid:
        uid = user_id or x_user_id or "00000000-0000-0000-0000-000000000000"

    try:
        res = history_service.get_user_comics(user_id=uid, page=page, limit=limit)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{id}")
def get_comic_sheet(id: str):
    """
    Fetch a granular metadata package for a specific generated comic sheet.
    """
    try:
        comic = history_service.get_comic_by_id(id)
        if not comic:
            raise HTTPException(status_code=404, detail="Comic sheet not found")
        return comic
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{id}")
def delete_comic_sheet(id: str):
    """
    Deletes a generated sheet from user history permanently.
    """
    try:
        success = history_service.delete_comic(comic_id=id)
        if not success:
            raise HTTPException(status_code=404, detail="Comic sheet not found or already deleted")
        return {"status": "success", "message": "Comic sheet deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history/{id}/share")
def share_comic_sheet(id: str, is_public: bool = Query(True)):
    """
    Toggles public sharing state of a comic sheet in history.
    """
    import sqlite3
    import httpx
    try:
        conn = sqlite3.connect(history_service.db_path)
        cursor = conn.cursor()
        
        # Check if the column is_public exists (if not, add it)
        try:
            cursor.execute("ALTER TABLE comics ADD COLUMN is_public INTEGER DEFAULT 0")
        except Exception:
            pass
            
        cursor.execute("UPDATE comics SET is_public = ? WHERE id = ?", (1 if is_public else 0, id))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if history_service.supabase_enabled:
            # Sync to Supabase
            url = f"{history_service.supabase_url.rstrip('/')}/rest/v1/comics?id=eq.{id}"
            headers = {
                "apikey": history_service.supabase_key,
                "Authorization": f"Bearer {history_service.supabase_key}"
            }
            payload = {"is_public": is_public}
            try:
                r = httpx.patch(url, headers=headers, json=payload, timeout=10.0)
                r.raise_for_status()
            except Exception as e:
                print(f"[Warning] Failed to sync share state in Supabase: {e}")
                
        if not success:
            raise HTTPException(status_code=404, detail="Comic sheet not found")
        return {"status": "success", "is_public": is_public}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

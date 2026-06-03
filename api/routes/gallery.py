from fastapi import APIRouter, HTTPException, Query, Header
from services.gallery_service import gallery_service
from typing import Optional

router = APIRouter()

@router.get("/gallery")
def get_gallery(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    style: Optional[str] = Query(None, description="Filter by style badge"),
):
    """
    Public unauthenticated route to fetch shared (public) comics in the gallery.
    """
    try:
        res = gallery_service.get_public_comics(style=style, page=page, limit=limit)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gallery/{id}/share")
def share_comic(
    id: str,
    user_id: Optional[str] = Query(None, description="Optional user identification UUID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID", description="Optional user identification in header"),
    authorization: Optional[str] = Header(None, description="Bearer token")
):
    """
    Authenticated toggle to share a comic (sets is_public = true).
    Only the owner of the comic can share it.
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
            print(f"[Warning] Failed to verify token in share_comic: {e}")

    if not uid:
        uid = user_id or x_user_id or "00000000-0000-0000-0000-000000000000"

    try:
        success = gallery_service.set_public(comic_id=id, is_public=True, user_id=uid)
        if not success:
            raise HTTPException(status_code=404, detail="Comic not found or not owned by user")
        return {"status": "success", "message": "Comic shared successfully.", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gallery/{id}/unshare")
def unshare_comic(
    id: str,
    user_id: Optional[str] = Query(None, description="Optional user identification UUID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID", description="Optional user identification in header"),
    authorization: Optional[str] = Header(None, description="Bearer token")
):
    """
    Authenticated toggle to unshare a comic (sets is_public = false).
    Only the owner of the comic can unshare it.
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
            print(f"[Warning] Failed to verify token in unshare_comic: {e}")

    if not uid:
        uid = user_id or x_user_id or "00000000-0000-0000-0000-000000000000"

    try:
        success = gallery_service.set_public(comic_id=id, is_public=False, user_id=uid)
        if not success:
            raise HTTPException(status_code=404, detail="Comic not found or not owned by user")
        return {"status": "success", "message": "Comic unshared successfully.", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

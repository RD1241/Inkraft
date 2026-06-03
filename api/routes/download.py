import os
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from fastapi.responses import FileResponse
from PIL import Image

from config import settings
from services.billing_service import billing_service
from core.comic_renderer import ComicRenderer
from core.panel_compositor import PanelCompositor, PageLayout, PanelCoords

router = APIRouter()

def get_current_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
) -> str:
    """Dependency that extracts and validates the user_id for authentication."""
    uid = None
    
    # 1. Try to extract from Authorization Bearer token
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        try:
            from providers.auth.supabase_auth import SupabaseAuth
            auth_provider = SupabaseAuth()
            user = auth_provider.verify_token(token)
            if user and "id" in user:
                uid = user["id"]
        except Exception as e:
            print(f"[Warning] Failed to verify token in get_current_user_id: {e}")
            
    # 2. Fallback to headers or query parameters
    if not uid:
        uid = x_user_id or user_id

    if not uid:
        raise HTTPException(status_code=401, detail="Authentication credentials missing.")
        
    try:
        import uuid
        uuid.UUID(uid)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID format. Must be a valid UUID.")
        
    return uid

def get_local_path_from_url(url: str) -> str:
    """Resolves a relative web URL or file name to its absolute local path."""
    if not url:
        return ""
    if "://" in url:
        # Extract path part of URL
        url = "/" + url.split("://", 1)[1].split("/", 1)[1]
        
    if url.startswith("/outputs/"):
        rel_path = url[len("/outputs/"):]
        return os.path.normpath(os.path.join(settings.OUTPUTS_DIR, rel_path))
        
    direct_path = os.path.normpath(os.path.join(settings.OUTPUTS_DIR, url.lstrip("/")))
    if os.path.exists(direct_path):
        return direct_path
        
    return url

def get_layout_for_comic(panel_images: list) -> PageLayout:
    """Loads metadata.json to calculate the exact custom layout, or falls back to grid coordinates."""
    if panel_images:
        first_img = panel_images[0]
        if os.path.exists(first_img):
            dir_name = os.path.dirname(first_img)
            meta_path = os.path.join(dir_name, "metadata.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        scene_data = json.load(f)
                    scenes = scene_data.get("scenes") or scene_data.get("panels")
                    if scenes:
                        compositor = PanelCompositor()
                        layout_type = scene_data.get("layout_type") or "standard"
                        return compositor.calculate_layout(scenes, layout_type=layout_type)
                except Exception as e:
                    print(f"[DownloadRoute] Failed to load metadata.json layout: {e}")
                    
    # Deterministic fallback coordinate system (like grid fallback)
    num_images = len(panel_images)
    cols = 2 if num_images > 2 else 1
    rows = (num_images + cols - 1) // cols
    
    panel_w = 490 if cols == 2 else 1000
    panel_h = 490
    gutter = 15
    
    panels = []
    for i in range(num_images):
        row = i // cols
        col = i % cols
        x = gutter + col * (panel_w + gutter)
        y = gutter + row * (panel_h + gutter)
        panels.append(PanelCoords(
            x=x, y=y, width=panel_w, height=panel_h,
            panel_id=i+1, size_class="medium"
        ))
    return PageLayout(panels=panels, layout_type="standard", total_panels=num_images)

@router.get("/download/{comic_id}/pdf")
def download_pdf(
    comic_id: str,
    user_id: str = Depends(get_current_user_id),
    tier: Optional[str] = Header(None, alias="X-User-Tier"),
    is_free_param: Optional[bool] = Query(None, alias="is_free")
):
    """
    Downloads the comic as an elegant A4 PDF page.
    Costs 1 credit and enforces billing deductor (balance check).
    """
    # 1. Fetch comic / job data
    comic = billing_service.get_comic_by_id(comic_id)
    if not comic:
        raise HTTPException(status_code=404, detail="Comic or Job not found.")
        
    # 2. Check and deduct 1 credit
    balance = billing_service.get_or_create_balance(user_id)
    if balance < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits. 1 credit is required to download PDF.")
        
    # Deduct 1 credit
    deducted = billing_service.deduct_credit(user_id, amount=1, reason="pdf_download")
    if not deducted:
        raise HTTPException(status_code=500, detail="Credit deduction failed. Please try again.")
        
    # 3. Locate panel images
    panel_urls = comic.get("panel_urls", [])
    if not panel_urls:
        raise HTTPException(status_code=400, detail="No panels found associated with this comic.")
        
    panel_images = [get_local_path_from_url(url) for url in panel_urls]
    
    # Verify that all panel files exist
    missing = [p for p in panel_images if not os.path.exists(p)]
    if missing:
        raise HTTPException(status_code=404, detail=f"Some panel images are missing on server: {missing}")
        
    # 4. Resolve layout
    page_layout = get_layout_for_comic(panel_images)
    
    # 5. Determine if watermark should be drawn (usually false for paid PDF downloads, but we support free user flags if passed)
    is_free = False
    if tier == "free" or is_free_param:
        is_free = True
        
    # 6. Generate PDF file in job directory
    first_img = panel_images[0]
    job_dir = os.path.dirname(first_img)
    pdf_filename = f"comic_{comic_id}.pdf"
    pdf_path = os.path.join(job_dir, pdf_filename)
    
    try:
        renderer = ComicRenderer()
        renderer.export_pdf(panel_images, page_layout, pdf_path, is_free=is_free)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF document: {e}")
        
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="PDF generation succeeded but output file is missing.")
        
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"comic_{comic_id}.pdf")

@router.get("/download/{comic_id}/png")
def download_png(
    comic_id: str,
    user_id: str = Depends(get_current_user_id),
    tier: Optional[str] = Header(None, alias="X-User-Tier"),
    is_free_param: Optional[bool] = Query(None, alias="is_free")
):
    """
    Downloads the full comic sheet as a PNG.
    Free of credit cost. Watermarks bottom-right corner for free tier users.
    """
    # 1. Fetch comic / job data
    comic = billing_service.get_comic_by_id(comic_id)
    if not comic:
        raise HTTPException(status_code=404, detail="Comic or Job not found.")
        
    final_page_url = comic.get("final_page")
    if not final_page_url:
        raise HTTPException(status_code=400, detail="Stitched final comic page has not been generated for this comic.")
        
    final_page_path = get_local_path_from_url(final_page_url)
    if not os.path.exists(final_page_path):
        raise HTTPException(status_code=404, detail="Stitched final page image is missing on server.")
        
    # 2. Determine if user is free tier
    is_free = False
    if tier == "free" or is_free_param:
        is_free = True
    else:
        # Check credit balance: if balance is 0 or less, they are treated as free
        balance = billing_service.get_or_create_balance(user_id)
        if balance <= 0:
            is_free = True
            
    # 3. Handle free user watermark injection
    if is_free:
        # Check or create watermarked PNG in same directory
        dir_name = os.path.dirname(final_page_path)
        base_name = os.path.basename(final_page_path)
        watermarked_filename = f"watermarked_{base_name}"
        watermarked_path = os.path.join(dir_name, watermarked_filename)
        
        if not os.path.exists(watermarked_path):
            try:
                img = Image.open(final_page_path)
                renderer = ComicRenderer()
                watermarked_img = renderer._add_watermark_to_pillow_image(img)
                watermarked_img.save(watermarked_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to apply watermark: {e}")
                
        return FileResponse(watermarked_path, media_type="image/png", filename=f"comic_{comic_id}.png")
        
    # Premium/paid users get original clean file
    return FileResponse(final_page_path, media_type="image/png", filename=f"comic_{comic_id}.png")

from fastapi import APIRouter, Header, Query, Depends
from fastapi.responses import JSONResponse
from config import settings
from core.scene_interpreter import detect_style
from services.comic_service import comic_service
from services.credits_service import credits_service
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from api.routes.auth import get_current_user

router = APIRouter()

class NovelInput(BaseModel):
    text: str
    style: str = ""   # optional: anime | manga | manhwa | realistic | cinematic
    panel_count: Optional[int] = Field(None, description="Optional panel count (1-10)")
    layout_type: Optional[str] = Field(None, description="Optional layout type")
    user_id: Optional[str] = Field(None, description="Optional user UUID or text string")
    characters: Optional[list] = Field(None, description="Optional character design sheets list")
    re_generate: Optional[bool] = Field(False, description="Optional bypass daily limit and re-generate")
    generation_format: Optional[str] = Field(None, description="Optional generation format: single_page | panel_strip | None")
    color_mode: Optional[str] = Field("auto", description="Colour mode: auto | color | bw")

    @field_validator("color_mode")
    @classmethod
    def validate_color_mode(cls, v):
        if v is None:
            return "auto"
        v = str(v).strip().lower()
        if v not in ("auto", "color", "bw"):
            raise ValueError("color_mode must be one of: auto, color, bw")
        return v

    @field_validator("panel_count")
    @classmethod
    def validate_panel_count(cls, v):
        max_panels = getattr(settings, "MAX_PANELS_PER_COMIC", 6)
        if v is not None and (v < 1 or v > max_panels):
            raise ValueError(f"panel_count must be between 1 and {max_panels}")
        return v

def fail(message: str, detail: str = None) -> JSONResponse:
    """Standard failure response."""
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": message, "detail": detail or ""}
    )

@router.post("/generate_comic")
def generate_comic(
    novel_input: NovelInput,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    query_user_id: Optional[str] = Query(None, alias="user_id"),
    current_user: dict = Depends(get_current_user)
):
    text = (novel_input.text or "").strip()

    # Resolve user_id: request body > authenticated user_id > header > query param > default UUID
    DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000"
    authenticated_user_id = current_user.get("id") if current_user else None
    user_id = novel_input.user_id or authenticated_user_id or x_user_id or query_user_id or DEFAULT_USER_ID

    # Resolve style: user-specified > auto-detected from text > default
    raw_style  = (novel_input.style or "").strip().lower()
    style      = raw_style if raw_style in getattr(settings, "MODEL_MAP", {}) else detect_style(text)
    style      = style or getattr(settings, "DEFAULT_STYLE", "anime")

    # Input validation
    if len(text) < settings.MIN_INPUT_LENGTH:
        return fail(
            f"Input too short. Please provide at least {settings.MIN_INPUT_LENGTH} characters.",
            f"Got {len(text)} characters."
        )
    if len(text) > settings.MAX_INPUT_LENGTH:
        return fail(
            f"Input too long. Max {settings.MAX_INPUT_LENGTH} characters allowed.",
            f"Got {len(text)} characters."
        )

    # Validate panel_count (capped at MAX_PANELS_PER_COMIC — a quality-neutral
    # runway guard; the UI already maxes at 6).
    max_panels = getattr(settings, "MAX_PANELS_PER_COMIC", 6)
    if novel_input.panel_count is not None:
        if novel_input.panel_count < 1 or novel_input.panel_count > max_panels:
            return fail(
                f"Invalid panel count. panel_count must be between 1 and {max_panels}.",
                f"Got panel_count={novel_input.panel_count}"
            )

    # Validate layout_type
    if novel_input.layout_type is not None:
        if not novel_input.layout_type.strip():
            return fail(
                "Invalid layout type. layout_type cannot be empty.",
                "Got empty layout_type"
            )

    # Cache check to avoid charging credits for cache hits
    is_cached = False
    if getattr(settings, "ENABLE_CACHING", True):
        cached_res = comic_service.cache_manager.get_cached_result(text)
        if cached_res:
            is_cached = True

    # Billing gate (only apply if not cached)
    if not is_cached:
        try:
            if getattr(novel_input, "re_generate", False):
                # Refund old generation first to achieve net zero: refund +1, deduct -1
                try:
                    credits_service.refund_credit(user_id)
                except Exception as refund_err:
                    print(f"[Warning] Refund before regeneration failed: {refund_err}")
                credits_service.deduct_credit(user_id, re_generate=True)
            else:
                credits_service.deduct_credit(user_id, re_generate=False)
        except ValueError as e:
            return fail(str(e), "Billing check failed. Please check credits balance and daily limit.")
        except Exception as e:
            return fail("Credits system error.", str(e))

    # Queue or return cache using comic_service
    try:
        job_id, cached = comic_service.queue_comic_generation(
            text=text,
            style=style,
            panel_count=novel_input.panel_count,
            layout_type=novel_input.layout_type,
            user_id=user_id,
            characters=novel_input.characters,
            generation_format=novel_input.generation_format,
            color_mode=novel_input.color_mode
        )
    except Exception as e:
        # If queueing itself failed, refund immediately
        if not is_cached:
            try:
                credits_service.refund_credit(user_id)
            except Exception:
                pass
        return fail("Failed to queue job.", str(e))
    
    if cached:
        return {
            "status": "success",
            "message": "Returned from cache.",
            "job_id": job_id,
            "cached": True,
            "data": {"job_id": job_id}
        }
    
    return {
        "status": "success",
        "message": "Job queued successfully.",
        "job_id": job_id,
        "cached": False,
        "data": {"job_id": job_id}
    }

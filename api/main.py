import sys
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from api.routes import generate, status, health, credits, history, gallery, download, auth, characters

app = FastAPI(title="Inkraft API", description="Enterprise-Grade AI Pipeline")

# Register routers under prefix '/api'
app.include_router(generate.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(download.router, prefix="/api")
app.include_router(gallery.router, prefix="/api")
app.include_router(credits.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(characters.router, prefix="/api")

# Startup check and static mounts
os.makedirs(settings.OUTPUTS_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=settings.OUTPUTS_DIR), name="outputs")
app.mount("/", StaticFiles(directory=os.path.join(settings.BASE_DIR, "frontend"), html=True), name="frontend")

@app.on_event("startup")
def startup_event():
    image_provider_name = os.environ.get("IMAGE_PROVIDER", "stable_diffusion").lower()
    if image_provider_name == "stable_diffusion":
        print("[Startup] IMAGE_PROVIDER is stable_diffusion. Pre-warming local model to avoid VRAM spikes...")
        try:
            from providers.factory import get_image_provider
            provider = get_image_provider()
            # Call load_model with default settings to pre-warm
            if hasattr(provider, "generator"):
                provider.generator.load_model(style=None)
                print("[Startup] Local model pre-warmed successfully.")
        except Exception as e:
            print(f"[Startup] [Warning] Failed to pre-warm local model: {e}")


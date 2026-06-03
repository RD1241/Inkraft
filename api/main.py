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

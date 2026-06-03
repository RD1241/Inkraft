from fastapi import APIRouter
from services.comic_service import comic_service

router = APIRouter()

@router.get("/health")
def get_health():
    return comic_service.drift_monitor.get_system_health()

@router.get("/metrics")
def get_metrics():
    return comic_service.drift_monitor.get_system_health()

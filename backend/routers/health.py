from fastapi import APIRouter

from backend.services.model import model_service

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "model_loaded": model_service.model is not None,
    }

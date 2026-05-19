import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services.model import model_service

logger = logging.getLogger(__name__)
router = APIRouter()


class LoadModelRequest(BaseModel):
    mode: str  # "free" | "prompt"


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "model_loaded": model_service.model is not None,
    }


@router.get("/model/status")
async def model_status():
    return model_service.get_status()


@router.post("/model/load")
async def load_model(req: LoadModelRequest):
    try:
        model_service.load_model(req.mode)
        return model_service.get_status()
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Model load failed: {e}")
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        logger.error(f"Model load error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services.model import model_service
from backend.services.training import training_service

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


class LoadCustomModelRequest(BaseModel):
    model_id: str


@router.post("/model/load-custom")
async def load_custom_model(req: LoadCustomModelRequest):
    try:
        model_meta = training_service.get_model_version(req.model_id)
        model_service.load_custom_model(
            model_path=model_meta["best_model_path"],
            class_names=model_meta["class_names"],
        )
        return model_service.get_status()
    except FileNotFoundError as e:
        logger.error(f"Custom model file not found: {e}")
        return JSONResponse(status_code=404, content={"error": str(e)})
    except Exception as e:
        logger.error(f"Custom model load error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

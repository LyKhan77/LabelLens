from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services.sam import sam_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sam", tags=["sam"])


class LoadSamRequest(BaseModel):
    model: str | None = None


@router.get("/status")
async def sam_status():
    return sam_service.get_status()


@router.post("/load")
async def load_sam(req: LoadSamRequest | None = None):
    try:
        sam_service._ensure_loaded()
        return sam_service.get_status()
    except Exception as e:
        logger.error(f"SAM load failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/unload")
async def unload_sam():
    sam_service.unload()
    return {"unloaded": True}

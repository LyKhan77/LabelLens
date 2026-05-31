import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services.gpu import gpu_service
from backend.services.model import model_service
from backend.services.sam import sam_service

logger = logging.getLogger(__name__)
router = APIRouter()


class GpuConfigRequest(BaseModel):
    yoloe_device: str
    sam_device: str


class TrainingGpuConfigRequest(BaseModel):
    training_mode: str
    training_device: str
    visible_devices: str
    amp: bool


@router.get("/system/gpus")
async def list_gpus():
    try:
        gpus = gpu_service.detect_gpus()
        inference_config = gpu_service.get_inference_config()
        cuda_visible = os.getenv("CUDA_VISIBLE_DEVICES", "")
        return {
            "gpus": gpus,
            "cuda_visible_devices": cuda_visible,
            "inference_config": inference_config,
        }
    except Exception as e:
        logger.error("Failed to list GPUs: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.put("/system/gpu-config")
async def update_gpu_config(req: GpuConfigRequest):
    try:
        inference_config = gpu_service.save_inference_config(
            yoloe_device=req.yoloe_device,
            sam_device=req.sam_device,
        )

        yoloe_reloaded = False
        sam_unloaded = False

        # Hot-swap YOLOE if currently loaded
        if model_service.model is not None:
            model_service.set_device(req.yoloe_device)
            model_service.load_model(model_service.current_mode)
            yoloe_reloaded = True

        # Hot-swap SAM: unload so it lazily reloads on next use
        if sam_service.model is not None:
            sam_service.unload()
            sam_service.set_device(req.sam_device)
            sam_unloaded = True

        return {
            "inference_config": inference_config,
            "yoloe_reloaded": yoloe_reloaded,
            "sam_unloaded": sam_unloaded,
        }
    except (ValueError, RuntimeError) as e:
        logger.error("Invalid GPU config: %s", e)
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.error("Failed to update GPU config: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/system/gpus/training")
async def list_training_gpus():
    try:
        gpus = gpu_service.detect_gpus()
        training_config = gpu_service.get_training_config()
        return {
            "gpus": gpus,
            "training_config": training_config,
        }
    except Exception as e:
        logger.error("Failed to list training GPUs: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.put("/training/gpu-config")
async def update_training_gpu_config(req: TrainingGpuConfigRequest):
    try:
        training_config = gpu_service.save_training_config(
            training_mode=req.training_mode,
            training_device=req.training_device,
            visible_devices=req.visible_devices,
            amp=req.amp,
        )
        return {"training_config": training_config}
    except (ValueError, RuntimeError) as e:
        logger.error("Invalid training GPU config: %s", e)
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.error("Failed to update training GPU config: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

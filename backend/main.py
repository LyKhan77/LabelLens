from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CORS_ORIGINS
from backend.routers import dataset, detection, health, sam, stream, system, training
from backend.services.model import model_service
from backend.services.training import training_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    training_service.mark_interrupted_jobs_failed()
    yield


app = FastAPI(title="LabelLens API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(dataset.router, prefix="/api")
app.include_router(detection.router, prefix="/api")
app.include_router(stream.router)
app.include_router(training.router, prefix='/api')
app.include_router(sam.router, prefix="/api")
app.include_router(system.router, prefix="/api")

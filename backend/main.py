from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CORS_ORIGINS
from backend.routers import detection, health, stream
from backend.services.model import model_service


@asynccontextmanager
async def lifespan(app: FastAPI):
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
app.include_router(detection.router, prefix="/api")
app.include_router(stream.router)

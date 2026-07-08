"""
FastAPI application entry point.

Endpoints:
  GET  /api/risk-map        — GeoJSON FeatureCollection of slope-unit risk scores
  GET  /api/alerts          — alert history
  GET  /api/districts       — per-district summary stats
  POST /api/trigger         — manually trigger a prediction run (demo + daily cron)
  POST /api/sms/callback    — Africa's Talking inbound SMS webhook
  GET  /health              — uptime check (keeps Render awake via UptimeRobot)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import close_client, ensure_indexes
from .routes.alerts import router as alerts_router
from .routes.districts import router as districts_router
from .routes.predict import router as predict_router
from .routes.risk_map import router as risk_map_router
from .routes.trigger import router as trigger_router
from .services.pipeline import DataPipeline
from .services.scheduler import scheduler, setup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await ensure_indexes()
    pipeline = DataPipeline()
    setup_scheduler(pipeline)
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    await close_client()


app = FastAPI(
    title="Landslide Early Warning System — Rwanda Northern Province",
    version="1.0.0",
    description="ML-based daily landslide risk prediction and SMS alerting.",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(risk_map_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(districts_router, prefix="/api")
app.include_router(trigger_router, prefix="/api")
app.include_router(predict_router, prefix="/api")


@app.get("/health")
async def health():
    """Uptime check — pinged every 14 min by UptimeRobot to prevent Render sleep."""
    return {"status": "ok"}

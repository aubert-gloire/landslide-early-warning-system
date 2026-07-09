"""
POST /api/trigger  — manually trigger a prediction run (returns JSON summary).
GET  /api/trigger/stream — same pipeline but streams live log lines via SSE.
Used for demos, testing, and the GitHub Actions daily cron.
"""

import asyncio
import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import Settings, get_settings
from ..services.pipeline import DataPipeline

router = APIRouter()

_pipeline: DataPipeline | None = None


def get_pipeline() -> DataPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = DataPipeline()
    return _pipeline


class TriggerRequest(BaseModel):
    # Optional override rainfall for testing different scenarios
    override_daily_mm: float | None = None
    override_antecedent_5day_mm: float | None = None
    dry_run: bool = False  # If True, run pipeline but do not send SMS


@router.post("/trigger")
async def trigger_prediction(
    body: TriggerRequest = Body(default=TriggerRequest()),
    settings: Settings = Depends(get_settings),
):
    """
    Manually trigger a prediction run.
    Supports rainfall value overrides so you can demo different risk scenarios.
    Set dry_run=true to run the full pipeline without dispatching real SMS.
    """
    pipeline = get_pipeline()

    if body.override_daily_mm is not None or body.override_antecedent_5day_mm is not None:
        # Inject synthetic rainfall for demo purposes
        import geopandas as gpd
        import pandas as pd
        from datetime import datetime

        gpkg = settings.processed_path() / "slope_units.gpkg"
        if not gpkg.exists():
            raise HTTPException(status_code=503, detail="slope_units.gpkg not found — run setup first")

        slope_units = gpd.read_file(gpkg)
        rainfall_df = pd.DataFrame({
            "unit_id": slope_units["unit_id"],
            "date": pd.Timestamp.today().normalize(),
            "daily_mm": body.override_daily_mm or 0.0,
            "antecedent_5day_mm": body.override_antecedent_5day_mm or 0.0,
        })
        feature_df = pipeline.build_feature_matrix(rainfall_df)
        model = pipeline._get_model()
        predictions_df = model.predict(feature_df)

        if body.dry_run:
            return {
                "dry_run": True,
                "units_processed": len(predictions_df),
                "alerts_triggered": int(predictions_df["alert_triggered"].sum()),
                "predictions_sample": predictions_df.head(5)[
                    ["unit_id", "risk_probability", "alert_triggered"]
                ].to_dict(orient="records"),
            }

    try:
        summary = await pipeline.run_daily()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    return summary


@router.get("/trigger/stream")
async def trigger_stream():
    """
    SSE endpoint — runs the pipeline and streams live log lines to the browser.
    The frontend connects with EventSource and renders each line as it arrives.
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def log_fn(msg: str):
        await queue.put({"type": "log", "message": msg})

    async def run():
        try:
            pipeline = get_pipeline()
            result = await pipeline.run_daily(log_fn=log_fn)
            await queue.put({"type": "done", "result": result})
        except Exception as e:
            await queue.put({"type": "error", "message": str(e)})

    asyncio.create_task(run())

    async def generate():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                # SSE comment line — keeps Render's load balancer from dropping
                # the connection during the slow CHIRPS download (~60-90s)
                yield ": heartbeat\n\n"
                continue
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] in ("done", "error"):
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

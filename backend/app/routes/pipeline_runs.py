from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from ..database import get_db
from .auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/pipeline-runs")
async def get_pipeline_runs(
    limit: int = Query(default=30, le=400),
    skip:  int = Query(default=0),
):
    """Returns daily pipeline run history, newest first."""
    db = get_db()
    runs = (
        await db.pipeline_runs.find({})
        .sort("run_date", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )
    total = await db.pipeline_runs.count_documents({})
    for r in runs:
        r["_id"] = str(r["_id"])
    return JSONResponse(content=jsonable_encoder({"total": total, "runs": runs}))

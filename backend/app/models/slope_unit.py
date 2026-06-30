from typing import Any
from pydantic import BaseModel, Field


class SlopeUnit(BaseModel):
    unit_id: int
    district: str
    geometry: dict[str, Any]  # GeoJSON Polygon
    centroid_lat: float
    centroid_lon: float
    slope_angle: float | None = None
    aspect: float | None = None
    twi: float | None = None
    drainage_density: float | None = None
    ndvi: float | None = None
    soil_class: int = 4  # default: loam

    model_config = {"populate_by_name": True}

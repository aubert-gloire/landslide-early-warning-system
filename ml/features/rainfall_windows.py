"""
Antecedent-rainfall rolling-window math, shared by both rainfall paths in
backend/app/services/pipeline.py (Mongo-cache fast path and IMERG/CHIRPS
slow path) — previously duplicated inline in each.
"""

from __future__ import annotations

import pandas as pd

WINDOWS = [(3, "antecedent_3day_mm"), (5, "antecedent_5day_mm"), (10, "antecedent_10day_mm")]


def compute_antecedent_windows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add rolling antecedent-rainfall columns (3/5/10-day sums per unit_id)
    and the daily/5-day rainfall_intensity_ratio to a unit-day rainfall
    DataFrame.

    Requires columns: unit_id, date (sortable), daily_mm. Expects one row
    per unit per day — a gap in a unit's date sequence silently shrinks its
    rolling window instead of erroring, since min_periods=1 accepts partial
    windows (used deliberately so the first few days of a unit's history
    aren't NaN).
    """
    df = df.sort_values(["unit_id", "date"])
    for window, col in WINDOWS:
        df[col] = (
            df.groupby("unit_id")["daily_mm"]
            .transform(lambda s, w=window: s.rolling(w, min_periods=1).sum())
        )
    df["rainfall_intensity_ratio"] = (
        df["daily_mm"] / (df["antecedent_5day_mm"] + 1.0)
    ).round(4)
    return df
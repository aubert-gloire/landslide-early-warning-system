"""
Unit tests for ml/features/rainfall_windows.py — the antecedent-rainfall
rolling-window math used by both rainfall paths in DataPipeline.run_daily().
Previously inline and duplicated in pipeline.py with no test coverage.
"""

import pandas as pd

from ml.features.rainfall_windows import compute_antecedent_windows


def _make_df(unit_id, daily_values, start="2026-01-01"):
    dates = pd.date_range(start, periods=len(daily_values), freq="D")
    return pd.DataFrame({"unit_id": unit_id, "date": dates, "daily_mm": daily_values})


class TestAntecedentWindows:
    def test_rolling_sums_match_manual_calculation(self):
        df = _make_df(1, [10, 20, 30, 40, 50])
        out = compute_antecedent_windows(df)
        last = out.iloc[-1]
        assert last["antecedent_3day_mm"] == 30 + 40 + 50
        assert last["antecedent_5day_mm"] == 10 + 20 + 30 + 40 + 50
        # Window (10) is wider than the available history (5 days) —
        # min_periods=1 sums whatever exists rather than requiring 10 rows.
        assert last["antecedent_10day_mm"] == 10 + 20 + 30 + 40 + 50

    def test_partial_window_at_start_of_history_is_not_nan(self):
        df = _make_df(1, [10, 20, 30])
        out = compute_antecedent_windows(df)
        assert out.iloc[0]["antecedent_3day_mm"] == 10
        assert out.iloc[1]["antecedent_3day_mm"] == 10 + 20

    def test_units_do_not_leak_into_each_other(self):
        # The most likely real bug here: a rolling window computed without
        # grouping by unit_id would let unit 2's heavy rainfall bleed into
        # unit 1's antecedent sum just because the rows are adjacent.
        df = pd.concat([
            _make_df(1, [0, 0, 0]),
            _make_df(2, [100, 100, 100]),
        ], ignore_index=True)
        out = compute_antecedent_windows(df)
        unit1 = out[out["unit_id"] == 1]
        assert (unit1["antecedent_3day_mm"] == 0).all()

    def test_rainfall_intensity_ratio_formula(self):
        df = _make_df(1, [10, 0, 0, 0, 40])
        out = compute_antecedent_windows(df)
        last = out.iloc[-1]
        expected = round(40 / (last["antecedent_5day_mm"] + 1.0), 4)
        assert last["rainfall_intensity_ratio"] == expected

    def test_zero_rainfall_does_not_divide_by_zero(self):
        df = _make_df(1, [0, 0, 0])
        out = compute_antecedent_windows(df)
        assert out["rainfall_intensity_ratio"].notna().all()
        assert (out["rainfall_intensity_ratio"] == 0).all()

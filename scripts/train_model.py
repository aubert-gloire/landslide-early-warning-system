"""
Train the Random Forest model on the prepared feature matrix.

Prerequisites:
  - scripts/setup_db.py all must have run successfully
  - data/processed/training_matrix.parquet must exist (built here if not)

Usage:
  python scripts/train_model.py
  python scripts/train_model.py --backtest   # also run backtest after training
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest", action="store_true", help="Run backtesting after training")
    args = parser.parse_args()

    from ml.pipeline.slope_units import SlopeUnitGenerator
    from ml.pipeline.labels import LabelLoader
    from ml.features.matrix import FeatureMatrixBuilder
    from ml.model.train import train

    processed_dir = ROOT / "data/processed"
    labels_dir = ROOT / "data/labels"
    artifacts_dir = ROOT / "ml/artifacts"

    gen = SlopeUnitGenerator(ROOT / "data/raw", processed_dir)
    slope_units = gen.load()

    # Build feature matrix if not already built
    matrix_path = processed_dir / "training_matrix.parquet"
    if not matrix_path.exists():
        logger.info("Building training matrix...")
        loader = LabelLoader(labels_dir, slope_units)
        labels_df = loader.merge()
        labels_df = loader.assign_slope_units(labels_df)
        logger.info("Labels with slope units: %d rows", len(labels_df))

        builder = FeatureMatrixBuilder(processed_dir)
        builder.build_training_matrix(slope_units, labels_df)
    else:
        logger.info("Training matrix already exists at %s", matrix_path)

    # Train
    metadata = train(matrix_path=matrix_path, artifacts_dir=artifacts_dir)

    logger.info("Feature importances:")
    for feat, imp in list(metadata.get("feature_importances", {}).items())[:5]:
        logger.info("  %-30s %.4f", feat, imp)

    # Backtest
    if args.backtest:
        logger.info("Running backtest...")
        import joblib
        from ml.model.evaluate import Backtester
        import json

        model = joblib.load(artifacts_dir / "rf_model.joblib")
        with open(artifacts_dir / "model_metadata.json") as f:
            meta = json.load(f)

        backtester = Backtester(
            model,
            feature_cols=meta["feature_cols"],
            alert_threshold=meta["production_threshold"],
        )
        report = backtester.run(
            matrix_path=matrix_path,
            slope_units_gdf=slope_units,
            output_path=ROOT / "ml/artifacts/backtest_report.csv",
        )
        print("\nBacktest Report:")
        print(report[["name", "max_probability", "alert_triggered", "status"]].to_string(index=False))


if __name__ == "__main__":
    main()

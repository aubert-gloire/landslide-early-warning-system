"""Backward-compatibility shim — import XGBModel from xgb_model instead."""
from .xgb_model import XGBModel

RFModel = XGBModel  # legacy alias kept so old scripts don't crash

"""
Optimization Models Module - ML Predictors
"""

import importlib
from typing import List

_LAZY_MODULES = {
    "catboost_trainer",
    "lightgbm_trainer",
    "model_logger",
    "train_enhanced",
    "xgboost_trainer",
    "xgboost_trainer_v2",
}


def __getattr__(name: str):
    if name in _LAZY_MODULES:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> List[str]:
    return sorted(list(globals().keys()) + list(_LAZY_MODULES))


__all__ = sorted(_LAZY_MODULES)

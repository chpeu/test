"""Utilities for extracting live prices from mixed data structures."""
from __future__ import annotations

from typing import Any, Optional, Tuple


PRICE_PRIORITY = (
    "markPrice",
    "fairPrice",
    "indexPrice",
    "price",
    "referencePrice",
    "lastPrice",
    "close",
    "value",
)


def _to_float(value: Any) -> Optional[float]:
    """Convert a value to float when possible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_price_with_source(price_data: Any) -> Tuple[Optional[float], Optional[str]]:
    """Return the preferred price along with the key it came from."""
    if price_data is None:
        return (None, None)

    if isinstance(price_data, dict):
        for key in PRICE_PRIORITY:
            candidate = _to_float(price_data.get(key))
            if candidate is not None and candidate > 0:
                return (candidate, key)
        return (None, None)

    numeric_value = _to_float(price_data)
    return (numeric_value, None) if numeric_value is not None else (None, None)


def get_preferred_price(price_data: Any, fallback: Optional[float] = None) -> Optional[float]:
    """Return only the preferred price value, falling back if necessary."""
    price, _ = get_price_with_source(price_data)
    return price if price is not None else fallback

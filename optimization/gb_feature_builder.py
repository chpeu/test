"""Centralized GradientBoosting feature builder.

Construit exactement les 20 features attendues par le modèle optimisé.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_GB_FEATURE_NAMES = [
    "di_minus_1m",
    "di_gap_1m",
    "bb_distance_to_lower_5m",
    "bb_distance_to_upper_5m",
    "ema_trend_strength_1m",
    "macd_hist_prev_5m",
    "ema_trend_strength_5m",
    "rsi_change_1m",
    "rsi_prev_1m",
    "rsi_5m",
    "hour",
    "volume_spike_5m",
    "ema_diff_pct_1m",
    "momentum_divergence",
    "bb_width_1m",
    "delta_volume",
    "macd_hist_5m",
    "atr_pct_5m",
    "di_gap_5m",
    "bb_distance_to_lower_1m",
]


def _resolve_feature_names() -> list[str]:
    metadata_path = Path(__file__).resolve().parent / "saved_models" / "gradient_boosting_optimized_metadata.json"
    try:
        with metadata_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        feature_names = payload.get("feature_names")
        if isinstance(feature_names, list) and feature_names:
            return [str(name) for name in feature_names]
    except Exception as exc:  # pragma: no cover - fallback only
        logger.debug("Unable to read GB metadata (%s), using defaults", exc)
    return list(_DEFAULT_GB_FEATURE_NAMES)


GB_FEATURE_NAMES = _resolve_feature_names()


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return float(value)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _coalesce(*values: Any) -> Optional[float]:
    for value in values:
        candidate = _safe_float(value)
        if candidate is not None:
            return candidate
    return None


def _unwrap_price(value: Any) -> Optional[float]:
    if isinstance(value, dict):
        for key in ("price", "lastPrice", "close", "value"):
            candidate = _safe_float(value.get(key))
            if candidate is not None:
                return candidate
        return None
    return _safe_float(value)


def _resolve_scan_price(best_setup: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[float]:
    for src in (best_setup, analysis):
        if not isinstance(src, dict):
            continue
        for key in ("price", "scan_price", "entry_price", "lastPrice", "close"):
            candidate = _unwrap_price(src.get(key))
            if candidate is not None:
                return candidate
        market_data = src.get("market_data")
        candidate = _unwrap_price(market_data.get("price")) if isinstance(market_data, dict) else None
        if candidate is not None:
            return candidate
        for nested_key in ("analysis_1m", "analysis_5m"):
            nested = src.get(nested_key)
            if isinstance(nested, dict):
                candidate = _unwrap_price(nested.get("price"))
                if candidate is not None:
                    return candidate
    return None


def _merge_indicators_from_raw(
    indicators: Dict[str, Any],
    raw_features: Dict[str, Any],
    suffix: str,
) -> Dict[str, Any]:
    aliases = {
        "macd_momentum": "macd_hist",
        "macd_histogram": "macd_hist",
        "volume_ratio": "volume_spike",
        "volumeSpike": "volume_spike",
    }
    if not isinstance(raw_features, dict):
        return indicators
    for key, value in raw_features.items():
        if not isinstance(key, str) or not key.endswith(suffix):
            continue
        base_key = key[: -len(suffix)]
        base_key = aliases.get(base_key, base_key)
        if indicators.get(base_key) is None:
            indicators[base_key] = value
    return indicators


def build_gb_features(
    best_setup: Optional[Dict[str, Any]] = None,
    analysis: Optional[Dict[str, Any]] = None,
    scalability_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Construire exactement les 20 features GB optimisées.

    Args:
        best_setup: Dict de setup (avec indicators_1m/5m ou features *_1m/_5m).
        analysis: Dict d'analyse complet (optionnel).
        scalability_data: Dict scalabilité (optionnel, pour delta_volume).

    Returns:
        Dict avec exactement les 20 features attendues par le modèle GB.
    """
    best_setup = best_setup if isinstance(best_setup, dict) else {}
    analysis = analysis if isinstance(analysis, dict) else {}
    scalability_data = scalability_data if isinstance(scalability_data, dict) else {}

    raw_features: Dict[str, Any] = {}
    raw_features.update(analysis)
    raw_features.update(best_setup)

    indicators_1m: Dict[str, Any] = {}
    indicators_5m: Dict[str, Any] = {}

    for source in (best_setup, analysis):
        if not isinstance(source, dict):
            continue
        if not indicators_1m:
            candidate = source.get("indicators_1m")
            if isinstance(candidate, dict):
                indicators_1m = dict(candidate)
        if not indicators_5m:
            candidate = source.get("indicators_5m")
            if isinstance(candidate, dict):
                indicators_5m = dict(candidate)

    indicators_1m = _merge_indicators_from_raw(indicators_1m, raw_features, "_1m")
    indicators_5m = _merge_indicators_from_raw(indicators_5m, raw_features, "_5m")

    scan_price = _resolve_scan_price(best_setup, analysis)

    di_minus_1m = _coalesce(indicators_1m.get("di_minus"), raw_features.get("di_minus_1m"))
    di_plus_1m = _coalesce(indicators_1m.get("di_plus"), raw_features.get("di_plus_1m"))
    di_gap_1m = _coalesce(indicators_1m.get("di_gap"), raw_features.get("di_gap_1m"))
    if di_gap_1m is None and di_plus_1m is not None and di_minus_1m is not None:
        di_gap_1m = di_plus_1m - di_minus_1m

    bb_distance_to_lower_5m = _coalesce(
        indicators_5m.get("bb_distance_to_lower"),
        raw_features.get("bb_distance_to_lower_5m"),
    )
    bb_distance_to_upper_5m = _coalesce(
        indicators_5m.get("bb_distance_to_upper"),
        raw_features.get("bb_distance_to_upper_5m"),
    )
    if bb_distance_to_lower_5m is None or bb_distance_to_upper_5m is None:
        bb_lower_5m = _coalesce(indicators_5m.get("bb_lower"), raw_features.get("bb_lower_5m"))
        bb_upper_5m = _coalesce(indicators_5m.get("bb_upper"), raw_features.get("bb_upper_5m"))
        if scan_price is not None and bb_lower_5m is not None and bb_distance_to_lower_5m is None:
            bb_distance_to_lower_5m = max(0.0, scan_price - bb_lower_5m)
        if scan_price is not None and bb_upper_5m is not None and bb_distance_to_upper_5m is None:
            bb_distance_to_upper_5m = max(0.0, bb_upper_5m - scan_price)

    ema_diff_pct_1m = _coalesce(indicators_1m.get("ema_diff_pct"), raw_features.get("ema_diff_pct_1m"))
    if ema_diff_pct_1m is None:
        ema9_1m = _coalesce(indicators_1m.get("ema9"), raw_features.get("ema_9_1m"))
        ema21_1m = _coalesce(indicators_1m.get("ema21"), raw_features.get("ema_21_1m"))
        if ema9_1m is not None and ema21_1m:
            ema_diff_pct_1m = ((ema9_1m - ema21_1m) / ema21_1m) * 100

    ema_diff_pct_5m = _coalesce(indicators_5m.get("ema_diff_pct"), raw_features.get("ema_diff_pct_5m"))
    if ema_diff_pct_5m is None:
        ema9_5m = _coalesce(indicators_5m.get("ema9"), raw_features.get("ema_9_5m"))
        ema21_5m = _coalesce(indicators_5m.get("ema21"), raw_features.get("ema_21_5m"))
        if ema9_5m is not None and ema21_5m:
            ema_diff_pct_5m = ((ema9_5m - ema21_5m) / ema21_5m) * 100

    ema_trend_strength_1m = _coalesce(indicators_1m.get("ema_trend_strength"), raw_features.get("ema_trend_strength_1m"))
    if ema_trend_strength_1m is None and ema_diff_pct_1m is not None:
        ema_trend_strength_1m = abs(ema_diff_pct_1m)

    ema_trend_strength_5m = _coalesce(indicators_5m.get("ema_trend_strength"), raw_features.get("ema_trend_strength_5m"))
    if ema_trend_strength_5m is None and ema_diff_pct_5m is not None:
        ema_trend_strength_5m = abs(ema_diff_pct_5m)

    macd_hist_5m = _coalesce(
        indicators_5m.get("macd_hist"),
        raw_features.get("macd_hist_5m"),
        raw_features.get("macd_momentum_5m"),
    )
    macd_hist_prev_5m = _coalesce(
        indicators_5m.get("macd_hist_prev"),
        raw_features.get("macd_hist_prev_5m"),
    )
    if macd_hist_prev_5m is None and macd_hist_5m is not None:
        macd_hist_prev_5m = macd_hist_5m

    rsi_1m = _coalesce(indicators_1m.get("rsi"), raw_features.get("rsi_1m"))
    rsi_prev_1m = _coalesce(indicators_1m.get("rsi_prev"), raw_features.get("rsi_prev_1m"))
    if rsi_prev_1m is None and rsi_1m is not None:
        rsi_prev_1m = rsi_1m

    rsi_change_1m = _coalesce(indicators_1m.get("rsi_change"), raw_features.get("rsi_change_1m"))
    if rsi_change_1m is None and rsi_1m is not None and rsi_prev_1m is not None:
        rsi_change_1m = rsi_1m - rsi_prev_1m

    rsi_5m = _coalesce(indicators_5m.get("rsi"), raw_features.get("rsi_5m"))

    volume_spike_5m = _coalesce(
        indicators_5m.get("volume_spike"),
        indicators_5m.get("volume_ratio"),
        indicators_5m.get("volumeSpike"),
        raw_features.get("volume_spike_5m"),
        raw_features.get("volume_ratio_5m"),
    )

    momentum_divergence = _coalesce(raw_features.get("momentum_divergence"))
    if momentum_divergence is None:
        macd_hist_1m = _coalesce(indicators_1m.get("macd_hist"), raw_features.get("macd_hist_1m"), raw_features.get("macd_momentum_1m"))
        macd_hist_5m_val = macd_hist_5m
        if rsi_1m is not None and macd_hist_1m is not None:
            momentum_1m = (rsi_1m / 100) * math.tanh(macd_hist_1m)
        else:
            momentum_1m = 0.0
        if rsi_5m is not None and macd_hist_5m_val is not None:
            momentum_5m = (rsi_5m / 100) * math.tanh(macd_hist_5m_val)
        else:
            momentum_5m = 0.0
        momentum_divergence = momentum_1m - momentum_5m

    bb_width_1m = _coalesce(indicators_1m.get("bb_width"), raw_features.get("bb_width_1m"))
    if bb_width_1m is None:
        bb_upper_1m = _coalesce(indicators_1m.get("bb_upper"), raw_features.get("bb_upper_1m"))
        bb_lower_1m = _coalesce(indicators_1m.get("bb_lower"), raw_features.get("bb_lower_1m"))
        if bb_upper_1m is not None and bb_lower_1m is not None:
            bb_width_1m = bb_upper_1m - bb_lower_1m

    delta_volume = _coalesce(
        scalability_data.get("delta_volume"),
        scalability_data.get("deltaVolume"),
        raw_features.get("delta_volume"),
    )
    if delta_volume is None:
        bid_vol = _coalesce(
            scalability_data.get("bid_vol"),
            scalability_data.get("bidVol"),
            raw_features.get("bid_vol"),
            raw_features.get("bidVol"),
        )
        ask_vol = _coalesce(
            scalability_data.get("ask_vol"),
            scalability_data.get("askVol"),
            raw_features.get("ask_vol"),
            raw_features.get("askVol"),
        )
        if bid_vol is not None and ask_vol is not None:
            delta_volume = bid_vol - ask_vol

    atr_pct_5m = _coalesce(indicators_5m.get("atr_pct"), raw_features.get("atr_pct_5m"))

    di_plus_5m = _coalesce(indicators_5m.get("di_plus"), raw_features.get("di_plus_5m"))
    di_minus_5m = _coalesce(indicators_5m.get("di_minus"), raw_features.get("di_minus_5m"))
    di_gap_5m = _coalesce(indicators_5m.get("di_gap"), raw_features.get("di_gap_5m"))
    if di_gap_5m is None and di_plus_5m is not None and di_minus_5m is not None:
        di_gap_5m = di_plus_5m - di_minus_5m

    bb_distance_to_lower_1m = _coalesce(
        indicators_1m.get("bb_distance_to_lower"),
        raw_features.get("bb_distance_to_lower_1m"),
    )
    if bb_distance_to_lower_1m is None:
        bb_lower_1m = _coalesce(indicators_1m.get("bb_lower"), raw_features.get("bb_lower_1m"))
        if scan_price is not None and bb_lower_1m is not None:
            bb_distance_to_lower_1m = max(0.0, scan_price - bb_lower_1m)

    now_hour = datetime.now().hour
    hour_value = _coalesce(raw_features.get("hour"))
    hour_value = hour_value if hour_value is not None else float(now_hour)

    feature_values = {
        "di_minus_1m": _safe_float(di_minus_1m) or 0.0,
        "di_gap_1m": _safe_float(di_gap_1m) or 0.0,
        "bb_distance_to_lower_5m": _safe_float(bb_distance_to_lower_5m) or 0.0,
        "bb_distance_to_upper_5m": _safe_float(bb_distance_to_upper_5m) or 0.0,
        "ema_trend_strength_1m": _safe_float(ema_trend_strength_1m) or 0.0,
        "macd_hist_prev_5m": _safe_float(macd_hist_prev_5m) or 0.0,
        "ema_trend_strength_5m": _safe_float(ema_trend_strength_5m) or 0.0,
        "rsi_change_1m": _safe_float(rsi_change_1m) or 0.0,
        "rsi_prev_1m": _safe_float(rsi_prev_1m) or 0.0,
        "rsi_5m": _safe_float(rsi_5m) or 0.0,
        "hour": _safe_float(hour_value) or 0.0,
        "volume_spike_5m": _safe_float(volume_spike_5m) or 0.0,
        "ema_diff_pct_1m": _safe_float(ema_diff_pct_1m) or 0.0,
        "momentum_divergence": _safe_float(momentum_divergence) or 0.0,
        "bb_width_1m": _safe_float(bb_width_1m) or 0.0,
        "delta_volume": _safe_float(delta_volume) or 0.0,
        "macd_hist_5m": _safe_float(macd_hist_5m) or 0.0,
        "atr_pct_5m": _safe_float(atr_pct_5m) or 0.0,
        "di_gap_5m": _safe_float(di_gap_5m) or 0.0,
        "bb_distance_to_lower_1m": _safe_float(bb_distance_to_lower_1m) or 0.0,
    }

    return {name: feature_values.get(name, 0.0) for name in GB_FEATURE_NAMES}

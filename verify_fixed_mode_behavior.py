#!/usr/bin/env python3
"""
Vérification comportement mode FIXE - cas principaux (TP/SL, BE, Trailing linéaire)
"""
from __future__ import annotations

import asyncio
import math
import os
import time
from copy import deepcopy

# Désactiver PostgreSQL logger pour ce script
os.environ["POSTGRES_ENABLED"] = "false"

from config import TRADING_CONFIG
from core.position_manager import PositionManager, PositionConfig


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def approx_equal(actual: float, expected: float, tolerance: float = 1e-6) -> bool:
    return abs(actual - expected) <= tolerance


def run_check(manager: PositionManager, price: float) -> str | None:
    return asyncio.run(manager.check_position(price))


def pnl_from_price(entry: float, price: float, direction: str) -> float:
    if direction == "LONG":
        return ((price - entry) / entry) * 100
    return ((entry - price) / entry) * 100


def price_for_pnl(entry: float, pnl_pct: float, direction: str) -> float:
    if direction == "LONG":
        return entry * (1 + pnl_pct / 100)
    return entry * (1 - pnl_pct / 100)


def calc_trailing_distance(pnl_pct: float, trigger: float, min_dist: float, max_dist: float, cap: float) -> float:
    if pnl_pct <= trigger:
        return min_dist
    denominator = cap - trigger
    if denominator > 0:
        x = min(1.0, max(0.0, (pnl_pct - trigger) / denominator))
    else:
        x = 1.0
    return min_dist + (max_dist - min_dist) * x


def calc_trailing_sl(entry: float, price: float, direction: str, distance: float) -> float:
    if direction == "LONG":
        return round(price * (1 - distance / 100), 8)
    return round(price * (1 + distance / 100), 8)


def sync_trailing_stop_trigger() -> None:
    trailing_stop = dict(TRADING_CONFIG.get("trailing_stop", {}) or {})
    if "trailing_trigger_pnl" in TRADING_CONFIG:
        trailing_stop["trigger_pnl"] = TRADING_CONFIG["trailing_trigger_pnl"]
    TRADING_CONFIG["trailing_stop"] = trailing_stop


def disable_early_invalidation() -> None:
    early = dict(TRADING_CONFIG.get("early_invalidation", {}) or {})
    early["enabled"] = False
    TRADING_CONFIG["early_invalidation"] = early


def build_manager() -> PositionManager:
    config = PositionConfig(use_atr=False)
    return PositionManager(config)


def prepare_manager(manager: PositionManager, symbol: str) -> None:
    manager.market_info_cache[symbol] = {
        "precision": {"price": 8},
        "tickSize": 0.01
    }
    manager._last_setup = {
        "indicators_1m": {},
        "indicators_5m": {},
        "totalScore": None,
        "score_total": None
    }


def set_base_fixed_config() -> None:
    TRADING_CONFIG.update(
        {
            "tp_sl_mode": "FIXE",
            "tp_percent": 0.6,
            "sl_percent": 0.25,
            "break_even_trigger": 0.3,
            "partial_tp_percent": 50.0,
            "partial_tp_be_lock_in_pct": 0.0,
            "trailing_enabled": True,
            "trailing_trigger_pnl": 0.2,
            "trailing_min_distance": 0.1,
            "trailing_max_distance": 0.3,
            "trailing_pnl_cap": 0.6,
            "gb_filter_enabled": False,
            "invert_signals": False,
        }
    )
    sync_trailing_stop_trigger()
    disable_early_invalidation()


def test_fixed_tp_sl_long_short() -> None:
    set_base_fixed_config()
    manager = build_manager()
    prepare_manager(manager, "BTC_USDT")
    long_pos = manager.open_position("BTC_USDT", "LONG", 100.0, 100.0)
    expect(long_pos is not None, "Position LONG non créée")
    expect(approx_equal(long_pos.sl, 99.75), f"SL LONG attendu 99.75, obtenu {long_pos.sl}")
    expect(approx_equal(long_pos.tp, 100.6), f"TP LONG attendu 100.6, obtenu {long_pos.tp}")

    prepare_manager(manager, "BTC_USDT")
    short_pos = manager.open_position("BTC_USDT", "SHORT", 100.0, 100.0)
    expect(short_pos is not None, "Position SHORT non créée")
    expect(approx_equal(short_pos.sl, 100.25), f"SL SHORT attendu 100.25, obtenu {short_pos.sl}")
    expect(approx_equal(short_pos.tp, 99.4), f"TP SHORT attendu 99.4, obtenu {short_pos.tp}")


def test_trailing_disabled_no_move() -> None:
    set_base_fixed_config()
    TRADING_CONFIG["trailing_enabled"] = False
    TRADING_CONFIG["break_even_trigger"] = 2.0
    TRADING_CONFIG["tp_percent"] = 5.0
    sync_trailing_stop_trigger()
    manager = build_manager()
    prepare_manager(manager, "BTC_USDT")
    pos = manager.open_position("BTC_USDT", "LONG", 100.0, 100.0)
    original_sl = pos.sl
    run_check(manager, price_for_pnl(100.0, 0.4, "LONG"))
    expect(approx_equal(manager.active_position.sl, original_sl), "SL ne doit pas bouger si trailing désactivé")
    expect(not manager.active_position.trailing_activated, "Trailing ne doit pas s'activer si trailing_enabled=False")


def test_trailing_below_trigger() -> None:
    set_base_fixed_config()
    TRADING_CONFIG["break_even_trigger"] = 2.0
    TRADING_CONFIG["tp_percent"] = 5.0
    manager = build_manager()
    prepare_manager(manager, "BTC_USDT")
    pos = manager.open_position("BTC_USDT", "LONG", 100.0, 100.0)
    original_sl = pos.sl
    run_check(manager, price_for_pnl(100.0, 0.19, "LONG"))
    expect(approx_equal(manager.active_position.sl, original_sl), "SL ne doit pas bouger sous le trigger")
    expect(not manager.active_position.trailing_activated, "Trailing ne doit pas s'activer sous le trigger")


def test_trailing_linear_progression_long() -> None:
    set_base_fixed_config()
    TRADING_CONFIG["break_even_trigger"] = 2.0
    TRADING_CONFIG["tp_percent"] = 5.0
    manager = build_manager()
    prepare_manager(manager, "BTC_USDT")
    manager.open_position("BTC_USDT", "LONG", 100.0, 100.0)

    # PnL = trigger (0.2%) -> min distance
    price = price_for_pnl(100.0, 0.2, "LONG")
    run_check(manager, price)
    pnl_pct = pnl_from_price(100.0, price, "LONG")
    distance = calc_trailing_distance(
        pnl_pct,
        TRADING_CONFIG["trailing_trigger_pnl"],
        TRADING_CONFIG["trailing_min_distance"],
        TRADING_CONFIG["trailing_max_distance"],
        TRADING_CONFIG["trailing_pnl_cap"]
    )
    expected_sl = calc_trailing_sl(100.0, price, "LONG", distance)
    expect(approx_equal(manager.active_position.sl, expected_sl), "Trailing min distance incorrect")

    # PnL = 0.4% -> distance intermédiaire 0.2%
    price = price_for_pnl(100.0, 0.4, "LONG")
    run_check(manager, price)
    pnl_pct = pnl_from_price(100.0, price, "LONG")
    distance = calc_trailing_distance(
        pnl_pct,
        TRADING_CONFIG["trailing_trigger_pnl"],
        TRADING_CONFIG["trailing_min_distance"],
        TRADING_CONFIG["trailing_max_distance"],
        TRADING_CONFIG["trailing_pnl_cap"]
    )
    expected_sl = calc_trailing_sl(100.0, price, "LONG", distance)
    expect(approx_equal(manager.active_position.sl, expected_sl), "Trailing distance intermédiaire incorrect")

    # PnL = 0.8% -> distance max 0.3%
    price = price_for_pnl(100.0, 0.8, "LONG")
    run_check(manager, price)
    pnl_pct = pnl_from_price(100.0, price, "LONG")
    distance = calc_trailing_distance(
        pnl_pct,
        TRADING_CONFIG["trailing_trigger_pnl"],
        TRADING_CONFIG["trailing_min_distance"],
        TRADING_CONFIG["trailing_max_distance"],
        TRADING_CONFIG["trailing_pnl_cap"]
    )
    expected_sl = calc_trailing_sl(100.0, price, "LONG", distance)
    expect(approx_equal(manager.active_position.sl, expected_sl), "Trailing distance max incorrect")


def test_trailing_cap_edge_case() -> None:
    set_base_fixed_config()
    TRADING_CONFIG["trailing_pnl_cap"] = 0.2  # cap == trigger
    TRADING_CONFIG["break_even_trigger"] = 2.0
    TRADING_CONFIG["tp_percent"] = 5.0
    sync_trailing_stop_trigger()
    manager = build_manager()
    prepare_manager(manager, "BTC_USDT")
    manager.open_position("BTC_USDT", "LONG", 100.0, 100.0)

    price = price_for_pnl(100.0, 0.25, "LONG")
    run_check(manager, price)
    expected_sl = calc_trailing_sl(100.0, price, "LONG", TRADING_CONFIG["trailing_max_distance"])
    expect(approx_equal(manager.active_position.sl, expected_sl), "Cap==trigger devrait utiliser max distance")


def test_trailing_stop_exit_ts() -> None:
    set_base_fixed_config()
    TRADING_CONFIG["break_even_trigger"] = 2.0
    TRADING_CONFIG["tp_percent"] = 5.0
    manager = build_manager()
    prepare_manager(manager, "BTC_USDT")
    manager.open_position("BTC_USDT", "LONG", 100.0, 100.0)

    run_check(manager, price_for_pnl(100.0, 0.4, "LONG"))
    sl_at_trail = manager.active_position.sl
    reason = run_check(manager, sl_at_trail)
    expect(reason == "TS", f"Sortie attendue TS, obtenu {reason}")


def test_partial_tp_break_even_only() -> None:
    set_base_fixed_config()
    TRADING_CONFIG["trailing_enabled"] = False
    TRADING_CONFIG["tp_percent"] = 5.0
    manager = build_manager()
    prepare_manager(manager, "BTC_USDT")
    manager.open_position("BTC_USDT", "LONG", 100.0, 100.0)

    run_check(manager, price_for_pnl(100.0, 0.31, "LONG"))
    pos = manager.active_position
    expect(pos.partial_tp_sold, "TP partiel devrait être déclenché")
    expect(pos.break_even_set, "Break-even devrait être activé")
    expect(approx_equal(pos.sl, 100.0), f"SL BE attendu 100.0, obtenu {pos.sl}")


def test_partial_tp_with_trailing() -> None:
    set_base_fixed_config()
    TRADING_CONFIG["tp_percent"] = 5.0
    manager = build_manager()
    prepare_manager(manager, "BTC_USDT")
    manager.open_position("BTC_USDT", "LONG", 100.0, 100.0)

    price = price_for_pnl(100.0, 0.31, "LONG")
    run_check(manager, price)
    pos = manager.active_position
    expect(pos.partial_tp_sold, "TP partiel devrait être déclenché")
    expect(pos.trailing_activated, "Trailing devrait être activé après TP partiel")
    pnl_pct = pnl_from_price(100.0, price, "LONG")
    distance = calc_trailing_distance(
        pnl_pct,
        TRADING_CONFIG["trailing_trigger_pnl"],
        TRADING_CONFIG["trailing_min_distance"],
        TRADING_CONFIG["trailing_max_distance"],
        TRADING_CONFIG["trailing_pnl_cap"]
    )
    expected_sl = calc_trailing_sl(100.0, price, "LONG", distance)
    expect(approx_equal(pos.sl, expected_sl), "SL trailing après TP partiel incorrect")


def test_trailing_short() -> None:
    set_base_fixed_config()
    TRADING_CONFIG["break_even_trigger"] = 2.0
    TRADING_CONFIG["tp_percent"] = 5.0
    manager = build_manager()
    prepare_manager(manager, "BTC_USDT")
    manager.open_position("BTC_USDT", "SHORT", 100.0, 100.0)

    price = price_for_pnl(100.0, 0.2, "SHORT")
    run_check(manager, price)
    pnl_pct = pnl_from_price(100.0, price, "SHORT")
    distance = calc_trailing_distance(
        pnl_pct,
        TRADING_CONFIG["trailing_trigger_pnl"],
        TRADING_CONFIG["trailing_min_distance"],
        TRADING_CONFIG["trailing_max_distance"],
        TRADING_CONFIG["trailing_pnl_cap"]
    )
    expected_sl = calc_trailing_sl(100.0, price, "SHORT", distance)
    expect(approx_equal(manager.active_position.sl, expected_sl), "Trailing SHORT min distance incorrect")


def main() -> None:
    original_config = deepcopy(TRADING_CONFIG)
    try:
        test_fixed_tp_sl_long_short()
        test_trailing_disabled_no_move()
        test_trailing_below_trigger()
        test_trailing_linear_progression_long()
        test_trailing_cap_edge_case()
        test_trailing_stop_exit_ts()
        test_partial_tp_break_even_only()
        test_partial_tp_with_trailing()
        test_trailing_short()
        print("✅ Toutes les vérifications FIXE ont réussi")
    finally:
        TRADING_CONFIG.clear()
        TRADING_CONFIG.update(original_config)


if __name__ == "__main__":
    main()

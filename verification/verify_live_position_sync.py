"""Verification loop to compare bot position sizes vs live MEXC data.

Run:
    python verification/verify_live_position_sync.py

Requirements: valid MEXC API key/secret or browser token configured in config_overrides.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trading.live_order_manager_futures import LiveOrderManagerFutures
from config import TRADING_CONFIG

LOG_FILE = Path("logs/verify_live_position_sync.jsonl")


def build_manager() -> LiveOrderManagerFutures:
    api_key = os.environ.get("MEXC_API_KEY") or TRADING_CONFIG.get("mexc_api_key")
    api_secret = os.environ.get("MEXC_API_SECRET") or TRADING_CONFIG.get("mexc_api_secret")
    browser_token = os.environ.get("MEXC_BROWSER_TOKEN") or TRADING_CONFIG.get("mexc_browser_token")

    if not browser_token:
        raise RuntimeError("MEXC browser token requis pour le mode bypass")

    manager = LiveOrderManagerFutures(
        api_key=api_key,
        api_secret=api_secret,
        browser_token=browser_token,
        dry_run=False,
        use_bypass=True,
        enable_circuit_breaker=False,
    )
    return manager


def get_active_symbol() -> Optional[str]:
    state_path = Path("data/runtime_state.json")
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text())
        position = data.get("active_position")
        if not position:
            return None
        return position.get("symbol")
    except Exception:
        return None


def log_result(payload: Dict[str, Any]) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> None:
    symbol = get_active_symbol()
    if not symbol:
        print("❌ Aucune position active détectée dans runtime_state.json")
        return

    manager = build_manager()
    print(f"🔍 Vérification live pour {symbol}")

    expected_contracts = None
    expected_size_usdt = None

    try:
        state = json.loads(Path("data/runtime_state.json").read_text())
        position = state.get("active_position") or {}
        expected_contracts = position.get("position_size_contracts")
        expected_size_usdt = position.get("size")
    except Exception:
        pass

    samples = []
    for i in range(3):
        live = manager._verify_position_size(symbol, reference_price=0, retries=1, delay_sec=0)
        payload = {
            "timestamp": time.time(),
            "symbol": symbol,
            "expected_contracts": expected_contracts,
            "expected_size_usdt": expected_size_usdt,
            "live_contracts": live.get("contracts") if live else None,
            "live_entry_price": live.get("entry_price") if live else None,
            "live_size_usdt": live.get("size_usdt") if live else None,
            "iteration": i + 1,
        }
        log_result(payload)
        samples.append(payload)
        print(f"[{i+1}/3] live_contracts={payload['live_contracts']} | live_size={payload['live_size_usdt']}")
        time.sleep(2)

    mismatches = [
        s for s in samples
        if s["live_contracts"] is not None and expected_contracts is not None
        and abs(s["live_contracts"] - expected_contracts) > 1e-6
    ]

    if mismatches:
        print("⚠️ Écart détecté entre le bot et MEXC. Voir logs/verify_live_position_sync.jsonl")
    else:
        print("✅ Taille de position alignée avec MEXC")


if __name__ == "__main__":
    main()

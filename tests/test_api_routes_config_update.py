import types
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import core.state_manager as state_manager
from api.routes.config import perform_config_update


class _DummyState:
    def __init__(self, pos_cfg=None, pos_mgr=None, ws_mgr=None):
        self._pos_cfg = pos_cfg
        self._pos_mgr = pos_mgr
        self._ws_mgr = ws_mgr

    def get_position_config(self):
        return self._pos_cfg

    def get_position_manager(self):
        return self._pos_mgr

    def get_ws_manager(self):
        return self._ws_mgr


@pytest.fixture()
def _patched_deps(monkeypatch: pytest.MonkeyPatch):
    import config as config_module

    trading_config = {
        "tp_sl_mode": "FIXE",
        "volume_multiplier": 1.0,
    }
    ml_config = {"enabled": True, "min_confidence": 0.55, "mode": "STRICT"}

    monkeypatch.setattr(config_module, "TRADING_CONFIG", trading_config, raising=False)
    monkeypatch.setattr(config_module, "ML_CONFIG", ml_config, raising=False)

    calls = {"add_log": [], "save_config": [], "ws_emit": []}

    async def _fake_add_log(level, title, detail):
        calls["add_log"].append((level, title, detail))

    def _fake_save_config_overrides(updated):
        calls["save_config"].append(dict(updated))

    ws_mgr = SimpleNamespace(emit=AsyncMock(side_effect=lambda event, payload: calls["ws_emit"].append((event, payload))))

    dummy_state = _DummyState(pos_cfg=None, pos_mgr=None, ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    import utils.logging_utils as logging_utils
    import utils.config_persistence as config_persistence

    monkeypatch.setattr(logging_utils, "add_log", _fake_add_log)
    monkeypatch.setattr(config_persistence, "save_config_overrides", _fake_save_config_overrides)

    return config_module, trading_config, ml_config, dummy_state, calls


@pytest.mark.asyncio
async def test_perform_config_update_clamps_and_coerces(_patched_deps):
    config_module, trading_config, _, _, calls = _patched_deps

    updated = await perform_config_update(
        {
            "volume_multiplier": "99",
            "use_confluence": "yes",
            "min_score_required": 0,
            "max_slippage_pct": 0.9,
            "scan_interval": 3,
        }
    )

    assert updated["volume_multiplier"] == 2.0
    assert trading_config["volume_multiplier"] == 2.0
    assert updated["use_confluence"] is True
    assert updated["min_score_required"] == 1.0
    assert updated["max_slippage_pct"] == 0.2
    assert updated["scan_interval"] == 15

    assert calls["add_log"]
    assert calls["save_config"]
    assert calls["ws_emit"]


@pytest.mark.asyncio
async def test_perform_config_update_updates_tp_sl_mode_and_recalculates_levels(monkeypatch: pytest.MonkeyPatch, _patched_deps):
    config_module, trading_config, _, dummy_state, _ = _patched_deps

    pos_cfg = SimpleNamespace(use_atr=False, fixed_tp_pct=None, fixed_sl_pct=None)

    class _DummyPosMgr:
        def __init__(self):
            self.config = SimpleNamespace(use_atr=False)
            self.tpsl_config = SimpleNamespace()
            self.active_position = SimpleNamespace(
                symbol="TEST/USDT",
                entry=100.0,
                atr=1.0,
                atr5m=None,
                direction="LONG",
                tp_escalier_enabled=False,
                tp=None,
                sl=None,
            )

    pos_mgr = _DummyPosMgr()

    def _calc_atr_levels(entry, atr, atr5m, direction, tpsl_config):
        return 90.0, 110.0

    def _calc_fixed_levels(entry, direction, tpsl_config):
        return 95.0, 105.0

    import core.position.tp_sl_calculator as tpsl_calc

    monkeypatch.setattr(tpsl_calc, "calculate_atr_levels", _calc_atr_levels)
    monkeypatch.setattr(tpsl_calc, "calculate_fixed_levels", _calc_fixed_levels)

    dummy_state._pos_cfg = pos_cfg
    dummy_state._pos_mgr = pos_mgr

    updated = await perform_config_update({"tp_sl_mode": "ATR"})
    assert updated["tp_sl_mode"] == "ATR"
    assert trading_config["tp_sl_mode"] == "ATR"
    assert pos_cfg.use_atr is True
    assert pos_mgr.config.use_atr is True
    assert pos_mgr.active_position.sl == 90.0
    assert pos_mgr.active_position.tp == 110.0

    updated2 = await perform_config_update({"tp_sl_mode": "FIXE"})
    assert updated2["tp_sl_mode"] == "FIXE"
    assert pos_cfg.use_atr is False
    assert pos_mgr.config.use_atr is False
    assert pos_mgr.active_position.sl == 95.0
    assert pos_mgr.active_position.tp == 105.0


@pytest.mark.asyncio
async def test_perform_config_update_updates_ml_and_calibration(_patched_deps):
    _, trading_config, ml_config, _, _ = _patched_deps

    updated = await perform_config_update(
        {
            "ml_filter_enabled": "false",
            "ml_min_confidence": 0.9,
            "ml_filter_mode": "soft",
            "ml_calibration_enabled": "true",
            "ml_calib_min_winrate": 40,
            "ml_calib_live_weight": 1.0,
            "ml_calib_dryrun_weight": 0.25,
            "ml_calib_decay_days": 7,
            "ml_calib_min_trades": 10,
            "ml_calib_bucket_size": 5,
        }
    )

    assert updated["ml_filter_enabled"] is False
    assert trading_config["ml_filter_enabled"] is False
    assert ml_config["enabled"] is False

    assert updated["ml_min_confidence"] == 0.9
    assert trading_config["ml_min_confidence"] == 0.9
    assert ml_config["min_confidence"] == 0.9

    assert updated["ml_filter_mode"] == "SOFT"
    assert trading_config["ml_filter_mode"] == "SOFT"
    assert ml_config["mode"] == "SOFT"

    assert updated["ml_calibration_enabled"] is True
    assert trading_config["ml_calibration_enabled"] is True
    assert updated["ml_calib_min_winrate"] == 40


@pytest.mark.asyncio
async def test_perform_config_update_trailing_alias_and_reload(monkeypatch: pytest.MonkeyPatch, _patched_deps):
    _, trading_config, _, dummy_state, _ = _patched_deps

    trailing_stop = SimpleNamespace(config=None)
    pos_mgr = SimpleNamespace(trailing_stop=trailing_stop)
    dummy_state._pos_mgr = pos_mgr

    updated = await perform_config_update({"trailing_atr_multiplier": 0.7})
    assert updated["trailing_atr_multiplier"] == 0.7
    assert trading_config["trailing_atr_multiplier"] == 0.7
    assert trading_config["trailing_distance_atr_mult"] == 0.7
    assert pos_mgr.trailing_stop.config is not None


@pytest.mark.asyncio
async def test_perform_config_update_finalize_emits_ws(_patched_deps):
    _, _, _, _, calls = _patched_deps

    calls["ws_emit"].clear()
    updated = await perform_config_update({"invert_signals": "1"})
    assert updated["invert_signals"] is True
    assert calls["ws_emit"]
    assert calls["ws_emit"][0][0] == "config_updated"

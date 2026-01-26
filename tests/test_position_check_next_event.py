import pytest

from core.callbacks.position_check_loop import _calculate_next_event


class _Pos:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_calculate_next_event_returns_next_tp_and_sl_long():
    position = _Pos(
        symbol="TEST/USDT",
        direction="LONG",
        entry=100.0,
        tp=110.0,
        sl=90.0,
        break_even_triggered=False,
        trailing_activated=False,
    )

    # PnL: (105-100)/100=0.05 => 5%
    current_price = 105.0
    pnl_pct = 0.05

    out = _calculate_next_event(
        position=position,
        current_price=current_price,
        pnl_pct=pnl_pct,
        atr_percent=1.0,
        break_even_trigger_pct=None,
        trailing_trigger_pct=None,
        effective_config={},
        trading_config={"tp_sl_mode": "FIXE"},
    )

    assert isinstance(out, dict)
    assert out["next_sl"] is not None
    assert out["next_tp"] is not None

    assert out["next_sl"]["type"] == "SL"
    assert out["next_sl"]["price"] == pytest.approx(90.0)

    assert out["next_tp"]["type"] == "TP"
    assert out["next_tp"]["price"] == pytest.approx(110.0)


def test_calculate_next_event_uses_break_even_as_partial_tp_when_applicable():
    position = _Pos(
        symbol="TEST/USDT",
        direction="LONG",
        entry=100.0,
        tp=110.0,
        sl=95.0,
        break_even_triggered=False,
        trailing_activated=False,
        partial_tp_sold=False,
    )

    current_price = 101.0
    pnl_pct = 0.01  # 1%

    out = _calculate_next_event(
        position=position,
        current_price=current_price,
        pnl_pct=pnl_pct,
        atr_percent=1.0,
        break_even_trigger_pct=2.0,  # 2% => next TP partiel attendu
        trailing_trigger_pct=None,
        effective_config={},
        trading_config={"tp_sl_mode": "FIXE", "partial_tp_disable_final_tp": False},
    )

    assert out["next_tp"] is not None
    assert out["next_tp"]["type"] == "TP_PARTIAL"
    assert out["next_tp"]["price"] == pytest.approx(102.0)


def test_calculate_next_event_short_distance_signs_are_consistent():
    position = _Pos(
        symbol="TEST/USDT",
        direction="SHORT",
        entry=100.0,
        tp=90.0,
        sl=110.0,
        break_even_triggered=False,
        trailing_activated=False,
    )

    current_price = 95.0
    pnl_pct = 0.05  # 5% gain sur un short

    out = _calculate_next_event(
        position=position,
        current_price=current_price,
        pnl_pct=pnl_pct,
        atr_percent=1.0,
        break_even_trigger_pct=None,
        trailing_trigger_pct=None,
        effective_config={},
        trading_config={"tp_sl_mode": "FIXE"},
    )

    assert out["next_tp"] is not None
    assert out["next_sl"] is not None
    assert out["next_tp"]["type"] == "TP"
    assert out["next_sl"]["type"] == "SL"

    # Pour un short à 95, TP à 90 est "plus bas" => distance positive
    assert out["next_tp"]["distance_pct"] > 0
    # SL à 110 est "plus haut" => distance positive
    assert out["next_sl"]["distance_pct"] > 0

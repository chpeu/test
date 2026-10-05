"""
Tests pour TestablePositionCalculator
Module: core/implementations/testable_position_calculator.py
"""

import logging
import pytest
from dataclasses import dataclass

from core.implementations.testable_position_calculator import (
    TestablePositionCalculator,
    RiskParameters,
)
from core.interfaces.position_interfaces import PositionConfig, PositionSize


# Configuration de logging pour tests
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class TestTestablePositionCalculatorInit:
    """Tests d'initialisation de TestablePositionCalculator"""

    def test_init_with_valid_config(self):
        """Test initialisation avec configuration valide"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )

        calculator = TestablePositionCalculator(config)

        assert calculator.config == config
        assert calculator.config.default_risk == 2.0
        assert calculator.config.max_risk_per_trade == 5.0

    def test_init_with_minimal_config(self):
        """Test initialisation avec configuration minimale"""
        config = PositionConfig(
            default_risk=1.0,
            max_risk_per_trade=3.0,
            min_position_size=50.0,
            max_position_size=5000.0,
        )

        calculator = TestablePositionCalculator(config)

        assert calculator is not None
        assert calculator.config.min_position_size == 50.0

    def test_init_with_extreme_values(self):
        """Test initialisation avec valeurs extrêmes"""
        config = PositionConfig(
            default_risk=0.1,
            max_risk_per_trade=10.0,
            min_position_size=1.0,
            max_position_size=1000000.0,
        )

        calculator = TestablePositionCalculator(config)

        assert calculator.config.default_risk == 0.1
        assert calculator.config.max_risk_per_trade == 10.0


class TestCalculateSize:
    """Tests pour la méthode calculate_size"""

    def test_calculate_size_with_valid_data(self):
        """Test calcul position avec données valides"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {
            "current_price": 100.0,
            "direction": "LONG",
            "score": 7.0,
            "score_1m": 7.0,
            "score_5m": 6.5,
            "atr": 2.0,
            "volatility_score": 1.0,
        }
        capital = 10000.0

        result = calculator.calculate_size(setup, capital)

        assert isinstance(result, PositionSize)
        assert result.final_size > 0
        assert result.risk_percentage > 0

    def test_calculate_size_with_zero_capital(self):
        """Test calcul position avec capital nul"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "direction": "LONG", "score": 7.0}

        result = calculator.calculate_size(setup, 0.0)

        assert isinstance(result, PositionSize)
        assert result.final_size == config.min_position_size

    def test_calculate_size_with_negative_capital(self):
        """Test calcul position avec capital négatif"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "direction": "LONG", "score": 7.0}

        result = calculator.calculate_size(setup, -1000.0)

        assert isinstance(result, PositionSize)
        assert result.final_size == config.min_position_size

    def test_calculate_size_with_missing_price(self):
        """Test calcul position sans prix courant"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"direction": "LONG", "score": 7.0}
        capital = 10000.0

        result = calculator.calculate_size(setup, capital)

        assert isinstance(result, PositionSize)
        assert result.final_size == config.min_position_size

    def test_calculate_size_with_high_score(self):
        """Test calcul position avec score élevé"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {
            "current_price": 100.0,
            "direction": "LONG",
            "score": 9.0,
            "score_1m": 9.0,
            "score_5m": 8.5,
            "atr": 2.0,
        }
        capital = 10000.0

        result = calculator.calculate_size(setup, capital)

        assert isinstance(result, PositionSize)
        assert result.adjusted_size > result.base_size

    def test_calculate_size_with_low_score(self):
        """Test calcul position avec score faible"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {
            "current_price": 100.0,
            "direction": "LONG",
            "score": 3.0,
            "score_1m": 3.0,
            "score_5m": 3.5,
            "atr": 2.0,
        }
        capital = 10000.0

        result = calculator.calculate_size(setup, capital)

        assert isinstance(result, PositionSize)
        assert result.adjusted_size < result.base_size

    def test_calculate_size_respects_max_risk(self):
        """Test respect du risque maximum"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {
            "current_price": 100.0,
            "direction": "LONG",
            "score": 7.0,
            "risk_percentage": 10.0,
        }
        capital = 10000.0

        result = calculator.calculate_size(setup, capital)

        assert result.risk_percentage <= config.max_risk_per_trade

    def test_calculate_size_with_exception(self):
        """Test gestion d'exception dans calculate_size"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 0.0, "direction": "LONG", "score": 7.0}
        capital = 10000.0

        result = calculator.calculate_size(setup, capital)

        assert isinstance(result, PositionSize)
        assert result.final_size == config.min_position_size


class TestCalculatePositionSize:
    """Tests pour la méthode calculate_position_size"""

    def test_calculate_position_size_with_full_data(self):
        """Test avec données complètes"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        position_data = {
            "capital": 10000.0,
            "entry_price": 100.0,
            "direction": "LONG",
            "score": 7.0,
            "symbol": "BTC/USDT",
            "leverage": 10,
        }

        result = calculator.calculate_position_size(position_data)

        assert isinstance(result, dict)
        assert "position_size" in result
        assert "risk_percent" in result
        assert result["position_size"] > 0

    def test_calculate_position_size_with_minimal_data(self):
        """Test avec données minimales"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        position_data = {"capital": 10000.0}

        result = calculator.calculate_position_size(position_data)

        assert isinstance(result, dict)
        assert result["position_size"] > 0

    def test_calculate_position_size_with_current_price(self):
        """Test avec champ current_price"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        position_data = {
            "capital": 10000.0,
            "current_price": 150.0,
            "direction": "SHORT",
        }

        result = calculator.calculate_position_size(position_data)

        assert isinstance(result, dict)
        assert result["position_size"] > 0

    def test_calculate_position_size_with_exception(self):
        """Test gestion d'exception"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        position_data = {"capital": -1000.0}

        result = calculator.calculate_position_size(position_data)

        assert isinstance(result, dict)
        assert result["position_size"] == 100.0


class TestCalculateStopLoss:
    """Tests pour la méthode calculate_stop_loss"""

    def test_calculate_stop_loss_long(self):
        """Test SL pour position LONG"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "side": "long", "atr": 2.0}
        position_size = 1000.0

        sl = calculator.calculate_stop_loss(setup, position_size)

        assert sl < 100.0
        assert 95.0 < sl < 99.0

    def test_calculate_stop_loss_short(self):
        """Test SL pour position SHORT"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "side": "short", "atr": 2.0}
        position_size = 1000.0

        sl = calculator.calculate_stop_loss(setup, position_size)

        assert sl > 100.0
        assert 101.0 < sl < 105.0

    def test_calculate_stop_loss_with_default_atr(self):
        """Test SL avec ATR par défaut"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "side": "long"}
        position_size = 1000.0

        sl = calculator.calculate_stop_loss(setup, position_size)

        assert sl < 100.0

    def test_calculate_stop_loss_with_invalid_price(self):
        """Test SL avec prix invalide"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 0.0, "side": "long"}
        position_size = 1000.0

        sl = calculator.calculate_stop_loss(setup, position_size)

        # Quand prix = 0.0, le fallback retourne 0.0 * 0.95 = 0.0
        assert sl == 0.0

    def test_calculate_stop_loss_respects_min_distance(self):
        """Test respect de la distance minimum SL"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "side": "long", "atr": 0.01}
        position_size = 1000.0

        sl = calculator.calculate_stop_loss(setup, position_size)

        assert 100.0 - sl >= 0.5

    def test_calculate_stop_loss_respects_max_distance(self):
        """Test respect de la distance maximum SL"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "side": "long", "atr": 50.0}
        position_size = 1000.0

        sl = calculator.calculate_stop_loss(setup, position_size)

        assert 100.0 - sl <= 10.0


class TestCalculateTakeProfit:
    """Tests pour la méthode calculate_take_profit"""

    def test_calculate_take_profit_long(self):
        """Test TP pour position LONG"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "side": "long", "atr": 2.0, "score_1m": 7.0}
        position_size = 1000.0

        tp = calculator.calculate_take_profit(setup, position_size)

        assert tp > 100.0
        assert 103.0 < tp < 107.0

    def test_calculate_take_profit_short(self):
        """Test TP pour position SHORT"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "side": "short", "atr": 2.0, "score_1m": 7.0}
        position_size = 1000.0

        tp = calculator.calculate_take_profit(setup, position_size)

        assert tp < 100.0
        assert 93.0 < tp < 97.0

    def test_calculate_take_profit_with_high_score(self):
        """Test TP avec score élevé"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "side": "long", "atr": 2.0, "score_1m": 9.0}
        position_size = 1000.0

        tp = calculator.calculate_take_profit(setup, position_size)

        assert tp > 105.0

    def test_calculate_take_profit_with_low_score(self):
        """Test TP avec score faible"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "side": "long", "atr": 2.0, "score_1m": 3.0}
        position_size = 1000.0

        tp = calculator.calculate_take_profit(setup, position_size)

        assert tp < 105.0

    def test_calculate_take_profit_with_invalid_price(self):
        """Test TP avec prix invalide"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 0.0, "side": "long"}
        position_size = 1000.0

        tp = calculator.calculate_take_profit(setup, position_size)

        # Quand prix = 0.0, le fallback retourne 0.0 * 1.05 = 0.0
        assert tp == 0.0


class TestCalculateBaseSize:
    """Tests pour la méthode privée _calculate_base_size"""

    def test_calculate_base_size_with_valid_capital(self):
        """Test calcul base size avec capital valide"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "risk_percentage": 2.0}
        capital = 10000.0

        base_size = calculator._calculate_base_size(setup, capital)

        assert base_size == 200.0

    def test_calculate_base_size_respects_min(self):
        """Test respect du minimum"""
        config = PositionConfig(
            default_risk=0.5,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "risk_percentage": 0.5}
        capital = 10000.0

        base_size = calculator._calculate_base_size(setup, capital)

        assert base_size >= config.min_position_size

    def test_calculate_base_size_with_zero_capital(self):
        """Test avec capital nul"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0}
        capital = 0.0

        base_size = calculator._calculate_base_size(setup, capital)

        assert base_size == config.min_position_size


class TestApplyScoreAdjustments:
    """Tests pour la méthode privée _apply_score_adjustments"""

    def test_apply_score_adjustments_with_high_score(self):
        """Test ajustement avec score élevé"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"score_1m": 9.0, "score_5m": 8.5}
        base_size = 1000.0

        adjusted_size = calculator._apply_score_adjustments(base_size, setup)

        assert adjusted_size > base_size

    def test_apply_score_adjustments_with_low_score(self):
        """Test ajustement avec score faible"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"score_1m": 3.0, "score_5m": 3.5}
        base_size = 1000.0

        adjusted_size = calculator._apply_score_adjustments(base_size, setup)

        assert adjusted_size < base_size

    def test_apply_score_adjustments_with_neutral_score(self):
        """Test ajustement avec score neutre"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"score_1m": 5.0, "score_5m": 5.0}
        base_size = 1000.0

        adjusted_size = calculator._apply_score_adjustments(base_size, setup)

        assert adjusted_size == base_size

    def test_apply_score_adjustments_respects_limits(self):
        """Test respect des limites d'ajustement"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"score_1m": 10.0, "score_5m": 10.0}
        base_size = 1000.0

        adjusted_size = calculator._apply_score_adjustments(base_size, setup)

        assert adjusted_size <= base_size * 1.5
        assert adjusted_size >= base_size * 0.7


class TestApplyPositionLimits:
    """Tests pour la méthode privée _apply_position_limits"""

    def test_apply_position_limits_respects_min(self):
        """Test respect du minimum"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        size = 50.0
        capital = 10000.0

        limited_size = calculator._apply_position_limits(size, capital)

        assert limited_size == config.min_position_size

    def test_apply_position_limits_respects_max(self):
        """Test respect du maximum"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        size = 50000.0
        capital = 100000.0

        limited_size = calculator._apply_position_limits(size, capital)

        assert limited_size == config.max_position_size

    def test_apply_position_limits_respects_capital_pct(self):
        """Test respect de la limite en % du capital"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        size = 5000.0
        capital = 10000.0

        limited_size = calculator._apply_position_limits(size, capital)

        assert limited_size <= capital * 0.20

    def test_apply_position_limits_with_zero_capital(self):
        """Test avec capital nul"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        size = 1000.0
        capital = 0.0

        limited_size = calculator._apply_position_limits(size, capital)

        assert limited_size == config.min_position_size


class TestCalculateSLDistance:
    """Tests pour la méthode privée _calculate_sl_distance"""

    def test_calculate_sl_distance_default(self):
        """Test distance SL par défaut"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "atr": 2.0}
        position_size = 1000.0

        distance = calculator._calculate_sl_distance(setup, position_size)

        assert distance == 3.0

    def test_calculate_sl_distance_with_high_volatility(self):
        """Test avec volatilité élevée"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "atr": 2.0, "volatility_score": 2.0}
        position_size = 1000.0

        distance = calculator._calculate_sl_distance(setup, position_size)

        assert distance > 3.0

    def test_calculate_sl_distance_with_low_volatility(self):
        """Test avec volatilité faible"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "atr": 2.0, "volatility_score": 0.3}
        position_size = 1000.0

        distance = calculator._calculate_sl_distance(setup, position_size)

        assert distance < 3.0


class TestCalculateTPDistance:
    """Tests pour la méthode privée _calculate_tp_distance"""

    def test_calculate_tp_distance_default(self):
        """Test distance TP par défaut"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "atr": 2.0, "score_1m": 5.0}
        position_size = 1000.0

        distance = calculator._calculate_tp_distance(setup, position_size)

        assert distance == 5.0

    def test_calculate_tp_distance_with_high_score(self):
        """Test avec score élevé"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "atr": 2.0, "score_1m": 9.0}
        position_size = 1000.0

        distance = calculator._calculate_tp_distance(setup, position_size)

        assert distance > 5.0

    def test_calculate_tp_distance_with_low_score(self):
        """Test avec score faible"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        setup = {"current_price": 100.0, "atr": 2.0, "score_1m": 3.0}
        position_size = 1000.0

        distance = calculator._calculate_tp_distance(setup, position_size)

        assert distance < 5.0


class TestCalculateEffectiveRisk:
    """Tests pour la méthode privée _calculate_effective_risk"""

    def test_calculate_effective_risk_normal(self):
        """Test calcul risque effectif normal"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        position_size = 1000.0
        capital = 10000.0
        sl_distance = 0.02

        risk = calculator._calculate_effective_risk(position_size, capital, sl_distance)

        # Calcul: (1000 * 0.02 / 10000) * 100 = 0.2
        assert risk == 0.2

    def test_calculate_effective_risk_with_zero_capital(self):
        """Test avec capital nul"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        risk = calculator._calculate_effective_risk(1000.0, 0.0, 0.02)

        assert risk == config.default_risk

    def test_calculate_effective_risk_respects_max(self):
        """Test respect du risque maximum"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        position_size = 100000.0
        capital = 10000.0
        sl_distance = 0.10

        risk = calculator._calculate_effective_risk(position_size, capital, sl_distance)

        assert risk <= config.max_risk_per_trade


class TestCreateSafeFallbackPosition:
    """Tests pour la méthode privée _create_safe_fallback_position"""

    def test_create_safe_fallback_position(self):
        """Test création position fallback sécurisée"""
        config = PositionConfig(
            default_risk=2.0,
            max_risk_per_trade=5.0,
            min_position_size=100.0,
            max_position_size=10000.0,
        )
        calculator = TestablePositionCalculator(config)

        result = calculator._create_safe_fallback_position(10000.0)

        assert isinstance(result, PositionSize)
        assert result.final_size == config.min_position_size
        assert result.risk_percentage == 1.0

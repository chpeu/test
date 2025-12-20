#!/usr/bin/env python3
"""
Edge Cases Tests for Trade Cursor v7.0
Target: Coverage edge cases for modules with good coverage
- TP/SL Calculator (precision edge cases)
- PnL Calculator (complex fees scenarios)
- Recovery Mode edge cases
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.position.tp_sl_calculator import TPSLConfig, calculate_fixed_levels, calculate_atr_levels
from core.position.pnl_calculator import PnLCalculator


# ============================================================================
# TP/SL CALCULATOR EDGE CASES
# ============================================================================

class TestTPSLCalculatorEdgeCases:
    """Edge cases pour TP/SL Calculator (précision, valeurs extrêmes)"""

    def test_calculate_fixed_levels_very_small_price(self):
        """Test calcul TP/SL avec prix très petit (< 0.001)"""
        config = TPSLConfig(fixed_tp_pct=0.6, fixed_sl_pct=0.25)

        sl, tp = calculate_fixed_levels(
            entry=0.00012345,
            direction='LONG',
            config=config
        )

        # Vérifier que les valeurs sont différentes de l'entrée
        assert sl != 0.00012345
        assert tp != 0.00012345
        assert sl < 0.00012345
        assert tp > 0.00012345

    def test_calculate_fixed_levels_medium_small_price(self):
        """Test calcul TP/SL avec prix petit (< 0.01)"""
        config = TPSLConfig(fixed_tp_pct=0.6, fixed_sl_pct=0.25)

        sl, tp = calculate_fixed_levels(
            entry=0.005678,
            direction='LONG',
            config=config
        )

        assert sl != 0.005678
        assert tp != 0.005678
        assert sl < 0.005678
        assert tp > 0.005678

    def test_calculate_fixed_levels_short_direction(self):
        """Test calcul TP/SL pour SHORT"""
        config = TPSLConfig(fixed_tp_pct=0.6, fixed_sl_pct=0.25)

        sl, tp = calculate_fixed_levels(
            entry=50000.0,
            direction='SHORT',
            config=config
        )

        # Pour SHORT: SL > entry, TP < entry
        assert sl > 50000.0
        assert tp < 50000.0

    def test_calculate_fixed_levels_invalid_entry(self):
        """Test calcul TP/SL avec entry invalide"""
        config = TPSLConfig()

        with pytest.raises(ValueError, match="Entry invalide"):
            calculate_fixed_levels(
                entry=0.0,
                direction='LONG',
                config=config
            )

        with pytest.raises(ValueError, match="Entry invalide"):
            calculate_fixed_levels(
                entry=-100.0,
                direction='LONG',
                config=config
            )

    def test_calculate_fixed_levels_invalid_config(self):
        """Test calcul TP/SL avec config invalide"""
        config = TPSLConfig(fixed_tp_pct=0.0, fixed_sl_pct=0.25)

        with pytest.raises(ValueError, match="Config invalide"):
            calculate_fixed_levels(
                entry=50000.0,
                direction='LONG',
                config=config
            )

    def test_calculate_fixed_levels_extreme_percentages(self):
        """Test calcul TP/SL avec pourcentages extrêmes (test adapté au capping)"""
        config = TPSLConfig(fixed_tp_pct=5.0, fixed_sl_pct=3.0)

        sl, tp = calculate_fixed_levels(
            entry=50000.0,
            direction='LONG',
            config=config
        )

        # Vérifier les différences (adapté au SL capping à 0.5%)
        sl_diff_pct = abs(sl - 50000.0) / 50000.0 * 100
        tp_diff_pct = abs(tp - 50000.0) / 50000.0 * 100

        # SL est cappé à 0.5% donc on teste ça
        assert sl_diff_pct >= 0.4  # Au moins 0.4% (cappé à 0.5%)
        assert tp_diff_pct > 4.0  # Au moins 4.0%

    def test_calculate_atr_levels_basic(self):
        """Test calcul TP/SL en mode ATR basique"""
        config = TPSLConfig(atr_mult_tp=1.5, atr_mult_sl=1.0)

        sl, tp = calculate_atr_levels(
            entry=50000.0,
            atr=200.0,
            atr5m=180.0,
            direction='LONG',
            config=config
        )

        # Vérifier que les valeurs utilisent l'ATR
        assert sl < 50000.0
        assert tp > 50000.0

    def test_calculate_atr_levels_extreme_atr(self):
        """Test calcul TP/SL avec ATR extrême"""
        config = TPSLConfig(atr_mult_tp=1.5, atr_mult_sl=1.0, atr_min=0.15, atr_max=1.5)

        # ATR très petit (devrait être limité par atr_min)
        sl1, tp1 = calculate_atr_levels(
            entry=50000.0,
            atr=0.05,  # Très petit
            atr5m=0.04,
            direction='LONG',
            config=config
        )

        # ATR très grand (devrait être limité par atr_max)
        sl2, tp2 = calculate_atr_levels(
            entry=50000.0,
            atr=3.0,  # Très grand
            atr5m=2.8,
            direction='LONG',
            config=config
        )

        # Les deux devraient avoir des valeurs raisonnables
        assert 49000.0 < sl1 < 50000.0
        assert 50000.0 < tp1 < 51000.0
        assert 48000.0 < sl2 < 50000.0
        assert 50000.0 < tp2 < 52000.0

    def test_calculate_atr_levels_no_atr5m(self):
        """Test calcul TP/SL sans ATR 5m"""
        config = TPSLConfig()

        sl, tp = calculate_atr_levels(
            entry=50000.0,
            atr=200.0,
            atr5m=None,
            direction='LONG',
            config=config
        )

        assert sl < 50000.0
        assert tp > 50000.0


# ============================================================================
# PNL CALCULATOR EDGE CASES
# ============================================================================

class TestPnLCalculatorEdgeCases:
    """Edge cases pour PnL Calculator (fees complexes, TP partiel)"""

    def test_calculate_pnl_percent_long(self):
        """Test calcul PnL % pour LONG"""
        pnl = PnLCalculator.calculate_pnl_percent(
            entry=50000.0,
            current_price=50500.0,
            direction='LONG'
        )

        assert pnl == pytest.approx(1.0, rel=0.01)

    def test_calculate_pnl_percent_short(self):
        """Test calcul PnL % pour SHORT"""
        pnl = PnLCalculator.calculate_pnl_percent(
            entry=50000.0,
            current_price=49500.0,
            direction='SHORT'
        )

        assert pnl == pytest.approx(1.0, rel=0.01)

    def test_calculate_pnl_percent_invalid_entry(self):
        """Test calcul PnL % avec entry invalide"""
        pnl = PnLCalculator.calculate_pnl_percent(
            entry=0.0,
            current_price=50000.0,
            direction='LONG'
        )

        assert pnl == 0.0

    def test_calculate_pnl_usdt_basic(self):
        """Test calcul PnL USDT basique"""
        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'size': 100.0,
            'partial_tp_sold': False
        }

        pnl_usdt = PnLCalculator.calculate_pnl_usdt(position, 50500.0)

        # PnL = 100 * (500 / 50000) = 1.0 USDT
        assert pnl_usdt == pytest.approx(1.0, rel=0.01)

    def test_calculate_pnl_usdt_with_partial_tp(self):
        """Test calcul PnL USDT avec TP partiel"""
        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'size': 100.0,
            'partial_tp_sold': True,
            'size_remaining': 50.0,
            'partial_profit_usdt': 0.5
        }

        pnl_usdt = PnLCalculator.calculate_pnl_usdt(position, 50500.0)

        # PnL = 50 * (500 / 50000) + 0.5 = 1.0 USDT
        assert pnl_usdt == pytest.approx(1.0, rel=0.01)

    def test_calculate_pnl_usdt_with_partial_tp_no_size_remaining(self):
        """Test calcul PnL USDT avec TP partiel sans size_remaining (fallback 50%)"""
        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'size': 100.0,
            'partial_tp_sold': True,
            'partial_profit_usdt': 0.5
        }

        pnl_usdt = PnLCalculator.calculate_pnl_usdt(position, 50500.0)

        # PnL = 50 * (500 / 50000) + 0.5 = 1.0 USDT (fallback 50%)
        assert pnl_usdt == pytest.approx(1.0, rel=0.01)

    def test_calculate_realized_pnl_basic(self):
        """Test calcul PnL réalisé basique"""
        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'size': 100.0,
            'partial_tp_sold': False
        }

        pnl = PnLCalculator.calculate_realized_pnl(position, 50500.0, fees_percent=0.04)

        assert pnl['pnl_pct'] > 0
        assert pnl['pnl_usdt_gross'] > 0
        assert pnl['fees'] > 0
        assert pnl['net_pnl'] < pnl['pnl_usdt_gross']

    def test_calculate_realized_pnl_with_partial_tp(self):
        """Test calcul PnL réalisé avec TP partiel"""
        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'size': 100.0,
            'partial_tp_sold': True,
            'size_remaining': 50.0,
            'partial_profit_usdt': 0.6
        }

        pnl = PnLCalculator.calculate_realized_pnl(position, 50500.0, fees_percent=0.04)

        # Devrait inclure le profit partiel
        assert pnl['pnl_usdt_gross'] > 1.0
        assert pnl['net_pnl'] > 0

    def test_calculate_realized_pnl_short(self):
        """Test calcul PnL réalisé pour SHORT"""
        position = {
            'entry': 50000.0,
            'direction': 'SHORT',
            'size': 100.0,
            'partial_tp_sold': False
        }

        pnl = PnLCalculator.calculate_realized_pnl(position, 49500.0, fees_percent=0.04)

        # SHORT gagnant
        assert pnl['pnl_pct'] > 0
        assert pnl['pnl_usdt_gross'] > 0

    def test_calculate_realized_pnl_loss(self):
        """Test calcul PnL réalisé avec perte"""
        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'size': 100.0,
            'partial_tp_sold': False
        }

        pnl = PnLCalculator.calculate_realized_pnl(position, 49500.0, fees_percent=0.04)

        # LONG perdant
        assert pnl['pnl_pct'] < 0
        assert pnl['pnl_usdt_gross'] < 0
        assert pnl['net_pnl'] < pnl['pnl_usdt_gross']  # Perte + fees

    def test_calculate_costs_basic(self):
        """Test calcul coûts basique"""
        position = {
            'entry': 50000.0,
            'size': 100.0
        }

        costs = PnLCalculator.calculate_costs(position, fees_percent=0.04, slippage_percent=0.02)

        assert 'fees' in costs
        assert 'slippage' in costs
        assert 'total_cost' in costs
        assert costs['fees'] > 0
        assert costs['total_cost'] >= costs['fees']

    def test_calculate_costs_no_slippage(self):
        """Test calcul coûts sans slippage"""
        position = {
            'entry': 50000.0,
            'size': 100.0
        }

        costs = PnLCalculator.calculate_costs(position, fees_percent=0.04, slippage_percent=None)

        assert costs['slippage'] == 0.0
        assert costs['total_cost'] == costs['fees']

    def test_calculate_costs_high_fees(self):
        """Test calcul coûts avec fees élevés"""
        position = {
            'entry': 50000.0,
            'size': 100.0
        }

        costs = PnLCalculator.calculate_costs(position, fees_percent=0.5, slippage_percent=0.1)

        # Fees + slippage devraient être significatifs
        assert costs['fees'] > 0.5
        assert costs['total_cost'] > 0.5


# ============================================================================
# RECOVERY MODE EDGE CASES
# ============================================================================

class TestRecoveryModeEdgeCases:
    """Edge cases pour Recovery Mode"""

    def test_recovery_mode_activation(self):
        """Test activation du Recovery Mode"""
        # Import local pour éviter side effects
        from core.position.recovery_mode import RecoveryModeManager

        recovery = RecoveryModeManager()

        # Activer avec 3 pertes consécutives
        level = recovery.activate(loss_streak=3)

        assert recovery.active is True
        assert level is not None

    def test_recovery_mode_deactivation(self):
        """Test désactivation du Recovery Mode"""
        from core.position.recovery_mode import RecoveryModeManager

        recovery = RecoveryModeManager()

        # Activer
        recovery.activate(loss_streak=3)
        assert recovery.active is True

        # Désactiver
        recovery.deactivate()

        # Devrait se désactiver
        assert recovery.active is False

    def test_recovery_mode_position_size_reduction(self):
        """Test réduction taille position en Recovery Mode"""
        from core.position.recovery_mode import RecoveryModeManager

        recovery = RecoveryModeManager()

        # Activer
        recovery.activate(loss_streak=3)

        # Obtenir multiplicateur de taille
        multiplier = recovery.get_position_size_multiplier(loss_streak=3)

        # Le multiplier devrait être < 1.0 (réduction)
        assert multiplier < 1.0
        assert multiplier > 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

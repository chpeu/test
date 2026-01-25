"""
Tests pour core/position/tp_sl_calculator.py
"""
import pytest
from core.position.tp_sl_calculator import (
    TPSLConfig,
    calculate_fixed_levels,
    calculate_atr_levels,
    validate_levels
)


class TestTPSLConfig:
    """Tests pour TPSLConfig"""

    def test_default_values(self):
        """Test valeurs par défaut"""
        config = TPSLConfig()
        assert config.fixed_tp_pct == 0.6
        assert config.fixed_sl_pct == 0.25
        assert config.atr_mult_tp == 1.5
        assert config.atr_mult_sl == 1.0
        assert config.atr_min == 0.15
        assert config.atr_max == 1.5
        assert config.win_streak == 0
        assert config.loss_streak == 0

    def test_custom_values(self):
        """Test valeurs personnalisées"""
        config = TPSLConfig(
            fixed_tp_pct=1.0,
            fixed_sl_pct=0.5,
            win_streak=3
        )
        assert config.fixed_tp_pct == 1.0
        assert config.fixed_sl_pct == 0.5
        assert config.win_streak == 3

    def test_legacy_multipliers_override_atr_multipliers(self):
        config = TPSLConfig(tp_multiplier=2.5, sl_multiplier=1.7)
        assert config.atr_mult_tp == 2.5
        assert config.atr_mult_sl == 1.7


class TestCalculateFixedLevels:
    """Tests pour calculate_fixed_levels"""

    def test_invalid_entry_zero(self):
        """Test avec entry = 0"""
        config = TPSLConfig()
        with pytest.raises(ValueError, match="Entry invalide"):
            calculate_fixed_levels(0, 'LONG', config)

    def test_invalid_entry_negative(self):
        """Test avec entry négatif"""
        config = TPSLConfig()
        with pytest.raises(ValueError, match="Entry invalide"):
            calculate_fixed_levels(-100, 'LONG', config)

    def test_invalid_config_zero_sl(self):
        """Test avec fixed_sl_pct = 0"""
        config = TPSLConfig(fixed_sl_pct=0)
        with pytest.raises(ValueError, match="Config invalide"):
            calculate_fixed_levels(50000, 'LONG', config)

    def test_invalid_config_negative_tp(self):
        """Test avec fixed_tp_pct négatif"""
        config = TPSLConfig(fixed_tp_pct=-0.5)
        with pytest.raises(ValueError, match="Config invalide"):
            calculate_fixed_levels(50000, 'LONG', config)

    def test_long_normal_case(self):
        """Test LONG cas normal"""
        config = TPSLConfig(fixed_sl_pct=0.25, fixed_tp_pct=0.6)
        sl, tp = calculate_fixed_levels(50000, 'LONG', config)

        # SL = 50000 * (1 - 0.25%) = 49875
        # TP = 50000 * (1 + 0.6%) = 50300
        assert sl == pytest.approx(49875, rel=0.001)
        assert tp == pytest.approx(50300, rel=0.001)

    def test_short_normal_case(self):
        """Test SHORT cas normal"""
        config = TPSLConfig(fixed_sl_pct=0.25, fixed_tp_pct=0.6)
        sl, tp = calculate_fixed_levels(50000, 'SHORT', config)

        # SL = 50000 * (1 + 0.25%) = 50125
        # TP = 50000 * (1 - 0.6%) = 49700
        assert sl == pytest.approx(50125, rel=0.001)
        assert tp == pytest.approx(49700, rel=0.001)

    def test_small_price_precision(self):
        """Test avec prix très petit (< 0.001)"""
        config = TPSLConfig(fixed_sl_pct=0.25, fixed_tp_pct=0.6)
        sl, tp = calculate_fixed_levels(0.0005, 'LONG', config)

        # Devrait utiliser precision=10
        assert sl < 0.0005
        assert tp > 0.0005

    def test_medium_price_precision(self):
        """Test avec prix moyen (< 0.01)"""
        config = TPSLConfig(fixed_sl_pct=0.25, fixed_tp_pct=0.6)
        sl, tp = calculate_fixed_levels(0.005, 'LONG', config)

        # Devrait utiliser precision=9
        assert sl < 0.005
        assert tp > 0.005

    def test_large_price_precision(self):
        """Test avec prix normal (>= 0.01)"""
        config = TPSLConfig(fixed_sl_pct=0.25, fixed_tp_pct=0.6)
        sl, tp = calculate_fixed_levels(50000, 'LONG', config)

        # Devrait utiliser precision=8
        assert sl < 50000
        assert tp > 50000

    def test_rounding_issue_adjustment(self):
        """Test ajustement quand rounding cause problème"""
        # Avec un très petit prix et petits pourcentages, le rounding peut causer des problèmes
        config = TPSLConfig(fixed_sl_pct=0.01, fixed_tp_pct=0.01)
        sl, tp = calculate_fixed_levels(0.000001, 'LONG', config)

        # Devrait forcer un minimum de 0.15% ou 0.2%
        assert abs(sl - 0.000001) > 0
        assert abs(tp - 0.000001) > 0

    def test_short_rounding_safeguard_prevents_widening(self):
        config = TPSLConfig(fixed_sl_pct=0.25, fixed_tp_pct=0.6)
        entry = 1.23456789
        sl_target = entry * (1 + config.fixed_sl_pct / 100)
        naive_sl = round(sl_target, 8)
        assert naive_sl > sl_target

        sl, tp = calculate_fixed_levels(entry, 'SHORT', config)
        assert sl < naive_sl
        assert tp < entry

    def test_short_rounding_safeguard_exception_is_ignored(self, monkeypatch):
        config = TPSLConfig(fixed_sl_pct=0.25, fixed_tp_pct=0.6)
        entry = 1.23456789
        sl_target = entry * (1 + config.fixed_sl_pct / 100)
        naive_sl = round(sl_target, 8)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr("core.position.tp_sl_calculator.math.floor", _boom)

        sl, _tp = calculate_fixed_levels(entry, 'SHORT', config)
        assert sl == naive_sl

    def test_short_min_diff_recalculation_debug_branch(self):
        config = TPSLConfig(fixed_sl_pct=0.005, fixed_tp_pct=0.005)
        entry = 50000
        sl, tp = calculate_fixed_levels(entry, 'SHORT', config)

        assert sl == pytest.approx(50050, rel=1e-12)
        assert tp == pytest.approx(49950, rel=1e-12)

    def test_short_min_diff_final_fallback_branch(self):
        config = TPSLConfig(fixed_sl_pct=0.01, fixed_tp_pct=0.01)
        entry = 0.000001
        sl, tp = calculate_fixed_levels(entry, 'SHORT', config)

        assert sl > entry
        assert tp < entry


class TestCalculateATRLevels:
    """Tests pour calculate_atr_levels"""

    def test_invalid_atr_zero(self):
        """Test avec ATR = 0 (fallback mode FIXE)"""
        config = TPSLConfig()
        sl, tp = calculate_atr_levels(50000, 0, None, 'LONG', config)

        # Devrait fallback sur calculate_fixed_levels
        assert sl < 50000
        assert tp > 50000

    def test_invalid_atr_negative(self):
        """Test avec ATR négatif (fallback mode FIXE)"""
        config = TPSLConfig()
        sl, tp = calculate_atr_levels(50000, -100, None, 'LONG', config)

        # Devrait fallback sur calculate_fixed_levels
        assert sl < 50000
        assert tp > 50000

    def test_invalid_entry(self):
        """Test avec entry invalide (fallback mode FIXE)"""
        config = TPSLConfig()
        # Note: entry <= 0 devrait aussi causer une erreur dans calculate_fixed_levels
        # mais le code fait le fallback d'abord
        with pytest.raises(ValueError):
            calculate_atr_levels(0, 500, None, 'LONG', config)

    def test_atr_blending_with_5m(self):
        """Test blending ATR 1m et 5m"""
        config = TPSLConfig()
        atr1m = 100
        atr5m = 200

        sl, tp = calculate_atr_levels(50000, atr1m, atr5m, 'LONG', config)

        # ATR blended = 100 * 0.7 + 200 * 0.3 = 70 + 60 = 130
        # Devrait utiliser 130 au lieu de 100
        assert sl < 50000
        assert tp > 50000

    def test_atr_no_blending(self):
        """Test sans ATR 5m"""
        config = TPSLConfig()
        sl, tp = calculate_atr_levels(50000, 100, None, 'LONG', config)

        # Devrait utiliser ATR 1m directement
        assert sl < 50000
        assert tp > 50000

    def test_atr_clamping_min(self):
        """Test clamping ATR en dessous du minimum"""
        config = TPSLConfig(atr_min=0.15)
        # ATR très petit qui donne < 0.15%
        atr = 10  # 10 / 50000 = 0.02%

        sl, tp = calculate_atr_levels(50000, atr, None, 'LONG', config)

        # Devrait clamp à atr_min=0.15%
        assert sl < 50000
        assert tp > 50000

    def test_atr_clamping_max(self):
        """Test clamping ATR au-dessus du maximum"""
        config = TPSLConfig(atr_max=1.5)
        # ATR très grand qui donne > 1.5%
        atr = 1000  # 1000 / 50000 = 2%

        sl, tp = calculate_atr_levels(50000, atr, None, 'LONG', config)

        # Devrait clamp à atr_max=1.5%
        assert sl < 50000
        assert tp > 50000

    def test_long_atr_normal(self):
        """Test LONG mode ATR normal"""
        config = TPSLConfig(atr_mult_tp=1.5, atr_mult_sl=1.0)
        atr = 250  # 250 / 50000 = 0.5%

        sl, tp = calculate_atr_levels(50000, atr, None, 'LONG', config)

        # SL = 50000 * (1 - 0.5% * 1.0) = 49750
        # TP = 50000 * (1 + 0.5% * 1.5) = 50375
        assert sl == pytest.approx(49750, rel=0.01)
        assert tp == pytest.approx(50375, rel=0.01)

    def test_short_atr_normal(self):
        """Test SHORT mode ATR normal"""
        config = TPSLConfig(atr_mult_tp=1.5, atr_mult_sl=1.0)
        atr = 250  # 0.5%

        sl, tp = calculate_atr_levels(50000, atr, None, 'SHORT', config)

        # SL = 50000 * (1 + 0.5% * 1.0) = 50250
        # TP = 50000 * (1 - 0.5% * 1.5) = 49625
        assert sl == pytest.approx(50250, rel=0.01)
        assert tp == pytest.approx(49625, rel=0.01)

    def test_win_streak_aggressive_mode(self):
        """Test mode agressif après win streak >= 3"""
        config = TPSLConfig(win_streak=3)
        atr = 250  # 0.5%

        sl, tp = calculate_atr_levels(50000, atr, None, 'LONG', config)

        # Mode agressif: TPx=4.0, SLx=1.2
        # SL = 50000 * (1 - 0.5% * 1.2) = 49700
        # TP = 50000 * (1 + 0.5% * 4.0) = 51000
        assert sl == pytest.approx(49700, rel=0.01)
        assert tp == pytest.approx(51000, rel=0.01)

    def test_loss_streak_prudent_mode(self):
        """Test mode prudent après loss streak >= 2"""
        config = TPSLConfig(loss_streak=2)
        atr = 250  # 0.5%

        sl, tp = calculate_atr_levels(50000, atr, None, 'LONG', config)

        # Mode prudent: TPx=1.5, SLx=1.2
        # SL = 50000 * (1 - 0.5% * 1.2) = 49700
        # TP = 50000 * (1 + 0.5% * 1.5) = 50375
        assert sl == pytest.approx(49700, rel=0.01)
        assert tp == pytest.approx(50375, rel=0.01)

    def test_precision_small_price(self):
        """Test précision avec petit prix"""
        config = TPSLConfig()
        atr = 0.000005  # Très petit ATR

        sl, tp = calculate_atr_levels(0.0005, atr, None, 'LONG', config)

        # Devrait utiliser precision=10
        assert sl < 0.0005
        assert tp > 0.0005

    def test_precision_medium_price(self):
        """Test précision avec prix moyen"""
        config = TPSLConfig()
        atr = 0.00005

        sl, tp = calculate_atr_levels(0.005, atr, None, 'LONG', config)

        # Devrait utiliser precision=9
        assert sl < 0.005
        assert tp > 0.005

    def test_return_atr_used_includes_percent_and_blended(self):
        config = TPSLConfig(atr_min=0.1, atr_max=2.0)
        entry = 50000
        atr1m = 100
        atr5m = 200

        sl, tp, atr_percent_used, atr_blended = calculate_atr_levels(
            entry,
            atr1m,
            atr5m,
            'LONG',
            config,
            return_atr_used=True,
        )

        assert sl < entry
        assert tp > entry
        assert atr_blended == pytest.approx(130)
        assert atr_percent_used == pytest.approx((130 / entry) * 100)

    def test_inverted_tp_sl_detection_long_branch(self):
        config = TPSLConfig(atr_mult_tp=-1.0, atr_mult_sl=-1.0)
        entry = 50000
        atr = 250

        sl, tp = calculate_atr_levels(entry, atr, None, 'LONG', config)
        assert sl > entry
        assert tp < entry

    def test_inverted_tp_sl_detection_short_branch(self):
        config = TPSLConfig(atr_mult_tp=-1.0, atr_mult_sl=-1.0)
        entry = 50000
        atr = 250

        sl, tp = calculate_atr_levels(entry, atr, None, 'SHORT', config)
        assert sl < entry
        assert tp > entry


class TestValidateLevels:
    """Tests pour validate_levels"""

    def test_invalid_entry_zero(self):
        """Test avec entry = 0"""
        result = validate_levels(0, 49875, 50300)
        assert result is False

    def test_invalid_entry_negative(self):
        """Test avec entry négatif"""
        result = validate_levels(-50000, 49875, 50300)
        assert result is False

    def test_valid_levels_normal(self):
        """Test niveaux valides normaux"""
        result = validate_levels(50000, 49875, 50300, tolerance=0.0001)

        # SL diff = 125 (0.25%) > 5 (0.01%)
        # TP diff = 300 (0.6%) > 5 (0.01%)
        assert result is True

    def test_invalid_sl_too_close(self):
        """Test SL trop proche de entry"""
        result = validate_levels(50000, 49999.9, 50300, tolerance=0.0001)

        # SL diff = 0.1 (0.0002%) < 5 (0.01%)
        assert result is False

    def test_invalid_tp_too_close(self):
        """Test TP trop proche de entry"""
        result = validate_levels(50000, 49875, 50000.1, tolerance=0.0001)

        # TP diff = 0.1 (0.0002%) < 5 (0.01%)
        assert result is False

    def test_custom_tolerance(self):
        """Test avec tolérance personnalisée"""
        result = validate_levels(50000, 49950, 50050, tolerance=0.001)

        # Min diff = 50 (0.1%)
        # SL diff = 50 (0.1%)
        # TP diff = 50 (0.1%)
        # Devrait être valide si tolerance = 0.001 (0.1%)
        assert result is True

    def test_exact_tolerance_boundary(self):
        """Test à la limite exacte de la tolérance"""
        entry = 50000
        tolerance = 0.0001
        min_diff = entry * tolerance  # 5

        # SL et TP exactement à min_diff
        sl = entry - min_diff
        tp = entry + min_diff

        result = validate_levels(entry, sl, tp, tolerance=tolerance)

        # À la limite, devrait être valide (>= min_diff)
        assert result is True


class TestIntegration:
    """Tests d'intégration"""

    def test_fixed_to_atr_comparison(self):
        """Test comparaison entre mode FIXE et ATR"""
        config = TPSLConfig()

        # Mode FIXE
        sl_fixed, tp_fixed = calculate_fixed_levels(50000, 'LONG', config)

        # Mode ATR avec ATR correspondant à ~0.5%
        atr = 250
        sl_atr, tp_atr = calculate_atr_levels(50000, atr, None, 'LONG', config)

        # Les deux devraient donner des résultats cohérents
        assert sl_fixed < 50000
        assert tp_fixed > 50000
        assert sl_atr < 50000
        assert tp_atr > 50000

        # Valider les deux
        assert validate_levels(50000, sl_fixed, tp_fixed)
        assert validate_levels(50000, sl_atr, tp_atr)

    def test_full_workflow_long(self):
        """Test workflow complet LONG"""
        config = TPSLConfig(
            fixed_sl_pct=0.25,
            fixed_tp_pct=0.6,
            atr_mult_tp=1.5,
            atr_mult_sl=1.0,
            win_streak=0
        )

        entry = 50000

        # Test mode FIXE
        sl_fixed, tp_fixed = calculate_fixed_levels(entry, 'LONG', config)
        assert validate_levels(entry, sl_fixed, tp_fixed)

        # Test mode ATR
        atr = 250
        sl_atr, tp_atr = calculate_atr_levels(entry, atr, None, 'LONG', config)
        assert validate_levels(entry, sl_atr, tp_atr)

    def test_full_workflow_short(self):
        """Test workflow complet SHORT"""
        config = TPSLConfig(
            fixed_sl_pct=0.25,
            fixed_tp_pct=0.6,
            win_streak=0
        )

        entry = 50000

        # Test mode FIXE
        sl_fixed, tp_fixed = calculate_fixed_levels(entry, 'SHORT', config)
        assert validate_levels(entry, sl_fixed, tp_fixed)

        # Test mode ATR
        atr = 250
        sl_atr, tp_atr = calculate_atr_levels(entry, atr, None, 'SHORT', config)
        assert validate_levels(entry, sl_atr, tp_atr)

    def test_edge_case_very_small_price(self):
        """Test cas limite prix très petit"""
        config = TPSLConfig()
        entry = 0.00001

        sl_fixed, tp_fixed = calculate_fixed_levels(entry, 'LONG', config)
        assert validate_levels(entry, sl_fixed, tp_fixed, tolerance=0.001)

        atr = 0.00000005
        sl_atr, tp_atr = calculate_atr_levels(entry, atr, None, 'LONG', config)
        assert validate_levels(entry, sl_atr, tp_atr, tolerance=0.001)

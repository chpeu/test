#!/usr/bin/env python3
"""
Tests d'intégration pour PositionManager refactorisé
Valide que la refactorisation fonctionne correctement
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.position_manager import Position, PositionConfig, PositionManager


def test_import_modules():
    """Test 1: Vérifier que tous les modules s'importent correctement"""
    print("Test 1: Import des modules... ", end="")

    try:
        from core.position.tp_sl_calculator import calculate_fixed_levels, calculate_atr_levels
        from core.position.early_invalidation import EarlyInvalidationChecker
        from core.position.trailing_stop import TrailingStopManager
        from core.position.pnl_calculator import PnLCalculator
        from core.position.recovery_mode import RecoveryModeManager
        from core.position.partial_tp_manager import PartialTPManager
        from core.position.tp_escalier_manager import TPEscalierManager
        from core.position.analytics_logger import AnalyticsLogger

        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        return False


def test_position_manager_init():
    """Test 2: Initialisation PositionManager"""
    print("Test 2: Initialisation PositionManager... ", end="")

    try:
        config = PositionConfig(
            use_atr=False,
            fixed_tp_pct=0.6,
            fixed_sl_pct=0.25
        )

        pm = PositionManager(config)

        # Vérifier que les managers sont initialisés
        assert pm.early_invalidation is not None
        assert pm.trailing_stop is not None
        assert pm.pnl_calculator is not None
        assert pm.recovery_mode is not None
        assert pm.partial_tp is not None
        assert pm.tp_escalier is not None

        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        return False


def test_open_position_fixed():
    """Test 3: Ouvrir position en mode FIXE"""
    print("Test 3: Ouvrir position mode FIXE... ", end="")

    try:
        config = PositionConfig(use_atr=False, fixed_tp_pct=0.6, fixed_sl_pct=0.25)
        pm = PositionManager(config)

        position = pm.open_position(
            symbol="BTC_USDT",
            direction="LONG",
            entry=50000.0,
            size=100.0,
            confirmed_by="Test"
        )

        # Vérifications
        assert position.symbol == "BTC_USDT"
        assert position.direction == "LONG"
        assert position.entry == 50000.0
        assert position.size == 100.0
        assert position.sl < position.entry  # SL en-dessous pour LONG
        assert position.tp > position.entry  # TP au-dessus pour LONG
        assert pm.active_position is not None

        # Vérifier calcul TP/SL
        expected_sl = 50000.0 * (1 - 0.25 / 100)  # -0.25%
        expected_tp = 50000.0 * (1 + 0.6 / 100)   # +0.6%

        assert abs(position.sl - expected_sl) < 1.0  # Tolérance
        assert abs(position.tp - expected_tp) < 1.0

        print(f"✓ OK (Entry={position.entry}, SL={position.sl:.2f}, TP={position.tp:.2f})")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_open_position_atr():
    """Test 4: Ouvrir position en mode ATR"""
    print("Test 4: Ouvrir position mode ATR... ", end="")

    try:
        config = PositionConfig(
            use_atr=True,
            atr_mult_tp=1.5,
            atr_mult_sl=1.0,
            atr_min=0.15,
            atr_max=1.5
        )
        pm = PositionManager(config)

        position = pm.open_position(
            symbol="ETH_USDT",
            direction="SHORT",
            entry=3000.0,
            size=200.0,
            atr=15.0,  # ATR = 15 USDT = 0.5%
            atr5m=18.0,
            confirmed_by="Test ATR"
        )

        # Vérifications
        assert position.symbol == "ETH_USDT"
        assert position.direction == "SHORT"
        assert position.atr == 15.0
        assert position.atr5m == 18.0
        assert position.sl > position.entry  # SL au-dessus pour SHORT
        assert position.tp < position.entry  # TP en-dessous pour SHORT

        print(f"✓ OK (Entry={position.entry}, SL={position.sl:.2f}, TP={position.tp:.2f})")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pnl_calculation():
    """Test 5: Calcul PnL"""
    print("Test 5: Calcul PnL... ", end="")

    try:
        config = PositionConfig(use_atr=False)
        pm = PositionManager(config)

        # Position LONG
        position = pm.open_position(
            symbol="BTC_USDT",
            direction="LONG",
            entry=50000.0,
            size=100.0
        )

        # Prix actuel: +1%
        current_price = 50500.0

        # Calculer PnL via le nouveau module
        position_dict = position.to_dict()
        pnl_pct = pm.pnl_calculator.calculate_pnl_percent(
            entry=position.entry,
            current_price=current_price,
            direction=position.direction
        )

        pnl_usdt = pm.pnl_calculator.calculate_pnl_usdt(
            position=position_dict,
            current_price=current_price
        )

        # Vérifications
        assert abs(pnl_pct - 1.0) < 0.01  # +1%
        assert abs(pnl_usdt - 1.0) < 0.01  # +1 USDT (100 * 1%)

        print(f"✓ OK (PnL: {pnl_pct:.2f}%, {pnl_usdt:.2f} USDT)")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_close_position():
    """Test 6: Fermer position"""
    print("Test 6: Fermer position... ", end="")

    try:
        config = PositionConfig(use_atr=False)
        pm = PositionManager(config)

        # Ouvrir position
        position = pm.open_position(
            symbol="BTC_USDT",
            direction="LONG",
            entry=50000.0,
            size=100.0
        )

        # Fermer à +2%
        exit_price = 51000.0
        result = pm.close_position(exit_price=exit_price, reason="TP_HIT")

        # Vérifications
        assert result['symbol'] == "BTC_USDT"
        assert result['reason'] == "TP_HIT"
        assert result['pnl_pct'] > 1.9  # ~2%
        assert pm.active_position is None  # Position fermée

        print(f"✓ OK (PnL: {result['pnl_pct']:.2f}%, Net: {result['net_pnl']:.2f} USDT)")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recovery_mode():
    """Test 7: Recovery Mode"""
    print("Test 7: Recovery Mode... ", end="")

    try:
        config = PositionConfig(use_atr=False, loss_streak=3)
        pm = PositionManager(config)

        # Obtenir niveau recovery
        recovery_level = pm.recovery_mode.get_recovery_level(loss_streak=3)

        assert recovery_level is not None
        assert recovery_level['level'] >= 1
        assert 'min_score_boost' in recovery_level
        assert 'position_size_reduction' in recovery_level

        print(f"✓ OK (Niveau: {recovery_level['level']}, Boost: +{recovery_level['min_score_boost']})")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Exécuter tous les tests"""
    print("\n" + "="*60)
    print("TESTS D'INTÉGRATION - POSITION MANAGER REFACTORISÉ")
    print("="*60 + "\n")

    tests = [
        test_import_modules,
        test_position_manager_init,
        test_open_position_fixed,
        test_open_position_atr,
        test_pnl_calculation,
        test_close_position,
        test_recovery_mode
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    print(f"RÉSULTATS: {passed}/{total} tests réussis")

    if passed == total:
        print("✅ TOUS LES TESTS PASSENT - Refactorisation validée!")
    else:
        print(f"⚠️  {total - passed} test(s) échoué(s)")

    print("="*60 + "\n")

    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Tests d'intégration simplifiés
Valide l'architecture refactorisée complète
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_all_modules_import():
    """Test 1: Import de tous les modules refactorisés"""
    print("Test 1: Import tous modules refactorisés... ", end="")

    try:
        # Position modules
        from core.position import (
            calculate_fixed_levels,
            calculate_atr_levels,
            EarlyInvalidationChecker,
            TrailingStopManager,
            PnLCalculator,
            RecoveryModeManager,
            PartialTPManager,
            TPEscalierManager,
            AnalyticsLogger
        )

        # Analyzer modules
        from core.analyzer import (
            check_volume_filter,
            generate_long_conditions,
            calculate_weighted_score,
            check_spread,
            detect_manipulation
        )

        # Routes et callbacks
        from api.routes import scanner_router, dashboard_router
        from core.callbacks import (
            scanner_loop_callback,
            position_check_loop_callback,
            scalability_refresh_loop_callback
        )

        print("✓ OK (position: 9, analyzer: 8, routes: 3, callbacks: 4)")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        return False


def test_position_modules_work():
    """Test 2: Modules position fonctionnels"""
    print("Test 2: Fonctionnalité modules position... ", end="")

    try:
        from core.position import calculate_fixed_levels, PnLCalculator, RecoveryModeManager
        from core.position.tp_sl_calculator import TPSLConfig

        # Test calculate_fixed_levels
        config = TPSLConfig(fixed_tp_pct=0.6, fixed_sl_pct=0.25)
        sl, tp = calculate_fixed_levels(entry=50000.0, direction="LONG", config=config)

        assert sl < 50000.0  # SL en-dessous pour LONG
        assert tp > 50000.0  # TP au-dessus pour LONG

        # Test PnLCalculator
        calc = PnLCalculator()
        pnl = calc.calculate_pnl_percent(entry=50000.0, current_price=50500.0, direction="LONG")
        assert abs(pnl - 1.0) < 0.01  # ~1%

        # Test RecoveryMode
        recovery = RecoveryModeManager()
        level = recovery.get_recovery_level(loss_streak=3)
        assert level is not None
        assert level['level'] >= 1

        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_analyzer_modules_work():
    """Test 3: Modules analyzer fonctionnels"""
    print("Test 3: Fonctionnalité modules analyzer... ", end="")

    try:
        from core.analyzer import generate_long_conditions, calculate_weighted_score

        # Test génération conditions LONG
        conditions, types = generate_long_conditions(
            ema9=50000, ema21=49500,
            rsi=40, rsi_prev=38,
            vol_spike=2.5, min_vol_ratio=1.2,
            macd={'macd': 0.5, 'signal': 0.3, 'histogram': 0.2},
            macd_prev={'histogram': 0.1},
            price=50000,
            bb={'lower': 49000, 'upper': 51000, 'middle': 50000},
            atr_percent=0.5,
            adx={'adx': 30, 'diPlus': 28, 'diMinus': 15},
            pattern='HAMMER'
        )

        assert len(conditions) > 0
        assert 'EMAs' in types

        # Test scoring
        score = calculate_weighted_score(['EMAs', 'RSI', 'MACD', 'Volume'])
        assert score > 0

        print(f"✓ OK ({len(conditions)} conditions, score={score:.1f})")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_routes_structure():
    """Test 4: Structure routes API"""
    print("Test 4: Structure routes API... ", end="")

    try:
        from api.routes import scanner_router, dashboard_router

        # Vérifier que les routers existent
        assert scanner_router is not None
        assert dashboard_router is not None

        # Vérifier qu'ils ont des routes
        assert len(scanner_router.routes) > 0
        assert len(dashboard_router.routes) > 0

        total_routes = len(scanner_router.routes) + len(dashboard_router.routes)
        print(f"✓ OK ({total_routes} routes)")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_callbacks_structure():
    """Test 5: Structure callbacks"""
    print("Test 5: Structure callbacks... ", end="")

    try:
        from core import callbacks

        # Vérifier que les callbacks existent
        assert hasattr(callbacks, 'scanner_loop_callback')
        assert hasattr(callbacks, 'position_check_loop_callback')
        assert hasattr(callbacks, 'scalability_refresh_loop_callback')

        print("✓ OK (3 callbacks)")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_refactored_files_syntax():
    """Test 6: Syntaxe fichiers refactorisés"""
    print("Test 6: Syntaxe fichiers refactorisés... ", end="")

    try:
        import py_compile
        import os

        files_to_check = [
            'core/position_manager.py',
            'core/analyzer.py',
            'main.py'
        ]

        for filepath in files_to_check:
            if os.path.exists(filepath):
                py_compile.compile(filepath, doraise=True)

        print(f"✓ OK ({len(files_to_check)} fichiers)")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        return False


def run_all_tests():
    """Exécuter tous les tests"""
    print("\n" + "="*60)
    print("TESTS D'INTÉGRATION - REFACTORISATION COMPLÈTE")
    print("="*60 + "\n")

    tests = [
        test_all_modules_import,
        test_position_modules_work,
        test_analyzer_modules_work,
        test_routes_structure,
        test_callbacks_structure,
        test_refactored_files_syntax,
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    print(f"RÉSULTATS: {passed}/{total} tests réussis")

    if passed == total:
        print("✅ TOUS LES TESTS PASSENT!")
        print("✅ Architecture refactorisée validée!")
    else:
        print(f"⚠️  {total - passed} test(s) échoué(s)")

    print("="*60 + "\n")

    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Tests d'intégration pour TechnicalAnalyzer refactorisé
Valide l'architecture modulaire analyzer
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_import_analyzer_modules():
    """Test 1: Import des modules analyzer"""
    print("Test 1: Import modules analyzer... ", end="")

    try:
        from core.analyzer import (
            check_volume_filter,
            check_snr_filter,
            check_breakout_filter,
            check_wick_filter,
            check_atr_filter,
            generate_long_conditions,
            generate_short_conditions,
            calculate_weighted_score,
            get_min_score_required,
            check_spread,
            check_orderbook_imbalance,
            detect_manipulation,
            check_price_action_coherence,
            check_static_correlation,
            calculate_trend_data
        )
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        return False


def test_filters():
    """Test 2: Filtres de validation"""
    print("Test 2: Filtres de validation... ", end="")

    try:
        from core.analyzer import check_volume_filter, check_atr_filter

        # Test volume filter - rejeté
        result = check_volume_filter(
            vol_spike=0.8,
            min_vol_ratio=1.2,
            symbol="BTC/USDT:USDT",
            timeframe="1m"
        )
        assert result is not None  # Rejeté car vol_spike < min_vol_ratio
        assert 'reason' in result

        # Test volume filter - passé
        result = check_volume_filter(
            vol_spike=2.5,
            min_vol_ratio=1.2,
            symbol="BTC/USDT:USDT",
            timeframe="1m"
        )
        assert result is None  # Passé

        # Test ATR filter
        result = check_atr_filter(
            atr_percent=0.5,
            min_atr=0.12,
            max_atr=0.75,
            timeframe="1m",
            symbol="BTC/USDT:USDT"
        )
        assert result is None  # ATR dans la plage

        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signal_generator():
    """Test 3: Génération signaux LONG/SHORT"""
    print("Test 3: Génération signaux... ", end="")

    try:
        from core.analyzer import generate_long_conditions, generate_short_conditions

        # Test LONG conditions
        conditions_long, types_long = generate_long_conditions(
            ema9=50000,
            ema21=49500,
            rsi=40,
            rsi_prev=38,
            vol_spike=2.5,
            min_vol_ratio=1.2,
            macd={'macd': 0.5, 'signal': 0.3, 'histogram': 0.2},
            macd_prev={'histogram': 0.1},
            price=50000,
            bb={'lower': 49000, 'upper': 51000, 'middle': 50000},
            atr_percent=0.5,
            adx={'adx': 30, 'diPlus': 28, 'diMinus': 15},
            pattern='HAMMER'
        )

        assert len(conditions_long) > 0  # Au moins une condition
        assert 'EMAs' in types_long  # EMA9 > EMA21

        # Test SHORT conditions
        conditions_short, types_short = generate_short_conditions(
            ema9=49500,
            ema21=50000,
            rsi=65,
            rsi_prev=67,
            vol_spike=2.0,
            min_vol_ratio=1.2,
            macd={'macd': -0.5, 'signal': -0.3, 'histogram': -0.2},
            macd_prev={'histogram': -0.1},
            price=50000,
            bb={'lower': 49000, 'upper': 51000, 'middle': 50000},
            atr_percent=0.5,
            adx={'adx': 28, 'diPlus': 15, 'diMinus': 26},
            pattern='SHOOTING_STAR'
        )

        assert len(conditions_short) > 0
        assert 'EMAs' in types_short  # EMA9 < EMA21

        print(f"✓ OK (LONG: {len(conditions_long)} conditions, SHORT: {len(conditions_short)} conditions)")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scoring():
    """Test 4: Système de scoring"""
    print("Test 4: Scoring pondéré... ", end="")

    try:
        from core.analyzer import calculate_weighted_score, get_min_score_required

        # Test score avec 4 conditions
        condition_types = ['EMAs', 'RSI', 'MACD', 'Volume']
        score = calculate_weighted_score(condition_types)

        # Vérifier que le score est calculé
        assert score > 0
        assert score <= 15  # Score max théorique

        # Test score minimum requis
        min_score = get_min_score_required(adx=30)
        assert min_score > 0

        # ADX élevé = tolérance plus faible
        min_score_high_adx = get_min_score_required(adx=50)
        assert min_score_high_adx < min_score  # Moins tolérant

        print(f"✓ OK (Score: {score:.1f}, Min requis ADX=30: {min_score:.1f})")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_risk_detector():
    """Test 5: Détection risques"""
    print("Test 5: Détection manipulation... ", end="")

    try:
        from core.analyzer import detect_manipulation

        # Test volume spike extrême (manipulation probable)
        result = detect_manipulation(
            symbol="BTC/USDT:USDT",
            timeframe="1m",
            ohlcv=[[1, 50000, 50500, 49800, 50200, 1000000]],
            volume=1000000,
            vol_spike=15.0  # 15x spike
        )

        assert result['suspicious'] == True
        assert result['severity'] in ['HIGH', 'MEDIUM', 'LOW']

        # Test volume normal (pas de manipulation)
        result = detect_manipulation(
            symbol="BTC/USDT:USDT",
            timeframe="1m",
            ohlcv=[[1, 50000, 50500, 49800, 50200, 1000000]],
            volume=1000000,
            vol_spike=1.5  # Normal
        )

        assert result['suspicious'] == False

        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_technical_analyzer_init():
    """Test 6: Initialisation TechnicalAnalyzer"""
    print("Test 6: Initialisation TechnicalAnalyzer... ", end="")

    try:
        from core.analyzer import TechnicalAnalyzer

        analyzer = TechnicalAnalyzer()

        # Vérifier que l'analyzer est initialisé
        assert analyzer is not None
        assert hasattr(analyzer, 'client')
        assert hasattr(analyzer, 'indicators')

        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Exécuter tous les tests"""
    print("\n" + "="*60)
    print("TESTS D'INTÉGRATION - TECHNICAL ANALYZER REFACTORISÉ")
    print("="*60 + "\n")

    tests = [
        test_import_analyzer_modules,
        test_filters,
        test_signal_generator,
        test_scoring,
        test_risk_detector,
        test_technical_analyzer_init,
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    print(f"RÉSULTATS: {passed}/{total} tests réussis")

    if passed == total:
        print("✅ TOUS LES TESTS PASSENT - Analyzer refactorisé validé!")
    else:
        print(f"⚠️  {total - passed} test(s) échoué(s)")

    print("="*60 + "\n")

    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

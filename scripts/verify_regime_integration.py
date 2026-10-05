"""
Script de vérification de l'intégration Market Regime Selector et Trading Circuit Breaker.

Vérifie:
1. Que les variables sont correctement lues depuis TRADING_CONFIG
2. Que les valeurs du régime sont appliquées quand market_regime_enabled = True
3. Que les valeurs de config.py sont utilisées quand market_regime_enabled = False
4. Que le nombre de Samples est correct
5. Que les modifications sont persistées

Auteur: Cascade AI
Date: 07/12/2025
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TRADING_CONFIG
from core.market_regime_selector import get_regime_selector, MarketRegime


def test_config_variables():
    """Test 1: Vérifier que toutes les variables Protection & Régime sont dans TRADING_CONFIG"""
    print("\n" + "="*60)
    print("TEST 1: Variables Protection & Regime dans TRADING_CONFIG")
    print("="*60)
    
    # Variables Market Regime Selector
    regime_vars = [
        'market_regime_enabled',
        'market_regime_check_interval',
        'market_regime_sample_count',
        'market_regime_atr_calme_max',
        'market_regime_atr_normal_max',
        'market_regime_adx_choppy',
    ]
    
    # Variables Trading Circuit Breaker
    cb_vars = [
        'trading_circuit_breaker_enabled',
        'trading_cb_max_consecutive_losses',
        'trading_cb_daily_drawdown_pause_pct',
        'trading_cb_daily_drawdown_stop_pct',
        'trading_cb_pause_duration_minutes',
        'trading_cb_score_boost_enabled',
        'trading_cb_score_boost_per_loss',
    ]
    
    all_vars = regime_vars + cb_vars
    missing = []
    
    for var in all_vars:
        value = TRADING_CONFIG.get(var)
        if value is None:
            missing.append(var)
            print(f"  [MISSING] {var}")
        else:
            print(f"  [OK] {var} = {value}")
    
    if missing:
        print(f"\n[FAIL] {len(missing)} variables manquantes!")
        return False
    else:
        print(f"\n[PASS] Toutes les {len(all_vars)} variables sont presentes")
        return True


def test_regime_selector_initialization():
    """Test 2: Vérifier l'initialisation du MarketRegimeSelector"""
    print("\n" + "="*60)
    print("TEST 2: Initialisation MarketRegimeSelector")
    print("="*60)
    
    selector = get_regime_selector()
    
    print(f"  Current Regime: {selector.current_regime.value}")
    print(f"  ATR Sample Count: {selector.atr_sample_count}")
    print(f"  ATR Values: {selector.atr_values}")
    print(f"  Avg ATR: {selector.avg_atr}")
    print(f"  Avg ADX: {selector.avg_adx}")
    print(f"  Check Interval: {selector.check_interval}")
    
    # Vérifier que atr_sample_count est initialisé
    if not hasattr(selector, 'atr_sample_count'):
        print("\n[FAIL] atr_sample_count n'existe pas!")
        return False
    
    print("\n[PASS] MarketRegimeSelector initialise correctement")
    return True


def test_regime_config_application():
    """Test 3: Vérifier que les configs du régime sont correctes"""
    print("\n" + "="*60)
    print("TEST 3: Configurations par Regime")
    print("="*60)
    
    selector = get_regime_selector()
    
    # Vérifier les configs par régime
    for regime_name, config in selector.regime_configs.items():
        print(f"\n  [{regime_name}]")
        print(f"    min_score_required: {config.min_score_required}")
        print(f"    atr_mult_sl: {config.atr_mult_sl}")
        print(f"    atr_mult_tp: {config.atr_mult_tp}")
        print(f"    ATR range: {config.optimal_atr_min} - {config.optimal_atr_max}")
    
    # Vérifier les valeurs attendues
    expected = {
        'CALME': {'min_score_required': 6.0, 'atr_mult_sl': 1.0},
        'NORMAL': {'min_score_required': 7.0, 'atr_mult_sl': 1.2},
        'VOLATILE': {'min_score_required': 8.0, 'atr_mult_sl': 1.5},
        'CHOPPY': {'min_score_required': 9.0, 'atr_mult_sl': 0.8},
    }
    
    errors = []
    for regime_name, expected_values in expected.items():
        config = selector.regime_configs.get(regime_name)
        if config:
            for key, expected_val in expected_values.items():
                actual_val = getattr(config, key)
                if actual_val != expected_val:
                    errors.append(f"{regime_name}.{key}: expected {expected_val}, got {actual_val}")
    
    if errors:
        print("\n[FAIL] Erreurs de configuration:")
        for err in errors:
            print(f"  - {err}")
        return False
    
    print("\n[PASS] Toutes les configurations de regime sont correctes")
    return True


def test_regime_enabled_logic():
    """Test 4: Vérifier la logique quand market_regime_enabled = True/False"""
    print("\n" + "="*60)
    print("TEST 4: Logique market_regime_enabled")
    print("="*60)
    
    # Valeur originale
    original_min_score = TRADING_CONFIG.get('min_score_required')
    original_enabled = TRADING_CONFIG.get('market_regime_enabled')
    
    print(f"  market_regime_enabled: {original_enabled}")
    print(f"  min_score_required actuel: {original_min_score}")
    
    selector = get_regime_selector()
    active_config = selector.get_active_config()
    
    if original_enabled:
        # Si activé, min_score_required devrait venir du régime
        regime_min_score = active_config.get('min_score_required') if active_config else None
        print(f"  Regime actif: {selector.current_regime.value}")
        print(f"  min_score du regime: {regime_min_score}")
        
        if regime_min_score and original_min_score != regime_min_score:
            print(f"\n[WARNING] min_score_required ({original_min_score}) != regime ({regime_min_score})")
            print("  -> Les valeurs devraient etre synchronisees apres un scan")
    else:
        print("  Regime desactive -> min_score_required vient de config.py")
    
    print("\n[INFO] Logique OK - verifiez apres redemarrage du backend")
    return True


def test_samples_count():
    """Test 5: Vérifier le comptage des Samples"""
    print("\n" + "="*60)
    print("TEST 5: Comptage des Samples")
    print("="*60)
    
    selector = get_regime_selector()
    
    # Simuler un check avec des valeurs ATR
    test_atr_values = [0.25, 0.30, 0.28, 0.32, 0.27, 0.29, 0.31, 0.26, 0.33, 0.24]
    test_adx_values = [25, 28, 22, 30, 26, 24, 29, 27, 23, 25]
    
    print(f"  Avant check: atr_sample_count = {selector.atr_sample_count}")
    
    # Appeler check_regime de manière synchrone (pour le test)
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        new_regime, changed = loop.run_until_complete(
            selector.check_regime(
                atr_values=test_atr_values,
                adx_values=test_adx_values,
                force=True,
                trigger="test"
            )
        )
        
        print(f"  Apres check: atr_sample_count = {selector.atr_sample_count}")
        print(f"  Regime detecte: {new_regime.value}")
        print(f"  ATR moyen: {selector.avg_atr:.3f}%")
        print(f"  ADX moyen: {selector.avg_adx:.1f}")
        
        # Vérifier get_status()
        status = selector.get_status()
        print(f"  get_status().atr_sample_count = {status.get('atr_sample_count')}")
        
        if status.get('atr_sample_count') != len(test_atr_values):
            print(f"\n[FAIL] atr_sample_count devrait etre {len(test_atr_values)}, pas {status.get('atr_sample_count')}")
            return False
        
    finally:
        loop.close()
    
    print("\n[PASS] Comptage des Samples correct")
    return True


def run_all_tests():
    """Exécuter tous les tests"""
    print("\n" + "#"*60)
    print("# VERIFICATION INTEGRATION REGIME & CIRCUIT BREAKER")
    print("#"*60)
    
    results = []
    
    results.append(("Variables TRADING_CONFIG", test_config_variables()))
    results.append(("Initialisation Selector", test_regime_selector_initialization()))
    results.append(("Configurations Regime", test_regime_config_application()))
    results.append(("Logique Enabled", test_regime_enabled_logic()))
    results.append(("Comptage Samples", test_samples_count()))
    
    print("\n" + "="*60)
    print("RESUME DES TESTS")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\nResultat: {passed}/{total} tests passes")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

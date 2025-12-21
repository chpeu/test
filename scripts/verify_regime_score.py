#!/usr/bin/env python3
"""
Script de vérification des scores minimums par régime.
Vérifie que le bot applique correctement les nouveaux seuils.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from core.market_regime_selector import DEFAULT_REGIME_CONFIGS, MarketRegimeSelector
from utils.effective_config import get_effective_value, set_regime_adjustments, clear_all_adjustments
from config import TRADING_CONFIG

# Valeurs attendues après modification du 19/12/2025
EXPECTED_SCORES = {
    "CALME": 8.5,
    "NORMAL": 8.0,
    "VOLATILE": 7.5,
    "CHOPPY": 10.0
}

def print_header(text):
    print(f"\n{'='*60}")
    print(f" {text}")
    print(f"{'='*60}")

def verify_default_configs():
    """Vérifie les valeurs dans DEFAULT_REGIME_CONFIGS"""
    print_header("1. VERIFICATION DEFAULT_REGIME_CONFIGS")
    
    all_ok = True
    for regime, expected in EXPECTED_SCORES.items():
        config = DEFAULT_REGIME_CONFIGS.get(regime)
        if config:
            actual = config.min_score_required
            status = "[OK]" if actual == expected else "[FAIL]"
            if actual != expected:
                all_ok = False
            print(f"  {status} {regime}: min_score = {actual} (attendu: {expected})")
        else:
            print(f"  [FAIL] {regime}: Config non trouvée!")
            all_ok = False
    
    return all_ok

def verify_regime_selector():
    """Vérifie que MarketRegimeSelector utilise les bonnes valeurs"""
    print_header("2. VERIFICATION MARKET_REGIME_SELECTOR")
    
    selector = MarketRegimeSelector()
    
    all_ok = True
    for regime, expected in EXPECTED_SCORES.items():
        config = selector.regime_configs.get(regime)
        if config:
            actual = config.min_score_required
            status = "[OK]" if actual == expected else "[FAIL]"
            if actual != expected:
                all_ok = False
            print(f"  {status} {regime}: min_score = {actual}")
        else:
            print(f"  [FAIL] {regime}: Config non trouvée dans selector!")
            all_ok = False
    
    return all_ok

def verify_effective_config():
    """Vérifie que les ajustements de régime sont bien appliqués"""
    print_header("3. VERIFICATION EFFECTIVE_CONFIG")
    
    all_ok = True
    
    for regime, expected in EXPECTED_SCORES.items():
        # Réinitialiser
        clear_all_adjustments()
        
        # Simuler l'activation du régime
        config = DEFAULT_REGIME_CONFIGS.get(regime)
        if config:
            adjustments = {
                'min_score_required': config.min_score_required,
                'atr_mult_sl': config.atr_mult_sl,
            }
            set_regime_adjustments(adjustments)
            
            # Vérifier valeur effective
            effective = get_effective_value('min_score_required')
            status = "[OK]" if effective == expected else "[FAIL]"
            if effective != expected:
                all_ok = False
            print(f"  {status} {regime}: effective min_score = {effective} (attendu: {expected})")
        else:
            print(f"  [FAIL] {regime}: Config non trouvée!")
            all_ok = False
    
    # Nettoyer
    clear_all_adjustments()
    
    return all_ok

def verify_base_config():
    """Vérifie la valeur de base dans TRADING_CONFIG"""
    print_header("4. VERIFICATION CONFIG DE BASE")
    
    base_min_score = TRADING_CONFIG.get('min_score_required', 'N/A')
    print(f"  TRADING_CONFIG['min_score_required'] = {base_min_score}")
    print(f"  (Cette valeur est utilisée quand le régime est désactivé)")
    
    return True

def simulate_score_check():
    """Simule la vérification de score pour chaque régime"""
    print_header("5. SIMULATION VERIFICATION SCORE")
    
    test_scores = [6.0, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5]
    
    print(f"\n  Test avec différents scores de setup:")
    print(f"  {'Score':<8} | {'CALME':<10} | {'NORMAL':<10} | {'VOLATILE':<10} | {'CHOPPY':<10}")
    print(f"  {'-'*8} | {'-'*10} | {'-'*10} | {'-'*10} | {'-'*10}")
    
    for score in test_scores:
        results = []
        for regime in ["CALME", "NORMAL", "VOLATILE", "CHOPPY"]:
            min_required = EXPECTED_SCORES[regime]
            accepted = score >= min_required
            results.append("ACCEPT" if accepted else "REJECT")
        
        print(f"  {score:<8} | {results[0]:<10} | {results[1]:<10} | {results[2]:<10} | {results[3]:<10}")
    
    return True

def main():
    print("\n" + "="*60)
    print(" VERIFICATION SCORES MINIMUMS PAR REGIME (19/12/2025)")
    print("="*60)
    
    results = []
    
    results.append(("DEFAULT_REGIME_CONFIGS", verify_default_configs()))
    results.append(("MarketRegimeSelector", verify_regime_selector()))
    results.append(("EffectiveConfig", verify_effective_config()))
    results.append(("Base Config", verify_base_config()))
    results.append(("Simulation", simulate_score_check()))
    
    print_header("RESUME")
    
    all_passed = True
    for name, passed in results:
        status = "[OK]" if passed else "[FAIL]"
        if not passed:
            all_passed = False
        print(f"  {status} {name}")
    
    print()
    if all_passed:
        print("  [SUCCESS] Tous les tests passent!")
        print("  Les nouveaux scores minimums sont correctement configurés:")
        for regime, score in EXPECTED_SCORES.items():
            print(f"    - {regime}: {score}")
    else:
        print("  [ERROR] Certains tests ont échoué!")
        print("  Vérifiez les modifications dans market_regime_selector.py")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Script de vérification: Séparation Base Config vs Effective Config

Vérifie que:
1. Les sliders (TRADING_CONFIG) ne changent PAS quand le régime est activé
2. effective_config reflète bien les ajustements du régime
3. Quand le régime est désactivé, les valeurs de base sont utilisées

Auteur: Cascade AI
Date: 08/12/2025
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TRADING_CONFIG
from utils.effective_config import (
    get_base_config, 
    get_effective_config, 
    set_regime_adjustments,
    set_circuit_breaker_adjustments,
    clear_all_adjustments,
    get_config_summary
)
from core.market_regime_selector import get_regime_selector, MarketRegime

# Couleurs pour affichage
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(title: str):
    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{CYAN}{'='*60}{RESET}")

def print_test(test_name: str, passed: bool, details: str = ""):
    status = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    print(f"  {status} {test_name}")
    if details:
        print(f"         {details}")

def main():
    print(f"\n{BOLD}[VERIFICATION] Base Config vs Effective Config{RESET}")
    print(f"   Date: 08/12/2025")
    
    all_passed = True
    
    # =========================================================================
    # TEST 1: Les valeurs de base ne changent pas
    # =========================================================================
    print_header("TEST 1: Valeurs de Base (TRADING_CONFIG)")
    
    # Sauvegarder les valeurs initiales
    initial_min_score = TRADING_CONFIG.get('min_score_required')
    initial_atr_mult_sl = TRADING_CONFIG.get('atr_mult_sl')
    
    print(f"  Valeurs initiales (sliders):")
    print(f"    min_score_required: {initial_min_score}")
    print(f"    atr_mult_sl: {initial_atr_mult_sl}")
    
    # Simuler un ajustement de régime
    regime_adjustments = {
        'min_score_required': 9.0,  # Valeur différente
        'atr_mult_sl': 0.8,
    }
    set_regime_adjustments(regime_adjustments)
    
    # Vérifier que TRADING_CONFIG n'a pas changé
    current_min_score = TRADING_CONFIG.get('min_score_required')
    current_atr_mult_sl = TRADING_CONFIG.get('atr_mult_sl')
    
    test_passed = (current_min_score == initial_min_score and 
                   current_atr_mult_sl == initial_atr_mult_sl)
    all_passed = all_passed and test_passed
    
    print_test(
        "TRADING_CONFIG non modifié par régime",
        test_passed,
        f"min_score: {initial_min_score} → {current_min_score}"
    )
    
    # =========================================================================
    # TEST 2: Effective config reflète les ajustements
    # =========================================================================
    print_header("TEST 2: Effective Config avec Ajustements")
    
    effective = get_effective_config()
    effective_min_score = effective.get('min_score_required')
    effective_atr_mult_sl = effective.get('atr_mult_sl')
    
    print(f"  Valeurs effectives:")
    print(f"    min_score_required: {effective_min_score}")
    print(f"    atr_mult_sl: {effective_atr_mult_sl}")
    
    # Vérifier que effective a les valeurs du régime
    test_passed = (effective_min_score == 9.0 and effective_atr_mult_sl == 0.8)
    all_passed = all_passed and test_passed
    
    print_test(
        "Effective config contient ajustements régime",
        test_passed,
        f"min_score: {effective_min_score}, atr_mult_sl: {effective_atr_mult_sl}"
    )
    
    # =========================================================================
    # TEST 3: Ajustements Circuit Breaker s'additionnent
    # =========================================================================
    print_header("TEST 3: Ajustements Circuit Breaker")
    
    # Ajouter un score boost du CB
    cb_adjustments = {'score_boost': 1.5}
    set_circuit_breaker_adjustments(cb_adjustments)
    
    effective = get_effective_config()
    effective_min_score = effective.get('min_score_required')
    expected_score = 9.0 + 1.5  # régime (9.0) + CB boost (1.5)
    
    test_passed = abs(effective_min_score - expected_score) < 0.01
    all_passed = all_passed and test_passed
    
    print_test(
        "Score boost CB s'additionne au score régime",
        test_passed,
        f"min_score: {effective_min_score} (attendu: {expected_score})"
    )
    
    # =========================================================================
    # TEST 4: Effacer les ajustements restaure les valeurs base
    # =========================================================================
    print_header("TEST 4: Effacement des Ajustements")
    
    clear_all_adjustments()
    
    effective = get_effective_config()
    effective_min_score = effective.get('min_score_required')
    
    # Devrait être égal à la valeur de base
    test_passed = effective_min_score == initial_min_score
    all_passed = all_passed and test_passed
    
    print_test(
        "Après clear, effective = base",
        test_passed,
        f"min_score: {effective_min_score} (base: {initial_min_score})"
    )
    
    # =========================================================================
    # TEST 5: get_config_summary retourne les bonnes infos
    # =========================================================================
    print_header("TEST 5: Config Summary")
    
    # Remettre des ajustements pour tester
    set_regime_adjustments({'min_score_required': 8.5})
    
    summary = get_config_summary()
    
    has_base = 'base_config' in summary
    has_effective = 'effective_config' in summary
    has_adjustments = 'adjustments' in summary
    has_differences = 'differences' in summary
    
    test_passed = has_base and has_effective and has_adjustments and has_differences
    all_passed = all_passed and test_passed
    
    print_test(
        "Summary contient toutes les clés",
        test_passed,
        f"base: {has_base}, effective: {has_effective}, adjustments: {has_adjustments}"
    )
    
    # Vérifier les différences
    differences = summary.get('differences', {})
    has_min_score_diff = 'min_score_required' in differences
    
    print(f"  Différences détectées:")
    for key, diff in differences.items():
        print(f"    {key}: base={diff['base']} → effective={diff['effective']}")
    
    print_test(
        "Différences correctement calculées",
        has_min_score_diff,
        f"min_score_required différence: {has_min_score_diff}"
    )
    
    # =========================================================================
    # TEST 6: Régime désactivé = pas d'ajustements
    # =========================================================================
    print_header("TEST 6: Régime Désactivé")
    
    # Sauvegarder l'état actuel
    original_enabled = TRADING_CONFIG.get('market_regime_enabled', True)
    
    # Désactiver le régime
    TRADING_CONFIG['market_regime_enabled'] = False
    
    # Les ajustements régime sont toujours stockés mais ne sont pas appliqués
    set_regime_adjustments({'min_score_required': 9.0})
    
    effective = get_effective_config()
    effective_min_score = effective.get('min_score_required')
    
    # Quand régime désactivé, effective = base
    test_passed = effective_min_score == initial_min_score
    all_passed = all_passed and test_passed
    
    print_test(
        "Régime désactivé → ajustements ignorés",
        test_passed,
        f"min_score: {effective_min_score} (base: {initial_min_score})"
    )
    
    # Restaurer
    TRADING_CONFIG['market_regime_enabled'] = original_enabled
    
    # =========================================================================
    # RÉSULTAT FINAL
    # =========================================================================
    print_header("RÉSULTAT FINAL")
    
    if all_passed:
        print(f"\n  {GREEN}✅ TOUS LES TESTS PASSÉS{RESET}")
        print(f"\n  Le système de séparation base/effective fonctionne correctement.")
        print(f"  - Les sliders ne sont jamais modifiés automatiquement")
        print(f"  - L'onglet 'Variables en cours' affichera les valeurs effectives")
        print(f"  - Les ajustements régime/CB sont correctement appliqués")
    else:
        print(f"\n  {RED}❌ CERTAINS TESTS ONT ÉCHOUÉ{RESET}")
        print(f"\n  Vérifiez les erreurs ci-dessus.")
    
    # Nettoyer
    clear_all_adjustments()
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

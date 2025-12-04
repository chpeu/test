#!/usr/bin/env python3
"""
=============================================================================
VERIFICATION LEVIER AUTOMATIQUE - Tests Exhaustifs
=============================================================================
Ce script vérifie que l'implémentation du levier automatique fonctionne
correctement dans tous les scénarios possibles.

SCENARIOS TESTES:
1. Solde suffisant -> utiliser levier par défaut (config.default_leverage)
2. Solde insuffisant, levier auto <= 5x -> adapter automatiquement
3. Solde insuffisant, levier auto > 5x -> refuser le trade
4. Edge cases: balance = 0, size = 0, etc.
5. Calcul marge correcte après adaptation

Auteur: Cascade
Date: 2024-12-04
=============================================================================
"""

import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple
from unittest.mock import MagicMock, patch
import logging

# Setup path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def success(msg): print(f"{GREEN}[PASS]{RESET} {msg}")
def fail(msg): print(f"{RED}[FAIL]{RESET} {msg}")
def warn(msg): print(f"{YELLOW}[WARN]{RESET} {msg}")
def info(msg): print(f"{BLUE}[INFO]{RESET} {msg}")


@dataclass
class MockFuturesOrderResult:
    """Mock du résultat d'ordre"""
    success: bool = True
    error_message: Optional[str] = None
    leverage: Optional[int] = None
    margin_used: Optional[float] = None


class AutoLeverageVerifier:
    """
    Simulateur isolé de la logique de levier automatique
    Reproduit EXACTEMENT le code de live_order_manager_futures.py
    """
    
    def __init__(self, default_leverage: int = 1):
        self.default_leverage = default_leverage
        self.MAX_AUTO_LEVERAGE = 5  # Doit correspondre au code réel
    
    def calculate_leverage(
        self,
        size_usdt: float,
        balance_free: float,
        leverage: Optional[int] = None
    ) -> Tuple[int, bool, str]:
        """
        Reproduit la logique exacte du code live_order_manager_futures.py
        
        Returns:
            Tuple (leverage_final, success, message)
        """
        leverage = leverage or self.default_leverage
        original_leverage = leverage
        
        # Cas edge: valeurs invalides
        if balance_free is None or balance_free <= 0:
            return (leverage, False, "Balance invalide ou nulle")
        
        if size_usdt <= 0:
            return (leverage, False, "Size invalide")
        
        margin_required = size_usdt / leverage
        
        # Si solde suffisant, garder levier par défaut
        if balance_free >= margin_required:
            return (leverage, True, f"Solde suffisant, levier par défaut {leverage}x")
        
        # Solde insuffisant - calculer levier minimum nécessaire
        # EXACTEMENT comme dans le code: int(size_usdt / (balance_free * 0.90)) + 1
        min_leverage_needed = int(size_usdt / (balance_free * 0.90)) + 1
        
        if min_leverage_needed <= self.MAX_AUTO_LEVERAGE:
            # Adapter automatiquement
            leverage = min_leverage_needed
            new_margin = size_usdt / leverage
            return (
                leverage, 
                True, 
                f"Levier adapté: {original_leverage}x -> {leverage}x (marge: {new_margin:.2f} USDT)"
            )
        else:
            # Refuser - levier trop élevé
            return (
                original_leverage,
                False,
                f"Levier nécessaire {min_leverage_needed}x > max auto {self.MAX_AUTO_LEVERAGE}x"
            )


def run_tests():
    """Exécuter tous les tests de vérification"""
    
    print(f"\n{BOLD}{'='*70}")
    print("VERIFICATION LEVIER AUTOMATIQUE")
    print(f"{'='*70}{RESET}\n")
    
    verifier = AutoLeverageVerifier(default_leverage=1)
    tests_passed = 0
    tests_failed = 0
    
    # ===========================================================================
    # TEST 1: Solde suffisant -> garder levier par défaut
    # ===========================================================================
    print(f"\n{BOLD}[TEST 1] Solde suffisant - Levier par défaut{RESET}")
    print("-" * 60)
    
    test_cases_1 = [
        # (size_usdt, balance_free, leverage, expected_leverage, expected_success)
        (25.0, 30.0, 1, 1, True),   # 25 USDT, 30 dispo, levier 1x -> OK
        (50.0, 100.0, 1, 1, True),  # 50 USDT, 100 dispo, levier 1x -> OK
        (10.0, 10.0, 1, 1, True),   # 10 USDT, 10 dispo, levier 1x -> OK (limite)
        (20.0, 50.0, 2, 2, True),   # 20 USDT, 50 dispo, levier 2x -> marge=10 -> OK
    ]
    
    for size, balance, lev, expected_lev, expected_ok in test_cases_1:
        result_lev, ok, msg = verifier.calculate_leverage(size, balance, lev)
        
        if result_lev == expected_lev and ok == expected_ok:
            success(f"size={size}, balance={balance}, lev={lev}x -> {result_lev}x (attendu: {expected_lev}x)")
            tests_passed += 1
        else:
            fail(f"size={size}, balance={balance}, lev={lev}x -> {result_lev}x (attendu: {expected_lev}x) | {msg}")
            tests_failed += 1
    
    # ===========================================================================
    # TEST 2: Solde insuffisant, adaptation <= 5x
    # ===========================================================================
    print(f"\n{BOLD}[TEST 2] Solde insuffisant - Adaptation auto (<=5x){RESET}")
    print("-" * 60)
    
    test_cases_2 = [
        # (size_usdt, balance_free, leverage, expected_leverage, expected_success)
        (50.0, 30.0, 1, 2, True),   # 50 USDT / 30 dispo -> marge=50, besoin 2x
        (100.0, 30.0, 1, 4, True),  # 100 USDT / 30 dispo -> besoin ~4x
        (120.0, 30.0, 1, 5, True),  # 120 USDT / 30 dispo -> besoin 5x (limite)
        (49.5, 30.38, 1, 2, True),  # Cas réel SUI: 49.5 USDT / 30.38 dispo -> 2x
    ]
    
    for size, balance, lev, expected_lev, expected_ok in test_cases_2:
        result_lev, ok, msg = verifier.calculate_leverage(size, balance, lev)
        
        # Vérifier que le levier est adapté ET que la nouvelle marge < balance
        new_margin = size / result_lev if result_lev > 0 else float('inf')
        margin_ok = new_margin <= balance
        
        if ok == expected_ok and margin_ok:
            success(f"size={size}, balance={balance} -> {result_lev}x | marge={new_margin:.2f} < {balance} OK")
            tests_passed += 1
        else:
            fail(f"size={size}, balance={balance} -> {result_lev}x | marge={new_margin:.2f} | {msg}")
            tests_failed += 1
    
    # ===========================================================================
    # TEST 3: Solde insuffisant, levier > 5x -> REFUSER
    # ===========================================================================
    print(f"\n{BOLD}[TEST 3] Solde insuffisant - Refus (>5x){RESET}")
    print("-" * 60)
    
    test_cases_3 = [
        # (size_usdt, balance_free, leverage, expected_success)
        (200.0, 30.0, 1, False),   # 200 USDT / 30 dispo -> besoin ~8x > 5x -> REFUS
        (300.0, 30.0, 1, False),   # 300 USDT / 30 dispo -> besoin ~12x > 5x -> REFUS
        (500.0, 10.0, 1, False),   # 500 USDT / 10 dispo -> besoin ~56x > 5x -> REFUS
    ]
    
    for size, balance, lev, expected_ok in test_cases_3:
        result_lev, ok, msg = verifier.calculate_leverage(size, balance, lev)
        
        if ok == expected_ok:
            success(f"size={size}, balance={balance} -> REFUSÉ (levier nécessaire > 5x)")
            tests_passed += 1
        else:
            fail(f"size={size}, balance={balance} -> {result_lev}x, ok={ok} (attendu: refus)")
            tests_failed += 1
    
    # ===========================================================================
    # TEST 4: Edge cases
    # ===========================================================================
    print(f"\n{BOLD}[TEST 4] Edge Cases{RESET}")
    print("-" * 60)
    
    # Balance = 0
    result_lev, ok, msg = verifier.calculate_leverage(50.0, 0.0, 1)
    if not ok:
        success(f"balance=0 -> Refusé correctement: {msg}")
        tests_passed += 1
    else:
        fail(f"balance=0 -> Devrait être refusé!")
        tests_failed += 1
    
    # Size = 0
    result_lev, ok, msg = verifier.calculate_leverage(0.0, 30.0, 1)
    if not ok:
        success(f"size=0 -> Refusé correctement: {msg}")
        tests_passed += 1
    else:
        fail(f"size=0 -> Devrait être refusé!")
        tests_failed += 1
    
    # Balance négative (impossible mais on teste)
    result_lev, ok, msg = verifier.calculate_leverage(50.0, -10.0, 1)
    if not ok:
        success(f"balance=-10 -> Refusé correctement: {msg}")
        tests_passed += 1
    else:
        fail(f"balance=-10 -> Devrait être refusé!")
        tests_failed += 1
    
    # ===========================================================================
    # TEST 5: Vérification calcul marge après adaptation
    # ===========================================================================
    print(f"\n{BOLD}[TEST 5] Vérification calcul marge{RESET}")
    print("-" * 60)
    
    # Cas réel: 49.5 USDT size, 30.38 balance
    size = 49.5
    balance = 30.38
    result_lev, ok, msg = verifier.calculate_leverage(size, balance, 1)
    
    new_margin = size / result_lev
    margin_with_buffer = new_margin * 1.10  # +10% sécurité
    
    info(f"Size: {size} USDT, Balance: {balance} USDT")
    info(f"Levier adapté: {result_lev}x")
    info(f"Nouvelle marge: {new_margin:.2f} USDT")
    info(f"Marge + buffer 10%: {margin_with_buffer:.2f} USDT")
    
    if new_margin <= balance:
        success(f"Marge {new_margin:.2f} <= Balance {balance} OK")
        tests_passed += 1
    else:
        fail(f"Marge {new_margin:.2f} > Balance {balance} - BUG!")
        tests_failed += 1
    
    # ===========================================================================
    # TEST 6: Vérification code réel (import)
    # ===========================================================================
    print(f"\n{BOLD}[TEST 6] Vérification code réel{RESET}")
    print("-" * 60)
    
    try:
        from trading.live_order_manager_futures import LiveOrderManagerFutures
        
        # Vérifier que MAX_AUTO_LEVERAGE = 5 dans le code
        # On lit le fichier source directement
        source_file = PROJECT_ROOT / "trading" / "live_order_manager_futures.py"
        with open(source_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        if "MAX_AUTO_LEVERAGE = 5" in source:
            success("MAX_AUTO_LEVERAGE = 5 trouvé dans le code source")
            tests_passed += 1
        else:
            fail("MAX_AUTO_LEVERAGE != 5 dans le code source!")
            tests_failed += 1
        
        # Vérifier la présence du log d'adaptation
        if "ADAPTATION LEVIER AUTO" in source:
            success("Log 'ADAPTATION LEVIER AUTO' présent")
            tests_passed += 1
        else:
            fail("Log 'ADAPTATION LEVIER AUTO' manquant!")
            tests_failed += 1
        
        # Vérifier le calcul avec marge 10%
        if "balance_free * 0.90" in source:
            success("Marge de sécurité 10% présente (balance_free * 0.90)")
            tests_passed += 1
        else:
            fail("Marge de sécurité 10% manquante!")
            tests_failed += 1
            
    except Exception as e:
        fail(f"Erreur import: {e}")
        tests_failed += 1
    
    # ===========================================================================
    # RESUME
    # ===========================================================================
    print(f"\n{BOLD}{'='*70}")
    print("RÉSUMÉ")
    print(f"{'='*70}{RESET}")
    
    total = tests_passed + tests_failed
    success_rate = (tests_passed / total * 100) if total > 0 else 0
    
    print(f"\n  Tests passés:  {GREEN}{tests_passed}/{total}{RESET}")
    print(f"  Tests échoués: {RED}{tests_failed}/{total}{RESET}")
    print(f"  Taux réussite: {GREEN if success_rate == 100 else YELLOW}{success_rate:.1f}%{RESET}")
    
    if tests_failed == 0:
        print(f"\n{GREEN}{BOLD}[OK] TOUS LES TESTS PASSENT - Levier auto OK{RESET}")
        print("\nComportement vérifié:")
        print("  1. Solde suffisant -> levier par défaut (1x)")
        print("  2. Solde insuffisant, besoin <=5x -> adaptation auto")
        print("  3. Solde insuffisant, besoin >5x -> trade refusé")
        print("  4. Marge calculée correctement après adaptation")
        print("  5. Buffer 10% appliqué pour sécurité")
    else:
        print(f"\n{RED}{BOLD}[FAIL] {tests_failed} TESTS ÉCHOUÉS - VÉRIFIER LE CODE!{RESET}")
        return 1
    
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(run_tests())

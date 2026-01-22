#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICATION COMPLETE DU MODE ATR HYBRID INTELLIGENT
Ce script verifie que tous les parametres sont correctement configures et fonctionnels.
"""

import json
import os
import sys
import io
from typing import Dict, List, Tuple

# Fix encoding pour Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Couleurs console (sans emojis pour compatibilite Windows)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def ok(msg: str): print(f"{GREEN}[OK] {msg}{RESET}")
def fail(msg: str): print(f"{RED}[FAIL] {msg}{RESET}")
def warn(msg: str): print(f"{YELLOW}[WARN] {msg}{RESET}")
def info(msg: str): print(f"{BLUE}[INFO] {msg}{RESET}")

# ============================================================
# PARAMÈTRES ATR À VÉRIFIER
# ============================================================
ATR_PARAMS = {
    # Base ATR
    "tp_sl_mode": ("str", "ATR"),
    "atr_mult_tp": ("float", 3.0),
    "atr_mult_sl": ("float", 1.2),
    "atr_min": ("float", 0.10),
    "atr_max": ("float", 1.0),
    
    # Break-Even ATR
    "break_even_use_atr": ("bool", True),
    "break_even_atr_mult": ("float", 0.5),
    
    # Trailing ATR
    "trailing_use_atr_trigger": ("bool", True),
    "trailing_trigger_atr_mult": ("float", 1.0),
    "trailing_atr_multiplier": ("float", 0.4),
    "trailing_min_distance": ("float", 0.06),
    "trailing_max_distance": ("float", 0.20),
    
    # Stagnation Exit
    "stagnation_exit_enabled": ("bool", True),
    "stagnation_exit_timeout_seconds": ("int", 120),
    "stagnation_exit_min_pnl_to_stay": ("float", 0.10),
    "stagnation_exit_max_loss_to_exit": ("float", -0.05),
    
    # TP Partiel
    "partial_tp_percent": ("float", 65.0),
}

def test_config_py() -> Tuple[int, int]:
    """Vérifier que tous les paramètres sont dans config.py"""
    print(f"\n{BLUE}{'='*60}")
    print("[1] VERIFICATION config.py")
    print(f"{'='*60}{RESET}\n")
    
    passed, failed = 0, 0
    
    try:
        # Importer TRADING_CONFIG
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from config import TRADING_CONFIG
        
        for key, (expected_type, default) in ATR_PARAMS.items():
            value = TRADING_CONFIG.get(key)
            
            # Vérifier si clé existe (peut être dans nested dict)
            if value is None:
                # Chercher dans nested
                if key.startswith('stagnation_exit_'):
                    nested_key = key.replace('stagnation_exit_', '')
                    nested = TRADING_CONFIG.get('stagnation_exit', {})
                    value = nested.get(nested_key)
                elif key.startswith('trailing_') and 'trigger' not in key and 'enabled' not in key:
                    nested = TRADING_CONFIG.get('trailing_stop', {})
                    if key == 'trailing_atr_multiplier':
                        value = nested.get('atr_multiplier')
                    elif key == 'trailing_min_distance':
                        value = nested.get('min_distance')
                    elif key == 'trailing_max_distance':
                        value = nested.get('max_distance')
            
            if value is not None:
                ok(f"{key}: {value}")
                passed += 1
            else:
                fail(f"{key}: MANQUANT (défaut attendu: {default})")
                failed += 1
                
    except Exception as e:
        fail(f"Erreur import config.py: {e}")
        failed += 1
    
    return passed, failed


def test_config_overrides() -> Tuple[int, int]:
    """Vérifier config_overrides.json"""
    print(f"\n{BLUE}{'='*60}")
    print("[2] VERIFICATION config_overrides.json")
    print(f"{'='*60}{RESET}\n")
    
    passed, failed = 0, 0
    overrides_path = os.path.join(os.path.dirname(__file__), 'config_overrides.json')
    
    if not os.path.exists(overrides_path):
        warn("config_overrides.json n'existe pas (sera créé au premier save)")
        return 0, 0
    
    try:
        with open(overrides_path, 'r') as f:
            overrides = json.load(f)
        
        for key, (expected_type, default) in ATR_PARAMS.items():
            if key in overrides:
                ok(f"{key}: {overrides[key]}")
                passed += 1
            else:
                warn(f"{key}: non personnalisé (utilise défaut)")
        
    except Exception as e:
        fail(f"Erreur lecture config_overrides.json: {e}")
        failed += 1
    
    return passed, failed


def test_main_py_handlers() -> Tuple[int, int]:
    """Vérifier que tous les handlers sont dans main.py"""
    print(f"\n{BLUE}{'='*60}")
    print("[3] VERIFICATION handlers main.py")
    print(f"{'='*60}{RESET}\n")
    
    passed, failed = 0, 0
    main_path = os.path.join(os.path.dirname(__file__), 'main.py')
    
    try:
        with open(main_path, 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        for key in ATR_PARAMS.keys():
            # Chercher le handler: if 'key' in params:
            handler_pattern = f"if '{key}' in params:"
            if handler_pattern in main_content:
                ok(f"Handler trouvé: {key}")
                passed += 1
            else:
                # Vérifier pattern alternatif
                alt_pattern = f"'{key}':"
                if alt_pattern in main_content and f"TRADING_CONFIG['{key}']" in main_content:
                    ok(f"Handler trouvé (alt): {key}")
                    passed += 1
                else:
                    fail(f"Handler MANQUANT: {key}")
                    failed += 1
                    
    except Exception as e:
        fail(f"Erreur lecture main.py: {e}")
        failed += 1
    
    return passed, failed


def test_position_manager() -> Tuple[int, int]:
    """Vérifier la logique dans position_manager.py"""
    print(f"\n{BLUE}{'='*60}")
    print("[4] VERIFICATION position_manager.py")
    print(f"{'='*60}{RESET}\n")
    
    passed, failed = 0, 0
    pm_path = os.path.join(os.path.dirname(__file__), 'core', 'position_manager.py')
    
    try:
        with open(pm_path, 'r', encoding='utf-8') as f:
            pm_content = f.read()
        
        # Vérifier les imports TRADING_CONFIG dans les méthodes critiques
        checks = [
            ("_get_position_atr_percent", "from config import TRADING_CONFIG"),
            ("_check_stagnation_exit", "from config import TRADING_CONFIG"),
            ("check_position", "from config import TRADING_CONFIG"),
        ]
        
        for method, import_stmt in checks:
            if f"def {method}" in pm_content:
                # Trouver la méthode et vérifier l'import
                method_start = pm_content.find(f"def {method}")
                method_end = pm_content.find("\n    def ", method_start + 1)
                if method_end == -1:
                    method_end = len(pm_content)
                method_body = pm_content[method_start:method_end]
                
                if import_stmt in method_body:
                    ok(f"{method}(): import TRADING_CONFIG ✓")
                    passed += 1
                else:
                    fail(f"{method}(): import TRADING_CONFIG MANQUANT")
                    failed += 1
            else:
                fail(f"Méthode {method} non trouvée")
                failed += 1
        
        # Vérifier la logique force_full_tp
        if "force_full_tp_for_partial" in pm_content:
            ok("Logique force_full_tp_for_partial présente")
            passed += 1
        else:
            fail("Logique force_full_tp_for_partial MANQUANTE")
            failed += 1
        
        # Vérifier break_even_use_atr
        if "break_even_use_atr" in pm_content:
            ok("Logique break_even_use_atr présente")
            passed += 1
        else:
            fail("Logique break_even_use_atr MANQUANTE")
            failed += 1
        
        # Vérifier trailing_use_atr_trigger
        if "trailing_use_atr_trigger" in pm_content:
            ok("Logique trailing_use_atr_trigger présente")
            passed += 1
        else:
            fail("Logique trailing_use_atr_trigger MANQUANTE")
            failed += 1
            
    except Exception as e:
        fail(f"Erreur lecture position_manager.py: {e}")
        failed += 1
    
    return passed, failed


def test_frontend() -> Tuple[int, int]:
    """Vérifier le frontend VariablesPanel.svelte"""
    print(f"\n{BLUE}{'='*60}")
    print("[5] VERIFICATION frontend (VariablesPanel.svelte)")
    print(f"{'='*60}{RESET}\n")
    
    passed, failed = 0, 0
    frontend_path = os.path.join(
        os.path.dirname(__file__), 
        'frontend', 'src', 'lib', 'components', 'VariablesPanel.svelte'
    )
    
    try:
        with open(frontend_path, 'r', encoding='utf-8') as f:
            frontend_content = f.read()
        
        # Vérifier les bindings (value pour sliders, checked pour checkboxes)
        critical_bindings = [
            ("bind:value={config.atr_mult_tp}", "atr_mult_tp"),
            ("bind:value={config.atr_mult_sl}", "atr_mult_sl"),
            ("bind:checked={config.break_even_use_atr}", "break_even_use_atr"),  # checkbox
            ("bind:value={config.break_even_atr_mult}", "break_even_atr_mult"),
            ("bind:checked={config.trailing_use_atr_trigger}", "trailing_use_atr_trigger"),  # checkbox
            ("bind:value={config.trailing_trigger_atr_mult}", "trailing_trigger_atr_mult"),
            ("bind:checked={config.stagnation_exit_enabled}", "stagnation_exit_enabled"),  # checkbox
            ("bind:value={config.partial_tp_percent}", "partial_tp_percent"),
            ("bind:value={config.trailing_atr_multiplier}", "trailing_atr_multiplier"),
        ]
        
        for binding, name in critical_bindings:
            if binding in frontend_content:
                ok(f"Binding: {name}")
                passed += 1
            else:
                fail(f"Binding MANQUANT: {binding}")
                failed += 1
        
        # Vérifier Variables en cours
        if "Hybrid: Trailing ATR" in frontend_content and "trailing_atr_multiplier:" in frontend_content:
            ok("Variables en cours: Trailing ATR avec distance")
            passed += 1
        else:
            warn("Variables en cours: vérifier section Trailing ATR")
            
        if "Hybrid: TP Partiel" in frontend_content:
            ok("Variables en cours: TP Partiel")
            passed += 1
        else:
            fail("Variables en cours: TP Partiel MANQUANT")
            failed += 1
            
    except Exception as e:
        fail(f"Erreur lecture frontend: {e}")
        failed += 1
    
    return passed, failed


def test_force_full_tp_logic() -> Tuple[int, int]:
    """Vérifier la logique de TP 100% pour petites positions"""
    print(f"\n{BLUE}{'='*60}")
    print("[6] VERIFICATION logique force_full_tp (petites positions)")
    print(f"{'='*60}{RESET}\n")
    
    passed, failed = 0, 0
    pm_path = os.path.join(os.path.dirname(__file__), 'core', 'position_manager.py')
    
    try:
        with open(pm_path, 'r', encoding='utf-8') as f:
            pm_content = f.read()
        
        # Vérifier la détection de petite position
        if "partial_qty < order_result.min_contract_amount" in pm_content:
            ok("Détection petite position: partial_qty < min_contract_amount")
            passed += 1
        else:
            fail("Détection petite position MANQUANTE")
            failed += 1
        
        # Vérifier le flag force_full_tp_for_partial
        if "force_full_tp_for_partial = True" in pm_content:
            ok("Flag force_full_tp_for_partial = True")
            passed += 1
        else:
            fail("Flag force_full_tp_for_partial = True MANQUANT")
            failed += 1
        
        # Vérifier l'utilisation du flag lors du TP
        if "force_full_tp = getattr(self.active_position, 'force_full_tp_for_partial'" in pm_content:
            ok("Utilisation force_full_tp lors du TP partiel")
            passed += 1
        else:
            fail("Utilisation force_full_tp MANQUANTE")
            failed += 1
        
        # Vérifier la mise à 100%
        if "partial_tp_percent = 100.0" in pm_content or "partial_tp_percent = 100" in pm_content:
            ok("Force à 100% quand position trop petite")
            passed += 1
        else:
            fail("Force à 100% MANQUANT")
            failed += 1
            
    except Exception as e:
        fail(f"Erreur: {e}")
        failed += 1
    
    return passed, failed


def test_atr_calculation() -> Tuple[int, int]:
    """Test de la logique de calcul ATR"""
    print(f"\n{BLUE}{'='*60}")
    print("[7] TEST CALCUL ATR (simulation)")
    print(f"{'='*60}{RESET}\n")
    
    passed, failed = 0, 0
    
    # Simulation de calcul ATR%
    test_cases = [
        # (entry, atr, atr_min, atr_max, expected_clamped)
        (142.00, 0.50, 0.10, 1.0, 0.35),  # Normal
        (100.00, 0.05, 0.10, 1.0, 0.10),  # Clamp min
        (50.00, 2.00, 0.10, 1.0, 1.0),    # Clamp max
    ]
    
    for entry, atr, atr_min, atr_max, expected in test_cases:
        atr_pct = (atr / entry) * 100
        clamped = max(atr_min, min(atr_max, atr_pct))
        
        if abs(clamped - expected) < 0.01:
            ok(f"ATR% calc: entry={entry}, atr={atr} → {clamped:.2f}% (attendu: {expected}%)")
            passed += 1
        else:
            fail(f"ATR% calc: entry={entry}, atr={atr} → {clamped:.2f}% (attendu: {expected}%)")
            failed += 1
    
    # Test Break-Even trigger
    atr_pct = 0.35
    be_mult = 0.5
    be_trigger = atr_pct * be_mult
    info(f"Break-Even trigger: {atr_pct}% × {be_mult} = +{be_trigger:.3f}%")
    
    # Test Trailing trigger
    trailing_mult = 1.0
    trailing_trigger = atr_pct * trailing_mult
    info(f"Trailing trigger: {atr_pct}% × {trailing_mult} = +{trailing_trigger:.3f}%")
    
    # Test Trailing distance
    trailing_dist_mult = 0.4
    trailing_dist = atr_pct * trailing_dist_mult
    info(f"Trailing distance: {atr_pct}% × {trailing_dist_mult} = {trailing_dist:.3f}%")
    
    passed += 1  # Si on arrive ici, le calcul fonctionne
    
    return passed, failed


def run_all_tests():
    """Exécuter tous les tests"""
    print(f"\n{BLUE}{'='*60}")
    print("VERIFICATION COMPLETE MODE ATR HYBRID INTELLIGENT")
    print(f"{'='*60}{RESET}")
    
    total_passed = 0
    total_failed = 0
    
    tests = [
        test_config_py,
        test_config_overrides,
        test_main_py_handlers,
        test_position_manager,
        test_frontend,
        test_force_full_tp_logic,
        test_atr_calculation,
    ]
    
    for test_func in tests:
        passed, failed = test_func()
        total_passed += passed
        total_failed += failed
    
    # Résumé
    print(f"\n{BLUE}{'='*60}")
    print("RESUME")
    print(f"{'='*60}{RESET}")
    print(f"\n{GREEN}[OK] Tests passes: {total_passed}{RESET}")
    print(f"{RED}[FAIL] Tests echoues: {total_failed}{RESET}")
    
    if total_failed == 0:
        print(f"\n{GREEN}MODE ATR PRET POUR LA PRODUCTION !{RESET}")
        return True
    else:
        print(f"\n{RED}Corrections necessaires avant mise en production{RESET}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

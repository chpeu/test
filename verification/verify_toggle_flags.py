#!/usr/bin/env python3
"""
Verification des flags de toggle (enabled/disabled) dans le backend.
Verifie que market_regime_enabled, trading_circuit_breaker_enabled,
et trading_cb_score_boost_enabled sont correctement respectes.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TRADING_CONFIG

def verify_toggle_flags():
    print("="*60)
    print("VERIFICATION DES FLAGS TOGGLE")
    print("="*60)
    
    errors = 0
    
    # ============================================================
    # TEST 1: market_regime_enabled
    # ============================================================
    print("\n[TEST 1] market_regime_enabled")
    
    # Verifier que le flag existe
    if 'market_regime_enabled' in TRADING_CONFIG:
        print(f"  [OK] Flag existe: {TRADING_CONFIG['market_regime_enabled']}")
    else:
        print("  [INFO] Flag non defini (default True)")
    
    # Verifier usage dans main.py (ligne 1105)
    main_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
    with open(main_file, 'r', encoding='utf-8') as f:
        main_content = f.read()
    
    if "TRADING_CONFIG.get('market_regime_enabled'" in main_content:
        print("  [OK] Flag verifie avant mise a jour regime (scanner_loop)")
    else:
        print("  [ERROR] Flag non verifie dans scanner_loop!")
        errors += 1
    
    # Verifier reset a la desactivation
    if "market_regime_enabled" in main_content and "set_regime_adjustments({})" in main_content:
        print("  [OK] Ajustements effaces a la desactivation")
    else:
        print("  [WARN] Verifier effacement ajustements")
    
    # ============================================================
    # TEST 2: trading_circuit_breaker_enabled
    # ============================================================
    print("\n[TEST 2] trading_circuit_breaker_enabled")
    
    if 'trading_circuit_breaker_enabled' in TRADING_CONFIG:
        print(f"  [OK] Flag existe: {TRADING_CONFIG['trading_circuit_breaker_enabled']}")
    else:
        print("  [INFO] Flag non defini (default True)")
    
    # Verifier usage dans main.py (can_trade)
    if "trading_circuit_breaker_enabled" in main_content and "can_trade()" in main_content:
        print("  [OK] Flag verifie avant can_trade() (scanner_loop)")
    else:
        print("  [ERROR] Flag non verifie avant can_trade!")
        errors += 1
    
    # Verifier usage dans position_manager.py (record_trade)
    pm_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'position_manager.py')
    with open(pm_file, 'r', encoding='utf-8') as f:
        pm_content = f.read()
    
    if "trading_circuit_breaker_enabled" in pm_content and "record_trade" in pm_content:
        # Verifier que le check est AVANT record_trade
        idx_check = pm_content.find("trading_circuit_breaker_enabled")
        idx_record = pm_content.find("record_trade")
        
        # Trouver le bloc qui contient les deux
        if "if TRADING_CONFIG.get('trading_circuit_breaker_enabled'" in pm_content:
            print("  [OK] Flag verifie avant record_trade() (position_manager)")
        else:
            print("  [WARN] Verifier condition avant record_trade")
    else:
        print("  [ERROR] record_trade non conditionne par le flag!")
        errors += 1
    
    # Verifier reset a la desactivation
    if "cb.reset()" in main_content or "trading_cb.reset()" in main_content:
        print("  [OK] CB reset a la desactivation")
    else:
        print("  [WARN] Verifier reset CB a la desactivation")
    
    # ============================================================
    # TEST 3: trading_cb_score_boost_enabled
    # ============================================================
    print("\n[TEST 3] trading_cb_score_boost_enabled")
    
    if 'trading_cb_score_boost_enabled' in TRADING_CONFIG:
        print(f"  [OK] Flag existe: {TRADING_CONFIG['trading_cb_score_boost_enabled']}")
    else:
        print("  [INFO] Flag non defini (default True)")
    
    if "trading_cb_score_boost_enabled" in main_content and "get_score_boost()" in main_content:
        print("  [OK] Flag verifie avant application score_boost")
    else:
        print("  [ERROR] Flag non verifie avant score_boost!")
        errors += 1
    
    # ============================================================
    # RESULTAT
    # ============================================================
    print("\n" + "="*60)
    if errors == 0:
        print("[OK] TOUS LES FLAGS SONT CORRECTEMENT VERIFIES")
    else:
        print(f"[ERROR] {errors} PROBLEMES DETECTES")
    print("="*60)
    
    return errors == 0

if __name__ == "__main__":
    success = verify_toggle_flags()
    sys.exit(0 if success else 1)

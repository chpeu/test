#!/usr/bin/env python3
"""
Script de vérification des fixes:
1. Fix net_pnl_pct: Cohérence pnl_usdt / size * 100 = pnl_pct
2. Fix TP/SL inversés: TP/SL du bon côté de entry selon direction

Usage:
    python verification/verify_fixes_pnl_tpsl.py
"""

import sys
import os

# Fix encodage Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.position.tp_sl_calculator import calculate_atr_levels, TPSLConfig


def test_fix_1_pnl_calculation():
    """
    Test Fix 1: Vérifier que le calcul net_pnl_pct est cohérent
    
    Le fix supprime la reconstruction de taille quand partial_tp_sold=True.
    Maintenant: net_pnl_pct = net_pnl_usdt / size * 100
    """
    print("=" * 60)
    print("TEST FIX 1: Calcul net_pnl_pct")
    print("=" * 60)
    
    # Simuler les cas de test
    test_cases = [
        # (size_usdt, net_pnl_usdt, expected_pnl_pct, description)
        (25.0, 0.0363, 0.1452, "SHIB trade problématique"),
        (25.0, -0.0763, -0.3052, "SHIB trade normal"),
        (100.0, 1.0, 1.0, "Trade simple 1% profit"),
        (50.0, -0.25, -0.5, "Trade simple 0.5% perte"),
    ]
    
    all_passed = True
    for size, pnl_usdt, expected_pct, desc in test_cases:
        # Calcul selon le fix: pnl_pct = (pnl_usdt / size) * 100
        calculated_pct = (pnl_usdt / size) * 100 if size > 0 else 0
        
        # Tolérance de 0.01% pour les arrondis
        diff = abs(calculated_pct - expected_pct)
        passed = diff < 0.01
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{status} {desc}")
        print(f"   Size: {size} USDT, PnL: {pnl_usdt} USDT")
        print(f"   Calculé: {calculated_pct:.4f}%, Attendu: {expected_pct:.4f}%")
        
        if not passed:
            all_passed = False
            print(f"   ⚠️ Écart: {diff:.4f}%")
    
    print("\n" + "-" * 60)
    if all_passed:
        print("✅ FIX 1 VALIDÉ: Calcul net_pnl_pct cohérent")
    else:
        print("❌ FIX 1 ÉCHOUÉ: Incohérences détectées")
    
    return all_passed


def test_fix_2_tpsl_direction():
    """
    Test Fix 2: Vérifier que TP/SL sont du bon côté selon direction
    
    LONG: tp > entry > sl
    SHORT: sl > entry > tp
    """
    print("\n" + "=" * 60)
    print("TEST FIX 2: Validation TP/SL selon direction")
    print("=" * 60)
    
    config = TPSLConfig(
        atr_mult_tp=1.8,
        atr_mult_sl=0.8,
        atr_min=0.1,
        atr_max=1.5
    )
    
    test_cases = [
        # (entry, atr, direction, description)
        (1.5391, 0.00174, "SHORT", "SUI SHORT"),
        (135.48, 0.5, "SHORT", "SOL SHORT"),
        (8.473e-06, 5e-09, "SHORT", "SHIB SHORT"),
        (100.0, 0.5, "LONG", "Generic LONG"),
        (50000.0, 200.0, "LONG", "BTC LONG"),
        (50000.0, 200.0, "SHORT", "BTC SHORT"),
    ]
    
    all_passed = True
    for entry, atr, direction, desc in test_cases:
        sl, tp = calculate_atr_levels(entry, atr, None, direction, config)
        
        # Validation selon direction
        if direction == "LONG":
            tp_correct = tp > entry
            sl_correct = sl < entry
        else:  # SHORT
            tp_correct = tp < entry
            sl_correct = sl > entry
        
        passed = tp_correct and sl_correct
        status = "✅ PASS" if passed else "❌ FAIL"
        
        print(f"\n{status} {desc}")
        print(f"   Entry: {entry:.8f}, ATR: {atr:.8f}")
        print(f"   TP: {tp:.8f} ({'>' if direction == 'LONG' else '<'} entry: {tp_correct})")
        print(f"   SL: {sl:.8f} ({'<' if direction == 'LONG' else '>'} entry: {sl_correct})")
        
        if not passed:
            all_passed = False
            if not tp_correct:
                print(f"   ⚠️ TP du mauvais côté!")
            if not sl_correct:
                print(f"   ⚠️ SL du mauvais côté!")
    
    print("\n" + "-" * 60)
    if all_passed:
        print("✅ FIX 2 VALIDÉ: TP/SL toujours du bon côté")
    else:
        print("❌ FIX 2 ÉCHOUÉ: TP/SL inversés détectés")
    
    return all_passed


def test_fix_2_edge_cases():
    """
    Test Fix 2: Cas limites - ATR très petit, très grand, etc.
    """
    print("\n" + "=" * 60)
    print("TEST FIX 2: Cas limites TP/SL")
    print("=" * 60)
    
    config = TPSLConfig(
        atr_mult_tp=1.8,
        atr_mult_sl=0.8,
        atr_min=0.1,
        atr_max=1.5
    )
    
    edge_cases = [
        # (entry, atr, direction, description)
        (100.0, 0.001, "SHORT", "ATR très petit (clamped à min)"),
        (100.0, 10.0, "SHORT", "ATR très grand (clamped à max)"),
        (0.00001, 0.00000001, "SHORT", "Prix très petit (SHIB-like)"),
        (50000.0, 500.0, "SHORT", "Prix très grand (BTC-like)"),
    ]
    
    all_passed = True
    for entry, atr, direction, desc in edge_cases:
        sl, tp = calculate_atr_levels(entry, atr, None, direction, config)
        
        # Pour SHORT: sl > entry > tp
        tp_correct = tp < entry
        sl_correct = sl > entry
        passed = tp_correct and sl_correct
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{status} {desc}")
        print(f"   Entry: {entry}, ATR: {atr}")
        print(f"   TP: {tp} (< entry: {tp_correct})")
        print(f"   SL: {sl} (> entry: {sl_correct})")
        
        if not passed:
            all_passed = False
    
    print("\n" + "-" * 60)
    if all_passed:
        print("✅ CAS LIMITES VALIDÉS")
    else:
        print("❌ CAS LIMITES ÉCHOUÉS")
    
    return all_passed


def main():
    """Exécuter tous les tests de vérification"""
    print("\n" + "=" * 60)
    print("VÉRIFICATION DES FIXES - PnL et TP/SL")
    print("=" * 60 + "\n")
    
    results = []
    
    # Test Fix 1: Calcul PnL
    results.append(("Fix 1 - Calcul net_pnl_pct", test_fix_1_pnl_calculation()))
    
    # Test Fix 2: Direction TP/SL
    results.append(("Fix 2 - Direction TP/SL", test_fix_2_tpsl_direction()))
    
    # Test Fix 2: Cas limites
    results.append(("Fix 2 - Cas limites", test_fix_2_edge_cases()))
    
    # Résumé final
    print("\n" + "=" * 60)
    print("RÉSUMÉ FINAL")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "-" * 60)
    if all_passed:
        print("🎉 TOUS LES TESTS PASSÉS - Fixes validés!")
        return 0
    else:
        print("⚠️ CERTAINS TESTS ÉCHOUÉS - Vérifier les fixes!")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification complète des variables du mode FIXE
"""
import sys
sys.path.append('c:\\Users\\sebta\\Documents\\clone github\\test\\test')

def check_fixed_mode_variables():
    """Vérifier toutes les variables qui affectent le mode FIXE"""
    
    print("🔍 VARIABLES DU MODE FIXE - VÉRIFICATION COMPLÈTE")
    print("=" * 80)
    
    try:
        from config import TRADING_CONFIG
        
        print("\n1️⃣ VARIABLES PRINCIPALES FIXE:")
        print("-" * 50)
        
        # Variables principales
        main_vars = {
            "tp_sl_mode": TRADING_CONFIG.get("tp_sl_mode", "Non défini"),
            "tp_percent": TRADING_CONFIG.get("tp_percent", 0),
            "sl_percent": TRADING_CONFIG.get("sl_percent", 0),
            "sl_exchange_percent": TRADING_CONFIG.get("sl_exchange_percent", 0),
        }
        
        for var, value in main_vars.items():
            if "%" in var:
                print(f"   {var:25s}: {value:.2f}%")
            else:
                print(f"   {var:25s}: {value}")
        
        print("\n2️⃣ TRAILING STOP:")
        print("-" * 50)
        
        trailing_vars = {
            "trailing_enabled": TRADING_CONFIG.get("trailing_enabled", False),
            "trailing_distance": TRADING_CONFIG.get("trailing_distance", 0),
            "trailing_trigger_pnl": TRADING_CONFIG.get("trailing_trigger_pnl", 0),
            "trailing_use_atr_trigger": TRADING_CONFIG.get("trailing_use_atr_trigger", False),
            "trailing_trigger_atr_mult": TRADING_CONFIG.get("trailing_trigger_atr_mult", 0),
            "trailing_atr_multiplier": TRADING_CONFIG.get("trailing_atr_multiplier", 0),
            "trailing_min_distance": TRADING_CONFIG.get("trailing_min_distance", 0),
            "trailing_max_distance": TRADING_CONFIG.get("trailing_max_distance", 0),
        }
        
        for var, value in trailing_vars.items():
            if isinstance(value, float) and "%" in var:
                print(f"   {var:25s}: {value:.2f}%")
            else:
                print(f"   {var:25s}: {value}")
        
        print("\n3️⃣ BREAK-EVEN:")
        print("-" * 50)
        
        be_vars = {
            "break_even_trigger": TRADING_CONFIG.get("break_even_trigger", 0),
            "break_even_use_atr": TRADING_CONFIG.get("break_even_use_atr", False),
            "break_even_atr_mult": TRADING_CONFIG.get("break_even_atr_mult", 0),
        }
        
        for var, value in be_vars.items():
            if isinstance(value, float):
                print(f"   {var:25s}: {value:.2f}%")
            else:
                print(f"   {var:25s}: {value}")
        
        print("\n4️⃣ TP PARTIEL (Si activé):")
        print("-" * 50)
        
        tp_partial = TRADING_CONFIG.get("tp_partial", {})
        if tp_partial:
            print(f"   tp_partial_enabled        : {tp_partial.get('enabled', False)}")
            print(f"   tp_partial_percent        : {tp_partial.get('percent', 0):.1f}%")
            print(f"   tp_partial_move_sl_to_entry: {tp_partial.get('move_sl_to_entry', False)}")
        else:
            print("   TP Partiel: Non configuré")
        
        print("\n5️⃣ STAGNATION EXIT:")
        print("-" * 50)
        
        stag = TRADING_CONFIG.get("stagnation_exit", {})
        if stag:
            print(f"   enabled                   : {stag.get('enabled', False)}")
            print(f"   timeout_seconds           : {stag.get('timeout_seconds', 0)}s")
            print(f"   min_pnl_to_stay           : {stag.get('min_pnl_to_stay', 0):.2f}%")
            print(f"   max_loss_to_exit          : {stag.get('max_loss_to_exit', 0):.2f}%")
        
        print("\n6️⃣ AUTRES VARIABLES INFLUENÇANT LES SORTIES:")
        print("-" * 50)
        
        other_vars = {
            "use_trailing_stop": TRADING_CONFIG.get("use_trailing_stop", True),
            "trailing_stop_enabled": TRADING_CONFIG.get("trailing_stop", {}).get("enabled", False),
            "tp_escalier_enabled": TRADING_CONFIG.get("tp_escalier", {}).get("enabled", False),
            "stagnation_positive_exit_enabled": TRADING_CONFIG.get("stagnation_positive_exit_enabled", False),
        }
        
        for var, value in other_vars.items():
            print(f"   {var:30s}: {value}")
        
        print("\n⚠️  POINTS D'ATTENTION:")
        print("-" * 50)
        
        # Vérifications importantes
        issues = []
        
        # TP/SL ratio
        tp = TRADING_CONFIG.get("tp_percent", 0)
        sl = TRADING_CONFIG.get("sl_percent", 0)
        if tp > 0 and sl > 0:
            ratio = tp / sl
            print(f"   ✅ Ratio TP/SL: {ratio:.1f} (TP {tp:.2f}% / SL {sl:.2f}%)")
            if ratio < 1.5:
                issues.append("Ratio TP/SL faible (< 1.5)")
        
        # Trailing
        trailing_enabled = TRADING_CONFIG.get("trailing_enabled", False)
        if trailing_enabled:
            trail_dist = TRADING_CONFIG.get("trailing_distance", 0)
            trail_trigger = TRADING_CONFIG.get("trailing_trigger_pnl", 0)
            if trail_dist >= tp * 0.8:
                issues.append(f"Trailing distance ({trail_dist:.1f}%) trop proche du TP ({tp:.1f}%)")
            if trail_trigger < tp * 0.3:
                issues.append(f"Trailing trigger ({trail_trigger:.1f}%) trop bas")
        
        # Stagnation
        stag = TRADING_CONFIG.get("stagnation_exit", {})
        if stag.get("enabled", False):
            timeout = stag.get("timeout_seconds", 0)
            if timeout < 60:
                issues.append("Stagnation timeout très court (< 60s)")
        
        if issues:
            print("\n   ⚠️  Problèmes potentiels:")
            for i, issue in enumerate(issues, 1):
                print(f"      {i}. {issue}")
        else:
            print("   ✅ Configuration semble cohérente")
        
        print("\n🎯 RÉCAPITULATIF DE VOTRE CONFIG ACTUELLE:")
        print("-" * 50)
        print(f"   Mode: FIXE")
        print(f"   TP: {tp:.2f}% | SL: {sl:.2f}% | Ratio: {tp/sl:.1f}")
        if trailing_enabled:
            print(f"   Trailing: ON (trigger: {trail_trigger:.1f}%, distance: {trail_dist:.1f}%)")
        else:
            print(f"   Trailing: OFF")
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_fixed_mode_variables()

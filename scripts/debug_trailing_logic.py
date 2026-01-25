#!/usr/bin/env python3
"""
Debug Trailing Stop Logic - Analyse détaillée du problème de fermeture
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

def main():
    print("🔍 DEBUG TRAILING STOP LOGIC")
    print("=" * 60)
    
    try:
        from config import TRADING_CONFIG
        from utils.effective_config import get_effective_value
        
        # 1. Analyser la logique de trailing en mode FIXE
        print("\n📊 LOGIQUE TRAILING MODE FIXE")
        print("-" * 40)
        
        tp_sl_mode = get_effective_value('tp_sl_mode') or TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        trailing_enabled = get_effective_value('trailing_enabled')
        if trailing_enabled is None:
            trailing_enabled = TRADING_CONFIG.get('trailing_enabled', True)
            
        trailing_trigger_pnl = get_effective_value('trailing_trigger_pnl') or TRADING_CONFIG.get('trailing_trigger_pnl', 0.20)
        trailing_min_distance = get_effective_value('trailing_min_distance') or TRADING_CONFIG.get('trailing_min_distance', 0.10)
        trailing_max_distance = get_effective_value('trailing_max_distance') or TRADING_CONFIG.get('trailing_max_distance', 0.30)
        trailing_pnl_cap = get_effective_value('trailing_pnl_cap') or TRADING_CONFIG.get('trailing_pnl_cap', 0.60)
        
        print(f"Mode TP/SL: {tp_sl_mode}")
        print(f"Trailing enabled: {trailing_enabled}")
        print(f"Trailing trigger: {trailing_trigger_pnl}%")
        print(f"Min distance: {trailing_min_distance}%")
        print(f"Max distance: {trailing_max_distance}%")
        print(f"PnL cap: {trailing_pnl_cap}%")
        
        # 2. Simuler la logique de check_position
        print("\n🔧 SIMULATION LOGIQUE CHECK_POSITION")
        print("-" * 40)
        
        # Conditions pour activation du trailing
        print("Conditions pour activation du trailing (ligne 2976-2983):")
        print(f"1. Mode FIXE + trailing_enabled = False → SKIP: {tp_sl_mode == 'FIXE' and not trailing_enabled}")
        print(f"2. partial_tp_sold OR pnl >= trigger → CHECK")
        
        if tp_sl_mode == 'FIXE' and not trailing_enabled:
            print("❌ PROBLÈME: Trailing sera ignoré en mode FIXE!")
        else:
            print("✅ Trailing sera vérifié si conditions remplies")
        
        # 3. Analyser la logique _update_trailing_stop_fixe
        print("\n🎢 LOGIQUE UPDATE_TRAILING_STOP_FIXE")
        print("-" * 40)
        
        print("Logique mode FIXE (lignes 3028-3063):")
        print("1. Calcul distance adaptative linéaire:")
        print(f"   if pnl <= {trailing_trigger_pnl}%: distance = {trailing_min_distance}%")
        print(f"   else: distance = {trailing_min_distance}% + progression vers {trailing_max_distance}%")
        print("2. Mise à jour SL:")
        print("   LONG: new_sl = current_price * (1 - distance/100)")
        print("   SHORT: new_sl = current_price * (1 + distance/100)")
        print("3. Condition update: new_sl > current_sl (LONG) ou new_sl < current_sl (SHORT)")
        
        # 4. Analyser la logique _check_levels  
        print("\n🎯 LOGIQUE CHECK_LEVELS")
        print("-" * 40)
        
        print("Vérification fermeture (lignes 3385-3396):")
        print("LONG:")
        print("  if current_price <= sl: return 'TS' if pnl >= 0 else 'SL'")
        print("  if current_price >= tp: return 'TP'")
        print("SHORT:")
        print("  if current_price >= sl: return 'TS' if pnl >= 0 else 'SL'")
        print("  if current_price <= tp: return 'TP'")
        
        # 5. Problèmes potentiels identifiés
        print("\n❌ PROBLÈMES POTENTIELS IDENTIFIÉS")
        print("-" * 40)
        
        issues = []
        
        # Issue 1: Trailing pas activé si pas de TP partiel vendu
        print("1. ACTIVATION DU TRAILING:")
        print("   trailing_should_activate = partial_tp_sold OR pnl >= trailing_trigger")
        print("   → Si pas de TP partiel ET pnl < trigger, trailing ne s'active JAMAIS")
        issues.append("Trailing ne s'active que si TP partiel vendu OU pnl >= trigger")
        
        # Issue 2: Mise à jour SL seulement si favorable
        print("\n2. MISE À JOUR SL:")
        print("   LONG: new_sl doit être > current_sl pour être accepté")
        print("   SHORT: new_sl doit être < current_sl pour être accepté")
        print("   → Si prix descend (LONG), trailing SL ne descend JAMAIS")
        issues.append("Trailing SL ne peut que monter (LONG) ou descendre (SHORT)")
        
        # Issue 3: _check_levels utilise SL statique
        print("\n3. VÉRIFICATION FERMETURE:")
        print("   Utilise self.active_position.sl (valeur actuelle)")
        print("   → Dépend de la mise à jour correcte du SL par trailing")
        issues.append("Fermeture dépend de la mise à jour correcte du SL")
        
        # 6. Test simulation avec position fictive
        print("\n🧪 SIMULATION AVEC POSITION FICTIVE")
        print("-" * 40)
        
        # Simuler position LONG
        entry_price = 100.0
        current_sl = 99.0  # SL initial -1%
        current_tp = 101.0  # TP initial +1%
        direction = "LONG"
        
        print(f"Position LONG fictive:")
        print(f"  Entry: {entry_price}")
        print(f"  SL initial: {current_sl}")
        print(f"  TP initial: {current_tp}")
        
        # Test scénarios
        test_scenarios = [
            {"price": 100.3, "desc": "Prix +0.3% (trigger trailing)"},
            {"price": 100.5, "desc": "Prix +0.5% (trailing actif)"},
            {"price": 100.2, "desc": "Prix redescend à +0.2%"},
            {"price": 99.8, "desc": "Prix à -0.2% (doit toucher SL)"},
        ]
        
        partial_tp_sold = False
        trailing_activated = False
        
        for scenario in test_scenarios:
            price = scenario["price"]
            desc = scenario["desc"]
            pnl = ((price - entry_price) / entry_price) * 100
            
            print(f"\n📊 Scénario: {desc}")
            print(f"   Prix: {price}, PnL: {pnl:+.2f}%")
            
            # Check si trailing devrait s'activer
            should_activate = partial_tp_sold or pnl >= trailing_trigger_pnl
            if should_activate and not trailing_activated:
                trailing_activated = True
                print(f"   ✅ Trailing activé (trigger: {trailing_trigger_pnl}%)")
            
            # Calculer nouveau SL si trailing actif
            if trailing_activated:
                # Calcul distance adaptative
                if pnl <= trailing_trigger_pnl:
                    distance = trailing_min_distance
                else:
                    denominator = trailing_pnl_cap - trailing_trigger_pnl
                    if denominator > 0:
                        x = min(1.0, max(0.0, (pnl - trailing_trigger_pnl) / denominator))
                        distance = trailing_min_distance + (trailing_max_distance - trailing_min_distance) * x
                    else:
                        distance = trailing_max_distance
                
                new_sl = price * (1 - distance / 100)
                
                print(f"   🎢 Trailing distance: {distance:.3f}%")
                print(f"   📈 Nouveau SL calculé: {new_sl:.4f}")
                
                # Check si SL doit être mis à jour
                if new_sl > current_sl:
                    current_sl = new_sl
                    print(f"   ✅ SL mis à jour: {current_sl:.4f}")
                else:
                    print(f"   ⏹️ SL non mis à jour (pas favorable)")
                
            # Check fermeture
            if price <= current_sl:
                close_reason = 'TS' if pnl >= 0 else 'SL'
                print(f"   🔚 Position devrait fermer: {close_reason}")
            elif price >= current_tp:
                print(f"   🔚 Position devrait fermer: TP")
            else:
                print(f"   ➡️ Position continue")
        
        # 7. Solutions proposées
        print("\n" + "=" * 60)
        print("💡 SOLUTIONS PROPOSÉES")
        print("=" * 60)
        
        print("1. **VÉRIFIER LOGS DE TRAILING:**")
        print("   Chercher dans logs: '🎢 Trailing FIXE', '🔄 Trailing SL'")
        print("   Vérifier si trailing s'active et met à jour SL")
        
        print("\n2. **AJOUTER LOGS DEBUG:**")
        print("   Ajouter logs dans check_position pour voir:")
        print("   - Si trailing_should_activate = True")
        print("   - Valeur de current_sl avant/après update")
        print("   - Si _check_levels détecte la fermeture")
        
        print("\n3. **VÉRIFIER PRIX EN TEMPS RÉEL:**")
        print("   Le prix doit effectivement toucher le SL mis à jour")
        print("   Si SL = 99.5 et prix = 99.6, position continue")
        
        print("\n4. **PROBLÈME POTENTIEL - TIMING:**")
        print("   Si prix descend trop vite, trailing peut ne pas suivre")
        print("   Solution: Réduire trailing_min_distance ou check_interval")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

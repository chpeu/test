#!/usr/bin/env python3
"""
Debug TP Partiel et Trailing Stop - Vérification configuration et logique
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

def main():
    print("🔍 DEBUG TP PARTIEL & TRAILING STOP")
    print("=" * 60)
    
    try:
        # 1. Vérifier configuration effective
        print("\n📊 CONFIGURATION ACTUELLE")
        print("-" * 40)
        
        from config import TRADING_CONFIG
        from utils.effective_config import get_effective_value, get_effective_config
        
        # Variables critiques pour TP partiel
        tp_sl_mode = get_effective_value('tp_sl_mode') or TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        use_partial_tp = get_effective_value('use_partial_tp')
        partial_tp_percent = get_effective_value('partial_tp_percent') or TRADING_CONFIG.get('partial_tp_percent', 50)
        break_even_trigger = get_effective_value('break_even_trigger') or TRADING_CONFIG.get('break_even_trigger', 0.3)
        
        print(f"🎯 Mode TP/SL: {tp_sl_mode}")
        print(f"🔄 TP Partiel activé: {use_partial_tp}")
        print(f"📊 TP Partiel %: {partial_tp_percent}%")
        print(f"⚡ Break-even trigger: {break_even_trigger}%")
        
        # Variables critiques pour trailing
        trailing_enabled = get_effective_value('trailing_enabled')
        if trailing_enabled is None:
            trailing_enabled = TRADING_CONFIG.get('trailing_enabled', True)
        
        trailing_trigger_pnl = get_effective_value('trailing_trigger_pnl') or TRADING_CONFIG.get('trailing_trigger_pnl', 0.20)
        trailing_min_distance = get_effective_value('trailing_min_distance') or TRADING_CONFIG.get('trailing_min_distance', 0.10)
        trailing_max_distance = get_effective_value('trailing_max_distance') or TRADING_CONFIG.get('trailing_max_distance', 0.30)
        trailing_pnl_cap = get_effective_value('trailing_pnl_cap') or TRADING_CONFIG.get('trailing_pnl_cap', 0.60)
        
        print(f"\n🎢 Trailing activé: {trailing_enabled}")
        print(f"📈 Trailing trigger: {trailing_trigger_pnl}%")
        print(f"📏 Trailing min distance: {trailing_min_distance}%")
        print(f"📏 Trailing max distance: {trailing_max_distance}%")
        print(f"🎯 Trailing PnL cap: {trailing_pnl_cap}%")
        
        # 2. Analyser les problèmes potentiels
        print("\n❌ PROBLÈMES IDENTIFIÉS")
        print("-" * 40)
        
        issues = []
        
        # Problème #1: use_partial_tp non défini
        if use_partial_tp is None:
            issues.append("use_partial_tp non défini dans la config - TP partiel désactivé par défaut")
        
        # Problème #2: Mode ATR au lieu de FIXE
        if tp_sl_mode != 'FIXE':
            issues.append(f"Mode {tp_sl_mode} au lieu de FIXE - comportement différent pour trailing")
        
        # Problème #3: trailing_enabled pourrait être False
        if not trailing_enabled:
            issues.append("trailing_enabled = False - trailing stop désactivé")
        
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue}")
        
        if not issues:
            print("✅ Aucun problème de configuration évident détecté")
        
        # 3. Vérifier logique du code
        print("\n🔧 VÉRIFICATION LOGIQUE CODE")
        print("-" * 40)
        
        print("📋 Logique TP Partiel (position_manager.py ligne 2863):")
        print(f"   if not tp_escalier_enabled AND get_effective_value('use_partial_tp'):")
        print(f"   → use_partial_tp = {use_partial_tp}")
        if use_partial_tp:
            print("   ✅ TP Partiel devrait être vérifié")
        else:
            print("   ❌ TP Partiel ne sera PAS vérifié")
        
        print(f"\n📋 Logique Trailing (position_manager.py ligne 2976-2983):")
        print(f"   if tp_sl_mode == 'FIXE' and not trailing_enabled:")
        print(f"   → Mode: {tp_sl_mode}, Enabled: {trailing_enabled}")
        
        if tp_sl_mode == 'FIXE' and not trailing_enabled:
            print("   ❌ Trailing sera SKIP (désactivé en mode FIXE)")
        else:
            print("   ✅ Trailing devrait être vérifié")
        
        # 4. Position manager check
        print("\n👨‍💼 VÉRIFICATION POSITION MANAGER")
        print("-" * 40)
        
        try:
            from core.state_manager import get_state_manager
            state = get_state_manager()
            position_manager = state.get_position_manager()
            
            if position_manager:
                print("✅ PositionManager disponible")
                active_pos = position_manager.active_position
                if active_pos:
                    print(f"📊 Position active: {active_pos.symbol} {active_pos.direction}")
                    print(f"   Entry: {active_pos.entry}")
                    print(f"   SL: {active_pos.sl}")
                    print(f"   TP: {active_pos.tp}")
                    print(f"   Partial TP sold: {getattr(active_pos, 'partial_tp_sold', False)}")
                    print(f"   Trailing activated: {getattr(active_pos, 'trailing_activated', False)}")
                else:
                    print("ℹ️ Aucune position active actuellement")
            else:
                print("❌ PositionManager non disponible")
        except Exception as e:
            print(f"❌ Erreur accès PositionManager: {e}")
        
        # 5. Solutions proposées
        print("\n" + "=" * 60)
        print("💡 SOLUTIONS PROPOSÉES")
        print("=" * 60)
        
        solutions = []
        
        if use_partial_tp is None:
            solutions.append({
                'probleme': 'use_partial_tp manquant',
                'solution': 'Ajouter "use_partial_tp": True dans config.py',
                'code': '"use_partial_tp": True,  # Activer TP partiel'
            })
        
        if tp_sl_mode != 'FIXE':
            solutions.append({
                'probleme': f'Mode {tp_sl_mode} au lieu de FIXE',
                'solution': 'Changer tp_sl_mode à FIXE dans config.py',
                'code': '"tp_sl_mode": "FIXE",  # Mode FIXE pour TP/SL'
            })
        
        if not trailing_enabled and tp_sl_mode == 'FIXE':
            solutions.append({
                'probleme': 'trailing_enabled = False bloque trailing en mode FIXE',
                'solution': 'Vérifier que trailing_enabled = True',
                'code': '"trailing_enabled": True,  # Autoriser trailing en mode FIXE'
            })
        
        if solutions:
            for i, sol in enumerate(solutions, 1):
                print(f"\n{i}. **{sol['probleme']}**")
                print(f"   Solution: {sol['solution']}")
                print(f"   Code: {sol['code']}")
        else:
            print("✅ Configuration semble correcte")
            print("Le problème pourrait être dans la logique de vérification des prix")
            print("ou dans les conditions de déclenchement")
        
        # 6. Test des conditions de déclenchement
        if position_manager and position_manager.active_position:
            print(f"\n🧪 TEST CONDITIONS DÉCLENCHEMENT")
            print("-" * 40)
            
            active_pos = position_manager.active_position
            # Simuler un prix pour test
            current_price = active_pos.entry * 1.005 if active_pos.direction == 'LONG' else active_pos.entry * 0.995
            
            print(f"Prix simulé: {current_price}")
            print(f"PnL simulé: +0.5%")
            
            # Test TP partiel
            try:
                from core.position.partial_tp_manager import PartialTPManager
                if use_partial_tp and not getattr(active_pos, 'partial_tp_sold', False):
                    should_trigger = PartialTPManager.check_trigger(
                        position=active_pos.to_dict(),
                        current_price=current_price,
                        trigger_pct=break_even_trigger
                    )
                    print(f"TP Partiel devrait se déclencher: {should_trigger}")
                else:
                    print("TP Partiel: conditions non remplies")
            except Exception as e:
                print(f"Erreur test TP partiel: {e}")
            
            # Test trailing
            if trailing_enabled:
                print(f"Trailing: conditions remplies pour vérification")
            else:
                print("Trailing: désactivé")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

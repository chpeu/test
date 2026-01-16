"""
Script pour vérifier la position active via l'état du bot
"""
import json
import os
import sys

def main():
    # Lire le fichier state.json qui contient l'état actuel du bot
    state_file = 'state.json'
    
    if not os.path.exists(state_file):
        print("❌ Fichier state.json introuvable")
        print("ℹ️ Le bot est peut-être arrêté ou n'a pas encore créé de state")
        return
    
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        print("=" * 70)
        print("🔍 VÉRIFICATION POSITION ACTIVE (depuis state.json)")
        print("=" * 70)
        
        # Vérifier si une position est active
        active_position = state.get('active_position')
        
        if not active_position:
            print("\n❌ Aucune position active dans le state")
            print("ℹ️ Le bot n'a peut-être pas encore ouvert de position ASTER")
            return
        
        # Extraire les informations
        symbol = active_position.get('symbol', 'N/A')
        direction = active_position.get('direction', 'N/A')
        entry = active_position.get('entry', 0)
        sl = active_position.get('sl', 0)
        tp = active_position.get('tp', 0)
        size = active_position.get('size', 0)
        
        # Métriques
        pnl_pct = active_position.get('pnl_pct', 0)
        max_pnl_reached = active_position.get('max_pnl_reached', 0)
        
        # Trailing
        trailing_activated = active_position.get('trailing_activated', False)
        break_even_triggered = active_position.get('break_even_triggered', False)
        
        # Config
        tp_sl_mode = active_position.get('tp_sl_mode', 'N/A')
        
        print(f"\n✅ Position active trouvée: {symbol}")
        print(f"   Direction: {direction}")
        print(f"   Entry: {entry:.8f}")
        print(f"   SL actuel: {sl:.8f}")
        print(f"   TP: {tp:.8f}")
        print(f"   Size: {size:.2f} USDT")
        print(f"   Mode: {tp_sl_mode}")
        
        print(f"\n📊 Performance:")
        print(f"   PnL actuel: {pnl_pct:.3f}%")
        print(f"   Max PnL (MFE): {max_pnl_reached:.3f}%")
        
        print(f"\n🔧 État Trailing:")
        print(f"   Trailing activé: {'✅ OUI' if trailing_activated else '❌ NON'}")
        print(f"   Break-even: {'✅ OUI' if break_even_triggered else '❌ NON'}")
        
        # Analyse trailing
        print(f"\n" + "=" * 70)
        print("🔍 DIAGNOSTIC TRAILING")
        print("=" * 70)
        
        if not trailing_activated:
            print(f"\n⚠️ TRAILING NON ACTIVÉ")
            
            # Vérifier les conditions
            if pnl_pct < 0:
                print(f"   ❌ Position en perte ({pnl_pct:.3f}%), trailing impossible")
            else:
                print(f"   ⚠️ PnL positif ({pnl_pct:.3f}%) mais trailing pas encore activé")
                print(f"   ℹ️ Le seuil trigger n'est peut-être pas atteint")
                
                # Estimer le trigger selon le mode
                if tp_sl_mode == 'FIXE':
                    print(f"   ℹ️ Mode FIXE: trigger par défaut ~0.20%")
                elif tp_sl_mode == 'ATR':
                    print(f"   ℹ️ Mode ATR: trigger basé sur ATR (1.5× ATR)")
        else:
            print(f"\n✅ TRAILING ACTIVÉ")
            
            # Vérifier si le SL a bougé
            sl_distance = abs((sl - entry) / entry * 100)
            print(f"   Distance SL/Entry: {sl_distance:.3f}%")
            
            if direction == 'LONG':
                if sl >= entry:
                    print(f"   ✅ SL ({sl:.8f}) au-dessus entry ({entry:.8f}) = BE atteint")
                else:
                    print(f"   ⚠️ SL ({sl:.8f}) encore sous entry ({entry:.8f})")
                    print(f"   ℹ️ Le prix doit monter plus pour que trailing remonte le SL")
            else:  # SHORT
                if sl <= entry:
                    print(f"   ✅ SL ({sl:.8f}) sous entry ({entry:.8f}) = BE atteint")
                else:
                    print(f"   ⚠️ SL ({sl:.8f}) encore au-dessus entry ({entry:.8f})")
                    print(f"   ℹ️ Le prix doit descendre plus pour que trailing descende le SL")
        
        # Vérification inversion
        print(f"\n" + "=" * 70)
        print("🔄 VÉRIFICATION INVERSION")
        print("=" * 70)
        
        # Vérifier dans les logs récents
        log_file = 'logs/app.log'
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                # Chercher les dernières 2000 lignes pour le message d'inversion
                recent_lines = lines[-2000:]
                inversion_found = False
                
                for line in recent_lines:
                    if 'INVERSION DE SIGNAL' in line and symbol in line:
                        print(f"\n✅ INVERSION DÉTECTÉE dans les logs:")
                        # Extraire la ligne pertinente
                        if 'Signal original:' in line:
                            print(f"   {line.strip()}")
                        inversion_found = True
                        break
                
                if not inversion_found:
                    print(f"\n⚠️ AUCUN MESSAGE D'INVERSION trouvé pour {symbol}")
                    print(f"   Direction actuelle: {direction}")
                    print(f"   ℹ️ Vérifiez si le backend a été redémarré avec invert_signals=True")
                    
            except Exception as e:
                print(f"   ⚠️ Impossible de lire les logs: {e}")
        
        # Recommandations
        print(f"\n" + "=" * 70)
        print("💡 RECOMMANDATIONS")
        print("=" * 70)
        
        if not trailing_activated and pnl_pct > 0:
            print(f"\n1. PnL positif mais trailing inactif:")
            print(f"   → Attendre que le PnL dépasse le seuil trigger")
            print(f"   → Vérifier config: trailing_trigger_pnl ou break_even_atr_mult")
        
        if trailing_activated and sl == entry:
            print(f"\n2. Trailing activé mais SL = entry:")
            print(f"   → Le prix doit continuer dans la bonne direction")
            print(f"   → Le trailing ne peut remonter que si prix monte (LONG) ou descend (SHORT)")
        
        print(f"\n3. Pour vérifier l'inversion:")
        print(f"   → Recherchez '🔄 INVERSION' dans les logs au moment de l'ouverture")
        print(f"   → Comparez la direction avec le signal original du scanner")
        
    except json.JSONDecodeError:
        print("❌ Erreur: state.json invalide (JSON mal formé)")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

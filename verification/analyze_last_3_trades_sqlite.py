"""
Analyse détaillée des 3 derniers trades pour vérifier le fonctionnement du trailing stop
Version SQLite (pas de problème d'encodage)
"""
import sqlite3
from datetime import datetime, timezone
import os

def main():
    try:
        # Connexion SQLite
        db_path = 'data/analytics.db'
        
        if not os.path.exists(db_path):
            print(f"❌ Base de données SQLite introuvable: {db_path}")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("🔍 ANALYSE DES 3 DERNIERS TRADES - TRAILING STOP")
        print("=" * 80)
        
        # Récupérer les 3 derniers trades fermés
        query = """
            SELECT 
                id,
                symbol,
                direction,
                entry_price,
                exit_price,
                sl,
                tp,
                pnl_pct,
                exit_reason,
                timestamp_entry,
                timestamp_exit,
                duration_seconds,
                tp_sl_mode,
                slippage_pct
            FROM trades
            WHERE exit_price IS NOT NULL
            ORDER BY timestamp_exit DESC
            LIMIT 3
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("❌ Aucun trade fermé trouvé")
            return
        
        print(f"\n✅ {len(rows)} trades analysés\n")
        
        for idx, row in enumerate(rows, 1):
            (trade_id, symbol, direction, entry_price, exit_price, sl, tp, pnl_pct,
             exit_reason, timestamp_entry, timestamp_exit, duration_seconds, tp_sl_mode,
             slippage_pct) = row
            
            # Calculer durée
            duration_min = duration_seconds / 60 if duration_seconds else 0
            
            print("=" * 80)
            print(f"📊 TRADE #{idx} - {symbol}")
            print("=" * 80)
            print(f"ID: {trade_id}")
            print(f"Direction: {direction}")
            print(f"Mode: {tp_sl_mode}")
            print(f"Entry: {entry_price:.8f}")
            print(f"Exit: {exit_price:.8f}")
            print(f"SL final: {sl:.8f}")
            print(f"TP: {tp:.8f}")
            print(f"Durée: {duration_min:.1f} min")
            print(f"Exit reason: {exit_reason}")
            print(f"Slippage: {slippage_pct:.3f}%" if slippage_pct else "Slippage: N/A")
            
            print(f"\n💰 Performance:")
            print(f"   PnL final: {pnl_pct:.3f}%")
            
            # Calculer les distances SL/TP
            if direction == 'LONG':
                sl_distance_pct = abs((entry_price - sl) / entry_price * 100) if entry_price else 0
                tp_distance_pct = abs((tp - entry_price) / entry_price * 100) if entry_price else 0
                price_move_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price else 0
            else:  # SHORT
                sl_distance_pct = abs((sl - entry_price) / entry_price * 100) if entry_price else 0
                tp_distance_pct = abs((entry_price - tp) / entry_price * 100) if entry_price else 0
                price_move_pct = ((entry_price - exit_price) / entry_price * 100) if entry_price else 0
            
            print(f"   SL distance: {sl_distance_pct:.3f}%")
            print(f"   TP distance: {tp_distance_pct:.3f}%")
            print(f"   Prix move: {price_move_pct:.3f}%")
            
            # Analyse de la sortie
            print(f"\n🚪 Analyse de la sortie:")
            
            if exit_reason == 'SL':
                print(f"   ❌ SL touché en {'perte' if pnl_pct < 0 else 'profit'} ({pnl_pct:.3f}%)")
                if pnl_pct < 0:
                    if abs(pnl_pct) < sl_distance_pct * 0.8:
                        print(f"   ⚠️ SL touché avant distance prévue ({abs(pnl_pct):.3f}% < {sl_distance_pct:.3f}%)")
                        print(f"   💡 Possible: slippage ou SL échange trop serré")
                else:
                    print(f"   ℹ️ Pourrait être un Trailing Stop non marqué comme 'TS'")
                    
            elif exit_reason == 'TS':
                print(f"   ✅ Trailing Stop (profits protégés: {pnl_pct:.3f}%)")
                print(f"   ✅ Le trailing a bien fonctionné")
                    
            elif exit_reason == 'TP':
                print(f"   ✅ Take Profit atteint ({pnl_pct:.3f}%)")
                if abs(pnl_pct - tp_distance_pct) > 0.05:
                    print(f"   ⚠️ PnL ({pnl_pct:.3f}%) != TP attendu ({tp_distance_pct:.3f}%)")
                
            elif exit_reason == 'STAGNATION':
                print(f"   ⏱️ Sortie par stagnation ({pnl_pct:.3f}%)")
                
            elif exit_reason and 'SL' in exit_reason:
                print(f"   ℹ️ SL variant: {exit_reason} ({pnl_pct:.3f}%)")
                
            else:
                print(f"   ℹ️ Autre raison: {exit_reason} ({pnl_pct:.3f}%)")
            
            # Vérifier si le SL a bougé (indication de trailing ou BE)
            print(f"\n🔧 Analyse du SL final:")
            
            if direction == 'LONG':
                if sl >= entry_price:
                    print(f"   ✅ SL ({sl:.8f}) >= Entry ({entry_price:.8f})")
                    print(f"   → Break-Even atteint (SL moved up)")
                    if exit_reason == 'SL':
                        print(f"   → SL touché APRÈS BE = Trailing protégeait les profits")
                else:
                    expected_sl = entry_price * (1 - sl_distance_pct / 100)
                    if abs(sl - expected_sl) < entry_price * 0.0001:
                        print(f"   ℹ️ SL ({sl:.8f}) = SL initial calculé")
                        print(f"   → Pas de mouvement de SL détecté")
                    else:
                        print(f"   ⚠️ SL ({sl:.8f}) != SL initial attendu ({expected_sl:.8f})")
            else:  # SHORT
                if sl <= entry_price:
                    print(f"   ✅ SL ({sl:.8f}) <= Entry ({entry_price:.8f})")
                    print(f"   → Break-Even atteint (SL moved down)")
                    if exit_reason == 'SL':
                        print(f"   → SL touché APRÈS BE = Trailing protégeait les profits")
                else:
                    expected_sl = entry_price * (1 + sl_distance_pct / 100)
                    if abs(sl - expected_sl) < entry_price * 0.0001:
                        print(f"   ℹ️ SL ({sl:.8f}) = SL initial calculé")
                        print(f"   → Pas de mouvement de SL détecté")
                    else:
                        print(f"   ⚠️ SL ({sl:.8f}) != SL initial attendu ({expected_sl:.8f})")
            
            # Recommandations
            print(f"\n💡 Recommandation pour ce trade:")
            
            if exit_reason == 'SL' and pnl_pct < 0 and duration_min < 1.0:
                print(f"   → SL touché très rapidement ({duration_min:.1f}min)")
                print(f"   → SL trop serré ({sl_distance_pct:.3f}%) ou mauvais timing")
                
            if exit_reason == 'TS':
                print(f"   → Trailing a bien fonctionné, protégé {pnl_pct:.3f}% de profits")
                
            if exit_reason == 'STAGNATION' and pnl_pct > 0:
                print(f"   → Sortie anticipée profitable, bon comportement")
            
            print()
        
        # Statistiques globales
        print("=" * 80)
        print("📈 STATISTIQUES GLOBALES (3 trades)")
        print("=" * 80)
        
        total_trades = len(rows)
        
        avg_pnl = sum(r[7] for r in rows if r[7] is not None) / total_trades
        avg_duration = sum(r[11] for r in rows if r[11] is not None) / total_trades / 60
        
        exit_reasons = {}
        for r in rows:
            reason = r[8]
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        print(f"\nPnL moyen: {avg_pnl:.3f}%")
        print(f"Durée moyenne: {avg_duration:.1f} min")
        
        print(f"\nRaisons de sortie:")
        for reason, count in exit_reasons.items():
            print(f"   • {reason}: {count} trade{'s' if count > 1 else ''}")
        
        # Analyse trailing
        ts_count = exit_reasons.get('TS', 0)
        sl_count = exit_reasons.get('SL', 0)
        
        print(f"\n" + "=" * 80)
        print("🎯 ANALYSE TRAILING STOP")
        print("=" * 80)
        
        if ts_count > 0:
            print(f"\n✅ {ts_count} trade{'s' if ts_count > 1 else ''} fermé{'s' if ts_count > 1 else ''} par Trailing Stop")
            print(f"   → Le trailing fonctionne et protège les profits")
        else:
            print(f"\n⚠️ AUCUN trade fermé par Trailing Stop (TS)")
            print(f"   → Soit le trailing ne s'active pas, soit les trades ne durent pas assez")
        
        if sl_count > 0:
            # Vérifier si certains SL sont en profit (donc potentiellement du trailing non marqué)
            sl_in_profit = sum(1 for r in rows if r[8] == 'SL' and r[7] and r[7] > 0)
            if sl_in_profit > 0:
                print(f"\n⚠️ {sl_in_profit} SL touché{'s' if sl_in_profit > 1 else ''} EN PROFIT")
                print(f"   → Possible trailing non marqué comme 'TS'")
                print(f"   → Vérifier la logique exit_reason dans position_manager.py")
        
        print(f"\n" + "=" * 80)
        print("🎯 CONCLUSION")
        print("=" * 80)
        
        if avg_pnl < -0.2:
            print(f"\n❌ PROBLÈME MAJEUR: PnL moyen très négatif ({avg_pnl:.3f}%)")
            print(f"   1. SL trop serré (vérifier sl_percent ou atr_mult_sl)")
            print(f"   2. Ou mauvais sens de position (vérifier inversion)")
        elif avg_pnl < 0:
            print(f"\n⚠️ PnL moyen négatif ({avg_pnl:.3f}%)")
            print(f"   → Ajuster SL ou vérifier qualité des signaux")
        else:
            print(f"\n✅ PnL moyen positif ({avg_pnl:.3f}%)")
        
        if ts_count == 0 and avg_duration < 2.0:
            print(f"\n⚠️ Trades très courts ({avg_duration:.1f}min) et pas de trailing")
            print(f"   → Trades fermés avant que trailing puisse s'activer")
            print(f"   → Réduire trailing_trigger_atr_mult ou augmenter SL initial")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

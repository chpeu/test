"""
Analyse simple des 3 derniers trades
"""
import sqlite3
import os

def main():
    try:
        db_path = 'data/analytics.db'
        
        if not os.path.exists(db_path):
            print(f"❌ Base de données introuvable: {db_path}")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # D'abord découvrir le schéma
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='trades'")
        schema = cursor.fetchone()
        if schema:
            print("Schéma de la table trades:")
            print(schema[0])
            print("\n" + "="*80 + "\n")
        
        # Lire tous les noms de colonnes
        cursor.execute("PRAGMA table_info(trades)")
        columns = cursor.fetchall()
        col_names = [col[1] for col in columns]
        
        print(f"Colonnes disponibles ({len(col_names)}):")
        for col in col_names:
            print(f"  - {col}")
        print("\n" + "="*80 + "\n")
        
        # Construire la requête avec les colonnes qui existent
        # Mapping des noms possibles
        entry_col = 'entry' if 'entry' in col_names else 'entry_price' if 'entry_price' in col_names else None
        exit_col = 'exit' if 'exit' in col_names else 'exit_price' if 'exit_price' in col_names else None
        
        if not entry_col or not exit_col:
            print("❌ Colonnes entry/exit introuvables")
            return
        
        # Requête avec colonnes existantes
        query = f"""
            SELECT 
                id, symbol, direction, {entry_col}, {exit_col}, 
                net_pnl_pct, reason, duration,
                max_pnl_reached, trailing_stop_triggered, break_even_triggered,
                timestamp, tp_sl_mode
            FROM trades
            WHERE {exit_col} IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 3
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("❌ Aucun trade fermé")
            return
        
        print(f"✅ {len(rows)} trades analysés\n")
        
        for idx, row in enumerate(rows, 1):
            (trade_id, symbol, direction, entry, exit_price, 
             pnl_pct, exit_reason, duration,
             max_pnl, trailing_triggered, be_triggered,
             timestamp, tp_sl_mode) = row
            
            duration_min = (duration / 60) if duration else 0
            
            print("="*80)
            print(f"TRADE #{idx} - {symbol}")
            print("="*80)
            print(f"ID: {trade_id}")
            print(f"Direction: {direction}")
            print(f"Mode: {tp_sl_mode}")
            print(f"Entry: {entry:.8f}")
            print(f"Exit: {exit_price:.8f}")
            print(f"Durée: {duration_min:.1f} min")
            print(f"Timestamp: {timestamp}")
            print(f"Exit reason: {exit_reason}")
            print(f"PnL: {pnl_pct:.3f}%")
            print(f"Max PnL (MFE): {max_pnl:.3f}%" if max_pnl else "Max PnL (MFE): N/A")
            
            print(f"\n🎢 Trailing Stop:")
            print(f"  Activé: {'✅ OUI' if trailing_triggered else '❌ NON'}")
            print(f"  Break-Even: {'✅ OUI' if be_triggered else '❌ NON'}")
            
            # Analyse de la performance
            print(f"\n📊 Analyse:")
            
            if trailing_triggered:
                print(f"  ✅ Trailing a été activé")
                if exit_reason == 'TS':
                    print(f"  ✅ Trade fermé par Trailing Stop - protégé {pnl_pct:.3f}%")
                    if max_pnl:
                        capture_rate = (pnl_pct / max_pnl * 100) if max_pnl > 0 else 0
                        print(f"  Capture du MFE: {capture_rate:.1f}%")
                else:
                    print(f"  ⚠️ Trailing activé mais trade fermé par: {exit_reason}")
                    if max_pnl and max_pnl > 0:
                        print(f"  ⚠️ Aurait pu capturer jusqu'à {max_pnl:.3f}%")
            else:
                print(f"  ❌ Trailing NON activé")
                if max_pnl and max_pnl > 0:
                    print(f"  ⚠️ Trade avait du potentiel (MFE: {max_pnl:.3f}%)")
                    print(f"  💡 Aurait bénéficié du trailing")
                elif max_pnl and max_pnl < 0.15:
                    print(f"  ✅ Normal - PnL trop faible pour trigger ({max_pnl:.3f}%)")
            
            if exit_reason == 'SL' and pnl_pct < 0:
                print(f"  ❌ SL touché en perte ({pnl_pct:.3f}%)")
                if max_pnl and max_pnl > 0:
                    print(f"  ⚠️ Trade était en profit (MFE: {max_pnl:.3f}%) puis retourné en perte")
                    print(f"  💡 Trailing aurait pu sauver ce trade")
            
            print()
        
        # Stats
        print("="*80)
        print("RÉSUMÉ")
        print("="*80)
        
        ts_count = sum(1 for r in rows if r[6] == 'TS')  # exit_reason est index 6
        sl_count = sum(1 for r in rows if r[6] == 'SL')
        trailing_activated_count = sum(1 for r in rows if r[9])  # trailing_triggered index 9
        avg_pnl = sum(r[7] for r in rows if r[7]) / len(rows)
        
        print(f"Trailing Stop (TS): {ts_count}/3 trades")
        print(f"Stop Loss (SL): {sl_count}/3 trades")
        print(f"PnL moyen: {avg_pnl:.3f}%")
        
        if ts_count == 0:
            print("\n⚠️ AUCUN trailing stop activé sur ces 3 trades")
            print("Causes possibles:")
            print("  1. PnL n'a pas atteint le seuil trigger (~0.18%)")
            print("  2. Trades trop courts (fermés avant activation)")
            print("  3. Trailing désactivé dans config")
        elif ts_count > 0:
            print(f"\n✅ Trailing fonctionne ({ts_count} trades)")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

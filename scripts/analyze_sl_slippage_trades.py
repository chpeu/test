#!/usr/bin/env python3
"""
Analyse des trades spécifiques avec SL slippage/gap
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime

def analyze_sl_slippage():
    load_dotenv()
    
    print("🔍 ANALYSE TRADES AVEC SL SLIPPAGE/GAP")
    print("=" * 80)
    
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD'),
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Rechercher les 3 trades spécifiques
        target_trades = [
            ("AAVE", "2026-01-09 21:15:00", "2026-01-09 21:25:00"),
            ("FARTCOIN", "2026-01-09 19:45:00", "2026-01-09 19:50:00"),
            ("BEAT", "2026-01-09 17:40:00", "2026-01-09 17:50:00")
        ]
        
        print("Recherche des trades spécifiques avec problèmes d'exécution SL...")
        print()
        
        for symbol_search, time_start, time_end in target_trades:
            print(f"🔎 {symbol_search} entre {time_start[-8:]} et {time_end[-8:]}")
            print("-" * 60)
            
            cur.execute("""
                SELECT id, symbol, direction, created_at, timestamp_exit,
                       entry_price, exit_price, sl_price, 
                       pnl_pct, pnl_usdt, exit_reason,
                       entry_sl_exchange_percent,
                       max_adverse_excursion, max_favorable_excursion,
                       break_even_set, break_even_triggered_at
                FROM trades 
                WHERE symbol LIKE %s 
                  AND created_at BETWEEN %s AND %s
                ORDER BY created_at DESC
            """, (f"%{symbol_search}%", time_start, time_end))
            
            trades = cur.fetchall()
            
            if not trades:
                print(f"❌ Aucun trade {symbol_search} trouvé dans cette fenêtre")
                print()
                continue
                
            for trade in trades:
                print(f"✅ Trade trouvé: {trade['symbol']} {trade['direction']}")
                print(f"   ID: {trade['id']}")
                print(f"   Created: {trade['created_at']}")
                print(f"   Exit: {trade['timestamp_exit']}")
                print(f"   Exit Reason: {trade['exit_reason']}")
                print()
                
                # Calculs critiques
                entry = float(trade['entry_price'])
                exit_actual = float(trade['exit_price'])
                sl_param = float(trade['sl_price']) if trade['sl_price'] else None
                direction = trade['direction']
                
                # SL paramétré théorique (depuis entry_sl_exchange_percent)
                sl_exchange_pct = trade['entry_sl_exchange_percent']
                if sl_exchange_pct:
                    sl_exchange_pct = float(sl_exchange_pct)
                    if direction == "LONG":
                        sl_theoretical = entry * (1 - sl_exchange_pct / 100)
                    else:  # SHORT
                        sl_theoretical = entry * (1 + sl_exchange_pct / 100)
                else:
                    sl_theoretical = None
                
                print(f"📊 ANALYSE SLIPPAGE:")
                print(f"   Entry Price: {entry}")
                print(f"   Exit Price (réel): {exit_actual}")
                print(f"   SL Price (loggé): {sl_param}")
                if sl_theoretical:
                    print(f"   SL Théorique ({sl_exchange_pct:.4f}%): {sl_theoretical:.6f}")
                
                # Calcul du slippage
                if sl_theoretical:
                    if direction == "LONG":
                        slippage_pct = (sl_theoretical - exit_actual) / entry * 100
                        expected_loss_pct = (entry - sl_theoretical) / entry * 100
                        actual_loss_pct = (entry - exit_actual) / entry * 100
                    else:  # SHORT
                        slippage_pct = (exit_actual - sl_theoretical) / entry * 100
                        expected_loss_pct = (sl_theoretical - entry) / entry * 100
                        actual_loss_pct = (exit_actual - entry) / entry * 100
                    
                    print(f"   Expected Loss: {expected_loss_pct:+.4f}%")
                    print(f"   Actual Loss: {actual_loss_pct:+.4f}%")
                    print(f"   SLIPPAGE: {slippage_pct:+.4f}% ({slippage_pct/sl_exchange_pct*100:+.1f}% du SL paramétré)")
                    
                    if abs(slippage_pct) > 0.05:  # > 0.05%
                        print(f"   🚨 SLIPPAGE SIGNIFICATIF DÉTECTÉ!")
                
                # Infos contextuelles
                print(f"   PnL: {trade['pnl_pct']:+.4f}% ({trade['pnl_usdt']:+.4f} USDT)")
                if trade['max_adverse_excursion']:
                    print(f"   MAE: {trade['max_adverse_excursion']:+.4f}%")
                if trade['max_favorable_excursion']:
                    print(f"   MFE: {trade['max_favorable_excursion']:+.4f}%")
                
                if trade['break_even_set']:
                    print(f"   🛡️ Break-Even activé à: {trade['break_even_triggered_at']}")
                
                print()
        
        # Analyse globale des SL_EXCHANGE avec slippage
        print("\n" + "=" * 80)
        print("📈 ANALYSE GLOBALE SL_EXCHANGE SLIPPAGE (dernières 48h)")
        print("=" * 80)
        
        cur.execute("""
            SELECT symbol, direction, created_at, entry_price, exit_price,
                   entry_sl_exchange_percent, pnl_pct, exit_reason
            FROM trades 
            WHERE created_at > NOW() - INTERVAL '48 hours'
              AND exit_reason IN ('SL', 'SL_EXCHANGE')
              AND entry_sl_exchange_percent IS NOT NULL
              AND entry_price IS NOT NULL
              AND exit_price IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 15
        """)
        
        sl_trades = cur.fetchall()
        
        print(f"Trades SL/SL_EXCHANGE analysés: {len(sl_trades)}")
        print("Symbol | Dir | Exit Reason | Expected Loss | Actual Loss | Slippage")
        print("-" * 75)
        
        significant_slippage = []
        
        for trade in sl_trades:
            entry = float(trade['entry_price'])
            exit_actual = float(trade['exit_price'])
            sl_pct = float(trade['entry_sl_exchange_percent'])
            direction = trade['direction']
            
            if direction == "LONG":
                sl_theoretical = entry * (1 - sl_pct / 100)
                slippage_pct = (sl_theoretical - exit_actual) / entry * 100
                expected_loss = sl_pct
                actual_loss_pct = (entry - exit_actual) / entry * 100
            else:  # SHORT
                sl_theoretical = entry * (1 + sl_pct / 100)
                slippage_pct = (exit_actual - sl_theoretical) / entry * 100
                expected_loss = sl_pct
                actual_loss_pct = (exit_actual - entry) / entry * 100
            
            status = "🚨" if abs(slippage_pct) > 0.05 else "✅"
            
            print(f"{trade['symbol'][:12]:12} | {direction:4} | {trade['exit_reason']:11} | "
                  f"{expected_loss:+.3f}% | {actual_loss_pct:+.3f}% | {slippage_pct:+.3f}% {status}")
            
            if abs(slippage_pct) > 0.05:
                significant_slippage.append({
                    'symbol': trade['symbol'],
                    'direction': direction,
                    'created_at': trade['created_at'],
                    'slippage_pct': slippage_pct,
                    'exit_reason': trade['exit_reason']
                })
        
        if significant_slippage:
            print(f"\n🚨 SLIPPAGE SIGNIFICATIF DÉTECTÉ sur {len(significant_slippage)} trades:")
            for slip in significant_slippage:
                print(f"   {slip['created_at']} | {slip['symbol']} {slip['direction']} | "
                      f"{slip['slippage_pct']:+.4f}% | {slip['exit_reason']}")
        else:
            print(f"\n✅ Pas de slippage significatif détecté (>{0.05:.3f}%)")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    analyze_sl_slippage()

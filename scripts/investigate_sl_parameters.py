#!/usr/bin/env python3
"""
Investigation des paramètres SL : config vs exécution vs base de données
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

def investigate_sl_parameters():
    print("🔍 INVESTIGATION PARAMÈTRES SL - MODE FIXE")
    print("=" * 80)
    
    # 1. Lire la configuration actuelle
    print("1️⃣ CONFIGURATION ACTUELLE")
    print("-" * 50)
    
    config_path = os.path.join(os.path.dirname(__file__), "..", "config_overrides.json")
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        sl_percent = config.get('sl_percent')
        tp_percent = config.get('tp_percent') 
        tp_sl_mode = config.get('tp_sl_mode')
        
        print(f"Mode TP/SL: {tp_sl_mode}")
        print(f"SL Bot (config): {sl_percent}%")
        print(f"TP Bot (config): {tp_percent}%")
        
    except Exception as e:
        print(f"❌ Erreur lecture config: {e}")
        return
    
    # 2. Constantes SL Exchange (depuis le code)
    print(f"\n2️⃣ CONSTANTES SL EXCHANGE (live_order_manager_futures.py)")
    print("-" * 50)
    
    SL_MEXC_MARGIN = 1.3  # 30% plus large que le SL bot
    SL_MEXC_MIN_PCT = 0.005  # 0.5% minimum
    
    print(f"SL_MEXC_MARGIN: {SL_MEXC_MARGIN} (×{SL_MEXC_MARGIN})")
    print(f"SL_MEXC_MIN_PCT: {SL_MEXC_MIN_PCT*100}% (0.5% minimum)")
    
    # 3. Calculs théoriques
    print(f"\n3️⃣ CALCULS THÉORIQUES")
    print("-" * 50)
    
    if sl_percent:
        sl_bot_pct = sl_percent / 100  # 0.25% -> 0.0025
        sl_exchange_calculated = sl_bot_pct * SL_MEXC_MARGIN  # 0.0025 * 1.3 = 0.00325
        sl_exchange_final = max(sl_exchange_calculated, SL_MEXC_MIN_PCT)  # max(0.00325, 0.005) = 0.005
        
        print(f"SL Bot théorique: {sl_bot_pct*100:.4f}%")
        print(f"SL Exchange calculé: {sl_exchange_calculated*100:.4f}%")
        print(f"SL Exchange final (avec min): {sl_exchange_final*100:.4f}%")
        
        # Exemple avec prix
        example_price = 100.0
        print(f"\n📊 EXEMPLE avec prix entry = {example_price}")
        print(f"   LONG:")
        print(f"   - SL Bot: {example_price * (1 - sl_bot_pct):.6f} (distance: {sl_bot_pct*100:.4f}%)")
        print(f"   - SL Exchange: {example_price * (1 - sl_exchange_final):.6f} (distance: {sl_exchange_final*100:.4f}%)")
        print(f"   SHORT:")
        print(f"   - SL Bot: {example_price * (1 + sl_bot_pct):.6f} (distance: {sl_bot_pct*100:.4f}%)")
        print(f"   - SL Exchange: {example_price * (1 + sl_exchange_final):.6f} (distance: {sl_exchange_final*100:.4f}%)")
    
    # 4. Vérification dans la base de données
    print(f"\n4️⃣ VÉRIFICATION BASE DE DONNÉES (10 derniers trades)")
    print("-" * 50)
    
    try:
        load_dotenv()
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD'),
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT created_at, symbol, direction, entry_price, sl_price,
                   entry_sl_exchange_percent, exit_price, exit_reason, pnl_pct
            FROM trades 
            WHERE created_at > NOW() - INTERVAL '24 hours'
              AND entry_sl_exchange_percent IS NOT NULL
              AND entry_price IS NOT NULL
              AND sl_price IS NOT NULL
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        trades = cur.fetchall()
        
        print("Date | Symbol Dir | Entry | SL_Bot | SL_Exchange% | Calculé_Bot% | Écart")
        print("-" * 80)
        
        discrepancies = []
        
        for trade in trades:
            entry = float(trade['entry_price'])
            sl_bot = float(trade['sl_price'])
            sl_exchange_pct = float(trade['entry_sl_exchange_percent'])
            direction = trade['direction']
            
            # Calculer la distance SL Bot réelle
            if direction == 'LONG':
                sl_bot_distance_pct = (entry - sl_bot) / entry * 100
            else:  # SHORT
                sl_bot_distance_pct = (sl_bot - entry) / entry * 100
            
            # Écart avec config théorique
            expected_sl_bot = sl_percent
            bot_discrepancy = sl_bot_distance_pct - expected_sl_bot if expected_sl_bot else 0
            
            # Écart SL Exchange vs théorique
            expected_sl_exchange = sl_exchange_final * 100 if 'sl_exchange_final' in locals() else 0
            exchange_discrepancy = sl_exchange_pct - expected_sl_exchange
            
            status = "🚨" if abs(bot_discrepancy) > 0.02 or abs(exchange_discrepancy) > 0.05 else "✅"
            
            print(f"{trade['created_at'].strftime('%m-%d %H:%M')} | "
                  f"{trade['symbol'][:8]:8} {direction:4} | "
                  f"{entry:8.4f} | {sl_bot:8.4f} | "
                  f"{sl_exchange_pct:6.3f}% | {sl_bot_distance_pct:6.3f}% | "
                  f"{bot_discrepancy:+.3f}% {status}")
            
            if abs(bot_discrepancy) > 0.02 or abs(exchange_discrepancy) > 0.05:
                discrepancies.append({
                    'symbol': trade['symbol'],
                    'direction': direction,
                    'created_at': trade['created_at'],
                    'bot_discrepancy': bot_discrepancy,
                    'exchange_discrepancy': exchange_discrepancy,
                    'exit_reason': trade['exit_reason']
                })
        
        if discrepancies:
            print(f"\n🚨 INCOHÉRENCES DÉTECTÉES ({len(discrepancies)} trades):")
            for disc in discrepancies:
                print(f"   {disc['created_at']} | {disc['symbol']} {disc['direction']} | "
                      f"Bot: {disc['bot_discrepancy']:+.3f}%, Exchange: {disc['exchange_discrepancy']:+.3f}% | "
                      f"{disc['exit_reason']}")
        else:
            print(f"\n✅ Aucune incohérence majeure détectée")
        
        # 5. Analyse slippage patterns
        print(f"\n5️⃣ ANALYSE SLIPPAGE vs PARAMÈTRES")
        print("-" * 50)
        
        cur.execute("""
            SELECT symbol, direction, entry_price, exit_price, entry_sl_exchange_percent,
                   exit_reason, pnl_pct, created_at
            FROM trades 
            WHERE created_at > NOW() - INTERVAL '48 hours'
              AND exit_reason IN ('SL', 'SL_EXCHANGE')
              AND entry_sl_exchange_percent IS NOT NULL
            ORDER BY created_at DESC 
            LIMIT 15
        """)
        
        sl_trades = cur.fetchall()
        
        print("Symbol | Dir | SL_Param% | Exit_Loss% | Slippage% | Type")
        print("-" * 65)
        
        high_slippage_count = 0
        
        for trade in sl_trades:
            entry = float(trade['entry_price'])
            exit_price = float(trade['exit_price'])
            sl_param_pct = float(trade['entry_sl_exchange_percent'])
            direction = trade['direction']
            
            # Calculer perte réelle
            if direction == 'LONG':
                actual_loss_pct = (entry - exit_price) / entry * 100
            else:  # SHORT
                actual_loss_pct = (exit_price - entry) / entry * 100
            
            slippage_pct = actual_loss_pct - sl_param_pct
            slippage_status = "🚨" if abs(slippage_pct) > 0.05 else "✅"
            
            if abs(slippage_pct) > 0.05:
                high_slippage_count += 1
            
            print(f"{trade['symbol'][:10]:10} | {direction:4} | "
                  f"{sl_param_pct:7.3f}% | {actual_loss_pct:8.3f}% | "
                  f"{slippage_pct:+7.3f}% | {trade['exit_reason']} {slippage_status}")
        
        print(f"\n📊 RÉSUMÉ SLIPPAGE:")
        print(f"   Trades SL analysés: {len(sl_trades)}")
        print(f"   Slippage significatif (>0.05%): {high_slippage_count} ({high_slippage_count/len(sl_trades)*100:.1f}%)")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur base de données: {e}")
    
    print(f"\n6️⃣ DIAGNOSTIC")
    print("-" * 50)
    
    if 'sl_exchange_final' in locals() and sl_exchange_final*100 >= 0.5:
        print(f"✅ SL Exchange minimum (0.5%) appliqué correctement")
    else:
        print(f"❌ Problème configuration SL Exchange")
    
    print(f"💡 RECOMMANDATIONS:")
    print(f"   1. SL Bot devrait être: {sl_percent}% (config)")
    print(f"   2. SL Exchange devrait être: {sl_exchange_final*100:.3f}% (min 0.5%)")
    print(f"   3. Vérifier logs 'SL MEXC MARGE' dans les traces d'exécution")
    print(f"   4. Le slippage élevé peut être dû à liquidité/timing, pas config")

if __name__ == "__main__":
    investigate_sl_parameters()

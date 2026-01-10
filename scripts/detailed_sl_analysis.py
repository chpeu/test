#!/usr/bin/env python3
"""
Analyse détaillée des SL sur les trades récents
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta

def main():
    load_dotenv()
    
    print("🔎 ANALYSE DÉTAILLÉE DES SL - TRADES RÉCENTS")
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

        # 1. Vérifier les nouveaux trades avec lock-in 0.04%
        print("\n1️⃣ VÉRIFICATION LOCK-IN 0.04% (trades depuis 10h04)")
        print("-" * 60)
        
        config_change_time = "2026-01-10 10:04:00+01:00"
        cur.execute("""
            SELECT created_at, symbol, direction, 
                   config_trailing_mfe_lock_in_pct, 
                   config_partial_tp_be_lock_in_pct,
                   pnl_pct, exit_reason
            FROM trades 
            WHERE created_at > %s 
            ORDER BY created_at DESC 
            LIMIT 10
        """, (config_change_time,))
        
        new_trades = cur.fetchall()
        if new_trades:
            print(f"✅ {len(new_trades)} nouveaux trades depuis la modif config:")
            print("Created | Symbol | Dir | TrailingLock | PartialLock | PnL | Exit")
            for t in new_trades:
                print(f"{t['created_at']} | {t['symbol']} {t['direction']} | "
                      f"{t['config_trailing_mfe_lock_in_pct']} | {t['config_partial_tp_be_lock_in_pct']} | "
                      f"{t['pnl_pct']}% | {t['exit_reason']}")
        else:
            print("❌ Aucun nouveau trade depuis la modification config")

        # 2. Analyser les SL au break-even (problème principal détecté)
        print("\n2️⃣ TRADES AVEC SL AU BREAK-EVEN (dernières 24h)")
        print("-" * 60)
        
        yesterday = datetime.now() - timedelta(days=1)
        cur.execute("""
            SELECT created_at, symbol, direction, entry_price, sl_price, 
                   exit_reason, pnl_pct, break_even_set, max_favorable_excursion
            FROM trades 
            WHERE created_at > %s 
              AND entry_price IS NOT NULL 
              AND sl_price IS NOT NULL
              AND ABS(CAST(entry_price AS DECIMAL) - CAST(sl_price AS DECIMAL)) / CAST(entry_price AS DECIMAL) < 0.002
            ORDER BY created_at DESC 
            LIMIT 15
        """, (yesterday,))
        
        be_trades = cur.fetchall()
        print(f"Trouvés: {len(be_trades)} trades avec SL ≈ entry_price")
        if be_trades:
            print("Date | Symbol Dir | Entry | SL | Distance | BE_Set | MFE | PnL | Exit")
            for t in be_trades:
                entry = float(t['entry_price'])
                sl = float(t['sl_price'])
                dist_pct = abs(entry - sl) / entry * 100
                mfe = t['max_favorable_excursion'] or 0
                print(f"{t['created_at'].strftime('%m-%d %H:%M')} | "
                      f"{t['symbol']} {t['direction']} | "
                      f"{entry:.6f} | {sl:.6f} | {dist_pct:.4f}% | "
                      f"{t['break_even_set']} | {mfe:.2f}% | {t['pnl_pct']}% | {t['exit_reason']}")

        # 3. Analyser les SL initiaux vs paramètre 0.25%
        print("\n3️⃣ SL INITIAUX THÉORIQUES (calcul distance initiale)")
        print("-" * 60)
        
        cur.execute("""
            SELECT created_at, symbol, direction, entry_price, sl_price, 
                   exit_reason, pnl_pct, break_even_set, entry_sl_exchange_percent
            FROM trades 
            WHERE created_at > %s
              AND entry_price IS NOT NULL 
              AND sl_price IS NOT NULL
              AND entry_sl_exchange_percent IS NOT NULL
            ORDER BY created_at DESC 
            LIMIT 20
        """, (yesterday,))
        
        init_trades = cur.fetchall()
        sl_param_expected = 0.25  # 0.25%
        
        if init_trades:
            print("Date | Symbol Dir | EntrySlExchange% | Calculé | Écart | PnL | Exit")
            low_sl_count = 0
            for t in init_trades:
                entry_sl_pct = float(t['entry_sl_exchange_percent'])
                if entry_sl_pct < sl_param_expected * 0.8:  # < 80% de 0.25% = 0.20%
                    low_sl_count += 1
                    ecart = entry_sl_pct - sl_param_expected
                    print(f"{t['created_at'].strftime('%m-%d %H:%M')} | "
                          f"{t['symbol']} {t['direction']} | "
                          f"{entry_sl_pct:.4f}% | {sl_param_expected:.4f}% | "
                          f"{ecart:+.4f}% | {t['pnl_pct']}% | {t['exit_reason']}")
            
            if low_sl_count == 0:
                print("✅ Aucun SL initial détecté comme anormalement bas")
            else:
                print(f"⚠️  {low_sl_count}/{len(init_trades)} trades avec entry_sl_exchange_percent < {sl_param_expected*0.8:.4f}%")

        # 4. Distribution des exit_reason pour comprendre le pattern
        print("\n4️⃣ DISTRIBUTION EXIT_REASON (20 derniers)")
        print("-" * 60)
        
        cur.execute("""
            SELECT exit_reason, COUNT(*) as count, AVG(pnl_pct) as avg_pnl
            FROM trades 
            WHERE created_at > %s
            GROUP BY exit_reason 
            ORDER BY count DESC
        """, (yesterday,))
        
        exit_stats = cur.fetchall()
        for stat in exit_stats:
            print(f"{stat['exit_reason']:15} | {stat['count']:2} trades | avg_pnl: {stat['avg_pnl']:+.3f}%")

        # 5. Résumé patterns détectés
        print("\n5️⃣ RÉSUMÉ PATTERNS DÉTECTÉS")
        print("-" * 60)
        
        if new_trades and new_trades[0]['config_trailing_mfe_lock_in_pct'] == 0.04:
            print("✅ Lock-in 0.04% est actif sur les nouveaux trades")
        elif new_trades:
            print("❌ Lock-in toujours à 0.0% sur les nouveaux trades (config pas rechargée)")
        else:
            print("⏳ Pas encore de nouveaux trades pour tester lock-in 0.04%")
            
        if be_trades:
            trailing_be = sum(1 for t in be_trades if 'TS' in (t['exit_reason'] or ''))
            sl_be = sum(1 for t in be_trades if 'SL' in (t['exit_reason'] or ''))
            print(f"📊 Pattern SL≈BE: {len(be_trades)} trades (TS:{trailing_be}, SL:{sl_be})")
            print("   → Explique pourquoi SL calculé = 0.0% (SL déplacé vers entry)")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    main()

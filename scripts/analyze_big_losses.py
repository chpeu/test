#!/usr/bin/env python3
"""Analyse des trades avec grosses pertes (< -0.5%)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}

def analyze_big_losses(limit=41, threshold=-0.5):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Trades avec PnL < threshold parmi les N derniers
    cur.execute('''
        WITH recent AS (
            SELECT * FROM trades ORDER BY timestamp_entry DESC LIMIT %s
        )
        SELECT symbol, direction, entry_price, exit_price, sl_price, tp_price,
               pnl_pct, pnl_usdt, max_favorable_excursion, max_adverse_excursion,
               exit_reason, duration_seconds, timestamp_entry,
               break_even_set, trailing_stop_activated
        FROM recent
        WHERE pnl_pct < %s
        ORDER BY pnl_pct ASC
    ''', (limit, threshold))

    trades = cur.fetchall()
    print(f'\n{"="*70}')
    print(f'TRADES AVEC PnL < {threshold}% ({len(trades)} trades sur {limit})')
    print(f'{"="*70}\n')

    for i, t in enumerate(trades, 1):
        print(f"\n{'-'*70}")
        print(f"{i}. {t['symbol']} {t['direction']}")
        print(f"   Entry: {t['entry_price']} -> Exit: {t['exit_price']}")
        print(f"   SL configure: {t['sl_price']} | TP: {t['tp_price']}")
        pnl_pct = t['pnl_pct'] or 0
        pnl_usdt = t['pnl_usdt'] or 0
        print(f"   PnL: {pnl_pct:.2f}% ({pnl_usdt:.4f} USDT)")
        mfe = t['max_favorable_excursion'] or 0
        mae = t['max_adverse_excursion'] or 0
        print(f"   MFE: {mfe:.2f}% | MAE: {mae:.2f}%")
        print(f"   Raison: {t['exit_reason']} | Duree: {t['duration_seconds']}s")
        print(f"   BE set: {t['break_even_set']} | Trail: {t['trailing_stop_activated']}")
        
        # Analyse detaillee
        entry = float(t['entry_price']) if t['entry_price'] else 0
        sl = float(t['sl_price']) if t['sl_price'] else 0
        exit_p = float(t['exit_price']) if t['exit_price'] else 0
        direction = t['direction']
        
        print(f"\n   --- DIAGNOSTIC ---")
        
        if entry and sl:
            sl_distance = abs(sl - entry) / entry * 100
            print(f"   Distance SL configuree: {sl_distance:.2f}%")
            
            if direction == 'SHORT':
                if sl < entry:
                    print(f"   [BUG] SL SHORT ({sl:.8f}) SOUS Entry ({entry:.8f}) - SL du mauvais cote!")
                else:
                    print(f"   [OK] SL SHORT: {sl:.8f} au-dessus de {entry:.8f}")
            else:
                if sl > entry:
                    print(f"   [BUG] SL LONG ({sl:.8f}) AU-DESSUS Entry ({entry:.8f}) - SL du mauvais cote!")
                else:
                    print(f"   [OK] SL LONG: {sl:.8f} en-dessous de {entry:.8f}")
        
        if entry and exit_p:
            actual_loss = abs(exit_p - entry) / entry * 100
            print(f"   Perte reelle: {actual_loss:.2f}%")
            if sl_distance and actual_loss > sl_distance * 1.2:
                print(f"   [ATTENTION] Perte ({actual_loss:.2f}%) depasse SL configure ({sl_distance:.2f}%)")
                print(f"   -> Possible: Slippage, SL MEXC trigger, ou gap de prix")
        
        if mfe <= 0:
            print(f"   [SETUP] Trade jamais en profit - mauvaise entree")
        elif mfe > 0.1 and pnl_pct < -0.3:
            print(f"   [GESTION] Avait +{mfe:.2f}% mais perdu - probleme de gestion")

    cur.close()
    conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=41)
    parser.add_argument('--threshold', type=float, default=-0.5)
    args = parser.parse_args()
    analyze_big_losses(args.limit, args.threshold)

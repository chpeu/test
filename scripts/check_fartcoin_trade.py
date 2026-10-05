#!/usr/bin/env python3
"""Analyse detaillee du trade FARTCOIN."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except: pass

import psycopg2
from psycopg2.extras import RealDictCursor

def main():
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("ANALYSE TRADE FARTCOIN")
    print("=" * 80)
    
    cur.execute("""
        SELECT *
        FROM trades 
        WHERE symbol LIKE '%FARTCOIN%'
        ORDER BY timestamp_entry DESC 
        LIMIT 1
    """)
    
    row = cur.fetchone()
    if not row:
        print("Aucun trade FARTCOIN trouve")
        return
    
    print(f"\nID: {row.get('id')}")
    print(f"Symbol: {row.get('symbol')}")
    print(f"Direction: {row.get('direction')}")
    print(f"Entry Time: {row.get('timestamp_entry')}")
    print(f"Exit Time: {row.get('timestamp_exit')}")
    print(f"\nPrix:")
    print(f"  Entry: {row.get('entry_price')}")
    print(f"  Exit: {row.get('exit_price')}")
    print(f"  TP: {row.get('tp_price')}")
    print(f"  SL: {row.get('sl_price')}")
    print(f"\nSize: {row.get('size_usdt')} USDT")
    print(f"\nPnL:")
    print(f"  Gross: {row.get('gross_pnl_usdt')} USDT")
    print(f"  Net: {row.get('net_pnl_usdt')} USDT ({row.get('net_pnl_pct')}%)")
    print(f"\nExit Reason: {row.get('exit_reason')}")
    print(f"Duration: {row.get('duration_seconds')}s")
    
    # Show all columns for debugging
    print(f"\n--- TOUTES LES COLONNES ---")
    for k, v in row.items():
        if v is not None:
            print(f"  {k}: {v}")
    
    # Calcul manuel du PnL attendu
    if row['entry_price'] and row['exit_price'] and row['direction']:
        entry = float(row['entry_price'])
        exit = float(row['exit_price'])
        size = float(row['size_usdt']) if row['size_usdt'] else 19.36
        
        if row['direction'] == 'SHORT':
            pnl_pct = (entry - exit) / entry * 100
            pnl_usdt = (entry - exit) / entry * size
        else:
            pnl_pct = (exit - entry) / entry * 100
            pnl_usdt = (exit - entry) / entry * size
        
        print(f"\n--- CALCUL MANUEL ---")
        print(f"Entry: {entry}")
        print(f"Exit: {exit}")
        print(f"Direction: {row['direction']}")
        print(f"Size: {size} USDT")
        print(f"PnL % calcule: {pnl_pct:.4f}%")
        print(f"PnL USDT calcule: {pnl_usdt:.4f} USDT")
        
        # Avec le SL MEXC reel (0.2784 selon les logs)
        sl_mexc = 0.2784
        if row['direction'] == 'SHORT':
            pnl_pct_sl = (entry - sl_mexc) / entry * 100
            pnl_usdt_sl = (entry - sl_mexc) / entry * size
        print(f"\n--- AVEC SL MEXC REEL (0.2784) ---")
        print(f"PnL % avec SL MEXC: {pnl_pct_sl:.4f}%")
        print(f"PnL USDT avec SL MEXC: {pnl_usdt_sl:.4f} USDT")
    
    conn.close()
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()

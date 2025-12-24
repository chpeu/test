#!/usr/bin/env python3
"""Vérifie l'activité récente : scans, setups et trades."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

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
    
    print("=" * 70)
    print("ACTIVITE RECENTE (dernières 12h)")
    print("=" * 70)
    
    # Scans totaux
    cur.execute("SELECT COUNT(*) as cnt FROM scan_logs WHERE timestamp > NOW() - INTERVAL '12 hours'")
    scans = cur.fetchone()['cnt']
    
    # Setups valides (sans reject_reason)
    cur.execute("SELECT COUNT(*) as cnt FROM scan_logs WHERE timestamp > NOW() - INTERVAL '12 hours' AND reject_reason IS NULL AND ml_confidence IS NOT NULL")
    setups = cur.fetchone()['cnt']
    
    # Trades
    cur.execute("SELECT COUNT(*) as cnt FROM trades WHERE timestamp_entry > NOW() - INTERVAL '12 hours'")
    trades = cur.fetchone()['cnt']
    
    print(f"\nScans totaux    : {scans}")
    print(f"Setups valides  : {setups}")
    print(f"Trades ouverts  : {trades}")
    
    # Derniers scans
    print("\n" + "-" * 70)
    print("5 DERNIERS SCANS")
    print("-" * 70)
    cur.execute("""
        SELECT timestamp, symbol, reject_reason, ml_confidence 
        FROM scan_logs 
        ORDER BY timestamp DESC 
        LIMIT 5
    """)
    for row in cur.fetchall():
        ts = row['timestamp'].strftime('%Y-%m-%d %H:%M') if row['timestamp'] else 'N/A'
        sym = row['symbol'] or 'N/A'
        reason = row['reject_reason'] or 'SETUP VALIDE'
        ml = f"{row['ml_confidence']:.1f}%" if row['ml_confidence'] else 'N/A'
        print(f"  {ts} | {sym:<15} | {reason[:30]:<30} | ML: {ml}")
    
    # Derniers trades
    print("\n" + "-" * 70)
    print("5 DERNIERS TRADES")
    print("-" * 70)
    cur.execute("""
        SELECT timestamp_entry, symbol, direction, net_pnl_usdt, exit_reason 
        FROM trades 
        ORDER BY timestamp_entry DESC 
        LIMIT 5
    """)
    rows = cur.fetchall()
    if not rows:
        print("  Aucun trade récent")
    else:
        for row in rows:
            ts = row['timestamp_entry'].strftime('%Y-%m-%d %H:%M') if row['timestamp_entry'] else 'N/A'
            sym = row['symbol'] or 'N/A'
            dir = row['direction'] or 'N/A'
            pnl = f"{row['net_pnl_usdt']:+.2f}$" if row['net_pnl_usdt'] else 'N/A'
            reason = row['exit_reason'] or 'OUVERT'
            print(f"  {ts} | {sym:<15} | {dir:<5} | PnL: {pnl:<10} | {reason}")
    
    # Raisons de rejet les plus fréquentes (12h)
    print("\n" + "-" * 70)
    print("RAISONS DE REJET (12h)")
    print("-" * 70)
    cur.execute("""
        SELECT reject_reason, COUNT(*) as cnt 
        FROM scan_logs 
        WHERE timestamp > NOW() - INTERVAL '12 hours' 
          AND reject_reason IS NOT NULL
        GROUP BY reject_reason 
        ORDER BY cnt DESC 
        LIMIT 10
    """)
    rows = cur.fetchall()
    if not rows:
        print("  Aucun rejet")
    else:
        for row in rows:
            print(f"  {row['cnt']:>5}x | {row['reject_reason'][:60]}")
    
    conn.close()
    print("\n" + "=" * 70)

if __name__ == '__main__':
    main()

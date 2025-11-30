#!/usr/bin/env python3
"""Boucle de verification order flow"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from dotenv import load_dotenv
load_dotenv()

LAST_ID = 101609  # ID avant redemarrage

def check():
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cur = conn.cursor()
    
    cur.execute(f"""
        SELECT id, symbol, 
               delta_volume IS NOT NULL as has_dv,
               bid_vol, ask_vol
        FROM scan_logs 
        WHERE id > {LAST_ID} AND symbol NOT LIKE '%TEST%'
        ORDER BY id DESC LIMIT 5
    """)
    rows = cur.fetchall()
    
    cur.execute(f"""
        SELECT COUNT(*) as total,
               COUNT(delta_volume) as with_dv
        FROM scan_logs WHERE id > {LAST_ID} AND symbol NOT LIKE '%TEST%'
    """)
    stats = cur.fetchone()
    
    cur.close()
    conn.close()
    return rows, stats

print("=" * 60)
print("  VERIFICATION ORDER FLOW - Ctrl+C pour arreter")
print(f"  Surveillance des scans avec ID > {LAST_ID}")
print("=" * 60)

while True:
    rows, stats = check()
    total, with_dv = stats
    
    print(f"\n[{time.strftime('%H:%M:%S')}] Nouveaux: {total} | Avec order flow: {with_dv}")
    
    if rows:
        print(f"  {'ID':<8} {'Symbol':<20} {'OK?':<5} {'bid_vol':<15} {'ask_vol'}")
        for r in rows:
            ok = "YES" if r[2] else "NO"
            print(f"  {r[0]:<8} {r[1]:<20} {ok:<5} {r[3]} / {r[4]}")
        
        if with_dv > 0:
            print("\n  *** ORDER FLOW FONCTIONNE! ***")
            break
    
    time.sleep(10)

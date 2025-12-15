#!/usr/bin/env python3
"""
WATCH ORDER FLOW - Boucle de vérification en temps réel
========================================================
Surveille les nouveaux scans et vérifie que les colonnes order flow sont remplies.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def get_conn():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

def check_latest():
    conn = get_conn()
    cur = conn.cursor()
    
    # Derniers scans
    cur.execute("""
        SELECT id, symbol, 
               delta_volume IS NOT NULL as has_delta,
               imbalance_normalized IS NOT NULL as has_imbalance,
               price_momentum_5 IS NOT NULL as has_momentum
        FROM scan_logs 
        WHERE symbol NOT LIKE 'TEST%'
        ORDER BY id DESC LIMIT 5
    """)
    rows = cur.fetchall()
    
    # Stats
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE id > 101412 AND delta_volume IS NOT NULL) as new_with_of,
            COUNT(*) FILTER (WHERE id > 101412) as new_total
        FROM scan_logs
        WHERE symbol NOT LIKE 'TEST%'
    """)
    stats = cur.fetchone()
    
    cur.close()
    conn.close()
    return rows, stats

def main():
    print("=" * 70)
    print("  WATCH ORDER FLOW - Surveillance en temps réel")
    print("  Ctrl+C pour arrêter")
    print("=" * 70)
    
    last_id = 0
    success_count = 0
    
    while True:
        rows, stats = check_latest()
        new_with_of, new_total = stats
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Nouveaux scans avec order flow: {new_with_of}/{new_total}")
        
        if rows:
            current_max_id = rows[0][0]
            if current_max_id > last_id:
                print("\n  5 derniers scans:")
                print(f"  {'ID':<8} {'Symbol':<25} {'delta':<6} {'imbal':<6} {'mom':<6}")
                print(f"  {'-'*55}")
                
                all_ok = True
                for row in rows:
                    id_, symbol, has_d, has_i, has_m = row
                    d = "✅" if has_d else "❌"
                    i = "✅" if has_i else "❌"
                    m = "✅" if has_m else "❌"
                    print(f"  {id_:<8} {symbol:<25} {d:<6} {i:<6} {m:<6}")
                    if not has_d:
                        all_ok = False
                
                if all_ok and rows[0][2]:  # Le plus récent a order flow
                    success_count += 1
                    if success_count >= 3:
                        print("\n" + "=" * 70)
                        print("  ✅ SUCCESS! Order flow fonctionne depuis 3 vérifications!")
                        print("=" * 70)
                        return
                else:
                    success_count = 0
                
                last_id = current_max_id
        
        time.sleep(15)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nArrêté par l'utilisateur.")

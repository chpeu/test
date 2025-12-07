#!/usr/bin/env python3
"""
VERIFICATION COMPLETE ORDER FLOW
================================
Verifie que les 6 colonnes order flow sont correctement remplies
et que les calculs sont mathematiquement corrects.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import math

load_dotenv()

def get_conn():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

def verify_calculations(last_n=20):
    """Verifie que les calculs sont corrects"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(f"""
        SELECT id, symbol, bid_vol, ask_vol, 
               delta_volume, imbalance_normalized, book_depth_ratio,
               spread_volatility_5, volume_acceleration, price_momentum_5
        FROM scan_logs 
        WHERE bid_vol IS NOT NULL AND ask_vol IS NOT NULL
        ORDER BY id DESC LIMIT {last_n}
    """)
    rows = cur.fetchall()
    
    errors = []
    for row in rows:
        id_, symbol, bid, ask, dv, imb, bdr, sv5, va, pm5 = row
        
        # Verifier delta_volume
        if dv is not None:
            expected_dv = bid - ask
            if abs(dv - expected_dv) > 0.01:
                errors.append(f"ID {id_}: delta_volume incorrect ({dv} != {expected_dv})")
        
        # Verifier imbalance_normalized
        if imb is not None and (bid + ask) > 0:
            expected_imb = (bid - ask) / (bid + ask)
            if abs(imb - expected_imb) > 0.0001:
                errors.append(f"ID {id_}: imbalance_normalized incorrect ({imb} != {expected_imb})")
        
        # Verifier book_depth_ratio
        if bdr is not None and ask > 0:
            expected_bdr = bid / ask
            if abs(bdr - expected_bdr) > 0.0001:
                errors.append(f"ID {id_}: book_depth_ratio incorrect ({bdr} != {expected_bdr})")
    
    cur.close()
    conn.close()
    
    return len(rows), errors

def get_fill_stats():
    """Recupere les stats de remplissage"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(delta_volume) as dv,
            COUNT(imbalance_normalized) as imb,
            COUNT(spread_volatility_5) as sv5,
            COUNT(book_depth_ratio) as bdr,
            COUNT(volume_acceleration) as va,
            COUNT(price_momentum_5) as pm5,
            COUNT(bid_vol) as has_bid
        FROM scan_logs 
        WHERE id > (SELECT MAX(id) - 100 FROM scan_logs)
    """)
    stats = cur.fetchone()
    
    cur.close()
    conn.close()
    return stats

def main():
    print("=" * 70)
    print("  VERIFICATION COMPLETE ORDER FLOW")
    print("  Ctrl+C pour arreter")
    print("=" * 70)
    
    success_count = 0
    
    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Verification...")
        
        # Stats de remplissage
        stats = get_fill_stats()
        total, dv, imb, sv5, bdr, va, pm5, has_bid = stats
        
        print(f"\n  REMPLISSAGE (derniers 100 scans):")
        print(f"  {'Colonne':<25} {'Rempli':<10} {'%':<10}")
        print(f"  {'-'*45}")
        print(f"  {'delta_volume':<25} {dv:<10} {dv*100//total if total else 0}%")
        print(f"  {'imbalance_normalized':<25} {imb:<10} {imb*100//total if total else 0}%")
        print(f"  {'spread_volatility_5':<25} {sv5:<10} {sv5*100//total if total else 0}%")
        print(f"  {'book_depth_ratio':<25} {bdr:<10} {bdr*100//total if total else 0}%")
        print(f"  {'volume_acceleration':<25} {va:<10} {va*100//total if total else 0}%")
        print(f"  {'price_momentum_5':<25} {pm5:<10} {pm5*100//total if total else 0}%")
        print(f"  {'-'*45}")
        print(f"  {'(scans avec bid_vol)':<25} {has_bid:<10}")
        
        # Verification des calculs
        checked, errors = verify_calculations(20)
        
        print(f"\n  VERIFICATION CALCULS ({checked} scans):")
        if errors:
            for err in errors[:5]:
                print(f"  [ERREUR] {err}")
            success_count = 0
        else:
            print(f"  [OK] Tous les calculs sont corrects!")
            success_count += 1
        
        # Calcul du taux global
        min_fill = min(dv, imb, sv5, bdr, va, pm5)
        fill_rate = min_fill * 100 // total if total else 0
        
        if fill_rate >= 80 and not errors:
            print(f"\n  *** SUCCES: Taux de remplissage >= 80% ({fill_rate}%) ***")
            if success_count >= 3:
                print(f"\n  *** VALIDATION COMPLETE APRES 3 VERIFICATIONS ***")
                break
        else:
            success_count = 0
        
        time.sleep(30)
    
    print("\n" + "=" * 70)
    print("  ORDER FLOW MIGRATION: VALIDEE")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nArrete par l'utilisateur.")

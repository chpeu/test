#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MONITORING ORDER FLOW - Vérifie que les colonnes se remplissent
================================================================
Execute ce script après redémarrage du backend pour vérifier
que les nouvelles colonnes order flow sont bien remplies.
"""

import sys
import os
import time
from datetime import datetime, timedelta

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

def check_orderflow_columns():
    """Vérifie le remplissage des colonnes order flow"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Stats globales
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(delta_volume) as with_delta,
            COUNT(imbalance_normalized) as with_imbalance,
            COUNT(spread_volatility_5) as with_spread_vol,
            COUNT(book_depth_ratio) as with_depth_ratio,
            COUNT(volume_acceleration) as with_vol_accel,
            COUNT(price_momentum_5) as with_momentum
        FROM scan_logs
    """)
    stats = cursor.fetchone()
    
    # Derniers scans
    cursor.execute("""
        SELECT 
            id, symbol, timestamp,
            delta_volume, imbalance_normalized, book_depth_ratio,
            bid_vol, ask_vol
        FROM scan_logs 
        ORDER BY timestamp DESC 
        LIMIT 5
    """)
    recent = cursor.fetchall()
    
    # Scans récents avec order flow
    cursor.execute("""
        SELECT 
            COUNT(*) as count,
            MIN(timestamp) as first_with_of,
            MAX(timestamp) as last_with_of
        FROM scan_logs 
        WHERE delta_volume IS NOT NULL
    """)
    with_of = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return stats, recent, with_of

def print_status():
    """Affiche le statut actuel"""
    try:
        stats, recent, with_of = check_orderflow_columns()
        
        total, delta, imb, spread_v, depth_r, vol_a, mom = stats
        
        print("\n" + "=" * 70)
        print(f"  MONITORING ORDER FLOW - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 70)
        
        print(f"\n  STATS GLOBALES:")
        print(f"  ├─ Total scans: {total}")
        print(f"  ├─ Avec delta_volume: {delta} ({delta/total*100:.1f}%)" if total > 0 else "")
        print(f"  ├─ Avec imbalance_normalized: {imb}")
        print(f"  ├─ Avec spread_volatility_5: {spread_v}")
        print(f"  ├─ Avec book_depth_ratio: {depth_r}")
        print(f"  ├─ Avec volume_acceleration: {vol_a}")
        print(f"  └─ Avec price_momentum_5: {mom}")
        
        if with_of[0] > 0:
            print(f"\n  ✅ ORDER FLOW ACTIF!")
            print(f"  ├─ Premier scan avec OF: {with_of[1]}")
            print(f"  └─ Dernier scan avec OF: {with_of[2]}")
        else:
            print(f"\n  ⚠️ AUCUN SCAN AVEC ORDER FLOW")
        
        print(f"\n  5 DERNIERS SCANS:")
        print(f"  {'ID':<8} {'Symbol':<25} {'delta_vol':<12} {'imbalance':<12} {'bid/ask'}")
        print(f"  {'-'*75}")
        
        for row in recent:
            id_, symbol, ts, delta_v, imb_n, depth_r, bid, ask = row
            delta_str = f"{delta_v:.2f}" if delta_v else "NULL"
            imb_str = f"{imb_n:.4f}" if imb_n else "NULL"
            bidask_str = f"{bid:.0f}/{ask:.0f}" if bid and ask else "NULL"
            
            status = "✅" if delta_v else "❌"
            print(f"  {status} {id_:<6} {symbol:<25} {delta_str:<12} {imb_str:<12} {bidask_str}")
        
        return delta > 0  # True si au moins un scan a order flow
        
    except Exception as e:
        print(f"\n  ❌ ERREUR: {e}")
        return False

def main():
    print("\n" + "=" * 70)
    print("  DEMARRAGE MONITORING ORDER FLOW")
    print("  Vérifie toutes les 30 secondes si les colonnes se remplissent")
    print("  Ctrl+C pour arrêter")
    print("=" * 70)
    
    # Vérification initiale
    has_orderflow = print_status()
    
    if has_orderflow:
        print("\n  ✅ Les colonnes order flow sont déjà remplies!")
        return
    
    print("\n  ⏳ En attente de nouveaux scans avec order flow...")
    print("  (Assurez-vous que le backend est redémarré)")
    
    # Boucle de monitoring
    checks = 0
    max_checks = 20  # 10 minutes max
    
    while checks < max_checks:
        time.sleep(30)
        checks += 1
        
        has_orderflow = print_status()
        
        if has_orderflow:
            print("\n" + "=" * 70)
            print("  ✅ SUCCESS! Les colonnes order flow se remplissent!")
            print("=" * 70)
            return
    
    print("\n" + "=" * 70)
    print("  ⚠️ TIMEOUT: Aucun scan avec order flow après 10 minutes")
    print("  Vérifiez:")
    print("  1. Le backend est bien redémarré")
    print("  2. Le scanner est actif (mode AUTO)")
    print("  3. Les logs pour d'éventuelles erreurs")
    print("=" * 70)

if __name__ == "__main__":
    main()

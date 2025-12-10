#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST INSERTION ORDER FLOW - Test direct du logging PostgreSQL
==============================================================
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.scanner import ScalabilityScanner
from core.postgresql_datalogger import PostgreSQLDataLogger

async def test_insert():
    print("=" * 70)
    print("  TEST INSERTION ORDER FLOW DANS POSTGRESQL")
    print("=" * 70)
    
    # Scanner une paire
    scanner = ScalabilityScanner()
    print("\n[1] Scanner SOL/USDT:USDT...")
    pair_data = await scanner.scan_pair("SOL/USDT:USDT")
    
    if not pair_data:
        print("   ❌ Scan échoué")
        return
    
    print(f"   ✅ Scan réussi")
    print(f"   delta_volume = {pair_data.get('delta_volume')}")
    print(f"   imbalance_normalized = {pair_data.get('imbalance_normalized')}")
    
    # Construire scan_data comme dans scanner_loop.py
    print("\n[2] Construction scan_data...")
    
    scan_data = {
        'scan_duration_ms': 100,
        'market_data': {
            'price': pair_data.get('price'),
            'spread_pct': pair_data.get('spread'),
            'book_depth': pair_data.get('bookDepth'),
            'balance_score': pair_data.get('balanceScore'),
            'bid_vol': pair_data.get('bidVol'),
            'ask_vol': pair_data.get('askVol'),
            'recent_volume': pair_data.get('recentVolume'),
            'vol5': pair_data.get('vol5'),
            'vol15': pair_data.get('vol15'),
            'scalability_score': pair_data.get('score'),
            # ORDER FLOW
            'delta_volume': pair_data.get('delta_volume'),
            'imbalance_normalized': pair_data.get('imbalance_normalized'),
            'spread_volatility_5': pair_data.get('spread_volatility_5'),
            'book_depth_ratio': pair_data.get('book_depth_ratio'),
            'volume_acceleration': pair_data.get('volume_acceleration'),
            'price_momentum_5': pair_data.get('price_momentum_5'),
        },
        'indicators_1m': {},
        'indicators_5m': {},
        'filters': {},
        'scores': {},
        'patterns': {},
        'is_opportunity': False,
        'reject_reason': 'TEST_ORDERFLOW',
        'reject_reason_category': 'TEST',
        'params_snapshot': {}
    }
    
    print(f"   market_data['delta_volume'] = {scan_data['market_data'].get('delta_volume')}")
    print(f"   market_data['imbalance_normalized'] = {scan_data['market_data'].get('imbalance_normalized')}")
    
    # Logger en mode DIRECT (pas batch)
    print("\n[3] Insertion en mode DIRECT (pas batch)...")
    logger = PostgreSQLDataLogger()
    
    if not logger.enabled:
        print("   ❌ Logger PostgreSQL désactivé!")
        return
    
    scan_id = logger.log_scan(
        symbol="TEST/ORDERFLOW:USDT",
        scan_data=scan_data,
        use_batch=False  # Mode direct pour test
    )
    
    if scan_id:
        print(f"   ✅ Scan inséré avec ID: {scan_id}")
        
        # Vérifier l'insertion
        print("\n[4] Vérification dans PostgreSQL...")
        import psycopg2
        from dotenv import load_dotenv
        load_dotenv()
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, symbol, delta_volume, imbalance_normalized, 
                   spread_volatility_5, book_depth_ratio, 
                   volume_acceleration, price_momentum_5
            FROM scan_logs 
            WHERE id = %s
        """, (scan_id,))
        
        row = cursor.fetchone()
        if row:
            print(f"   ID: {row[0]}")
            print(f"   Symbol: {row[1]}")
            print(f"   delta_volume: {row[2]}")
            print(f"   imbalance_normalized: {row[3]}")
            print(f"   spread_volatility_5: {row[4]}")
            print(f"   book_depth_ratio: {row[5]}")
            print(f"   volume_acceleration: {row[6]}")
            print(f"   price_momentum_5: {row[7]}")
            
            if row[2] is not None:
                print("\n   ✅ SUCCESS! Les colonnes order flow sont remplies!")
            else:
                print("\n   ❌ ÉCHEC! Les colonnes sont NULL")
        
        cursor.close()
        conn.close()
    else:
        print("   ❌ Insertion échouée (scan_id=None)")
    
    await scanner.close()
    print("\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(test_insert())

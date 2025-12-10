#!/usr/bin/env python3
"""Test mode batch pour order flow"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import asyncio
from core.scanner import ScalabilityScanner
from core.postgresql_datalogger import PostgreSQLDataLogger

async def test_batch():
    print("=" * 70)
    print("  TEST BATCH INSERT ORDER FLOW")
    print("=" * 70)
    
    scanner = ScalabilityScanner()
    pair_data = await scanner.scan_pair("ETH/USDT:USDT")
    
    if not pair_data:
        print("❌ Scan échoué")
        return
    
    print(f"\n[1] Scan ETH: delta_volume={pair_data.get('delta_volume')}")
    
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
            'delta_volume': pair_data.get('delta_volume'),
            'imbalance_normalized': pair_data.get('imbalance_normalized'),
            'spread_volatility_5': pair_data.get('spread_volatility_5'),
            'book_depth_ratio': pair_data.get('book_depth_ratio'),
            'volume_acceleration': pair_data.get('volume_acceleration'),
            'price_momentum_5': pair_data.get('price_momentum_5'),
        },
        'indicators_1m': {}, 'indicators_5m': {}, 'filters': {},
        'scores': {}, 'patterns': {},
        'is_opportunity': False,
        'reject_reason': 'TEST_BATCH',
        'reject_reason_category': 'TEST',
        'params_snapshot': {}
    }
    
    logger = PostgreSQLDataLogger()
    
    print("\n[2] Test mode BATCH...")
    # Ajouter au buffer
    logger.log_scan("TEST/BATCH:USDT", scan_data, use_batch=True)
    
    # Forcer le flush
    print("[3] Flush forcé...")
    logger._flush_buffers(force=True)
    
    # Vérifier
    print("\n[4] Vérification...")
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
        SELECT id, symbol, delta_volume, imbalance_normalized, price_momentum_5
        FROM scan_logs 
        WHERE symbol = 'TEST/BATCH:USDT'
        ORDER BY id DESC LIMIT 1
    """)
    
    row = cursor.fetchone()
    if row:
        print(f"   ID: {row[0]}")
        print(f"   delta_volume: {row[2]}")
        print(f"   imbalance_normalized: {row[3]}")
        print(f"   price_momentum_5: {row[4]}")
        
        if row[2] is not None:
            print("\n   ✅ BATCH INSERT FONCTIONNE!")
        else:
            print("\n   ❌ Colonnes NULL - batch insert broken")
    else:
        print("   ❌ Aucune ligne trouvée")
    
    cursor.close()
    conn.close()
    await scanner.close()

if __name__ == "__main__":
    asyncio.run(test_batch())

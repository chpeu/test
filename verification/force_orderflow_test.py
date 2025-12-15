#!/usr/bin/env python3
"""
FORCE TEST ORDER FLOW - Simule le flux complet du backend
"""

import sys, os, time, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from dotenv import load_dotenv
load_dotenv()

def get_conn():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

async def main():
    print("=" * 70)
    print("  FORCE TEST ORDER FLOW")
    print("=" * 70)
    
    # 1. Scanner une paire
    print("\n[1] Import et scan...")
    from core.scanner import ScalabilityScanner
    from core.postgresql_datalogger import PostgreSQLDataLogger
    
    scanner = ScalabilityScanner()
    pair = await scanner.scan_pair("BTC/USDT:USDT")
    
    if not pair:
        print("   ERREUR: Scan echoue")
        return
    
    print(f"   Scan OK: delta_volume={pair.get('delta_volume')}")
    
    # 2. Construire scan_data EXACTEMENT comme scanner_loop
    print("\n[2] Construction scan_data...")
    
    # Simuler scalability_data depuis pair (comme dans top_pairs)
    bid_vol = pair.get('bidVol')
    ask_vol = pair.get('askVol')
    
    scalability_data = {
        'spread': pair.get('spread'),
        'bookDepth': pair.get('bookDepth'),
        'balanceScore': pair.get('balanceScore'),
        'bidVol': bid_vol,
        'askVol': ask_vol,
        'bid_vol': bid_vol,
        'ask_vol': ask_vol,
        'recent_volume': pair.get('recentVolume'),
        'vol5': pair.get('vol5'),
        'vol15': pair.get('vol15'),
        'scalability_score': pair.get('score'),
        # ORDER FLOW
        'delta_volume': pair.get('delta_volume'),
        'imbalance_normalized': pair.get('imbalance_normalized'),
        'spread_volatility_5': pair.get('spread_volatility_5'),
        'book_depth_ratio': pair.get('book_depth_ratio'),
        'volume_acceleration': pair.get('volume_acceleration'),
        'price_momentum_5': pair.get('price_momentum_5'),
    }
    
    print(f"   scalability_data['delta_volume'] = {scalability_data.get('delta_volume')}")
    
    # Construire scan_data comme scanner_loop ligne 1211+
    scan_data = {
        'scan_duration_ms': 100,
        'market_data': {
            'price': pair.get('price'),
            'spread_pct': scalability_data.get('spread'),
            'book_depth': scalability_data.get('bookDepth'),
            'balance_score': scalability_data.get('balanceScore'),
            'bid_vol': scalability_data.get('bidVol') or scalability_data.get('bid_vol'),
            'ask_vol': scalability_data.get('askVol') or scalability_data.get('ask_vol'),
            'recent_volume': scalability_data.get('recent_volume'),
            'vol5': scalability_data.get('vol5'),
            'vol15': scalability_data.get('vol15'),
            'scalability_score': scalability_data.get('scalability_score'),
            # ORDER FLOW
            'delta_volume': scalability_data.get('delta_volume'),
            'imbalance_normalized': scalability_data.get('imbalance_normalized'),
            'spread_volatility_5': scalability_data.get('spread_volatility_5'),
            'book_depth_ratio': scalability_data.get('book_depth_ratio'),
            'volume_acceleration': scalability_data.get('volume_acceleration'),
            'price_momentum_5': scalability_data.get('price_momentum_5'),
        },
        'indicators_1m': {},
        'indicators_5m': {},
        'filters': {},
        'scores': {},
        'patterns': {},
        'is_opportunity': False,
        'reject_reason': 'FORCE_TEST',
        'reject_reason_category': 'TEST',
        'params_snapshot': {}
    }
    
    print(f"   scan_data['market_data']['delta_volume'] = {scan_data['market_data'].get('delta_volume')}")
    
    # 3. Logger avec batch=True (comme le backend)
    print("\n[3] Log avec batch=True...")
    logger = PostgreSQLDataLogger()
    
    # Ajouter au buffer
    logger.log_scan("FORCE/TEST:USDT", scan_data, use_batch=True)
    print(f"   Buffer size: {len(logger.scan_buffer)}")
    
    # 4. Forcer le flush
    print("\n[4] Flush force...")
    logger._flush_buffers(force=True)
    
    # 5. Verifier dans la base
    print("\n[5] Verification PostgreSQL...")
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, symbol, delta_volume, imbalance_normalized, 
               book_depth_ratio, price_momentum_5
        FROM scan_logs 
        WHERE symbol = 'FORCE/TEST:USDT'
        ORDER BY id DESC LIMIT 1
    """)
    
    row = cur.fetchone()
    if row:
        print(f"   ID: {row[0]}")
        print(f"   delta_volume: {row[2]}")
        print(f"   imbalance_normalized: {row[3]}")
        print(f"   book_depth_ratio: {row[4]}")
        print(f"   price_momentum_5: {row[5]}")
        
        if row[2] is not None:
            print("\n   *** SUCCESS! Les colonnes sont remplies! ***")
        else:
            print("\n   *** ECHEC! Colonnes NULL ***")
    else:
        print("   Aucune ligne trouvee")
    
    cur.close()
    conn.close()
    await scanner.close()
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(main())

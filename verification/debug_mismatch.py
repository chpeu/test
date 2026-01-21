
import os
import json
import pandas as pd

# Nettoyage de l'environnement pour éviter UnicodeDecodeError sur Windows
for k, v in list(os.environ.items()):
    if any(ord(c) > 127 for c in v):
        del os.environ[k]

import psycopg2
from psycopg2.extras import RealDictCursor

def analyze():
    # Connexion DB
    try:
        conn = psycopg2.connect(
            dbname='trading_db',
            user='postgres',
            password='postgres',
            host='localhost',
            port='5432'
        )
    except Exception as e:
        print(f"Erreur connexion DB: {e}")
        return

    # IDs avec gros écarts (vus dans le rapport précédent)
    ids = [
        'c23648d8-4b7d-44f0-bc9d-7658d762de59', # Ratio 0.64
        '2e73162d-03c2-4aed-8848-f113991f1afd', # Ratio 0.65
        'dcf71fe7-fccd-42f4-89c1-84dd87fe895e'  # Ratio 0.50
    ]

    query = """
    SELECT id, symbol, direction, size_usdt, pnl_usdt, net_pnl_usdt, entry_price, exit_price, position_size_contracts, leverage_used
    FROM trades 
    WHERE id = ANY(%s)
    """

    print("--- Données en Base (DB) ---")
    db_rows = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (ids,))
        db_rows = cur.fetchall()
        for r in db_rows:
            print(json.dumps(r, default=str))
    conn.close()

    # Charger le cache des specs
    cache_path = 'data/contract_specs_cache.json'
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            specs = data.get('specs', {})
        print("\n--- Specs Contrats (Cache) ---")
        for r in db_rows:
            symbol = r['symbol']
            spec = specs.get(symbol, {})
            c_size = spec.get('contract_size')
            print(f"{symbol}: contract_size={c_size}")

if __name__ == '__main__':
    analyze()

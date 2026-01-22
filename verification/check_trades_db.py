
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus

def query_db():
    # Nettoyage environnement pour Windows
    for k, v in list(os.environ.items()):
        if any(ord(c) > 127 for c in v):
            del os.environ[k]

    password = quote_plus('@Cmtr1di12345')
    dbname = 'trade_cursor_ml'
    user = 'postgres'
    host = 'localhost'
    port = '5432'
    
    try:
        conn = psycopg2.connect(f'postgresql://{user}:{password}@{host}:{port}/{dbname}')
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("--- Recherche des trades récents pour ADA et HBAR ---")
        query = """
        SELECT id, symbol, direction, timestamp_entry, timestamp_exit, size_usdt, pnl_usdt, position_size_contracts, partial_tp_executed
        FROM trades 
        WHERE symbol LIKE 'ADA%' OR symbol LIKE 'HBAR%'
        ORDER BY timestamp_exit DESC 
        LIMIT 20
        """
        cur.execute(query)
        rows = cur.fetchall()
        for r in rows:
            print(json.dumps(r, default=str))
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"ERREUR DB: {e}")

if __name__ == '__main__':
    query_db()

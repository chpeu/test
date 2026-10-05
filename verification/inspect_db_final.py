
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus

def check_db():
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
        
        # 1. Lister les colonnes
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'trades'")
        cols = [r['column_name'] for r in cur.fetchall()]
        print("COLUMNS:", cols)
        
        # 2. Vérifier le trade ADA
        trade_id = 'c23648d8-4b7d-44f0-bc9d-7658d762de59'
        cur.execute("SELECT * FROM trades WHERE id = %s", (trade_id,))
        row = cur.fetchone()
        if row:
            print("\nTRADE ADA DETAILS:")
            for k, v in row.items():
                if v is not None and 'entry' not in k and 'exit' not in k and 'indicators' not in k:
                    print(f"  {k}: {v}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"ERREUR DB: {e}")

if __name__ == '__main__':
    check_db()

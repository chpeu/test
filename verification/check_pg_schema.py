
import os
import json
import psycopg2
from urllib.parse import quote_plus

def check_schema():
    # Nettoyage environnement pour Windows (évite UnicodeDecodeError)
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
        cur = conn.cursor()
        
        print("--- Colonnes de la table trades ---")
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'trades' 
            ORDER BY column_name
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"{r[0]:30} {r[1]}")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"ERREUR DB: {e}")

if __name__ == '__main__':
    check_schema()

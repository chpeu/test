import os
import psycopg2
from dotenv import load_dotenv

def verify_columns():
    load_dotenv()
    
    conn_str = os.getenv('POSTGRES_URL') or (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'trade_cursor_ml')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASSWORD', '')}"
    )

    tables_to_check = ['market_regime_history', 'opportunities', 'scan_logs', 'trade_atr_metrics', 'trades', 'scan_errors']

    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        
        print("--- État actuel des colonnes VARCHAR ---")
        for table in tables_to_check:
            cur.execute(f"""
                SELECT column_name, data_type, character_maximum_length 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = '{table}' 
                AND data_type = 'character varying'
                ORDER BY column_name;
            """)
            rows = cur.fetchall()
            for col, dtype, length in rows:
                print(f"{table}.{col}: {dtype}({length})")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    verify_columns()

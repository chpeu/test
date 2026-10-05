import os
import psycopg2
from dotenv import load_dotenv

def check_dependencies():
    load_dotenv()
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    try:
        conn = psycopg2.connect(**pg_config)
        cursor = conn.cursor()
        
        print("--- Existing Views ---")
        cursor.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'public';")
        views = cursor.fetchall()
        for v in views:
            print(f"View: {v[0]}")
            
        print("\n--- Dependencies on scan_logs.symbol ---")
        # This is a bit complex in PG, but we can check columns of views
        cursor.execute("""
            SELECT table_name, column_name 
            FROM information_schema.view_column_usage 
            WHERE view_schema = 'public' 
            AND table_name = 'scan_logs' 
            AND column_name = 'symbol';
        """)
        deps = cursor.fetchall()
        for d in deps:
            print(f"View '{d[0]}' depends on scan_logs.symbol")

        print("\n--- Dependencies on trades.symbol ---")
        cursor.execute("""
            SELECT table_name, column_name 
            FROM information_schema.view_column_usage 
            WHERE view_schema = 'public' 
            AND table_name = 'trades' 
            AND column_name = 'symbol';
        """)
        deps = cursor.fetchall()
        for d in deps:
            print(f"View '{d[0]}' depends on trades.symbol")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_dependencies()

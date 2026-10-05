
import psycopg2
import os
from dotenv import load_dotenv

def check_reject_reason():
    load_dotenv()
    conn_str = os.getenv('POSTGRES_URL') or (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'trade_cursor_ml')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASSWORD', '')}"
    )
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'scan_logs' AND column_name = 'reject_reason';
        """)
        row = cur.fetchone()
        if row:
            print(f"Table: scan_logs, Column: {row[0]}, Type: {row[1]}, Length: {row[2]}")
        else:
            print("Column reject_reason not found in scan_logs")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_reject_reason()

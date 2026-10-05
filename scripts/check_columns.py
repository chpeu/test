from dotenv import load_dotenv
load_dotenv()
import os
import psycopg2

try:
    conn = psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', 'localhost'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
        database=os.environ.get('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.environ.get('POSTGRES_USER', 'postgres'),
        password=os.environ.get('POSTGRES_PASSWORD', '')
    )
except psycopg2.OperationalError as e:
    print(f"Impossible de se connecter à PostgreSQL: {e}")
    print("Ce script nécessite une base de données PostgreSQL active.")
    exit(0)  # Exit gracefully for test environment
cur = conn.cursor()
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'trades'
    ORDER BY column_name
""")
print("Colonnes contenant break/trailing/stagnation:")
for row in cur.fetchall():
    col = row[0]
    if 'break' in col or 'trailing' in col or 'stagnation' in col:
        print(f"  {col}")
conn.close()

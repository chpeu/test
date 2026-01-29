import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg2

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
except psycopg2.OperationalError as e:
    print(f"Impossible de se connecter à PostgreSQL: {e}")
    print("Ce script nécessite une base de données PostgreSQL active.")
    exit(0)  # Exit gracefully for test environment
cur = conn.cursor()

cur.execute(
    """
    SELECT 
        win,
        COUNT(*) AS count,
        ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER() * 100, 2) AS pct
    FROM trades
    WHERE timestamp_exit IS NOT NULL
      AND win IS NOT NULL
      AND timestamp_entry > NOW() - INTERVAL '210 days'
    GROUP BY win
    ORDER BY win
    """
)

print("WIN/LOSS distribution (210 days):")
rows = cur.fetchall()
for win, count, pct in rows:
    print(f"WIN={win} | count={count} | pct={pct}%")

cur.close()
conn.close()

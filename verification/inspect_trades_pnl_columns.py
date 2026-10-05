"""\
Inspecter les colonnes PnL/size dans la table trades (PostgreSQL)
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*70)
print("🔎 Colonnes PnL/Size dans trades")
print("="*70)

cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'trades'
      AND (
        column_name ILIKE '%pnl%'
        OR column_name ILIKE '%fee%'
        OR column_name ILIKE '%size%'
        OR column_name ILIKE '%cost%'
      )
    ORDER BY column_name
""")
rows = cur.fetchall()

for r in rows:
    print(f"{r['column_name']:<30} {r['data_type']}")

cur.close()
conn.close()
print("="*70)

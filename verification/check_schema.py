import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / 'data' / 'analytics.db'
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("Schema de la table trades:")
print("-" * 80)
cursor.execute("PRAGMA table_info(trades)")
for row in cursor.fetchall():
    print(f"{row[1]:30} {row[2]:15} nullable={row[3]==0}")

conn.close()

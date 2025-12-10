#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('data/analytics.db')
cur = conn.cursor()

cur.execute("PRAGMA table_info(trades)")
cols = cur.fetchall()

print(f"Colonnes dans la table trades: {len(cols)}")
print("\nListe des colonnes:")
for i, (cid, name, ctype, notnull, dflt, pk) in enumerate(cols, 1):
    print(f"{i:3}. {name:40} {ctype}")

conn.close()

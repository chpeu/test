#!/usr/bin/env python3
"""Script simple pour verifier les colonnes ATR"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', 'localhost'),
    port=int(os.getenv('POSTGRES_PORT', '5432')),
    database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    user=os.getenv('POSTGRES_USER', 'postgres'),
    password=os.getenv('POSTGRES_PASSWORD', '')
)
cur = conn.cursor()

print("=" * 60)
print("COLONNES trade_atr_metrics")
print("=" * 60)

cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'trade_atr_metrics' 
    ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
for c in cols:
    marker = "[ATR]" if "atr" in c.lower() else ""
    print(f"  {c} {marker}")

print(f"\nTotal: {len(cols)} colonnes")

# Verifier si entry_atr_pct_used existe
has_pct_used = 'entry_atr_pct_used' in cols
has_blended = 'entry_atr_blended' in cols

print("\n" + "=" * 60)
print("STATUT COLONNES CRITIQUES")
print("=" * 60)
print(f"  entry_atr_pct_used: {'OK' if has_pct_used else 'MANQUANTE - MIGRATION REQUISE'}")
print(f"  entry_atr_blended:  {'OK' if has_blended else 'MANQUANTE - MIGRATION REQUISE'}")

if not has_pct_used or not has_blended:
    print("\n>>> MIGRATION A EXECUTER:")
    print("    psql -f database/migrations/add_entry_atr_columns.sql")

cur.close()
conn.close()

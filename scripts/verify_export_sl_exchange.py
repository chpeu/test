#!/usr/bin/env python3
"""
TEST EXPORT SL EXCHANGE
=======================
Test de l'export Excel pour vérifier la présence de la colonne entry_sl_exchange_percent
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

def get_conn():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

def main():
    print("=" * 60)
    print("  TEST EXPORT SL EXCHANGE")
    print("=" * 60)
    
    try:
        conn = get_conn()
        print("✅ Connexion PostgreSQL réussie")
        
        # Vérifier la structure de la table trades
        query = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trades'
        """
        
        df_cols = pd.read_sql(query, conn)
        cols = df_cols['column_name'].tolist()
        
        target_col = 'entry_sl_exchange_percent'
        
        if target_col in cols:
            print(f"✅ Colonne '{target_col}' PRÉSENTE dans PostgreSQL")
        else:
            print(f"❌ Colonne '{target_col}' MANQUANTE dans PostgreSQL")
            
        # Vérifier export via SELECT *
        query_data = "SELECT * FROM trades LIMIT 1"
        df_data = pd.read_sql(query_data, conn)
        
        if target_col in df_data.columns:
            print(f"✅ Colonne '{target_col}' INCLUSE dans SELECT * (sera exportée)")
        else:
            print(f"❌ Colonne '{target_col}' NON INCLUSE dans SELECT *")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    main()

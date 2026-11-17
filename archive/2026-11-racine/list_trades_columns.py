#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liste les colonnes de configuration dans la table trades
"""
import psycopg2

def list_config_columns():
    """Lister toutes les colonnes de la table trades"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    cursor = conn.cursor()
    
    # Lister toutes les colonnes de la table trades
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'trades' AND table_schema = 'public'
        ORDER BY ordinal_position
    """)
    
    print("Colonnes de la table 'trades':")
    print("=" * 80)
    
    config_columns = []
    for row in cursor.fetchall():
        col_name, data_type, is_nullable = row
        if 'config_' in col_name:
            config_columns.append((col_name, data_type, is_nullable))
            print(f"  {col_name:40s} {data_type:15s} nullable: {is_nullable}")
    
    print(f"\nTotal colonnes 'config_': {len(config_columns)}")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        list_config_columns()
    except Exception as e:
        print(f"Erreur: {e}")

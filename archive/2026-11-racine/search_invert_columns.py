#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rechercher config_invert_signals dans toutes les tables et vues
"""
import psycopg2

def search_everywhere():
    """Rechercher la colonne dans tout le schéma public"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    cursor = conn.cursor()
    
    # Rechercher dans toutes les tables et vues
    cursor.execute("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns 
        WHERE column_name ILIKE '%invert%'
        ORDER BY table_name, column_name
    """)
    
    results = cursor.fetchall()
    
    if results:
        print(f"🔍 Colonnes avec 'invert' trouvées ({len(results)}):")
        for table, col, dtype in results:
            print(f"   - {table}.{col} ({dtype})")
    else:
        print("❌ Aucune colonne avec 'invert' trouvée")
    
    # Lister toutes les tables contenant 'config'
    cursor.execute("""
        SELECT DISTINCT table_name
        FROM information_schema.columns 
        WHERE column_name LIKE 'config_%'
        ORDER BY table_name
    """)
    
    tables = cursor.fetchall()
    print(f"\n📋 Tables avec des colonnes 'config_' ({len(tables)}):")
    for table, in tables:
        print(f"   - {table}")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        search_everywhere()
    except Exception as e:
        print(f"Erreur: {e}")

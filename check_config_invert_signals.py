#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification spécifique de la colonne config_invert_signals
"""
import psycopg2

def check_config_invert_signals():
    """Vérifier si config_invert_signals existe et son contenu"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    cursor = conn.cursor()
    
    # Vérifier si la colonne existe
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'trades' 
        AND column_name = 'config_invert_signals'
    """)
    
    result = cursor.fetchone()
    
    if result:
        col_name, data_type = result
        print(f"✅ Colonne trouvée: {col_name} (type: {data_type})")
        
        # Vérifier les valeurs dans cette colonne
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(config_invert_signals) as filled,
                COUNT(*) - COUNT(config_invert_signals) as nulls,
                ROUND((COUNT(*) - COUNT(config_invert_signals)) * 100.0 / COUNT(*), 2) as null_pct
            FROM trades 
            WHERE timestamp_entry >= NOW() - INTERVAL '6 hours'
        """)
        
        total, filled, nulls, null_pct = cursor.fetchone()
        print(f"\n📊 Stats sur 6 derniers heures:")
        print(f"   Total: {total}")
        print(f"   Remplis: {filled}")
        print(f"   NULL: {nulls} ({null_pct}%)")
        
        # Voir quelques valeurs exemples
        cursor.execute("""
            SELECT config_invert_signals 
            FROM trades 
            WHERE config_invert_signals IS NOT NULL
            AND timestamp_entry >= NOW() - INTERVAL '6 hours'
            LIMIT 5
        """)
        
        values = cursor.fetchall()
        if values:
            print(f"\n📋 Valeurs exemples:")
            for val in values:
                print(f"   {val[0]}")
    else:
        print("❌ Colonne config_invert_signals NON trouvée dans la table trades")
        
        # Chercher dans toutes les tables
        cursor.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns 
            WHERE column_name = 'config_invert_signals'
        """)
        
        results = cursor.fetchall()
        if results:
            print(f"\n🔍 Colonne trouvée dans {len(results)} table(s):")
            for table, col, dtype in results:
                print(f"   - {table}.{col} ({dtype})")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        check_config_invert_signals()
    except Exception as e:
        print(f"Erreur: {e}")

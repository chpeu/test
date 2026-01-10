#!/usr/bin/env python3
"""
Vérifier le schéma réel de la table trades PostgreSQL
"""

import os
import psycopg2
from dotenv import load_dotenv

def check_trades_schema():
    load_dotenv()
    
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    try:
        conn = psycopg2.connect(**pg_config)
        cursor = conn.cursor()
        
        # Obtenir les colonnes de la table trades
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'trades'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        
        print(f"📋 Schéma de la table 'trades' ({len(columns)} colonnes):\n")
        
        # Colonnes principales/identifiantes
        key_columns = []
        antigiveback_columns = []
        other_columns = []
        
        for col_name, data_type, nullable, default in columns:
            col_info = f"{col_name:35} {data_type:20} {'NULL' if nullable == 'YES' else 'NOT NULL':8} {default or '':15}"
            
            if col_name in ['id', 'symbol', 'direction', 'entry', 'exit', 'created_at']:
                key_columns.append((col_name, data_type, nullable, default))
                print(f"🔑 {col_info}")
            elif 'trailing_mfe' in col_name or 'partial_tp_be' in col_name:
                antigiveback_columns.append((col_name, data_type, nullable, default))
                print(f"🛡️ {col_info}")
            else:
                other_columns.append((col_name, data_type, nullable, default))
        
        print(f"\n📊 Résumé:")
        print(f"  - Colonnes clés: {len(key_columns)}")
        print(f"  - Colonnes anti-giveback: {len(antigiveback_columns)}")
        print(f"  - Autres colonnes: {len(other_columns)}")
        
        # Afficher les colonnes anti-giveback spécifiquement
        if antigiveback_columns:
            print(f"\n🛡️ Colonnes anti-giveback détaillées:")
            for col_name, data_type, nullable, default in antigiveback_columns:
                print(f"  - {col_name:35} ({data_type})")
        
        # Trouver la clé primaire ou colonne d'identifiant
        cursor.execute("""
            SELECT column_name
            FROM information_schema.key_column_usage
            WHERE table_name = 'trades' AND constraint_name LIKE '%pkey%';
        """)
        
        pk_columns = cursor.fetchall()
        if pk_columns:
            print(f"\n🔐 Clé primaire: {[row[0] for row in pk_columns]}")
        else:
            print(f"\n⚠️ Aucune clé primaire trouvée")
        
        cursor.close()
        conn.close()
        
        return key_columns, antigiveback_columns
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return [], []

if __name__ == "__main__":
    key_cols, ag_cols = check_trades_schema()
    
    if ag_cols:
        print(f"\n✅ {len(ag_cols)} colonnes anti-giveback trouvées dans le schéma")
    else:
        print(f"\n❌ Aucune colonne anti-giveback trouvée")

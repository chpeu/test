#!/usr/bin/env python3
"""
Script pour vérifier l'état de la migration anti-giveback dans PostgreSQL
"""

import os
import psycopg2
from dotenv import load_dotenv

def check_migration_status():
    # Charger les variables d'environnement
    load_dotenv()
    
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    print(f"Vérification de l'état des colonnes anti-giveback dans: {pg_config['database']}")
    
    # Colonnes attendues
    expected_columns = [
        'config_trailing_mfe_enabled',
        'config_trailing_mfe_trigger_pct', 
        'config_trailing_mfe_lock_in_pct',
        'config_partial_tp_be_lock_in_pct',
        'trailing_mfe_triggered',
        'trailing_mfe_triggered_at',
        'trailing_mfe_trigger_pnl_pct',
        'trailing_mfe_trigger_price',
        'trailing_mfe_new_sl'
    ]
    
    try:
        conn = psycopg2.connect(**pg_config)
        cursor = conn.cursor()
        
        # Vérifier quelles colonnes existent déjà
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'trades' 
            AND column_name IN %s
            ORDER BY column_name;
        """, (tuple(expected_columns),))
        
        existing_columns = cursor.fetchall()
        existing_names = [col[0] for col in existing_columns]
        
        print(f"\n✅ Colonnes existantes ({len(existing_columns)}/{len(expected_columns)}):")
        for col_name, col_type, nullable in existing_columns:
            print(f"  - {col_name} ({col_type}, nullable: {nullable})")
        
        missing_columns = [col for col in expected_columns if col not in existing_names]
        if missing_columns:
            print(f"\n❌ Colonnes manquantes ({len(missing_columns)}):")
            for col in missing_columns:
                print(f"  - {col}")
        
        # Vérifier les index liés
        cursor.execute("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'trades' 
            AND (indexname LIKE '%trailing_mfe%' OR indexname LIKE '%partial_tp%')
            ORDER BY indexname;
        """)
        
        indexes = cursor.fetchall()
        if indexes:
            print(f"\n🔍 Index anti-giveback trouvés ({len(indexes)}):")
            for idx_name, idx_def in indexes:
                print(f"  - {idx_name}")
        
        cursor.close()
        conn.close()
        
        return existing_names, missing_columns
        
    except psycopg2.Error as e:
        print(f"❌ Erreur PostgreSQL: {e}")
        return [], expected_columns

if __name__ == "__main__":
    existing, missing = check_migration_status()
    
    if not missing:
        print(f"\n🎉 Migration complète! Toutes les colonnes anti-giveback sont présentes.")
    else:
        print(f"\n⚠️ Migration partielle. {len(missing)} colonnes manquantes sur {len(existing) + len(missing)}.")

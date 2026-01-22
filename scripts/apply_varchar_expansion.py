#!/usr/bin/env python3
"""
Script pour appliquer la migration d'expansion des colonnes VARCHAR(30) vers VARCHAR(100).
Ceci corrige l'erreur "valeur trop longue pour le type character varying(30)".
"""

import os
import psycopg2
from dotenv import load_dotenv

def apply_migration():
    # Charger les variables d'environnement
    load_dotenv()
    
    # Paramètres de connexion PostgreSQL depuis .env
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    print(f"Connexion à PostgreSQL: {pg_config['user']}@{pg_config['host']}:{pg_config['port']}/{pg_config['database']}")
    
    conn = None
    try:
        # Connexion à PostgreSQL
        conn = psycopg2.connect(**pg_config)
        conn.autocommit = False  # Transaction manuelle
        cursor = conn.cursor()
        
        # Lire le fichier de migration
        migration_file = 'database/migrations/expand_varchar_size.sql'
        print(f"Lecture du fichier de migration: {migration_file}")
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Diviser en statements individuels (séparés par ';')
        statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
        
        print(f"Exécution de {len(statements)} statements SQL...")
        
        # Exécuter chaque statement
        for i, statement in enumerate(statements, 1):
            if statement and len(statement) > 5:
                print(f"  [{i}/{len(statements)}] Exécution...")
                cursor.execute(statement)
                print(f"  [{i}/{len(statements)}] ✓ OK")
        
        # Commit transaction
        conn.commit()
        print("\n🎉 Migration appliquée avec succès!")
        
        # Vérification
        print("\n🔍 Vérification des nouvelles tailles de colonnes:")
        tables_to_check = ['scan_logs', 'opportunities', 'trades', 'scan_errors']
        for table in tables_to_check:
            cursor.execute(f"""
                SELECT column_name, character_maximum_length 
                FROM information_schema.columns 
                WHERE table_name = '{table}' AND column_name IN ('symbol', 'exit_reason');
            """)
            results = cursor.fetchall()
            for col_name, length in results:
                print(f"  - {table}.{col_name}: {length} chars")
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Erreur PostgreSQL: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False
    
    return True

if __name__ == "__main__":
    success = apply_migration()
    if success:
        print("\n✅ Expansion des colonnes terminée!")
    else:
        print("\n💥 Échec de la migration.")
        exit(1)

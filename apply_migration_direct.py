#!/usr/bin/env python3
"""
Script pour appliquer directement la migration add_antigiveback_trailing_mfe_columns.sql
en utilisant les mêmes paramètres de connexion que le bot.
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
    
    try:
        # Connexion à PostgreSQL
        conn = psycopg2.connect(**pg_config)
        conn.autocommit = False  # Transaction manuelle pour rollback en cas d'erreur
        cursor = conn.cursor()
        
        # Lire le fichier de migration
        migration_file = 'database/migrations/add_antigiveback_trailing_mfe_columns.sql'
        print(f"Lecture du fichier de migration: {migration_file}")
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Diviser en statements individuels (séparés par ';')
        statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
        
        print(f"Exécution de {len(statements)} statements SQL...")
        
        # Exécuter chaque statement
        for i, statement in enumerate(statements, 1):
            if statement and len(statement) > 5:  # Ignorer statements trop courts ou vides
                print(f"  [{i}/{len(statements)}] Exécution en cours...")
                cursor.execute(statement)
                print(f"  [{i}/{len(statements)}] ✓ OK")
        
        # Commit transaction
        conn.commit()
        print("\n🎉 Migration appliquée avec succès!")
        
        # Vérification: lister les nouvelles colonnes ajoutées
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'trades' 
            AND column_name LIKE '%trailing_mfe%' OR column_name LIKE '%partial_tp_be%'
            ORDER BY column_name;
        """)
        
        new_columns = cursor.fetchall()
        if new_columns:
            print(f"\n✅ Nouvelles colonnes ajoutées à la table 'trades':")
            for col_name, col_type in new_columns:
                print(f"  - {col_name} ({col_type})")
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Erreur PostgreSQL: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False
    except FileNotFoundError:
        print(f"❌ Fichier de migration non trouvé: {migration_file}")
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
        print("\n🔧 Migration terminée. Les nouvelles colonnes anti-giveback sont prêtes!")
    else:
        print("\n💥 Échec de la migration.")

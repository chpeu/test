#!/usr/bin/env python3
"""
Script robuste pour appliquer la migration anti-giveback statement par statement
avec gestion d'erreurs individuelles et autocommit.
"""

import os
import psycopg2
from dotenv import load_dotenv

def apply_migration_robust():
    # Charger les variables d'environnement
    load_dotenv()
    
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    print(f"Application robuste de la migration sur: {pg_config['database']}")
    
    try:
        # Connexion avec autocommit pour éviter les rollbacks
        conn = psycopg2.connect(**pg_config)
        conn.autocommit = True  # Chaque statement est committé immédiatement
        cursor = conn.cursor()
        
        # Lire le fichier de migration
        migration_file = 'database/migrations/add_antigiveback_trailing_mfe_columns.sql'
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Diviser en statements individuels
        statements = []
        for stmt in migration_sql.split(';'):
            stmt = stmt.strip()
            if stmt and not stmt.startswith('--') and len(stmt) > 5:
                statements.append(stmt)
        
        print(f"\nExécution de {len(statements)} statements SQL (mode autocommit)...")
        
        success_count = 0
        error_count = 0
        
        # Exécuter chaque statement individuellement
        for i, statement in enumerate(statements, 1):
            try:
                print(f"  [{i:2d}/{len(statements)}] ", end="", flush=True)
                cursor.execute(statement)
                print(f"✅ OK")
                success_count += 1
                
            except psycopg2.Error as e:
                error_msg = str(e).strip()
                if 'already exists' in error_msg or 'existe déjà' in error_msg:
                    print(f"⚠️ Déjà existant (ignoré)")
                elif 'IF NOT EXISTS' in statement and ('relation' in error_msg or 'column' in error_msg):
                    print(f"⚠️ IF NOT EXISTS ignoré")
                else:
                    print(f"❌ ERREUR: {error_msg}")
                    error_count += 1
        
        print(f"\n📊 Résultat: {success_count} succès, {error_count} erreurs")
        
        # Vérification finale
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trades' 
            AND (column_name LIKE '%trailing_mfe%' OR column_name LIKE '%partial_tp_be%')
            ORDER BY column_name;
        """)
        
        final_columns = cursor.fetchall()
        print(f"\n✅ Colonnes anti-giveback trouvées ({len(final_columns)}):")
        for (col_name,) in final_columns:
            print(f"  - {col_name}")
        
        cursor.close()
        conn.close()
        
        return len(final_columns) >= 8  # Au moins 8 colonnes attendues
        
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        return False

if __name__ == "__main__":
    success = apply_migration_robust()
    if success:
        print("\n🎉 Migration anti-giveback appliquée avec succès!")
    else:
        print("\n💥 Échec de la migration.")

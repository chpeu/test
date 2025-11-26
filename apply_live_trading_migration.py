#!/usr/bin/env python3
"""
Script pour appliquer la migration des colonnes LIVE TRADING a PostgreSQL
Usage: python apply_live_trading_migration.py
"""

import os
import sys

def apply_migration():
    """Appliquer la migration SQL pour ajouter les colonnes live trading"""
    
    # Lire le fichier de migration
    migration_file = os.path.join(
        os.path.dirname(__file__), 
        'database', 'migrations', 'add_live_trading_columns.sql'
    )
    
    if not os.path.exists(migration_file):
        print(f"[ERREUR] Fichier de migration non trouve: {migration_file}")
        return False
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()
    
    print(f"[INFO] Migration chargee: {len(migration_sql)} caracteres")
    
    # Essayer de se connecter a PostgreSQL
    try:
        import psycopg2
    except ImportError:
        print("[ERREUR] psycopg2 non installe. Installez-le avec: pip install psycopg2-binary")
        return False
    
    # Configuration de connexion
    pg_config = {
        'host': os.getenv('PG_HOST', 'localhost'),
        'port': int(os.getenv('PG_PORT', 5432)),
        'database': os.getenv('PG_DATABASE', 'tradecursor'),
        'user': os.getenv('PG_USER', 'postgres'),
        'password': os.getenv('PG_PASSWORD', ''),
    }
    
    print(f"[INFO] Connexion a PostgreSQL: {pg_config['host']}:{pg_config['port']}/{pg_config['database']}")
    
    try:
        conn = psycopg2.connect(**pg_config)
        cursor = conn.cursor()
        
        print("[OK] Connexion etablie")
        
        # Executer la migration
        print("[INFO] Application de la migration...")
        cursor.execute(migration_sql)
        conn.commit()
        
        print("[OK] Migration appliquee avec succes!")
        
        # Verifier les nouvelles colonnes
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trades' 
            AND (column_name LIKE 'is_live%%' OR column_name LIKE 'leverage%%' OR column_name LIKE 'entry_order%%')
            ORDER BY column_name
        """)
        new_columns = cursor.fetchall()
        
        if new_columns:
            print(f"\n[INFO] Nouvelles colonnes live trading detectees ({len(new_columns)}):")
            for col in new_columns[:10]:  # Afficher les 10 premieres
                print(f"   - {col[0]}")
            if len(new_columns) > 10:
                print(f"   ... et {len(new_columns) - 10} autres")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.OperationalError as e:
        print(f"[ERREUR] Erreur de connexion PostgreSQL: {e}")
        print("\n[INFO] Verifiez vos variables d'environnement:")
        print("   PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD")
        return False
    except Exception as e:
        print(f"[ERREUR] {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("MIGRATION: Colonnes LIVE TRADING pour table trades")
    print("=" * 60)
    
    success = apply_migration()
    
    print("=" * 60)
    if success:
        print("[OK] Migration terminee avec succes")
    else:
        print("[ERREUR] Migration echouee")
        print("\n[INFO] Pour appliquer manuellement:")
        print("   psql -U postgres -d tradecursor -f database/migrations/add_live_trading_columns.sql")
    print("=" * 60)
    
    sys.exit(0 if success else 1)

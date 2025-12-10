#!/usr/bin/env python3
"""
Script pour exécuter la migration des colonnes Order Flow
"""

import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

def run_migration():
    """Exécute la migration SQL pour les colonnes order flow"""
    try:
        import psycopg2
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Connexion à PostgreSQL
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cursor = conn.cursor()
        
        print("[INFO] Exécution de la migration Order Flow...")
        
        # Lire le fichier SQL
        migration_file = Path(__file__).parent / "database" / "migrations" / "add_orderflow_columns.sql"
        
        if not migration_file.exists():
            print(f"❌ Fichier migration non trouvé: {migration_file}")
            return False
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        # Exécuter les commandes SQL (une par une pour les erreurs)
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        for stmt in statements:
            if stmt.strip():
                try:
                    cursor.execute(stmt)
                    print(f"[OK] Exécuté: {stmt[:60]}...")
                except Exception as e:
                    print(f"[WARN] Erreur (ignorée): {e}")
        
        conn.commit()
        
        # Vérifier les colonnes ajoutées
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'scan_logs' 
            AND column_name IN ('delta_volume', 'imbalance_normalized', 'spread_volatility_5', 
                               'book_depth_ratio', 'volume_acceleration', 'price_momentum_5')
            ORDER BY column_name
        """)
        
        columns = cursor.fetchall()
        
        print(f"\n[OK] Migration terminée. Colonnes ajoutées:")
        for col_name, col_type in columns:
            print(f"   - {col_name}: {col_type}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except ImportError:
        print("[ERROR] psycopg2 non installé. Installez-le avec: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"[ERROR] Erreur migration: {e}")
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

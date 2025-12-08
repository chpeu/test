#!/usr/bin/env python3
"""
Migration: Ajout des colonnes de paramètres dynamiques du régime
Date: 2025-12-08
"""
import sys
import os
import io

# Force UTF-8 for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2

# Configuration DB
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'dbname': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}

COLUMNS_TO_ADD = [
    # (table, column_name, data_type, comment)
    ('trades', 'entry_volume_multiplier', 'REAL', 'Multiplicateur volume effectif au moment de entrée'),
    ('trades', 'entry_rsi_filter_mode', 'TEXT', 'Mode filtre RSI effectif: STRICT, PERMISSIVE, STANDARD'),
    ('trades', 'entry_position_timeout', 'INTEGER', 'Timeout position en secondes effectif'),
    ('trades', 'entry_optimal_atr_max_1m', 'REAL', 'ATR max 1m autorisé effectif'),
    # Optionnel: scan_logs
    ('scan_logs', 'volume_multiplier', 'REAL', 'Multiplicateur volume pour ce scan'),
    ('scan_logs', 'rsi_filter_mode', 'TEXT', 'Mode filtre RSI pour ce scan'),
]

def add_column_if_not_exists(cursor, table, column, data_type, comment=None):
    """Ajoute une colonne si elle n'existe pas déjà."""
    # Vérifier si la colonne existe
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        )
    """, (table, column))
    exists = cursor.fetchone()[0]
    
    if exists:
        print(f"  ⏭️  {table}.{column} existe déjà")
        return False
    
    # Ajouter la colonne
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {data_type}")
    print(f"  ✅ {table}.{column} ajoutée ({data_type})")
    
    # Ajouter le commentaire si fourni
    if comment:
        cursor.execute(f"COMMENT ON COLUMN {table}.{column} IS %s", (comment,))
    
    return True

def main():
    print("=" * 60)
    print(" MIGRATION: Colonnes paramètres dynamiques du régime")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()
        
        print("\n📊 Ajout des colonnes...")
        added = 0
        
        for table, column, data_type, comment in COLUMNS_TO_ADD:
            try:
                if add_column_if_not_exists(cursor, table, column, data_type, comment):
                    added += 1
            except Exception as e:
                print(f"  ⚠️  Erreur pour {table}.{column}: {e}")
        
        # Commit
        conn.commit()
        
        print(f"\n✅ Migration terminée: {added} colonnes ajoutées")
        
        # Vérification
        print("\n📋 Vérification...")
        for table, column, _, _ in COLUMNS_TO_ADD:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = %s
                )
            """, (table, column))
            exists = cursor.fetchone()[0]
            status = "✅" if exists else "❌"
            print(f"  {status} {table}.{column}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Erreur migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

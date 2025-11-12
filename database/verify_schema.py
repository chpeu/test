#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Python pour vérifier que le schéma PostgreSQL correspond au schéma attendu
"""
import psycopg2
import os
import sys
from dotenv import load_dotenv

# Fix encoding pour Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Charger variables d'environnement
load_dotenv()

# Configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}

# Tables attendues
EXPECTED_TABLES = [
    'trading_sessions',
    'config_snapshots',
    'scan_logs',
    'opportunities',
    'trades',
    'market_context',
    'scan_errors',
    'model_predictions',
    'features_engineered'
]

# Colonnes importantes par table
EXPECTED_COLUMNS = {
    'trading_sessions': ['id', 'start_time', 'end_time', 'config_snapshot'],
    'scan_logs': ['id', 'timestamp', 'session_id', 'symbol', 'scan_duration_ms', 'price', 'score_total', 'is_opportunity'],
    'opportunities': ['id', 'scan_log_id', 'session_id', 'symbol', 'timestamp', 'status', 'direction', 'setup_score'],
    'trades': ['id', 'timestamp_entry', 'timestamp_exit', 'symbol', 'direction', 'entry_price', 'exit_price', 'net_pnl_usdt', 'net_pnl_pct'],
    'market_context': ['id', 'timestamp', 'session_id', 'btc_price', 'eth_price'],
    'scan_errors': ['id', 'timestamp', 'session_id', 'symbol', 'error_type', 'error_message']
}

def check_schema():
    """Vérifier le schéma PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("=" * 70)
        print("🔍 VÉRIFICATION DU SCHÉMA POSTGRESQL")
        print("=" * 70)
        print()
        
        # 1. Vérifier les tables
        print("1️⃣ Vérification des tables...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = set(EXPECTED_TABLES) - set(existing_tables)
        extra_tables = set(existing_tables) - set(EXPECTED_TABLES)
        
        if missing_tables:
            print(f"   ❌ Tables manquantes: {', '.join(missing_tables)}")
        if extra_tables:
            print(f"   ⚠️  Tables supplémentaires: {', '.join(extra_tables)}")
        if not missing_tables and not extra_tables:
            print(f"   ✅ Toutes les tables sont présentes ({len(EXPECTED_TABLES)} tables)")
        print()
        
        # 2. Vérifier les colonnes importantes
        print("2️⃣ Vérification des colonnes importantes...")
        for table_name, expected_cols in EXPECTED_COLUMNS.items():
            if table_name not in existing_tables:
                print(f"   ⚠️  Table '{table_name}' n'existe pas - colonnes non vérifiées")
                continue
            
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns
                WHERE table_schema = 'public' 
                    AND table_name = %s
            """, (table_name,))
            existing_cols = [row[0] for row in cursor.fetchall()]
            
            missing_cols = set(expected_cols) - set(existing_cols)
            if missing_cols:
                print(f"   ❌ Table '{table_name}' - colonnes manquantes: {', '.join(missing_cols)}")
            else:
                print(f"   ✅ Table '{table_name}' - toutes les colonnes importantes présentes")
        print()
        
        # 3. Vérifier l'extension UUID
        print("3️⃣ Vérification des extensions...")
        cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'uuid-ossp'")
        if cursor.fetchone():
            print("   ✅ Extension 'uuid-ossp' installée")
        else:
            print("   ❌ Extension 'uuid-ossp' manquante")
        print()
        
        # 4. Vérifier les index
        print("4️⃣ Vérification des index...")
        cursor.execute("""
            SELECT tablename, COUNT(*) as index_count
            FROM pg_indexes
            WHERE schemaname = 'public'
                AND tablename IN %s
            GROUP BY tablename
            ORDER BY tablename
        """, (tuple(EXPECTED_TABLES),))
        indexes = cursor.fetchall()
        
        for table_name, count in indexes:
            print(f"   ✅ Table '{table_name}': {count} index(es)")
        print()
        
        # 5. Vérifier les Foreign Keys
        print("5️⃣ Vérification des Foreign Keys...")
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.table_constraints
            WHERE constraint_type = 'FOREIGN KEY'
                AND table_schema = 'public'
                AND table_name IN %s
        """, (tuple(EXPECTED_TABLES),))
        fk_count = cursor.fetchone()[0]
        print(f"   ✅ {fk_count} Foreign Key(s) trouvé(s)")
        print()
        
        # 6. Statistiques des tables
        print("6️⃣ Statistiques des tables...")
        for table_name in EXPECTED_TABLES:
            if table_name not in existing_tables:
                continue
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"   📊 Table '{table_name}': {count} ligne(s)")
            except Exception as e:
                print(f"   ⚠️  Table '{table_name}': erreur - {e}")
        print()
        
        # 7. Vérifier colonnes timestamp_entry/timestamp_exit pour trades
        print("7️⃣ Vérification spécifique table 'trades'...")
        if 'trades' in existing_tables:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns
                WHERE table_schema = 'public' 
                    AND table_name = 'trades'
                    AND column_name IN ('timestamp', 'timestamp_entry', 'timestamp_exit')
            """)
            trade_timestamp_cols = [row[0] for row in cursor.fetchall()]
            
            if 'timestamp_entry' in trade_timestamp_cols and 'timestamp_exit' in trade_timestamp_cols:
                print("   ✅ Colonnes 'timestamp_entry' et 'timestamp_exit' présentes")
            elif 'timestamp' in trade_timestamp_cols:
                print("   ⚠️  Table 'trades' utilise 'timestamp' au lieu de 'timestamp_entry'/'timestamp_exit'")
            else:
                print("   ❌ Colonnes timestamp manquantes dans 'trades'")
        print()
        
        print("=" * 70)
        print("✅ Vérification terminée")
        print("=" * 70)
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Erreur PostgreSQL: {e}")
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == '__main__':
    check_schema()


#!/usr/bin/env python3
"""
Diagnostic post-exit DB - Vérifie si les tables existent et le type de trade_id
"""
import sys
import os

# Fix encoding Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2

def main():
    print("=" * 60)
    print("🔍 Diagnostic Post-Exit Database")
    print("=" * 60)
    
    # Connexion
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        print("✅ Connexion PostgreSQL OK")
    except Exception as e:
        print(f"❌ Connexion échouée: {e}")
        return
    
    try:
        with conn.cursor() as cur:
            # 1. Vérifier si table trade_post_exit_analysis existe
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'trade_post_exit_analysis'
                )
            """)
            table_exists = cur.fetchone()[0]
            print(f"\n📋 Table trade_post_exit_analysis existe: {table_exists}")
            
            # 2. Vérifier si table trade_post_exit_samples existe
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'trade_post_exit_samples'
                )
            """)
            samples_exists = cur.fetchone()[0]
            print(f"📋 Table trade_post_exit_samples existe: {samples_exists}")
            
            # 3. Vérifier le type de trades.id
            cur.execute("""
                SELECT column_name, data_type, udt_name 
                FROM information_schema.columns 
                WHERE table_name = 'trades' AND column_name = 'id'
            """)
            result = cur.fetchone()
            if result:
                print(f"\n🔑 Type de trades.id: {result[1]} ({result[2]})")
            else:
                print("⚠️ Table trades non trouvée!")
            
            # 4. Si la table post_exit existe, vérifier son type trade_id
            if table_exists:
                cur.execute("""
                    SELECT column_name, data_type, udt_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'trade_post_exit_analysis' AND column_name = 'trade_id'
                """)
                result = cur.fetchone()
                if result:
                    print(f"🔑 Type de trade_post_exit_analysis.trade_id: {result[1]} ({result[2]})")
                
                # Compter les rows
                cur.execute("SELECT COUNT(*) FROM trade_post_exit_analysis")
                count = cur.fetchone()[0]
                print(f"📊 Nombre de rows: {count}")
            
            # 5. Vérifier les derniers trades pour voir leur format d'ID
            cur.execute("""
                SELECT id, symbol, created_at 
                FROM trades 
                ORDER BY created_at DESC 
                LIMIT 3
            """)
            trades = cur.fetchall()
            print(f"\n📊 Derniers trades (id, symbol, created_at):")
            for t in trades:
                print(f"   - {t[0]} ({type(t[0]).__name__}) | {t[1]} | {t[2]}")
            
            print("\n" + "=" * 60)
            
            if not table_exists:
                print("⚠️ ACTION REQUISE: Exécuter la migration!")
                print("   psql -d trade_cursor_ml -f database/migrations/add_post_exit_analysis_tables.sql")
                
    except Exception as e:
        print(f"❌ Erreur: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()

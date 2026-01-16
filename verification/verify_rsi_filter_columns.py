"""
Vérification des colonnes RSI Final Filter dans PostgreSQL
Date: 2025-12-09
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

# Ensure Unicode prints don't crash on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load environment
load_dotenv()

def get_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )


def verify_columns():
    """Verify RSI filter columns exist and have data"""
    print("\n" + "=" * 60)
    print("🔍 VÉRIFICATION COLONNES RSI FINAL FILTER")
    print("=" * 60)
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. Check trades table columns exist
        print("\n📊 1. Vérification colonnes trades...")
        cur.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'trades'
            AND column_name IN ('config_rsi_filter_enabled', 'config_rsi_long_max', 'config_rsi_short_min')
            ORDER BY column_name;
        """)
        trades_cols = cur.fetchall()
        
        if len(trades_cols) == 3:
            print("   ✅ Les 3 colonnes existent dans trades:")
            for col in trades_cols:
                print(f"      - {col[0]}: {col[1]} (default: {col[2]})")
        else:
            print(f"   ❌ Colonnes manquantes! Trouvées: {len(trades_cols)}/3")
            print("   → Exécutez la migration: database/migrations/add_rsi_final_filter_columns.sql")
            return False
        
        # 2. Check scan_logs table column exists
        print("\n📊 2. Vérification colonne scan_logs...")
        cur.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'scan_logs'
            AND column_name = 'rsi_filter_blocked';
        """)
        scan_cols = cur.fetchall()
        
        if len(scan_cols) == 1:
            print(f"   ✅ Colonne rsi_filter_blocked existe: {scan_cols[0][1]}")
        else:
            print("   ❌ Colonne rsi_filter_blocked manquante dans scan_logs!")
            return False
        
        # 3. Check fill rate for trades
        print("\n📊 3. Taux de remplissage trades...")
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(config_rsi_filter_enabled) as rsi_enabled_filled,
                COUNT(config_rsi_long_max) as rsi_long_filled,
                COUNT(config_rsi_short_min) as rsi_short_filled,
                ROUND(100.0 * COUNT(config_rsi_filter_enabled) / NULLIF(COUNT(*), 0), 1) as fill_rate
            FROM trades;
        """)
        result = cur.fetchone()
        
        if result:
            print(f"   Total trades: {result[0]}")
            print(f"   config_rsi_filter_enabled rempli: {result[1]} ({result[4]}%)")
            print(f"   config_rsi_long_max rempli: {result[2]}")
            print(f"   config_rsi_short_min rempli: {result[3]}")
        
        # 4. Sample recent trades
        print("\n📊 4. Échantillon derniers trades...")
        cur.execute("""
            SELECT 
                id,
                symbol,
                timestamp_entry,
                config_rsi_filter_enabled,
                config_rsi_long_max,
                config_rsi_short_min
            FROM trades
            ORDER BY timestamp_entry DESC NULLS LAST
            LIMIT 5;
        """)
        samples = cur.fetchall()
        
        if samples:
            for s in samples:
                enabled_str = "✅ ON" if s[3] else "❌ OFF" if s[3] is not None else "NULL"
                print(
                    f"   Trade #{s[0]} {s[1]} @ {s[2]}: RSI Filter {enabled_str} | Long Max: {s[4]} | Short Min: {s[5]}"
                )
        else:
            print("   (Aucun trade trouvé)")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ VÉRIFICATION TERMINÉE - Tout est OK!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        return False


def run_migration():
    """Execute the migration SQL"""
    print("\n🔧 Exécution de la migration...")
    
    migration_file = os.path.join(
        os.path.dirname(__file__), 
        '..', 'database', 'migrations', 'add_rsi_final_filter_columns.sql'
    )
    
    if not os.path.exists(migration_file):
        print(f"❌ Fichier migration non trouvé: {migration_file}")
        return False
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        # Execute migration
        cur.execute(sql)
        conn.commit()
        
        cur.close()
        conn.close()
        
        print("✅ Migration exécutée avec succès!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur migration: {e}")
        return False


if __name__ == "__main__":
    # Check if migration needed
    if not verify_columns():
        print("\n⚠️ Colonnes manquantes - Exécution de la migration...")
        if run_migration():
            # Re-verify
            verify_columns()
    else:
        print("\n✅ Toutes les colonnes sont en place!")

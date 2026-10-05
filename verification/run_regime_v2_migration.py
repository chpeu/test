"""
Execute la migration SQL pour Market Regime V2.
SAFE: Toutes les commandes sont IF NOT EXISTS.

Usage:
    python verification/run_regime_v2_migration.py
"""
import psycopg2
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ajouter le repertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()


def run_migration():
    """Execute la migration SQL"""
    print("=" * 60)
    print("MIGRATION: Market Regime V2")
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
        print("[OK] Connexion PostgreSQL etablie")
    except Exception as e:
        print(f"[ERREUR] Connexion: {e}")
        return False
    
    # Charger et executer la migration
    migration_path = Path(__file__).parent.parent / 'database' / 'migrations' / 'add_regime_context_columns.sql'
    
    if not migration_path.exists():
        print(f"[ERREUR] Fichier migration non trouve: {migration_path}")
        return False
    
    print(f"Migration: {migration_path.name}")
    
    try:
        sql = migration_path.read_text(encoding='utf-8')
        
        with conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()
        
        print("[OK] Migration executee avec succes")
        
    except Exception as e:
        print(f"[ERREUR] Migration: {e}")
        conn.rollback()
        return False
    
    # Verification
    print("\nVerification des nouvelles colonnes:")
    print("-" * 60)
    
    verifications = [
        ("trade_atr_metrics", ["session_market", "hour_utc", "regime_detection_method", "pnl_if_calme_params"]),
        ("market_regime_history", ["detection_method", "atr_median", "hysteresis_applied"]),
        ("scan_logs", ["session_market", "regime_at_scan"]),
    ]
    
    all_ok = True
    with conn.cursor() as cur:
        for table, columns in verifications:
            cur.execute(f"""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = '{table}'
            """)
            existing = {row[0] for row in cur.fetchall()}
            
            for col in columns:
                if col in existing:
                    print(f"  [OK] {table}.{col}")
                else:
                    print(f"  [MANQUANT] {table}.{col}")
                    all_ok = False
    
    # Verifier les vues
    print("\nVerification des vues:")
    views = ["v_performance_by_session", "v_performance_by_regime_session", "v_optimal_regime_analysis", "v_performance_by_hour"]
    
    with conn.cursor() as cur:
        for view in views:
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views 
                    WHERE table_name = '{view}'
                )
            """)
            exists = cur.fetchone()[0]
            status = "[OK]" if exists else "[MANQUANT]"
            print(f"  {status} {view}")
            if not exists:
                all_ok = False
    
    conn.close()
    
    print("\n" + "=" * 60)
    if all_ok:
        print("[OK] MIGRATION COMPLETE - Toutes les verifications OK")
    else:
        print("[ATTENTION] MIGRATION PARTIELLE - Verifier les erreurs ci-dessus")
    print("=" * 60)
    
    return all_ok


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

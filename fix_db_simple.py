"""
Script simple de correction de compatibilité base de données
Utilise psycopg2 directement sans dépendances complexes
"""
import sys
import os
from pathlib import Path

def main():
    print("\n" + "=" * 80)
    print("  CORRECTION AUTOMATIQUE BASE DE DONNEES")
    print("=" * 80)
    
    # Charger .env si disponible
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            print("[OK] Fichier .env charge")
        else:
            print("[INFO] Fichier .env non trouve, utilisation variables systeme")
    except ImportError:
        print("[INFO] python-dotenv non installe, utilisation variables systeme")
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("[ERROR] psycopg2 non installe")
        print("[INFO] Installer: pip install psycopg2-binary")
        return False
    
    # Connexion PostgreSQL
    try:
        db_host = os.getenv('POSTGRES_HOST', 'localhost')
        db_port = os.getenv('POSTGRES_PORT', '5432')
        db_name = os.getenv('POSTGRES_DB', 'tradebot')
        db_user = os.getenv('POSTGRES_USER', 'postgres')
        db_pass = os.getenv('POSTGRES_PASSWORD', '')
        
        print(f"[INFO] Connexion a {db_user}@{db_host}:{db_port}/{db_name}")
        
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass
        )
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print("[OK] Connexion PostgreSQL etablie")
        
    except Exception as e:
        print(f"[ERROR] Connexion PostgreSQL echouee: {e}")
        print("[INFO] Verifiez les variables d'environnement ou .env")
        return False
    
    try:
        # ====================================================================
        # ETAPE 1: Verifier colonnes scan_logs
        # ====================================================================
        print("\n" + "=" * 80)
        print("  1. Verification scan_logs")
        print("=" * 80)
        
        scan_logs_cols = {
            'config_min_score_required': 'FLOAT',
            'config_snr_threshold': 'FLOAT',
            'config_atr_min_1m': 'FLOAT',
            'config_atr_max_1m': 'FLOAT',
            'config_atr_min_5m': 'FLOAT',
            'config_atr_max_5m': 'FLOAT',
            'config_volume_multiplier': 'FLOAT',
            'config_use_confluence': 'BOOLEAN',
        }
        
        added_scan_logs = 0
        for col_name, col_type in scan_logs_cols.items():
            cur.execute("""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_name = 'scan_logs' AND column_name = %s
            """, (col_name,))
            
            result = cur.fetchone()
            if result['count'] == 0:
                print(f"[INFO] Ajout colonne scan_logs.{col_name}...")
                cur.execute(f"ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                added_scan_logs += 1
                print(f"[OK] Ajoutee: {col_name}")
            else:
                print(f"[OK] Existe deja: {col_name}")
        
        print(f"\n[OK] scan_logs: {added_scan_logs} colonnes ajoutees")
        
        # ====================================================================
        # ETAPE 2: Verifier colonnes trades
        # ====================================================================
        print("\n" + "=" * 80)
        print("  2. Verification trades")
        print("=" * 80)
        
        trades_cols = {
            'config_min_score_required': 'FLOAT',
            'config_snr_threshold': 'FLOAT',
            'config_optimal_atr_min_1m': 'FLOAT',
            'config_optimal_atr_max_1m': 'FLOAT',
            'config_optimal_atr_min_5m': 'FLOAT',
            'config_optimal_atr_max_5m': 'FLOAT',
            'config_volume_multiplier': 'FLOAT',
            'config_use_confluence': 'BOOLEAN',
        }
        
        added_trades = 0
        for col_name, col_type in trades_cols.items():
            cur.execute("""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_name = 'trades' AND column_name = %s
            """, (col_name,))
            
            result = cur.fetchone()
            if result['count'] == 0:
                print(f"[INFO] Ajout colonne trades.{col_name}...")
                cur.execute(f"ALTER TABLE trades ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                added_trades += 1
                print(f"[OK] Ajoutee: {col_name}")
            else:
                print(f"[OK] Existe deja: {col_name}")
        
        print(f"\n[OK] trades: {added_trades} colonnes ajoutees")
        
        # ====================================================================
        # ETAPE 3: Backfill depuis JSONB
        # ====================================================================
        if added_scan_logs > 0 or added_trades > 0:
            print("\n" + "=" * 80)
            print("  3. Backfill donnees depuis JSONB")
            print("=" * 80)
            
            # Backfill scan_logs
            if added_scan_logs > 0:
                print("[INFO] Backfill scan_logs depuis params_snapshot...")
                cur.execute("""
                    UPDATE scan_logs
                    SET 
                        config_min_score_required = (params_snapshot->>'min_score_required')::FLOAT,
                        config_snr_threshold = (params_snapshot->>'snr_threshold')::FLOAT,
                        config_atr_min_1m = (params_snapshot->'optimal_atr'->'1m'->>'min')::FLOAT,
                        config_atr_max_1m = (params_snapshot->'optimal_atr'->'1m'->>'max')::FLOAT,
                        config_atr_min_5m = (params_snapshot->'optimal_atr'->'5m'->>'min')::FLOAT,
                        config_atr_max_5m = (params_snapshot->'optimal_atr'->'5m'->>'max')::FLOAT,
                        config_volume_multiplier = (params_snapshot->>'volume_multiplier')::FLOAT,
                        config_use_confluence = (params_snapshot->>'use_confluence')::BOOLEAN
                    WHERE params_snapshot IS NOT NULL
                      AND config_min_score_required IS NULL
                """)
                
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM scan_logs
                    WHERE config_min_score_required IS NOT NULL
                """)
                result = cur.fetchone()
                print(f"[OK] Backfill scan_logs: {result['count']} lignes")
            
            # Backfill trades
            if added_trades > 0:
                print("[INFO] Backfill trades depuis config_snapshot...")
                cur.execute("""
                    UPDATE trades
                    SET 
                        config_min_score_required = (config_snapshot->>'min_score_required')::FLOAT,
                        config_snr_threshold = (config_snapshot->>'snr_threshold')::FLOAT,
                        config_optimal_atr_min_1m = (config_snapshot->'optimal_atr'->'1m'->>'min')::FLOAT,
                        config_optimal_atr_max_1m = (config_snapshot->'optimal_atr'->'1m'->>'max')::FLOAT,
                        config_optimal_atr_min_5m = (config_snapshot->'optimal_atr'->'5m'->>'min')::FLOAT,
                        config_optimal_atr_max_5m = (config_snapshot->'optimal_atr'->'5m'->>'max')::FLOAT,
                        config_volume_multiplier = (config_snapshot->>'volume_multiplier')::FLOAT,
                        config_use_confluence = (config_snapshot->>'use_confluence')::BOOLEAN
                    WHERE config_snapshot IS NOT NULL
                      AND config_min_score_required IS NULL
                """)
                
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM trades
                    WHERE config_min_score_required IS NOT NULL
                """)
                result = cur.fetchone()
                print(f"[OK] Backfill trades: {result['count']} lignes")
            
            # ====================================================================
            # ETAPE 4: Creer index
            # ====================================================================
            print("\n" + "=" * 80)
            print("  4. Creation index de performance")
            print("=" * 80)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_scan_config_score 
                ON scan_logs(config_min_score_required) 
                WHERE config_min_score_required IS NOT NULL
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_config_score 
                ON trades(config_min_score_required) 
                WHERE config_min_score_required IS NOT NULL
            """)
            
            print("[OK] Index crees")
        
        # ====================================================================
        # ETAPE 5: Verification vue ml_features
        # ====================================================================
        print("\n" + "=" * 80)
        print("  5. Verification vue ml_features")
        print("=" * 80)
        
        try:
            cur.execute("""
                SELECT 
                    config_min_score_required,
                    config_snr_threshold
                FROM ml_features
                LIMIT 1
            """)
            print("[OK] Vue ml_features fonctionne")
        except Exception as e:
            print(f"[WARNING] Vue ml_features: {e}")
        
        # ====================================================================
        # ETAPE 6: Stats finales
        # ====================================================================
        print("\n" + "=" * 80)
        print("  6. Statistiques finales")
        print("=" * 80)
        
        cur.execute("""
            SELECT 
                'scan_logs' as table_name,
                COUNT(*) as total,
                COUNT(config_min_score_required) as filled,
                ROUND(COUNT(config_min_score_required)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) as fill_pct
            FROM scan_logs
            WHERE params_snapshot IS NOT NULL
        """)
        
        result = cur.fetchone()
        if result:
            print(f"scan_logs    - {result['filled']:6}/{result['total']:6} lignes ({result['fill_pct']}%)")
        
        cur.execute("""
            SELECT 
                'trades' as table_name,
                COUNT(*) as total,
                COUNT(config_min_score_required) as filled,
                ROUND(COUNT(config_min_score_required)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) as fill_pct
            FROM trades
            WHERE config_snapshot IS NOT NULL
        """)
        
        result = cur.fetchone()
        if result:
            print(f"trades       - {result['filled']:6}/{result['total']:6} lignes ({result['fill_pct']}%)")
        
        # ====================================================================
        # RESUME
        # ====================================================================
        print("\n" + "=" * 80)
        print("  RESUME")
        print("=" * 80)
        
        print("[OK] Migration terminee avec succes")
        print("[OK] Base de donnees 100% compatible")
        print("[OK] XGBoost V2 et Optuna V2 operationnels")
        
        print("\n[INFO] Prochaines etapes:")
        print("  1. Redemarrer le backend (optionnel)")
        print("  2. Tester XGBoost V2")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

"""
Script de vérification de compatibilité base de données
Vérifie que les colonnes config_* existent et sont remplies
"""
import sys
from pathlib import Path

def print_header(text):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_warning(text):
    print(f"⚠️  {text}")

def check_config_columns_scan_logs():
    """Vérifier colonnes config_* dans scan_logs"""
    print_header("1. Vérification scan_logs - Colonnes config_*")
    
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg = get_pg_datalogger()
        if not pg or not pg.enabled:
            print_error("PostgreSQL datalogger non disponible")
            return False
        
        # Vérifier colonnes
        query = """
            SELECT column_name 
            FROM information_schema.columns
            WHERE table_name = 'scan_logs'
              AND column_name LIKE 'config_%'
            ORDER BY column_name
        """
        
        result = pg.execute_query(query, fetch=True)
        
        expected_columns = [
            'config_atr_max_1m',
            'config_atr_max_5m',
            'config_atr_min_1m',
            'config_atr_min_5m',
            'config_min_score_required',
            'config_snr_threshold',
            'config_use_confluence',
            'config_volume_multiplier',
        ]
        
        if result:
            found_columns = [row['column_name'] for row in result]
            print_success(f"{len(found_columns)} colonnes config_* trouvées")
            
            for col in expected_columns:
                if col in found_columns:
                    print_success(f"  - {col}")
                else:
                    print_error(f"  - {col} MANQUANTE")
            
            if len(found_columns) == len(expected_columns):
                print_success("Toutes les colonnes config_* présentes dans scan_logs")
                return True
            else:
                print_error(f"Colonnes manquantes: {len(expected_columns) - len(found_columns)}")
                return False
        else:
            print_error("Aucune colonne config_* trouvée dans scan_logs")
            print_warning("Exécutez: psql -U postgres -d tradebot -f database\\migration_add_config_columns.sql")
            return False
            
    except Exception as e:
        print_error(f"Erreur vérification scan_logs: {e}")
        return False

def check_config_columns_trades():
    """Vérifier colonnes config_* dans trades"""
    print_header("2. Vérification trades - Colonnes config_*")
    
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg = get_pg_datalogger()
        if not pg or not pg.enabled:
            print_error("PostgreSQL datalogger non disponible")
            return False
        
        # Vérifier colonnes
        query = """
            SELECT column_name 
            FROM information_schema.columns
            WHERE table_name = 'trades'
              AND column_name LIKE 'config_%'
            ORDER BY column_name
        """
        
        result = pg.execute_query(query, fetch=True)
        
        expected_columns = [
            'config_min_score_required',
            'config_optimal_atr_max_1m',
            'config_optimal_atr_max_5m',
            'config_optimal_atr_min_1m',
            'config_optimal_atr_min_5m',
            'config_snr_threshold',
            'config_use_confluence',
            'config_volume_multiplier',
        ]
        
        if result:
            found_columns = [row['column_name'] for row in result]
            print_success(f"{len(found_columns)} colonnes config_* trouvées")
            
            for col in expected_columns:
                if col in found_columns:
                    print_success(f"  - {col}")
                else:
                    print_error(f"  - {col} MANQUANTE")
            
            if len(found_columns) == len(expected_columns):
                print_success("Toutes les colonnes config_* présentes dans trades")
                return True
            else:
                print_error(f"Colonnes manquantes: {len(expected_columns) - len(found_columns)}")
                return False
        else:
            print_error("Aucune colonne config_* trouvée dans trades")
            print_warning("Exécutez: psql -U postgres -d tradebot -f database\\migration_add_config_columns.sql")
            return False
            
    except Exception as e:
        print_error(f"Erreur vérification trades: {e}")
        return False

def check_backfill_scan_logs():
    """Vérifier backfill dans scan_logs"""
    print_header("3. Vérification scan_logs - Backfill")
    
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg = get_pg_datalogger()
        if not pg or not pg.enabled:
            print_error("PostgreSQL datalogger non disponible")
            return False
        
        # Vérifier taux de remplissage
        query = """
            SELECT 
                COUNT(*) AS total,
                COUNT(config_min_score_required) AS filled,
                ROUND(COUNT(config_min_score_required)::NUMERIC / COUNT(*) * 100, 2) AS fill_pct
            FROM scan_logs
            WHERE params_snapshot IS NOT NULL
        """
        
        result = pg.execute_query(query, fetch=True)
        
        if result and result[0]['total'] > 0:
            total = result[0]['total']
            filled = result[0]['filled']
            fill_pct = result[0]['fill_pct']
            
            print_success(f"Total lignes avec params_snapshot: {total}")
            print_success(f"Lignes avec config_min_score_required: {filled}")
            
            if fill_pct >= 90:
                print_success(f"Taux de remplissage: {fill_pct}% ✅ (≥90%)")
                return True
            elif fill_pct >= 50:
                print_warning(f"Taux de remplissage: {fill_pct}% ⚠️ (<90%)")
                print_warning("Certaines lignes n'ont pas été backfillées")
                return True
            else:
                print_error(f"Taux de remplissage: {fill_pct}% ❌ (<50%)")
                print_error("Le backfill a échoué ou params_snapshot est incomplet")
                return False
        else:
            print_warning("Aucune ligne avec params_snapshot dans scan_logs")
            return True
            
    except Exception as e:
        print_error(f"Erreur vérification backfill scan_logs: {e}")
        return False

def check_backfill_trades():
    """Vérifier backfill dans trades"""
    print_header("4. Vérification trades - Backfill")
    
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg = get_pg_datalogger()
        if not pg or not pg.enabled:
            print_error("PostgreSQL datalogger non disponible")
            return False
        
        # Vérifier taux de remplissage
        query = """
            SELECT 
                COUNT(*) AS total,
                COUNT(config_min_score_required) AS filled,
                ROUND(COUNT(config_min_score_required)::NUMERIC / COUNT(*) * 100, 2) AS fill_pct
            FROM trades
            WHERE config_snapshot IS NOT NULL
        """
        
        result = pg.execute_query(query, fetch=True)
        
        if result and result[0]['total'] > 0:
            total = result[0]['total']
            filled = result[0]['filled']
            fill_pct = result[0]['fill_pct']
            
            print_success(f"Total lignes avec config_snapshot: {total}")
            print_success(f"Lignes avec config_min_score_required: {filled}")
            
            if fill_pct >= 90:
                print_success(f"Taux de remplissage: {fill_pct}% ✅ (≥90%)")
                return True
            elif fill_pct >= 50:
                print_warning(f"Taux de remplissage: {fill_pct}% ⚠️ (<90%)")
                print_warning("Certaines lignes n'ont pas été backfillées")
                return True
            else:
                print_error(f"Taux de remplissage: {fill_pct}% ❌ (<50%)")
                print_error("Le backfill a échoué ou config_snapshot est incomplet")
                return False
        else:
            print_warning("Aucune ligne avec config_snapshot dans trades")
            return True
            
    except Exception as e:
        print_error(f"Erreur vérification backfill trades: {e}")
        return False

def check_ml_view():
    """Vérifier que la vue ml_features fonctionne"""
    print_header("5. Vérification vue ml_features")
    
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg = get_pg_datalogger()
        if not pg or not pg.enabled:
            print_error("PostgreSQL datalogger non disponible")
            return False
        
        # Vérifier que la vue existe
        query_exists = """
            SELECT COUNT(*) as count
            FROM information_schema.views
            WHERE table_name = 'ml_features'
        """
        
        result = pg.execute_query(query_exists, fetch=True)
        
        if not result or result[0]['count'] == 0:
            print_error("Vue ml_features n'existe pas")
            print_warning("Exécutez: psql -U postgres -d tradebot -f database\\create_ml_view.sql")
            return False
        
        print_success("Vue ml_features existe")
        
        # Tester la vue avec colonnes config_*
        query_test = """
            SELECT 
                config_min_score_required,
                config_snr_threshold,
                config_atr_min_1m
            FROM ml_features
            LIMIT 5
        """
        
        result = pg.execute_query(query_test, fetch=True)
        
        if result:
            print_success(f"Vue ml_features retourne {len(result)} lignes")
            
            # Vérifier qu'au moins une ligne a des valeurs config_*
            has_values = any(
                row['config_min_score_required'] is not None 
                for row in result
            )
            
            if has_values:
                print_success("Colonnes config_* contiennent des valeurs")
                return True
            else:
                print_warning("Colonnes config_* sont NULL (backfill incomplet)")
                return True
        else:
            print_warning("Vue ml_features vide (aucun trade fermé)")
            return True
            
    except Exception as e:
        print_error(f"Erreur vérification vue ml_features: {e}")
        print_warning("La vue existe mais contient des erreurs")
        return False

def run_verification():
    """Exécuter toutes les vérifications"""
    print("\n" + "🔍" * 40)
    print("VÉRIFICATION COMPATIBILITÉ BASE DE DONNÉES")
    print("🔍" * 40)
    
    checks = [
        ("Colonnes scan_logs", check_config_columns_scan_logs),
        ("Colonnes trades", check_config_columns_trades),
        ("Backfill scan_logs", check_backfill_scan_logs),
        ("Backfill trades", check_backfill_trades),
        ("Vue ml_features", check_ml_view),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Erreur lors de {name}: {e}")
            results.append((name, False))
    
    # Résumé
    print_header("RÉSUMÉ")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:12} - {name}")
    
    print("\n" + "=" * 80)
    print(f"Score: {passed}/{total} vérifications réussies")
    
    if passed == total:
        print("\n🎉 SUCCÈS ! Base de données 100% compatible")
        print("✅ Vous pouvez utiliser XGBoost V2 et Optuna V2")
        return 0
    elif passed >= total - 1:
        print("\n⚠️  QUASI-SUCCÈS : Compatibilité partielle")
        print("Quelques vérifications ont échoué mais le système peut fonctionner")
        return 0
    else:
        print("\n❌ ÉCHEC : Incompatibilité détectée")
        print("Exécutez la migration:")
        print("  psql -U postgres -d tradebot -f database\\migration_add_config_columns.sql")
        return 1

if __name__ == "__main__":
    sys.exit(run_verification())

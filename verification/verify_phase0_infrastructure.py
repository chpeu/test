"""
Verification script pour Phase 0: Infrastructure Market Regime V2

Usage:
    python verification/verify_phase0_infrastructure.py

Verifie:
    1. Migration SQL executee (colonnes + vues)
    2. session_detector.py fonctionne
    3. MARKET_REGIME_V2_CONFIG dans config.py
    4. Toggles dans config_overrides.json
    5. Export Excel inclut nouvelles colonnes
"""
import os
import sys
from pathlib import Path

# Ajouter le repertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def check_migration():
    """Verifie que la migration SQL a ete executee"""
    print("\n" + "=" * 60)
    print("1. VERIFICATION MIGRATION SQL")
    print("=" * 60)
    
    import psycopg2
    
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
    except Exception as e:
        print(f"[ERREUR] Connexion PostgreSQL: {e}")
        return False
    
    all_ok = True
    
    # Colonnes trade_atr_metrics
    tam_columns = [
        'session_market', 'hour_utc', 'day_of_week', 'is_weekend',
        'regime_detection_method', 'regime_atr_median', 'regime_atr_smoothed',
        'regime_confidence', 'regime_stability_minutes',
        'regime_ml_predicted', 'regime_ml_confidence', 'regime_ml_vs_rule_match',
        'pnl_if_calme_params', 'pnl_if_normal_params', 'pnl_if_volatile_params',
        'optimal_regime_retrospective', 'session_atr_multiplier'
    ]
    
    # Colonnes market_regime_history
    mrh_columns = [
        'detection_method', 'atr_median', 'atr_smoothed',
        'session_market', 'hysteresis_applied', 'outliers_filtered_count', 'ml_confidence'
    ]
    
    # Colonnes scan_logs
    scan_columns = ['session_market', 'hour_utc', 'regime_at_scan', 'regime_confidence_at_scan']
    
    # Vues
    views = ['v_performance_by_session', 'v_performance_by_regime_session', 
             'v_optimal_regime_analysis', 'v_performance_by_hour']
    
    with conn.cursor() as cur:
        # Check trade_atr_metrics
        print("\n[trade_atr_metrics]")
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'trade_atr_metrics'
        """)
        existing = {row[0] for row in cur.fetchall()}
        
        for col in tam_columns:
            if col in existing:
                print(f"  [OK] {col}")
            else:
                print(f"  [MANQUANT] {col}")
                all_ok = False
        
        # Check market_regime_history
        print("\n[market_regime_history]")
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'market_regime_history'
        """)
        existing = {row[0] for row in cur.fetchall()}
        
        for col in mrh_columns:
            if col in existing:
                print(f"  [OK] {col}")
            else:
                print(f"  [MANQUANT] {col}")
                all_ok = False
        
        # Check scan_logs
        print("\n[scan_logs]")
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'scan_logs'
        """)
        existing = {row[0] for row in cur.fetchall()}
        
        for col in scan_columns:
            if col in existing:
                print(f"  [OK] {col}")
            else:
                print(f"  [MANQUANT] {col}")
                all_ok = False
        
        # Check views
        print("\n[Vues SQL]")
        for view in views:
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views 
                    WHERE table_name = '{view}'
                )
            """)
            exists = cur.fetchone()[0]
            if exists:
                print(f"  [OK] {view}")
            else:
                print(f"  [MANQUANT] {view}")
                all_ok = False
    
    conn.close()
    return all_ok


def check_session_detector():
    """Verifie que session_detector.py fonctionne"""
    print("\n" + "=" * 60)
    print("2. VERIFICATION SESSION DETECTOR")
    print("=" * 60)
    
    try:
        from utils.session_detector import get_current_session, get_full_context, DEFAULT_SESSIONS
        
        # Test chaque heure
        sessions_found = set()
        for hour in range(24):
            session = get_current_session(hour)
            sessions_found.add(session['name'])
        
        expected_sessions = set(DEFAULT_SESSIONS.keys())
        
        if sessions_found == expected_sessions:
            print(f"  [OK] 8 sessions detectees: {', '.join(sorted(sessions_found))}")
        else:
            missing = expected_sessions - sessions_found
            print(f"  [ERREUR] Sessions manquantes: {missing}")
            return False
        
        # Test contexte actuel
        ctx = get_full_context()
        print(f"  [OK] Session actuelle: {ctx['name']} (x{ctx['atr_multiplier']})")
        print(f"  [OK] Contexte: {ctx['context_string']}")
        
        return True
        
    except Exception as e:
        print(f"  [ERREUR] Import session_detector: {e}")
        return False


def check_config():
    """Verifie MARKET_REGIME_V2_CONFIG dans config.py"""
    print("\n" + "=" * 60)
    print("3. VERIFICATION CONFIG.PY")
    print("=" * 60)
    
    try:
        from config import MARKET_REGIME_V2_CONFIG
        
        required_keys = [
            'v2_enabled', 'use_median', 'use_hysteresis', 'use_smoothing',
            'use_atr_5m', 'use_seasonality', 'use_ml_regime',
            'outlier_filter_enabled', 'hysteresis_buffer_percent',
            'smoothing_alpha', 'min_regime_duration_minutes', 'sessions'
        ]
        
        all_ok = True
        for key in required_keys:
            if key in MARKET_REGIME_V2_CONFIG:
                print(f"  [OK] {key} = {MARKET_REGIME_V2_CONFIG[key]}")
            else:
                print(f"  [MANQUANT] {key}")
                all_ok = False
        
        # Verifier que tous les toggles sont OFF par defaut
        toggles = ['v2_enabled', 'use_median', 'use_hysteresis', 'use_smoothing', 
                   'use_atr_5m', 'use_seasonality', 'use_ml_regime']
        
        all_off = all(MARKET_REGIME_V2_CONFIG.get(t) == False for t in toggles)
        if all_off:
            print(f"\n  [OK] Tous les toggles sont OFF par defaut (comportement V1 preserve)")
        else:
            print(f"\n  [ATTENTION] Certains toggles sont ON!")
            all_ok = False
        
        return all_ok
        
    except ImportError as e:
        print(f"  [ERREUR] Import MARKET_REGIME_V2_CONFIG: {e}")
        return False


def check_overrides():
    """Verifie les toggles dans config_overrides.json"""
    print("\n" + "=" * 60)
    print("4. VERIFICATION CONFIG_OVERRIDES.JSON")
    print("=" * 60)
    
    import json
    
    overrides_path = Path(__file__).parent.parent / 'config_overrides.json'
    
    if not overrides_path.exists():
        print(f"  [ERREUR] Fichier non trouve: {overrides_path}")
        return False
    
    try:
        with open(overrides_path, 'r') as f:
            overrides = json.load(f)
        
        v2_keys = [
            'market_regime_v2_enabled', 'market_regime_use_median',
            'market_regime_use_hysteresis', 'market_regime_use_smoothing',
            'market_regime_use_atr_5m', 'market_regime_use_seasonality',
            'market_regime_hysteresis_buffer', 'market_regime_smoothing_alpha',
            'market_regime_atr_1m_weight', 'market_regime_atr_5m_weight',
            'market_regime_min_duration_minutes'
        ]
        
        all_ok = True
        for key in v2_keys:
            if key in overrides:
                print(f"  [OK] {key} = {overrides[key]}")
            else:
                print(f"  [MANQUANT] {key}")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  [ERREUR] Lecture config_overrides.json: {e}")
        return False


def check_export_excel():
    """Verifie que main.py inclut les colonnes V2 dans l'export Excel"""
    print("\n" + "=" * 60)
    print("5. VERIFICATION EXPORT EXCEL (main.py)")
    print("=" * 60)
    
    main_path = Path(__file__).parent.parent / 'main.py'
    
    try:
        content = main_path.read_text(encoding='utf-8')
        
        checks = [
            ("trade_atr_metrics V2 columns", "session_market', 'hour_utc', 'day_of_week"),
            ("regime_detection_method", "regime_detection_method"),
            ("pnl_if_calme_params", "pnl_if_calme_params"),
            ("scan_logs V2 columns", "regime_at_scan"),
            ("market_regime_history V2", "detection_method', 'atr_median"),
        ]
        
        all_ok = True
        for name, pattern in checks:
            if pattern in content:
                print(f"  [OK] {name}")
            else:
                print(f"  [MANQUANT] {name}")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  [ERREUR] Lecture main.py: {e}")
        return False


def check_files_exist():
    """Verifie que tous les fichiers Phase 0 existent"""
    print("\n" + "=" * 60)
    print("6. VERIFICATION FICHIERS PHASE 0")
    print("=" * 60)
    
    root = Path(__file__).parent.parent
    
    files = [
        'database/migrations/add_regime_context_columns.sql',
        'utils/session_detector.py',
        'verification/run_regime_v2_migration.py',
    ]
    
    all_ok = True
    for f in files:
        path = root / f
        if path.exists():
            print(f"  [OK] {f}")
        else:
            print(f"  [MANQUANT] {f}")
            all_ok = False
    
    return all_ok


def main():
    print("=" * 60)
    print("VERIFICATION PHASE 0: INFRASTRUCTURE MARKET REGIME V2")
    print("=" * 60)
    
    results = {
        "Migration SQL": check_migration(),
        "Session Detector": check_session_detector(),
        "Config.py": check_config(),
        "Config Overrides": check_overrides(),
        "Export Excel": check_export_excel(),
        "Fichiers": check_files_exist(),
    }
    
    print("\n" + "=" * 60)
    print("RESUME")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "[OK]" if passed else "[ECHEC]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] PHASE 0 COMPLETE - Infrastructure prete!")
    else:
        print("[ECHEC] Phase 0 incomplete - Voir erreurs ci-dessus")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

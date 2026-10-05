"""
Verification complete des implementations Phase 0 + Phase 1
"""
import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def verify_config():
    """Verifier les parametres dans config.py et config_overrides.json"""
    print("\n" + "=" * 60)
    print("1. VERIFICATION CONFIG")
    print("=" * 60)
    
    from config import TRADING_CONFIG
    
    params_to_check = [
        'trailing_distance_atr_mult',
        'trailing_atr_multiplier', 
        'trailing_trigger_atr_mult',
        'break_even_atr_mult',
        'atr_mult_sl',
        'atr_mult_tp',
        'stagnation_exit_timeout_seconds',
        'stagnation_exit_min_pnl_to_stay'
    ]
    
    print("\nParametres ATR dans TRADING_CONFIG:")
    all_ok = True
    for param in params_to_check:
        value = TRADING_CONFIG.get(param, 'MISSING')
        status = "OK" if value != 'MISSING' else "MISSING"
        if status == "MISSING":
            all_ok = False
        print(f"  {param}: {value} [{status}]")
    
    # Verifier config_overrides.json
    print("\nParametres dans config_overrides.json:")
    with open('config_overrides.json', 'r') as f:
        overrides = json.load(f)
    
    for param in ['trailing_distance_atr_mult', 'trailing_atr_multiplier', 'trailing_trigger_atr_mult']:
        value = overrides.get(param, 'MISSING')
        status = "OK" if value != 'MISSING' else "MISSING"
        print(f"  {param}: {value} [{status}]")
    
    return all_ok

def verify_sql_table():
    """Verifier que la table trade_atr_metrics existe"""
    print("\n" + "=" * 60)
    print("2. VERIFICATION TABLE SQL trade_atr_metrics")
    print("=" * 60)
    
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv()
    
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        cur = conn.cursor()
        
        # Check table exists
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'trade_atr_metrics'
        """)
        exists = cur.fetchone()[0] > 0
        
        if exists:
            # Count columns
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_name = 'trade_atr_metrics'
            """)
            col_count = cur.fetchone()[0]
            print(f"  Table existe: OUI ({col_count} colonnes)")
            
            # Check key columns
            cur.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'trade_atr_metrics'
                AND column_name IN ('param_trailing_distance_mult', 'market_volatility_state', 'pnl_if_no_be')
            """)
            key_cols = [r[0] for r in cur.fetchall()]
            print(f"  Colonnes cles presentes: {key_cols}")
        else:
            print("  Table existe: NON - Executez la migration!")
            return False
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"  Erreur SQL: {e}")
        return False

def verify_export_excel():
    """Verifier que trade_atr_metrics est dans l'export Excel"""
    print("\n" + "=" * 60)
    print("3. VERIFICATION EXPORT EXCEL")
    print("=" * 60)
    
    with open('export_datalogger_to_excel.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'trade_atr_metrics' in content:
        print("  trade_atr_metrics dans export: OUI")
        return True
    else:
        print("  trade_atr_metrics dans export: NON")
        return False

def verify_main_handler():
    """Verifier le handler dans main.py"""
    print("\n" + "=" * 60)
    print("4. VERIFICATION HANDLER main.py")
    print("=" * 60)
    
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("trailing_distance_atr_mult handler", "trailing_distance_atr_mult' in params" in content),
        ("Sync avec trailing_atr_multiplier", "TRADING_CONFIG['trailing_atr_multiplier'] = val  # Sync" in content),
    ]
    
    all_ok = True
    for name, passed in checks:
        status = "OK" if passed else "MISSING"
        if not passed:
            all_ok = False
        print(f"  {name}: {status}")
    
    return all_ok

def verify_logger_enrichment():
    """Verifier que le logger ATR metrics est implementé"""
    print("\n" + "=" * 60)
    print("5. VERIFICATION LOGGER ENRICHI")
    print("=" * 60)
    
    with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("Méthode log_trade_atr_metrics", "def log_trade_atr_metrics" in content),
        ("Appel dans log_trade", "self.log_trade_atr_metrics(trade_id" in content),
        ("Extraction param_trailing_distance_mult", "param_trailing_distance_mult" in content),
        ("Détection market_volatility_state", "market_volatility_state = 'LOW'" in content),
        ("Détection market_trend_state", "market_trend_state = 'RANGING'" in content),
    ]
    
    all_ok = True
    for name, passed in checks:
        status = "OK" if passed else "MISSING"
        if not passed:
            all_ok = False
        print(f"  {name}: {status}")
    
    return all_ok

def verify_frontend():
    """Verifier le frontend VariablesPanel.svelte"""
    print("\n" + "=" * 60)
    print("6. VERIFICATION FRONTEND")
    print("=" * 60)
    
    with open('frontend/src/lib/components/VariablesPanel.svelte', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("trailing_distance_atr_mult slider", "trailing-distance-atr-mult" in content),
        ("Trailing Distance label", "Trailing Distance" in content),
        ("Variables en cours - trailing_distance", "trailing_distance_atr_mult:" in content),
    ]
    
    all_ok = True
    for name, passed in checks:
        status = "OK" if passed else "MISSING"
        if not passed:
            all_ok = False
        print(f"  {name}: {status}")
    
    return all_ok

def main():
    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE - Phase 0 + Phase 1")
    print("=" * 60)
    
    results = {
        'Config': verify_config(),
        'SQL Table': verify_sql_table(),
        'Export Excel': verify_export_excel(),
        'Main Handler': verify_main_handler(),
        'Logger Enrichi': verify_logger_enrichment(),
        'Frontend': verify_frontend(),
    }
    
    print("\n" + "=" * 60)
    print("RESUME")
    print("=" * 60)
    
    all_ok = True
    for name, passed in results.items():
        status = "OK" if passed else "FAILED"
        if not passed:
            all_ok = False
        print(f"  {name}: {status}")
    
    print("\n" + ("=" * 60))
    if all_ok:
        print("VERIFICATION COMPLETE - Tout est OK!")
    else:
        print("ATTENTION: Certaines verifications ont echoue!")
    print("=" * 60)
    
    return all_ok

if __name__ == "__main__":
    main()

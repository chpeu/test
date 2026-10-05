"""
Verification script for Trailing MFE implementation
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

def verify_config():
    """1. Verify config.py"""
    print("=== 1. CONFIG.PY ===")
    from config import TRADING_CONFIG
    
    enabled = TRADING_CONFIG.get('trailing_mfe_enabled')
    trigger = TRADING_CONFIG.get('trailing_mfe_trigger_pct')
    
    if enabled is not None:
        print(f"OK: trailing_mfe_enabled = {enabled}")
    else:
        print("ERROR: trailing_mfe_enabled MISSING")
        
    if trigger is not None:
        print(f"OK: trailing_mfe_trigger_pct = {trigger}")
    else:
        print("ERROR: trailing_mfe_trigger_pct MISSING")
    
    return enabled is not None and trigger is not None

def verify_position_manager():
    """2. Verify position_manager.py logic"""
    print("\n=== 2. POSITION_MANAGER LOGIC ===")
    
    with open('core/position_manager.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("TRADING_CONFIG.get('trailing_mfe_enabled'", "Logic reads trailing_mfe_enabled"),
        ("trailing_mfe_triggered: bool", "Position dataclass has attribute"),
        ("'trailing_mfe_triggered': self.active_position.trailing_mfe_triggered", "trade_data output"),
    ]
    
    all_ok = True
    for pattern, desc in checks:
        if pattern in content:
            print(f"OK: {desc}")
        else:
            print(f"ERROR: {desc} - pattern not found")
            all_ok = False
    
    return all_ok

def verify_datalogger():
    """3. Verify postgresql_datalogger.py"""
    print("\n=== 3. POSTGRESQL_DATALOGGER ===")
    
    with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("trailing_mfe_triggered = trade_data.get", "Extracts trailing_mfe_triggered"),
        ("trailing_mfe_triggered, trailing_mfe_triggered_at", "INSERT columns"),
    ]
    
    all_ok = True
    for pattern, desc in checks:
        if pattern in content:
            print(f"OK: {desc}")
        else:
            print(f"ERROR: {desc} - pattern not found")
            all_ok = False
    
    return all_ok

def verify_sql_columns():
    """4. Verify SQL columns exist"""
    print("\n=== 4. SQL COLUMNS ===")
    
    import psycopg2
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        database=os.getenv('POSTGRES_DB', 'trading_db'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cur = conn.cursor()
    
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'trade_atr_metrics' AND column_name LIKE 'trailing_mfe%'
    """)
    cols = [r[0] for r in cur.fetchall()]
    conn.close()
    
    expected = [
        'trailing_mfe_triggered', 
        'trailing_mfe_triggered_at', 
        'trailing_mfe_trigger_pnl_pct', 
        'trailing_mfe_trigger_price'
    ]
    
    print(f"Found columns: {cols}")
    
    missing = [c for c in expected if c not in cols]
    if missing:
        print(f"ERROR: Missing columns: {missing}")
        return False
    else:
        print("OK: All 4 columns exist")
        return True

def verify_websocket_handler():
    """5. Verify main.py WebSocket handler"""
    print("\n=== 5. WEBSOCKET HANDLER ===")
    
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("if 'trailing_mfe_enabled' in params:", "Handler for trailing_mfe_enabled"),
        ("if 'trailing_mfe_trigger_pct' in params:", "Handler for trailing_mfe_trigger_pct"),
    ]
    
    all_ok = True
    for pattern, desc in checks:
        if pattern in content:
            print(f"OK: {desc}")
        else:
            print(f"ERROR: {desc} - pattern not found")
            all_ok = False
    
    return all_ok

if __name__ == "__main__":
    print("=" * 60)
    print("TRAILING MFE IMPLEMENTATION VERIFICATION")
    print("=" * 60)
    
    results = []
    results.append(("Config.py", verify_config()))
    results.append(("Position Manager", verify_position_manager()))
    results.append(("PostgreSQL Datalogger", verify_datalogger()))
    results.append(("SQL Columns", verify_sql_columns()))
    results.append(("WebSocket Handler", verify_websocket_handler()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_ok = True
    for name, ok in results:
        status = "OK" if ok else "FAILED"
        print(f"  {name}: {status}")
        if not ok:
            all_ok = False
    
    print()
    if all_ok:
        print("ALL CHECKS PASSED - Implementation complete!")
    else:
        print("SOME CHECKS FAILED - Review errors above")

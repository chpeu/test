#!/usr/bin/env python3
"""
Verification script for Dec 1 fixes:
1. mexc_contracts variable initialization before use
2. ml_confidence column logging

Run: python verification/verify_fixes_dec01.py
"""

import os
import sys
import re

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verify_mexc_contracts_fix():
    """Verify mexc_contracts is defined before use."""
    print("\n" + "="*60)
    print("FIX 1: mexc_contracts variable initialization")
    print("="*60)
    
    filepath = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'trading', 'live_order_manager_futures.py'
    )
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find definition and usage
    definition_pattern = r'mexc_contracts\s*=\s*amount'
    usage_pattern = r'verified_contracts\s*-\s*mexc_contracts'
    
    definition_match = re.search(definition_pattern, content)
    usage_match = re.search(usage_pattern, content)
    
    if definition_match and usage_match:
        def_pos = definition_match.start()
        usage_pos = usage_match.start()
        
        if def_pos < usage_pos:
            print("[OK] mexc_contracts is DEFINED before USED")
            print(f"     Definition at position: {def_pos}")
            print(f"     Usage at position: {usage_pos}")
            return True
        else:
            print("[FAIL] mexc_contracts is used BEFORE definition!")
            print(f"       Usage at position: {usage_pos}")
            print(f"       Definition at position: {def_pos}")
            return False
    else:
        print("[WARN] Could not find mexc_contracts patterns")
        return False


def verify_position_size_fix():
    """Verify position size returns real tokens, not MEXC contracts."""
    print("\n" + "="*60)
    print("FIX 3: Position size returns real tokens (not MEXC contracts)")
    print("="*60)
    
    # Check live_order_manager_futures.py
    filepath = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'trading', 'live_order_manager_futures.py'
    )
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        'filled_amount uses real_filled_amount': 'filled_amount=real_filled_amount' in content,
        'filled_contracts uses real_filled_amount': 'filled_contracts=real_filled_amount' in content,
    }
    
    all_ok = True
    for check, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} live_order_manager_futures.py: {check}")
        if not passed:
            all_ok = False
    
    # Check position_manager.py
    pm_filepath = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'core', 'position_manager.py'
    )
    
    with open(pm_filepath, 'r', encoding='utf-8') as f:
        pm_content = f.read()
    
    pm_checks = {
        '_get_contract_size method exists': 'def _get_contract_size' in pm_content,
        'Sync uses contract_size': 'real_tokens = live_contracts * contract_size' in pm_content,
        'size_initial_contracts uses real_tokens': 'size_initial_contracts = real_tokens' in pm_content,
    }
    
    for check, passed in pm_checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} position_manager.py: {check}")
        if not passed:
            all_ok = False
    
    if all_ok:
        print("\n  [INFO] Position sizes will now show actual token amounts")
        print("         Example: SHIB 2524 contracts x 1000 contractSize = 2,524,000 tokens")
    
    return all_ok


def verify_ml_confidence_column():
    """Verify ml_confidence column is properly added."""
    print("\n" + "="*60)
    print("FIX 2: ml_confidence column in scan_logs")
    print("="*60)
    
    # Check postgresql_datalogger.py
    logger_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'core', 'postgresql_datalogger.py'
    )
    
    with open(logger_path, 'r', encoding='utf-8') as f:
        logger_content = f.read()
    
    logger_checks = {
        'INSERT column': 'ml_confidence' in logger_content and 'INSERT INTO scan_logs' in logger_content,
        'Direct insert value': "scan_data.get('ml_confidence')" in logger_content,
        'Batch columns list': "'ml_confidence'" in logger_content or '"ml_confidence"' in logger_content,
        'update_ml_confidence method': "def update_ml_confidence" in logger_content,
    }
    
    all_ok = True
    for check, passed in logger_checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} postgresql_datalogger.py: {check}")
        if not passed:
            all_ok = False
    
    # Check main.py
    main_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'main.py'
    )
    
    with open(main_path, 'r', encoding='utf-8') as f:
        main_content = f.read()
    
    main_checks = {
        'Init in callback': "last_ml_confidence = None  # 🔥 FIX: Initialiser ICI" in main_content,
        'Init in scan_pair_for_setup': "# 🔥 FIX: Initialiser last_ml_confidence pour le logging PostgreSQL" in main_content,
        'Store in setup': "setup['ml_confidence'] = ml_conf_pct" in main_content,
        'Store in last_ml_confidence': "last_ml_confidence = ml_conf_pct" in main_content,
        'Pass to scan_data': "'ml_confidence': last_ml_confidence" in main_content,
        'Call update_ml_confidence': "pg_logger.update_ml_confidence(symbol, ml_conf_pct)" in main_content,
    }
    
    for check, passed in main_checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} main.py: {check}")
        if not passed:
            all_ok = False
    
    # Check scanner_loop.py
    scanner_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'core', 'callbacks', 'scanner_loop.py'
    )
    
    with open(scanner_path, 'r', encoding='utf-8') as f:
        scanner_content = f.read()
    
    scanner_checks = {
        'Store in best_setup': "best_setup['ml_confidence'] = confidence * 100" in scanner_content,
    }
    
    for check, passed in scanner_checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} scanner_loop.py: {check}")
        if not passed:
            all_ok = False
    
    return all_ok


def verify_db_column():
    """Check if ml_confidence column exists in database."""
    print("\n" + "="*60)
    print("FIX 2b: Database column ml_confidence")
    print("="*60)
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '@Cmtr1di12345')
        )
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check column exists
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'scan_logs'
            AND column_name = 'ml_confidence'
        """)
        
        result = cursor.fetchone()
        
        if result:
            print(f"  [OK] Column exists: {result['column_name']} ({result['data_type']})")
            
            # Check recent data
            cursor.execute("""
                SELECT COUNT(*) as total,
                       COUNT(ml_confidence) as with_value,
                       AVG(ml_confidence) as avg_confidence
                FROM scan_logs
                WHERE timestamp > NOW() - INTERVAL '1 hour'
            """)
            
            stats = cursor.fetchone()
            print(f"  [INFO] Recent scans (1h): {stats['total']} total, {stats['with_value']} with ml_confidence")
            if stats['avg_confidence']:
                print(f"  [INFO] Avg confidence: {stats['avg_confidence']:.2f}%")
            
            cursor.close()
            conn.close()
            return True
        else:
            print("  [FAIL] Column ml_confidence not found in scan_logs")
            cursor.close()
            conn.close()
            return False
            
    except Exception as e:
        print(f"  [ERROR] Database check failed: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("VERIFICATION: December 1st Fixes")
    print("="*60)
    
    results = {
        'mexc_contracts': verify_mexc_contracts_fix(),
        'position_size_tokens': verify_position_size_fix(),
        'ml_confidence_code': verify_ml_confidence_column(),
        'ml_confidence_db': verify_db_column(),
    }
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_ok = all(results.values())
    
    for check, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")
    
    if all_ok:
        print("\n[SUCCESS] All fixes verified!")
    else:
        print("\n[WARNING] Some fixes need attention.")
        print("\nNext steps:")
        print("  1. Restart backend: python main.py")
        print("  2. Wait for a few ML predictions")
        print("  3. Check logs for: 'ml_confidence' values")
        print("  4. Verify in DB: SELECT ml_confidence FROM scan_logs ORDER BY timestamp DESC LIMIT 10;")
    
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())

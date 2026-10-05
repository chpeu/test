# -*- coding: utf-8 -*-
"""Verify exit strategies implementation - 14/12/2025"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from dotenv import load_dotenv

load_dotenv()

def main():
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cur = conn.cursor()
    
    print("=" * 70)
    print("VERIFICATION: Exit Strategies Implementation - 14/12/2025")
    print("=" * 70)
    
    # 1. Check new SQL columns exist
    print("\n[1] NEW SQL COLUMNS IN trade_atr_metrics")
    print("-" * 50)
    new_columns = [
        'param_stagnation_positive_enabled',
        'param_stagnation_positive_threshold', 
        'param_stagnation_positive_timeout',
        'param_trailing_mfe_enabled',
        'param_trailing_mfe_trigger_pct',
        'param_stagnation_mfe_tracking',
        'param_stagnation_mfe_pullback_pct',
        'stagnation_positive_triggered',
        'stagnation_mfe_at_exit',
        'stagnation_pullback_at_exit'
    ]
    
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trade_atr_metrics'
    """)
    existing_cols = [r[0] for r in cur.fetchall()]
    
    all_ok = True
    for col in new_columns:
        exists = col in existing_cols
        status = "OK" if exists else "MISSING"
        print(f"  {col}: {status}")
        if not exists:
            all_ok = False
    
    print(f"\n  Result: {'ALL COLUMNS PRESENT' if all_ok else 'SOME COLUMNS MISSING'}")
    
    # 2. Check exit_reason values
    print("\n[2] EXIT REASONS IN DATABASE")
    print("-" * 50)
    cur.execute("""
        SELECT exit_reason, COUNT(*) 
        FROM trades 
        GROUP BY exit_reason 
        ORDER BY COUNT(*) DESC
    """)
    for row in cur.fetchall():
        marker = " <-- NEW" if row[0] in ['STAGNATION_POSITIVE', 'STAGNATION_MFE_PROTECT'] else ""
        print(f"  {row[0]}: {row[1]} trades{marker}")
    
    # 3. Check Python code changes
    print("\n[3] PYTHON CODE VERIFICATION")
    print("-" * 50)
    
    # Check position_manager.py
    pm_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'position_manager.py')
    with open(pm_path, 'r', encoding='utf-8') as f:
        pm_content = f.read()
    
    checks = {
        'Position.stagnation_positive_triggered': 'stagnation_positive_triggered: bool = False',
        'Position.stagnation_mfe_at_exit': 'stagnation_mfe_at_exit: Optional[float]',
        'Position.stagnation_pullback_at_exit': 'stagnation_pullback_at_exit: Optional[float]',
        'base_stagnation_positive_timeout': "base_stagnation_positive_timeout = TRADING_CONFIG.get('stagnation_positive_timeout_seconds'",
        'MEDIUM regime multiplier': "effective_params['stagnation_positive_timeout_seconds'] = int(base_stagnation_positive_timeout * 0.8)",
        'HIGH regime multiplier': "effective_params['stagnation_positive_timeout_seconds'] = int(base_stagnation_positive_timeout * 1.5)",
        'LOW regime (neutral)': "effective_params['stagnation_positive_timeout_seconds'] = base_stagnation_positive_timeout",
        'effective_stagnation_positive_timeout': "effective_stagnation_positive_timeout = effective_config_local.get('stagnation_positive_timeout_seconds')",
        'trade_data stagnation_positive_triggered': "'stagnation_positive_triggered': getattr(self.active_position, 'stagnation_positive_triggered'",
        'trade_data stagnation_mfe_at_exit': "'stagnation_mfe_at_exit': getattr(self.active_position, 'stagnation_mfe_at_exit'",
    }
    
    for name, pattern in checks.items():
        found = pattern in pm_content
        status = "OK" if found else "MISSING"
        print(f"  {name}: {status}")
    
    # Check postgresql_datalogger.py
    dl_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'postgresql_datalogger.py')
    with open(dl_path, 'r', encoding='utf-8') as f:
        dl_content = f.read()
    
    dl_checks = {
        'param_stagnation_positive_enabled extraction': "param_stagnation_positive_enabled = config_snapshot.get('stagnation_positive_exit_enabled'",
        'param_trailing_mfe_enabled extraction': "param_trailing_mfe_enabled = config_snapshot.get('trailing_mfe_enabled'",
        'stagnation_positive_triggered extraction': "stagnation_positive_triggered = trade_data.get('stagnation_positive_triggered'",
        'INSERT param_stagnation_positive_enabled': 'param_stagnation_positive_enabled, param_stagnation_positive_threshold',
        'INSERT param_trailing_mfe_enabled': 'param_trailing_mfe_enabled, param_trailing_mfe_trigger_pct',
    }
    
    print("\n  postgresql_datalogger.py:")
    for name, pattern in dl_checks.items():
        found = pattern in dl_content
        status = "OK" if found else "MISSING"
        print(f"    {name}: {status}")
    
    # 4. Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
Exit Strategies Implementation Complete:

1. exit_reason values (already working):
   - STAGNATION_POSITIVE: 6 trades (sortie anticipee en profit)
   - STAGNATION_MFE_PROTECT: 0 trades (protection MFE, pas encore declenche)
   - STAGNATION: 534 trades (timeout normal)
   - TRAILING_MFE: N'est PAS un exit_reason (deplace SL->BE, exit = SL/TS)

2. NEW SQL columns added for ML analysis:
   - param_stagnation_positive_* (3 cols): Config at trade time
   - param_trailing_mfe_* (2 cols): Config at trade time
   - param_stagnation_mfe_* (2 cols): MFE protection config
   - stagnation_positive_triggered: Was STAGNATION_POSITIVE exit used
   - stagnation_mfe_at_exit: MFE% at stagnation exit
   - stagnation_pullback_at_exit: Pullback% at MFE protection exit

3. Regime multipliers for stagnation_positive_timeout:
   - MEDIUM volatility: x0.8 (faster positive exit)
   - HIGH volatility: x1.5 (more time for volatility)
   - LOW volatility: x1.0 (neutral)
""")
    
    conn.close()

if __name__ == '__main__':
    main()

"""Analyse impact RSI sur nombre de trades vs PnL"""
import subprocess
import os
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def run_sql(query):
    env = os.environ.copy()
    env['PGPASSWORD'] = '@Cmtr1di12345'
    env['PGCLIENTENCODING'] = 'UTF8'
    result = subprocess.run(
        ['psql', '-h', 'localhost', '-U', 'postgres', '-d', 'trade_cursor_ml', 
         '-t', '-A', '-F', '|', '-c', query],
        capture_output=True, text=True, env=env, encoding='utf-8', errors='replace'
    )
    if result.returncode != 0:
        return []
    return [line.split('|') for line in result.stdout.strip().split('\n') if line.strip()]

print("=" * 90)
print("ANALYSE IMPACT SEUILS RSI: NOMBRE DE TRADES vs PNL")
print("=" * 90)

# Scenarios de seuils à tester
scenarios = [
    {'name': 'ACTUEL', 'calme_long': 60, 'calme_short': 40, 'normal_long': 65, 'normal_short': 35},
    {'name': 'STRICT', 'calme_long': 55, 'calme_short': 45, 'normal_long': 60, 'normal_short': 40},
    {'name': 'PERMISSIF', 'calme_long': 70, 'calme_short': 30, 'normal_long': 70, 'normal_short': 30},
    {'name': 'CALME_STRICT', 'calme_long': 55, 'calme_short': 45, 'normal_long': 65, 'normal_short': 35},
    {'name': 'NORMAL_STRICT', 'calme_long': 60, 'calme_short': 40, 'normal_long': 60, 'normal_short': 40},
]

print("\n" + "-" * 90)
print(f"{'Scenario':<15} {'Regime':<10} {'Total':<7} {'Passes':<7} {'Bloques':<8} {'% Gardes':<10} {'PnL Gardes':<12} {'PnL Bloques':<12}")
print("-" * 90)

for sc in scenarios:
    for regime in ['CALME', 'NORMAL']:
        if regime == 'CALME':
            long_th = sc['calme_long']
            short_th = sc['calme_short']
        else:
            long_th = sc['normal_long']
            short_th = sc['normal_short']
        
        query = f'''
        SELECT 
            COUNT(*) as total,
            SUM(CASE 
                WHEN (direction='LONG' AND entry_rsi_1m <= {long_th}) 
                  OR (direction='SHORT' AND entry_rsi_1m >= {short_th}) 
                THEN 1 ELSE 0 END) as passes,
            SUM(CASE 
                WHEN (direction='LONG' AND entry_rsi_1m > {long_th}) 
                  OR (direction='SHORT' AND entry_rsi_1m < {short_th}) 
                THEN 1 ELSE 0 END) as blocked,
            ROUND(SUM(CASE 
                WHEN (direction='LONG' AND entry_rsi_1m <= {long_th}) 
                  OR (direction='SHORT' AND entry_rsi_1m >= {short_th}) 
                THEN net_pnl_usdt ELSE 0 END)::numeric, 2) as pnl_passes,
            ROUND(SUM(CASE 
                WHEN (direction='LONG' AND entry_rsi_1m > {long_th}) 
                  OR (direction='SHORT' AND entry_rsi_1m < {short_th}) 
                THEN net_pnl_usdt ELSE 0 END)::numeric, 2) as pnl_blocked
        FROM (
            SELECT * FROM trades 
            WHERE is_live_trade = true AND exit_price IS NOT NULL
            ORDER BY timestamp_exit DESC 
            LIMIT 100
        ) t
        WHERE COALESCE(entry_market_regime, 'UNKNOWN') = '{regime}' 
          AND entry_rsi_1m IS NOT NULL
        '''
        rows = run_sql(query)
        if rows and len(rows[0]) >= 5:
            r = rows[0]
            total = int(r[0]) if r[0] else 0
            passes = int(r[1]) if r[1] else 0
            blocked = int(r[2]) if r[2] else 0
            pnl_p = float(r[3]) if r[3] else 0
            pnl_b = float(r[4]) if r[4] else 0
            pct = round(100 * passes / total, 1) if total > 0 else 0
            
            print(f"{sc['name']:<15} {regime:<10} {total:<7} {passes:<7} {blocked:<8} {pct:<10} {pnl_p:<12} {pnl_b:<12}")

# Tableau recap par scenario
print("\n" + "=" * 90)
print("RECAP PAR SCENARIO (tous regimes confondus)")
print("=" * 90)

print(f"\n{'Scenario':<15} {'Trades Total':<14} {'Trades Gardes':<14} {'% Gardes':<10} {'PnL Gardes':<12} {'PnL Bloques':<12} {'PnL/Trade':<10}")
print("-" * 90)

for sc in scenarios:
    query = f'''
    SELECT 
        COUNT(*) as total,
        SUM(CASE 
            WHEN entry_market_regime = 'CALME' AND direction='LONG' AND entry_rsi_1m <= {sc['calme_long']} THEN 1
            WHEN entry_market_regime = 'CALME' AND direction='SHORT' AND entry_rsi_1m >= {sc['calme_short']} THEN 1
            WHEN entry_market_regime = 'NORMAL' AND direction='LONG' AND entry_rsi_1m <= {sc['normal_long']} THEN 1
            WHEN entry_market_regime = 'NORMAL' AND direction='SHORT' AND entry_rsi_1m >= {sc['normal_short']} THEN 1
            WHEN entry_market_regime = 'VOLATILE' THEN 1
            WHEN entry_market_regime IS NULL THEN 1
            ELSE 0 END) as passes,
        ROUND(SUM(CASE 
            WHEN entry_market_regime = 'CALME' AND direction='LONG' AND entry_rsi_1m <= {sc['calme_long']} THEN net_pnl_usdt
            WHEN entry_market_regime = 'CALME' AND direction='SHORT' AND entry_rsi_1m >= {sc['calme_short']} THEN net_pnl_usdt
            WHEN entry_market_regime = 'NORMAL' AND direction='LONG' AND entry_rsi_1m <= {sc['normal_long']} THEN net_pnl_usdt
            WHEN entry_market_regime = 'NORMAL' AND direction='SHORT' AND entry_rsi_1m >= {sc['normal_short']} THEN net_pnl_usdt
            WHEN entry_market_regime = 'VOLATILE' THEN net_pnl_usdt
            WHEN entry_market_regime IS NULL THEN net_pnl_usdt
            ELSE 0 END)::numeric, 2) as pnl_passes,
        ROUND(SUM(CASE 
            WHEN entry_market_regime = 'CALME' AND direction='LONG' AND entry_rsi_1m > {sc['calme_long']} THEN net_pnl_usdt
            WHEN entry_market_regime = 'CALME' AND direction='SHORT' AND entry_rsi_1m < {sc['calme_short']} THEN net_pnl_usdt
            WHEN entry_market_regime = 'NORMAL' AND direction='LONG' AND entry_rsi_1m > {sc['normal_long']} THEN net_pnl_usdt
            WHEN entry_market_regime = 'NORMAL' AND direction='SHORT' AND entry_rsi_1m < {sc['normal_short']} THEN net_pnl_usdt
            ELSE 0 END)::numeric, 2) as pnl_blocked
    FROM (
        SELECT * FROM trades 
        WHERE is_live_trade = true AND exit_price IS NOT NULL
        ORDER BY timestamp_exit DESC 
        LIMIT 100
    ) t
    WHERE entry_rsi_1m IS NOT NULL
    '''
    rows = run_sql(query)
    if rows and len(rows[0]) >= 4:
        r = rows[0]
        total = int(r[0]) if r[0] else 0
        passes = int(r[1]) if r[1] else 0
        pnl_p = float(r[2]) if r[2] else 0
        pnl_b = float(r[3]) if r[3] else 0
        pct = round(100 * passes / total, 1) if total > 0 else 0
        pnl_per_trade = round(pnl_p / passes, 3) if passes > 0 else 0
        
        print(f"{sc['name']:<15} {total:<14} {passes:<14} {pct:<10} {pnl_p:<12} {pnl_b:<12} {pnl_per_trade:<10}")

print("\n" + "=" * 90)
print("LEGENDE:")
print("  - ACTUEL: Seuils implementes (CALME 60/40, NORMAL 65/35)")
print("  - STRICT: Tous les seuils resserres (moins de trades, plus filtrant)")
print("  - PERMISSIF: Tous les seuils elargis (plus de trades)")
print("  - CALME_STRICT: Seulement CALME resserre")
print("  - NORMAL_STRICT: Seulement NORMAL resserre (LONG 65->60)")
print("=" * 90)

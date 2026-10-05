"""Analyse RSI des 100 derniers trades par regime - Version subprocess"""
import subprocess
import os
import sys

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def run_sql(query):
    """Execute SQL via psql subprocess"""
    env = os.environ.copy()
    env['PGPASSWORD'] = '@Cmtr1di12345'
    env['PGCLIENTENCODING'] = 'UTF8'
    result = subprocess.run(
        ['psql', '-h', 'localhost', '-U', 'postgres', '-d', 'trade_cursor_ml', 
         '-t', '-A', '-F', '|', '-c', query],
        capture_output=True, text=True, env=env, encoding='utf-8', errors='replace'
    )
    if result.returncode != 0:
        print(f"SQL Error: {result.stderr}")
        return []
    lines = [line for line in result.stdout.strip().split('\n') if line.strip()]
    return [line.split('|') for line in lines]

print("=" * 80)
print("ANALYSE RSI DES 100 DERNIERS TRADES")
print("=" * 80)

# 1. PnL global par regime
query1 = '''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    COUNT(*) as trades,
    SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
    ROUND(SUM(net_pnl_usdt)::numeric, 2) as total_pnl_usdt,
    ROUND(AVG(net_pnl_pct)::numeric, 3) as avg_pnl_pct
FROM (
    SELECT * FROM trades 
    WHERE is_live_trade = true AND exit_price IS NOT NULL
    ORDER BY timestamp_exit DESC 
    LIMIT 100
) t
GROUP BY 1
ORDER BY total_pnl_usdt DESC
'''

print("\n1. PNL PAR REGIME (100 derniers trades)")
print("-" * 70)
print(f"{'Regime':<12} {'Trades':<8} {'Wins':<6} {'WR%':<8} {'PnL USDT':<12} {'Avg PnL%':<10}")
print("-" * 70)
for row in run_sql(query1):
    if len(row) >= 6:
        print(f"{row[0]:<12} {row[1]:<8} {row[2]:<6} {row[3]:<8} {row[4]:<12} {row[5]:<10}")

# 2. PnL par regime et direction
query2 = '''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    direction,
    COUNT(*) as trades,
    SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
    ROUND(SUM(net_pnl_usdt)::numeric, 2) as total_pnl_usdt
FROM (
    SELECT * FROM trades 
    WHERE is_live_trade = true AND exit_price IS NOT NULL
    ORDER BY timestamp_exit DESC 
    LIMIT 100
) t
GROUP BY 1, 2
ORDER BY 1, 2
'''

print("\n2. PNL PAR REGIME ET DIRECTION")
print("-" * 70)
print(f"{'Regime':<12} {'Dir':<6} {'Trades':<8} {'Wins':<6} {'WR%':<8} {'PnL USDT':<12}")
print("-" * 70)
for row in run_sql(query2):
    if len(row) >= 6:
        print(f"{row[0]:<12} {row[1]:<6} {row[2]:<8} {row[3]:<6} {row[4]:<8} {row[5]:<12}")

# 3. LONG: PnL par regime et bucket RSI
query3 = '''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    CASE 
        WHEN entry_rsi_1m IS NULL THEN 'NULL'
        WHEN entry_rsi_1m < 40 THEN 'RSI<40'
        WHEN entry_rsi_1m < 50 THEN 'RSI 40-50'
        WHEN entry_rsi_1m < 55 THEN 'RSI 50-55'
        WHEN entry_rsi_1m < 60 THEN 'RSI 55-60'
        WHEN entry_rsi_1m < 65 THEN 'RSI 60-65'
        WHEN entry_rsi_1m < 70 THEN 'RSI 65-70'
        ELSE 'RSI>=70'
    END as rsi_bucket,
    COUNT(*) as trades,
    SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
    ROUND(SUM(net_pnl_usdt)::numeric, 2) as total_pnl_usdt,
    ROUND(AVG(net_pnl_pct)::numeric, 3) as avg_pnl
FROM (
    SELECT * FROM trades 
    WHERE is_live_trade = true AND exit_price IS NOT NULL
    ORDER BY timestamp_exit DESC 
    LIMIT 100
) t
WHERE direction = 'LONG'
GROUP BY 1, 2
ORDER BY 1, 2
'''

print("\n3. LONG: PNL PAR REGIME ET RSI BUCKET")
print("-" * 80)
print(f"{'Regime':<12} {'RSI Bucket':<12} {'N':<5} {'Wins':<5} {'WR%':<8} {'PnL$':<10} {'Avg%':<8}")
print("-" * 80)
for row in run_sql(query3):
    if len(row) >= 7:
        print(f"{row[0]:<12} {row[1]:<12} {row[2]:<5} {row[3]:<5} {row[4]:<8} {row[5]:<10} {row[6]:<8}")

# 4. SHORT: PnL par regime et bucket RSI
query4 = '''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    CASE 
        WHEN entry_rsi_1m IS NULL THEN 'NULL'
        WHEN entry_rsi_1m > 60 THEN 'RSI>60'
        WHEN entry_rsi_1m > 50 THEN 'RSI 50-60'
        WHEN entry_rsi_1m > 45 THEN 'RSI 45-50'
        WHEN entry_rsi_1m > 40 THEN 'RSI 40-45'
        WHEN entry_rsi_1m > 35 THEN 'RSI 35-40'
        WHEN entry_rsi_1m > 30 THEN 'RSI 30-35'
        ELSE 'RSI<=30'
    END as rsi_bucket,
    COUNT(*) as trades,
    SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
    ROUND(SUM(net_pnl_usdt)::numeric, 2) as total_pnl_usdt,
    ROUND(AVG(net_pnl_pct)::numeric, 3) as avg_pnl
FROM (
    SELECT * FROM trades 
    WHERE is_live_trade = true AND exit_price IS NOT NULL
    ORDER BY timestamp_exit DESC 
    LIMIT 100
) t
WHERE direction = 'SHORT'
GROUP BY 1, 2
ORDER BY 1, 2
'''

print("\n4. SHORT: PNL PAR REGIME ET RSI BUCKET")
print("-" * 80)
print(f"{'Regime':<12} {'RSI Bucket':<12} {'N':<5} {'Wins':<5} {'WR%':<8} {'PnL$':<10} {'Avg%':<8}")
print("-" * 80)
for row in run_sql(query4):
    if len(row) >= 7:
        print(f"{row[0]:<12} {row[1]:<12} {row[2]:<5} {row[3]:<5} {row[4]:<8} {row[5]:<10} {row[6]:<8}")

# 5. Impact simulation des seuils actuels
print("\n" + "=" * 80)
print("5. SIMULATION IMPACT SEUILS RSI ACTUELS")
print("=" * 80)

thresholds = {
    'CALME': {'long_max': 60, 'short_min': 40},
    'NORMAL': {'long_max': 65, 'short_min': 35},
    'VOLATILE': {'long_max': 70, 'short_min': 30},
    'CHOPPY': {'long_max': 55, 'short_min': 45},
}

for regime, th in thresholds.items():
    query5 = f'''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN direction='LONG' AND entry_rsi_1m > {th['long_max']} THEN 1 ELSE 0 END) as long_blocked,
        SUM(CASE WHEN direction='SHORT' AND entry_rsi_1m < {th['short_min']} THEN 1 ELSE 0 END) as short_blocked,
        SUM(CASE WHEN direction='LONG' AND entry_rsi_1m > {th['long_max']} AND net_pnl_pct < 0 THEN 1 ELSE 0 END) as long_blocked_losses,
        SUM(CASE WHEN direction='SHORT' AND entry_rsi_1m < {th['short_min']} AND net_pnl_pct < 0 THEN 1 ELSE 0 END) as short_blocked_losses,
        ROUND(SUM(CASE WHEN direction='LONG' AND entry_rsi_1m > {th['long_max']} THEN net_pnl_usdt ELSE 0 END)::numeric, 2) as long_blocked_pnl,
        ROUND(SUM(CASE WHEN direction='SHORT' AND entry_rsi_1m < {th['short_min']} THEN net_pnl_usdt ELSE 0 END)::numeric, 2) as short_blocked_pnl
    FROM (
        SELECT * FROM trades 
        WHERE is_live_trade = true AND exit_price IS NOT NULL
        ORDER BY timestamp_exit DESC 
        LIMIT 100
    ) t
    WHERE COALESCE(entry_market_regime, 'UNKNOWN') = '{regime}' AND entry_rsi_1m IS NOT NULL
    '''
    rows = run_sql(query5)
    if rows and len(rows[0]) >= 7:
        row = rows[0]
        total = int(row[0]) if row[0] else 0
        if total > 0:
            print(f"\n{regime} (seuils: LONG<={th['long_max']}, SHORT>={th['short_min']}):")
            print(f"  Total trades: {total}")
            lb = int(row[1]) if row[1] else 0
            sb = int(row[2]) if row[2] else 0
            lbl = int(row[3]) if row[3] else 0
            sbl = int(row[4]) if row[4] else 0
            lbp = row[5] if row[5] else '0'
            sbp = row[6] if row[6] else '0'
            print(f"  LONG bloques (RSI>{th['long_max']}): {lb} dont {lbl} pertes -> evite {lbp}$")
            print(f"  SHORT bloques (RSI<{th['short_min']}): {sb} dont {sbl} pertes -> evite {sbp}$")

# 6. Recommandations
print("\n" + "=" * 80)
print("6. RSI MOYEN PAR REGIME (wins vs losses)")
print("=" * 80)

for regime in ['CALME', 'NORMAL', 'VOLATILE', 'CHOPPY']:
    query6 = f'''
    SELECT 
        ROUND(AVG(CASE WHEN direction='LONG' AND net_pnl_pct < 0 THEN entry_rsi_1m END)::numeric, 1) as avg_rsi_long_losses,
        ROUND(AVG(CASE WHEN direction='LONG' AND net_pnl_pct > 0 THEN entry_rsi_1m END)::numeric, 1) as avg_rsi_long_wins,
        ROUND(AVG(CASE WHEN direction='SHORT' AND net_pnl_pct < 0 THEN entry_rsi_1m END)::numeric, 1) as avg_rsi_short_losses,
        ROUND(AVG(CASE WHEN direction='SHORT' AND net_pnl_pct > 0 THEN entry_rsi_1m END)::numeric, 1) as avg_rsi_short_wins
    FROM (
        SELECT * FROM trades 
        WHERE is_live_trade = true AND exit_price IS NOT NULL
        ORDER BY timestamp_exit DESC 
        LIMIT 100
    ) t
    WHERE COALESCE(entry_market_regime, 'UNKNOWN') = '{regime}' AND entry_rsi_1m IS NOT NULL
    '''
    rows = run_sql(query6)
    if rows and len(rows[0]) >= 4:
        row = rows[0]
        if any(row):
            print(f"\n{regime}:")
            print(f"  LONG: losses avg RSI={row[0]}, wins avg RSI={row[1]}")
            print(f"  SHORT: losses avg RSI={row[2]}, wins avg RSI={row[3]}")

print("\n" + "=" * 80)
print("FIN ANALYSE")
print("=" * 80)

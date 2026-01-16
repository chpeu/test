"""Analyse RSI des 100 derniers trades par regime"""
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
    env['PGPASSWORD'] = 'music'
    env['PGCLIENTENCODING'] = 'UTF8'
    result = subprocess.run(
        ['psql', '-h', 'localhost', '-U', 'postgres', '-d', 'trade_cursor_ml', 
         '-t', '-A', '-F', '|', '-c', query],
        capture_output=True, text=True, env=env, encoding='utf-8', errors='replace'
    )
    if result.returncode != 0:
        print(f"SQL Error: {result.stderr}")
        return []
    return [line.split('|') for line in result.stdout.strip().split('\n') if line]

print("=" * 80)
print("ANALYSE RSI DES 100 DERNIERS TRADES")
print("=" * 80)

# 1. PnL global par regime
cur.execute('''
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
    ORDER BY closed_at DESC 
    LIMIT 100
) t
GROUP BY 1
ORDER BY total_pnl_usdt DESC
''')

print("\n1. PNL PAR REGIME (100 derniers trades)")
print("-" * 70)
print(f"{'Regime':<12} {'Trades':<8} {'Wins':<6} {'WR%':<8} {'PnL USDT':<12} {'Avg PnL%':<10}")
print("-" * 70)
for row in cur.fetchall():
    print(f"{row[0]:<12} {row[1]:<8} {row[2]:<6} {row[3]:<8} {row[4]:<12} {row[5]:<10}")

# 2. PnL par regime et direction
cur.execute('''
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
    ORDER BY closed_at DESC 
    LIMIT 100
) t
GROUP BY 1, 2
ORDER BY 1, 2
''')

print("\n2. PNL PAR REGIME ET DIRECTION")
print("-" * 70)
print(f"{'Regime':<12} {'Dir':<6} {'Trades':<8} {'Wins':<6} {'WR%':<8} {'PnL USDT':<12}")
print("-" * 70)
for row in cur.fetchall():
    print(f"{row[0]:<12} {row[1]:<6} {row[2]:<8} {row[3]:<6} {row[4]:<8} {row[5]:<12}")

# 3. LONG: PnL par regime et bucket RSI
cur.execute('''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    CASE 
        WHEN entry_rsi IS NULL THEN 'NULL'
        WHEN entry_rsi < 40 THEN 'RSI<40'
        WHEN entry_rsi < 50 THEN 'RSI 40-50'
        WHEN entry_rsi < 55 THEN 'RSI 50-55'
        WHEN entry_rsi < 60 THEN 'RSI 55-60'
        WHEN entry_rsi < 65 THEN 'RSI 60-65'
        WHEN entry_rsi < 70 THEN 'RSI 65-70'
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
    ORDER BY closed_at DESC 
    LIMIT 100
) t
WHERE direction = 'LONG'
GROUP BY 1, 2
ORDER BY 1, 2
''')

print("\n3. LONG: PNL PAR REGIME ET RSI BUCKET")
print("-" * 80)
print(f"{'Regime':<12} {'RSI Bucket':<12} {'N':<5} {'Wins':<5} {'WR%':<8} {'PnL$':<10} {'Avg%':<8}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{row[0]:<12} {row[1]:<12} {row[2]:<5} {row[3]:<5} {row[4]:<8} {row[5]:<10} {row[6]:<8}")

# 4. SHORT: PnL par regime et bucket RSI
cur.execute('''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    CASE 
        WHEN entry_rsi IS NULL THEN 'NULL'
        WHEN entry_rsi > 60 THEN 'RSI>60'
        WHEN entry_rsi > 50 THEN 'RSI 50-60'
        WHEN entry_rsi > 45 THEN 'RSI 45-50'
        WHEN entry_rsi > 40 THEN 'RSI 40-45'
        WHEN entry_rsi > 35 THEN 'RSI 35-40'
        WHEN entry_rsi > 30 THEN 'RSI 30-35'
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
    ORDER BY closed_at DESC 
    LIMIT 100
) t
WHERE direction = 'SHORT'
GROUP BY 1, 2
ORDER BY 1, 2
''')

print("\n4. SHORT: PNL PAR REGIME ET RSI BUCKET")
print("-" * 80)
print(f"{'Regime':<12} {'RSI Bucket':<12} {'N':<5} {'Wins':<5} {'WR%':<8} {'PnL$':<10} {'Avg%':<8}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{row[0]:<12} {row[1]:<12} {row[2]:<5} {row[3]:<5} {row[4]:<8} {row[5]:<10} {row[6]:<8}")

# 5. Impact des seuils actuels (simulation)
print("\n" + "=" * 80)
print("5. SIMULATION IMPACT SEUILS RSI ACTUELS")
print("=" * 80)

# Seuils actuels
thresholds = {
    'CALME': {'long_max': 60, 'short_min': 40},
    'NORMAL': {'long_max': 65, 'short_min': 35},
    'VOLATILE': {'long_max': 70, 'short_min': 30},
    'CHOPPY': {'long_max': 55, 'short_min': 45},
}

for regime, th in thresholds.items():
    cur.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN direction='LONG' AND entry_rsi > %s THEN 1 ELSE 0 END) as long_blocked,
        SUM(CASE WHEN direction='SHORT' AND entry_rsi < %s THEN 1 ELSE 0 END) as short_blocked,
        SUM(CASE WHEN direction='LONG' AND entry_rsi > %s AND net_pnl_pct < 0 THEN 1 ELSE 0 END) as long_blocked_were_losses,
        SUM(CASE WHEN direction='SHORT' AND entry_rsi < %s AND net_pnl_pct < 0 THEN 1 ELSE 0 END) as short_blocked_were_losses,
        ROUND(SUM(CASE WHEN direction='LONG' AND entry_rsi > %s THEN net_pnl_usdt ELSE 0 END)::numeric, 2) as long_blocked_pnl,
        ROUND(SUM(CASE WHEN direction='SHORT' AND entry_rsi < %s THEN net_pnl_usdt ELSE 0 END)::numeric, 2) as short_blocked_pnl
    FROM (
        SELECT * FROM trades 
        WHERE is_live_trade = true AND exit_price IS NOT NULL
        ORDER BY closed_at DESC 
        LIMIT 100
    ) t
    WHERE COALESCE(entry_market_regime, 'UNKNOWN') = %s AND entry_rsi IS NOT NULL
    ''', (th['long_max'], th['short_min'], th['long_max'], th['short_min'], th['long_max'], th['short_min'], regime))
    
    row = cur.fetchone()
    if row and row[0] and row[0] > 0:
        print(f"\n{regime} (seuils: LONG<={th['long_max']}, SHORT>={th['short_min']}):")
        print(f"  Total trades: {row[0]}")
        print(f"  LONG bloques (RSI>{th['long_max']}): {row[1]} dont {row[3]} etaient des pertes -> evite {row[5]}$")
        print(f"  SHORT bloques (RSI<{th['short_min']}): {row[2]} dont {row[4]} etaient des pertes -> evite {row[6]}$")

# 6. Recommandations
print("\n" + "=" * 80)
print("6. RECOMMANDATIONS AJUSTEMENT SEUILS RSI")
print("=" * 80)

# Analyser les seuils optimaux par régime
for regime in ['CALME', 'NORMAL', 'VOLATILE', 'CHOPPY']:
    cur.execute('''
    SELECT 
        ROUND(AVG(CASE WHEN direction='LONG' AND net_pnl_pct < 0 THEN entry_rsi END)::numeric, 1) as avg_rsi_long_losses,
        ROUND(AVG(CASE WHEN direction='LONG' AND net_pnl_pct > 0 THEN entry_rsi END)::numeric, 1) as avg_rsi_long_wins,
        ROUND(AVG(CASE WHEN direction='SHORT' AND net_pnl_pct < 0 THEN entry_rsi END)::numeric, 1) as avg_rsi_short_losses,
        ROUND(AVG(CASE WHEN direction='SHORT' AND net_pnl_pct > 0 THEN entry_rsi END)::numeric, 1) as avg_rsi_short_wins
    FROM (
        SELECT * FROM trades 
        WHERE is_live_trade = true AND exit_price IS NOT NULL
        ORDER BY closed_at DESC 
        LIMIT 100
    ) t
    WHERE COALESCE(entry_market_regime, 'UNKNOWN') = %s AND entry_rsi IS NOT NULL
    ''', (regime,))
    
    row = cur.fetchone()
    if row and any(row):
        print(f"\n{regime}:")
        print(f"  LONG losses avg RSI: {row[0]}, LONG wins avg RSI: {row[1]}")
        print(f"  SHORT losses avg RSI: {row[2]}, SHORT wins avg RSI: {row[3]}")
        
        # Recommandation
        if row[0] and row[1]:
            suggested_long = int((row[0] + row[1]) / 2) if row[0] > row[1] else int(row[0] - 2)
            print(f"  -> Suggestion LONG max: {suggested_long} (couper entre wins et losses)")
        if row[2] and row[3]:
            suggested_short = int((row[2] + row[3]) / 2) if row[2] < row[3] else int(row[2] + 2)
            print(f"  -> Suggestion SHORT min: {suggested_short}")

conn.close()
print("\n" + "=" * 80)
print("FIN ANALYSE")
print("=" * 80)

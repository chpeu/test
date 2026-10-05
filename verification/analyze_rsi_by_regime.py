"""Analyse RSI par regime pour determiner les seuils optimaux"""
import os
import sys
import psycopg2

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Get password from env or use empty
pg_password = os.environ.get('POSTGRES_PASSWORD', '')

# Simple connection
conn = psycopg2.connect(
    host='localhost',
    database='trade_cursor_ml',
    user='postgres',
    password=pg_password
)
cur = conn.cursor()

# Analyze RSI distribution by regime and outcome (win/loss)
cur.execute('''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    direction,
    CASE WHEN net_pnl_pct > 0 THEN 'WIN' ELSE 'LOSS' END as outcome,
    COUNT(*) as trades,
    ROUND(AVG(entry_rsi)::numeric, 1) as avg_rsi,
    ROUND(MIN(entry_rsi)::numeric, 1) as min_rsi,
    ROUND(MAX(entry_rsi)::numeric, 1) as max_rsi,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY entry_rsi)::numeric, 1) as p25_rsi,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY entry_rsi)::numeric, 1) as p75_rsi
FROM trades
WHERE entry_rsi IS NOT NULL 
  AND is_live_trade = true
  AND closed_at > NOW() - INTERVAL '30 days'
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3
''')

print('=== RSI Distribution par Regime/Direction/Outcome (30j) ===')
print(f'{"Regime":<12} {"Dir":<6} {"Result":<5} {"N":<4} {"Avg":<6} {"Min":<6} {"Max":<6} {"P25":<6} {"P75":<6}')
print('-' * 70)
for row in cur.fetchall():
    print(f'{row[0]:<12} {row[1]:<6} {row[2]:<5} {row[3]:<4} {row[4]:<6} {row[5]:<6} {row[6]:<6} {row[7]:<6} {row[8]:<6}')

print()

# Detailed: LONG losses with high RSI by regime
cur.execute('''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    COUNT(*) FILTER (WHERE entry_rsi > 60) as rsi_60_plus,
    COUNT(*) FILTER (WHERE entry_rsi > 65) as rsi_65_plus,
    COUNT(*) FILTER (WHERE entry_rsi > 70) as rsi_70_plus,
    COUNT(*) as total_long_losses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE entry_rsi > 60) / NULLIF(COUNT(*), 0), 1) as pct_60_plus
FROM trades
WHERE direction = 'LONG'
  AND net_pnl_pct < 0
  AND entry_rsi IS NOT NULL
  AND is_live_trade = true
  AND closed_at > NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1
''')

print('=== LONG Losses avec RSI eleve (candidats a bloquer) ===')
print(f'{"Regime":<12} {"RSI>60":<8} {"RSI>65":<8} {"RSI>70":<8} {"Total":<8} {"% >60":<8}')
print('-' * 55)
for row in cur.fetchall():
    print(f'{row[0]:<12} {row[1]:<8} {row[2]:<8} {row[3]:<8} {row[4]:<8} {row[5]:<8}')

print()

# SHORT losses with low RSI by regime  
cur.execute('''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    COUNT(*) FILTER (WHERE entry_rsi < 40) as rsi_under_40,
    COUNT(*) FILTER (WHERE entry_rsi < 35) as rsi_under_35,
    COUNT(*) FILTER (WHERE entry_rsi < 30) as rsi_under_30,
    COUNT(*) as total_short_losses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE entry_rsi < 40) / NULLIF(COUNT(*), 0), 1) as pct_under_40
FROM trades
WHERE direction = 'SHORT'
  AND net_pnl_pct < 0
  AND entry_rsi IS NOT NULL
  AND is_live_trade = true
  AND closed_at > NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1
''')

print('=== SHORT Losses avec RSI bas (candidats a bloquer) ===')
print(f'{"Regime":<12} {"RSI<40":<8} {"RSI<35":<8} {"RSI<30":<8} {"Total":<8} {"% <40":<8}')
print('-' * 55)
for row in cur.fetchall():
    print(f'{row[0]:<12} {row[1]:<8} {row[2]:<8} {row[3]:<8} {row[4]:<8} {row[5]:<8}')

print()

# Win rate by RSI bucket per regime for LONG
cur.execute('''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    CASE 
        WHEN entry_rsi < 40 THEN 'RSI<40'
        WHEN entry_rsi < 50 THEN 'RSI 40-50'
        WHEN entry_rsi < 60 THEN 'RSI 50-60'
        WHEN entry_rsi < 65 THEN 'RSI 60-65'
        WHEN entry_rsi < 70 THEN 'RSI 65-70'
        ELSE 'RSI>70'
    END as rsi_bucket,
    COUNT(*) as trades,
    SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
    ROUND(AVG(net_pnl_pct)::numeric, 3) as avg_pnl
FROM trades
WHERE direction = 'LONG'
  AND entry_rsi IS NOT NULL
  AND is_live_trade = true
  AND closed_at > NOW() - INTERVAL '30 days'
GROUP BY 1, 2
HAVING COUNT(*) >= 3
ORDER BY 1, 2
''')

print('=== LONG Winrate par RSI Bucket et Regime (min 3 trades) ===')
print(f'{"Regime":<12} {"RSI Bucket":<12} {"N":<5} {"Wins":<5} {"WR%":<8} {"Avg PnL":<8}')
print('-' * 55)
for row in cur.fetchall():
    print(f'{row[0]:<12} {row[1]:<12} {row[2]:<5} {row[3]:<5} {row[4]:<8} {row[5]:<8}')

print()

# Win rate by RSI bucket per regime for SHORT
cur.execute('''
SELECT 
    COALESCE(entry_market_regime, 'UNKNOWN') as regime,
    CASE 
        WHEN entry_rsi > 60 THEN 'RSI>60'
        WHEN entry_rsi > 50 THEN 'RSI 50-60'
        WHEN entry_rsi > 40 THEN 'RSI 40-50'
        WHEN entry_rsi > 35 THEN 'RSI 35-40'
        WHEN entry_rsi > 30 THEN 'RSI 30-35'
        ELSE 'RSI<30'
    END as rsi_bucket,
    COUNT(*) as trades,
    SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_pct > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
    ROUND(AVG(net_pnl_pct)::numeric, 3) as avg_pnl
FROM trades
WHERE direction = 'SHORT'
  AND entry_rsi IS NOT NULL
  AND is_live_trade = true
  AND closed_at > NOW() - INTERVAL '30 days'
GROUP BY 1, 2
HAVING COUNT(*) >= 3
ORDER BY 1, 2
''')

print('=== SHORT Winrate par RSI Bucket et Regime (min 3 trades) ===')
print(f'{"Regime":<12} {"RSI Bucket":<12} {"N":<5} {"Wins":<5} {"WR%":<8} {"Avg PnL":<8}')
print('-' * 55)
for row in cur.fetchall():
    print(f'{row[0]:<12} {row[1]:<12} {row[2]:<5} {row[3]:<5} {row[4]:<8} {row[5]:<8}')

conn.close()

print()
print('=== RECOMMANDATIONS SEUILS RSI PAR REGIME ===')
print('CALME:    rsi_final_long_max=60, rsi_final_short_min=40 (strict)')
print('NORMAL:   rsi_final_long_max=65, rsi_final_short_min=35 (standard)')
print('VOLATILE: rsi_final_long_max=70, rsi_final_short_min=30 (permissif)')
print('CHOPPY:   rsi_final_long_max=55, rsi_final_short_min=45 (tres strict)')

#!/usr/bin/env python3
"""Analyse de performance des derniers trades"""

from dotenv import load_dotenv
load_dotenv()
import os
import psycopg2

conn = psycopg2.connect(
    host=os.environ.get('POSTGRES_HOST', 'localhost'),
    port=os.environ.get('POSTGRES_PORT', '5432'),
    database=os.environ.get('POSTGRES_DB', 'trade_cursor_ml'),
    user=os.environ.get('POSTGRES_USER', 'postgres'),
    password=os.environ.get('POSTGRES_PASSWORD', '')
)
cur = conn.cursor()

print('='*70)
print('ANALYSE PERFORMANCE - 11 DERNIERS TRADES')
print('='*70)

# Recuperer les 11 derniers trades
cur.execute('''
    SELECT 
        t.symbol,
        t.direction,
        t.exit_reason,
        t.net_pnl_pct * 100 as pnl_pct,
        t.net_pnl_usdt,
        t.duration_seconds,
        t.entry_price,
        t.exit_price,
        t.win,
        m.stagnation_positive_triggered,
        m.market_volatility_state,
        m.be_triggered,
        m.trailing_activated,
        t.created_at
    FROM trades t
    LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
    ORDER BY t.created_at DESC
    LIMIT 11
''')

rows = cur.fetchall()

print('\nDETAIL DES TRADES:')
print('-'*70)

total_pnl_pct = 0
total_pnl_usdt = 0
wins = 0
losses = 0
exit_reasons = {}

for i, row in enumerate(rows, 1):
    symbol = row[0]
    direction = row[1]
    exit_reason = row[2]
    pnl_pct = row[3] or 0
    pnl_usdt = row[4] or 0
    duration = row[5] or 0
    win = row[8]
    volatility = row[10] or '-'
    
    total_pnl_pct += pnl_pct
    total_pnl_usdt += pnl_usdt
    
    if win:
        wins += 1
    else:
        losses += 1
    
    if exit_reason not in exit_reasons:
        exit_reasons[exit_reason] = {'count': 0, 'wins': 0, 'pnl': 0}
    exit_reasons[exit_reason]['count'] += 1
    exit_reasons[exit_reason]['pnl'] += pnl_pct
    if win:
        exit_reasons[exit_reason]['wins'] += 1
    
    duration_min = duration / 60
    pnl_sign = '+' if pnl_pct >= 0 else ''
    print(f'{i:2}. {symbol:18} {direction:5} | {exit_reason:20} | {pnl_sign}{pnl_pct:6.2f}% | {duration_min:5.1f}min | {volatility:6}')

print('\n' + '='*70)
print('RESUME STATISTIQUE')
print('='*70)

winrate = (wins / len(rows) * 100) if rows and len(rows) > 0 else 0
avg_pnl = total_pnl_pct / len(rows) if rows and len(rows) > 0 else 0

print(f'  Total trades:        {len(rows)}')
print(f'  Wins / Losses:       {wins} / {losses}')
print(f'  Winrate:             {winrate:.1f}%')
print(f'  PnL total:           {total_pnl_pct:+.2f}% ({total_pnl_usdt:+.2f} USDT)')
print(f'  PnL moyen/trade:     {avg_pnl:+.3f}%')

print('\n' + '='*70)
print('PERFORMANCE PAR EXIT REASON')
print('='*70)

for reason, data in sorted(exit_reasons.items(), key=lambda x: -x[1]['count']):
    count = data['count']
    w = data['wins']
    pnl = data['pnl']
    wr = (w/count*100) if count else 0
    avg = pnl/count if count else 0
    print(f'  {reason:20}: {count:2} trades | WR={wr:5.1f}% | Avg={avg:+6.3f}%')

# Analyser correlation volatilite/performance
print('\n' + '='*70)
print('PERFORMANCE PAR VOLATILITE')
print('='*70)

cur.execute('''
    SELECT 
        m.market_volatility_state,
        COUNT(*) as count,
        SUM(CASE WHEN t.win THEN 1 ELSE 0 END) as wins,
        AVG(t.net_pnl_pct) * 100 as avg_pnl
    FROM trades t
    JOIN trade_atr_metrics m ON t.id = m.trade_id
    WHERE t.id IN (SELECT id FROM trades ORDER BY created_at DESC LIMIT 11)
    GROUP BY m.market_volatility_state
    ORDER BY count DESC
''')

for row in cur.fetchall():
    vol = row[0] or 'N/A'
    count = row[1]
    w = row[2]
    avg = row[3] or 0
    wr = (w/count*100) if count else 0
    print(f'  {vol:8}: {count:2} trades | WR={wr:5.1f}% | Avg={avg:+6.3f}%')

conn.close()

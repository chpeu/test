#!/usr/bin/env python3
"""Analyse des trades de l'après-midi"""
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('data/analytics.db')
c = conn.cursor()

# Tous les trades récents
c.execute('''
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) as wins,
    SUM(net_pnl_usdt) as pnl,
    AVG(ml_confidence) as avg_conf,
    MIN(timestamp), MAX(timestamp)
FROM trades 
WHERE datetime(timestamp) >= datetime('now', '-8 hours')
''')
r = c.fetchone()
if r and len(r) == 6:
    total, wins, pnl, avg_conf, min_ts, max_ts = r
else:
    # Pas de résultats, valeurs par défaut
    total, wins, pnl, avg_conf, min_ts, max_ts = 0, 0, 0, 0, None, None
print(f'=== TOUS LES TRADES (8h) ===')
print(f'Total: {total} | Wins: {wins or 0}')
if total and total > 0:
    print(f'Winrate: {(wins or 0)/total*100:.1f}%')
    print(f'PnL: {pnl or 0:.4f} USDT')
    if avg_conf:
        print(f'Conf ML moy: {avg_conf:.1f}%')
print(f'Range: {min_ts} -> {max_ts}')

# Modes
print(f'\n=== MODES ===')
c.execute('''
SELECT is_live_trade, is_dry_run, COUNT(*) 
FROM trades 
WHERE datetime(timestamp) >= datetime('now', '-8 hours') 
GROUP BY is_live_trade, is_dry_run
''')
for r in c.fetchall():
    print(f'  is_live={r[0]}, is_dry_run={r[1]}: {r[2]} trades')

# Par raison
print(f'\n=== PAR RAISON DE SORTIE ===')
c.execute('''
SELECT 
    reason,
    COUNT(*) as cnt,
    SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) as w,
    SUM(net_pnl_usdt) as p,
    AVG(ml_confidence) as conf
FROM trades 
WHERE datetime(timestamp) >= datetime('now', '-8 hours')
GROUP BY reason
ORDER BY cnt DESC
''')
for row in c.fetchall():
    reason, cnt, w, p, conf = row
    wr = ((w or 0)/cnt*100) if cnt > 0 else 0
    conf_str = f'{conf:.0f}%' if conf else 'N/A'
    print(f'  {reason}: {cnt} trades, WR={wr:.0f}%, PnL={p or 0:.4f}, conf={conf_str}')

# Derniers trades
print(f'\n=== 25 DERNIERS TRADES ===')
c.execute('''
SELECT symbol, direction, reason, net_pnl_usdt, net_pnl_pct, ml_confidence, is_live_trade, timestamp
FROM trades 
ORDER BY timestamp DESC
LIMIT 25
''')
for row in c.fetchall():
    sym, dir, reason, pnl, pct, conf, live, ts = row
    conf_str = f'{conf:.0f}%' if conf else 'N/A'
    live_str = 'LIVE' if live else 'DRY'
    pnl_val = pnl or 0
    pct_val = pct or 0
    result = '✅' if pnl_val > 0 else '❌'
    print(f'  {result} [{live_str}] {sym} {dir} -> {reason}: {pnl_val:.4f} ({pct_val:.2f}%) conf={conf_str}')

# Statistiques par confidence
print(f'\n=== WINRATE PAR TRANCHE DE CONFIDENCE ===')
c.execute('''
SELECT 
    CASE 
        WHEN ml_confidence < 45 THEN '< 45%'
        WHEN ml_confidence < 50 THEN '45-50%'
        WHEN ml_confidence < 55 THEN '50-55%'
        WHEN ml_confidence < 60 THEN '55-60%'
        ELSE '>= 60%'
    END as conf_range,
    COUNT(*) as cnt,
    SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) as w,
    SUM(net_pnl_usdt) as p
FROM trades 
WHERE datetime(timestamp) >= datetime('now', '-8 hours')
AND ml_confidence IS NOT NULL
GROUP BY conf_range
ORDER BY conf_range
''')
for row in c.fetchall():
    conf_range, cnt, w, p = row
    wr = ((w or 0)/cnt*100) if cnt > 0 else 0
    print(f'  {conf_range}: {cnt} trades, WR={wr:.0f}%, PnL={p or 0:.4f}')

conn.close()

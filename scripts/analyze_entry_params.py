#!/usr/bin/env python3
"""Analyse des parametres d'entree actuels"""

from dotenv import load_dotenv
load_dotenv()
import os
import psycopg2
import json

conn = psycopg2.connect(
    host=os.environ.get('POSTGRES_HOST', 'localhost'),
    port=os.environ.get('POSTGRES_PORT', '5432'),
    database=os.environ.get('POSTGRES_DB', 'trade_cursor_ml'),
    user=os.environ.get('POSTGRES_USER', 'postgres'),
    password=os.environ.get('POSTGRES_PASSWORD', '')
)
cur = conn.cursor()

# Analyser le dernier config_snapshot
cur.execute('''
    SELECT config_snapshot FROM trades 
    WHERE config_snapshot IS NOT NULL 
    ORDER BY created_at DESC LIMIT 1
''')
row = cur.fetchone()
if row and row[0]:
    config = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    print('PARAMETRES ACTUELS DE PRISE DE TRADE')
    print('='*60)
    
    print(f"\nSCORE MINIMUM:")
    print(f"  min_score_required: {config.get('min_score_required', 'N/A')}")
    
    print(f"\nFILTRES ATR:")
    print(f"  optimal_atr_min_1m: {config.get('optimal_atr_min_1m', 'N/A')}")
    print(f"  optimal_atr_max_1m: {config.get('optimal_atr_max_1m', 'N/A')}")
    print(f"  optimal_atr_min_5m: {config.get('optimal_atr_min_5m', 'N/A')}")
    print(f"  optimal_atr_max_5m: {config.get('optimal_atr_max_5m', 'N/A')}")
    
    print(f"\nFILTRES RSI:")
    print(f"  rsi_filter_enabled: {config.get('rsi_filter_enabled', 'N/A')}")
    print(f"  rsi_long_max: {config.get('rsi_long_max', 'N/A')}")
    print(f"  rsi_short_min: {config.get('rsi_short_min', 'N/A')}")
    
    print(f"\nFILTRES VOLUME:")
    print(f"  volume_multiplier: {config.get('volume_multiplier', 'N/A')}")
    
    print(f"\nCONFLUENCE:")
    print(f"  use_confluence: {config.get('use_confluence', 'N/A')}")
    print(f"  snr_threshold: {config.get('snr_threshold', 'N/A')}")

# Frequence trades 7 jours
print('\n' + '='*60)
print('FREQUENCE DE TRADES (7 derniers jours)')
print('='*60)

cur.execute('''
    SELECT DATE(created_at) as day, COUNT(*) as trades
    FROM trades
    WHERE created_at > NOW() - INTERVAL '7 days'
    GROUP BY DATE(created_at)
    ORDER BY day DESC
''')

total_trades = 0
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} trades")
    total_trades += row[1]

# Stats 24h
cur.execute('SELECT COUNT(*) FROM scan_logs WHERE created_at > NOW() - INTERVAL %s', ('24 hours',))
scans = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM opportunities WHERE created_at > NOW() - INTERVAL %s', ('24 hours',))
opps = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM trades WHERE created_at > NOW() - INTERVAL %s', ('24 hours',))
trades_24h = cur.fetchone()[0]

print(f"\nDERNIERES 24H:")
print(f"  Scans effectues: {scans}")
print(f"  Opportunites detectees: {opps}")
print(f"  Trades executes: {trades_24h}")
if opps > 0:
    print(f"  Taux conversion opps->trades: {trades_24h/opps*100:.1f}%")

# Analyser les scores des trades recents
print('\n' + '='*60)
print('DISTRIBUTION DES SCORES (11 derniers trades)')
print('='*60)

cur.execute('''
    SELECT entry_score, entry_min_score_required, symbol
    FROM trades
    ORDER BY created_at DESC
    LIMIT 11
''')

scores = []
for row in cur.fetchall():
    score = row[0]
    min_req = row[1]
    symbol = row[2]
    if score:
        scores.append(score)
        margin = score - (min_req or 0) if min_req else None
        print(f"  {symbol:18} score={score:.1f} (min={min_req}, marge={margin:.1f if margin else 'N/A'})")

if scores:
    print(f"\n  Score moyen: {sum(scores)/len(scores):.1f}")
    print(f"  Score min: {min(scores):.1f}")
    print(f"  Score max: {max(scores):.1f}")

conn.close()

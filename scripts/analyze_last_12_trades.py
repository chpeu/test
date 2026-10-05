#!/usr/bin/env python3
"""Analyse des trades FIXE avec séparation ancienne/nouvelle config"""

import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone, timedelta

load_dotenv(Path(__file__).parent.parent / '.env')

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', 'localhost'),
    port=int(os.getenv('POSTGRES_PORT', '5432')),
    database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    user=os.getenv('POSTGRES_USER', 'postgres'),
    password=os.getenv('POSTGRES_PASSWORD', '')
)
cur = conn.cursor()

# Point de séparation: trade HBAR 04:39:32 = nouvelle config
# Ancienne config: SL 0.25%, BE/trailing trigger 0.1%
CONFIG_CHANGE_TIME = datetime(2026, 1, 19, 4, 39, 32, tzinfo=timezone(timedelta(hours=1)))

cur.execute('''
    SELECT id, symbol, direction, pnl_pct, pnl_usdt, 
           exit_reason, tp_sl_mode, 
           max_favorable_excursion, max_adverse_excursion,
           setup_score, timestamp_exit,
           EXTRACT(EPOCH FROM (timestamp_exit - created_at)) as duration_sec
    FROM trades 
    WHERE exit_price IS NOT NULL 
    ORDER BY timestamp_exit DESC 
    LIMIT 15
''')
rows = cur.fetchall()
cols = [d[0] for d in cur.description]

old_config_trades = []
new_config_trades = []

for r in rows:
    d = dict(zip(cols, r))
    if d['timestamp_exit'] >= CONFIG_CHANGE_TIME:
        new_config_trades.append(d)
    else:
        old_config_trades.append(d)

def analyze_trades(trades, label, config_info):
    if not trades:
        print(f"Aucun trade pour {label}")
        return
    
    print('=' * 110)
    print(f"{label} ({len(trades)} trades) - Config: {config_info}")
    print('=' * 110)
    
    wins = 0
    total_pnl = 0
    mfe_sum = 0
    mae_sum = 0
    trailing_trigger = 0.1  # Ancienne config
    
    for d in trades:
        pnl = d['pnl_pct'] or 0
        mfe = d['max_favorable_excursion'] or 0
        mae = d['max_adverse_excursion'] or 0
        dur = d['duration_sec'] or 0
        score = d['setup_score'] or 0
        
        total_pnl += pnl
        mfe_sum += mfe
        mae_sum += mae
        if pnl > 0:
            wins += 1
        
        status = 'WIN ' if pnl > 0 else 'LOSS'
        exit_short = (d['exit_reason'] or 'UNK')[:20]
        trailing_status = 'T' if mfe >= trailing_trigger else '-'
        ts = d['timestamp_exit'].strftime('%H:%M:%S')
        print(f"{ts} {status} {d['symbol']:22} {d['direction']:5} PnL:{pnl:+.3f}% MFE:{mfe:.3f}%[{trailing_status}] MAE:{mae:.3f}% sc:{score:.1f} | {exit_short}")
    
    n = len(trades)
    print()
    print(f"Winrate:   {wins}/{n} ({wins/n*100:.1f}%)")
    print(f"PnL total: {total_pnl:.3f}%")
    print(f"PnL moyen: {total_pnl/n:.4f}%")
    print(f"MFE moyen: {mfe_sum/n:.4f}%")
    print(f"MAE moyen: {mae_sum/n:.4f}%")
    print(f"Giveback:  {(mfe_sum/n - total_pnl/n):.4f}%")
    
    # Analyse MFE vs trailing trigger
    mfe_above_trigger = sum(1 for d in trades if (d['max_favorable_excursion'] or 0) >= trailing_trigger)
    mfe_below_trigger = n - mfe_above_trigger
    
    wins_above = sum(1 for d in trades if (d['max_favorable_excursion'] or 0) >= trailing_trigger and (d['pnl_pct'] or 0) > 0)
    wins_below = sum(1 for d in trades if (d['max_favorable_excursion'] or 0) < trailing_trigger and (d['pnl_pct'] or 0) > 0)
    
    print()
    print(f"MFE >= {trailing_trigger}% (trailing activé):  {mfe_above_trigger} trades, {wins_above} wins ({wins_above/mfe_above_trigger*100 if mfe_above_trigger else 0:.0f}% WR)")
    print(f"MFE <  {trailing_trigger}% (trailing PAS activé): {mfe_below_trigger} trades, {wins_below} wins ({wins_below/mfe_below_trigger*100 if mfe_below_trigger else 0:.0f}% WR)")
    print()

# Analyser les 11 trades ancienne config
analyze_trades(old_config_trades[:11], "ANCIENNE CONFIG", "SL 0.25%, BE/trailing trigger 0.1%")

# Analyser les trades nouvelle config
analyze_trades(new_config_trades, "NOUVELLE CONFIG", "Config actuelle")

cur.close()
conn.close()

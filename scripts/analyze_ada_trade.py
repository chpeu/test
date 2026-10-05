#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import psycopg2
from datetime import datetime, timedelta

conn = psycopg2.connect(
    host='localhost',
    database='trading_bot',
    user='postgres',
    password='Goldorak8!'
)
cur = conn.cursor()

# Dernier trade ADA
cur.execute('''
    SELECT t.id, t.symbol, t.direction, t.entry_price, t.exit_price, 
           t.size_usdt, t.leverage_used, t.pnl_usdt, t.pnl_percent,
           t.entry_time, t.exit_time, t.exit_reason, t.score,
           t.atr_entry, t.sl_price, t.tp_price, t.status,
           t.max_pnl_percent, t.min_pnl_percent
    FROM trades t
    WHERE t.symbol LIKE '%ADA%'
    ORDER BY t.entry_time DESC
    LIMIT 1
''')
trade = cur.fetchone()

if not trade:
    print("Aucun trade ADA trouve")
    sys.exit(0)

trade_id = trade[0]
symbol = trade[1]
direction = trade[2]
entry_price = float(trade[3]) if trade[3] else 0
exit_price = float(trade[4]) if trade[4] else 0
size_usdt = float(trade[5]) if trade[5] else 0
leverage = float(trade[6]) if trade[6] else 1
pnl_usdt = float(trade[7]) if trade[7] else 0
pnl_pct = float(trade[8]) if trade[8] else 0
entry_time = trade[9]
exit_time = trade[10]
exit_reason = trade[11]
score = float(trade[12]) if trade[12] else 0
atr_entry = float(trade[13]) if trade[13] else 0
sl_price = float(trade[14]) if trade[14] else 0
tp_price = float(trade[15]) if trade[15] else 0
status = trade[16]
max_pnl = float(trade[17]) if trade[17] else 0
min_pnl = float(trade[18]) if trade[18] else 0

print("=" * 70)
print("FILM DU TRADE ADA")
print("=" * 70)

# Calculs
if entry_price > 0 and atr_entry > 0:
    atr_pct = (atr_entry / entry_price) * 100
    if sl_price > 0:
        sl_distance = abs(entry_price - sl_price)
        sl_atr_mult = sl_distance / atr_entry if atr_entry else 0
    else:
        sl_atr_mult = 0
    if tp_price > 0:
        tp_distance = abs(tp_price - entry_price)
        tp_atr_mult = tp_distance / atr_entry if atr_entry else 0
    else:
        tp_atr_mult = 0
else:
    atr_pct = 0
    sl_atr_mult = 0
    tp_atr_mult = 0

duration = (exit_time - entry_time).total_seconds() / 60 if exit_time and entry_time else 0

print(f"\n[1] IDENTIFICATION")
print(f"    Trade ID: {trade_id}")
print(f"    Symbol: {symbol}")
print(f"    Direction: {direction}")
print(f"    Score: {score:.1f}")
print(f"    Status: {status}")

print(f"\n[2] ENTREE")
print(f"    Date/Heure: {entry_time}")
print(f"    Prix entree: {entry_price:.6f}")
print(f"    Taille: {size_usdt:.2f} USDT")
print(f"    Leverage: {leverage}x")
print(f"    ATR: {atr_entry:.6f} ({atr_pct:.3f}%)")

print(f"\n[3] NIVEAUX CALCULES")
print(f"    SL: {sl_price:.6f} (distance: {sl_atr_mult:.2f}x ATR)")
print(f"    TP: {tp_price:.6f} (distance: {tp_atr_mult:.2f}x ATR)")
if direction == 'LONG':
    sl_pct = ((sl_price - entry_price) / entry_price) * 100 if entry_price else 0
    tp_pct = ((tp_price - entry_price) / entry_price) * 100 if entry_price else 0
else:
    sl_pct = ((entry_price - sl_price) / entry_price) * 100 if entry_price else 0
    tp_pct = ((entry_price - tp_price) / entry_price) * 100 if entry_price else 0
print(f"    SL%: {sl_pct:.2f}%")
print(f"    TP%: {tp_pct:.2f}%")

print(f"\n[4] EVOLUTION DU TRADE")
print(f"    Max PnL atteint: {max_pnl:.2f}%")
print(f"    Min PnL atteint: {min_pnl:.2f}%")
print(f"    Duree: {duration:.1f} minutes")

print(f"\n[5] SORTIE")
print(f"    Date/Heure: {exit_time}")
print(f"    Prix sortie: {exit_price:.6f}")
print(f"    Raison: {exit_reason}")
print(f"    PnL: {pnl_usdt:.4f} USDT ({pnl_pct:.2f}%)")

# Analyse du resultat
print(f"\n[6] ANALYSE")
if pnl_pct > 0:
    print(f"    Resultat: GAGNANT (+{pnl_pct:.2f}%)")
    if max_pnl > 0 and pnl_pct < max_pnl * 0.5:
        print(f"    Opportunite manquee: Max etait {max_pnl:.2f}%, sorti a {pnl_pct:.2f}%")
else:
    print(f"    Resultat: PERDANT ({pnl_pct:.2f}%)")
    if min_pnl < pnl_pct:
        print(f"    Recuperation partielle: Min etait {min_pnl:.2f}%, sorti a {pnl_pct:.2f}%")

# Metriques ATR detaillees
cur.execute('''
    SELECT atr_mult_sl_used, atr_mult_tp_used, market_volatility_state,
           max_pnl_during_trade, min_pnl_during_trade,
           pnl_if_calme_params, pnl_if_normal_params, pnl_if_volatile_params,
           optimal_regime_retrospective, regime_at_entry
    FROM trade_atr_metrics 
    WHERE trade_id = %s
''', (trade_id,))
metrics = cur.fetchone()

if metrics:
    print(f"\n[7] METRIQUES ATR DETAILLEES")
    print(f"    ATR mult SL utilise: {metrics[0]}")
    print(f"    ATR mult TP utilise: {metrics[1]}")
    print(f"    Regime volatilite: {metrics[2]}")
    print(f"    Regime a l'entree: {metrics[9]}")
    print(f"    Max PnL pendant trade: {metrics[3]}")
    print(f"    Min PnL pendant trade: {metrics[4]}")
    
    print(f"\n[8] SCENARIOS WHAT-IF")
    print(f"    Si params CALME: {metrics[5]}")
    print(f"    Si params NORMAL: {metrics[6]}")
    print(f"    Si params VOLATILE: {metrics[7]}")
    print(f"    Regime optimal retrospectif: {metrics[8]}")

# Timeline des evenements
print(f"\n[9] TIMELINE DU TRADE")
print(f"    {entry_time} - OUVERTURE {direction} @ {entry_price:.6f}")

if direction == 'LONG':
    price_move = ((exit_price - entry_price) / entry_price) * 100
else:
    price_move = ((entry_price - exit_price) / entry_price) * 100

if max_pnl > 0:
    print(f"    ... Prix monte, max PnL: +{max_pnl:.2f}%")
if min_pnl < 0:
    print(f"    ... Prix descend, min PnL: {min_pnl:.2f}%")
    
print(f"    {exit_time} - FERMETURE @ {exit_price:.6f} ({exit_reason})")
print(f"    Mouvement prix: {price_move:+.2f}%")

print("\n" + "=" * 70)

conn.close()

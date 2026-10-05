"""Analyse du dernier trade ADA - Film de la position"""
import os
import sys
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

load_dotenv()

password = quote_plus(os.getenv('POSTGRES_PASSWORD', ''))
db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{password}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(db_url)

# Query dernier trade ADA avec metriques
query = text("""
SELECT t.*, tam.*
FROM trades t
LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.symbol LIKE '%ADA%'
ORDER BY t.created_at DESC
LIMIT 1
""")

with engine.connect() as conn:
    result = conn.execute(query)
    rows = result.fetchall()
    cols = list(result.keys())

if not rows:
    print("Aucun trade ADA trouve")
    sys.exit(0)

row = rows[0]
data = dict(zip(cols, row))

print("=" * 70)
print("FILM DU TRADE ADA")
print("=" * 70)

# Extraction des donnees
trade_id = data.get('id')
symbol = data.get('symbol')
direction = data.get('direction')
entry_price = float(data.get('entry_price') or 0)
exit_price = float(data.get('exit_price') or 0)
size_usdt = float(data.get('size_usdt') or 0)
leverage = float(data.get('leverage_used') or 1)
pnl_usdt = float(data.get('pnl_usdt') or data.get('net_pnl_usdt') or 0)
pnl_pct = float(data.get('pnl_percent') or data.get('net_pnl_percent') or 0)
entry_time = data.get('entry_time')
exit_time = data.get('exit_time')
exit_reason = data.get('exit_reason')
score = float(data.get('score') or 0)
atr_entry = float(data.get('atr_entry') or data.get('entry_atr_1m') or 0)
sl_price = float(data.get('sl_price') or 0)
tp_price = float(data.get('tp_price') or 0)
status = data.get('status')
max_pnl = float(data.get('max_pnl_percent') or 0)
min_pnl = float(data.get('min_pnl_percent') or 0)

# Metriques ATR
atr_mult_sl_used = data.get('atr_mult_sl_used') or data.get('entry_atr_mult_sl')
atr_mult_tp_used = data.get('atr_mult_tp_used') or data.get('entry_atr_mult_tp')
volatility_state = data.get('market_volatility_state') or data.get('entry_market_regime')
regime_at_entry = data.get('regime_at_entry') or data.get('entry_market_regime')
max_pnl_trade = data.get('max_pnl_during_trade')
min_pnl_trade = data.get('min_pnl_during_trade')
pnl_if_calme = data.get('pnl_if_calme_params')
pnl_if_normal = data.get('pnl_if_normal_params')
pnl_if_volatile = data.get('pnl_if_volatile_params')
optimal_regime = data.get('optimal_regime_retrospective')

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

if exit_time and entry_time:
    duration = (exit_time - entry_time).total_seconds() / 60
else:
    duration = 0

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

print(f"\n[4] PARAMETRES ATR UTILISES")
print(f"    ATR mult SL: {atr_mult_sl_used}")
print(f"    ATR mult TP: {atr_mult_tp_used}")
print(f"    Regime volatilite: {volatility_state}")
print(f"    Regime a l'entree: {regime_at_entry}")

print(f"\n[5] EVOLUTION DU TRADE")
print(f"    Max PnL atteint: {max_pnl:.2f}%" if max_pnl else "    Max PnL: N/A")
print(f"    Min PnL atteint: {min_pnl:.2f}%" if min_pnl else "    Min PnL: N/A")
if max_pnl_trade:
    print(f"    Max PnL (metrics): {max_pnl_trade}")
if min_pnl_trade:
    print(f"    Min PnL (metrics): {min_pnl_trade}")
print(f"    Duree: {duration:.1f} minutes")

print(f"\n[6] SORTIE")
print(f"    Date/Heure: {exit_time}")
print(f"    Prix sortie: {exit_price:.6f}")
print(f"    Raison: {exit_reason}")
print(f"    PnL: {pnl_usdt:.4f} USDT ({pnl_pct:.2f}%)")

# Analyse du resultat
print(f"\n[7] ANALYSE")
if pnl_pct > 0:
    print(f"    Resultat: GAGNANT (+{pnl_pct:.2f}%)")
    if max_pnl > 0 and pnl_pct < max_pnl * 0.5:
        print(f"    >> Opportunite manquee: Max etait {max_pnl:.2f}%, sorti a {pnl_pct:.2f}%")
else:
    print(f"    Resultat: PERDANT ({pnl_pct:.2f}%)")
    if min_pnl and min_pnl < pnl_pct:
        print(f"    >> Recuperation partielle: Min etait {min_pnl:.2f}%, sorti a {pnl_pct:.2f}%")

print(f"\n[8] SCENARIOS WHAT-IF")
print(f"    Si params CALME: {pnl_if_calme}")
print(f"    Si params NORMAL: {pnl_if_normal}")
print(f"    Si params VOLATILE: {pnl_if_volatile}")
print(f"    Regime optimal retrospectif: {optimal_regime}")

# Timeline
print(f"\n[9] TIMELINE DU TRADE")
print(f"    {entry_time} - OUVERTURE {direction} @ {entry_price:.6f}")

if direction == 'LONG':
    price_move = ((exit_price - entry_price) / entry_price) * 100 if entry_price else 0
else:
    price_move = ((entry_price - exit_price) / entry_price) * 100 if entry_price else 0

if max_pnl and max_pnl > 0:
    print(f"    ... Prix favorable, max PnL: +{max_pnl:.2f}%")
if min_pnl and min_pnl < 0:
    print(f"    ... Prix defavorable, min PnL: {min_pnl:.2f}%")
    
print(f"    {exit_time} - FERMETURE @ {exit_price:.6f} ({exit_reason})")
print(f"    Mouvement prix final: {price_move:+.2f}%")

# Diagnostic
print(f"\n[10] DIAGNOSTIC")
if exit_reason and 'SL' in str(exit_reason).upper():
    print(f"    >> Trade sorti en STOP LOSS")
    if sl_atr_mult < 1.0:
        print(f"    >> SL trop serre ({sl_atr_mult:.2f}x ATR) - considerer augmenter")
elif exit_reason and 'TP' in str(exit_reason).upper():
    print(f"    >> Trade sorti en TAKE PROFIT - Objectif atteint!")
elif exit_reason and 'TRAILING' in str(exit_reason).upper():
    print(f"    >> Trade sorti par TRAILING STOP")
else:
    print(f"    >> Sortie: {exit_reason}")

print("\n" + "=" * 70)

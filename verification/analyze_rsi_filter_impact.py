"""
Analyse impact du filtre RSI sur les trades des dernieres 24h
Compare: avec filtre RSI (LONG si RSI>70, SHORT si RSI<30) vs sans filtre
"""
import os
import sys

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

load_dotenv()

password = quote_plus(os.getenv('POSTGRES_PASSWORD', ''))
db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{password}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(db_url)

# Query all trades from last 24h with RSI data
query = text("""
SELECT t.*
FROM trades t
WHERE t.created_at > NOW() - INTERVAL '24 hours'
ORDER BY t.created_at DESC
""")

with engine.connect() as conn:
    result = conn.execute(query)
    rows = result.fetchall()
    cols = list(result.keys())

trades = [dict(zip(cols, row)) for row in rows]

print("=" * 70)
print("ANALYSE IMPACT FILTRE RSI - DERNIÈRES 24H")
print("=" * 70)
print(f"\nTotal trades analysés: {len(trades)}")

# Separate trades by RSI filter
# RSI Filter: Block LONG if RSI > 70, Block SHORT if RSI < 30

def would_be_filtered(trade):
    """Return True if trade would be filtered by RSI extreme filter"""
    direction = trade.get('direction')
    rsi = trade.get('entry_rsi_1m')
    
    if rsi is None:
        return False  # No RSI data, can't filter
    
    if direction == 'LONG' and rsi > 70:
        return True
    if direction == 'SHORT' and rsi < 30:
        return True
    return False

def calculate_pnl_pct(trade):
    """Calculate PnL % from entry/exit prices"""
    entry = trade.get('entry_price')
    exit_p = trade.get('exit_price')
    direction = trade.get('direction')
    
    if not entry or not exit_p or not direction:
        return 0
    
    if direction == 'LONG':
        return (exit_p - entry) / entry * 100
    else:
        return (entry - exit_p) / entry * 100

# Categorize trades
filtered_trades = []  # Trades that WOULD be filtered (bad RSI)
kept_trades = []      # Trades that would pass the filter

for trade in trades:
    trade['pnl_pct'] = calculate_pnl_pct(trade)
    trade['is_win'] = trade['net_pnl_usdt'] > 0 if trade['net_pnl_usdt'] else False
    
    if would_be_filtered(trade):
        filtered_trades.append(trade)
    else:
        kept_trades.append(trade)

# Calculate metrics
def calc_metrics(trade_list, label):
    if not trade_list:
        return {'count': 0, 'wins': 0, 'losses': 0, 'winrate': 0, 'pnl_total': 0, 'pnl_pct_avg': 0}
    
    wins = sum(1 for t in trade_list if t['is_win'])
    losses = len(trade_list) - wins
    pnl_total = sum(t['net_pnl_usdt'] or 0 for t in trade_list)
    pnl_pct_avg = sum(t['pnl_pct'] for t in trade_list) / len(trade_list)
    winrate = wins / len(trade_list) * 100 if trade_list else 0
    
    return {
        'count': len(trade_list),
        'wins': wins,
        'losses': losses,
        'winrate': winrate,
        'pnl_total': pnl_total,
        'pnl_pct_avg': pnl_pct_avg
    }

# Current state (no RSI filter)
all_metrics = calc_metrics(trades, "ALL")

# What would be FILTERED (removed)
filtered_metrics = calc_metrics(filtered_trades, "FILTERED")

# What would be KEPT (with filter active)
kept_metrics = calc_metrics(kept_trades, "KEPT")

# By direction
long_trades = [t for t in trades if t['direction'] == 'LONG']
short_trades = [t for t in trades if t['direction'] == 'SHORT']

long_filtered = [t for t in filtered_trades if t['direction'] == 'LONG']
short_filtered = [t for t in filtered_trades if t['direction'] == 'SHORT']

long_kept = [t for t in kept_trades if t['direction'] == 'LONG']
short_kept = [t for t in kept_trades if t['direction'] == 'SHORT']

print("\n" + "=" * 70)
print("COMPARAISON SANS vs AVEC FILTRE RSI")
print("=" * 70)

print("\n┌─────────────────────────────────────────────────────────────────────┐")
print("│ SITUATION ACTUELLE (SANS filtre RSI)                               │")
print("├─────────────────────────────────────────────────────────────────────┤")
print(f"│  Total trades:    {all_metrics['count']:3d}                                              │")
print(f"│  Wins/Losses:     {all_metrics['wins']:3d} / {all_metrics['losses']:3d}                                          │")
print(f"│  Win Rate:        {all_metrics['winrate']:5.1f}%                                           │")
print(f"│  PnL Total:       ${all_metrics['pnl_total']:+7.2f}                                        │")
print(f"│  PnL % moyen:     {all_metrics['pnl_pct_avg']:+6.3f}%                                         │")
print("└─────────────────────────────────────────────────────────────────────┘")

print("\n┌─────────────────────────────────────────────────────────────────────┐")
print("│ TRADES QUI SERAIENT FILTRÉS (RSI extrême)                          │")
print("├─────────────────────────────────────────────────────────────────────┤")
print(f"│  Trades filtrés:  {filtered_metrics['count']:3d} ({filtered_metrics['count']/all_metrics['count']*100 if all_metrics['count'] else 0:4.1f}% du total)                           │")
print(f"│  - LONG (RSI>70): {len(long_filtered):3d}                                              │")
print(f"│  - SHORT (RSI<30):{len(short_filtered):3d}                                              │")
print(f"│  Win Rate:        {filtered_metrics['winrate']:5.1f}%                                           │")
print(f"│  PnL Total:       ${filtered_metrics['pnl_total']:+7.2f}                                        │")
print(f"│  PnL % moyen:     {filtered_metrics['pnl_pct_avg']:+6.3f}%                                         │")
print("└─────────────────────────────────────────────────────────────────────┘")

print("\n┌─────────────────────────────────────────────────────────────────────┐")
print("│ SITUATION AVEC FILTRE RSI (trades conservés)                       │")
print("├─────────────────────────────────────────────────────────────────────┤")
print(f"│  Trades gardés:   {kept_metrics['count']:3d} ({kept_metrics['count']/all_metrics['count']*100 if all_metrics['count'] else 0:4.1f}% du total)                           │")
print(f"│  Wins/Losses:     {kept_metrics['wins']:3d} / {kept_metrics['losses']:3d}                                          │")
print(f"│  Win Rate:        {kept_metrics['winrate']:5.1f}%                                           │")
print(f"│  PnL Total:       ${kept_metrics['pnl_total']:+7.2f}                                        │")
print(f"│  PnL % moyen:     {kept_metrics['pnl_pct_avg']:+6.3f}%                                         │")
print("└─────────────────────────────────────────────────────────────────────┘")

# Impact analysis
print("\n" + "=" * 70)
print("IMPACT DU FILTRE RSI")
print("=" * 70)

winrate_delta = kept_metrics['winrate'] - all_metrics['winrate']
pnl_delta = kept_metrics['pnl_total'] - all_metrics['pnl_total']

print(f"\n  Trades évités:     {filtered_metrics['count']:+3d} ({-filtered_metrics['count']/all_metrics['count']*100 if all_metrics['count'] else 0:+5.1f}%)")
print(f"  Delta Win Rate:    {winrate_delta:+5.1f}%")
print(f"  Delta PnL:         ${pnl_delta:+7.2f}")

if pnl_delta > 0:
    print(f"\n  ✅ Le filtre RSI aurait AMÉLIORÉ le PnL de ${pnl_delta:.2f}")
else:
    print(f"\n  ⚠️ Le filtre RSI aurait RÉDUIT le PnL de ${-pnl_delta:.2f}")

# Detail of filtered trades
print("\n" + "=" * 70)
print("DÉTAIL DES TRADES QUI AURAIENT ÉTÉ FILTRÉS")
print("=" * 70)

if filtered_trades:
    print(f"\n{'Symbol':<20} {'Dir':<6} {'RSI':<6} {'PnL%':<8} {'PnL$':<8} {'Dur':<6} {'Exit':<12} {'Regime':<10}")
    print("-" * 90)
    for t in filtered_trades:
        symbol = t['symbol'].replace('/USDT:USDT', '') if t['symbol'] else ''
        direction = t['direction'] or ''
        rsi = f"{t['entry_rsi_1m']:.1f}" if t['entry_rsi_1m'] else 'N/A'
        pnl_pct = f"{t['pnl_pct']:+.3f}%" if t['pnl_pct'] else ''
        pnl_usd = f"${t['net_pnl_usdt']:+.2f}" if t['net_pnl_usdt'] else ''
        duration = f"{t['duration_seconds']:.0f}s" if t['duration_seconds'] else ''
        exit_r = t['exit_reason'] or ''
        regime = t['entry_market_regime'] or ''
        print(f"{symbol:<20} {direction:<6} {rsi:<6} {pnl_pct:<8} {pnl_usd:<8} {duration:<6} {exit_r:<12} {regime:<10}")
else:
    print("\n  Aucun trade n'aurait été filtré.")

# Additional analysis by regime
print("\n" + "=" * 70)
print("ANALYSE PAR RÉGIME DE MARCHÉ")
print("=" * 70)

regimes = {}
for t in trades:
    regime = t['entry_market_regime'] or 'UNKNOWN'
    if regime not in regimes:
        regimes[regime] = []
    regimes[regime].append(t)

print(f"\n{'Régime':<12} {'Trades':<8} {'Wins':<6} {'WinRate':<10} {'PnL$':<10} {'PnL%':<10}")
print("-" * 60)
for regime, regime_trades in sorted(regimes.items()):
    metrics = calc_metrics(regime_trades, regime)
    print(f"{regime:<12} {metrics['count']:<8} {metrics['wins']:<6} {metrics['winrate']:>5.1f}%    ${metrics['pnl_total']:>+7.2f}   {metrics['pnl_pct_avg']:>+6.3f}%")

# Analysis by exit reason
print("\n" + "=" * 70)
print("ANALYSE PAR RAISON DE SORTIE")
print("=" * 70)

exits = {}
for t in trades:
    exit_r = t['exit_reason'] or 'UNKNOWN'
    if exit_r not in exits:
        exits[exit_r] = []
    exits[exit_r].append(t)

print(f"\n{'Exit Reason':<15} {'Trades':<8} {'Wins':<6} {'WinRate':<10} {'PnL$':<10} {'Dur moy':<10}")
print("-" * 65)
for exit_r, exit_trades in sorted(exits.items()):
    metrics = calc_metrics(exit_trades, exit_r)
    avg_dur = sum(t['duration_seconds'] or 0 for t in exit_trades) / len(exit_trades) if exit_trades else 0
    print(f"{exit_r:<15} {metrics['count']:<8} {metrics['wins']:<6} {metrics['winrate']:>5.1f}%    ${metrics['pnl_total']:>+7.2f}   {avg_dur:>6.1f}s")

# Analysis by RSI ranges
print("\n" + "=" * 70)
print("ANALYSE PAR PLAGE RSI (à l'entrée)")
print("=" * 70)

rsi_ranges = {
    'RSI < 30 (oversold)': [],
    'RSI 30-50 (bearish)': [],
    'RSI 50-70 (bullish)': [],
    'RSI > 70 (overbought)': [],
    'RSI N/A': []
}

for t in trades:
    rsi = t['entry_rsi_1m']
    if rsi is None:
        rsi_ranges['RSI N/A'].append(t)
    elif rsi < 30:
        rsi_ranges['RSI < 30 (oversold)'].append(t)
    elif rsi < 50:
        rsi_ranges['RSI 30-50 (bearish)'].append(t)
    elif rsi < 70:
        rsi_ranges['RSI 50-70 (bullish)'].append(t)
    else:
        rsi_ranges['RSI > 70 (overbought)'].append(t)

print(f"\n{'Plage RSI':<25} {'Trades':<8} {'LONG':<6} {'SHORT':<6} {'WinRate':<10} {'PnL$':<10}")
print("-" * 70)
for rsi_range, range_trades in rsi_ranges.items():
    if range_trades:
        metrics = calc_metrics(range_trades, rsi_range)
        longs = sum(1 for t in range_trades if t['direction'] == 'LONG')
        shorts = sum(1 for t in range_trades if t['direction'] == 'SHORT')
        print(f"{rsi_range:<25} {metrics['count']:<8} {longs:<6} {shorts:<6} {metrics['winrate']:>5.1f}%    ${metrics['pnl_total']:>+7.2f}")

# Specific analysis: LONG when RSI > 70
print("\n" + "=" * 70)
print("ANALYSE SPÉCIFIQUE: LONG quand RSI > 70 (PROBLÉMATIQUE)")
print("=" * 70)

long_overbought = [t for t in trades if t['direction'] == 'LONG' and t.get('entry_rsi_1m') and t['entry_rsi_1m'] > 70]
if long_overbought:
    metrics = calc_metrics(long_overbought, "LONG RSI>70")
    print(f"\n  Nombre de trades:  {metrics['count']}")
    print(f"  Win Rate:          {metrics['winrate']:.1f}%")
    print(f"  PnL Total:         ${metrics['pnl_total']:+.2f}")
    print(f"  PnL % moyen:       {metrics['pnl_pct_avg']:+.3f}%")
    
    print(f"\n  ⚠️ Ces {metrics['count']} trades LONG sur RSI overbought ont un winrate de {metrics['winrate']:.1f}%")
    print(f"     et ont coûté ${abs(metrics['pnl_total']):.2f} au total.")
else:
    print("\n  Aucun trade LONG avec RSI > 70")

# Specific analysis: SHORT when RSI < 30
print("\n" + "=" * 70)
print("ANALYSE SPÉCIFIQUE: SHORT quand RSI < 30 (PROBLÉMATIQUE)")
print("=" * 70)

short_oversold = [t for t in trades if t['direction'] == 'SHORT' and t.get('entry_rsi_1m') and t['entry_rsi_1m'] < 30]
if short_oversold:
    metrics = calc_metrics(short_oversold, "SHORT RSI<30")
    print(f"\n  Nombre de trades:  {metrics['count']}")
    print(f"  Win Rate:          {metrics['winrate']:.1f}%")
    print(f"  PnL Total:         ${metrics['pnl_total']:+.2f}")
    print(f"  PnL % moyen:       {metrics['pnl_pct_avg']:+.3f}%")
else:
    print("\n  Aucun trade SHORT avec RSI < 30")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print(f"""
RECOMMANDATION:
{"✅ ACTIVER le filtre RSI extrême" if filtered_metrics['pnl_total'] < 0 else "⚠️ Le filtre RSI aurait filtré des trades profitables"}

Impact estimé:
- Trades évités: {filtered_metrics['count']}
- PnL récupéré: ${-filtered_metrics['pnl_total']:+.2f}
- Nouveau win rate: {kept_metrics['winrate']:.1f}% (vs {all_metrics['winrate']:.1f}% actuel)
""")

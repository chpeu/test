"""
Backtest 3 exit strategies:
1. Trailing MFE Protection - move SL to breakeven when MFE reaches threshold
2. Quick Exit on reversal signals - exit if momentum reverses while in profit
3. Conditional exit on duration - exit if trade > X seconds AND profit > threshold

Uses fees=0, slippage buffer for market-only execution.
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
import math

load_dotenv()


def _parse_env_float(key: str, default: str) -> float:
    raw = os.getenv(key, default)
    if raw is None:
        raw = default
    if isinstance(raw, str):
        raw = raw.strip().replace(',', '.')
    return float(raw)


password = quote_plus(os.getenv('POSTGRES_PASSWORD', ''))
db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{password}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(db_url)

lookback_hours = int(os.getenv('LOOKBACK_HOURS', '168'))
SLIPPAGE_PCT = _parse_env_float('ANALYSIS_SLIPPAGE_PCT', '0.03')

# Query ALL trades with MFE data and exit indicators
query = text(f"""
SELECT 
    t.id,
    t.symbol,
    t.direction,
    t.entry_price,
    t.exit_price,
    t.net_pnl_usdt,
    t.duration_seconds,
    t.exit_reason,
    t.rsi_at_entry,
    t.entry_rsi_1m,
    tam.max_price_reached,
    tam.min_price_reached,
    t.exit_rsi_1m,
    t.exit_adx_1m
FROM trades t
LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
  AND tam.max_price_reached IS NOT NULL
  AND tam.min_price_reached IS NOT NULL
  AND t.entry_price IS NOT NULL
  AND t.exit_price IS NOT NULL
  -- Exclude corrupted data: MFE must be >= 0
  AND (
    (t.direction = 'LONG' AND tam.max_price_reached >= t.entry_price)
    OR
    (t.direction = 'SHORT' AND tam.min_price_reached <= t.entry_price)
  )
  -- Exclude corrupted data: exit must be within min-max range
  AND (
    (t.direction = 'LONG' AND t.exit_price <= tam.max_price_reached AND t.exit_price >= tam.min_price_reached)
    OR
    (t.direction = 'SHORT' AND t.exit_price >= tam.min_price_reached AND t.exit_price <= tam.max_price_reached)
  )
ORDER BY t.created_at DESC
""")

with engine.connect() as conn:
    result = conn.execute(query)
    rows = result.fetchall()
    cols = list(result.keys())

trades = [dict(zip(cols, row)) for row in rows]

print("=" * 80)
print("BACKTEST EXIT STRATEGIES (fees=0, slippage={:.2f}%)".format(SLIPPAGE_PCT))
print("=" * 80)
print(f"Lookback: {lookback_hours}h")
print(f"Trades avec MFE valide: {len(trades)}")


def calc_pnl_pct(trade):
    """Calculate PnL % from entry/exit prices"""
    entry = trade.get('entry_price') or 1
    exit_p = trade.get('exit_price') or entry
    direction = trade.get('direction')
    if direction == 'LONG':
        return (exit_p - entry) / entry * 100
    else:
        return (entry - exit_p) / entry * 100


def calc_mfe_pct(trade):
    """Calculate Max Favorable Excursion %"""
    entry = trade.get('entry_price') or 1
    max_p = trade.get('max_price_reached')
    min_p = trade.get('min_price_reached')
    direction = trade.get('direction')
    if direction == 'LONG':
        return ((max_p - entry) / entry * 100) if max_p else 0
    else:
        return ((entry - min_p) / entry * 100) if min_p else 0


def calc_mae_pct(trade):
    """Calculate Max Adverse Excursion %"""
    entry = trade.get('entry_price') or 1
    max_p = trade.get('max_price_reached')
    min_p = trade.get('min_price_reached')
    direction = trade.get('direction')
    if direction == 'LONG':
        return ((entry - min_p) / entry * 100) if min_p else 0
    else:
        return ((max_p - entry) / entry * 100) if max_p else 0


# Enrich trades
for t in trades:
    t['pnl_pct'] = calc_pnl_pct(t)
    t['mfe_pct'] = calc_mfe_pct(t)
    t['mae_pct'] = calc_mae_pct(t)
    t['is_win'] = (t['net_pnl_usdt'] or 0) > 0


# Baseline metrics
baseline_pnl = sum(t['pnl_pct'] for t in trades)
baseline_wins = sum(1 for t in trades if t['is_win'])
baseline_winrate = baseline_wins / len(trades) * 100 if trades else 0

print(f"\n{'='*80}")
print("BASELINE (mode actuel)")
print(f"{'='*80}")
print(f"Trades: {len(trades)}")
print(f"PnL Total: {baseline_pnl:+.2f}%")
print(f"PnL Moyen: {baseline_pnl/len(trades):+.4f}%")
print(f"Win Rate: {baseline_winrate:.1f}%")


# ============================================================================
# STRATEGY 1: TRAILING MFE PROTECTION
# ============================================================================
print(f"\n{'='*80}")
print("STRATÉGIE 1: TRAILING MFE PROTECTION")
print("Principe: Si MFE atteint X%, on monte le SL à breakeven (0% après slippage)")
print(f"{'='*80}")

def simulate_trailing_mfe(trades, mfe_trigger_pct, exit_at_breakeven=True):
    """
    Simulate trailing MFE strategy:
    - If MFE >= mfe_trigger_pct, we assume SL is moved to breakeven
    - If actual PnL < 0, we exit at breakeven (0% - slippage) instead of actual loss
    - If actual PnL >= 0, we keep actual PnL (didn't need protection)
    """
    total_pnl = 0
    protected_count = 0
    
    for t in trades:
        mfe = t['mfe_pct']
        actual_pnl = t['pnl_pct']
        
        # Did MFE reach the trigger?
        if mfe >= mfe_trigger_pct:
            # MFE was high enough to trigger breakeven protection
            if actual_pnl < 0:
                # Trade ended in loss but we had breakeven SL
                # Exit at breakeven minus slippage
                simulated_pnl = -SLIPPAGE_PCT
                protected_count += 1
            else:
                # Trade ended in profit, keep actual
                simulated_pnl = actual_pnl
        else:
            # MFE never reached trigger, keep actual PnL
            simulated_pnl = actual_pnl
        
        total_pnl += simulated_pnl
    
    return total_pnl, protected_count


print(f"\n{'Trigger MFE':<15} {'PnL Simulé':<15} {'vs Baseline':<15} {'Protections':<15}")
print("-" * 60)

best_trailing = {'trigger': 0, 'pnl': baseline_pnl, 'delta': 0}

for trigger in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]:
    pnl, protected = simulate_trailing_mfe(trades, trigger)
    delta = pnl - baseline_pnl
    print(f"+{trigger:.2f}%{'':<10} {pnl:+.2f}%{'':<8} {delta:+.2f}%{'':<8} {protected}")
    
    if delta > best_trailing['delta']:
        best_trailing = {'trigger': trigger, 'pnl': pnl, 'delta': delta, 'protected': protected}


# ============================================================================
# STRATEGY 2: QUICK EXIT ON REVERSAL SIGNALS
# ============================================================================
print(f"\n{'='*80}")
print("STRATÉGIE 2: QUICK EXIT SUR SIGNAUX DE RETOURNEMENT")
print("Principe: Sortir si RSI_exit inverse la direction ET on est en profit")
print(f"{'='*80}")

def simulate_reversal_exit(trades, min_profit_pct, rsi_reversal_threshold=50):
    """
    Simulate reversal exit strategy:
    - If trade is LONG and exit_rsi < rsi_reversal_threshold AND profit > min_profit_pct
      → Exit at min_profit_pct instead of waiting for SL/TP
    - If trade is SHORT and exit_rsi > rsi_reversal_threshold AND profit > min_profit_pct
      → Exit at min_profit_pct
    """
    total_pnl = 0
    early_exits = 0
    trades_with_rsi = 0
    
    for t in trades:
        actual_pnl = t['pnl_pct']
        exit_rsi = t.get('exit_rsi_1m')
        direction = t['direction']
        mfe = t['mfe_pct']
        
        if exit_rsi is None:
            # No exit RSI data, keep actual
            total_pnl += actual_pnl
            continue
        
        trades_with_rsi += 1
        
        # Check for reversal signal
        is_reversal = False
        if direction == 'LONG' and exit_rsi < rsi_reversal_threshold:
            is_reversal = True
        elif direction == 'SHORT' and exit_rsi > (100 - rsi_reversal_threshold):
            is_reversal = True
        
        # Would we have had enough MFE to exit at min_profit?
        net_exit_pnl = min_profit_pct - SLIPPAGE_PCT
        could_exit = mfe >= (min_profit_pct + SLIPPAGE_PCT)
        
        if is_reversal and could_exit:
            # Exit early at min_profit
            if actual_pnl < net_exit_pnl:
                # Only beneficial if actual was worse
                simulated_pnl = net_exit_pnl
                early_exits += 1
            else:
                simulated_pnl = actual_pnl
        else:
            simulated_pnl = actual_pnl
        
        total_pnl += simulated_pnl
    
    return total_pnl, early_exits, trades_with_rsi


print(f"\n{'Min Profit':<12} {'RSI Thresh':<12} {'PnL Simulé':<15} {'vs Baseline':<15} {'Early Exits':<12}")
print("-" * 70)

best_reversal = {'config': '', 'pnl': baseline_pnl, 'delta': 0}

for min_profit in [0.03, 0.05, 0.08, 0.10]:
    for rsi_thresh in [40, 45, 50]:
        pnl, early_exits, with_rsi = simulate_reversal_exit(trades, min_profit, rsi_thresh)
        delta = pnl - baseline_pnl
        print(f"+{min_profit:.2f}%{'':<6} RSI<{rsi_thresh}{'':<6} {pnl:+.2f}%{'':<8} {delta:+.2f}%{'':<8} {early_exits}/{with_rsi}")
        
        if delta > best_reversal['delta']:
            best_reversal = {'config': f'profit={min_profit}%, rsi={rsi_thresh}', 'pnl': pnl, 'delta': delta}


# ============================================================================
# STRATEGY 3: CONDITIONAL EXIT ON DURATION
# ============================================================================
print(f"\n{'='*80}")
print("STRATÉGIE 3: EXIT CONDITIONNEL SUR DURÉE")
print("Principe: Si trade > X secondes ET profit > threshold → exit")
print(f"{'='*80}")

def simulate_duration_exit(trades, min_duration_sec, min_profit_pct):
    """
    Simulate duration-based exit:
    - If duration > min_duration_sec AND MFE >= min_profit_pct + slippage
      → Assume we would exit at min_profit_pct
    - Only beneficial if actual PnL < min_profit_pct
    """
    total_pnl = 0
    duration_exits = 0
    
    for t in trades:
        actual_pnl = t['pnl_pct']
        duration = t.get('duration_seconds') or 0
        mfe = t['mfe_pct']
        
        net_exit_pnl = min_profit_pct - SLIPPAGE_PCT
        could_exit = mfe >= (min_profit_pct + SLIPPAGE_PCT)
        
        if duration >= min_duration_sec and could_exit:
            if actual_pnl < net_exit_pnl:
                simulated_pnl = net_exit_pnl
                duration_exits += 1
            else:
                simulated_pnl = actual_pnl
        else:
            simulated_pnl = actual_pnl
        
        total_pnl += simulated_pnl
    
    return total_pnl, duration_exits


print(f"\n{'Min Duration':<15} {'Min Profit':<12} {'PnL Simulé':<15} {'vs Baseline':<15} {'Exits':<10}")
print("-" * 70)

best_duration = {'config': '', 'pnl': baseline_pnl, 'delta': 0}

for min_dur in [30, 60, 120, 180, 300]:
    for min_profit in [0.03, 0.05, 0.08, 0.10]:
        pnl, exits = simulate_duration_exit(trades, min_dur, min_profit)
        delta = pnl - baseline_pnl
        print(f"{min_dur}s{'':<12} +{min_profit:.2f}%{'':<6} {pnl:+.2f}%{'':<8} {delta:+.2f}%{'':<8} {exits}")
        
        if delta > best_duration['delta']:
            best_duration = {'config': f'dur={min_dur}s, profit={min_profit}%', 'pnl': pnl, 'delta': delta}


# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{'='*80}")
print("RÉSUMÉ - MEILLEURE CONFIG PAR STRATÉGIE")
print(f"{'='*80}")

print(f"\n📊 BASELINE: {baseline_pnl:+.2f}% (PnL moyen: {baseline_pnl/len(trades):+.4f}%)")

print(f"\n1️⃣ TRAILING MFE:")
if best_trailing['delta'] > 0:
    print(f"   ✅ Trigger: +{best_trailing['trigger']:.2f}% → PnL: {best_trailing['pnl']:+.2f}% ({best_trailing['delta']:+.2f}%)")
    print(f"      Trades protégés: {best_trailing.get('protected', 'N/A')}")
else:
    print(f"   ❌ Aucune amélioration (meilleur delta: {best_trailing['delta']:+.2f}%)")

print(f"\n2️⃣ REVERSAL EXIT:")
if best_reversal['delta'] > 0:
    print(f"   ✅ Config: {best_reversal['config']} → PnL: {best_reversal['pnl']:+.2f}% ({best_reversal['delta']:+.2f}%)")
else:
    print(f"   ❌ Aucune amélioration (meilleur delta: {best_reversal['delta']:+.2f}%)")

print(f"\n3️⃣ DURATION EXIT:")
if best_duration['delta'] > 0:
    print(f"   ✅ Config: {best_duration['config']} → PnL: {best_duration['pnl']:+.2f}% ({best_duration['delta']:+.2f}%)")
else:
    print(f"   ❌ Aucune amélioration (meilleur delta: {best_duration['delta']:+.2f}%)")

print(f"\n{'='*80}")

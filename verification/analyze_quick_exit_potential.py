"""
Analyse du potentiel du mode QUICK EXIT sur les trades RSI hors seuils
Vérifie si un exit rapide aurait été profitable
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

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

lookback_hours = int(os.getenv('LOOKBACK_HOURS', '24'))

# Query trades RSI hors seuils avec MFE (Max Favorable Excursion)
query = text("""
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
    tam.max_price_reached,
    tam.min_price_reached
FROM trades t
LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.created_at > NOW() - INTERVAL :lookback_interval
  AND (
    (t.direction = 'LONG' AND t.rsi_at_entry > 70)
    OR
    (t.direction = 'SHORT' AND t.rsi_at_entry < 30)
  )
  AND tam.max_price_reached IS NOT NULL
  AND tam.min_price_reached IS NOT NULL
ORDER BY t.created_at DESC
""")

with engine.connect() as conn:
    result = conn.execute(query, {'lookback_interval': f"{lookback_hours} hours"})
    rows = result.fetchall()
    cols = list(result.keys())

trades = [dict(zip(cols, row)) for row in rows]

print("=" * 80)
print("ANALYSE POTENTIEL MODE 'QUICK EXIT' - TRADES RSI HORS SEUILS")
print("=" * 80)
print(f"\nLookback: {lookback_hours}h")
print(f"Trades analysés: {len(trades)} (RSI > 70 pour LONG, RSI < 30 pour SHORT)")

# Analyze each trade
print("\n" + "-" * 80)
print(f"{'Symbol':<12} {'Dir':<6} {'RSI':<6} {'MFE%':<8} {'MAE%':<8} {'PnL%':<8} {'Quick Exit?':<15}")
print("-" * 80)

quick_exit_wins = 0
quick_exit_losses = 0
quick_exit_pnl = 0
normal_pnl = 0

# Quick exit threshold (minimum gain to exit)
QUICK_EXIT_THRESHOLD = _parse_env_float('QUICK_EXIT_THRESHOLD_PCT', '0.05')  # 0.05% minimum gain
FEE_PCT = _parse_env_float('ANALYSIS_FEE_PCT', '0.08')  # 0.04% entry + 0.04% exit
SLIPPAGE_PCT = _parse_env_float('ANALYSIS_SLIPPAGE_PCT', '0.0')

for t in trades:
    symbol = t['symbol'].replace('/USDT:USDT', '') if t['symbol'] else ''
    direction = t['direction'] or ''
    rsi = t['rsi_at_entry'] or 0
    
    # Calculate MFE % from prices if not in tam
    entry = t['entry_price']
    max_p = t['max_price_reached']
    min_p = t['min_price_reached']
    
    if entry and max_p and min_p:
        if direction == 'LONG':
            mfe_pct = (max_p - entry) / entry * 100
            mae_pct = (entry - min_p) / entry * 100
        else:
            mfe_pct = (entry - min_p) / entry * 100
            mae_pct = (max_p - entry) / entry * 100
    else:
        mfe_pct = t.get('mfe_pct') or 0
        mae_pct = t.get('mae_pct') or 0
    
    # Calculate actual PnL %
    exit_p = t['exit_price']
    if entry and exit_p:
        if direction == 'LONG':
            actual_pnl_pct = (exit_p - entry) / entry * 100
        else:
            actual_pnl_pct = (entry - exit_p) / entry * 100
    else:
        actual_pnl_pct = 0
    
    normal_pnl += actual_pnl_pct
    
    # Would quick exit have worked?
    # MFE must be > threshold + fees + slippage/spread buffer
    net_mfe = mfe_pct - FEE_PCT - SLIPPAGE_PCT
    
    if net_mfe >= QUICK_EXIT_THRESHOLD:
        quick_exit_result = f"✅ +{QUICK_EXIT_THRESHOLD:.2f}%"
        quick_exit_wins += 1
        quick_exit_pnl += QUICK_EXIT_THRESHOLD
    else:
        quick_exit_result = f"❌ MFE insuffisant"
        quick_exit_losses += 1
        # Would still hit SL
        quick_exit_pnl += actual_pnl_pct
    
    print(f"{symbol:<12} {direction:<6} {rsi:<6.1f} {mfe_pct:>+6.2f}%  {mae_pct:>+6.2f}%  {actual_pnl_pct:>+6.2f}%  {quick_exit_result}")

print("-" * 80)

print("\n" + "=" * 80)
print("COMPARAISON: MODE NORMAL vs QUICK EXIT")
print("=" * 80)

print(f"""
┌─────────────────────────────────────────────────────────────────┐
│                    MODE NORMAL (actuel)                         │
├─────────────────────────────────────────────────────────────────┤
│  Trades:          {len(trades):3d}                                           │
│  PnL Total:       {normal_pnl:+6.2f}%                                        │
│  PnL Moyen:       {normal_pnl/len(trades) if trades else 0:+6.3f}%                                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    MODE QUICK EXIT (simulé)                     │
├─────────────────────────────────────────────────────────────────┤
│  Threshold:       +{QUICK_EXIT_THRESHOLD:.2f}% (après fees={FEE_PCT:.2f}%, slippage={SLIPPAGE_PCT:.2f}%)     │
│  Exits réussis:   {quick_exit_wins:3d} ({quick_exit_wins/len(trades)*100 if trades else 0:.1f}%)                                      │
│  Exits ratés:     {quick_exit_losses:3d} (MFE insuffisant → SL)                    │
│  PnL Total:       {quick_exit_pnl:+6.2f}%                                        │
│  PnL Moyen:       {quick_exit_pnl/len(trades) if trades else 0:+6.3f}%                                       │
└─────────────────────────────────────────────────────────────────┘
""")

delta = quick_exit_pnl - normal_pnl
print(f"Delta PnL: {delta:+.2f}%")
if delta > 0:
    print(f"\n✅ Le mode QUICK EXIT aurait AMÉLIORÉ le PnL de {delta:.2f}%")
else:
    print(f"\n⚠️ Le mode QUICK EXIT aurait RÉDUIT le PnL de {-delta:.2f}%")

# Additional analysis: what MFE threshold would be optimal?
print("\n" + "=" * 80)
print("ANALYSE: QUEL SEUIL QUICK EXIT OPTIMAL?")
print("=" * 80)

thresholds = [0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20]

print(f"\n{'Threshold':<12} {'Exits OK':<10} {'Exits KO':<10} {'PnL Simulé':<12} {'vs Normal':<12}")
print("-" * 60)

for thresh in thresholds:
    wins = 0
    pnl = 0
    
    for t in trades:
        entry = t['entry_price']
        max_p = t['max_price_reached']
        min_p = t['min_price_reached']
        exit_p = t['exit_price']
        direction = t['direction']
        
        if entry and max_p and min_p:
            if direction == 'LONG':
                mfe = (max_p - entry) / entry * 100
                actual = (exit_p - entry) / entry * 100 if exit_p else 0
            else:
                mfe = (entry - min_p) / entry * 100
                actual = (entry - exit_p) / entry * 100 if exit_p else 0
        else:
            mfe = 0
            actual = 0
        
        net_mfe = mfe - FEE_PCT - SLIPPAGE_PCT
        
        if net_mfe >= thresh:
            wins += 1
            pnl += thresh
        else:
            pnl += actual
    
    losses = len(trades) - wins
    delta_vs_normal = pnl - normal_pnl
    marker = "✅" if delta_vs_normal > 0 else ""
    print(f"+{thresh:.2f}%       {wins:<10} {losses:<10} {pnl:+6.2f}%       {delta_vs_normal:+6.2f}% {marker}")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

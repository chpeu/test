"""Analyze COAI trade with -0.68% PnL"""
import os
import sys
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

load_dotenv()

password = quote_plus(os.getenv('POSTGRES_PASSWORD', ''))
db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{password}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(db_url)

# First list trades columns
cols_query = text("""
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'trades' 
ORDER BY ordinal_position
""")

with engine.connect() as conn:
    result = conn.execute(cols_query)
    print("Trades columns:", [r[0] for r in result.fetchall()])

# Query COAI trades - use * to get all columns
query = text("""
SELECT t.*, tam.*
FROM trades t
LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.symbol LIKE '%COAI%'
ORDER BY t.created_at DESC
LIMIT 3
""")

with engine.connect() as conn:
    result = conn.execute(query)
    rows = result.fetchall()
    cols = list(result.keys())

print("=" * 60)
print("COAI TRADES ANALYSIS")
print("=" * 60)

# Key columns to display
key_cols = [
    'id', 'symbol', 'direction', 'entry_price', 'exit_price', 
    'net_pnl_usdt', 'duration_seconds', 'exit_reason',
    'entry_market_regime', 'created_at',
    'entry_atr_1m', 'entry_atr_5m', 'entry_adx', 'entry_rsi_1m',
    'entry_atr_mult_sl', 'entry_atr_mult_tp',
    'calculated_sl_pct', 'calculated_tp_pct',
    'max_price_reached', 'min_price_reached',
    'mfe_pct', 'mae_pct', 'sl_mexc_touched',
    'break_even_atr_mult', 'trailing_trigger_atr_mult',
    'entry_score_1m', 'entry_score_5m',
    'stagnation_positive_triggered', 'early_invalidation_triggered'
]

for row in rows:
    print()
    row_dict = dict(zip(cols, row))
    
    # Calculate PnL % from entry/exit
    entry_p = row_dict.get('entry_price')
    exit_p = row_dict.get('exit_price')
    direction = row_dict.get('direction')
    if entry_p and exit_p and direction:
        if direction == 'LONG':
            pnl_pct = (exit_p - entry_p) / entry_p * 100
        else:
            pnl_pct = (entry_p - exit_p) / entry_p * 100
        print(f"  {'PNL_PCT (calculated)':30s}: {pnl_pct:.4f}%")
    
    for col in key_cols:
        if col in row_dict and row_dict[col] is not None:
            print(f"  {col:30s}: {row_dict[col]}")
    print("-" * 60)

# Also get today's session trades for context
print("\n" + "=" * 60)
print("TODAY'S SESSION SUMMARY")
print("=" * 60)

session_query = text("""
SELECT 
    COUNT(*) as total_trades,
    SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN net_pnl_usdt <= 0 THEN 1 ELSE 0 END) as losses,
    ROUND(SUM(net_pnl_usdt)::numeric, 2) as total_pnl,
    ROUND(AVG(duration_seconds)::numeric, 1) as avg_duration
FROM trades
WHERE created_at > NOW() - INTERVAL '24 hours'
""")

with engine.connect() as conn:
    result = conn.execute(session_query)
    row = result.fetchone()
    print(f"  Total trades (24h): {row[0]}")
    print(f"  Wins: {row[1]}")
    print(f"  Losses: {row[2]}")
    print(f"  Total PnL: ${row[3]}")
    print(f"  Avg duration: {row[4]}s")

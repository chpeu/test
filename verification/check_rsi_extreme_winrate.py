"""Check win rate of RSI extreme trades"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

load_dotenv()

password = quote_plus(os.getenv('POSTGRES_PASSWORD', ''))
db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{password}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(db_url)

lookback = int(os.getenv('LOOKBACK_HOURS', '168'))

print("=" * 70)
print("RSI EXTREME TRADES - WIN RATE ANALYSIS")
print("=" * 70)

# Win rate of RSI extreme trades with valid MFE
query1 = text(f"""
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN net_pnl_usdt <= 0 THEN 1 ELSE 0 END) as losses,
  ROUND(100.0 * SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
  ROUND(AVG(net_pnl_usdt)::numeric, 4) as avg_pnl_usdt,
  ROUND(SUM(net_pnl_usdt)::numeric, 2) as total_pnl_usdt
FROM trades t
JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.created_at > NOW() - INTERVAL '{lookback} hours'
  AND ((t.direction = 'LONG' AND t.rsi_at_entry > 70) OR (t.direction = 'SHORT' AND t.rsi_at_entry < 30))
  AND tam.max_price_reached IS NOT NULL
""")

with engine.connect() as conn:
    r = conn.execute(query1).fetchone()
    print(f"\nLookback: {lookback}h")
    print(f"RSI Extreme trades (MFE valide): {r[0]}")
    print(f"Wins: {r[1]} | Losses: {r[2]}")
    print(f"Win Rate: {r[3]}%")
    print(f"Avg PnL: {r[4]} USDT")
    print(f"Total PnL: {r[5]} USDT")

# Compare with ALL trades
query2 = text(f"""
SELECT 
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
  ROUND(AVG(net_pnl_usdt)::numeric, 4) as avg_pnl_usdt
FROM trades t
WHERE t.created_at > NOW() - INTERVAL '{lookback} hours'
""")

with engine.connect() as conn:
    r = conn.execute(query2).fetchone()
    print(f"\nALL trades (comparison): {r[0]}")
    print(f"Win Rate: {r[1]}%")
    print(f"Avg PnL: {r[2]} USDT")

# Breakdown: trades where Quick Exit would HELP vs HURT
query3 = text(f"""
WITH rsi_trades AS (
  SELECT 
    t.id,
    t.direction,
    t.entry_price,
    t.net_pnl_usdt,
    tam.max_price_reached,
    tam.min_price_reached,
    CASE 
      WHEN t.direction = 'LONG' THEN (tam.max_price_reached - t.entry_price) / t.entry_price * 100
      ELSE (t.entry_price - tam.min_price_reached) / t.entry_price * 100
    END as mfe_pct
  FROM trades t
  JOIN trade_atr_metrics tam ON t.id = tam.trade_id
  WHERE t.created_at > NOW() - INTERVAL '{lookback} hours'
    AND ((t.direction = 'LONG' AND t.rsi_at_entry > 70) OR (t.direction = 'SHORT' AND t.rsi_at_entry < 30))
    AND tam.max_price_reached IS NOT NULL
)
SELECT
  -- Trades where MFE >= 0.08% (would trigger quick exit at 0.05% net after 0.03% slippage)
  SUM(CASE WHEN mfe_pct >= 0.08 THEN 1 ELSE 0 END) as qe_triggered,
  -- Of those, how many had actual PnL > 0.05% (quick exit HURT them)
  SUM(CASE WHEN mfe_pct >= 0.08 AND (net_pnl_usdt / 0.25) > 0.05 THEN 1 ELSE 0 END) as qe_hurt,
  -- Of those, how many had actual PnL <= 0 (quick exit HELPED them)
  SUM(CASE WHEN mfe_pct >= 0.08 AND net_pnl_usdt <= 0 THEN 1 ELSE 0 END) as qe_helped,
  -- Trades where MFE < 0.08% (quick exit wouldn't trigger)
  SUM(CASE WHEN mfe_pct < 0.08 THEN 1 ELSE 0 END) as qe_not_triggered
FROM rsi_trades
""")

with engine.connect() as conn:
    r = conn.execute(query3).fetchone()
    print(f"\n" + "-" * 70)
    print("QUICK EXIT IMPACT ANALYSIS (threshold=0.05%, slippage=0.03%)")
    print("-" * 70)
    print(f"Quick Exit would trigger: {r[0]} trades")
    print(f"  - QE would HURT (actual PnL > +0.05%): {r[1]} trades")
    print(f"  - QE would HELP (actual PnL <= 0): {r[2]} trades")
    print(f"Quick Exit wouldn't trigger (MFE too low): {r[3]} trades")

# Average PnL of trades where QE triggers
query4 = text(f"""
WITH rsi_trades AS (
  SELECT 
    t.net_pnl_usdt,
    CASE 
      WHEN t.direction = 'LONG' THEN (tam.max_price_reached - t.entry_price) / t.entry_price * 100
      ELSE (t.entry_price - tam.min_price_reached) / t.entry_price * 100
    END as mfe_pct
  FROM trades t
  JOIN trade_atr_metrics tam ON t.id = tam.trade_id
  WHERE t.created_at > NOW() - INTERVAL '{lookback} hours'
    AND ((t.direction = 'LONG' AND t.rsi_at_entry > 70) OR (t.direction = 'SHORT' AND t.rsi_at_entry < 30))
    AND tam.max_price_reached IS NOT NULL
)
SELECT
  ROUND(AVG(CASE WHEN mfe_pct >= 0.08 THEN net_pnl_usdt END)::numeric, 4) as avg_pnl_qe_triggered,
  ROUND(AVG(CASE WHEN mfe_pct < 0.08 THEN net_pnl_usdt END)::numeric, 4) as avg_pnl_qe_not_triggered
FROM rsi_trades
""")

with engine.connect() as conn:
    r = conn.execute(query4).fetchone()
    print(f"\nAvg PnL when QE would trigger: {r[0]} USDT")
    print(f"Avg PnL when QE wouldn't trigger: {r[1]} USDT")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)

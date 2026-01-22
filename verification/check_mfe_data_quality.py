"""Check MFE data quality for Quick Exit analysis"""
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

lookback_hours = int(os.getenv('LOOKBACK_HOURS', '168'))

print("=" * 70)
print("MFE DATA QUALITY CHECK - QUICK EXIT ANALYSIS")
print("=" * 70)

# Check MFE availability for RSI extreme trades
query1 = text(f"""
SELECT 
    COUNT(*) as total,
    COUNT(tam.max_price_reached) as with_mfe,
    COUNT(*) - COUNT(tam.max_price_reached) as without_mfe,
    ROUND(100.0 * COUNT(tam.max_price_reached) / NULLIF(COUNT(*), 0), 1) as pct_with_mfe
FROM trades t
LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
  AND (
    (t.direction = 'LONG' AND t.rsi_at_entry > 70)
    OR
    (t.direction = 'SHORT' AND t.rsi_at_entry < 30)
  )
""")

with engine.connect() as conn:
    r = conn.execute(query1).fetchone()
    print(f"\nLookback: {lookback_hours}h")
    print(f"Total trades RSI extreme: {r[0]}")
    print(f"Avec MFE (max_price_reached NOT NULL): {r[1]} ({r[3] or 0}%)")
    print(f"Sans MFE (NULL): {r[2]}")

# Check if trade_atr_metrics exists for these trades
query2 = text(f"""
SELECT 
    COUNT(*) as total,
    COUNT(tam.trade_id) as with_tam_row,
    COUNT(*) - COUNT(tam.trade_id) as without_tam_row
FROM trades t
LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
  AND (
    (t.direction = 'LONG' AND t.rsi_at_entry > 70)
    OR
    (t.direction = 'SHORT' AND t.rsi_at_entry < 30)
  )
""")

with engine.connect() as conn:
    r = conn.execute(query2).fetchone()
    print(f"\nTrades avec ligne trade_atr_metrics: {r[1]}")
    print(f"Trades sans ligne trade_atr_metrics: {r[2]}")

# Sample trades WITH MFE to verify data
query3 = text(f"""
SELECT 
    t.id,
    t.symbol,
    t.direction,
    t.rsi_at_entry,
    t.entry_price,
    t.exit_price,
    t.net_pnl_usdt,
    tam.max_price_reached,
    tam.min_price_reached,
    t.created_at
FROM trades t
LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
  AND (
    (t.direction = 'LONG' AND t.rsi_at_entry > 70)
    OR
    (t.direction = 'SHORT' AND t.rsi_at_entry < 30)
  )
  AND tam.max_price_reached IS NOT NULL
ORDER BY t.created_at DESC
LIMIT 10
""")

with engine.connect() as conn:
    result = conn.execute(query3)
    rows = result.fetchall()
    cols = list(result.keys())

print("\n" + "-" * 70)
print("SAMPLE: 10 trades RSI extreme AVEC MFE valide")
print("-" * 70)

if rows:
    for row in rows:
        t = dict(zip(cols, row))
        entry = t['entry_price'] or 1
        max_p = t['max_price_reached']
        min_p = t['min_price_reached']
        direction = t['direction']
        
        if direction == 'LONG':
            mfe_pct = ((max_p - entry) / entry * 100) if max_p else 0
        else:
            mfe_pct = ((entry - min_p) / entry * 100) if min_p else 0
        
        symbol = (t['symbol'] or '').replace('/USDT:USDT', '')
        print(f"{symbol:<10} {direction:<6} RSI={t['rsi_at_entry']:.1f} MFE={mfe_pct:+.2f}% PnL={t['net_pnl_usdt'] or 0:+.2f}$")
else:
    print("Aucun trade avec MFE valide trouvé!")

# Check recent trades (last 24h) specifically
query4 = text("""
SELECT 
    COUNT(*) as total,
    COUNT(tam.max_price_reached) as with_mfe
FROM trades t
LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.created_at > NOW() - INTERVAL '24 hours'
  AND (
    (t.direction = 'LONG' AND t.rsi_at_entry > 70)
    OR
    (t.direction = 'SHORT' AND t.rsi_at_entry < 30)
  )
""")

with engine.connect() as conn:
    r = conn.execute(query4).fetchone()
    print(f"\n24h RÉCENTES: {r[0]} trades RSI extreme, {r[1]} avec MFE")

# Overall MFE fill rate
query5 = text(f"""
SELECT 
    COUNT(*) as total,
    COUNT(tam.max_price_reached) as with_mfe,
    ROUND(100.0 * COUNT(tam.max_price_reached) / NULLIF(COUNT(*), 0), 1) as pct
FROM trades t
LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
""")

with engine.connect() as conn:
    r = conn.execute(query5).fetchone()
    print(f"\nTOUS les trades (7j): {r[0]} total, {r[1]} avec MFE ({r[2] or 0}%)")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)

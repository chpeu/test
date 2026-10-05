"""
Check PnL data quality - look for outliers and suspicious values
"""
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

print("=" * 80)
print("DATA QUALITY CHECK - PnL / MFE / MAE")
print("=" * 80)

# Check for outliers in PnL
query1 = text(f"""
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN net_pnl_usdt > 1 THEN 1 END) as pnl_gt_1usd,
    COUNT(CASE WHEN net_pnl_usdt < -1 THEN 1 END) as pnl_lt_minus1usd,
    COUNT(CASE WHEN net_pnl_usdt > 0.5 THEN 1 END) as pnl_gt_05usd,
    COUNT(CASE WHEN net_pnl_usdt < -0.5 THEN 1 END) as pnl_lt_minus05usd,
    ROUND(MIN(net_pnl_usdt)::numeric, 4) as min_pnl,
    ROUND(MAX(net_pnl_usdt)::numeric, 4) as max_pnl,
    ROUND(AVG(net_pnl_usdt)::numeric, 4) as avg_pnl,
    ROUND(STDDEV(net_pnl_usdt)::numeric, 4) as std_pnl
FROM trades t
JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
  AND tam.max_price_reached IS NOT NULL
""")

with engine.connect() as conn:
    r = conn.execute(query1).fetchone()
    print(f"\nLookback: {lookback_hours}h")
    print(f"Total trades avec MFE: {r[0]}")
    print(f"\nDistribution PnL (USDT):")
    print(f"  Min: {r[5]} | Max: {r[6]} | Avg: {r[7]} | Std: {r[8]}")
    print(f"  PnL > +1$: {r[1]} | PnL < -1$: {r[2]}")
    print(f"  PnL > +0.5$: {r[3]} | PnL < -0.5$: {r[4]}")

# Check MFE distribution
query2 = text(f"""
WITH mfe_data AS (
    SELECT 
        t.id,
        t.direction,
        t.entry_price,
        tam.max_price_reached,
        tam.min_price_reached,
        t.net_pnl_usdt,
        CASE 
            WHEN t.direction = 'LONG' THEN (tam.max_price_reached - t.entry_price) / t.entry_price * 100
            ELSE (t.entry_price - tam.min_price_reached) / t.entry_price * 100
        END as mfe_pct
    FROM trades t
    JOIN trade_atr_metrics tam ON t.id = tam.trade_id
    WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
      AND tam.max_price_reached IS NOT NULL
      AND t.entry_price IS NOT NULL
)
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN mfe_pct > 1 THEN 1 END) as mfe_gt_1pct,
    COUNT(CASE WHEN mfe_pct > 0.5 THEN 1 END) as mfe_gt_05pct,
    COUNT(CASE WHEN mfe_pct < 0.05 THEN 1 END) as mfe_lt_005pct,
    ROUND(MIN(mfe_pct)::numeric, 4) as min_mfe,
    ROUND(MAX(mfe_pct)::numeric, 4) as max_mfe,
    ROUND(AVG(mfe_pct)::numeric, 4) as avg_mfe,
    ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY mfe_pct)::numeric, 4) as p50_mfe,
    ROUND(percentile_cont(0.9) WITHIN GROUP (ORDER BY mfe_pct)::numeric, 4) as p90_mfe
FROM mfe_data
""")

with engine.connect() as conn:
    r = conn.execute(query2).fetchone()
    print(f"\nDistribution MFE (%):")
    print(f"  Min: {r[4]}% | Max: {r[5]}% | Avg: {r[6]}%")
    print(f"  P50: {r[7]}% | P90: {r[8]}%")
    print(f"  MFE > 1%: {r[1]} | MFE > 0.5%: {r[2]} | MFE < 0.05%: {r[3]}")

# Check for suspicious trades: MFE very high but PnL negative
query3 = text(f"""
WITH trade_data AS (
    SELECT 
        t.id,
        t.symbol,
        t.direction,
        t.entry_price,
        t.exit_price,
        tam.max_price_reached,
        tam.min_price_reached,
        t.net_pnl_usdt,
        t.created_at,
        CASE 
            WHEN t.direction = 'LONG' THEN (tam.max_price_reached - t.entry_price) / t.entry_price * 100
            ELSE (t.entry_price - tam.min_price_reached) / t.entry_price * 100
        END as mfe_pct,
        CASE 
            WHEN t.direction = 'LONG' THEN (t.exit_price - t.entry_price) / t.entry_price * 100
            ELSE (t.entry_price - t.exit_price) / t.entry_price * 100
        END as pnl_pct_calculated
    FROM trades t
    JOIN trade_atr_metrics tam ON t.id = tam.trade_id
    WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
      AND tam.max_price_reached IS NOT NULL
      AND t.entry_price IS NOT NULL
)
SELECT 
    id, symbol, direction, 
    ROUND(entry_price::numeric, 6) as entry,
    ROUND(exit_price::numeric, 6) as exit,
    ROUND(max_price_reached::numeric, 6) as max_p,
    ROUND(min_price_reached::numeric, 6) as min_p,
    ROUND(net_pnl_usdt::numeric, 4) as pnl_usdt,
    ROUND(mfe_pct::numeric, 4) as mfe_pct,
    ROUND(pnl_pct_calculated::numeric, 4) as pnl_pct
FROM trade_data
WHERE mfe_pct > 0.5 AND net_pnl_usdt < -0.1
ORDER BY mfe_pct DESC
LIMIT 15
""")

with engine.connect() as conn:
    result = conn.execute(query3)
    rows = result.fetchall()
    cols = list(result.keys())

print(f"\n" + "-" * 80)
print("TRADES SUSPECTS: MFE > 0.5% mais PnL < -0.10$ (max 15)")
print("-" * 80)

if rows:
    print(f"{'Symbol':<10} {'Dir':<6} {'Entry':<12} {'Exit':<12} {'Max/Min P':<12} {'MFE%':<8} {'PnL$':<8}")
    print("-" * 80)
    for row in rows:
        t = dict(zip(cols, row))
        max_min = t['max_p'] if t['direction'] == 'LONG' else t['min_p']
        print(f"{t['symbol']:<10} {t['direction']:<6} {t['entry']:<12} {t['exit']:<12} {max_min:<12} {t['mfe_pct']:+.2f}%   {t['pnl_usdt']:+.2f}$")
    print(f"\n⚠️ {len(rows)} trades avec MFE élevé mais PnL négatif - normal si le prix a atteint MFE puis retracé")
else:
    print("Aucun trade suspect trouvé")

# Check for impossible values: MFE negative or exit_price outside entry-max range
query4 = text(f"""
WITH trade_data AS (
    SELECT 
        t.id,
        t.symbol,
        t.direction,
        t.entry_price,
        t.exit_price,
        tam.max_price_reached,
        tam.min_price_reached,
        CASE 
            WHEN t.direction = 'LONG' THEN (tam.max_price_reached - t.entry_price) / t.entry_price * 100
            ELSE (t.entry_price - tam.min_price_reached) / t.entry_price * 100
        END as mfe_pct
    FROM trades t
    JOIN trade_atr_metrics tam ON t.id = tam.trade_id
    WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
      AND tam.max_price_reached IS NOT NULL
)
SELECT 
    COUNT(CASE WHEN mfe_pct < 0 THEN 1 END) as negative_mfe,
    COUNT(CASE WHEN direction = 'LONG' AND exit_price > max_price_reached THEN 1 END) as exit_gt_max_long,
    COUNT(CASE WHEN direction = 'SHORT' AND exit_price < min_price_reached THEN 1 END) as exit_lt_min_short
FROM trade_data
""")

with engine.connect() as conn:
    r = conn.execute(query4).fetchone()
    print(f"\n" + "-" * 80)
    print("VALEURS IMPOSSIBLES:")
    print("-" * 80)
    print(f"  MFE négatif: {r[0]}")
    print(f"  LONG avec exit > max_price: {r[1]}")
    print(f"  SHORT avec exit < min_price: {r[2]}")
    
    if r[0] > 0 or r[1] > 0 or r[2] > 0:
        print("  ⚠️ DONNÉES CORROMPUES DÉTECTÉES!")
    else:
        print("  ✅ Pas de valeurs impossibles détectées")

# Summary statistics for baseline verification
query5 = text(f"""
SELECT 
    COUNT(*) as total,
    ROUND(SUM(net_pnl_usdt)::numeric, 2) as total_pnl_usdt,
    ROUND(AVG(net_pnl_usdt)::numeric, 4) as avg_pnl_usdt,
    SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as winrate
FROM trades t
JOIN trade_atr_metrics tam ON t.id = tam.trade_id
WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
  AND tam.max_price_reached IS NOT NULL
""")

with engine.connect() as conn:
    r = conn.execute(query5).fetchone()
    print(f"\n" + "=" * 80)
    print("RÉSUMÉ BASELINE (trades avec MFE valide)")
    print("=" * 80)
    print(f"Total trades: {r[0]}")
    print(f"Total PnL: {r[1]} USDT")
    print(f"Avg PnL: {r[2]} USDT/trade")
    print(f"Wins: {r[3]} | Win Rate: {r[4]}%")

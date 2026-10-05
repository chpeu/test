"""
Vérifier le PnL depuis 06/01 20:19:41 jusqu'à maintenant
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*70)
print("🔍 PnL depuis 06/01 20:19:41")
print("="*70)

# Définir la période
start_time = datetime(2026, 1, 6, 20, 19, 41)
now = datetime.now()

print(f"\n📅 Période: {start_time:%Y-%m-%d %H:%M:%S} → {now:%Y-%m-%d %H:%M:%S}")
print(f"   Durée: {(now - start_time).total_seconds() / 3600:.1f} heures")

# 1. PnL total sur la période
cur.execute("""
    SELECT 
        COUNT(*) as total_trades,
        SUM(pnl_pct) as total_pct,
        SUM(pnl_usdt) as total_usdt,
        SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as winners,
        SUM(CASE WHEN pnl_pct < 0 THEN 1 ELSE 0 END) as losers,
        SUM(CASE WHEN pnl_pct = 0 THEN 1 ELSE 0 END) as neutrals
    FROM trades
    WHERE timestamp_exit >= %s AND exit_price IS NOT NULL
""", (start_time,))
result = cur.fetchone()

print(f"\n📊 PERFORMANCE TOTALE:")
print(f"   Trades: {result['total_trades']}")
print(f"   PnL: {result['total_pct']:+.3f}% ({result['total_usdt']:+.4f} USDT)")
print(f"   Gagnants: {result['winners']} ({result['winners']/result['total_trades']*100:.0f}%)")
print(f"   Perdants: {result['losers']} ({result['losers']/result['total_trades']*100:.0f}%)")
print(f"   Neutres: {result['neutrals']}")

# 2. PnL des trades AVEC métriques sur la période
cur.execute("""
    SELECT 
        COUNT(*) as trades_with_metrics,
        SUM(t.pnl_pct) as pnl_with_metrics,
        SUM(t.pnl_usdt) as usdt_with_metrics
    FROM trades t
    JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
    WHERE t.timestamp_exit >= %s AND t.exit_price IS NOT NULL
""", (start_time,))
with_metrics = cur.fetchone()

print(f"\n📊 AVEC MÉTRIQUES:")
print(f"   Trades: {with_metrics['trades_with_metrics']}")
print(f"   PnL: {with_metrics['pnl_with_metrics']:+.3f}% ({with_metrics['usdt_with_metrics']:+.4f} USDT)")

# 3. PnL des trades SANS métriques sur la période
cur.execute("""
    SELECT 
        COUNT(*) as trades_without_metrics,
        SUM(t.pnl_pct) as pnl_without_metrics,
        SUM(t.pnl_usdt) as usdt_without_metrics
    FROM trades t
    LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
    WHERE t.timestamp_exit >= %s AND t.exit_price IS NOT NULL AND m.trade_id IS NULL
""", (start_time,))
without_metrics = cur.fetchone()

print(f"\n⚠️ SANS MÉTRIQUES:")
print(f"   Trades: {without_metrics['trades_without_metrics']}")
if without_metrics['pnl_without_metrics'] is not None:
    print(f"   PnL: {without_metrics['pnl_without_metrics']:+.3f}% ({without_metrics['usdt_without_metrics']:+.4f} USDT)")
else:
    print(f"   PnL: N/A")

# 4. Détail par heure
cur.execute("""
    SELECT 
        DATE_TRUNC('hour', timestamp_exit) as hour,
        COUNT(*) as trades,
        SUM(pnl_pct) as pnl_pct,
        SUM(pnl_usdt) as pnl_usdt,
        COUNT(CASE WHEN m.trade_id IS NOT NULL THEN 1 END) as with_metrics
    FROM trades t
    LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
    WHERE t.timestamp_exit >= %s AND t.exit_price IS NOT NULL
    GROUP BY DATE_TRUNC('hour', timestamp_exit)
    ORDER BY hour DESC
""", (start_time,))
hourly = cur.fetchall()

print(f"\n⏰ DÉTAIL PAR HEURE:")
for row in hourly:
    row = dict(row)
    hour = row['hour']
    if hour:
        hour_str = hour.strftime('%H:%M')
    else:
        hour_str = '??:??'
    
    metrics_pct = row['with_metrics'] / row['trades'] * 100 if row['trades'] > 0 else 0
    print(f"   {hour_str} | Trades: {row['trades']:>2} | PnL: {row['pnl_pct']:+6.3f}% | Métriques: {metrics_pct:.0f}%")

# 5. Derniers trades détaillés
cur.execute("""
    SELECT 
        symbol,
        direction,
        pnl_pct,
        pnl_usdt,
        exit_reason,
        timestamp_exit,
        CASE WHEN m.trade_id IS NOT NULL THEN '✅' ELSE '❌' END as has_metrics
    FROM trades t
    LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
    WHERE t.timestamp_exit >= %s AND t.exit_price IS NOT NULL
    ORDER BY t.timestamp_exit DESC
    LIMIT 10
""", (start_time,))
recent = cur.fetchall()

print(f"\n DERNIERS TRADES:")
for trade in recent:
    trade = dict(trade)
    pnl_color = "🟢" if trade['pnl_pct'] > 0 else "🔴" if trade['pnl_pct'] < 0 else "⚪"
    exit_icons = {'TS': '🎢', 'SL': '❌', 'TP': '✅', 'SL_EXCHANGE': '🏦', 'STAGNATION': '⏰'}
    exit_icon = exit_icons.get(trade['exit_reason'], '❓')
    
    print(f"   {pnl_color} {trade['timestamp_exit']:%H:%M:%S} | {trade['symbol']:<15} | "
          f"{trade['direction']:<5} | {trade['pnl_pct']:+6.3f}% | "
          f"{exit_icon}{trade['exit_reason']:<12} | {trade['has_metrics']}")

cur.close()
conn.close()
print("="*70)

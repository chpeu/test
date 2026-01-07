"""
Vérifier la divergence de PnL entre les 21 derniers trades et les stats globales
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*70)
print("🔍 ANALYSE DIVERGENCE PnL")
print("="*70)

# 1. PnL des 21 derniers trades avec métriques
cur.execute("""
    SELECT SUM(pnl_pct) as pnl_21_pct, SUM(pnl_usdt) as pnl_21_usdt, COUNT(*) as count
    FROM (
        SELECT t.pnl_pct, t.pnl_usdt
        FROM trades t
        JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
        WHERE t.exit_price IS NOT NULL
        ORDER BY t.timestamp_exit DESC
        LIMIT 21
    ) as subq
""")
result_21 = cur.fetchone()
print(f"\n📊 21 derniers trades (avec métriques):")
print(f"   PnL: {result_21['pnl_21_pct']:+.3f}% ({result_21['pnl_21_usdt']:+.4f} USDT)")
print(f"   Count: {result_21['count']} trades")

# 2. PnL des 21 derniers trades TOUS (sans filtre métriques)
cur.execute("""
    SELECT SUM(pnl_pct) as pnl_21_all_pct, SUM(pnl_usdt) as pnl_21_all_usdt, COUNT(*) as count
    FROM (
        SELECT pnl_pct, pnl_usdt
        FROM trades
        WHERE exit_price IS NOT NULL
        ORDER BY timestamp_exit DESC
        LIMIT 21
    ) as subq
""")
result_21_all = cur.fetchone()
print(f"\n📊 21 derniers trades (tous):")
print(f"   PnL: {result_21_all['pnl_21_all_pct']:+.3f}% ({result_21_all['pnl_21_all_usdt']:+.4f} USDT)")
print(f"   Count: {result_21_all['count']} trades")

# 3. PnL total de tous les trades
cur.execute("""
    SELECT SUM(pnl_pct) as pnl_total_pct, SUM(pnl_usdt) as pnl_total_usdt, COUNT(*) as count
    FROM trades
    WHERE exit_price IS NOT NULL
""")
result_total = cur.fetchone()
print(f"\n📊 TOUS les trades:")
print(f"   PnL: {result_total['pnl_total_pct']:+.3f}% ({result_total['pnl_total_usdt']:+.4f} USDT)")
print(f"   Count: {result_total['count']} trades")

# 4. PnL des trades SANS métriques (gap)
cur.execute("""
    SELECT t.id, t.symbol, t.pnl_pct, t.timestamp_exit
    FROM trades t
    LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
    WHERE t.exit_price IS NOT NULL AND m.trade_id IS NULL
    ORDER BY t.timestamp_exit DESC
    LIMIT 10
""")
missing_metrics = cur.fetchall()

print(f"\n⚠️ Trades SANS métriques (10 premiers):")
if missing_metrics:
    for trade in missing_metrics:
        trade = dict(trade)
        print(f"   {trade['timestamp_exit']:%Y-%m-%d %H:%M} | {trade['symbol']:<15} | PnL: {trade['pnl_pct']:+.3f}%")
else:
    print("   ✅ Tous les trades ont des métriques")

# 5. Compter le gap exact
cur.execute("""
    SELECT COUNT(*) as missing_count, SUM(pnl_pct) as missing_pnl
    FROM trades t
    LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
    WHERE t.exit_price IS NOT NULL AND m.trade_id IS NULL
""")
gap_info = cur.fetchone()

print(f"\n📊 Gap de métriques:")
print(f"   Trades sans métriques: {gap_info['missing_count']}")
print(f"   PnL de ces trades: {gap_info['missing_pnl']:+.3f}%")

# 6. Vérifier la date du bug
cur.execute("""
    SELECT DATE(t.timestamp_exit) as date, 
           COUNT(*) FILTER (WHERE m.trade_id IS NULL) as missing_count,
           COUNT(*) as total_count,
           SUM(t.pnl_pct) as total_pnl,
           SUM(t.pnl_pct) FILTER (WHERE m.trade_id IS NULL) as missing_pnl
    FROM trades t
    LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
    WHERE t.exit_price IS NOT NULL 
    GROUP BY DATE(t.timestamp_exit)
    ORDER BY DATE(t.timestamp_exit) DESC
    LIMIT 10
""")
daily = cur.fetchall()

print(f"\n📅 PnL par jour (avec/ sans métriques):")
for row in daily:
    row = dict(row)
    has_metrics = "✅" if row['missing_count'] == 0 else "❌"
    print(f"   {row['date']} | {has_metrics} | Total: {row['total_count']} | Manquant: {row['missing_count']} | PnL: {row['total_pnl']:+.3f}%")

cur.close()
conn.close()
print("="*70)

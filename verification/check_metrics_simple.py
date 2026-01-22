"""
Analyse simple des trades et métriques ATR
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*80)
print("📊 ANALYSE DES 10 DERNIERS TRADES")
print("="*80)

# Récupérer trades
cur.execute("""
    SELECT id, symbol, exit_reason, pnl_pct, timestamp_exit
    FROM trades 
    WHERE exit_price IS NOT NULL 
    ORDER BY timestamp_exit DESC 
    LIMIT 10
""")
trades = [dict(r) for r in cur.fetchall()]

print(f"\n{'Symbol':<20} | {'Exit':<12} | {'PnL':>8} | {'Metrics':^8} | {'MFE':>10} | {'Trail':^6} | {'BE':^4}")
print("-"*90)

missing_count = 0
for t in trades:
    tid = str(t['id'])
    cur.execute("SELECT max_pnl_reached, trailing_activated, be_triggered FROM trade_atr_metrics WHERE trade_id = %s", (tid,))
    m = cur.fetchone()
    
    has_m = 'OUI' if m else 'NON'
    if not m:
        missing_count += 1
    
    mfe = f"{m['max_pnl_reached']:.3f}%" if m and m['max_pnl_reached'] else "NULL"
    trail = "✅" if m and m['trailing_activated'] else "❌"
    be = "✅" if m and m['be_triggered'] else "❌"
    
    symbol = t['symbol'][:18] if t['symbol'] else 'N/A'
    exit_r = t['exit_reason'] or 'N/A'
    pnl = t['pnl_pct'] or 0
    
    print(f"{symbol:<20} | {exit_r:<12} | {pnl:+.3f}% | {has_m:^8} | {mfe:>10} | {trail:^6} | {be:^4}")

# Stats
print(f"\n📈 RÉSUMÉ")
print("-"*40)
print(f"   Trades analysés: {len(trades)}")
print(f"   Sans métriques ATR: {missing_count}")
print(f"   Couverture: {(len(trades) - missing_count) / len(trades) * 100:.0f}%")

# Compter total
cur.execute("SELECT COUNT(*) as cnt FROM trades WHERE exit_price IS NOT NULL")
total = cur.fetchone()['cnt']
cur.execute("SELECT COUNT(*) as cnt FROM trade_atr_metrics")
total_m = cur.fetchone()['cnt']
print(f"\n   Total trades fermés: {total}")
print(f"   Total métriques ATR: {total_m}")

cur.close()
conn.close()
print("="*80)

"""
Vérifier pourquoi les métriques ATR ne sont pas enregistrées
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

# Vérifier le type de trade_id dans trade_atr_metrics
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'trade_atr_metrics' AND column_name = 'trade_id'
""")
col_info = cur.fetchone()
print(f"trade_atr_metrics.trade_id type: {col_info['data_type'] if col_info else 'N/A'}")

print("="*70)
print("📊 ANALYSE DES 10 DERNIERS TRADES")
print("="*70)

# Récupérer trades et métriques séparément
cur.execute("""
    SELECT id, symbol, exit_reason, pnl_pct, timestamp_exit
    FROM trades 
    WHERE exit_price IS NOT NULL 
    ORDER BY timestamp_exit DESC 
    LIMIT 10
""")
trades = [dict(r) for r in cur.fetchall()]

# Pour chaque trade, chercher les métriques
for t in trades:
    tid = str(t['id'])
    cur.execute("SELECT max_pnl_reached, trailing_activated, be_triggered FROM trade_atr_metrics WHERE trade_id = %s", (tid,))
    m = cur.fetchone()
    t['has_metrics'] = 'OUI' if m else 'NON'
    t['mfe'] = m['max_pnl_reached'] if m else None
    t['trailing'] = m['trailing_activated'] if m else None
    t['be'] = m['be_triggered'] if m else None

trades = cur.fetchall()

print(f"\n{'Symbol':<20} | {'Exit':<12} | {'PnL':>8} | {'Metrics':^8} | {'MFE':>8} | {'Trail':^6} | {'BE':^4}")
print("-"*85)

trades_without_metrics = []
for r in trades:
    r = dict(r)
    symbol = r['symbol'][:18]
    exit_r = r['exit_reason'] or 'N/A'
    pnl = r['pnl_pct'] or 0
    has_m = r['has_metrics']
    mfe = f"{r['mfe']:.3f}%" if r['mfe'] else "NULL"
    trail = "✅" if r['trailing_activated'] else "❌"
    be = "✅" if r['be_triggered'] else "❌"
    
    print(f"{symbol:<20} | {exit_r:<12} | {pnl:+.3f}% | {has_m:^8} | {mfe:>8} | {trail:^6} | {be:^4}")
    
    if has_m == 'NON':
        trades_without_metrics.append(r)

# Analyse des trades sans métriques
if trades_without_metrics:
    print(f"\n⚠️ {len(trades_without_metrics)} TRADES SANS MÉTRIQUES ATR")
    print("-"*70)
    
    for t in trades_without_metrics:
        trade_id = str(t['id'])
        print(f"\n   Trade ID: {trade_id}")
        print(f"   Symbol: {t['symbol']}")
        print(f"   Exit: {t['exit_reason']}")
        print(f"   Timestamp: {t['timestamp_exit']}")
        
        # Vérifier si une entrée existe avec un ID différent
        cur.execute("""
            SELECT trade_id FROM trade_atr_metrics 
            WHERE trade_id LIKE %s
        """, (f"%{trade_id[:8]}%",))
        
        similar = cur.fetchall()
        if similar:
            print(f"   → Entrées similaires trouvées: {[s['trade_id'] for s in similar]}")
        else:
            print(f"   → Aucune entrée similaire")

# Statistiques globales
print(f"\n📈 STATISTIQUES")
print("-"*70)

cur.execute("SELECT COUNT(*) as cnt FROM trades WHERE exit_price IS NOT NULL")
total_trades = cur.fetchone()['cnt']

cur.execute("SELECT COUNT(*) as cnt FROM trade_atr_metrics")
total_metrics = cur.fetchone()['cnt']

cur.execute("""
    SELECT COUNT(*) as cnt 
    FROM trades t
    LEFT JOIN trade_atr_metrics m ON t.id::text = m.trade_id
    WHERE t.exit_price IS NOT NULL AND m.trade_id IS NULL
""")
missing = cur.fetchone()['cnt']

print(f"   Total trades fermés: {total_trades}")
print(f"   Total métriques ATR: {total_metrics}")
print(f"   Trades sans métriques: {missing}")
print(f"   Couverture: {(total_trades - missing) / total_trades * 100:.1f}%")

# Vérifier le format des IDs
print(f"\n🔍 FORMAT DES IDs")
print("-"*70)

cur.execute("SELECT id FROM trades ORDER BY timestamp_exit DESC LIMIT 3")
trade_ids = [str(r['id']) for r in cur.fetchall()]
print(f"   Exemples trade IDs: {trade_ids}")

cur.execute("SELECT trade_id FROM trade_atr_metrics ORDER BY created_at DESC LIMIT 3")
metric_ids = [r['trade_id'] for r in cur.fetchall()]
print(f"   Exemples metric trade_id: {metric_ids}")

# Comparer les formats
if trade_ids and metric_ids:
    print(f"\n   Trade ID type: {type(trade_ids[0])}, len={len(trade_ids[0])}")
    print(f"   Metric trade_id type: {type(metric_ids[0])}, len={len(metric_ids[0])}")

cur.close()
conn.close()

print("\n" + "="*70)

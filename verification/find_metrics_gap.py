"""
Trouver quand les métriques ATR ont arrêté d'être enregistrées
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

# Dernière métrique ATR enregistrée
cur.execute("""
    SELECT trade_id, created_at
    FROM trade_atr_metrics
    ORDER BY created_at DESC
    LIMIT 1
""")
last_metric = cur.fetchone()

print("="*70)
print("🔍 ANALYSE DU GAP DE MÉTRIQUES ATR")
print("="*70)

if last_metric:
    print(f"\n📊 Dernière métrique ATR enregistrée:")
    print(f"   Trade ID: {last_metric['trade_id'][:8]}...")
    print(f"   Created: {last_metric['created_at']}")
else:
    print("❌ Aucune métrique ATR trouvée!")

# Compter trades sans métriques
cur.execute("SELECT COUNT(*) as cnt FROM trades WHERE exit_price IS NOT NULL")
total_trades = cur.fetchone()['cnt']
cur.execute("SELECT COUNT(*) as cnt FROM trade_atr_metrics")
total_metrics = cur.fetchone()['cnt']
print(f"\n   Total trades: {total_trades}")
print(f"   Total métriques: {total_metrics}")
print(f"   Gap: {total_trades - total_metrics}")

# Premier trade SANS métrique
first_missing = None

if first_missing:
    print(f"\n⚠️ Premier trade SANS métrique:")
    print(f"   Trade: {first_missing['symbol']}")
    print(f"   Exit: {first_missing['timestamp_exit']}")
    print(f"   Reason: {first_missing['exit_reason']}")

# Compter trades par jour
print(f"\n📈 TRADES PAR JOUR (3 derniers jours):")
print("-"*50)

cur.execute("""
    SELECT 
        DATE(timestamp_exit) as day,
        COUNT(*) as total
    FROM trades
    WHERE exit_price IS NOT NULL 
      AND timestamp_exit > NOW() - INTERVAL '3 days'
    GROUP BY DATE(timestamp_exit)
    ORDER BY day DESC
""")

for r in cur.fetchall():
    r = dict(r)
    print(f"   {r['day']} | {r['total']} trades")

cur.close()
conn.close()
print("="*70)

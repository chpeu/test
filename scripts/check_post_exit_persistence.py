"""
Script pour vérifier la persistance des trackers post-exit après shutdown/restart
"""
import psycopg2
from datetime import datetime

# Connexion PostgreSQL
conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='trade_cursor_ml',
    user='postgres',
    password='@Cmtr1di12345'
)

cur = conn.cursor()

print("=" * 80)
print("🔍 VÉRIFICATION PERSISTANCE POST-EXIT")
print("=" * 80)

# 1. Vérifier les trackers actifs persistés
cur.execute('SELECT COUNT(*) FROM post_exit_active_trackers')
count = cur.fetchone()[0]
print(f"\n📊 Trackers actifs persistés: {count}")

if count > 0:
    cur.execute('''
        SELECT trade_id, symbol, samples_collected, 
               tracking_duration_sec, created_at, updated_at
        FROM post_exit_active_trackers 
        ORDER BY created_at DESC 
        LIMIT 5
    ''')
    rows = cur.fetchall()
    print("\n📋 Derniers trackers persistés:")
    for row in rows:
        trade_id, symbol, samples, duration, created, updated = row
        print(f"  • {symbol} (trade: {trade_id[:8]}...)")
        print(f"    Samples: {samples}, Durée: {duration}s")
        print(f"    Créé: {created}, MAJ: {updated}")
        print()

# 2. Vérifier les analyses post-exit complétées
cur.execute('''
    SELECT COUNT(*) as total,
           COUNT(ml_optimal_trailing_distance) as with_trailing
    FROM trade_post_exit_analysis
''')
total, with_trailing = cur.fetchone()
print(f"\n📈 Analyses post-exit complétées: {total}")
print(f"   Avec ml_optimal_trailing_distance: {with_trailing}")

# 3. Dernières analyses
cur.execute('''
    SELECT trade_id, symbol, exit_timing_grade, 
           ml_optimal_sl_pct, ml_optimal_trailing_trigger, 
           ml_optimal_trailing_distance, created_at
    FROM trade_post_exit_analysis 
    ORDER BY created_at DESC 
    LIMIT 3
''')
rows = cur.fetchall()
print("\n📋 Dernières analyses post-exit:")
for row in rows:
    trade_id, symbol, grade, sl, trigger, trailing_dist, created = row
    print(f"  • {symbol or 'N/A'} (trade: {trade_id[:8]}...)")
    print(f"    Grade: {grade}, SL: {sl}%, Trigger: {trigger}%")
    print(f"    Trailing Distance: {trailing_dist}%")
    print(f"    Créé: {created}")
    print()

# 4. Vérifier le trade XRP récent
cur.execute('''
    SELECT t.id, t.symbol, pea.exit_timestamp, t.pnl_pct,
           pea.exit_timing_grade, pea.ml_optimal_trailing_distance
    FROM trades t
    LEFT JOIN trade_post_exit_analysis pea ON t.id = pea.trade_id
    WHERE t.symbol LIKE '%XRP%'
    ORDER BY pea.exit_timestamp DESC NULLS LAST
    LIMIT 1
''')
row = cur.fetchone()
if row:
    trade_id, symbol, exit_time, pnl, grade, trailing_dist = row
    print(f"\n🔍 Dernier trade XRP:")
    print(f"  Trade ID: {trade_id}")
    print(f"  Symbol: {symbol}")
    print(f"  Exit: {exit_time}")
    print(f"  PnL: {pnl}%")
    print(f"  Grade post-exit: {grade or 'N/A'}")
    print(f"  Trailing distance optimal: {trailing_dist or 'N/A'}%")
else:
    print("\n⚠️ Aucun trade XRP trouvé")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("✅ Vérification terminée")
print("=" * 80)

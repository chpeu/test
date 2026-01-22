import sqlite3

conn = sqlite3.connect('data/analytics.db')
cursor = conn.cursor()

# Total trades
cursor.execute('SELECT COUNT(*) FROM trades')
total = cursor.fetchone()[0]
print(f'Total trades: {total}')

# Derniers 10 trades
cursor.execute('''
    SELECT 
        id, 
        symbol, 
        direction, 
        reason, 
        net_pnl_usdt, 
        ml_confidence, 
        ml_prediction,
        CASE 
            WHEN ml_features IS NULL THEN "NULL"
            WHEN ml_features = "null" THEN "json_null"
            ELSE "populated"
        END as ml_features_status
    FROM trades 
    ORDER BY id DESC 
    LIMIT 10
''')

rows = cursor.fetchall()
print("\nDerniers 10 trades:")
print("-" * 120)
for row in rows:
    print(f"ID={row[0]:3d} | {row[1]:8s} {row[2]:5s} | Exit={row[3]:20s} | PnL={row[4]:7.4f} | ML_conf={row[5]} | ML_pred={row[6]} | ML_feat={row[7]}")

# Stats sur ml_prediction et ml_features
cursor.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN ml_prediction IS NOT NULL THEN 1 ELSE 0 END) as with_prediction,
        SUM(CASE WHEN ml_features IS NOT NULL AND ml_features != "null" THEN 1 ELSE 0 END) as with_features
    FROM trades
''')
stats = cursor.fetchone()
print("\n" + "=" * 120)
print(f"Stats ML fields:")
print(f"  - Total trades: {stats[0]}")
print(f"  - Avec ml_prediction: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)")
print(f"  - Avec ml_features: {stats[2]} ({stats[2]/stats[0]*100:.1f}%)")

# Performance des 43 derniers trades
cursor.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) as wins,
        AVG(net_pnl_usdt) as avg_pnl,
        SUM(net_pnl_usdt) as total_pnl,
        AVG(ml_confidence) as avg_ml_conf
    FROM (SELECT * FROM trades ORDER BY id DESC LIMIT 43)
''')
perf = cursor.fetchone()
win_rate = perf[1] / perf[0] * 100 if perf[0] > 0 else 0
print("\n" + "=" * 120)
print(f"Performance des 43 derniers trades:")
print(f"  - Win rate: {perf[1]}/{perf[0]} = {win_rate:.1f}%")
print(f"  - PnL moyen: {perf[2]:.4f} USDT")
print(f"  - PnL total: {perf[3]:.4f} USDT")
print(f"  - ML confidence moyenne: {perf[4]:.1f}%" if perf[4] else "  - ML confidence moyenne: N/A")

# Raisons de sortie des 43 derniers
cursor.execute('''
    SELECT 
        reason,
        COUNT(*) as count,
        AVG(net_pnl_usdt) as avg_pnl
    FROM (SELECT * FROM trades ORDER BY id DESC LIMIT 43)
    GROUP BY reason
    ORDER BY count DESC
''')
print("\nRaisons de sortie (43 derniers trades):")
for row in cursor.fetchall():
    print(f"  - {row[0]:20s}: {row[1]:2d} trades (PnL moyen: {row[2]:7.4f})")

conn.close()

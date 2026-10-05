import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / 'data' / 'analytics.db'

if not db_path.exists():
    print(f"❌ DB n'existe pas: {db_path}")
else:
    print(f"✅ DB existe: {db_path}")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    total = cursor.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    closed = cursor.execute("SELECT COUNT(*) FROM trades WHERE exit IS NOT NULL").fetchone()[0]
    
    print(f"Total trades: {total}")
    print(f"Trades fermés: {closed}")
    
    if closed > 0:
        print("\nDerniers trades fermés:")
        cursor.execute("""
            SELECT id, symbol, direction, tp_sl_mode, reason, net_pnl_pct, timestamp
            FROM trades 
            WHERE exit IS NOT NULL 
            ORDER BY timestamp DESC 
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"  ID {row[0]}: {row[1]} {row[2]} | Mode={row[3]} | Sortie={row[4]} | PnL={row[5]:.2f}% | {row[6]}")
    
    conn.close()

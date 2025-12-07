import sqlite3
import sys
import os
import json
from datetime import datetime

# Connect to database
db_path = "data/analytics.db"
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    db_path = "analytics_instance_9999.db"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path} either.")
        # Try to find any db
        import glob
        dbs = glob.glob("*.db") + glob.glob("data/*.db")
        if dbs:
            db_path = dbs[0]
            print(f"Found DB: {db_path}")
        else:
            sys.exit(1)

print(f"Connecting to {db_path}...")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", [t['name'] for t in tables])

# Query recent trades
print("\n--- Recent Trades (Last 10) ---")
try:
    cursor.execute("""
        SELECT id, symbol, direction, entry, exit, exit_fill_price, reason, net_pnl_pct, net_pnl_usdt, created_at 
        FROM trades 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    trades = cursor.fetchall()
    
    print(f"{'ID':<5} | {'Symbol':<10} | {'Dir':<5} | {'Entry':<10} | {'Exit':<10} | {'Fill Exit':<10} | {'Reason':<10} | {'PnL %':<8} | {'PnL $':<8}")
    print("-" * 100)
    
    for t in trades:
        print(f"{t['id']:<5} | {t['symbol']:<10} | {t['direction']:<5} | {t['entry']:<10} | {t['exit']:<10} | {t['exit_fill_price'] or 'N/A':<10} | {t['reason']:<10} | {t['net_pnl_pct']:<8} | {t['net_pnl_usdt']:<8}")
        
except Exception as e:
    print(f"Error querying trades: {e}")
    # Check table schema
    cursor.execute("PRAGMA table_info(trades)")
    columns = cursor.fetchall()
    print("\nTrades table columns:")
    for col in columns:
        print(col['name'])

conn.close()

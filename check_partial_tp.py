"""Check partial_tp_profit and partial_tp_percent columns"""
import sys
import os

# Set environment variable for password before importing psycopg2
os.environ['PGPASSWORD'] = 'Goldorak69!'
os.environ['PGCLIENTENCODING'] = 'UTF8'

import psycopg2

def check_partial_tp():
    # Direct connection with explicit encoding
    conn = psycopg2.connect(
        "host=localhost port=5432 dbname=trade_cursor_ml user=postgres password=Goldorak69!"
    )
    conn.set_client_encoding('UTF8')
    cur = conn.cursor()
    
    # Check trade_atr_metrics table
    print("\n=== trade_atr_metrics ===")
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(partial_tp_profit) as with_profit,
            COUNT(partial_tp_percent) as with_percent
        FROM trade_atr_metrics
    """)
    row = cur.fetchone()
    print(f"Total records: {row[0]}")
    print(f"With partial_tp_profit: {row[1]} ({row[1]*100/row[0] if row[0] > 0 else 0:.1f}%)")
    print(f"With partial_tp_percent: {row[2]} ({row[2]*100/row[0] if row[0] > 0 else 0:.1f}%)")
    
    # Check recent trades with partial TP
    print("\n=== Recent trades with partial TP ===")
    cur.execute("""
        SELECT 
            t.symbol, t.direction, t.exit_reason, t.pnl_pct,
            m.partial_tp_profit, m.partial_tp_percent, m.partial_tp_executed
        FROM trades t
        LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
        WHERE m.partial_tp_executed = true
        ORDER BY t.timestamp_entry DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    
    if rows:
        for r in rows:
            print(f"  {r[0][:15]:15} | {r[1]:5} | {r[2]:10} | PnL:{r[3]:+.2f}% | TP_profit:{r[4]} | TP_pct:{r[5]}")
    else:
        print("  No trades with partial_tp_executed=true found")
    
    # Check if columns exist in trades table
    print("\n=== Checking trades table columns ===")
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trades' 
        AND column_name IN ('partial_tp_profit', 'partial_tp_percent')
    """)
    cols = cur.fetchall()
    print(f"Columns in trades table: {[c[0] for c in cols]}")
    
    # Check if columns exist in trade_atr_metrics table
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trade_atr_metrics' 
        AND column_name IN ('partial_tp_profit', 'partial_tp_percent', 'partial_tp_executed')
    """)
    cols = cur.fetchall()
    print(f"Columns in trade_atr_metrics table: {[c[0] for c in cols]}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_partial_tp()

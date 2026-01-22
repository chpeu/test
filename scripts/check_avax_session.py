#!/usr/bin/env python3
"""Check if AVAX trade session matches current session"""
import os
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load trade history JSON
json_file = "trade_history_instance_5000.json"
if os.path.exists(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        json_trades = json.load(f)
    print(f"JSON file has {len(json_trades)} trades")
    if json_trades:
        print(f"Last trade in JSON: {json_trades[-1].get('symbol')} at {json_trades[-1].get('closed_at')}")
else:
    print("No JSON file found")

# Check PostgreSQL
from core.postgresql_datalogger import PostgreSQLDataLogger
pg_logger = PostgreSQLDataLogger()
if pg_logger.enabled:
    conn = pg_logger.pool.getconn()
    try:
        with conn.cursor() as cur:
            # Get AVAX trade session
            cur.execute("""
                SELECT id, symbol, session_id, exit_reason, created_at, 
                       pnl_pct, is_live_trade, live_execution_mode
                FROM trades 
                WHERE symbol LIKE '%AVAX%'
                ORDER BY created_at DESC
                LIMIT 1
            """)
            avax = cur.fetchone()
            if avax:
                print(f"\nAVAX trade in PostgreSQL:")
                print(f"  ID: {avax[0]}")
                print(f"  Session ID: {avax[2]}")
                print(f"  Exit Reason: {avax[3]}")
                print(f"  Created At: {avax[4]}")
                print(f"  PnL %: {avax[5]}")
                print(f"  Is Live: {avax[6]}")
                print(f"  Execution Mode: {avax[7]}")
                
            # Get current session trades count
            cur.execute("""
                SELECT session_id, COUNT(*) as count, MIN(created_at), MAX(created_at)
                FROM trades 
                WHERE created_at > NOW() - INTERVAL '24 hours'
                GROUP BY session_id
                ORDER BY MAX(created_at) DESC
            """)
            sessions = cur.fetchall()
            print(f"\nRecent sessions (last 24h):")
            for s in sessions:
                print(f"  Session {s[0][:8]}...: {s[1]} trades ({s[2]} to {s[3]})")
                
    finally:
        pg_logger.pool.putconn(conn)

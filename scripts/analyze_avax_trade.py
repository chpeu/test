#!/usr/bin/env python3
import os
import sys
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.postgresql_datalogger import PostgreSQLDataLogger

def analyze_avax_trade():
    pg_logger = PostgreSQLDataLogger()
    if not pg_logger.enabled:
        print("PostgreSQL disabled")
        return

    conn = pg_logger.pool.getconn()
    try:
        with conn.cursor() as cur:
            # Find the latest AVAX trade
            # First get column names
            cur.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'trades' 
                AND column_name LIKE '%time%' OR column_name LIKE '%at%' OR column_name LIKE '%date%'
            """)
            time_cols = [r[0] for r in cur.fetchall()]
            print(f"Time-related columns: {time_cols}")
            
            cur.execute("""
                SELECT * FROM trades 
                WHERE symbol LIKE '%AVAX%'
                ORDER BY created_at DESC
                LIMIT 1
            """)
            trades = cur.fetchall()
            
            if not trades:
                print("No AVAX trades found in database.")
                return
            
            print(f"Found {len(trades)} AVAX trades:\n")
            
            # Get column names for this cursor
            col_names = [desc[0] for desc in cur.description]
            print(f"Columns: {col_names}\n")
            
            for t in trades:
                print("Trade details:")
                for i, col in enumerate(col_names):
                    print(f"  {col}: {t[i]}")
                print("-" * 50)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pg_logger.pool.putconn(conn)

if __name__ == "__main__":
    analyze_avax_trade()

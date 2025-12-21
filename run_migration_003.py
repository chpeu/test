"""Run migration 003 to create trade_events table"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.postgresql_datalogger import get_pg_datalogger

def run_migration():
    pg_logger = get_pg_datalogger()
    if not pg_logger or not pg_logger.enabled:
        print("ERROR: PostgreSQL DataLogger not available")
        return False
    
    # Read migration SQL
    migration_path = os.path.join(
        os.path.dirname(__file__), 
        'database', 'migrations', '003_create_trade_events.sql'
    )
    
    with open(migration_path, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # Execute migration
    conn = pg_logger._get_connection()
    if not conn:
        print("ERROR: Cannot get connection")
        return False
    
    try:
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        cur.close()
        pg_logger._return_connection(conn)
        print("OK: Migration 003 executed successfully - trade_events table created")
        return True
    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        conn.rollback()
        pg_logger._return_connection(conn)
        return False

if __name__ == "__main__":
    run_migration()

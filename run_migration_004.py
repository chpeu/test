"""Run migration 004 to add partial_tp columns"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.postgresql_datalogger import get_pg_datalogger

def run_migration():
    pg_logger = get_pg_datalogger()
    if not pg_logger or not pg_logger.enabled:
        print("ERROR: PostgreSQL DataLogger not available")
        return False
    
    migration_path = os.path.join(
        os.path.dirname(__file__), 
        'database', 'migrations', '004_add_partial_tp_columns.sql'
    )
    
    with open(migration_path, 'r', encoding='utf-8') as f:
        sql = f.read()
    
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
        print("OK: Migration 004 executed - partial_tp columns added")
        return True
    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        conn.rollback()
        pg_logger._return_connection(conn)
        return False

if __name__ == "__main__":
    run_migration()

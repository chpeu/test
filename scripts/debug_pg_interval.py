
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.callbacks.scanner_loop import get_pg_datalogger
import logging

# Setup basic logging
logging.basicConfig(level=logging.DEBUG)

def test_query():
    pg = get_pg_datalogger()
    if not pg or not pg.enabled:
        print("PostgreSQL not enabled")
        return

    print("Testing Interval Query...")
    try:
        # This is the suspicious syntax
        query = "SELECT 1 WHERE NOW() > NOW() - INTERVAL '%s minutes'"
        res = pg._execute_query(query, (60,))
        print(f"Result 1 (suspicious): {res}")
    except Exception as e:
        print(f"Error 1: {e}")

    try:
        # This is the safer syntax
        query = "SELECT 1 WHERE NOW() > NOW() - (INTERVAL '1 minute' * %s)"
        res = pg._execute_query(query, (60,), fetch=True)
        print(f"Result 2 (safer): {res}")
    except Exception as e:
        print(f"Error 2: {e}")

    # Test actual data retrieval
    try:
        symbol = 'SOL/USDT:USDT'
        query = """
                SELECT ml_confidence FROM scan_logs 
                WHERE symbol = %s 
                AND ml_confidence IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 1
            """
        res = pg._execute_query(query, (symbol,), fetch=True)
        print(f"Data check for {symbol}: {res}")
    except Exception as e:
        print(f"Error data check: {e}")

if __name__ == "__main__":
    test_query()

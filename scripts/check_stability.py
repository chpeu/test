
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

def check_stability():
    load_dotenv()
    conn_str = os.getenv('POSTGRES_URL') or (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'trade_cursor_ml')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASSWORD', '')}"
    )
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        
        # Check columns of scan_errors
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'scan_errors';")
        cols = [r[0] for r in cur.fetchall()]
        print(f"Columns in scan_errors: {cols}")

        print("\n--- Recent Scan Errors (last 10 min) ---")
        # Use available columns
        err_col = 'error_message' if 'error_message' in cols else 'details' if 'details' in cols else 'message'
        stack_col = 'error_stack' if 'error_stack' in cols else None
        time_col = 'created_at' if 'created_at' in cols else 'timestamp' if 'timestamp' in cols else None
        
        if err_col in cols and time_col:
            query = f"SELECT error_type, {err_col}, {time_col}"
            if stack_col:
                query += f", {stack_col}"
            query += f" FROM scan_errors WHERE {time_col} > %s ORDER BY {time_col} DESC LIMIT 5;"
            
            cur.execute(query, (datetime.now() - timedelta(minutes=10),))
            errors = cur.fetchall()
            if errors:
                for err in errors:
                    print(f"[{err[2]}] {err[0]}: {str(err[1])}")
                    if stack_col and len(err) > 3 and err[3]:
                        print(f"Stack: {str(err[3])[:500]}...")
                    print("-" * 20)
            else:
                print("No recent scan errors.")

        print("\n--- Recent Scan Logs (last 5 min) ---")
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'scan_logs';")
        log_cols = [r[0] for r in cur.fetchall()]
        time_col_log = 'created_at' if 'created_at' in log_cols else 'timestamp' if 'timestamp' in log_cols else None
        
        if time_col_log:
            cur.execute(f"SELECT symbol, is_opportunity, reject_reason_category, {time_col_log} FROM scan_logs WHERE {time_col_log} > %s ORDER BY {time_col_log} DESC LIMIT 5;", (datetime.now() - timedelta(minutes=5),))
            logs = cur.fetchall()
            if logs:
                for log in logs:
                    print(f"[{log[3]}] {log[0]} - Opp: {log[1]}, Reject: {log[2]}")
            else:
                print("No recent scan logs. Scans might not be running or no results yet.")
        else:
            print(f"Could not find a time column in scan_logs. Available: {log_cols}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_stability()

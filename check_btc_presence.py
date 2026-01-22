import psycopg2
import pandas as pd

def check_btc():
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    print("Checking BTC presence in scan_logs for today...")
    query = "SELECT DISTINCT symbol FROM scan_logs WHERE DATE(timestamp) = CURRENT_DATE AND symbol ILIKE '%BTC%'"
    df = pd.read_sql(query, conn)
    print(f"Symbols matching %BTC% today: {df['symbol'].tolist()}")
    
    query_all = "SELECT DISTINCT symbol FROM scan_logs WHERE DATE(timestamp) = CURRENT_DATE ORDER BY symbol"
    df_all = pd.read_sql(query_all, conn)
    print(f"Total unique symbols today: {len(df_all)}")
    
    # Check if BTC is in the top_pairs or excluded symbols in config
    print("\nChecking if BTC is in any scans at all (ever):")
    query_ever = "SELECT DISTINCT symbol FROM scan_logs WHERE symbol ILIKE '%BTC%' LIMIT 5"
    df_ever = pd.read_sql(query_ever, conn)
    print(f"Symbols matching %BTC% ever: {df_ever['symbol'].tolist()}")

    conn.close()

if __name__ == "__main__":
    check_btc()

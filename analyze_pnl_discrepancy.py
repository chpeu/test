import psycopg2
from psycopg2.extras import RealDictCursor
import json

def analyze_trades():
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='trade_cursor_ml',
            user='postgres',
            password='@Cmtr1di12345'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Last 12 trades
        print("--- LAST 12 TRADES ---")
        query = """
        SELECT id, symbol, direction, entry_fill_price, exit_fill_price, 
               size_usdt, position_size_contracts, leverage_used,
               pnl_usdt, pnl_pct, net_pnl_usdt, net_pnl_pct, 
               total_fees_usdt, entry_timestamp_live
        FROM trades 
        ORDER BY created_at DESC 
        LIMIT 12
        """
        cur.execute(query)
        trades = cur.fetchall()
        
        header = f"{'Symbol':<15} | {'Dir':<5} | {'Entry':<10} | {'Exit':<10} | {'Size($)':<8} | {'PnL($)':<10} | {'NetPnL($)':<10} | {'NetPnL(%)':<10}"
        print(header)
        print("-" * len(header))
        
        for t in trades:
            print(f"{str(t['symbol']):<15} | {str(t['direction']):<5} | {float(t['entry_fill_price'] or 0):<10.4f} | {float(t['exit_fill_price'] or 0):<10.4f} | {float(t['size_usdt'] or 0):<8.2f} | {float(t['pnl_usdt'] or 0):<10.4f} | {float(t['net_pnl_usdt'] or 0):<10.4f} | {float(t['net_pnl_pct'] or 0):<10.4f}")

        # Specific ASTER trade
        print("\n--- ASTER TRADE DETAIL (14:49:04) ---")
        # Search for ASTER around that time
        query_aster = """
        SELECT *
        FROM trades 
        WHERE symbol LIKE '%ASTER%' 
        AND entry_timestamp_live::text LIKE '%14:49%'
        ORDER BY created_at DESC 
        LIMIT 1
        """
        cur.execute(query_aster)
        aster = cur.fetchone()
        if aster:
            for key, value in aster.items():
                if value is not None:
                    print(f"{key}: {value}")
        else:
            print("ASTER trade not found with time 14:49")
            # Try without time filter
            cur.execute("SELECT * FROM trades WHERE symbol LIKE '%ASTER%' ORDER BY created_at DESC LIMIT 1")
            aster = cur.fetchone()
            if aster:
                print("Found latest ASTER trade instead:")
                for key, value in aster.items():
                    if value is not None:
                        print(f"{key}: {value}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_trades()

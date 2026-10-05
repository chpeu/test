import psycopg2
from psycopg2.extras import RealDictCursor

def find_aster_trade():
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='trade_cursor_ml',
        user='postgres',
        password='@Cmtr1di12345'
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Search for ASTER trade around 14:49 today or yesterday
    # Since I don't know the exact date in the DB, I'll search by symbol and time
    query = """
    SELECT * 
    FROM trades 
    WHERE symbol LIKE '%ASTER%' 
    ORDER BY created_at DESC 
    LIMIT 20
    """
    cur.execute(query)
    trades = cur.fetchall()
    
    for t in trades:
        print(f"ID: {t['id']}")
        print(f"Symbol: {t['symbol']}")
        print(f"Created At: {t['created_at']}")
        print(f"Entry Price: {t['entry_fill_price']}")
        print(f"Exit Price: {t['exit_fill_price']}")
        print(f"Size USDT: {t['size_usdt']}")
        print(f"Contracts: {t['position_size_contracts']}")
        print(f"Direction: {t['direction']}")
        print(f"PnL USDT: {t['pnl_usdt']}")
        print(f"PnL PCT: {t['pnl_pct']}")
        print(f"Net PnL USDT: {t['net_pnl_usdt']}")
        print(f"Net PnL PCT: {t['net_pnl_pct']}")
        print(f"Fees USDT: {t['total_fees_usdt']}")
        print("-" * 40)

    conn.close()

if __name__ == "__main__":
    find_aster_trade()

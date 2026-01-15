import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

def check_trades():
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='trade_cursor_ml',
        user='postgres',
        password='@Cmtr1di12345'
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
    SELECT 
        id, symbol, direction, entry_fill_price, exit_fill_price, 
        position_size_contracts, size_usdt, margin_used, leverage_used,
        net_pnl_usdt, net_pnl_pct, pnl_usdt, pnl_pct, entry_timestamp_live,
        total_fees_usdt
    FROM trades 
    ORDER BY entry_timestamp_live DESC 
    LIMIT 12
    """
    cur.execute(query)
    trades = cur.fetchall()
    
    print(f"{'ID':<6} | {'Symbol':<10} | {'Side':<5} | {'Entry':<10} | {'Exit':<10} | {'Size($)':<8} | {'PnL($)':<10} | {'PnL(%)':<8} | {'NetPnL($)':<10} | {'NetPnL(%)':<8} | {'Time'}")
    print("-" * 140)
    for t in trades:
        entry = t['entry_fill_price'] if t['entry_fill_price'] is not None else 0
        exit = t['exit_fill_price'] if t['exit_fill_price'] is not None else 0
        size_usdt = t['size_usdt'] if t['size_usdt'] is not None else 0
        pnl_usdt = t['pnl_usdt'] if t['pnl_usdt'] is not None else 0
        pnl_pct = t['pnl_pct'] if t['pnl_pct'] is not None else 0
        net_pnl_usdt = t['net_pnl_usdt'] if t['net_pnl_usdt'] is not None else 0
        net_pnl_pct = t['net_pnl_pct'] if t['net_pnl_pct'] is not None else 0
        time = t['entry_timestamp_live']
        side = t['direction']
        
        print(f"{str(t['id'])[:8]:<8} | {str(t['symbol']):<10} | {str(side):<5} | {entry:<10.4f} | {exit:<10.4f} | {size_usdt:<8.2f} | {pnl_usdt:<10.4f} | {pnl_pct:<8.4f} | {net_pnl_usdt:<10.4f} | {net_pnl_pct:<8.4f} | {time}")

    conn.close()

if __name__ == "__main__":
    check_trades()

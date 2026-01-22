import psycopg2
from psycopg2.extras import RealDictCursor

def get_aster_data():
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='trade_cursor_ml',
            user='postgres',
            password='@Cmtr1di12345'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        SELECT id, symbol, entry_fill_price, exit_fill_price, 
               size_usdt, position_size_contracts, 
               leverage_used, pnl_usdt, pnl_pct, net_pnl_usdt, net_pnl_pct, 
               direction, entry_fee_usdt, exit_fee_usdt, total_fees_usdt,
               partial_tp_executed, partial_tp_profit
        FROM trades 
        WHERE symbol LIKE '%ASTER%' 
        ORDER BY created_at DESC 
        LIMIT 1
        """
        cur.execute(query)
        trade = cur.fetchone()
        if trade:
            for k, v in trade.items():
                print(f"{k}: {v}")
            
            # Manual calculation
            entry = float(trade['entry_fill_price'])
            exit = float(trade['exit_fill_price'])
            size = float(trade['size_usdt'])
            contracts = float(trade['position_size_contracts'])
            contract_size = float(trade['contract_size_used'] or 1.0)
            leverage = float(trade['leverage_used'] or 1.0)
            
            print("\n--- Manual Verification ---")
            price_change_pct = ((exit - entry) / entry) * 100 if trade['direction'] == 'LONG' else ((entry - exit) / entry) * 100
            print(f"Price Change %: {price_change_pct:.6f}%")
            
            # Theoretical Notional PnL
            # Notional = contracts * entry * contract_size
            notional = contracts * entry * contract_size
            print(f"Calculated Notional: {notional:.4f} USDT")
            print(f"Logged Size USDT: {size:.4f} USDT")
            
            theoretical_pnl = notional * (price_change_pct / 100)
            print(f"Theoretical PnL (Notional * Move): {theoretical_pnl:.6f} USDT")
            print(f"Logged PnL USDT: {trade['pnl_usdt']}")
            
            pnl_pct_on_notional = (theoretical_pnl / notional) * 100 if notional > 0 else 0
            print(f"PnL % on Notional: {pnl_pct_on_notional:.6f}%")
            
            pnl_pct_on_size = (float(trade['pnl_usdt']) / size) * 100 if size > 0 else 0
            print(f"PnL % on Logged Size: {pnl_pct_on_size:.6f}%")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_aster_data()

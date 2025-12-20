import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
import os

# Paramètres de connexion
DB_PARAMS = {
    "dbname": "trade_cursor_ml",
    "user": "postgres",
    "password": "@Cmtr1di12345", # Mot de passe correct
    "host": "localhost",
    "port": "5432"
}

def get_db_connection():
    try:
        return psycopg2.connect(**DB_PARAMS)
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None

def analyze_trade():
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Lister colonnes de 'trades'
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'trades' ORDER BY ordinal_position;
        """)
        cols = [r['column_name'] for r in cur.fetchall()]
        print(f"Colonnes 'trades': {cols}")
        
        # 3. Chercher trade JELLY avec TP partiel aujourd'hui
        query = """
            SELECT t.id, t.symbol, t.timestamp_entry, t.timestamp_exit, t.pnl_pct, t.exit_reason,
                   t.partial_tp_executed, t.partial_tp_percent, t.partial_tp_profit,
                   m.max_pnl_reached, m.max_price_reached,
                   t.net_pnl_pct, t.gross_pnl_usdt
            FROM trades t
            LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
            WHERE t.timestamp_entry >= '2025-12-16 00:00:00'
            AND t.symbol ILIKE '%JELLY%'
            ORDER BY t.timestamp_entry DESC;
        """
        
        cur.execute(query)
        trades = cur.fetchall()
        
        print(f"\nFound {len(trades)} JELLY trades today (Detailed check):\n")

        for trade in trades:
            ts_entry = trade['timestamp_entry'].strftime('%H:%M:%S')
            pnl = trade['pnl_pct']
            partial_exec = trade['partial_tp_executed']
            mfe = trade['max_pnl_reached']
            
            print(f"Time: {ts_entry} | PnL: {pnl}% | Partial: {partial_exec} | MFE: {mfe}% | Net PnL: {trade['net_pnl_pct']}%")
            
            if partial_exec:
                 print(f"   >>> PARTIAL EXECUTED <<<")
                 print(f"   Partial Profit: {trade['partial_tp_profit']}")
                 print(f"   Partial Percent: {trade['partial_tp_percent']}")
                
    except Exception as e:
        print(f"Query Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    analyze_trade()

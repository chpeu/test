import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import json
import sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Charger les variables d'environnement
load_dotenv()

DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

def get_connection():
    try:
        return psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return None

def format_timestamp(ts):
    if not ts:
        return "N/A"
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return ts
    return ts.strftime('%Y-%m-%d %H:%M:%S')

def analyze_last_trades(limit=5):
    conn = get_connection()
    if not conn:
        return

    cursor = conn.cursor()

    # Récupérer les 5 derniers trades
    query_trades = """
        SELECT id, symbol, direction, entry_price, exit_price, net_pnl_usdt, net_pnl_pct, created_at
        FROM trades
        ORDER BY created_at DESC
        LIMIT %s
    """
    cursor.execute(query_trades, (limit,))
    trades = cursor.fetchall()

    print(f"\n🎬 FILM DES {limit} DERNIERS TRADES\n" + "="*50)

    for trade in trades:
        # trade_uuid est db_id (la clé primaire de la table trades)
        trade_uuid, symbol, direction, entry, exit_price, pnl_usdt, pnl_pct, created_at = trade
        
        direction_str = "LONG 🟢" if direction == "LONG" else "SHORT 🔴"
        pnl_str = f"{pnl_usdt:.2f} USDT" if pnl_usdt is not None else "En cours"
        pnl_pct_str = f"({pnl_pct:.2f}%)" if pnl_pct is not None else ""
        
        print(f"\n📌 TRADE {symbol} {direction_str} | {format_timestamp(created_at)}")
        print(f"   ID: {trade_uuid}")
        print(f"   Entry: {entry} | Exit: {exit_price} | PnL: {pnl_str} {pnl_pct_str}")
        print(f"   Events:")

        # Récupérer les événements pour ce trade
        if trade_uuid:
            query_events = """
                SELECT event_type, event_timestamp, price_at_event, pnl_pct_at_event, details
                FROM trade_events
                WHERE trade_id = %s
                ORDER BY event_timestamp ASC
            """
            cursor.execute(query_events, (str(trade_uuid),))
            events = cursor.fetchall()

            if not events:
                print("      (Aucun événement enregistré)")
            
            for evt in events:
                e_type, e_ts, e_price, e_pnl, e_details = evt
                ts_str = format_timestamp(e_ts).split(' ')[1] # Juste l'heure
                pnl_display = f"PnL: {e_pnl:.2f}%" if e_pnl is not None else ""
                
                details_str = ""
                if e_details:
                    # Simplifier l'affichage des détails
                    if isinstance(e_details, str):
                        try:
                            det = json.loads(e_details)
                        except:
                            det = e_details
                    else:
                        det = e_details
                    
                    if e_type == 'TRAILING_SL_MOVED':
                        details_str = f"SL: {det.get('old_sl')} -> {det.get('new_sl')}"
                    elif e_type == 'MAX_PNL_REACHED':
                        details_str = f"Max: {det.get('previous_max')} -> {e_pnl}"
                    elif e_type == 'ENTRY':
                         details_str = f"Size: {det.get('size_usdt')} USDT"
                    else:
                        details_str = str(det)

                print(f"      🕒 {ts_str} - {e_type:<20} | Price: {e_price} | {pnl_display} {details_str}")
        else:
             print("      (Pas de trade_id UUID lié)")
        
        print("-" * 50)

    conn.close()

if __name__ == "__main__":
    analyze_last_trades(5)

"""
Verification des donnees dans trade_atr_metrics
"""
import psycopg2
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

def check_atr_metrics():
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cur = conn.cursor()

    # Verifier colonnes remplies
    cur.execute('''
        SELECT 
            tam.id,
            t.symbol,
            tam.entry_atr_1m,
            tam.entry_atr_pct_1m,
            tam.entry_adx,
            tam.param_atr_mult_sl,
            tam.param_trailing_distance_mult,
            tam.market_volatility_state,
            tam.market_trend_state,
            tam.calculated_sl_pct,
            tam.calculated_tp_pct,
            tam.be_triggered,
            tam.trailing_activated
        FROM trade_atr_metrics tam
        LEFT JOIN trades t ON tam.trade_id = t.id
        ORDER BY tam.created_at DESC
        LIMIT 5
    ''')
    rows = cur.fetchall()
    
    print("=" * 100)
    print("VERIFICATION trade_atr_metrics")
    print("=" * 100)
    
    for row in rows:
        print(f"\n[Trade ID={row[0]}] {row[1]}")
        print(f"  Contexte ATR:")
        print(f"    - entry_atr_1m: {row[2]}")
        print(f"    - entry_atr_pct_1m: {row[3]}")
        print(f"    - entry_adx: {row[4]}")
        print(f"  Params utilises:")
        print(f"    - param_atr_mult_sl: {row[5]}")
        print(f"    - param_trailing_distance_mult: {row[6]} <-- NOUVEAU")
        print(f"  Context Tagging:")
        print(f"    - market_volatility_state: {row[7]}")
        print(f"    - market_trend_state: {row[8]}")
        print(f"  Niveaux calcules:")
        print(f"    - calculated_sl_pct: {row[9]}")
        print(f"    - calculated_tp_pct: {row[10]}")
        print(f"  Evenements:")
        print(f"    - be_triggered: {row[11]}")
        print(f"    - trailing_activated: {row[12]}")
    
    # Statistiques
    cur.execute('''
        SELECT 
            COUNT(*) as total,
            COUNT(entry_atr_1m) as with_atr,
            COUNT(market_volatility_state) as with_volatility,
            COUNT(param_trailing_distance_mult) as with_trailing_dist
        FROM trade_atr_metrics
    ''')
    stats = cur.fetchone()
    print("\n" + "=" * 100)
    print("STATISTIQUES")
    print("=" * 100)
    print(f"  Total entrees: {stats[0]}")
    print(f"  Avec ATR 1m: {stats[1]} ({100*stats[1]/max(stats[0],1):.0f}%)")
    print(f"  Avec volatility_state: {stats[2]} ({100*stats[2]/max(stats[0],1):.0f}%)")
    print(f"  Avec trailing_distance_mult: {stats[3]} ({100*stats[3]/max(stats[0],1):.0f}%)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_atr_metrics()

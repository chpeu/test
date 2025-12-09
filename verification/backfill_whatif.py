"""
Backfill What-If calculations for existing trades
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from dotenv import load_dotenv
from core.analysis.what_if_simulator import WhatIfSimulator, TradeData

load_dotenv()

def backfill_whatif():
    """Backfill What-If pour tous les trades existants dans trade_atr_metrics"""
    
    print("=" * 80)
    print("BACKFILL WHAT-IF SIMULATOR")
    print("=" * 80)
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cur = conn.cursor()
    
    # Récupérer trades sans What-If calculé
    cur.execute('''
        SELECT 
            tam.trade_id,
            t.symbol,
            t.direction,
            t.entry_price,
            t.exit_price,
            t.sl_price,
            t.tp_price,
            t.size_usdt,
            tam.max_pnl_reached,
            tam.min_pnl_reached,
            tam.param_atr_mult_sl,
            tam.param_atr_mult_tp,
            tam.param_trailing_trigger_mult,
            tam.param_trailing_distance_mult,
            tam.param_be_atr_mult,
            tam.entry_atr_pct_1m,
            tam.be_triggered,
            tam.trailing_activated
        FROM trade_atr_metrics tam
        JOIN trades t ON tam.trade_id = t.id
        WHERE tam.pnl_if_no_be IS NULL
        ORDER BY tam.created_at DESC
        LIMIT 10
    ''')
    
    rows = cur.fetchall()
    print(f"\nTrades a traiter: {len(rows)}")
    
    if not rows:
        print("Aucun trade a backfill!")
        cur.close()
        conn.close()
        return
    
    simulator = WhatIfSimulator(db_connection=conn)
    
    for row in rows:
        trade_id = row[0]
        symbol = row[1]
        direction = row[2]
        entry_price = float(row[3]) if row[3] else 0
        exit_price = float(row[4]) if row[4] else 0
        sl_price = float(row[5]) if row[5] else 0
        tp_price = float(row[6]) if row[6] else 0
        size_usdt = float(row[7]) if row[7] else 0
        
        # Estimer max/min price depuis PnL si non disponible
        max_pnl = float(row[8]) if row[8] else 0
        min_pnl = float(row[9]) if row[9] else 0
        
        # Calculer prix max/min depuis PnL %
        if direction == 'LONG':
            max_price = entry_price * (1 + max_pnl / 100) if max_pnl else exit_price
            min_price = entry_price * (1 + min_pnl / 100) if min_pnl else exit_price
        else:
            max_price = entry_price * (1 - min_pnl / 100) if min_pnl else exit_price
            min_price = entry_price * (1 - max_pnl / 100) if max_pnl else exit_price
        
        # Params
        atr_mult_sl = float(row[10]) if row[10] else 1.2
        atr_mult_tp = float(row[11]) if row[11] else 2.2
        trailing_trigger = float(row[12]) if row[12] else 1.5
        trailing_distance = float(row[13]) if row[13] else 0.8
        be_mult = float(row[14]) if row[14] else 1.0
        entry_atr_pct = float(row[15]) if row[15] else 0.2
        be_triggered = row[16] or False
        trailing_activated = row[17] or False
        
        print(f"\n[{symbol}] {direction}")
        print(f"  Entry: {entry_price:.6f} | Exit: {exit_price:.6f}")
        print(f"  SL: {sl_price:.6f} | TP: {tp_price:.6f}")
        print(f"  Max: {max_price:.6f} | Min: {min_price:.6f}")
        print(f"  BE: {be_triggered} | Trail: {trailing_activated}")
        
        # Créer TradeData
        trade = TradeData(
            trade_id=str(trade_id),
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            sl_price=sl_price,
            tp_price=tp_price,
            size_usdt=size_usdt,
            max_price=max_price,
            min_price=min_price,
            be_triggered=be_triggered,
            trailing_activated=trailing_activated,
            atr_mult_sl=atr_mult_sl,
            atr_mult_tp=atr_mult_tp,
            trailing_trigger_mult=trailing_trigger,
            trailing_distance_mult=trailing_distance,
            be_atr_mult=be_mult,
            entry_atr_pct=entry_atr_pct
        )
        
        # Simuler
        result = simulator.simulate(trade)
        
        print(f"  What-If Results:")
        print(f"    - pnl_if_no_be: {result.pnl_if_no_be:.3f}%" if result.pnl_if_no_be else "    - pnl_if_no_be: N/A")
        print(f"    - pnl_if_no_trailing: {result.pnl_if_no_trailing:.3f}%" if result.pnl_if_no_trailing else "    - pnl_if_no_trailing: N/A")
        print(f"    - sl_efficiency: {result.sl_efficiency:.1f}%" if result.sl_efficiency else "    - sl_efficiency: N/A")
        print(f"    - trailing_capture: {result.trailing_capture_pct:.1f}%" if result.trailing_capture_pct else "    - trailing_capture: N/A")
        
        # Update DB
        simulator.update_database(str(trade_id), result)
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("BACKFILL TERMINE!")
    print("=" * 80)

if __name__ == "__main__":
    backfill_whatif()

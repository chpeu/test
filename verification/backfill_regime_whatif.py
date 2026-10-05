"""
Backfill Regime What-If - Phase 1C

Calcule pnl_if_calme_params, pnl_if_normal_params, pnl_if_volatile_params
et optimal_regime_retrospective pour les trades existants.

Usage:
    python verification/backfill_regime_whatif.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from core.analysis.what_if_simulator import WhatIfSimulator, TradeData


def backfill_regime_whatif():
    print("=" * 60)
    print("BACKFILL REGIME WHAT-IF - Phase 1C")
    print("=" * 60)
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    
    cur = conn.cursor()
    
    # Recuperer les trades avec max/min price disponibles et sans regime what-if
    query = """
        SELECT 
            t.id,
            t.symbol,
            t.direction,
            t.entry_price,
            t.exit_price,
            tam.entry_atr_pct_1m,
            tam.max_price_reached,
            tam.min_price_reached
        FROM trades t
        JOIN trade_atr_metrics tam ON tam.trade_id = t.id
        WHERE tam.pnl_if_calme_params IS NULL
          AND t.entry_price IS NOT NULL
          AND t.exit_price IS NOT NULL
          AND tam.max_price_reached IS NOT NULL
          AND tam.min_price_reached IS NOT NULL
    """
    
    cur.execute(query)
    trades = cur.fetchall()
    
    print(f"\nTrades a traiter: {len(trades)}")
    
    if not trades:
        print("Aucun trade a backfiller.")
        conn.close()
        return
    
    simulator = WhatIfSimulator(conn)
    success = 0
    errors = 0
    
    for row in trades:
        trade_id, symbol, direction, entry_price, exit_price, atr_pct, max_price, min_price = row
        
        # Creer TradeData
        trade = TradeData(
            trade_id=str(trade_id),
            symbol=symbol,
            direction=direction or 'LONG',
            entry_price=float(entry_price) if entry_price else 0,
            exit_price=float(exit_price) if exit_price else 0,
            sl_price=0,  # Non utilise pour regime what-if
            tp_price=0,
            size_usdt=0,
            max_price=float(max_price) if max_price else float(exit_price) if exit_price else 0,
            min_price=float(min_price) if min_price else float(exit_price) if exit_price else 0,
            be_triggered=False,
            trailing_activated=False
        )
        
        # Calculer regime what-if
        atr = float(atr_pct) if atr_pct else 0.5
        regime_results = simulator.simulate_regime_scenarios(trade, atr)
        
        if regime_results:
            # Mettre a jour
            update_query = """
                UPDATE trade_atr_metrics SET
                    pnl_if_calme_params = %s,
                    pnl_if_normal_params = %s,
                    pnl_if_volatile_params = %s,
                    optimal_regime_retrospective = %s
                WHERE trade_id = %s
            """
            try:
                cur.execute(update_query, (
                    regime_results.get('pnl_if_calme_params'),
                    regime_results.get('pnl_if_normal_params'),
                    regime_results.get('pnl_if_volatile_params'),
                    regime_results.get('optimal_regime_retrospective'),
                    trade_id
                ))
                success += 1
            except Exception as e:
                print(f"  Erreur {symbol}: {e}")
                errors += 1
        else:
            errors += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\nResultat:")
    print(f"  - Succes: {success}")
    print(f"  - Erreurs: {errors}")
    
    # Verification
    conn2 = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cur2 = conn2.cursor()
    
    cur2.execute("""
        SELECT 
            optimal_regime_retrospective,
            COUNT(*) as count,
            ROUND(AVG(pnl_if_calme_params)::numeric, 3) as avg_calme,
            ROUND(AVG(pnl_if_normal_params)::numeric, 3) as avg_normal,
            ROUND(AVG(pnl_if_volatile_params)::numeric, 3) as avg_volatile
        FROM trade_atr_metrics
        WHERE optimal_regime_retrospective IS NOT NULL
        GROUP BY optimal_regime_retrospective
        ORDER BY count DESC
    """)
    
    print("\nDistribution des regimes optimaux:")
    for row in cur2.fetchall():
        regime, count, avg_calme, avg_normal, avg_volatile = row
        print(f"  {regime}: {count} trades | CALME={avg_calme}% | NORMAL={avg_normal}% | VOLATILE={avg_volatile}%")
    
    cur2.close()
    conn2.close()
    
    print("\n" + "=" * 60)
    print("BACKFILL TERMINE")
    print("=" * 60)


if __name__ == "__main__":
    backfill_regime_whatif()

"""
Vérifie que le tracking Phase 0.5 fonctionne correctement.
- Timestamps BE et Trailing
- Max/Min price et PnL
- Time to max/min PnL

Usage:
    python verification/verify_phase05_tracking.py
"""
import psycopg2
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_tracking():
    print("=" * 60)
    print("🔍 VÉRIFICATION PHASE 0.5: Tracking Colonnes")
    print("=" * 60)
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    
    with conn.cursor() as cur:
        # 1. Vérifier les colonnes
        print("\n📊 Colonnes de tracking:")
        columns_to_check = [
            'be_triggered_at', 'trailing_activated_at',
            'max_price_reached', 'min_price_reached',
            'time_to_max_pnl_seconds', 'time_to_min_pnl_seconds',
            'calculated_sl_price', 'calculated_tp_price'
        ]
        
        for col in columns_to_check:
            cur.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT({col}) as filled
                FROM trade_atr_metrics
            """)
            total, filled = cur.fetchone()
            pct = (filled / total * 100) if total > 0 else 0
            status = "✅" if pct > 0 or total == 0 else "⏳"
            print(f"  {status} {col}: {filled}/{total} ({pct:.0f}%)")
        
        # 2. Stats sur les derniers trades
        print("\n📊 Derniers trades avec tracking:")
        cur.execute("""
            SELECT 
                t.symbol,
                t.direction,
                t.pnl_percent,
                tam.be_triggered,
                tam.be_triggered_at IS NOT NULL as has_be_timestamp,
                tam.trailing_activated,
                tam.trailing_activated_at IS NOT NULL as has_trail_timestamp,
                tam.max_price_reached IS NOT NULL as has_max_price,
                tam.min_price_reached IS NOT NULL as has_min_price,
                tam.time_to_max_pnl_seconds,
                tam.time_to_min_pnl_seconds
            FROM trade_atr_metrics tam
            JOIN trades t ON t.id = tam.trade_id
            ORDER BY t.closed_at DESC
            LIMIT 5
        """)
        
        rows = cur.fetchall()
        if rows:
            print(f"{'Symbol':<12} {'Dir':<6} {'PnL%':>8} {'BE':>4} {'BE_TS':>6} {'TS':>4} {'TS_TS':>6} {'MaxP':>5} {'MinP':>5} {'T2Max':>6} {'T2Min':>6}")
            print("-" * 80)
            for row in rows:
                symbol, direction, pnl, be, be_ts, ts, ts_ts, max_p, min_p, t2max, t2min = row
                print(f"{symbol[:12]:<12} {direction:<6} {pnl:>7.2f}% {str(be)[:4]:>4} {str(be_ts)[:5]:>6} {str(ts)[:4]:>4} {str(ts_ts)[:5]:>6} {str(max_p)[:5]:>5} {str(min_p)[:5]:>5} {str(t2max)[:6]:>6} {str(t2min)[:6]:>6}")
        else:
            print("  ⏳ Aucun trade récent")
        
        # 3. Résumé
        print("\n" + "=" * 60)
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(be_triggered_at) as with_be_ts,
                COUNT(trailing_activated_at) as with_trail_ts,
                COUNT(max_price_reached) as with_max_price,
                COUNT(time_to_max_pnl_seconds) as with_time_max
            FROM trade_atr_metrics
        """)
        total, be_ts, trail_ts, max_p, time_max = cur.fetchone()
        
        print(f"📋 RÉSUMÉ ({total} trades total):")
        print(f"  - BE timestamp:       {be_ts}/{total}")
        print(f"  - Trailing timestamp: {trail_ts}/{total}")
        print(f"  - Max price:          {max_p}/{total}")
        print(f"  - Time to max PnL:    {time_max}/{total}")
        
        if total > 0 and (be_ts > 0 or trail_ts > 0 or max_p > 0):
            print("\n✅ PHASE 0.5 OPÉRATIONNELLE")
        elif total > 0:
            print("\n⏳ En attente de nouveaux trades pour vérifier le tracking")
        else:
            print("\n⏳ Aucun trade - en attente de données")
    
    conn.close()
    print("=" * 60)


if __name__ == "__main__":
    verify_tracking()

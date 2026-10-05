#!/usr/bin/env python3
"""
Verification de la ML Calibration
==================================
Verifie que la calibration fonctionne correctement et detecte les incoherences.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

def check_calibration():
    from core.postgresql_datalogger import PostgreSQLDataLogger
    
    pg_logger = PostgreSQLDataLogger()
    if not pg_logger.enabled:
        print("PostgreSQL non disponible")
        return
    
    conn = pg_logger.pool.getconn()
    try:
        with conn.cursor() as cur:
            # 1. Stats de la table ml_calibration
            print("=" * 70)
            print("  ML CALIBRATION - DIAGNOSTIC")
            print("=" * 70)
            
            cur.execute("""
                SELECT direction, confidence_bucket, 
                       total_trades, weighted_total, actual_winrate,
                       avg_pnl_pct, total_pnl_usdt,
                       created_at, updated_at
                FROM ml_calibration
                ORDER BY direction, confidence_bucket
            """)
            rows = cur.fetchall()
            
            print(f"\n{'Direction':<10} {'Bucket':<10} {'Trades':<10} {'Weighted':<12} {'WR%':<10} {'AvgPnL':<10} {'Created':<12}")
            print("-" * 80)
            
            total_trades = 0
            for r in rows:
                direction, bucket, trades, weighted, wr, avg_pnl, total_pnl, created, updated = r
                total_trades += trades or 0
                wr_str = f"{wr:.1f}%" if wr else "N/A"
                created_str = created.strftime("%Y-%m-%d") if created else "N/A"
                print(f"{direction:<10} {bucket:<10} {trades or 0:<10} {weighted or 0:<12.2f} {wr_str:<10} {avg_pnl or 0:<10.3f}% {created_str:<12}")
            
            print(f"\nTotal trades dans calibration: {total_trades}")
            
            # 2. Comparer avec les trades reels des 7 derniers jours
            print("\n" + "=" * 70)
            print("  COMPARAISON AVEC TRADES REELS (7 derniers jours)")
            print("=" * 70)
            
            cur.execute("""
                SELECT 
                    direction,
                    CASE 
                        WHEN ml_confidence >= 50 THEN '50+'
                        ELSE CONCAT(FLOOR(ml_confidence / 5) * 5, '-', FLOOR(ml_confidence / 5) * 5 + 5)
                    END as bucket,
                    COUNT(*) as trades,
                    SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
                    AVG(net_pnl_pct) as avg_pnl
                FROM trades
                WHERE created_at > NOW() - INTERVAL '7 days'
                  AND ml_confidence IS NOT NULL
                  AND ml_confidence >= 30
                GROUP BY direction, bucket
                ORDER BY direction, bucket
            """)
            recent_trades = cur.fetchall()
            
            print(f"\n{'Direction':<10} {'Bucket':<10} {'Trades':<10} {'Wins':<10} {'WR%':<10} {'AvgPnL':<10}")
            print("-" * 60)
            
            recent_total = 0
            for r in recent_trades:
                direction, bucket, trades, wins, avg_pnl = r
                recent_total += trades
                wr = (wins / trades * 100) if trades > 0 else 0
                print(f"{direction:<10} {bucket:<10} {trades:<10} {wins:<10} {wr:<10.1f}% {avg_pnl or 0:<10.3f}%")
            
            print(f"\nTotal trades 7 derniers jours: {recent_total}")
            
            # 3. Detecter les incoherences
            print("\n" + "=" * 70)
            print("  ANALYSE")
            print("=" * 70)
            
            if total_trades > recent_total * 10:
                print(f"\n[WARNING] La calibration contient {total_trades} trades mais seulement {recent_total} trades recents.")
                print("          -> Les donnees de calibration sont probablement obsoletes.")
                print("          -> Recommandation: python scripts/seed_ml_calibration.py --reset --days 7")
            elif total_trades == 0:
                print("\n[WARNING] La calibration est vide!")
                print("          -> Recommandation: python scripts/seed_ml_calibration.py --days 30")
            else:
                print(f"\n[OK] La calibration semble coherente ({total_trades} trades calibres, {recent_total} recents)")
            
            # 4. Verifier le dernier update
            cur.execute("""
                SELECT MAX(updated_at) FROM ml_calibration
            """)
            last_update = cur.fetchone()[0]
            if last_update:
                age = datetime.now(last_update.tzinfo) - last_update if last_update.tzinfo else datetime.now() - last_update
                print(f"\nDernier update calibration: {last_update} (il y a {age.total_seconds()/3600:.1f}h)")
                
                if age.total_seconds() > 3600 * 24:
                    print("[WARNING] Pas d'update depuis plus de 24h - verifier que les trades mettent a jour la calibration")
            
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pg_logger.pool.putconn(conn)


if __name__ == "__main__":
    check_calibration()

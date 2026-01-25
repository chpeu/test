#!/usr/bin/env python3
"""
Recalcule la calibration ML a partir des trades existants.

Corrige le bug ou ml_confidence etait stockee en decimal (0.51) 
mais la calibration attendait des pourcentages (51).
"""
import sys
sys.path.append('.')

from datetime import datetime, timezone
from decimal import Decimal

def main():
    print('='*80)
    print('RECALCULATION ML CALIBRATION')
    print('='*80)
    
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        from ml.calibration import MLCalibrationManager, VALID_EXIT_REASONS_CALIBRATION
        
        pg_logger = PostgreSQLDataLogger()
        if not pg_logger.enabled or not pg_logger.pool:
            print('[ERROR] PostgreSQL non disponible')
            return 1
        
        # 1. Reset des buckets de calibration
        print('\n1. RESET DES BUCKETS DE CALIBRATION...')
        conn = pg_logger.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE ml_calibration
                    SET weighted_wins = 0,
                        weighted_total = 0,
                        total_trades = 0,
                        actual_winrate = NULL,
                        avg_pnl_pct = 0,
                        total_pnl_usdt = 0,
                        updated_at = NOW()
                """)
                conn.commit()
                print(f'   [OK] Buckets reinitialises')
        finally:
            pg_logger.pool.putconn(conn)
        
        # 2. Recuperer tous les trades avec ml_confidence
        print('\n2. RECUPERATION DES TRADES...')
        conn = pg_logger.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, symbol, direction, ml_confidence, net_pnl_usdt, 
                           pnl_pct, exit_reason, is_live_trade, created_at
                    FROM trades
                    WHERE ml_confidence IS NOT NULL
                    AND exit_reason IS NOT NULL
                    ORDER BY created_at ASC
                """)
                trades = cur.fetchall()
                print(f'   Total trades avec ml_confidence: {len(trades)}')
        finally:
            pg_logger.pool.putconn(conn)
        
        if not trades:
            print('   [WARNING] Aucun trade a traiter')
            return 0
        
        # 3. Traiter chaque trade
        print('\n3. RECALCUL DE LA CALIBRATION...')
        
        calib_manager = MLCalibrationManager()
        processed = 0
        skipped_exit = 0
        skipped_conf = 0
        wins = 0
        losses = 0
        
        for trade in trades:
            trade_id, symbol, direction, ml_conf_raw, net_pnl_usdt, pnl_pct, exit_reason, is_live, created_at = trade
            
            # Convertir ml_confidence en pourcentage si decimal
            if ml_conf_raw is not None:
                ml_conf_raw = float(ml_conf_raw)
                ml_conf_pct = ml_conf_raw * 100 if ml_conf_raw < 1 else ml_conf_raw
            else:
                ml_conf_pct = None
            
            # Filtrer par exit_reason (exclure MANUAL, ERROR, etc.)
            if exit_reason and exit_reason.upper() not in VALID_EXIT_REASONS_CALIBRATION:
                skipped_exit += 1
                continue
            
            # Filtrer par confidence minimum (30%)
            if ml_conf_pct is None or ml_conf_pct < 30:
                skipped_conf += 1
                continue
            
            # Determiner win/loss
            pnl = float(pnl_pct) if pnl_pct else (float(net_pnl_usdt) if net_pnl_usdt else 0)
            win = pnl > 0
            
            if win:
                wins += 1
            else:
                losses += 1
            
            # Mettre a jour la calibration
            try:
                calib_manager.update_calibration(
                    direction=direction,
                    ml_confidence=ml_conf_pct,
                    win=win,
                    pnl_pct=float(pnl_pct) if pnl_pct else 0,
                    pnl_usdt=float(net_pnl_usdt) if net_pnl_usdt else 0,
                    is_live=bool(is_live),
                    is_dry_run=not bool(is_live),
                    trade_timestamp=created_at if created_at else datetime.now(timezone.utc),
                    exit_reason=exit_reason
                )
                processed += 1
            except Exception as e:
                print(f'   [ERROR] Trade {trade_id}: {e}')
        
        print(f'   Trades traites: {processed}')
        print(f'   Trades ignores (exit_reason): {skipped_exit}')
        print(f'   Trades ignores (conf < 30%): {skipped_conf}')
        print(f'   Wins: {wins} | Losses: {losses}')
        if wins + losses > 0:
            print(f'   Winrate global: {wins/(wins+losses)*100:.1f}%')
        
        # 4. Afficher les resultats
        print('\n4. RESULTATS CALIBRATION:')
        conn = pg_logger.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT direction, confidence_bucket, weighted_wins, weighted_total, 
                           total_trades, actual_winrate
                    FROM ml_calibration
                    WHERE total_trades > 0
                    ORDER BY direction, confidence_bucket
                """)
                results = cur.fetchall()
                
                if results:
                    print(f'   {"Direction":<8} | {"Bucket":<8} | {"Wins":>8} | {"Total":>8} | {"Trades":>6} | {"WR":>6}')
                    print('   ' + '-'*60)
                    for row in results:
                        direction, bucket, w_wins, w_total, trades_count, winrate = row
                        wr_str = f'{winrate:.1f}%' if winrate else 'N/A'
                        print(f'   {direction:<8} | {bucket:<8} | {float(w_wins):>8.2f} | {float(w_total):>8.2f} | {trades_count:>6} | {wr_str:>6}')
                else:
                    print('   [WARNING] Aucun bucket avec des trades')
        finally:
            pg_logger.pool.putconn(conn)
        
        print('\n' + '='*80)
        print('RECALCULATION TERMINEE')
        print('='*80)
        return 0
        
    except Exception as e:
        print(f'[ERROR] Erreur: {e}')
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    _imported_mod = sys.modules.get('scripts.recalculate_ml_calibration')
    if _imported_mod is not None and hasattr(_imported_mod, 'main'):
        sys.exit(_imported_mod.main())
    sys.exit(main())

#!/usr/bin/env python3
"""
Script de monitoring continu des executions de trades
=====================================================
Surveille en temps reel que les trades sont correctement executes et logges.

Verifications:
1. Prix de sortie reel vs theorique
2. Coherence PnL calcule vs PnL reel
3. Presence des champs critiques (exit_fill_price, etc.)
4. Detection des anomalies (ecarts > seuil)

Usage: python scripts/monitor_trade_execution.py [--interval 60]
"""
import os
import sys
import time
import argparse
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_recent_trades(minutes=5):
    """Verifier les trades des X dernieres minutes"""
    from core.postgresql_datalogger import PostgreSQLDataLogger
    
    pg_logger = PostgreSQLDataLogger()
    if not pg_logger.enabled:
        return {'error': 'PostgreSQL non disponible'}
    
    conn = pg_logger.pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT 
                    id, symbol, direction, 
                    entry_price, exit_price, sl_price, tp_price,
                    exit_reason, pnl_pct, net_pnl_pct, net_pnl_usdt,
                    entry_fill_price, exit_fill_price,
                    size_usdt, duration_seconds,
                    created_at
                FROM trades 
                WHERE created_at > NOW() - INTERVAL '{minutes} minutes'
                ORDER BY created_at DESC
            """)
            trades = cur.fetchall()
            
            results = {
                'timestamp': datetime.now().isoformat(),
                'period_minutes': minutes,
                'trades_count': len(trades),
                'issues': [],
                'trades': []
            }
            
            for t in trades:
                trade_info = {
                    'id': str(t[0])[:8],
                    'symbol': t[1],
                    'direction': t[2],
                    'entry_price': float(t[3]) if t[3] else 0,
                    'exit_price': float(t[4]) if t[4] else 0,
                    'sl_price': float(t[5]) if t[5] else 0,
                    'exit_reason': t[7],
                    'pnl_pct': float(t[8]) if t[8] else 0,
                    'net_pnl_pct': float(t[9]) if t[9] else 0,
                    'net_pnl_usdt': float(t[10]) if t[10] else 0,
                    'exit_fill_price': float(t[12]) if t[12] else None,
                    'size_usdt': float(t[13]) if t[13] else 0,
                    'duration_seconds': float(t[14]) if t[14] else 0,
                    'created_at': str(t[15])
                }
                
                # Verifications
                issues = []
                
                # 1. exit_fill_price manquant
                if trade_info['exit_fill_price'] is None:
                    issues.append('exit_fill_price manquant')
                
                # 2. Pour SL_EXCHANGE, verifier coherence prix
                if trade_info['exit_reason'] == 'SL_EXCHANGE':
                    if trade_info['sl_price'] > 0 and trade_info['exit_price'] > 0:
                        # Calculer ecart entre SL theorique et prix de sortie
                        ecart = abs(trade_info['exit_price'] - trade_info['sl_price']) / trade_info['sl_price'] * 100
                        if ecart > 0.5:  # Plus de 0.5% d'ecart
                            issues.append(f'Ecart SL_EXCHANGE: {ecart:.2f}%')
                
                # 3. PnL coherent avec prix
                if trade_info['entry_price'] > 0 and trade_info['exit_price'] > 0:
                    if trade_info['direction'] == 'LONG':
                        expected_pnl = (trade_info['exit_price'] - trade_info['entry_price']) / trade_info['entry_price'] * 100
                    else:
                        expected_pnl = (trade_info['entry_price'] - trade_info['exit_price']) / trade_info['entry_price'] * 100
                    
                    actual_pnl = trade_info['pnl_pct']
                    pnl_diff = abs(expected_pnl - actual_pnl)
                    if pnl_diff > 0.1:  # Plus de 0.1% de difference
                        issues.append(f'PnL incoherent: attendu {expected_pnl:.3f}%, reel {actual_pnl:.3f}%')
                
                # 4. Duration suspecte (< 5s ou > 1h)
                if trade_info['duration_seconds'] < 5:
                    issues.append(f'Duration tres courte: {trade_info["duration_seconds"]}s')
                elif trade_info['duration_seconds'] > 3600:
                    issues.append(f'Duration tres longue: {trade_info["duration_seconds"]/60:.0f}min')
                
                trade_info['issues'] = issues
                results['trades'].append(trade_info)
                
                if issues:
                    results['issues'].append({
                        'trade_id': trade_info['id'],
                        'symbol': trade_info['symbol'],
                        'issues': issues
                    })
            
            return results
            
    except Exception as e:
        return {'error': str(e)}
    finally:
        pg_logger.pool.putconn(conn)


def print_status(results):
    """Afficher le statut de maniere lisible"""
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("=" * 60)
    print(f"  MONITORING TRADES - {results.get('timestamp', 'N/A')}")
    print("=" * 60)
    
    if 'error' in results:
        print(f"\n[ERREUR] {results['error']}")
        return
    
    print(f"\nPeriode: {results['period_minutes']} dernieres minutes")
    print(f"Trades trouves: {results['trades_count']}")
    
    if results['trades_count'] == 0:
        print("\nAucun trade recent.")
    else:
        print("\n--- TRADES RECENTS ---")
        for t in results['trades'][:5]:  # Max 5 trades
            status = "[OK]" if not t['issues'] else "[!!]"
            print(f"\n{status} {t['symbol']} | {t['direction']} | {t['exit_reason']}")
            print(f"    Entry: {t['entry_price']:.6f} | Exit: {t['exit_price']:.6f}")
            print(f"    PnL: {t['net_pnl_pct']:.3f}% ({t['net_pnl_usdt']:.4f} USDT)")
            print(f"    Duration: {t['duration_seconds']:.0f}s | Size: {t['size_usdt']:.2f} USDT")
            if t['exit_fill_price']:
                print(f"    Exit Fill: {t['exit_fill_price']:.6f}")
            if t['issues']:
                for issue in t['issues']:
                    print(f"    [ISSUE] {issue}")
    
    if results['issues']:
        print("\n" + "=" * 60)
        print(f"  PROBLEMES DETECTES: {len(results['issues'])}")
        print("=" * 60)
        for issue in results['issues']:
            print(f"\n  Trade {issue['trade_id']} ({issue['symbol']}):")
            for i in issue['issues']:
                print(f"    - {i}")
    else:
        print("\n[OK] Aucun probleme detecte")
    
    print("\n" + "-" * 60)
    print("Ctrl+C pour arreter le monitoring")


def main():
    parser = argparse.ArgumentParser(description='Monitoring des executions de trades')
    parser.add_argument('--interval', type=int, default=30, help='Intervalle de verification en secondes')
    parser.add_argument('--period', type=int, default=10, help='Periode a analyser en minutes')
    parser.add_argument('--once', action='store_true', help='Executer une seule fois')
    args = parser.parse_args()
    
    print("Demarrage du monitoring...")
    
    try:
        while True:
            results = check_recent_trades(minutes=args.period)
            print_status(results)
            
            if args.once:
                break
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring arrete.")


if __name__ == "__main__":
    main()

"""
Script pour initialiser la calibration ML avec les trades historiques.

Usage:
    python scripts/seed_ml_calibration.py [--days 30] [--reset]
"""

import sys
import os
import argparse

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.calibration import get_calibration_manager


def main():
    parser = argparse.ArgumentParser(description='Seed ML Calibration avec trades historiques')
    parser.add_argument('--days', type=int, default=30, help='Nombre de jours d\'historique (défaut: 30)')
    parser.add_argument('--reset', action='store_true', help='Reset la calibration avant seed')
    args = parser.parse_args()
    
    print(f"[START] Initialisation ML Calibration avec {args.days} jours d'historique...")
    
    calib_manager = get_calibration_manager()
    
    if args.reset:
        print("[RESET] Reset de la calibration...")
        calib_manager.reset_calibration(reason="manual_seed_reset")
    
    # Seed avec historique
    count = calib_manager.seed_from_historical_trades(days=args.days)
    
    print(f"[OK] {count} trades traites")
    
    # Afficher les stats
    print("\n[STATS] Statistiques de calibration:\n")
    stats = calib_manager.get_all_stats()
    
    print(f"{'Direction':<10} {'Bucket':<10} {'Trades':<10} {'Weighted':<10} {'WR Reel':<12} {'Avg PnL':<10}")
    print("-" * 70)
    
    for direction in ['LONG', 'SHORT']:
        for bucket in ['30-35', '35-40', '40-45', '45-50', '50+']:
            s = stats.get(direction, {}).get(bucket)
            if s:
                wr_str = f"{s.actual_winrate:.1f}%" if s.actual_winrate else "N/A"
                print(f"{direction:<10} {bucket:<10} {s.total_trades:<10} {s.weighted_total:<10.2f} {wr_str:<12} {s.avg_pnl_pct:<10.3f}%")
    
    print()


if __name__ == '__main__':
    main()

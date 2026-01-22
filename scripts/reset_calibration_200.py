#!/usr/bin/env python3
"""
Reset ML Calibration avec les 200 derniers trades
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.calibration import get_calibration_manager

def main():
    print("[START] Reset ML Calibration avec les 200 derniers trades...")
    
    calib_manager = get_calibration_manager()
    
    # Reset
    print("[RESET] Reset de la calibration...")
    calib_manager.reset_calibration(reason="manual_reset_200_trades")
    
    # Seed avec les 200 derniers trades
    print("[SEED] Seeding avec les 200 derniers trades...")
    count = calib_manager.seed_from_last_n_trades(n_trades=200)
    
    print(f"[OK] {count} trades traites")
    
    # Afficher les stats
    print("\n[STATS] Nouvelles statistiques de calibration:\n")
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

"""
Test CorrelationEngine - Phase 2A
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.analysis.correlation_engine import get_correlation_engine

def main():
    print("=" * 60)
    print("TEST CORRELATION ENGINE - Phase 2A")
    print("=" * 60)
    
    engine = get_correlation_engine()
    report = engine.get_full_analysis_report(7)
    
    print(f"\nSessions: {len(report['by_session'])}")
    print(f"Regimes: {len(report['by_local_regime'])}")
    print(f"Hours: {len(report['by_hour'])}")
    print(f"Exit Reasons: {len(report['by_exit_reason'])}")
    print(f"Suggestions: {len(report['suggestions'])}")
    
    print("\n--- Par Session ---")
    for s in report['by_session']:
        print(f"  {s['value']}: {s['trades']} trades, WR={s['winrate']}%, PnL={s['total_pnl']} ({s['recommendation']})")
    
    print("\n--- Par Regime Local ---")
    for r in report['by_local_regime']:
        print(f"  {r['value']}: {r['trades']} trades, WR={r['winrate']}%, PnL={r['total_pnl']} ({r['recommendation']})")
    
    print("\n--- Par Exit Reason ---")
    for e in report['by_exit_reason']:
        print(f"  {e['value']}: {e['trades']} trades, WR={e['winrate']}%, PnL={e['total_pnl']}")
    
    print("\n--- Distribution Regime Optimal ---")
    dist = report.get('optimal_regime_distribution', {})
    for regime, data in dist.get('distribution', {}).items():
        print(f"  {regime}: {data['trades']} trades ({data['percentage']}%)")
    print(f"  Dominant: {dist.get('dominant_regime')}")
    
    print("\n--- Suggestions ---")
    for s in report['suggestions']:
        print(f"  [{s['confidence']}] {s['parameter']}: {s['expected_improvement']}")
    
    print("\n" + "=" * 60)
    print("TEST TERMINE")
    print("=" * 60)

if __name__ == "__main__":
    main()

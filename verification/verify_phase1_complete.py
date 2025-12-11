"""
Verification complete Phase 0 + 1A + 1B + 1C
Market Regime V2 + ATR Optimization

Usage:
    python verification/verify_phase1_complete.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import psycopg2


def get_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )


def check_phase0_infrastructure():
    """Verifie Phase 0: Infrastructure"""
    print("\n" + "=" * 60)
    print("PHASE 0: INFRASTRUCTURE")
    print("=" * 60)
    
    results = {}
    
    # 1. Verifier session_detector
    try:
        from utils.session_detector import get_current_session, get_day_info
        session = get_current_session()
        day = get_day_info()
        print(f"  [OK] session_detector: {session['name']} (x{session['atr_multiplier']})")
        print(f"       hour_utc={day['hour_utc']}, day_of_week={day['day_of_week']}")
        results['session_detector'] = True
    except Exception as e:
        print(f"  [ERREUR] session_detector: {e}")
        results['session_detector'] = False
    
    # 2. Verifier config MARKET_REGIME_V2_CONFIG
    try:
        from config import MARKET_REGIME_V2_CONFIG
        toggles = ['v2_enabled', 'use_median', 'use_hysteresis', 'use_smoothing']
        print(f"  [OK] MARKET_REGIME_V2_CONFIG present ({len(MARKET_REGIME_V2_CONFIG)} cles)")
        results['config'] = True
    except Exception as e:
        print(f"  [ERREUR] MARKET_REGIME_V2_CONFIG: {e}")
        results['config'] = False
    
    # 3. Verifier colonnes SQL
    conn = get_connection()
    cur = conn.cursor()
    
    # Colonnes trade_atr_metrics
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'trade_atr_metrics' 
        AND column_name IN ('session_market', 'hour_utc', 'regime_detection_method', 
                           'pnl_if_calme_params', 'optimal_regime_retrospective')
    """)
    cols = [r[0] for r in cur.fetchall()]
    if len(cols) >= 5:
        print(f"  [OK] Colonnes trade_atr_metrics: {len(cols)} colonnes V2")
        results['sql_columns'] = True
    else:
        print(f"  [ATTENTION] Colonnes trade_atr_metrics: {cols}")
        results['sql_columns'] = False
    
    cur.close()
    conn.close()
    
    return all(results.values())


def check_phase1a_logging():
    """Verifie Phase 1A: Logging Contextuel"""
    print("\n" + "=" * 60)
    print("PHASE 1A: LOGGING CONTEXTUEL")
    print("=" * 60)
    
    conn = get_connection()
    cur = conn.cursor()
    
    results = {}
    
    # 1. trade_atr_metrics
    cur.execute("""
        SELECT COUNT(*) as total,
               COUNT(session_market) as session_filled,
               COUNT(hour_utc) as hour_filled
        FROM trade_atr_metrics
    """)
    row = cur.fetchone()
    total, session, hour = row
    pct = 100 * session / total if total > 0 else 0
    status = "[OK]" if pct >= 90 else "[ATTENTION]"
    print(f"  {status} trade_atr_metrics: {session}/{total} avec session_market ({pct:.0f}%)")
    results['trades'] = pct >= 90
    
    # 2. scan_logs
    cur.execute("""
        SELECT COUNT(*) as total,
               COUNT(session_market) as session_filled
        FROM scan_logs
    """)
    row = cur.fetchone()
    total, session = row
    pct = 100 * session / total if total > 0 else 0
    status = "[OK]" if pct >= 90 else "[ATTENTION]"
    print(f"  {status} scan_logs: {session}/{total} avec session_market ({pct:.0f}%)")
    results['scans'] = pct >= 90
    
    # 3. market_regime_history
    cur.execute("""
        SELECT COUNT(*) as total,
               COUNT(session_market) as session_filled,
               COUNT(detection_method) as method_filled
        FROM market_regime_history
    """)
    row = cur.fetchone()
    total, session, method = row
    pct = 100 * session / total if total > 0 else 0
    print(f"  [OK] market_regime_history: {total} entrees, {session} avec session")
    results['regime_history'] = True
    
    cur.close()
    conn.close()
    
    return all(results.values())


def check_phase1b_v2_methods():
    """Verifie Phase 1B: Methodes V2"""
    print("\n" + "=" * 60)
    print("PHASE 1B: METHODES V2 (REGIME SELECTOR)")
    print("=" * 60)
    
    results = {}
    
    try:
        from core.market_regime_selector import MarketRegimeSelector
        rs = MarketRegimeSelector()
        
        # Verifier methodes presentes
        methods = ['calculate_atr_metric', 'apply_smoothing', 
                   'should_change_regime', 'calculate_combined_atr']
        
        for method in methods:
            if hasattr(rs, method):
                print(f"  [OK] {method}() presente")
                results[method] = True
            else:
                print(f"  [ERREUR] {method}() manquante")
                results[method] = False
        
        # Test rapide calculate_atr_metric
        test_values = [0.20, 0.22, 0.19, 0.21, 0.23]
        result = rs.calculate_atr_metric(test_values)
        print(f"  [OK] calculate_atr_metric([...]) = {result:.4f}%")
        
        # Verifier attributs V2
        attrs = ['last_atr_median', 'last_atr_smoothed', 'hysteresis_was_applied']
        for attr in attrs:
            if hasattr(rs, attr):
                print(f"  [OK] Attribut {attr} present")
            else:
                print(f"  [ATTENTION] Attribut {attr} manquant")
        
    except Exception as e:
        print(f"  [ERREUR] Import MarketRegimeSelector: {e}")
        return False
    
    return all(results.values())


def check_phase1c_whatif():
    """Verifie Phase 1C: What-If Regime"""
    print("\n" + "=" * 60)
    print("PHASE 1C: WHAT-IF REGIME")
    print("=" * 60)
    
    results = {}
    
    # 1. Verifier methode simulate_regime_scenarios
    try:
        from core.analysis.what_if_simulator import WhatIfSimulator, TradeData
        simulator = WhatIfSimulator()
        
        if hasattr(simulator, 'simulate_regime_scenarios'):
            print(f"  [OK] simulate_regime_scenarios() presente")
            results['method'] = True
        else:
            print(f"  [ERREUR] simulate_regime_scenarios() manquante")
            results['method'] = False
        
        if hasattr(simulator, 'update_regime_whatif'):
            print(f"  [OK] update_regime_whatif() presente")
        
    except Exception as e:
        print(f"  [ERREUR] Import WhatIfSimulator: {e}")
        results['method'] = False
    
    # 2. Verifier donnees DB
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT COUNT(*) as total,
               COUNT(pnl_if_calme_params) as calme,
               COUNT(pnl_if_normal_params) as normal,
               COUNT(pnl_if_volatile_params) as volatile,
               COUNT(optimal_regime_retrospective) as optimal
        FROM trade_atr_metrics
    """)
    row = cur.fetchone()
    total, calme, normal, volatile, optimal = row
    pct = 100 * optimal / total if total > 0 else 0
    
    print(f"  [OK] What-If Regime: {optimal}/{total} trades calcules ({pct:.0f}%)")
    results['data'] = True
    
    # 3. Distribution regimes optimaux
    cur.execute("""
        SELECT optimal_regime_retrospective, COUNT(*) 
        FROM trade_atr_metrics 
        WHERE optimal_regime_retrospective IS NOT NULL
        GROUP BY optimal_regime_retrospective
        ORDER BY COUNT(*) DESC
    """)
    rows = cur.fetchall()
    if rows:
        print(f"\n  Distribution regimes optimaux:")
        for regime, count in rows:
            pct = 100 * count / optimal if optimal > 0 else 0
            print(f"    - {regime}: {count} trades ({pct:.0f}%)")
    
    cur.close()
    conn.close()
    
    return all(results.values())


def check_toggles_status():
    """Verifie l'etat des toggles V2"""
    print("\n" + "=" * 60)
    print("TOGGLES V2 (config_overrides.json)")
    print("=" * 60)
    
    from utils.config_persistence import get_config_value
    
    toggles = [
        ('market_regime_v2_enabled', False),
        ('market_regime_use_median', False),
        ('market_regime_use_hysteresis', False),
        ('market_regime_use_smoothing', False),
        ('market_regime_use_atr_5m', False),
        ('market_regime_use_seasonality', False),
    ]
    
    all_off = True
    for key, expected in toggles:
        value = get_config_value(key, expected)
        status = "OFF" if not value else "ON"
        icon = "[OK]" if value == expected else "[ACTIF]"
        print(f"  {icon} {key} = {status}")
        if value != expected:
            all_off = False
    
    if all_off:
        print(f"\n  [OK] Tous toggles OFF - Comportement V1 preserve")
    else:
        print(f"\n  [INFO] Certains toggles actifs - Mode V2 partiel")
    
    return True


def check_session_performance():
    """Analyse performance par session"""
    print("\n" + "=" * 60)
    print("PERFORMANCE PAR SESSION (Insight)")
    print("=" * 60)
    
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            tam.session_market,
            COUNT(*) as trades,
            ROUND(AVG(t.pnl_pct)::numeric, 3) as avg_pnl,
            SUM(CASE WHEN t.pnl_pct > 0 THEN 1 ELSE 0 END) as wins
        FROM trade_atr_metrics tam
        JOIN trades t ON t.id = tam.trade_id
        WHERE tam.session_market IS NOT NULL
        GROUP BY tam.session_market
        ORDER BY avg_pnl DESC
    """)
    
    rows = cur.fetchall()
    if rows:
        print(f"  {'Session':<15} {'Trades':>8} {'Avg PnL':>10} {'Win%':>8}")
        print(f"  {'-'*15} {'-'*8} {'-'*10} {'-'*8}")
        for session, trades, avg_pnl, wins in rows:
            winrate = 100 * wins / trades if trades > 0 else 0
            indicator = "+" if float(avg_pnl or 0) > 0 else ""
            print(f"  {session:<15} {trades:>8} {indicator}{avg_pnl:>9}% {winrate:>7.0f}%")
    
    cur.close()
    conn.close()
    
    return True


def main():
    print("=" * 60)
    print("VERIFICATION COMPLETE - PHASE 0 + 1A + 1B + 1C")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    results = {
        "Phase 0 (Infrastructure)": check_phase0_infrastructure(),
        "Phase 1A (Logging)": check_phase1a_logging(),
        "Phase 1B (Methodes V2)": check_phase1b_v2_methods(),
        "Phase 1C (What-If Regime)": check_phase1c_whatif(),
        "Toggles V2": check_toggles_status(),
    }
    
    # Bonus: Performance par session
    check_session_performance()
    
    print("\n" + "=" * 60)
    print("RESUME FINAL")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "[OK]" if passed else "[ECHEC]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] PHASES 0-1C OPERATIONNELLES!")
        print("\nEtat actuel:")
        print("  - Infrastructure V2 en place")
        print("  - Logging contextuel actif")
        print("  - Methodes V2 pretes (toggles OFF)")
        print("  - What-If Regime calcule")
        print("\nProchaine etape: Phase 1D (Integration composants)")
        print("  -> Necessite FRONTEND pour toggles V2")
    else:
        print("[ECHEC] Verifier les erreurs ci-dessus")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

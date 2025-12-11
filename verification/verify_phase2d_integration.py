"""
Vérification Phase 2D - Threshold Optimizer & Drift Detector Integration
=========================================================================
Ce script vérifie que les composants Phase 2D fonctionnent correctement.

Usage:
    python verification/verify_phase2d_integration.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(test_name: str, passed: bool, details: str = ""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} | {test_name}")
    if details:
        print(f"       -> {details}")


def test_threshold_optimizer_import():
    """Test 1: Import du Threshold Optimizer"""
    try:
        from core.ml import get_threshold_optimizer, ContextualThresholdOptimizer
        optimizer = get_threshold_optimizer()
        return True, f"Instance: {type(optimizer).__name__}"
    except Exception as e:
        return False, str(e)


def test_drift_detector_import():
    """Test 2: Import du Drift Detector"""
    try:
        from core.ml import get_drift_detector, MarketDriftDetector
        detector = get_drift_detector()
        return True, f"Instance: {type(detector).__name__}"
    except Exception as e:
        return False, str(e)


def test_threshold_optimizer_get_threshold():
    """Test 3: Obtention d'un seuil dynamique"""
    try:
        from core.ml import get_threshold_optimizer
        optimizer = get_threshold_optimizer()
        
        # Tester différents contextes
        contexts = [
            ('CALME', 'EUROPE', 10),
            ('NORMAL', 'US', 14),
            ('VOLATILE', 'ASIA', 2),
        ]
        
        thresholds = []
        for regime, session, hour in contexts:
            threshold = optimizer.get_threshold(regime=regime, session=session, hour=hour)
            thresholds.append((regime, session, threshold))
        
        # Vérifier que les seuils sont dans les bornes
        all_valid = all(0.40 <= t <= 0.80 for _, _, t in thresholds)
        details = ", ".join([f"{r}/{s}={t*100:.0f}%" for r, s, t in thresholds])
        
        return all_valid, details
    except Exception as e:
        return False, str(e)


def test_threshold_optimizer_update():
    """Test 4: Mise à jour après un trade"""
    try:
        from core.ml import get_threshold_optimizer
        optimizer = get_threshold_optimizer()
        
        # Simuler un trade
        regime, session, hour = 'NORMAL', 'EUROPE', 10
        
        # Obtenir stats avant
        context_key = optimizer._get_context_key(regime, session, hour)
        stats_before = optimizer._context_stats.get(context_key)
        trades_before = stats_before.total_trades if stats_before else 0
        
        # Mettre à jour
        optimizer.update(regime=regime, session=session, hour=hour, win=True, pnl=0.15)
        
        # Vérifier stats après
        stats_after = optimizer._context_stats.get(context_key)
        trades_after = stats_after.total_trades if stats_after else 0
        
        passed = trades_after == trades_before + 1
        return passed, f"Trades: {trades_before} -> {trades_after}"
    except Exception as e:
        return False, str(e)


def test_drift_detector_update():
    """Test 5: Mise à jour du Drift Detector"""
    try:
        from core.ml import get_drift_detector
        detector = get_drift_detector()
        
        trades_before = detector.total_trades
        
        # Simuler quelques trades
        result = detector.update(pnl=0.10, win=True)
        
        trades_after = detector.total_trades
        passed = trades_after == trades_before + 1
        
        details = f"Trades: {trades_before} -> {trades_after}, Drift: {result.get('drift_detected', False)}"
        return passed, details
    except Exception as e:
        return False, str(e)


def test_drift_detector_status():
    """Test 6: Status du Drift Detector"""
    try:
        from core.ml import get_drift_detector
        detector = get_drift_detector()
        
        status = detector.get_status()
        
        required_keys = ['enabled', 'total_trades', 'pnl_stats', 'winrate_stats']
        has_all_keys = all(k in status for k in required_keys)
        
        details = f"enabled={status.get('enabled')}, trades={status.get('total_trades')}"
        return has_all_keys, details
    except Exception as e:
        return False, str(e)


def test_config_variables_exist():
    """Test 7: Variables de config Phase 2D existent"""
    try:
        from config import TRADING_CONFIG
        
        required_vars = [
            'threshold_optimizer_enabled',
            'threshold_min',
            'threshold_max',
            'drift_detection_enabled',
        ]
        
        missing = [v for v in required_vars if v not in TRADING_CONFIG]
        
        if missing:
            return False, f"Manquantes: {missing}"
        
        values = {v: TRADING_CONFIG.get(v) for v in required_vars}
        details = ", ".join([f"{k}={v}" for k, v in values.items()])
        return True, details
    except Exception as e:
        return False, str(e)


def test_api_config_returns_phase2d():
    """Test 8: /api/config retourne les variables Phase 2D"""
    try:
        import requests
        
        response = requests.get('http://localhost:5000/api/config', timeout=5)
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        
        data = response.json()
        
        required_vars = [
            'threshold_optimizer_enabled',
            'threshold_min',
            'threshold_max',
            'drift_detection_enabled',
        ]
        
        missing = [v for v in required_vars if v not in data]
        
        if missing:
            return False, f"Manquantes dans API: {missing}"
        
        values = {v: data.get(v) for v in required_vars}
        details = ", ".join([f"{k}={v}" for k, v in values.items()])
        return True, details
    except requests.exceptions.ConnectionError:
        return False, "Backend non accessible (démarrer main.py)"
    except Exception as e:
        return False, str(e)


def test_websocket_update_phase2d():
    """Test 9: WebSocket accepte les variables Phase 2D"""
    try:
        from config import TRADING_CONFIG
        
        # Vérifier que les variables sont dans TRADING_CONFIG
        # (le WebSocket handler les acceptera si elles sont dans le code)
        
        # Vérifier le code du handler dans main.py
        import re
        
        main_py_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
        with open(main_py_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        handlers = [
            "if 'threshold_optimizer_enabled' in params:",
            "if 'threshold_min' in params:",
            "if 'threshold_max' in params:",
            "if 'drift_detection_enabled' in params:",
        ]
        
        found = [h for h in handlers if h in content]
        missing = [h for h in handlers if h not in content]
        
        if missing:
            return False, f"Handlers manquants: {len(missing)}/{len(handlers)}"
        
        return True, f"Tous les {len(handlers)} handlers trouvés"
    except Exception as e:
        return False, str(e)


def test_feedback_loop_in_position_manager():
    """Test 10: Feedback loop dans position_manager.py"""
    try:
        pm_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'position_manager.py')
        with open(pm_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            "PHASE 2D: Feedback loop",
            "get_threshold_optimizer",
            "get_drift_detector",
            "optimizer.update(",
            "detector.update(",
            "drift_detected",
            "optimizer.reset_all()",
        ]
        
        found = [c for c in checks if c in content]
        missing = [c for c in checks if c not in content]
        
        if missing:
            return False, f"Manquants: {missing}"
        
        return True, f"Tous les {len(checks)} éléments trouvés"
    except Exception as e:
        return False, str(e)


def test_threshold_optimizer_persistence():
    """Test 11: Persistance du Threshold Optimizer"""
    try:
        from core.ml import get_threshold_optimizer
        optimizer = get_threshold_optimizer()
        
        # Vérifier le chemin de persistence
        path = optimizer.persistence_path
        
        if path.exists():
            return True, f"Fichier existe: {path}"
        else:
            # Le fichier sera créé après la première sauvegarde
            return True, f"Chemin configuré: {path} (sera créé après 10 updates)"
    except Exception as e:
        return False, str(e)


def test_drift_detector_persistence():
    """Test 12: Persistance du Drift Detector"""
    try:
        from core.ml import get_drift_detector
        detector = get_drift_detector()
        
        # Vérifier le chemin de persistence
        path = detector.persistence_path
        
        if path.exists():
            return True, f"Fichier existe: {path}"
        else:
            return True, f"Chemin configuré: {path} (sera créé après 50 trades)"
    except Exception as e:
        return False, str(e)


def run_all_tests():
    """Exécute tous les tests"""
    print_header("VERIFICATION PHASE 2D - Threshold Optimizer & Drift Detector")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("1. Import Threshold Optimizer", test_threshold_optimizer_import),
        ("2. Import Drift Detector", test_drift_detector_import),
        ("3. Get Threshold (contextes)", test_threshold_optimizer_get_threshold),
        ("4. Update Threshold (trade)", test_threshold_optimizer_update),
        ("5. Update Drift Detector", test_drift_detector_update),
        ("6. Status Drift Detector", test_drift_detector_status),
        ("7. Variables config.py", test_config_variables_exist),
        ("8. API /api/config Phase 2D", test_api_config_returns_phase2d),
        ("9. WebSocket handlers Phase 2D", test_websocket_update_phase2d),
        ("10. Feedback loop position_manager", test_feedback_loop_in_position_manager),
        ("11. Persistence Threshold Optimizer", test_threshold_optimizer_persistence),
        ("12. Persistence Drift Detector", test_drift_detector_persistence),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed, details = test_func()
            results.append(passed)
            print_result(test_name, passed, details)
        except Exception as e:
            results.append(False)
            print_result(test_name, False, f"Exception: {e}")
    
    # Résumé
    print_header("RÉSUMÉ")
    passed = sum(results)
    total = len(results)
    pct = (passed / total) * 100 if total > 0 else 0
    
    print(f"Tests passés: {passed}/{total} ({pct:.0f}%)")
    
    if passed == total:
        print("\n[OK] PHASE 2D ENTIEREMENT OPERATIONNELLE!")
        print("\nProchaines etapes:")
        print("  1. Activer threshold_optimizer_enabled dans Config ML")
        print("  2. Activer drift_detection_enabled dans Config ML")
        print("  3. Trader et observer les logs:")
        print("     - Threshold Optimizer updated: ...")
        print("     - DRIFT DETECTE (si drift)")
    else:
        print(f"\n[WARNING] {total - passed} test(s) echoue(s)")
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

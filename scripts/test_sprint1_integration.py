#!/usr/bin/env python3
"""
Script de Test Sprint 1 - Market Regime & Trading Circuit Breaker
==================================================================

Ce script teste l'intégration complète des fonctionnalités Sprint 1:
1. Market Regime Selector - Détection du régime de marché
2. Trading Circuit Breaker - Protection du capital

Usage:
    python scripts/test_sprint1_integration.py
"""

import sys
import os
import asyncio
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Couleurs pour la console
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def test_market_regime_selector():
    """Test du Market Regime Selector"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 1: Market Regime Selector{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    try:
        from core.market_regime_selector import (
            MarketRegimeSelector, 
            get_regime_selector,
            MarketRegime
        )
        print(f"{GREEN}[OK]{RESET} Import MarketRegimeSelector")
    except ImportError as e:
        print(f"{RED}[ERREUR]{RESET} Import: {e}")
        return False
    
    # Test création instance
    selector = get_regime_selector()
    print(f"{GREEN}[OK]{RESET} Instance créée")
    
    # Test détermination régime
    test_cases = [
        (0.10, 25, "CALME"),
        (0.25, 28, "NORMAL"),
        (0.50, 35, "VOLATILE"),
        (0.15, 18, "CHOPPY"),  # ADX < 20
    ]
    
    all_passed = True
    for atr, adx, expected in test_cases:
        result = selector.determine_regime(atr, adx)
        passed = result.value == expected
        status = f"{GREEN}[OK]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
        print(f"  {status} ATR={atr:.2f}%, ADX={adx} -> {result.value} (attendu: {expected})")
        if not passed:
            all_passed = False
    
    # Test check_regime async
    async def test_check():
        atr_values = [0.12, 0.15, 0.18, 0.14, 0.16]
        adx_values = [24, 26, 22, 25, 23]
        regime, changed = await selector.check_regime(
            atr_values=atr_values,
            adx_values=adx_values,
            force=True,
            trigger="test"
        )
        return regime
    
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(test_check())
    print(f"\n{GREEN}[OK]{RESET} check_regime() async fonctionne: {result.value}")
    
    # Test get_status
    status = selector.get_status()
    print(f"{GREEN}[OK]{RESET} get_status() retourne: {status['current_regime']}")
    print(f"    ATR moyen: {status['avg_atr']:.3f}%")
    print(f"    ADX moyen: {status['avg_adx']:.1f}")
    
    # Test get_active_config
    config = selector.get_active_config()
    if config:
        print(f"{GREEN}[OK]{RESET} get_active_config() retourne: {len(config)} paramètres")
    else:
        print(f"{YELLOW}[WARN]{RESET} get_active_config() retourne config vide (régime UNKNOWN)")
    
    return all_passed


def test_trading_circuit_breaker():
    """Test du Trading Circuit Breaker"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 2: Trading Circuit Breaker{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    try:
        from core.trading_circuit_breaker import (
            TradingCircuitBreaker,
            get_trading_circuit_breaker,
            CircuitBreakerState
        )
        print(f"{GREEN}[OK]{RESET} Import TradingCircuitBreaker")
    except ImportError as e:
        print(f"{RED}[ERREUR]{RESET} Import: {e}")
        return False
    
    # Créer une nouvelle instance pour les tests (pas l'instance globale)
    cb = TradingCircuitBreaker(
        max_consecutive_losses=3,
        daily_drawdown_pause_pct=-2.0,
        daily_drawdown_stop_pct=-5.0,
        pause_duration_minutes=1,
        score_boost_per_loss=0.5
    )
    print(f"{GREEN}[OK]{RESET} Instance créée (max_losses=3, pause=1min)")
    
    # Test initial: peut trader
    assert cb.can_trade() == True
    print(f"{GREEN}[OK]{RESET} can_trade() = True initialement")
    
    # Simuler des trades gagnants
    cb.record_trade("BTC/USDT", 0.5, 5.0)
    cb.record_trade("ETH/USDT", 0.3, 3.0)
    assert cb.consecutive_losses == 0
    print(f"{GREEN}[OK]{RESET} 2 trades gagnants -> consecutive_losses=0")
    
    # Simuler des pertes consécutives
    cb.record_trade("XRP/USDT", -0.2, -2.0)
    assert cb.consecutive_losses == 1
    print(f"{GREEN}[OK]{RESET} 1 perte -> consecutive_losses=1")
    
    cb.record_trade("SOL/USDT", -0.3, -3.0)
    assert cb.consecutive_losses == 2
    assert cb.get_score_boost() == 1.0  # 2 * 0.5
    print(f"{GREEN}[OK]{RESET} 2 pertes -> score_boost=1.0")
    
    cb.record_trade("DOGE/USDT", -0.1, -1.0)
    # Après 3 pertes, circuit breaker en pause
    assert cb.state == CircuitBreakerState.PAUSED
    assert cb.can_trade() == False
    print(f"{GREEN}[OK]{RESET} 3 pertes -> État PAUSED, can_trade()=False")
    
    # Test reset manuel
    cb.reset(manual=True)
    assert cb.can_trade() == True
    assert cb.consecutive_losses == 0
    print(f"{GREEN}[OK]{RESET} reset() -> can_trade()=True, consecutive_losses=0")
    
    # Test drawdown journalier (pause)
    cb.record_trade("BTC/USDT", -2.5, -25.0)  # -2.5% > -2% seuil
    assert cb.state == CircuitBreakerState.PAUSED
    print(f"{GREEN}[OK]{RESET} Drawdown -2.5% -> État PAUSED")
    
    cb.reset()
    
    # Test drawdown critique (stop)
    cb.record_trade("ETH/USDT", -6.0, -60.0)  # -6% > -5% seuil
    assert cb.state == CircuitBreakerState.STOPPED
    print(f"{GREEN}[OK]{RESET} Drawdown -6% -> État STOPPED")
    
    # Test get_status
    status = cb.get_status()
    assert 'can_trade' in status
    assert 'state' in status
    assert 'consecutive_losses' in status
    print(f"{GREEN}[OK]{RESET} get_status() retourne toutes les clés attendues")
    
    return True


def test_api_endpoints():
    """Test des endpoints API"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 3: API Endpoints{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    try:
        from api.regime_endpoints import router
        print(f"{GREEN}[OK]{RESET} Import regime_endpoints.router")
    except ImportError as e:
        print(f"{RED}[ERREUR]{RESET} Import: {e}")
        return False
    
    # Vérifier que les routes sont définies
    routes = [r.path for r in router.routes]
    expected_routes = [
        '/regime/status',
        '/regime/force-check',
        '/regime/history',
        '/regime/thresholds',
        '/circuit-breaker/trading/status',
        '/circuit-breaker/trading/reset',
        '/circuit-breaker/trading/events',
        '/circuit-breaker/trading/config',
    ]
    
    all_found = True
    for expected in expected_routes:
        found = any(expected in r for r in routes)
        status = f"{GREEN}[OK]{RESET}" if found else f"{RED}[FAIL]{RESET}"
        print(f"  {status} Route {expected}")
        if not found:
            all_found = False
    
    return all_found


def test_config_files():
    """Test des fichiers de configuration régime"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 4: Fichiers Configuration Régime{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    import json
    config_dir = Path(__file__).parent.parent / "config" / "regimes"
    
    expected_files = ["calme.json", "normal.json", "volatile.json", "choppy.json"]
    all_valid = True
    
    for filename in expected_files:
        filepath = config_dir / filename
        if filepath.exists():
            try:
                with open(filepath) as f:
                    data = json.load(f)
                required_keys = ["name", "min_score_required", "atr_mult_sl", "atr_mult_tp"]
                has_all = all(k in data for k in required_keys)
                if has_all:
                    print(f"{GREEN}[OK]{RESET} {filename} - valide (min_score={data['min_score_required']})")
                else:
                    print(f"{YELLOW}[WARN]{RESET} {filename} - clés manquantes")
                    all_valid = False
            except Exception as e:
                print(f"{RED}[FAIL]{RESET} {filename} - erreur: {e}")
                all_valid = False
        else:
            print(f"{RED}[FAIL]{RESET} {filename} - fichier manquant")
            all_valid = False
    
    return all_valid


def test_config_variables():
    """Test des variables de configuration Sprint 1"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 4b: Variables Config Sprint 1{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    import json
    
    # Test config.py
    try:
        from config import TRADING_CONFIG
        
        expected_vars = [
            'market_regime_enabled',
            'market_regime_check_interval',
            'market_regime_sample_count',
            'trading_circuit_breaker_enabled',
            'trading_cb_max_consecutive_losses',
            'trading_cb_daily_drawdown_pause_pct',
            'trading_cb_score_boost_enabled',
            'trading_cb_score_boost_per_loss'
        ]
        
        all_found = True
        for var in expected_vars:
            if var in TRADING_CONFIG:
                print(f"{GREEN}[OK]{RESET} TRADING_CONFIG.{var} = {TRADING_CONFIG[var]}")
            else:
                print(f"{RED}[FAIL]{RESET} TRADING_CONFIG.{var} manquant")
                all_found = False
        
    except ImportError as e:
        print(f"{RED}[FAIL]{RESET} Import config.py: {e}")
        return False
    
    # Test config_overrides.json
    config_path = Path(__file__).parent.parent / "config_overrides.json"
    if config_path.exists():
        with open(config_path) as f:
            overrides = json.load(f)
        
        override_vars = ['market_regime_enabled', 'trading_circuit_breaker_enabled']
        for var in override_vars:
            if var in overrides:
                print(f"{GREEN}[OK]{RESET} config_overrides.{var} = {overrides[var]}")
            else:
                print(f"{RED}[FAIL]{RESET} config_overrides.{var} manquant")
                all_found = False
    else:
        print(f"{RED}[FAIL]{RESET} config_overrides.json manquant")
        return False
    
    return all_found


def test_main_integration():
    """Test d'intégration dans main.py"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 5: Intégration main.py{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    main_path = Path(__file__).parent.parent / "main.py"
    
    if not main_path.exists():
        print(f"{RED}[FAIL]{RESET} main.py introuvable")
        return False
    
    with open(main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("Import regime_router", "from api.regime_endpoints import router as regime_router"),
        ("Include regime_router", "app.include_router(regime_router)"),
        ("Import Trading CB dans scanner", "from core.trading_circuit_breaker import get_trading_circuit_breaker"),
        ("Toggle CB enabled", "trading_circuit_breaker_enabled"),
        ("Vérification can_trade()", "if not trading_cb.can_trade()"),
        ("Toggle score_boost enabled", "trading_cb_score_boost_enabled"),
        ("Vérification score_boost", "score_boost = trading_cb.get_score_boost()"),
        ("Import Market Regime", "from core.market_regime_selector import get_regime_selector"),
        ("Toggle Regime enabled", "market_regime_enabled"),
        ("Check regime dans scanner", "await regime_selector.check_regime"),
    ]
    
    all_found = True
    for name, pattern in checks:
        found = pattern in content
        status = f"{GREEN}[OK]{RESET}" if found else f"{RED}[FAIL]{RESET}"
        print(f"  {status} {name}")
        if not found:
            all_found = False
    
    return all_found


def test_position_manager_integration():
    """Test d'intégration dans position_manager.py"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 6: Intégration position_manager.py{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    pm_path = Path(__file__).parent.parent / "core" / "position_manager.py"
    
    if not pm_path.exists():
        print(f"{RED}[FAIL]{RESET} position_manager.py introuvable")
        return False
    
    with open(pm_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("Import Trading CB", "from core.trading_circuit_breaker import get_trading_circuit_breaker"),
        ("Appel record_trade()", "trading_cb.record_trade("),
    ]
    
    all_found = True
    for name, pattern in checks:
        found = pattern in content
        status = f"{GREEN}[OK]{RESET}" if found else f"{RED}[FAIL]{RESET}"
        print(f"  {status} {name}")
        if not found:
            all_found = False
    
    return all_found


def main():
    """Exécuter tous les tests"""
    print(f"\n{BLUE}{'#'*60}{RESET}")
    print(f"{BLUE}#  TESTS SPRINT 1 - Market Regime & Circuit Breaker{' '*8}#{RESET}")
    print(f"{BLUE}{'#'*60}{RESET}")
    
    results = []
    
    results.append(("Market Regime Selector", test_market_regime_selector()))
    results.append(("Trading Circuit Breaker", test_trading_circuit_breaker()))
    results.append(("API Endpoints", test_api_endpoints()))
    results.append(("Config Files", test_config_files()))
    results.append(("Config Variables Sprint 1", test_config_variables()))
    results.append(("main.py Integration", test_main_integration()))
    results.append(("position_manager.py Integration", test_position_manager_integration()))
    
    # Résumé
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}RÉSUMÉ{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    passed = 0
    failed = 0
    for name, result in results:
        if result:
            print(f"  {GREEN}[PASS]{RESET} {name}")
            passed += 1
        else:
            print(f"  {RED}[FAIL]{RESET} {name}")
            failed += 1
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    if failed == 0:
        print(f"{GREEN}Tous les tests passent! ({passed}/{passed}){RESET}")
        return 0
    else:
        print(f"{RED}{failed} test(s) échoué(s) sur {passed + failed}{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

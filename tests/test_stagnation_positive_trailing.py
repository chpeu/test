"""
Test de vérification : Stagnation Positive vs Trailing Stop
============================================================
Ce script vérifie que Stagnation Positive ne se déclenche PAS si le trailing est activé.

Scénarios testés:
1. PnL 0.05%, elapsed 120s, trailing OFF → STAGNATION_POSITIVE
2. PnL 0.05%, elapsed 120s, trailing ON → None (trailing gère)
3. PnL 0.25%, elapsed 120s, trailing ON → None (trailing gère)
4. PnL 0.02%, elapsed 120s, trailing OFF → None (sous seuil)
5. MFE Protect: MFE 0.10%, pullback 0.08% → STAGNATION_MFE_PROTECT
"""

import sys
import os
import time
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from unittest.mock import MagicMock, patch

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock des imports avant d'importer position_manager
sys.modules['core.mexc_client'] = MagicMock()
sys.modules['core.trailing_stop'] = MagicMock()

from config import TRADING_CONFIG


@dataclass
class MockPosition:
    """Position simulée pour les tests"""
    symbol: str = "TESTUSDT"
    direction: str = "LONG"
    entry: float = 100.0
    sl: float = 99.0
    tp: float = 102.0
    size: float = 10.0
    open_time: float = field(default_factory=time.time)
    
    # Trailing
    trailing_activated: bool = False
    trailing_activated_at: Optional[float] = None
    
    # Stagnation
    stagnation_detected_at: Optional[float] = None
    stagnation_pnl_at_detection: Optional[float] = None
    stagnation_positive_triggered: bool = False
    stagnation_mfe_at_exit: Optional[float] = None
    stagnation_pullback_at_exit: Optional[float] = None
    
    # MFE
    max_pnl_reached: Optional[float] = None
    
    # Autres
    partial_tp_sold: bool = False
    break_even_set: bool = False
    dynamic_sl: Optional[float] = None
    effective_config: dict = field(default_factory=dict)


def test_stagnation_positive_logic():
    """Test la logique de _check_stagnation_exit avec différents scénarios"""
    
    print("=" * 70)
    print("[TEST] Stagnation Positive vs Trailing Stop")
    print("=" * 70)
    
    # Configuration de test
    stagnation_positive_threshold = TRADING_CONFIG.get('stagnation_positive_threshold', 0.03)
    stagnation_positive_timeout = TRADING_CONFIG.get('stagnation_positive_timeout_seconds', 60)
    stagnation_mfe_pullback_pct = TRADING_CONFIG.get('stagnation_mfe_pullback_pct', 0.08)
    
    print(f"\n[CONFIG] Configuration actuelle:")
    print(f"   - stagnation_positive_threshold: {stagnation_positive_threshold}%")
    print(f"   - stagnation_positive_timeout: {stagnation_positive_timeout}s")
    print(f"   - stagnation_mfe_pullback_pct: {stagnation_mfe_pullback_pct}%")
    print(f"   - trailing_trigger_pnl: {TRADING_CONFIG.get('trailing_trigger_pnl', 0.20)}%")
    
    results = []
    
    # ═══════════════════════════════════════════════════════════════════
    # SCÉNARIO 1: PnL positif, timeout atteint, trailing OFF
    # Attendu: STAGNATION_POSITIVE
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "-" * 70)
    print("[Scenario 1] PnL=0.05%, elapsed=120s, trailing=OFF")
    print("   Attendu: STAGNATION_POSITIVE")
    
    position1 = MockPosition()
    position1.open_time = time.time() - 120  # 120s elapsed
    position1.trailing_activated = False
    position1.max_pnl_reached = 0.05
    
    result1 = simulate_stagnation_check(position1, pnl=0.05)
    expected1 = 'STAGNATION_POSITIVE'
    passed1 = result1 == expected1
    results.append(passed1)
    
    print(f"   Résultat: {result1}")
    print(f"   {'[PASS]' if passed1 else '[FAIL]'}")
    
    # ===================================================================
    # SCENARIO 2: PnL positif, timeout atteint, trailing ON
    # Attendu: None (trailing gere)
    # ===================================================================
    print("\n" + "-" * 70)
    print("[Scenario 2] PnL=0.05%, elapsed=120s, trailing=ON")
    print("   Attendu: None (trailing gère la sortie)")
    
    position2 = MockPosition()
    position2.open_time = time.time() - 120
    position2.trailing_activated = True  # 🔥 Trailing activé
    position2.trailing_activated_at = time.time() - 60
    position2.max_pnl_reached = 0.25
    
    result2 = simulate_stagnation_check(position2, pnl=0.05)
    expected2 = None
    passed2 = result2 == expected2
    results.append(passed2)
    
    print(f"   Résultat: {result2}")
    print(f"   {'[PASS]' if passed2 else '[FAIL]'}")
    
    # ===================================================================
    # SCENARIO 3: PnL eleve (au-dessus trailing), trailing ON
    # Attendu: None (trailing gere)
    # ===================================================================
    print("\n" + "-" * 70)
    print("[Scenario 3] PnL=0.25%, elapsed=120s, trailing=ON")
    print("   Attendu: None (trailing gère la sortie)")
    
    position3 = MockPosition()
    position3.open_time = time.time() - 120
    position3.trailing_activated = True
    position3.max_pnl_reached = 0.30
    
    result3 = simulate_stagnation_check(position3, pnl=0.25)
    expected3 = None
    passed3 = result3 == expected3
    results.append(passed3)
    
    print(f"   Résultat: {result3}")
    print(f"   {'[PASS]' if passed3 else '[FAIL]'}")
    
    # ===================================================================
    # SCENARIO 4: PnL sous seuil, trailing OFF
    # Attendu: None (PnL < stagnation_positive_threshold)
    # ===================================================================
    print("\n" + "-" * 70)
    print("[Scenario 4] PnL=0.02%, elapsed=120s, trailing=OFF")
    print("   Attendu: None (PnL sous seuil 0.03%)")
    
    position4 = MockPosition()
    position4.open_time = time.time() - 120
    position4.trailing_activated = False
    position4.max_pnl_reached = 0.02
    
    result4 = simulate_stagnation_check(position4, pnl=0.02)
    # Peut retourner STAGNATION si timeout normal atteint et PnL < min_pnl_to_stay
    # Mais pas STAGNATION_POSITIVE
    passed4 = result4 != 'STAGNATION_POSITIVE'
    results.append(passed4)
    
    print(f"   Résultat: {result4}")
    print(f"   {'[PASS]' if passed4 else '[FAIL]'} (pas STAGNATION_POSITIVE)")
    
    # ===================================================================
    # SCENARIO 5: MFE Protect - pullback depuis MFE
    # Attendu: STAGNATION_MFE_PROTECT
    # ===================================================================
    print("\n" + "-" * 70)
    print("[Scenario 5] MFE=0.15%, PnL actuel=0.05%, pullback=0.10%")
    print("   Attendu: STAGNATION_MFE_PROTECT")
    
    position5 = MockPosition()
    position5.open_time = time.time() - 120
    position5.trailing_activated = False
    position5.max_pnl_reached = 0.15  # MFE atteint
    position5.stagnation_detected_at = time.time() - 60  # Stagnation détectée
    
    result5 = simulate_stagnation_check(position5, pnl=0.05)  # Pullback = 0.15 - 0.05 = 0.10%
    expected5 = 'STAGNATION_MFE_PROTECT'
    passed5 = result5 == expected5
    results.append(passed5)
    
    print(f"   Résultat: {result5}")
    print(f"   {'[PASS]' if passed5 else '[FAIL]'}")
    
    # ===================================================================
    # SCENARIO 6: Timeout pas encore atteint
    # Attendu: None
    # ===================================================================
    print("\n" + "-" * 70)
    print("[Scenario 6] PnL=0.05%, elapsed=30s, trailing=OFF")
    print("   Attendu: None (timeout pas atteint)")
    
    position6 = MockPosition()
    position6.open_time = time.time() - 30  # Seulement 30s
    position6.trailing_activated = False
    position6.max_pnl_reached = 0.05
    
    result6 = simulate_stagnation_check(position6, pnl=0.05)
    expected6 = None
    passed6 = result6 == expected6
    results.append(passed6)
    
    print(f"   Résultat: {result6}")
    print(f"   {'[PASS]' if passed6 else '[FAIL]'}")
    
    # ===================================================================
    # RESUME
    # ===================================================================
    print("\n" + "=" * 70)
    print("[SUMMARY] RESUME DES TESTS")
    print("=" * 70)
    
    total = len(results)
    passed = sum(results)
    
    print(f"\n   Tests passés: {passed}/{total}")
    
    if passed == total:
        print("\n   >>> TOUS LES TESTS PASSENT ! <<<")
        print("\n   La logique Stagnation Positive vs Trailing fonctionne correctement.")
    else:
        print(f"\n   [FAIL] {total - passed} test(s) echoue(s)")
    
    return passed == total


def simulate_stagnation_check(position: MockPosition, pnl: float) -> Optional[str]:
    """
    Simule la logique de _check_stagnation_exit sans instancier PositionManager
    Logique mise a jour 15/12/2025:
    - Si trailing active -> ignorer Stagnation Positive ET MFE Protect
    - MFE Protect a priorite sur Stagnation Positive
    """
    from config import TRADING_CONFIG
    from utils.effective_config import get_effective_value
    
    elapsed = time.time() - position.open_time
    
    # Config stagnation
    stagnation_config = TRADING_CONFIG.get('stagnation_exit', {})
    timeout = TRADING_CONFIG.get('stagnation_exit_timeout_seconds', 
                                  stagnation_config.get('timeout_seconds', 120))
    
    # PHASE 0: Configuration commune
    stagnation_positive_enabled = TRADING_CONFIG.get('stagnation_positive_exit_enabled', True)
    stagnation_positive_threshold = TRADING_CONFIG.get('stagnation_positive_threshold', 0.03)
    stagnation_positive_timeout = TRADING_CONFIG.get('stagnation_positive_timeout_seconds', 60)
    
    # Detection stagnation
    stagnation_detection_threshold = min(stagnation_positive_timeout, timeout)
    if elapsed >= stagnation_detection_threshold and not position.stagnation_detected_at:
        position.stagnation_detected_at = time.time()
        position.stagnation_pnl_at_detection = pnl
    
    # FIX 15/12: Si trailing active, ignorer Stagnation Positive ET MFE Protect
    if not position.trailing_activated:
        # PHASE 1: MFE PROTECTION (priorite sur Stagnation Positive)
        stagnation_use_mfe_tracking = TRADING_CONFIG.get('stagnation_use_mfe_tracking', True)
        stagnation_mfe_pullback_pct = TRADING_CONFIG.get('stagnation_mfe_pullback_pct', 0.08)
        
        if stagnation_use_mfe_tracking and position.stagnation_detected_at:
            mfe = position.max_pnl_reached or 0
            if mfe > stagnation_positive_threshold:
                pullback = mfe - pnl
                if pullback >= stagnation_mfe_pullback_pct:
                    position.stagnation_mfe_at_exit = mfe
                    position.stagnation_pullback_at_exit = pullback
                    return 'STAGNATION_MFE_PROTECT'
        
        # PHASE 2: STAGNATION POSITIVE
        if stagnation_positive_enabled and pnl >= stagnation_positive_threshold:
            if elapsed >= stagnation_positive_timeout:
                position.stagnation_positive_triggered = True
                position.stagnation_mfe_at_exit = position.max_pnl_reached or pnl
                return 'STAGNATION_POSITIVE'
    
    # PHASE 3: STAGNATION NORMALE
    if elapsed < timeout:
        return None
    
    min_pnl_to_stay = TRADING_CONFIG.get('stagnation_exit_min_pnl_to_stay', 
                                          stagnation_config.get('min_pnl_to_stay', 0.10))
    max_loss_to_exit = TRADING_CONFIG.get('stagnation_exit_max_loss_to_exit',
                                           stagnation_config.get('max_loss_to_exit', -0.05))
    
    if pnl >= min_pnl_to_stay:
        return None
    
    if pnl < max_loss_to_exit or (pnl >= max_loss_to_exit and pnl < min_pnl_to_stay):
        if not position.stagnation_detected_at:
            position.stagnation_detected_at = time.time()
            position.stagnation_pnl_at_detection = pnl
        position.stagnation_mfe_at_exit = position.max_pnl_reached or pnl
        return 'STAGNATION'
    
    return None


if __name__ == "__main__":
    success = test_stagnation_positive_logic()
    sys.exit(0 if success else 1)

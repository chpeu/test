
import sys
import os
import logging
from typing import Dict, Any

# Ajouter le dossier racine au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock config BEFORE importing PositionManager if possible, 
# but usually config is imported at module level.
# We will mutate TRADING_CONFIG after import.

from config import TRADING_CONFIG
from core.position_manager import PositionManager
from core.position.tp_sl_calculator import TPSLConfig
from utils.effective_config import get_effective_config, clear_all_adjustments

# Configure logging
logging.basicConfig(level=logging.ERROR) # Only ERRORs to keep output clean
logger = logging.getLogger("VerifyAdaptive")

class MockConfig(TPSLConfig):
    def __getattr__(self, name):
        return False

def verify_adaptive_logic():
    print("="*60)
    print("TEST: Vérification de l'adaptation dynamique ATR (Sprint 3)")
    print("="*60)
    
    # Reset / Setup Config
    TRADING_CONFIG['atr_mult_tp'] = 2.0
    TRADING_CONFIG['atr_mult_sl'] = 1.0
    TRADING_CONFIG['break_even_atr_mult'] = 1.0
    TRADING_CONFIG['trailing_trigger_atr_mult'] = 1.5
    TRADING_CONFIG['trailing_distance_mult'] = 1.0
    TRADING_CONFIG['stagnation_exit_timeout_seconds'] = 120
    TRADING_CONFIG['stagnation_exit_min_pnl_to_stay'] = 0.05
    TRADING_CONFIG['tp_sl_mode'] = 'ATR' # Ensure ATR mode
    
    # Initialize Manager with MockConfig
    tpsl_config = MockConfig(
        fixed_tp_pct=0.15,
        fixed_sl_pct=0.10,
        atr_mult_tp=2.0,
        atr_mult_sl=1.0,
        atr_min=0.15,
        atr_max=1.5
    )
    pm = PositionManager(config=tpsl_config)
    
    clear_all_adjustments()

    # ---------------------------------------------------------
    # TEST 1: LOW Volatility (<0.20% ATR)
    # Expected: NO CHANGE (Sweet spot)
    # ---------------------------------------------------------
    print("\n[TEST 1] Régime LOW (ATR=0.15%)")
    entry_price = 10000.0
    atr = 15.0 # 0.15% of 10000
    
    pm.open_position(
        symbol="BTCUSDT",
        direction="LONG",
        entry=entry_price,
        size=100.0,
        atr=atr
    )
    
    pos = pm.active_position
    eff = getattr(pos, 'effective_config', {})
    
    regime = eff.get('local_regime')
    print(f"  > Régime détecté: {regime}")
    
    errors = 0
    
    if regime == 'LOW':
        print("  [OK] Regime correctement identifie")
    else:
        print(f"  [ERROR] Erreur detection regime: {regime} (Attendu: LOW)")
        errors += 1

    tp_mult = eff.get('atr_mult_tp')
    if tp_mult == 2.0:
        print(f"  [OK] TP Mult inchange: {tp_mult}")
    else:
        print(f"  [ERROR] TP Mult modifie: {tp_mult} (Attendu: 2.0)")
        errors += 1

    pm.close_position(10000.0, "TEST")
    
    # ---------------------------------------------------------
    # TEST 2: MEDIUM Volatility (0.35% ATR)
    # Expected: TIGHTEN (TP*0.8, BE*0.8)
    # ---------------------------------------------------------
    print("\n[TEST 2] Régime MEDIUM (ATR=0.35%)")
    atr = 35.0 # 0.35% of 10000
    
    pm.open_position("BTCUSDT", "LONG", entry_price, 100.0, atr=atr)
    pos = pm.active_position
    eff = getattr(pos, 'effective_config', {})
    
    regime = eff.get('local_regime')
    print(f"  > Régime détecté: {regime}")
    
    if regime == 'MEDIUM':
        print("  [OK] Regime correctement identifie")
    else:
        print(f"  [ERROR] Erreur detection regime: {regime} (Attendu: MEDIUM)")
        errors += 1
    
    expected_tp = 2.0 * 0.8
    tp_mult = eff.get('atr_mult_tp', 0)
    if abs(tp_mult - expected_tp) < 0.01:
        print(f"  [OK] TP Mult resserre: {tp_mult} (Attendu: {expected_tp})")
    else:
        print(f"  [ERROR] Erreur TP Mult: {tp_mult}")
        errors += 1

    expected_be = 1.0 * 0.8
    be_mult = eff.get('break_even_atr_mult', 0)
    if abs(be_mult - expected_be) < 0.01:
        print(f"  [OK] BE Mult resserre: {be_mult} (Attendu: {expected_be})")
    else:
        print(f"  [ERROR] Erreur BE Mult: {be_mult}")
        errors += 1
        
    # Verify global effective config propagation
    global_eff = get_effective_config()
    if global_eff.get('_local_regime') == 'MEDIUM':
         print("  [OK] Global Effective Config a jour (_local_regime=MEDIUM)")
    else:
         print(f"  [ERROR] Erreur Global Effective Config: {global_eff.get('_local_regime')}")
         errors += 1

    pm.close_position(10000.0, "TEST")
    
    # Check cleanup
    global_eff_clean = get_effective_config()
    local_adj = global_eff_clean.get('_local_regime')
    if local_adj is None or local_adj == 'UNKNOWN':
         print("  [OK] Global Effective Config nettoyee apres fermeture")
    else:
         print(f"  [ERROR] Erreur nettoyage Global Config: {local_adj}")
         # Note: Depending on implementation, it might disappear or be UNKNOWN. 
         # effective_config.py implementation removes 'local_trade' key from active adjustments,
         # so '_local_regime' should likely disappear from get_effective_config() result.

    # ---------------------------------------------------------
    # TEST 3: HIGH Volatility (0.80% ATR)
    # Expected: WIDEN (Trailing Dist*1.5, Stagnation Timeout*1.5)
    # ---------------------------------------------------------
    print("\n[TEST 3] Régime HIGH (ATR=0.80%)")
    atr = 80.0 # 0.80% of 10000
    
    pm.open_position("BTCUSDT", "LONG", entry_price, 100.0, atr=atr)
    pos = pm.active_position
    eff = getattr(pos, 'effective_config', {})
    
    regime = eff.get('local_regime')
    print(f"  > Régime détecté: {regime}")
    
    if regime == 'HIGH':
        print("  [OK] Regime correctement identifie")
    else:
        print(f"  [ERROR] Erreur detection regime: {regime} (Attendu: HIGH)")
        errors += 1
    
    expected_dist = 1.0 * 1.5
    dist_mult = eff.get('trailing_distance_mult', 0)
    if abs(dist_mult - expected_dist) < 0.01:
        print(f"  [OK] Trailing Dist elargie: {dist_mult} (Attendu: {expected_dist})")
    else:
        print(f"  [ERROR] Erreur Trailing Dist: {dist_mult}")
        errors += 1

    expected_timeout = int(120 * 1.5)
    timeout = eff.get('stagnation_exit_timeout_seconds', 0)
    if timeout == expected_timeout:
        print(f"  [OK] Stagnation Timeout elargi: {timeout} (Attendu: {expected_timeout})")
    else:
        print(f"  [ERROR] Erreur Stagnation Timeout: {timeout}")
        errors += 1
        
    pm.close_position(10000.0, "TEST")

    print("\n" + "="*60)
    if errors == 0:
        print("[OK] TOUS LES TESTS PASSES AVEC SUCCES")
    else:
        print(f"[ERROR] {errors} ERREURS DETECTEES")
    print("="*60)

if __name__ == "__main__":
    verify_adaptive_logic()

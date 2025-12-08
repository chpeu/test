#!/usr/bin/env python3
"""
Script de vérification des paramètres dynamiques par régime
Vérifie que les valeurs optimales (ATR max, Volume, RSI mode, Timeout) sont bien appliquées.
"""
import sys
import os
import logging
import io

# Force UTF-8 for stdout/stderr
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ajouter la racine au path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.effective_config import get_effective_value, set_regime_adjustments, clear_all_adjustments
from core.market_regime_selector import DEFAULT_REGIME_CONFIGS

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def verify_regime(regime_name: str):
    """Vérifie les valeurs effectives pour un régime donné"""
    config = DEFAULT_REGIME_CONFIGS.get(regime_name)
    if not config:
        print(f"❌ Régime {regime_name} non trouvé dans DEFAULT_REGIME_CONFIGS")
        return

    print(f"\n🔍 Test Régime: {regime_name}")
    
    # Simuler l'activation du régime
    adjustments = {
        "min_score_required": config.min_score_required,
        "atr_mult_sl": config.atr_mult_sl,
        "atr_mult_tp": config.atr_mult_tp,
        "break_even_atr_mult": config.break_even_atr_mult,
        "trailing_trigger_atr_mult": config.trailing_trigger_atr_mult,
        "position_timeout": config.max_position_time,
        "optimal_atr_min_1m": config.optimal_atr_min,
        "optimal_atr_max_1m": config.optimal_atr_max,
        "volume_multiplier": config.volume_multiplier,
        "rsi_filter_mode": config.rsi_filter_mode
    }
    
    set_regime_adjustments(adjustments)
    
    # Vérifier les valeurs
    errors = []
    
    # 1. ATR Max
    eff_atr_max = get_effective_value("optimal_atr_max_1m")
    if eff_atr_max != config.optimal_atr_max:
        errors.append(f"ATR Max: Attendu {config.optimal_atr_max}, Reçu {eff_atr_max}")
    else:
        print(f"✅ ATR Max: {eff_atr_max}%")

    # 2. Volume Multiplier
    eff_vol_mult = get_effective_value("volume_multiplier")
    if eff_vol_mult != config.volume_multiplier:
        errors.append(f"Vol Mult: Attendu {config.volume_multiplier}, Reçu {eff_vol_mult}")
    else:
        print(f"✅ Vol Mult: {eff_vol_mult}x")

    # 3. RSI Mode
    eff_rsi_mode = get_effective_value("rsi_filter_mode")
    if eff_rsi_mode != config.rsi_filter_mode:
        errors.append(f"RSI Mode: Attendu {config.rsi_filter_mode}, Reçu {eff_rsi_mode}")
    else:
        print(f"✅ RSI Mode: {eff_rsi_mode}")

    # 4. Position Timeout
    eff_timeout = get_effective_value("position_timeout")
    if eff_timeout != config.max_position_time:
        errors.append(f"Timeout: Attendu {config.max_position_time}, Reçu {eff_timeout}")
    else:
        print(f"✅ Timeout: {eff_timeout}s")

    # 5. SL Multiplier
    eff_sl = get_effective_value("atr_mult_sl")
    if eff_sl != config.atr_mult_sl:
        errors.append(f"SL Mult: Attendu {config.atr_mult_sl}, Reçu {eff_sl}")
    else:
        print(f"✅ SL Mult: {eff_sl}x")

    # 6. TP Multiplier
    eff_tp = get_effective_value("atr_mult_tp")
    if eff_tp != config.atr_mult_tp:
        errors.append(f"TP Mult: Attendu {config.atr_mult_tp}, Reçu {eff_tp}")
    else:
        print(f"✅ TP Mult: {eff_tp}x")

    if errors:
        print(f"❌ ECHEC {regime_name}:")
        for e in errors:
            print(f"  - {e}")
    else:
        print(f"✨ {regime_name} OK")

def main():
    print("🚀 Démarrage vérification paramètres régimes...")
    
    try:
        verify_regime("CALME")
        verify_regime("NORMAL")
        verify_regime("VOLATILE")
        verify_regime("CHOPPY")
        
        clear_all_adjustments()
        print("\n✅ Vérification terminée.")
        
    except Exception as e:
        print(f"❌ Erreur script: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

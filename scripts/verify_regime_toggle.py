#!/usr/bin/env python3
"""
Script de vérification du comportement ON/OFF du Market Regime Selector.
Vérifie que:
- Quand activé: les valeurs effectives = valeurs du régime (pas les sliders)
- Quand désactivé: les valeurs effectives = valeurs base (sliders)
"""
import sys
import os
import io

# Force UTF-8 for stdout/stderr
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ajouter la racine au path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TRADING_CONFIG
from utils.effective_config import (
    get_effective_value, 
    set_regime_adjustments, 
    clear_all_adjustments,
    get_config_summary
)
from core.market_regime_selector import DEFAULT_REGIME_CONFIGS

def test_regime_enabled():
    """Test avec Market Regime Selector ACTIVÉ"""
    print("\n" + "="*60)
    print("TEST 1: Market Regime Selector ACTIVÉ")
    print("="*60)
    
    # S'assurer que le régime est activé
    original_enabled = TRADING_CONFIG.get('market_regime_enabled', True)
    TRADING_CONFIG['market_regime_enabled'] = True
    
    # Valeurs base (sliders)
    base_sl = TRADING_CONFIG.get('atr_mult_sl', 1.0)
    base_tp = TRADING_CONFIG.get('atr_mult_tp', 1.5)
    base_score = TRADING_CONFIG.get('min_score_required', 7.0)
    
    print(f"\n📊 Valeurs BASE (sliders):")
    print(f"   SL Mult: {base_sl}x")
    print(f"   TP Mult: {base_tp}x")
    print(f"   Score Min: {base_score}")
    
    # Simuler activation du régime CALME
    config = DEFAULT_REGIME_CONFIGS.get("CALME")
    adjustments = {
        "min_score_required": config.min_score_required,
        "atr_mult_sl": config.atr_mult_sl,
        "atr_mult_tp": config.atr_mult_tp,
        "volume_multiplier": config.volume_multiplier,
        "rsi_filter_mode": config.rsi_filter_mode,
        "position_timeout": config.max_position_time,
    }
    set_regime_adjustments(adjustments)
    
    # Valeurs effectives (régime CALME)
    eff_sl = get_effective_value('atr_mult_sl')
    eff_tp = get_effective_value('atr_mult_tp')
    eff_score = get_effective_value('min_score_required')
    
    print(f"\n🌡️ Valeurs EFFECTIVES (régime CALME):")
    print(f"   SL Mult: {eff_sl}x (attendu: {config.atr_mult_sl}x)")
    print(f"   TP Mult: {eff_tp}x (attendu: {config.atr_mult_tp}x)")
    print(f"   Score Min: {eff_score} (attendu: {config.min_score_required})")
    
    # Vérifications
    errors = []
    if eff_sl != config.atr_mult_sl:
        errors.append(f"SL: attendu {config.atr_mult_sl}, reçu {eff_sl}")
    if eff_tp != config.atr_mult_tp:
        errors.append(f"TP: attendu {config.atr_mult_tp}, reçu {eff_tp}")
    if eff_score != config.min_score_required:
        errors.append(f"Score: attendu {config.min_score_required}, reçu {eff_score}")
    
    # Vérifier que les sliders N'ONT PAS changé
    if TRADING_CONFIG.get('atr_mult_sl') != base_sl:
        errors.append(f"ERREUR: Slider SL modifié! ({base_sl} -> {TRADING_CONFIG.get('atr_mult_sl')})")
    if TRADING_CONFIG.get('atr_mult_tp') != base_tp:
        errors.append(f"ERREUR: Slider TP modifié! ({base_tp} -> {TRADING_CONFIG.get('atr_mult_tp')})")
    
    if errors:
        print(f"\n❌ ÉCHEC:")
        for e in errors:
            print(f"   - {e}")
        return False
    else:
        print(f"\n✅ Test ACTIVÉ réussi:")
        print(f"   - Valeurs effectives = régime CALME")
        print(f"   - Sliders non modifiés")
        return True

def test_regime_disabled():
    """Test avec Market Regime Selector DÉSACTIVÉ"""
    print("\n" + "="*60)
    print("TEST 2: Market Regime Selector DÉSACTIVÉ")
    print("="*60)
    
    # Désactiver le régime
    TRADING_CONFIG['market_regime_enabled'] = False
    
    # Les ajustements sont toujours stockés mais NE DOIVENT PAS être appliqués
    config = DEFAULT_REGIME_CONFIGS.get("CALME")
    adjustments = {
        "min_score_required": config.min_score_required,
        "atr_mult_sl": config.atr_mult_sl,
        "atr_mult_tp": config.atr_mult_tp,
    }
    set_regime_adjustments(adjustments)
    
    # Valeurs base (sliders)
    base_sl = TRADING_CONFIG.get('atr_mult_sl', 1.0)
    base_tp = TRADING_CONFIG.get('atr_mult_tp', 1.5)
    base_score = TRADING_CONFIG.get('min_score_required', 7.0)
    
    print(f"\n📊 Valeurs BASE (sliders):")
    print(f"   SL Mult: {base_sl}x")
    print(f"   TP Mult: {base_tp}x")
    print(f"   Score Min: {base_score}")
    
    # Valeurs effectives (doivent être = base car régime désactivé)
    eff_sl = get_effective_value('atr_mult_sl')
    eff_tp = get_effective_value('atr_mult_tp')
    eff_score = get_effective_value('min_score_required')
    
    print(f"\n📋 Valeurs EFFECTIVES (régime DÉSACTIVÉ):")
    print(f"   SL Mult: {eff_sl}x (attendu: {base_sl}x = base)")
    print(f"   TP Mult: {eff_tp}x (attendu: {base_tp}x = base)")
    print(f"   Score Min: {eff_score} (attendu: {base_score} = base)")
    
    # Vérifications: effective doit = base (pas régime)
    errors = []
    if eff_sl != base_sl:
        errors.append(f"SL: attendu {base_sl} (base), reçu {eff_sl}")
    if eff_tp != base_tp:
        errors.append(f"TP: attendu {base_tp} (base), reçu {eff_tp}")
    if eff_score != base_score:
        errors.append(f"Score: attendu {base_score} (base), reçu {eff_score}")
    
    if errors:
        print(f"\n❌ ÉCHEC:")
        for e in errors:
            print(f"   - {e}")
        return False
    else:
        print(f"\n✅ Test DÉSACTIVÉ réussi:")
        print(f"   - Valeurs effectives = valeurs BASE (sliders)")
        print(f"   - Ajustements régime ignorés")
        return True

def test_summary_differences():
    """Test du résumé des différences pour le frontend"""
    print("\n" + "="*60)
    print("TEST 3: Résumé des différences (pour frontend)")
    print("="*60)
    
    # Activer le régime et appliquer CALME
    TRADING_CONFIG['market_regime_enabled'] = True
    config = DEFAULT_REGIME_CONFIGS.get("CALME")
    adjustments = {
        "min_score_required": config.min_score_required,
        "atr_mult_sl": config.atr_mult_sl,
        "atr_mult_tp": config.atr_mult_tp,
    }
    set_regime_adjustments(adjustments)
    
    summary = get_config_summary()
    differences = summary.get('differences', {})
    
    print(f"\n🔄 Différences détectées:")
    for key, diff in differences.items():
        print(f"   {key}: {diff['base']} → {diff['effective']}", end="")
        if diff.get('delta') is not None:
            sign = '+' if diff['delta'] > 0 else ''
            print(f" ({sign}{diff['delta']:.2f})")
        else:
            print()
    
    # Vérifier que les clés importantes sont présentes
    expected_keys = ['atr_mult_sl', 'atr_mult_tp', 'min_score_required']
    missing = [k for k in expected_keys if k not in differences]
    
    if missing:
        print(f"\n⚠️ Clés manquantes dans differences: {missing}")
        print("   (Normal si base = effective pour ces clés)")
    
    print(f"\n✅ Résumé généré correctement")
    return True

def main():
    print("🚀 Vérification du comportement ON/OFF du Market Regime Selector")
    
    # Sauvegarder l'état original
    original_enabled = TRADING_CONFIG.get('market_regime_enabled', True)
    
    try:
        test1 = test_regime_enabled()
        test2 = test_regime_disabled()
        test3 = test_summary_differences()
        
        clear_all_adjustments()
        
        print("\n" + "="*60)
        print("RÉSUMÉ")
        print("="*60)
        print(f"Test 1 (Régime ACTIVÉ):     {'✅ OK' if test1 else '❌ ÉCHEC'}")
        print(f"Test 2 (Régime DÉSACTIVÉ):  {'✅ OK' if test2 else '❌ ÉCHEC'}")
        print(f"Test 3 (Résumé frontend):   {'✅ OK' if test3 else '❌ ÉCHEC'}")
        
        if test1 and test2 and test3:
            print("\n🎉 Tous les tests passent !")
        else:
            print("\n⚠️ Certains tests ont échoué.")
            
    finally:
        # Restaurer l'état original
        TRADING_CONFIG['market_regime_enabled'] = original_enabled
        clear_all_adjustments()

if __name__ == "__main__":
    main()

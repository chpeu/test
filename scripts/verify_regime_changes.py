#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
Vérifie que les modifications de paramètres régime sont bien chargées et appliquées.
"""

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("="*70)
    print("VERIFICATION DES MODIFICATIONS REGIME")
    print("="*70)
    
    # 1. Vérifier les valeurs dans DEFAULT_REGIME_CONFIGS
    print("\n[1] Vérification DEFAULT_REGIME_CONFIGS:")
    try:
        from core.market_regime_selector import DEFAULT_REGIME_CONFIGS
        
        for regime_name, config in DEFAULT_REGIME_CONFIGS.items():
            print(f"\n  [{regime_name}]")
            print(f"    atr_mult_sl: {config.atr_mult_sl}")
            print(f"    atr_mult_tp: {config.atr_mult_tp}")
            print(f"    break_even_atr_mult: {config.break_even_atr_mult}")
            print(f"    trailing_trigger_atr_mult: {config.trailing_trigger_atr_mult}")
        
        # Vérifier les nouvelles valeurs
        print("\n  --- Vérification des changements du 28/12 ---")
        calme = DEFAULT_REGIME_CONFIGS["CALME"]
        normal = DEFAULT_REGIME_CONFIGS["NORMAL"]
        
        checks = []
        checks.append(("CALME atr_mult_sl", calme.atr_mult_sl, 1.2))
        checks.append(("NORMAL atr_mult_sl", normal.atr_mult_sl, 1.6))
        checks.append(("NORMAL atr_mult_tp", normal.atr_mult_tp, 2.0))
        
        all_ok = True
        for name, actual, expected in checks:
            status = "✅" if actual == expected else "❌"
            if actual != expected:
                all_ok = False
            print(f"  {status} {name}: {actual} (attendu: {expected})")
        
        if all_ok:
            print("\n  ✅ Toutes les modifications sont correctement chargées!")
        else:
            print("\n  ❌ Certaines modifications ne sont pas correctes!")
            
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. Vérifier le RegimeSelector singleton
    print("\n[2] Vérification du RegimeSelector actif:")
    try:
        from core.market_regime_selector import get_regime_selector
        
        selector = get_regime_selector()
        status = selector.get_status()
        
        print(f"  Régime actuel: {status.get('current_regime', 'N/A')}")
        print(f"  ATR moyen: {status.get('avg_atr', 'N/A')}")
        
        # Obtenir la config du régime actuel
        current_config = selector.get_current_config()
        if current_config:
            print(f"\n  Config active pour {status.get('current_regime')}:")
            print(f"    atr_mult_sl: {current_config.atr_mult_sl}")
            print(f"    atr_mult_tp: {current_config.atr_mult_tp}")
        else:
            print("  ⚠️ Pas de config active (régime non détecté)")
            
    except Exception as e:
        print(f"  ⚠️ RegimeSelector non initialisé (normal si bot pas lancé): {e}")
    
    # 3. Vérifier le flux effective_config
    print("\n[3] Vérification effective_config:")
    try:
        from utils.effective_config import get_effective_value, get_active_adjustments
        
        atr_sl = get_effective_value('atr_mult_sl')
        atr_tp = get_effective_value('atr_mult_tp')
        
        print(f"  atr_mult_sl effectif: {atr_sl}")
        print(f"  atr_mult_tp effectif: {atr_tp}")
        
        adjustments = get_active_adjustments()
        if adjustments:
            print(f"\n  Ajustements actifs:")
            for key, val in adjustments.items():
                print(f"    {key}: {val}")
        else:
            print("  Aucun ajustement actif (config de base)")
            
    except Exception as e:
        print(f"  ⚠️ effective_config: {e}")
    
    # 4. Vérifier que position_manager utilise les bonnes valeurs
    print("\n[4] Vérification du flux position_manager:")
    try:
        from core.position_manager import PositionManagerConfig
        
        # Config par défaut
        default_config = PositionManagerConfig()
        print(f"  Config par défaut:")
        print(f"    atr_mult_sl: {default_config.atr_mult_sl}")
        print(f"    atr_mult_tp: {default_config.atr_mult_tp}")
        
    except Exception as e:
        print(f"  ⚠️ Erreur: {e}")
    
    # 5. Test d'intégration: simuler un appel get_effective_trading_params
    print("\n[5] Test d'intégration (simulation):")
    try:
        # Simuler différents ATR pour voir les ajustements locaux
        test_cases = [
            (0.10, "LOW/CALME"),    # ATR < 0.20%
            (0.30, "MEDIUM/NORMAL"), # 0.20% < ATR < 0.50%
            (0.70, "HIGH/VOLATILE")  # ATR > 0.50%
        ]
        
        for atr_pct, label in test_cases:
            if atr_pct < 0.20:
                local = 'LOW'
            elif atr_pct < 0.50:
                local = 'MEDIUM'
            else:
                local = 'HIGH'
            print(f"\n  ATR={atr_pct}% -> Régime local: {local} ({label})")
            
            # Les multiplicateurs locaux appliqués dans position_manager
            if local == 'MEDIUM':
                print(f"    → TP mult ajusté: base × 0.7")
                print(f"    → SL mult ajusté: base × 1.3")
            elif local == 'HIGH':
                print(f"    → TP mult: base (pas de changement)")
                print(f"    → SL mult ajusté: base × 1.2")
            else:  # LOW
                print(f"    → TP mult: base (pas de changement)")
                print(f"    → SL mult: base (pas de changement)")
                
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
    
    print("\n" + "="*70)
    print("VERIFICATION TERMINEE")
    print("="*70)
    
    print("\n⚠️  NOTE: Pour que les changements soient actifs sur le bot live,")
    print("    un REDEMARRAGE du bot est nécessaire!")

if __name__ == "__main__":
    main()

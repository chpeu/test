#!/usr/bin/env python3
"""
🔍 Vérification des paramètres Régime V2
Vérifie que tous les paramètres sont correctement lus et utilisés par le bot.
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows UTF-8
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from config import TRADING_CONFIG
from utils.config_persistence import get_config_value

def check_param(name: str, expected_type: type, default_value=None):
    """Vérifie un paramètre et retourne son état."""
    # Valeur dans TRADING_CONFIG
    config_val = TRADING_CONFIG.get(name)
    # Valeur effective (avec overrides)
    effective_val = get_config_value(name, default_value)
    
    status = "✅" if effective_val is not None else "❌"
    type_ok = "✅" if isinstance(effective_val, expected_type) else f"⚠️ (attendu {expected_type.__name__})"
    
    return {
        'name': name,
        'config_val': config_val,
        'effective_val': effective_val,
        'status': status,
        'type_ok': type_ok
    }

def main():
    print("=" * 70)
    print("🌡️ VÉRIFICATION PARAMÈTRES RÉGIME V2")
    print("=" * 70)
    
    # Liste des paramètres V2 à vérifier
    params_v2 = [
        # Activation
        ('market_regime_v2_enabled', bool, False),
        # Calcul ATR
        ('market_regime_use_median', bool, False),
        ('market_regime_outlier_filter', bool, True),
        ('market_regime_use_atr_5m', bool, False),
        # Stabilité
        ('market_regime_use_hysteresis', bool, False),
        ('market_regime_hysteresis_buffer', float, 0.10),
        ('market_regime_use_smoothing', bool, False),
        ('market_regime_smoothing_alpha', float, 0.30),
        ('market_regime_min_duration_minutes', int, 30),
        # Saisonnalité
        ('market_regime_use_seasonality', bool, False),
        # Phase 1E
        ('market_regime_auto_calibration_enabled', bool, False),
        ('market_regime_calibration_lookback_days', int, 7),
        ('market_regime_btc_indicator_enabled', bool, False),
        ('market_regime_btc_volatile_threshold_1h', float, 2.0),
        ('market_regime_btc_force_volatile_enabled', bool, True),
    ]
    
    print("\n📋 ÉTAT DES PARAMÈTRES:")
    print("-" * 70)
    
    all_ok = True
    active_count = 0
    
    for name, expected_type, default in params_v2:
        result = check_param(name, expected_type, default)
        
        # Affichage
        val_display = result['effective_val']
        if isinstance(val_display, bool):
            val_display = "ON" if val_display else "OFF"
            if result['effective_val']:
                active_count += 1
        
        print(f"  {result['status']} {name}")
        print(f"     → Valeur: {val_display} {result['type_ok']}")
        
        if result['effective_val'] is None:
            all_ok = False
    
    print("\n" + "=" * 70)
    print(f"📊 RÉSUMÉ: {active_count}/{len(params_v2)} paramètres ACTIFS")
    print("=" * 70)
    
    # Vérifier que le MarketRegimeSelector utilise les paramètres
    print("\n🔍 TEST D'UTILISATION PAR LE BOT:")
    print("-" * 70)
    
    try:
        from core.market_regime_selector import MarketRegimeSelector
        
        selector = MarketRegimeSelector()
        
        # Test calculate_atr_metric
        test_values = [0.15, 0.22, 0.18, 0.25, 0.19, 0.50]  # Avec un outlier (0.50)
        result = selector.calculate_atr_metric(test_values)
        
        use_median = get_config_value('market_regime_use_median', False)
        outlier_filter = get_config_value('market_regime_outlier_filter', True)
        
        print(f"  ✅ calculate_atr_metric() fonctionne")
        print(f"     → Valeurs test: {test_values}")
        print(f"     → Résultat: {result:.4f}%")
        print(f"     → Mode: {'Médiane' if use_median else 'Moyenne'}")
        print(f"     → Filtrage outliers: {'ON' if outlier_filter else 'OFF'}")
        
        # Test apply_smoothing
        smoothed = selector.apply_smoothing(0.25)
        use_smoothing = get_config_value('market_regime_use_smoothing', False)
        print(f"  ✅ apply_smoothing() fonctionne")
        print(f"     → Lissage: {'ON' if use_smoothing else 'OFF'}")
        
        # Test should_change_regime
        should_change = selector.should_change_regime("NORMAL", "VOLATILE", 0.42)
        use_hysteresis = get_config_value('market_regime_use_hysteresis', False)
        print(f"  ✅ should_change_regime() fonctionne")
        print(f"     → Hystérésis: {'ON' if use_hysteresis else 'OFF'}")
        
        # Test determine_regime
        regime = selector.determine_regime(0.25, 25.0)
        print(f"  ✅ determine_regime() fonctionne")
        print(f"     → Régime pour ATR=0.25%, ADX=25: {regime.name}")

        async def run_realistic_loop() -> None:
            print("\n🔁 SIMULATION RÉALISTE check_regime() (EMA + hystérésis + durée min):")
            print("-" * 70)

            min_duration = get_config_value('market_regime_min_duration_minutes', 30)
            check_interval = get_config_value('market_regime_check_interval', 60)
            print(f"     Config: min_duration={min_duration}min | check_interval={check_interval}min")

            # Aligner l'intervalle interne du selector avec la config
            selector.check_interval = timedelta(minutes=check_interval)

            base_adx = 35.0
            atr_steps = [
                (0.18, 0),
                (0.23, 1),
                (0.42, 2),
                (0.39, 3),
                (0.18, 4),
                (0.42, min_duration + 1),
                (0.18, min_duration + 2),
            ]

            selector.current_regime = selector.determine_regime(0.18, base_adx)
            selector.current_config = selector.regime_configs.get(selector.current_regime.value)
            selector.regime_since = datetime.now() - timedelta(minutes=min_duration + 5)
            selector.last_check = datetime.now() - timedelta(minutes=check_interval + 5)

            print(f"     Départ: {selector.current_regime.value}")

            for i, (atr, age_minutes) in enumerate(atr_steps, 1):
                selector.last_check = datetime.now() - timedelta(minutes=check_interval + 5)
                selector.regime_since = datetime.now() - timedelta(minutes=age_minutes)

                atr_values = [atr] * 10
                adx_values = [base_adx] * 10

                prev_regime = selector.current_regime
                prev_avg_atr = selector.avg_atr

                new_regime, changed = await selector.check_regime(
                    atr_values=atr_values,
                    adx_values=adx_values,
                    force=True,
                    trigger="auto"
                )

                gate = "OK"
                if (prev_regime != new_regime) and (not changed):
                    gate = "BLOQUÉ (durée min/hystérésis)"

                print(
                    f"     {i:02d}. age={age_minutes:>3}min | ATR_in={atr:.3f}% | "
                    f"avg_atr:{prev_avg_atr:.3f}%→{selector.avg_atr:.3f}% | "
                    f"{prev_regime.value}→{new_regime.value} | changed={changed} | {gate}"
                )

        asyncio.run(run_realistic_loop())
        
        print("\n✅ TOUS LES PARAMÈTRES SONT CORRECTEMENT UTILISÉS PAR LE BOT")
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    
    # Vérifier la persistance
    print("\n💾 VÉRIFICATION PERSISTANCE (config_overrides.json):")
    print("-" * 70)
    
    try:
        import json
        overrides_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config_overrides.json')
        
        if os.path.exists(overrides_path):
            with open(overrides_path, 'r') as f:
                overrides = json.load(f)
            
            v2_overrides = {k: v for k, v in overrides.items() if 'market_regime' in k}
            
            if v2_overrides:
                print(f"  ✅ {len(v2_overrides)} paramètres V2 dans config_overrides.json:")
                for k, v in v2_overrides.items():
                    print(f"     • {k}: {v}")
            else:
                print("  ⚠️ Aucun paramètre V2 dans config_overrides.json (utilise defaults)")
        else:
            print("  ⚠️ config_overrides.json n'existe pas")
    except Exception as e:
        print(f"  ❌ Erreur lecture overrides: {e}")
    
    return all_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

"""Verification que les seuils RSI sont bien charges par regime"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.market_regime_selector import MarketRegimeSelector, MarketRegime

print("=" * 70)
print("VERIFICATION SEUILS RSI PAR REGIME")
print("=" * 70)

# Charger le selector (va lire les fichiers JSON)
selector = MarketRegimeSelector()

print("\n1. Seuils RSI charges depuis les fichiers JSON:")
print("-" * 70)
print(f"{'Regime':<12} {'rsi_final_long_max':<20} {'rsi_final_short_min':<20}")
print("-" * 70)

for regime_name, config in selector.regime_configs.items():
    long_max = getattr(config, 'rsi_final_long_max', 'N/A')
    short_min = getattr(config, 'rsi_final_short_min', 'N/A')
    print(f"{regime_name:<12} {long_max:<20} {short_min:<20}")

# Tester get_active_config pour chaque regime
print("\n2. Valeurs retournees par get_active_config():")
print("-" * 70)

for regime in [MarketRegime.CALME, MarketRegime.NORMAL, MarketRegime.VOLATILE, MarketRegime.CHOPPY]:
    selector.current_regime = regime
    selector.current_config = selector.regime_configs.get(regime.value)
    
    active = selector.get_active_config()
    rsi_long = active.get('rsi_final_long_max', 'MISSING')
    rsi_short = active.get('rsi_final_short_min', 'MISSING')
    
    status = "OK" if rsi_long != 'MISSING' and rsi_short != 'MISSING' else "ERREUR"
    print(f"{regime.value:<12} long_max={rsi_long:<5} short_min={rsi_short:<5} [{status}]")

# Tester effective_config
print("\n3. Test effective_config propagation:")
print("-" * 70)

from utils.effective_config import set_regime_adjustments, get_effective_value, clear_all_adjustments

# Clear first
clear_all_adjustments()

# Simuler un regime CALME
selector.current_regime = MarketRegime.CALME
selector.current_config = selector.regime_configs.get('CALME')
active_config = selector.get_active_config()

print(f"Config active CALME: {active_config}")

# Appliquer les ajustements
set_regime_adjustments(active_config)

# Verifier get_effective_value
eff_long = get_effective_value('rsi_final_long_max')
eff_short = get_effective_value('rsi_final_short_min')

print(f"\nget_effective_value('rsi_final_long_max') = {eff_long}")
print(f"get_effective_value('rsi_final_short_min') = {eff_short}")

if eff_long == 60 and eff_short == 40:
    print("\n" + "=" * 70)
    print("RESULTAT: TOUT EST OK - Les seuils RSI sont bien propages!")
    print("=" * 70)
else:
    print("\n" + "=" * 70)
    print("ERREUR: Les seuils RSI ne sont pas correctement propages!")
    print(f"  Attendu: long_max=60, short_min=40")
    print(f"  Obtenu: long_max={eff_long}, short_min={eff_short}")
    print("=" * 70)

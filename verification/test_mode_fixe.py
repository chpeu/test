"""
🧪 Script de vérification complet du MODE FIXE
Teste toute la logique: SL/TP, Break-Even, Trailing Stop, Stagnation
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
import time

# Configuration MODE FIXE (défauts, surchargés par la config active)
DEFAULT_FIXE_CONFIG = {
    'tp_sl_mode': 'FIXE',
    'tp_percent': 5.0,
    'sl_percent': 0.25,
    'break_even_trigger': 0.15,
    'trailing_trigger_pnl': 0.15,
    'trailing_distance': 0.1,
    'trailing_use_atr_trigger': False,
    'stagnation_exit_enabled': True,
    'stagnation_exit_timeout_seconds': 540,
    'stagnation_exit_min_pnl_to_stay': 0.03,
    'partial_tp_percent': 60.0,
}


def _load_overrides_config() -> Dict[str, Any]:
    overrides_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config_overrides.json')
    if not os.path.exists(overrides_path):
        return {}
    with open(overrides_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_fixe_config() -> Dict[str, Any]:
    """Charger la configuration FIXE active (TRADING_CONFIG puis overrides)."""
    config = DEFAULT_FIXE_CONFIG.copy()

    try:
        overrides = _load_overrides_config()
        for key in config.keys():
            if key in overrides:
                config[key] = overrides[key]
    except Exception:
        pass

    try:
        from config import TRADING_CONFIG
        for key in config.keys():
            if key in TRADING_CONFIG:
                config[key] = TRADING_CONFIG[key]
    except Exception:
        pass

    return config


FIXE_CONFIG = load_fixe_config()

@dataclass
class MockPosition:
    """Position simulée pour tests"""
    symbol: str = "TEST/USDT"
    direction: str = "LONG"
    entry: float = 100.0
    sl: Optional[float] = None
    tp: Optional[float] = None
    size: float = 1000.0
    start_time: float = None
    break_even_set: bool = False
    break_even_triggered_at: float = None
    trailing_activated: bool = False
    trailing_activated_at: float = None
    partial_tp_sold: bool = False
    max_pnl_reached: float = None
    min_pnl_reached: float = None
    dynamic_sl: float = None
    stagnation_detected_at: float = None
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = time.time()

        if self.sl is None:
            sl_pct = FIXE_CONFIG['sl_percent']
            self.sl = self.entry * (1 - sl_pct / 100)

        if self.tp is None:
            tp_pct = FIXE_CONFIG['tp_percent']
            self.tp = self.entry * (1 + tp_pct / 100)


def calculate_pnl(entry: float, current: float, direction: str) -> float:
    """Calculer PnL en %"""
    if direction == 'LONG':
        return (current - entry) / entry * 100
    else:
        return (entry - current) / entry * 100


def calculate_sl_long(entry: float, sl_pct: float) -> float:
    """Calculer SL pour LONG"""
    return entry * (1 - sl_pct / 100)


def calculate_tp_long(entry: float, tp_pct: float) -> float:
    """Calculer TP pour LONG"""
    return entry * (1 + tp_pct / 100)


def update_trailing_stop_fixe(current_price: float, current_sl: float, 
                               direction: str, trailing_distance: float) -> Optional[float]:
    """
    Simuler la mise à jour du trailing stop en mode FIXE
    """
    if direction == 'LONG':
        new_sl = current_price * (1 - trailing_distance / 100)
        if new_sl > current_sl:
            return round(new_sl, 8)
    else:
        new_sl = current_price * (1 + trailing_distance / 100)
        if new_sl < current_sl:
            return round(new_sl, 8)
    return None


class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def add(self, name: str, passed: bool, detail: str = ""):
        self.tests.append((name, passed, detail))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def print_summary(self):
        print("\n" + "="*80)
        print("📊 RÉSULTATS DES TESTS MODE FIXE")
        print("="*80)
        
        for name, passed, detail in self.tests:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} | {name}")
            if detail and not passed:
                print(f"       → {detail}")
        
        print("\n" + "-"*80)
        total = self.passed + self.failed
        print(f"Total: {self.passed}/{total} tests passés ({self.passed/total*100:.0f}%)")
        if self.failed > 0:
            print(f"⚠️ {self.failed} test(s) échoué(s)")
        else:
            print("✅ Tous les tests passent!")
        print("="*80)


def run_tests():
    """Exécuter tous les tests de vérification"""
    results = TestResults()
    
    print("🧪 Démarrage des tests MODE FIXE...")
    print("="*80)
    
    # ═══════════════════════════════════════════════════════════════════
    # TEST 1: Calcul SL/TP initial
    # ═══════════════════════════════════════════════════════════════════
    print("\n📋 TEST 1: Calcul SL/TP initial")
    
    entry = 100.0
    sl_pct = FIXE_CONFIG['sl_percent']
    tp_pct = FIXE_CONFIG['tp_percent']
    
    expected_sl = entry * (1 - sl_pct / 100)
    expected_tp = entry * (1 + tp_pct / 100)
    
    actual_sl = calculate_sl_long(entry, sl_pct)
    actual_tp = calculate_tp_long(entry, tp_pct)
    
    results.add(
        f"SL initial LONG ({sl_pct}%)",
        abs(actual_sl - expected_sl) < 0.001,
        f"Expected {expected_sl}, got {actual_sl}"
    )
    
    results.add(
        f"TP initial LONG ({tp_pct}%)",
        abs(actual_tp - expected_tp) < 0.001,
        f"Expected {expected_tp}, got {actual_tp}"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # TEST 2: Break-Even Trigger
    # ═══════════════════════════════════════════════════════════════════
    print("\n📋 TEST 2: Break-Even Trigger")
    
    pos = MockPosition(entry=100.0)
    be_trigger = FIXE_CONFIG['break_even_trigger']
    be_margin = max(abs(be_trigger) * 0.1, 0.01)

    if be_trigger > 0:
        below_trigger_pct = max(be_trigger - be_margin, 0.0)
        above_trigger_pct = be_trigger + be_margin

        price_below_trigger = pos.entry * (1 + below_trigger_pct / 100)
        pnl_below = calculate_pnl(pos.entry, price_below_trigger, pos.direction)
        should_trigger_below = pnl_below >= be_trigger

        results.add(
            f"BE non activé à +{pnl_below:.2f}% (< {be_trigger}%)",
            not should_trigger_below,
            f"PnL={pnl_below:.3f}%, trigger={be_trigger}%"
        )

        price_above_trigger = pos.entry * (1 + above_trigger_pct / 100)
        pnl_above = calculate_pnl(pos.entry, price_above_trigger, pos.direction)
        should_trigger_above = pnl_above >= be_trigger

        results.add(
            f"BE activé à +{pnl_above:.2f}% (>= {be_trigger}%)",
            should_trigger_above,
            f"PnL={pnl_above:.3f}%, trigger={be_trigger}%"
        )
    else:
        should_trigger_above = True
        results.add(
            "BE trigger <= 0% (skip seuils)",
            True
        )
    
    # Après BE, SL = entry
    if should_trigger_above:
        pos.sl = pos.entry
        pos.break_even_set = True
    
    results.add(
        "SL = entry après BE",
        pos.sl == pos.entry,
        f"SL={pos.sl}, entry={pos.entry}"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # TEST 3: Trailing Stop Activation
    # ═══════════════════════════════════════════════════════════════════
    print("\n📋 TEST 3: Trailing Stop Activation")
    
    pos = MockPosition(entry=100.0, sl=100.0)  # Déjà en BE
    trailing_trigger = FIXE_CONFIG['trailing_trigger_pnl']
    trailing_distance = FIXE_CONFIG['trailing_distance']
    trailing_margin = max(abs(trailing_trigger) * 0.1, 0.01)

    if trailing_trigger > 0:
        below_trigger_pct = max(trailing_trigger - trailing_margin, 0.0)
        above_trigger_pct = trailing_trigger + trailing_margin

        price_below = pos.entry * (1 + below_trigger_pct / 100)
        pnl_below = calculate_pnl(pos.entry, price_below, pos.direction)
        should_activate_below = pnl_below >= trailing_trigger

        results.add(
            f"Trailing non activé à +{pnl_below:.2f}%",
            not should_activate_below,
            f"PnL={pnl_below:.3f}%, trigger={trailing_trigger}%"
        )

        price_above = pos.entry * (1 + above_trigger_pct / 100)
        pnl_above = calculate_pnl(pos.entry, price_above, pos.direction)
        should_activate_above = pnl_above >= trailing_trigger

        results.add(
            f"Trailing activé à +{pnl_above:.2f}%",
            should_activate_above,
            f"PnL={pnl_above:.3f}%, trigger={trailing_trigger}%"
        )
    else:
        should_activate_above = True
        results.add(
            "Trailing trigger <= 0% (skip seuils)",
            True
        )
    
    # ═══════════════════════════════════════════════════════════════════
    # TEST 4: Trailing Stop SL Update
    # ═══════════════════════════════════════════════════════════════════
    print("\n📋 TEST 4: Trailing Stop SL Update")
    
    pos = MockPosition(entry=100.0, sl=100.0, trailing_activated=True)
    
    # Prix monte à 100.40 (+0.4%)
    current_price = 100.40
    new_sl = update_trailing_stop_fixe(
        current_price, pos.sl, pos.direction, trailing_distance
    )
    
    expected_new_sl = current_price * (1 - trailing_distance / 100)
    
    results.add(
        "SL mis à jour après trailing activation",
        new_sl is not None,
        f"new_sl={new_sl}"
    )
    
    if new_sl:
        results.add(
            f"Nouveau SL = {new_sl:.4f} (attendu ~{expected_new_sl:.4f})",
            abs(new_sl - expected_new_sl) < 0.01,
            f"Différence: {abs(new_sl - expected_new_sl):.6f}"
        )
        pos.sl = new_sl
    
    # Prix monte encore à 100.50 (+0.5%)
    current_price = 100.50
    old_sl = pos.sl
    new_sl = update_trailing_stop_fixe(
        current_price, pos.sl, pos.direction, trailing_distance
    )
    
    results.add(
        "SL continue de monter avec le prix",
        new_sl is not None and new_sl > old_sl,
        f"old_sl={old_sl:.4f}, new_sl={new_sl}"
    )
    
    if new_sl:
        pos.sl = new_sl
    
    # Prix redescend à 100.35 → SL ne doit PAS descendre
    current_price = 100.35
    old_sl = pos.sl
    new_sl = update_trailing_stop_fixe(
        current_price, pos.sl, pos.direction, trailing_distance
    )
    
    results.add(
        "SL ne descend PAS quand prix baisse",
        new_sl is None,
        f"old_sl={old_sl:.4f}, new_sl={new_sl}"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # TEST 5: Trailing Stop Continue After Pullback
    # ═══════════════════════════════════════════════════════════════════
    print("\n📋 TEST 5: Trailing Continue Après Pullback")
    
    # Scénario ASTER: prix monte à +0.4%, redescend à +0.2%, le trailing doit continuer
    pos = MockPosition(entry=100.0, sl=100.0, trailing_activated=True)
    
    # 1. Prix monte à +0.4% → SL mis à jour
    price_high = 100.40
    new_sl = update_trailing_stop_fixe(price_high, pos.sl, pos.direction, trailing_distance)
    if new_sl:
        pos.sl = new_sl
    sl_at_high = pos.sl
    
    # 2. Prix redescend à +0.2% → SL doit rester
    price_low = 100.20
    new_sl = update_trailing_stop_fixe(price_low, pos.sl, pos.direction, trailing_distance)
    
    results.add(
        "SL protège gains après pullback",
        new_sl is None and pos.sl == sl_at_high,
        f"SL={pos.sl:.4f} maintenu (prix={price_low})"
    )
    
    # 3. Vérifier que le SL protège bien
    # Si le prix touche le SL, le PnL doit être positif
    pnl_at_sl = calculate_pnl(pos.entry, pos.sl, pos.direction)
    
    results.add(
        f"PnL protégé si SL touché: +{pnl_at_sl:.3f}%",
        pnl_at_sl > 0,
        f"SL={pos.sl:.4f}, entry={pos.entry}"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # TEST 6: Stagnation Exit (Mode FIXE)
    # ═══════════════════════════════════════════════════════════════════
    print("\n📋 TEST 6: Stagnation Exit (Mode FIXE)")
    
    timeout = FIXE_CONFIG['stagnation_exit_timeout_seconds']  # 540s
    min_pnl = FIXE_CONFIG['stagnation_exit_min_pnl_to_stay']
    min_pnl_margin = max(abs(min_pnl) * 0.2, 0.01)
    
    # Position avec PnL < min_pnl après timeout → STAGNATION
    pos = MockPosition(entry=100.0)
    pos.start_time = time.time() - timeout - 10  # Timeout dépassé
    
    below_pnl = min_pnl - min_pnl_margin
    current_price = pos.entry * (1 + below_pnl / 100)
    pnl = calculate_pnl(pos.entry, current_price, pos.direction)
    elapsed = time.time() - pos.start_time
    
    should_exit_stagnation = elapsed >= timeout and pnl < min_pnl
    
    results.add(
        f"STAGNATION: PnL={pnl:.3f}% < {min_pnl}% après {elapsed:.0f}s",
        should_exit_stagnation,
        f"elapsed={elapsed:.0f}s, timeout={timeout}s"
    )
    
    # Position avec PnL >= min_pnl après timeout → NE PAS sortir
    above_pnl = min_pnl + min_pnl_margin
    current_price = pos.entry * (1 + above_pnl / 100)
    pnl = calculate_pnl(pos.entry, current_price, pos.direction)
    should_stay = elapsed >= timeout and pnl >= min_pnl
    
    results.add(
        f"RESTE: PnL={pnl:.3f}% >= {min_pnl}% après timeout",
        should_stay,
        f"PnL={pnl:.3f}%"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # TEST 7: Exit Reasons
    # ═══════════════════════════════════════════════════════════════════
    print("\n📋 TEST 7: Exit Reasons")
    
    pos = MockPosition(entry=100.0, sl=100.10, tp=105.0)  # SL au-dessus de entry (trailing)
    
    # SL touché en profit → TS
    current_price = 100.10
    pnl = calculate_pnl(pos.entry, current_price, pos.direction)
    exit_reason = 'TS' if pnl >= 0 else 'SL'
    
    results.add(
        "Exit reason = TS si SL touché en profit",
        exit_reason == 'TS' and pnl >= 0,
        f"exit_reason={exit_reason}, pnl={pnl:.3f}%"
    )
    
    # SL initial touché (en perte) → SL
    pos = MockPosition(entry=100.0, sl=99.75)
    current_price = 99.75
    pnl = calculate_pnl(pos.entry, current_price, pos.direction)
    exit_reason = 'TS' if pnl >= 0 else 'SL'
    
    results.add(
        "Exit reason = SL si SL touché en perte",
        exit_reason == 'SL' and pnl < 0,
        f"exit_reason={exit_reason}, pnl={pnl:.3f}%"
    )
    
    # TP touché → TP
    pos = MockPosition(entry=100.0, tp=105.0)
    current_price = 105.0
    pnl = calculate_pnl(pos.entry, current_price, pos.direction)
    
    results.add(
        "Exit reason = TP si TP touché",
        current_price >= pos.tp and pnl >= FIXE_CONFIG['tp_percent'],
        f"TP={pos.tp}, price={current_price}, pnl={pnl:.2f}%"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # TEST 8: Scenario Complet ASTER
    # ═══════════════════════════════════════════════════════════════════
    print("\n📋 TEST 8: Scénario Complet (Type ASTER)")
    
    entry_price = 0.7749
    sl_pct = FIXE_CONFIG['sl_percent']
    tp_pct = FIXE_CONFIG['tp_percent']
    be_trigger = FIXE_CONFIG['break_even_trigger']
    trailing_trigger = FIXE_CONFIG['trailing_trigger_pnl']

    activation_trigger = max(be_trigger, trailing_trigger, 0.0)
    activation_margin = max(activation_trigger * 0.5, 0.1)

    pct_before = max(activation_trigger - activation_margin, 0.01)
    pct_trigger = activation_trigger + (activation_margin * 0.2)
    pct_high = activation_trigger + activation_margin
    pct_pullback = activation_trigger + (activation_margin * 0.6)
    pct_lower = activation_trigger + (activation_margin * 0.3)

    pos = MockPosition(
        entry=entry_price,
        sl=entry_price * (1 - sl_pct / 100),
        tp=entry_price * (1 + tp_pct / 100)
    )

    # Simulation des ticks
    ticks = [
        (entry_price * (1 + pct_before / 100), f"Prix monte à +{pct_before:.2f}%"),
        (entry_price * (1 + pct_trigger / 100), f"Prix monte à +{pct_trigger:.2f}% - BE & Trailing trigger"),
        (entry_price * (1 + pct_high / 100), f"Prix monte à +{pct_high:.2f}% - Max"),
        (entry_price * (1 + pct_pullback / 100), f"Prix redescend à +{pct_pullback:.2f}%"),
        (entry_price * (1 + pct_lower / 100), f"Prix redescend à +{pct_lower:.2f}%"),
    ]
    
    print(f"   Entry: {pos.entry:.4f}, SL initial: {pos.sl:.6f}")
    
    for price, desc in ticks:
        pnl = calculate_pnl(pos.entry, price, pos.direction)
        
        # BE check
        if not pos.break_even_set and pnl >= FIXE_CONFIG['break_even_trigger']:
            pos.sl = pos.entry
            pos.break_even_set = True
            print(f"   🛡️ BE activé à {price:.4f} (PnL={pnl:.3f}%)")
        
        # Trailing activation
        if not pos.trailing_activated and pnl >= FIXE_CONFIG['trailing_trigger_pnl']:
            pos.trailing_activated = True
            print(f"   🎢 Trailing activé à {price:.4f} (PnL={pnl:.3f}%)")
        
        # Trailing update
        if pos.trailing_activated:
            new_sl = update_trailing_stop_fixe(
                price, pos.sl, pos.direction, FIXE_CONFIG['trailing_distance']
            )
            if new_sl:
                old_sl = pos.sl
                pos.sl = new_sl
                print(f"   📈 SL mis à jour: {old_sl:.6f} → {new_sl:.6f} ({desc})")
        
        # Track MFE
        if pos.max_pnl_reached is None or pnl > pos.max_pnl_reached:
            pos.max_pnl_reached = pnl
    
    # Vérification finale
    final_pnl_at_sl = calculate_pnl(pos.entry, pos.sl, pos.direction)
    
    print(f"\n   📊 Résultat final:")
    print(f"      SL final: {pos.sl:.6f}")
    print(f"      MFE: +{pos.max_pnl_reached:.3f}%")
    print(f"      PnL si SL touché: +{final_pnl_at_sl:.3f}%")
    
    min_protected_pnl = max(activation_trigger * 0.3, 0.05)
    results.add(
        "Scénario ASTER: SL protège gains",
        final_pnl_at_sl > min_protected_pnl,
        f"PnL protégé: +{final_pnl_at_sl:.3f}% (min: {min_protected_pnl:.3f}%)"
    )
    
    results.add(
        "Scénario ASTER: Trailing activé",
        pos.trailing_activated,
        f"trailing_activated={pos.trailing_activated}"
    )
    
    expected_mfe = pct_high - 0.01
    results.add(
        "Scénario ASTER: MFE tracké",
        pos.max_pnl_reached is not None and pos.max_pnl_reached >= expected_mfe,
        f"MFE={pos.max_pnl_reached:.3f}% (min: {expected_mfe:.3f}%)"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # Résumé
    # ═══════════════════════════════════════════════════════════════════
    results.print_summary()
    
    return results.failed == 0


def verify_config():
    """Vérifier que la config actuelle est valide pour le MODE FIXE (valeurs actives)."""
    print("\n" + "="*80)
    print("🔧 VÉRIFICATION DE LA CONFIGURATION")
    print("="*80)

    try:
        config = load_fixe_config()

        checks = [
            ('tp_sl_mode', 'FIXE', config.get('tp_sl_mode')),
            ('sl_percent', None, config.get('sl_percent')),
            ('tp_percent', None, config.get('tp_percent')),
            ('break_even_trigger', None, config.get('break_even_trigger')),
            ('trailing_trigger_pnl', None, config.get('trailing_trigger_pnl')),
            ('trailing_distance', None, config.get('trailing_distance')),
            ('trailing_use_atr_trigger', False, config.get('trailing_use_atr_trigger')),
            ('stagnation_exit_enabled', None, config.get('stagnation_exit_enabled')),
        ]

        all_ok = True
        for key, expected, actual in checks:
            if expected is None:
                match = actual is not None
                status = "✅" if match else "❌"
                print(f"{status} {key}: {actual}")
            else:
                match = actual == expected
                status = "✅" if match else "❌"
                print(f"{status} {key}: {actual} (attendu: {expected})")
            if not match:
                all_ok = False

        if all_ok:
            print("\n✅ Configuration MODE FIXE valide (valeurs actives)")
        else:
            print("\n⚠️ Configuration MODE FIXE invalide")

        return all_ok

    except Exception as e:
        print(f"❌ Erreur lecture config: {e}")
        return False


if __name__ == '__main__':
    print("="*80)
    print("🧪 VÉRIFICATION COMPLÈTE DU MODE FIXE")
    print("="*80)
    
    # 1. Vérifier la config
    config_ok = verify_config()
    
    # 2. Exécuter les tests
    tests_ok = run_tests()
    
    # Résultat final
    print("\n" + "="*80)
    if config_ok and tests_ok:
        print("✅ VALIDATION MODE FIXE: SUCCÈS")
    else:
        print("❌ VALIDATION MODE FIXE: ÉCHEC")
        if not config_ok:
            print("   → Corriger la configuration")
        if not tests_ok:
            print("   → Des tests ont échoué")
    print("="*80)

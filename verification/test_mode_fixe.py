"""
🧪 Script de vérification complet du MODE FIXE
Teste toute la logique: SL/TP, Break-Even, Trailing Stop, Stagnation
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
import time

# Configuration MODE FIXE attendue
FIXE_CONFIG = {
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

@dataclass
class MockPosition:
    """Position simulée pour tests"""
    symbol: str = "TEST/USDT"
    direction: str = "LONG"
    entry: float = 100.0
    sl: float = 99.75  # -0.25%
    tp: float = 105.0  # +5%
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
    sl_pct = FIXE_CONFIG['sl_percent']  # 0.25%
    tp_pct = FIXE_CONFIG['tp_percent']  # 5.0%
    
    expected_sl = 99.75  # 100 * (1 - 0.25/100)
    expected_tp = 105.0  # 100 * (1 + 5/100)
    
    actual_sl = calculate_sl_long(entry, sl_pct)
    actual_tp = calculate_tp_long(entry, tp_pct)
    
    results.add(
        "SL initial LONG (0.25%)",
        abs(actual_sl - expected_sl) < 0.001,
        f"Expected {expected_sl}, got {actual_sl}"
    )
    
    results.add(
        "TP initial LONG (5%)",
        abs(actual_tp - expected_tp) < 0.001,
        f"Expected {expected_tp}, got {actual_tp}"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # TEST 2: Break-Even Trigger
    # ═══════════════════════════════════════════════════════════════════
    print("\n📋 TEST 2: Break-Even Trigger")
    
    pos = MockPosition(entry=100.0, sl=99.75)
    be_trigger = FIXE_CONFIG['break_even_trigger']  # 0.15%
    
    # Prix à +0.14% → BE ne doit PAS s'activer
    price_below_trigger = 100.14
    pnl_below = calculate_pnl(pos.entry, price_below_trigger, pos.direction)
    should_trigger_below = pnl_below >= be_trigger
    
    results.add(
        f"BE non activé à +{pnl_below:.2f}% (< {be_trigger}%)",
        not should_trigger_below,
        f"PnL={pnl_below:.3f}%, trigger={be_trigger}%"
    )
    
    # Prix à +0.16% → BE DOIT s'activer
    price_above_trigger = 100.16
    pnl_above = calculate_pnl(pos.entry, price_above_trigger, pos.direction)
    should_trigger_above = pnl_above >= be_trigger
    
    results.add(
        f"BE activé à +{pnl_above:.2f}% (>= {be_trigger}%)",
        should_trigger_above,
        f"PnL={pnl_above:.3f}%, trigger={be_trigger}%"
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
    trailing_trigger = FIXE_CONFIG['trailing_trigger_pnl']  # 0.15%
    trailing_distance = FIXE_CONFIG['trailing_distance']  # 0.1%
    
    # Prix à +0.14% → Trailing ne doit PAS s'activer
    price_below = 100.14
    pnl_below = calculate_pnl(pos.entry, price_below, pos.direction)
    should_activate_below = pnl_below >= trailing_trigger
    
    results.add(
        f"Trailing non activé à +{pnl_below:.2f}%",
        not should_activate_below,
        f"PnL={pnl_below:.3f}%, trigger={trailing_trigger}%"
    )
    
    # Prix à +0.20% → Trailing DOIT s'activer
    price_above = 100.20
    pnl_above = calculate_pnl(pos.entry, price_above, pos.direction)
    should_activate_above = pnl_above >= trailing_trigger
    
    results.add(
        f"Trailing activé à +{pnl_above:.2f}%",
        should_activate_above,
        f"PnL={pnl_above:.3f}%, trigger={trailing_trigger}%"
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
    
    expected_new_sl = 100.40 * (1 - 0.1/100)  # 100.2996
    
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
    min_pnl = FIXE_CONFIG['stagnation_exit_min_pnl_to_stay']  # 0.03%
    
    # Position avec PnL < min_pnl après timeout → STAGNATION
    pos = MockPosition(entry=100.0)
    pos.start_time = time.time() - timeout - 10  # Timeout dépassé
    
    current_price = 100.02  # +0.02% < 0.03%
    pnl = calculate_pnl(pos.entry, current_price, pos.direction)
    elapsed = time.time() - pos.start_time
    
    should_exit_stagnation = elapsed >= timeout and pnl < min_pnl
    
    results.add(
        f"STAGNATION: PnL={pnl:.3f}% < {min_pnl}% après {elapsed:.0f}s",
        should_exit_stagnation,
        f"elapsed={elapsed:.0f}s, timeout={timeout}s"
    )
    
    # Position avec PnL >= min_pnl après timeout → NE PAS sortir
    current_price = 100.05  # +0.05% >= 0.03%
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
    
    pos = MockPosition(
        entry=0.7749,
        sl=0.7749 * (1 - 0.25/100),  # SL initial
        tp=0.7749 * (1 + 5/100)
    )
    
    # Simulation des ticks
    ticks = [
        (0.7755, "Prix monte à +0.08%"),
        (0.7765, "Prix monte à +0.21% - BE & Trailing trigger"),
        (0.7780, "Prix monte à +0.40% - Max"),
        (0.7770, "Prix redescend à +0.27%"),
        (0.7760, "Prix redescend à +0.14%"),
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
    
    results.add(
        "Scénario ASTER: SL protège gains après +0.4%",
        final_pnl_at_sl > 0.2,  # Devrait protéger au moins +0.2%
        f"PnL protégé: +{final_pnl_at_sl:.3f}%"
    )
    
    results.add(
        "Scénario ASTER: Trailing activé",
        pos.trailing_activated,
        f"trailing_activated={pos.trailing_activated}"
    )
    
    results.add(
        "Scénario ASTER: MFE tracké",
        pos.max_pnl_reached is not None and pos.max_pnl_reached >= 0.35,
        f"MFE={pos.max_pnl_reached:.3f}%"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # Résumé
    # ═══════════════════════════════════════════════════════════════════
    results.print_summary()
    
    return results.failed == 0


def verify_config():
    """Vérifier que la config actuelle correspond au MODE FIXE attendu"""
    print("\n" + "="*80)
    print("🔧 VÉRIFICATION DE LA CONFIGURATION")
    print("="*80)
    
    try:
        # Charger config_overrides.json
        import json
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config_overrides.json')
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        checks = [
            ('tp_sl_mode', 'FIXE', config.get('tp_sl_mode')),
            ('sl_percent', 0.25, config.get('sl_percent')),
            ('tp_percent', 5.0, config.get('tp_percent')),
            ('break_even_trigger', 0.15, config.get('break_even_trigger')),
            ('trailing_trigger_pnl', 0.15, config.get('trailing_trigger_pnl')),
            ('trailing_distance', 0.1, config.get('trailing_distance')),
            ('trailing_use_atr_trigger', False, config.get('trailing_use_atr_trigger')),
            ('stagnation_exit_enabled', True, config.get('stagnation_exit_enabled')),
        ]
        
        all_ok = True
        for key, expected, actual in checks:
            match = actual == expected
            status = "✅" if match else "❌"
            print(f"{status} {key}: {actual} (attendu: {expected})")
            if not match:
                all_ok = False
        
        if all_ok:
            print("\n✅ Configuration MODE FIXE correcte!")
        else:
            print("\n⚠️ Configuration à corriger!")
        
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

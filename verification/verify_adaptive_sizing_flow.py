#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICATION FLOW SIZING ADAPTATIF
===================================
Simule le flux exact: WinRate evolutif par paire, multiplicateur au moment
de l'ouverture, et seuil grosse perte sur UN SEUL trade.
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from datetime import datetime
print("=" * 70)
print("  VERIFICATION FLOW SIZING ADAPTATIF")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

from core.position.adaptive_sizing import (
    get_adaptive_sizing_manager,
    reset_adaptive_sizing_manager
)
from config import TRADING_CONFIG

# Reset pour demarrer propre
reset_adaptive_sizing_manager()
manager = get_adaptive_sizing_manager()

SYMBOL = "TEST/USDT:USDT"
min_trades = TRADING_CONFIG.get('adaptive_sizing_min_trades', 3)
big_loss_threshold = TRADING_CONFIG.get('adaptive_sizing_big_loss_threshold', -2.0)

print(f"\n   Config: min_trades={min_trades}, big_loss_threshold={big_loss_threshold}%")
print("\n" + "-" * 70)

# =============================================================================
# SIMULATION: 7 trades avec multiplicateur au moment de l'ouverture
# =============================================================================
print("\n[SIMULATION] 7 trades successifs sur", SYMBOL)
print("=" * 70)

trades = [
    # (pnl_pct, is_win, description)
    (0.30, True, "Trade 1: WIN +0.30%"),
    (0.25, True, "Trade 2: WIN +0.25%"),
    (-0.15, False, "Trade 3: LOSS -0.15%"),
    (0.40, True, "Trade 4: WIN +0.40%"),
    (0.35, True, "Trade 5: WIN +0.35%"),
    (-0.20, False, "Trade 6: LOSS -0.20%"),
    (-2.50, False, "Trade 7: GROSSE PERTE -2.50% (> seuil)"),
]

print("\n   FLUX: Multiplicateur calcule AVANT ouverture, WinRate mis a jour APRES trade")
print("-" * 70)

for i, (pnl, is_win, desc) in enumerate(trades):
    # Stats AVANT ce trade
    stats = manager.pair_stats.get(SYMBOL)
    trades_before = stats.total_trades if stats else 0
    wins_before = stats.wins if stats else 0
    losses_before = stats.losses if stats else 0
    wr_before = stats.winrate if stats else 0.0
    
    # MULTIPLICATEUR AU MOMENT DE L'OUVERTURE (avant le trade)
    mult_at_open = manager.get_size_multiplier(SYMBOL)
    
    print(f"\n   === Trade {i+1} ===")
    print(f"   AVANT ouverture: trades={trades_before}, WR={wr_before:.0%} ({wins_before}W/{losses_before}L)")
    print(f"   -> Multiplicateur utilise: x{mult_at_open:.2f}")
    print(f"   Execution: {desc}")
    
    # ENREGISTRER LE TRADE (apres fermeture)
    manager.record_trade(SYMBOL, pnl, is_win)
    
    # Stats APRES ce trade
    stats_after = manager.pair_stats.get(SYMBOL)
    if stats_after:
        print(f"   APRES trade: trades={stats_after.total_trades}, WR={stats_after.winrate:.0%} ({stats_after.wins}W/{stats_after.losses}L)")
    else:
        print(f"   APRES trade: RESET (grosse perte detectee)")

print("\n" + "=" * 70)
print("  VERIFICATION ASSERTIONS")
print("=" * 70)

# =============================================================================
# VERIFICATIONS
# =============================================================================
tests_passed = 0
tests_total = 0

# Test 1: Grosse perte sur UN SEUL TRADE reset les stats
reset_adaptive_sizing_manager()
manager = get_adaptive_sizing_manager()

# Simuler 3 wins
manager.record_trade(SYMBOL, 0.30, True)
manager.record_trade(SYMBOL, 0.25, True)
manager.record_trade(SYMBOL, 0.20, True)

stats = manager.pair_stats.get(SYMBOL)
total_before = stats.total_trades if stats else 0
print(f"\n[TEST 1] Grosse perte = UN SEUL TRADE")
print(f"   Avant: {total_before} trades (100% WR)")

# UN SEUL trade avec grosse perte
manager.record_trade(SYMBOL, big_loss_threshold - 0.5, False)

stats_after = manager.pair_stats.get(SYMBOL)
total_after = stats_after.total_trades if stats_after else 0
print(f"   Apres UN trade a {big_loss_threshold - 0.5}%: {total_after} trades")

tests_total += 1
if total_after == 0:
    print(f"   [OK] UN SEUL trade perdant reset les stats")
    tests_passed += 1
else:
    print(f"   [FAIL] Devrait avoir reset (trades={total_after})")

# Test 2: WinRate evolutif par paire
reset_adaptive_sizing_manager()
manager = get_adaptive_sizing_manager()

print(f"\n[TEST 2] WinRate EVOLUTIF par paire")

# Enregistrer trades et verifier WR apres chaque
expected_wrs = []
manager.record_trade(SYMBOL, 0.30, True)   # 1W/0L = 100%
expected_wrs.append((1.0, manager.pair_stats[SYMBOL].winrate))

manager.record_trade(SYMBOL, -0.15, False)  # 1W/1L = 50%
expected_wrs.append((0.5, manager.pair_stats[SYMBOL].winrate))

manager.record_trade(SYMBOL, 0.25, True)   # 2W/1L = 66.7%
expected_wrs.append((0.667, manager.pair_stats[SYMBOL].winrate))

manager.record_trade(SYMBOL, 0.20, True)   # 3W/1L = 75%
expected_wrs.append((0.75, manager.pair_stats[SYMBOL].winrate))

manager.record_trade(SYMBOL, -0.10, False)  # 3W/2L = 60%
expected_wrs.append((0.6, manager.pair_stats[SYMBOL].winrate))

all_correct = True
for i, (expected, actual) in enumerate(expected_wrs):
    status = "[OK]" if abs(expected - actual) < 0.01 else "[FAIL]"
    print(f"   Trade {i+1}: WR attendu={expected:.0%}, obtenu={actual:.0%} {status}")
    if abs(expected - actual) >= 0.01:
        all_correct = False

tests_total += 1
if all_correct:
    print(f"   [OK] WinRate mis a jour apres CHAQUE trade")
    tests_passed += 1
else:
    print(f"   [FAIL] WinRate incorrect")

# Test 3: Multiplicateur au moment de l'ouverture
reset_adaptive_sizing_manager()
manager = get_adaptive_sizing_manager()

print(f"\n[TEST 3] Multiplicateur au moment de l'OUVERTURE")

# Avant min_trades: mult = 1.0
mult_before_min = manager.get_size_multiplier(SYMBOL)
print(f"   0 trades: mult={mult_before_min:.2f} (attendu: 1.0)")

# Enregistrer 3 wins pour atteindre min_trades avec excellent WR
manager.record_trade(SYMBOL, 0.30, True)
manager.record_trade(SYMBOL, 0.25, True)
manager.record_trade(SYMBOL, 0.20, True)

# Maintenant mult devrait refleter 100% WR
mult_after_3wins = manager.get_size_multiplier(SYMBOL)
excellent_mult = TRADING_CONFIG.get('adaptive_sizing_excellent_mult', 1.5)
print(f"   3W/0L (100% WR): mult={mult_after_3wins:.2f} (attendu: ~{excellent_mult:.2f})")

# Enregistrer 2 losses
manager.record_trade(SYMBOL, -0.15, False)
manager.record_trade(SYMBOL, -0.20, False)

# Maintenant 3W/2L = 60% WR
mult_after_losses = manager.get_size_multiplier(SYMBOL)
good_wr = TRADING_CONFIG.get('adaptive_sizing_good_wr', 0.6)
good_mult = TRADING_CONFIG.get('adaptive_sizing_good_mult', 1.25)
print(f"   3W/2L (60% WR): mult={mult_after_losses:.2f} (attendu: ~{good_mult:.2f})")

tests_total += 1
# Le mult doit changer en fonction du WR
if mult_before_min == 1.0 and mult_after_3wins > mult_after_losses:
    print(f"   [OK] Multiplicateur change en fonction du WR au moment de l'ouverture")
    tests_passed += 1
else:
    print(f"   [FAIL] Multiplicateur ne change pas correctement")

# Test 4: Isolation par paire
reset_adaptive_sizing_manager()
manager = get_adaptive_sizing_manager()

print(f"\n[TEST 4] Isolation par PAIRE")

PAIR_A = "BTC/USDT:USDT"
PAIR_B = "ETH/USDT:USDT"

# PAIR_A: 3 wins = 100% WR
for _ in range(3):
    manager.record_trade(PAIR_A, 0.30, True)

# PAIR_B: 3 losses = 0% WR
for _ in range(3):
    manager.record_trade(PAIR_B, -0.20, False)

mult_a = manager.get_size_multiplier(PAIR_A)
mult_b = manager.get_size_multiplier(PAIR_B)
wr_a = manager.pair_stats[PAIR_A].winrate
wr_b = manager.pair_stats[PAIR_B].winrate

print(f"   {PAIR_A}: WR={wr_a:.0%}, mult={mult_a:.2f}")
print(f"   {PAIR_B}: WR={wr_b:.0%}, mult={mult_b:.2f}")

tests_total += 1
if mult_a > mult_b and wr_a > wr_b:
    print(f"   [OK] Paires completement isolees")
    tests_passed += 1
else:
    print(f"   [FAIL] Paires non isolees")

# =============================================================================
# RESUME
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME")
print("=" * 70)

print(f"\n   Tests passes: {tests_passed}/{tests_total}")

if tests_passed == tests_total:
    print("\n   [SUCCESS] TOUS LES TESTS PASSENT")
else:
    print(f"\n   [WARNING] {tests_total - tests_passed} TEST(S) ECHOUE(S)")

print("\n" + "=" * 70)
print("  CONFIRMATION DU FLUX")
print("=" * 70)
print("""
   1. SEUIL GROSSE PERTE = UN SEUL TRADE
      - Si pnl_pct <= big_loss_threshold sur UN trade -> reset immediate
      - Pas de cumul, juste le dernier trade
   
   2. WINRATE EVOLUTIF PAR PAIRE
      - Apres chaque trade: wins++ ou losses++
      - winrate = wins / (wins + losses) recalcule en temps reel
   
   3. MULTIPLICATEUR AU MOMENT DE L'OUVERTURE
      - get_size_multiplier() appele dans calculate_position_size()
      - Utilise le WR ACTUEL de la session pour cette paire
      - Le trade en cours n'est PAS encore compte
   
   4. SESSION = RAM
      - Redemarrage backend = reset toutes les stats
      - Identique a dashboard.stats / graphiques / tradehistory
""")
print("=" * 70)

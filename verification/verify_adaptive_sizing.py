#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔬 VÉRIFICATION SIZING ADAPTATIF PAR PAIRE/SESSION
===================================================
Simule des trades pour vérifier le bon fonctionnement du sizing adaptatif.
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from datetime import datetime

print("=" * 70)
print("  VÉRIFICATION SIZING ADAPTATIF")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# =============================================================================
# 1. CHARGEMENT DE LA CONFIGURATION
# =============================================================================
print("\n[1/5] Chargement configuration...")

from config import TRADING_CONFIG

print(f"   adaptive_sizing_enabled: {TRADING_CONFIG.get('adaptive_sizing_enabled', True)}")
print(f"   adaptive_sizing_min_trades: {TRADING_CONFIG.get('adaptive_sizing_min_trades', 3)}")
print(f"   adaptive_sizing_excellent_wr: {TRADING_CONFIG.get('adaptive_sizing_excellent_wr', 0.75)}")
print(f"   adaptive_sizing_good_wr: {TRADING_CONFIG.get('adaptive_sizing_good_wr', 0.60)}")
print(f"   adaptive_sizing_poor_wr: {TRADING_CONFIG.get('adaptive_sizing_poor_wr', 0.40)}")
print(f"   adaptive_sizing_excellent_mult: {TRADING_CONFIG.get('adaptive_sizing_excellent_mult', 1.50)}")
print(f"   adaptive_sizing_poor_mult: {TRADING_CONFIG.get('adaptive_sizing_poor_mult', 0.70)}")

# =============================================================================
# 2. TEST DU MANAGER
# =============================================================================
print("\n[2/5] Test du AdaptiveSizingManager...")

from core.position.adaptive_sizing import (
    AdaptiveSizingManager, 
    AdaptiveSizingConfig,
    load_adaptive_sizing_config,
    reset_adaptive_sizing_manager,
    get_adaptive_sizing_manager
)

# Reset pour test propre
reset_adaptive_sizing_manager()

# Créer manager avec config depuis TRADING_CONFIG
manager = get_adaptive_sizing_manager()
print(f"   ✅ Manager créé avec config depuis TRADING_CONFIG")
print(f"   Config chargée: enabled={manager.config.enabled}")

# =============================================================================
# 3. SIMULATION DE TRADES
# =============================================================================
print("\n[3/5] Simulation de trades...")

SYMBOL_A = "BTC/USDT"
SYMBOL_B = "DOGE/USDT"

# Scénario 1: BTC/USDT - Excellente performance (4W/1L = 80% WR)
print(f"\n   📊 Scénario 1: {SYMBOL_A} - Performance excellente")
trades_btc = [
    (0.35, True),   # Win +0.35%
    (0.22, True),   # Win +0.22%
    (-0.15, False), # Loss -0.15%
    (0.45, True),   # Win +0.45%
    (0.18, True),   # Win +0.18%
]

for pnl, is_win in trades_btc:
    mult_before = manager.get_size_multiplier(SYMBOL_A)
    manager.record_trade(SYMBOL_A, pnl, is_win)
    mult_after = manager.get_size_multiplier(SYMBOL_A)
    print(f"      Trade {'WIN' if is_win else 'LOSS'} {pnl:+.2f}% | Mult: {mult_before:.2f} → {mult_after:.2f}")

stats_btc = manager.pair_stats.get(SYMBOL_A)
print(f"   Résultat: {stats_btc.wins}W/{stats_btc.losses}L = {stats_btc.winrate:.0%} WR")
print(f"   Multiplicateur final: {manager.get_size_multiplier(SYMBOL_A):.2f}")

# Scénario 2: DOGE/USDT - Mauvaise performance (1W/4L = 20% WR)
print(f"\n   📊 Scénario 2: {SYMBOL_B} - Mauvaise performance")
trades_doge = [
    (-0.25, False), # Loss -0.25%
    (-0.18, False), # Loss -0.18%
    (0.30, True),   # Win +0.30%
    (-0.22, False), # Loss -0.22%
    (-0.15, False), # Loss -0.15%
]

for pnl, is_win in trades_doge:
    mult_before = manager.get_size_multiplier(SYMBOL_B)
    manager.record_trade(SYMBOL_B, pnl, is_win)
    mult_after = manager.get_size_multiplier(SYMBOL_B)
    print(f"      Trade {'WIN' if is_win else 'LOSS'} {pnl:+.2f}% | Mult: {mult_before:.2f} → {mult_after:.2f}")

stats_doge = manager.pair_stats.get(SYMBOL_B)
print(f"   Résultat: {stats_doge.wins}W/{stats_doge.losses}L = {stats_doge.winrate:.0%} WR")
print(f"   Multiplicateur final: {manager.get_size_multiplier(SYMBOL_B):.2f}")

# =============================================================================
# 4. VÉRIFICATION DES MULTIPLICATEURS
# =============================================================================
print("\n[4/5] Vérification des multiplicateurs...")

# Attendu: BTC (80% WR) devrait avoir mult >= 1.25 (bon) ou 1.50 (excellent)
mult_btc = manager.get_size_multiplier(SYMBOL_A)
expected_btc = manager.config.excellent_multiplier  # 80% >= 75% = excellent

# Attendu: DOGE (20% WR) devrait avoir mult <= 0.50 (très mauvais) ou 0.70 (mauvais)
mult_doge = manager.get_size_multiplier(SYMBOL_B)
expected_doge = manager.config.very_poor_multiplier  # 20% <= 30% = très mauvais

tests_passed = 0
tests_total = 2

# Test 1: BTC devrait avoir multiplicateur excellent
if mult_btc >= manager.config.good_multiplier:
    print(f"   ✅ TEST 1 PASS: {SYMBOL_A} mult={mult_btc:.2f} >= {manager.config.good_multiplier:.2f} (bon+)")
    tests_passed += 1
else:
    print(f"   ❌ TEST 1 FAIL: {SYMBOL_A} mult={mult_btc:.2f} < {manager.config.good_multiplier:.2f}")

# Test 2: DOGE devrait avoir multiplicateur réduit
if mult_doge <= manager.config.poor_multiplier:
    print(f"   ✅ TEST 2 PASS: {SYMBOL_B} mult={mult_doge:.2f} <= {manager.config.poor_multiplier:.2f} (mauvais)")
    tests_passed += 1
else:
    print(f"   ❌ TEST 2 FAIL: {SYMBOL_B} mult={mult_doge:.2f} > {manager.config.poor_multiplier:.2f}")

# =============================================================================
# 5. TEST RESET ET GROSSE PERTE
# =============================================================================
print("\n[5/5] Test reset et grosse perte...")

# Simuler une grosse perte sur BTC (devrait reset)
print(f"   Avant grosse perte: {SYMBOL_A} mult={manager.get_size_multiplier(SYMBOL_A):.2f}")
manager.record_trade(SYMBOL_A, -2.5, False)  # Grosse perte -2.5%
print(f"   Après grosse perte: {SYMBOL_A} mult={manager.get_size_multiplier(SYMBOL_A):.2f}")

# Vérifier que stats ont été reset
stats_btc_after = manager.pair_stats.get(SYMBOL_A)
if stats_btc_after.total_trades == 0:
    print(f"   ✅ TEST 3 PASS: Stats reset après grosse perte")
    tests_passed += 1
    tests_total += 1
else:
    print(f"   ❌ TEST 3 FAIL: Stats non reset (trades={stats_btc_after.total_trades})")
    tests_total += 1

# =============================================================================
# RÉSUMÉ
# =============================================================================
print("\n" + "=" * 70)
print("  RÉSUMÉ")
print("=" * 70)

all_stats = manager.get_all_stats()
print(f"\n   Stats toutes paires:")
for symbol, data in all_stats.items():
    print(f"      {symbol}: {data['wins']}W/{data['losses']}L = {data['winrate']:.0%} | mult={data['current_multiplier']:.2f}")

print(f"\n   Tests passés: {tests_passed}/{tests_total}")

if tests_passed == tests_total:
    print("\n   🎉 TOUS LES TESTS PASSENT - SIZING ADAPTATIF FONCTIONNEL")
else:
    print(f"\n   ⚠️ {tests_total - tests_passed} TEST(S) ÉCHOUÉ(S)")

print("\n" + "=" * 70)

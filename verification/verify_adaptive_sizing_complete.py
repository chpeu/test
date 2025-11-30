#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICATION COMPLETE - SIZING ADAPTATIF PAR PAIRE/SESSION
============================================================
Teste l'ensemble du systeme: config, manager, integration, persistence.
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import time
from datetime import datetime

print("=" * 70)
print("  VERIFICATION COMPLETE SIZING ADAPTATIF")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

tests_passed = 0
tests_total = 0

# =============================================================================
# 1. VERIFICATION CONFIG.PY
# =============================================================================
print("\n[1/6] Verification config.py...")

from config import TRADING_CONFIG

required_keys = [
    'adaptive_sizing_enabled',
    'adaptive_sizing_min_trades',
    'adaptive_sizing_excellent_wr',
    'adaptive_sizing_good_wr',
    'adaptive_sizing_poor_wr',
    'adaptive_sizing_very_poor_wr',
    'adaptive_sizing_excellent_mult',
    'adaptive_sizing_good_mult',
    'adaptive_sizing_normal_mult',
    'adaptive_sizing_poor_mult',
    'adaptive_sizing_very_poor_mult',
    'adaptive_sizing_max_mult',
    'adaptive_sizing_min_mult',
    'adaptive_sizing_reset_hours',
    'adaptive_sizing_reset_big_loss',
    'adaptive_sizing_big_loss_threshold'
]

missing_keys = [k for k in required_keys if k not in TRADING_CONFIG]
tests_total += 1
if not missing_keys:
    print(f"   [OK] Toutes les {len(required_keys)} variables presentes dans TRADING_CONFIG")
    tests_passed += 1
else:
    print(f"   [FAIL] Variables manquantes: {missing_keys}")

# Afficher les valeurs actuelles
print("\n   Valeurs actuelles:")
for key in required_keys:
    val = TRADING_CONFIG.get(key, 'MANQUANT')
    print(f"      {key}: {val}")

# =============================================================================
# 2. VERIFICATION ADAPTIVE_SIZING MODULE
# =============================================================================
print("\n[2/6] Verification module adaptive_sizing...")

from core.position.adaptive_sizing import (
    AdaptiveSizingManager,
    AdaptiveSizingConfig,
    load_adaptive_sizing_config,
    get_adaptive_sizing_manager,
    reset_adaptive_sizing_manager
)

# Test: load_adaptive_sizing_config charge depuis TRADING_CONFIG
config = load_adaptive_sizing_config()
tests_total += 1
if config.enabled == TRADING_CONFIG.get('adaptive_sizing_enabled', True):
    print(f"   [OK] load_adaptive_sizing_config() charge depuis TRADING_CONFIG")
    tests_passed += 1
else:
    print(f"   [FAIL] load_adaptive_sizing_config() ne charge pas depuis TRADING_CONFIG")

# =============================================================================
# 3. TEST PAR PAIRE (ISOLATION)
# =============================================================================
print("\n[3/6] Test sizing par paire (isolation)...")

reset_adaptive_sizing_manager()
manager = get_adaptive_sizing_manager()

# Simuler des trades sur 3 paires differentes
PAIR_A = "BTC/USDT:USDT"
PAIR_B = "ETH/USDT:USDT"
PAIR_C = "DOGE/USDT:USDT"

# PAIR_A: 5 trades, 4W/1L = 80% WR (excellent)
for _ in range(4):
    manager.record_trade(PAIR_A, 0.30, True)
manager.record_trade(PAIR_A, -0.15, False)

# PAIR_B: 5 trades, 2W/3L = 40% WR (mauvais)
for _ in range(2):
    manager.record_trade(PAIR_B, 0.25, True)
for _ in range(3):
    manager.record_trade(PAIR_B, -0.20, False)

# PAIR_C: 2 trades seulement (< min_trades, devrait rester a 1.0)
manager.record_trade(PAIR_C, 0.30, True)
manager.record_trade(PAIR_C, -0.10, False)

# Verifier l'isolation
mult_a = manager.get_size_multiplier(PAIR_A)
mult_b = manager.get_size_multiplier(PAIR_B)
mult_c = manager.get_size_multiplier(PAIR_C)

print(f"   {PAIR_A}: 4W/1L = 80% WR -> mult={mult_a:.2f}")
print(f"   {PAIR_B}: 2W/3L = 40% WR -> mult={mult_b:.2f}")
print(f"   {PAIR_C}: 1W/1L = 50% WR (< min_trades) -> mult={mult_c:.2f}")

# Test: Les multiplicateurs doivent etre differents
tests_total += 1
if mult_a > mult_b:
    print(f"   [OK] Paire A (80% WR) a un mult plus eleve que Paire B (40% WR)")
    tests_passed += 1
else:
    print(f"   [FAIL] mult_a ({mult_a}) devrait etre > mult_b ({mult_b})")

# Test: Paire C doit rester a 1.0 (pas assez de trades)
tests_total += 1
if mult_c == 1.0:
    print(f"   [OK] Paire C reste a mult=1.0 (trades < min_trades)")
    tests_passed += 1
else:
    print(f"   [FAIL] Paire C devrait avoir mult=1.0, a {mult_c}")

# =============================================================================
# 4. TEST RESET APRES GROSSE PERTE
# =============================================================================
print("\n[4/6] Test reset apres grosse perte...")

stats_before = manager.pair_stats.get(PAIR_A)
total_before = stats_before.total_trades if stats_before else 0
print(f"   Avant grosse perte: {PAIR_A} trades={total_before}, mult={manager.get_size_multiplier(PAIR_A):.2f}")

# Simuler grosse perte (> seuil)
big_loss = TRADING_CONFIG.get('adaptive_sizing_big_loss_threshold', -2.0)
manager.record_trade(PAIR_A, big_loss - 0.5, False)  # Perte > seuil

stats_after = manager.pair_stats.get(PAIR_A)
total_after = stats_after.total_trades if stats_after else 0
mult_after = manager.get_size_multiplier(PAIR_A)
print(f"   Apres grosse perte ({big_loss-0.5}%): trades={total_after}, mult={mult_after:.2f}")

tests_total += 1
if TRADING_CONFIG.get('adaptive_sizing_reset_big_loss', True):
    if total_after == 0:
        print(f"   [OK] Stats reset apres grosse perte (reset_big_loss=True)")
        tests_passed += 1
    else:
        print(f"   [FAIL] Stats non reset (trades={total_after})")
else:
    print(f"   [INFO] reset_big_loss=False, pas de reset attendu")
    tests_passed += 1

# =============================================================================
# 5. TEST SESSION (RAZ AU REDEMARRAGE)
# =============================================================================
print("\n[5/6] Test session (RAZ au redemarrage)...")

# Simuler un "redemarrage" en reset du manager
stats_pair_b = manager.pair_stats.get(PAIR_B)
trades_before_reset = stats_pair_b.total_trades if stats_pair_b else 0
print(f"   Avant reset: {PAIR_B} trades={trades_before_reset}")

reset_adaptive_sizing_manager()
manager = get_adaptive_sizing_manager()

stats_pair_b_after = manager.pair_stats.get(PAIR_B)
trades_after_reset = stats_pair_b_after.total_trades if stats_pair_b_after else 0
print(f"   Apres reset (simule redemarrage): {PAIR_B} trades={trades_after_reset}")

tests_total += 1
if trades_after_reset == 0:
    print(f"   [OK] Stats remises a zero apres reset (comme redemarrage backend)")
    tests_passed += 1
else:
    print(f"   [FAIL] Stats non reset (trades={trades_after_reset})")

# =============================================================================
# 6. TEST INTEGRATION POSITION_MANAGER
# =============================================================================
print("\n[6/6] Test integration position_manager...")

try:
    from core.position_manager import PositionManager
    
    # Verifier que record_trade_for_adaptive_sizing existe
    tests_total += 1
    if hasattr(PositionManager, 'record_trade_for_adaptive_sizing'):
        print(f"   [OK] PositionManager.record_trade_for_adaptive_sizing existe")
        tests_passed += 1
    else:
        print(f"   [FAIL] PositionManager.record_trade_for_adaptive_sizing n'existe pas")
    
    # Verifier que calculate_position_size utilise adaptive_sizing
    import inspect
    source = inspect.getsource(PositionManager.calculate_position_size)
    tests_total += 1
    if 'adaptive_sizing' in source.lower() or 'get_size_multiplier' in source:
        print(f"   [OK] calculate_position_size integre le sizing adaptatif")
        tests_passed += 1
    else:
        print(f"   [FAIL] calculate_position_size n'integre pas le sizing adaptatif")
        
except Exception as e:
    print(f"   [WARN] Erreur test integration: {e}")
    tests_total += 2

# =============================================================================
# RESUME
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME")
print("=" * 70)

print(f"\n   Tests passes: {tests_passed}/{tests_total}")

if tests_passed == tests_total:
    print("\n   [SUCCESS] TOUS LES TESTS PASSENT - SIZING ADAPTATIF FONCTIONNEL")
else:
    print(f"\n   [WARNING] {tests_total - tests_passed} TEST(S) ECHOUE(S)")

# =============================================================================
# EXPLICATION DU SYSTEME
# =============================================================================
print("\n" + "=" * 70)
print("  EXPLICATION DU SYSTEME")
print("=" * 70)

print("""
   SIZING ADAPTATIF PAR PAIRE/SESSION
   -----------------------------------
   
   1. PAR PAIRE: Chaque symbole a ses propres stats (wins, losses, winrate).
      - BTC/USDT peut avoir mult=1.50 (excellent WR)
      - DOGE/USDT peut avoir mult=0.50 (mauvais WR)
      - Les multiplicateurs sont independants.
   
   2. PAR SESSION: Les stats sont en memoire (RAM).
      - Au redemarrage du backend, toutes les stats sont remises a zero.
      - Identique au comportement de dashboard.stats / graphiques / tradehistory.
   
   3. RESET APRES (HEURES):
      - Si aucun trade sur une paire pendant X heures, ses stats sont reset.
      - Exemple: adaptive_sizing_reset_hours=8
        -> Pas de trade BTC depuis 8h? Stats BTC remises a zero.
      - Permet de "repartir a zero" apres une longue pause.
   
   4. SEUIL GROSSE PERTE (%):
      - Si une perte depasse ce seuil, les stats de la paire sont reset.
      - Exemple: adaptive_sizing_big_loss_threshold=-2.0%
        -> Perte de -2.5% sur ETH? Stats ETH remises a zero.
      - Protege contre l'effet "je continue a trader une paire perdante".
      - Activable/desactivable via adaptive_sizing_reset_big_loss.
   
   5. SEUILS DE WIN RATE:
      - excellent_wr (75%+): mult = 1.50 (trade 50% plus gros)
      - good_wr (60-75%): mult = 1.25 (trade 25% plus gros)
      - normal (40-60%): mult = 1.00 (taille normale)
      - poor_wr (30-40%): mult = 0.70 (trade 30% plus petit)
      - very_poor_wr (<30%): mult = 0.50 (trade 50% plus petit)
""")

print("=" * 70)

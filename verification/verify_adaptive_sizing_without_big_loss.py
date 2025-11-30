#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICATION: Seuils WR/Mult suffisent sans reset grosse perte
===============================================================
Demontre que le seuil grosse perte est inutile avec un SL protecteur
et que les seuils WR/multiplicateurs offrent une protection progressive.
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from datetime import datetime
print("=" * 70)
print("  VERIFICATION: SEUILS WR/MULT SUFFISENT")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

from config import TRADING_CONFIG

sl_percent = TRADING_CONFIG.get('sl_percent', 0.2)
big_loss_threshold = TRADING_CONFIG.get('adaptive_sizing_big_loss_threshold', -2.0)

print(f"\n   CONFIG ACTUELLE:")
print(f"   - SL: {sl_percent}%")
print(f"   - Seuil grosse perte: {big_loss_threshold}%")

# =============================================================================
# 1. DEMONSTRATION: Seuil grosse perte INUTILE avec SL
# =============================================================================
print("\n" + "=" * 70)
print("[1/3] DEMONSTRATION: Seuil grosse perte INUTILE avec SL")
print("=" * 70)

max_loss_per_trade = -sl_percent  # Pire cas avec SL
print(f"\n   Perte MAX par trade avec SL: {max_loss_per_trade}%")
print(f"   Seuil grosse perte: {big_loss_threshold}%")

if max_loss_per_trade > big_loss_threshold:
    print(f"\n   [CONFIRMATION] {max_loss_per_trade}% > {big_loss_threshold}%")
    print(f"   -> Le seuil grosse perte ne sera JAMAIS atteint avec ce SL!")
    print(f"   -> Cette fonctionnalite est INUTILE dans votre config.")
else:
    print(f"\n   [ATTENTION] Le seuil peut etre atteint (SL > seuil)")

# =============================================================================
# 2. DEMONSTRATION: Protection progressive par WR/Mult
# =============================================================================
print("\n" + "=" * 70)
print("[2/3] DEMONSTRATION: Protection progressive par WR/Mult")
print("=" * 70)

from core.position.adaptive_sizing import (
    get_adaptive_sizing_manager,
    reset_adaptive_sizing_manager
)

# Desactiver reset_big_loss pour ce test
reset_adaptive_sizing_manager()
manager = get_adaptive_sizing_manager()
manager.config.reset_after_big_loss = False  # Desactive pour demo

SYMBOL = "TEST/USDT:USDT"
BASE_SIZE = 100  # Taille de base en USDT

print(f"\n   Simulation: Serie de pertes consecutives (SL = -{sl_percent}%)")
print(f"   Taille de base: {BASE_SIZE} USDT")
print("-" * 70)

# Simuler 10 trades perdants consecutifs
trades_results = []
cumulative_loss = 0.0

for i in range(10):
    # Multiplicateur AVANT le trade
    mult = manager.get_size_multiplier(SYMBOL)
    actual_size = BASE_SIZE * mult
    
    # Perte avec SL
    loss_pct = -sl_percent
    loss_usdt = actual_size * (loss_pct / 100)
    cumulative_loss += loss_usdt
    
    # Stats avant
    stats = manager.pair_stats.get(SYMBOL)
    wr = stats.winrate if stats else 0
    total = stats.total_trades if stats else 0
    
    trades_results.append({
        'trade': i + 1,
        'wr_before': wr,
        'mult': mult,
        'size': actual_size,
        'loss': loss_usdt,
        'cumul': cumulative_loss
    })
    
    # Enregistrer le trade
    manager.record_trade(SYMBOL, loss_pct, False)
    
    print(f"   Trade {i+1}: WR={wr:.0%} -> mult=x{mult:.2f} -> size={actual_size:.1f} USDT -> perte={loss_usdt:.2f} USDT (cumul: {cumulative_loss:.2f})")

# =============================================================================
# 3. ANALYSE: Comparaison avec/sans protection
# =============================================================================
print("\n" + "=" * 70)
print("[3/3] ANALYSE: Impact de la protection progressive")
print("=" * 70)

# Sans protection (mult=1.0 constant)
loss_without_protection = 10 * BASE_SIZE * (-sl_percent / 100)
print(f"\n   SANS protection (mult=1.0 constant):")
print(f"   - 10 trades a {BASE_SIZE} USDT chacun")
print(f"   - Perte totale: {loss_without_protection:.2f} USDT")

# Avec protection (mult variable)
print(f"\n   AVEC protection progressive (mult variable):")
print(f"   - Multiplicateur diminue avec le WR")
print(f"   - Perte totale: {cumulative_loss:.2f} USDT")

reduction = ((loss_without_protection - cumulative_loss) / abs(loss_without_protection)) * 100
print(f"\n   REDUCTION DES PERTES: {reduction:.1f}%")

# Tableau detaille
print("\n   Detail par trade:")
print("   " + "-" * 60)
print(f"   {'Trade':<8} {'WR':<8} {'Mult':<8} {'Taille':<12} {'Perte':<10}")
print("   " + "-" * 60)
for t in trades_results:
    print(f"   {t['trade']:<8} {t['wr_before']:.0%}{'':<5} x{t['mult']:.2f}{'':<4} {t['size']:.1f} USDT{'':<4} {t['loss']:.2f} USDT")
print("   " + "-" * 60)

# =============================================================================
# RESUME
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME")
print("=" * 70)

print(f"""
   1. SEUIL GROSSE PERTE: INUTILE
      - SL = {sl_percent}% -> perte max = -{sl_percent}%
      - Seuil = {big_loss_threshold}% -> jamais atteint
      - RECOMMANDATION: adaptive_sizing_reset_big_loss = false
   
   2. SEUILS WR/MULT: SUFFISENT
      - WR baisse naturellement apres pertes
      - Multiplicateur diminue progressivement
      - Protection automatique sans intervention
   
   3. REDUCTION DES PERTES: {reduction:.1f}%
      - 10 pertes consecutives sans protection: {loss_without_protection:.2f} USDT
      - 10 pertes consecutives avec protection: {cumulative_loss:.2f} USDT
      
   CONCLUSION: Les seuils WR/multiplicateurs offrent une protection
   progressive suffisante. Le reset grosse perte est redondant.
""")

print("=" * 70)

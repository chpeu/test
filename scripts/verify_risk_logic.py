#!/usr/bin/env python3
"""
Script de verification: Logique de gestion de risque (Streak & Recovery)

Verifie que:
1. Recovery Mode prend le dessus sur Streak Multiplier en cas de pertes (pas de cumul)
2. Streak Multiplier (bonus gains) fonctionne toujours
3. Les reductions de taille sont correctes selon les niveaux de perte
"""

import sys
import os
import logging
from dataclasses import dataclass

# Ajouter le chemin racine pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock des configurations
@dataclass
class MockConfig:
    win_streak: int = 0
    loss_streak: int = 0
    
# Mock de RecoveryModeManager pour eviter les dependances complexes
class MockRecoveryModeManager:
    def __init__(self):
        self.levels = [
            {'trigger_loss_streak': 2, 'position_size_reduction': 0.85},
            {'trigger_loss_streak': 3, 'position_size_reduction': 0.70},
            {'trigger_loss_streak': 5, 'position_size_reduction': 0.50}
        ]
    
    def get_position_size_multiplier(self, loss_streak: int) -> float:
        multiplier = 1.0
        for level in self.levels:
            if loss_streak >= level['trigger_loss_streak']:
                multiplier = level['position_size_reduction']
        return multiplier

# Classe de test qui simule PositionManager.calculate_position_size
class TestRiskManager:
    def __init__(self):
        self.config = MockConfig()
        self.recovery_mode = MockRecoveryModeManager()
        self.logger = logging.getLogger("TestRiskManager")
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        self.logger.addHandler(handler)

    # C'est une COPIE de la methode modifiee dans core/position_manager.py
    # Cela permet de tester la logique isolee
    def calculate_mults(self) -> float:
        # 1. Multiplicateur selon streaks (Gains uniquement)
        streak_mult = 1.0
        
        # 🟢 BOOST GAINS : Si on est sur une série de victoires, on augmente
        if self.config.win_streak >= 3:
            streak_mult = 1.1  # +10%
            
        # 🔴 PROTECTION PERTES : Gérée par le Recovery Mode
        # On n'applique pas de réduction simple ici pour éviter le double emploi
        
        # Recovery Mode - Réduction de taille progressive
        recovery_mult = self.recovery_mode.get_position_size_multiplier(self.config.loss_streak)
        
        if recovery_mult < 1.0:
            # Si le Recovery Mode est actif, il dicte la réduction
            # Cela remplace tout multiplicateur de streak précédent
            streak_mult = recovery_mult
            print(f"  [DEBUG] Recovery Mode Actif: {recovery_mult:.2f} (Streak {self.config.loss_streak} pertes)")
        else:
            print(f"  [DEBUG] Mode Normal: Streak Mult {streak_mult:.2f} (Streak {self.config.win_streak} wins)")
            
        return streak_mult

def run_tests():
    print("=" * 60)
    print("VERIFICATION LOGIQUE RISQUE (Streak vs Recovery)")
    print("=" * 60)
    
    manager = TestRiskManager()
    tests_passed = 0
    tests_failed = 0
    
    # TEST 1: Cas Normal (0 win, 0 loss)
    print("\n--- Test 1: Normal (0 win, 0 loss) ---")
    manager.config.win_streak = 0
    manager.config.loss_streak = 0
    mult = manager.calculate_mults()
    expected = 1.0
    if abs(mult - expected) < 0.001:
        print(f"[OK] PASS: Multiplicateur = {mult} (Attendu: {expected})")
        tests_passed += 1
    else:
        print(f"[FAIL] FAIL: Multiplicateur = {mult} (Attendu: {expected})")
        tests_failed += 1
        
    # TEST 2: Boost Gains (3 wins)
    print("\n--- Test 2: Boost Gains (3 wins) ---")
    manager.config.win_streak = 3
    manager.config.loss_streak = 0
    mult = manager.calculate_mults()
    expected = 1.1
    if abs(mult - expected) < 0.001:
        print(f"[OK] PASS: Multiplicateur = {mult} (Attendu: {expected})")
        tests_passed += 1
    else:
        print(f"[FAIL] FAIL: Multiplicateur = {mult} (Attendu: {expected})")
        tests_failed += 1
        
    # TEST 3: Recovery Niveau 1 (2 pertes)
    # AVANT le fix: 0.85 (streak) * 0.85 (recovery) = 0.7225
    # APRES le fix: 0.85 (recovery seulement)
    print("\n--- Test 3: Recovery Niveau 1 (2 pertes) ---")
    manager.config.win_streak = 0
    manager.config.loss_streak = 2
    mult = manager.calculate_mults()
    expected = 0.85
    if abs(mult - expected) < 0.001:
        print(f"[OK] PASS: Multiplicateur = {mult} (Attendu: {expected})")
        tests_passed += 1
    else:
        print(f"[FAIL] FAIL: Multiplicateur = {mult} (Attendu: {expected}) - Double penalite detectee!")
        tests_failed += 1

    # TEST 4: Recovery Niveau 2 (3 pertes)
    # AVANT le fix: 0.85 (streak) * 0.70 (recovery) = 0.595
    # APRES le fix: 0.70 (recovery seulement)
    print("\n--- Test 4: Recovery Niveau 2 (3 pertes) ---")
    manager.config.win_streak = 0
    manager.config.loss_streak = 3
    mult = manager.calculate_mults()
    expected = 0.70
    if abs(mult - expected) < 0.001:
        print(f"[OK] PASS: Multiplicateur = {mult} (Attendu: {expected})")
        tests_passed += 1
    else:
        print(f"[FAIL] FAIL: Multiplicateur = {mult} (Attendu: {expected})")
        tests_failed += 1
        
    # TEST 5: Recovery Niveau 3 (5 pertes)
    print("\n--- Test 5: Recovery Niveau 3 (5 pertes) ---")
    manager.config.win_streak = 0
    manager.config.loss_streak = 5
    mult = manager.calculate_mults()
    expected = 0.50
    if abs(mult - expected) < 0.001:
        print(f"[OK] PASS: Multiplicateur = {mult} (Attendu: {expected})")
        tests_passed += 1
    else:
        print(f"[FAIL] FAIL: Multiplicateur = {mult} (Attendu: {expected})")
        tests_failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTAT: {tests_passed}/{tests_passed + tests_failed} tests passes")
    print("=" * 60)
    
    return tests_failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

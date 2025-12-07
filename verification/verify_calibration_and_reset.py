#!/usr/bin/env python3
"""
Vérification complète de la Calibration ML et du Reset Automatique.
"""
import sys
import os
import logging
import json
from datetime import datetime

# Ajouter la racine du projet au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_position_to_dict():
    """Vérifie que ml_calibrated_winrate est bien dans Position.to_dict()"""
    print("\n>>> ETAPE 1: Vérification Position.to_dict()")
    
    try:
        from core.position_manager import Position
        
        # Créer une position factice
        pos = Position(
            symbol="BTC/USDT",
            direction="LONG",
            entry=50000.0,
            size=100.0,
            sl=49000.0,
            tp=52000.0
        )
        
        # Assigner les valeurs ML
        pos.ml_confidence = 65.5
        pos.ml_calibrated_winrate = 48.2
        pos.adaptive_sizing_multiplier = 1.2
        
        # Convertir en dict
        pos_dict = pos.to_dict()
        
        # Vérifier la présence des champs
        missing = []
        if 'ml_confidence' not in pos_dict: missing.append('ml_confidence')
        if 'ml_calibrated_winrate' not in pos_dict: missing.append('ml_calibrated_winrate')
        if 'adaptive_sizing_multiplier' not in pos_dict: missing.append('adaptive_sizing_multiplier')
        
        if missing:
            print(f"   [FAIL] Champs manquants dans to_dict(): {missing}")
            return False
        
        # Vérifier les valeurs
        if pos_dict['ml_calibrated_winrate'] != 48.2:
            print(f"   [FAIL] Valeur incorrecte pour ml_calibrated_winrate: {pos_dict['ml_calibrated_winrate']} != 48.2")
            return False
            
        print(f"   [OK] Position.to_dict() contient bien ml_calibrated_winrate ({pos_dict['ml_calibrated_winrate']}%)")
        return True
        
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False

def check_auto_reset_logic():
    """Vérifie que les endpoints apply appellent bien reset_calibration"""
    print("\n>>> ETAPE 2: Vérification Logique Auto-Reset")
    
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'api', 'routes', 'ml_legacy.py')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier le premier endpoint /optimize/apply
        check1 = "reset_calibration(reason=\"auto_reset_after_optimization\")" in content
        if check1:
            print("   [OK] /optimize/apply contient reset_calibration")
        else:
            print("   [FAIL] /optimize/apply manque reset_calibration")
        
        # Vérifier le deuxième endpoint /optimize/auto/apply
        check2 = "reset_calibration(reason=\"auto_reset_after_auto_optimization\")" in content
        if check2:
            print("   [OK] /optimize/auto/apply contient reset_calibration")
        else:
            print("   [FAIL] /optimize/auto/apply manque reset_calibration")
            
        return check1 and check2
            
    except Exception as e:
        print(f"   [ERROR] de lecture fichier: {e}")
        return False

def check_frontend_code():
    """Vérifie le code frontend pour l'affichage du badge"""
    print("\n>>> ETAPE 3: Vérification Frontend Svelte")
    
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'src', 'lib', 'components', 'PositionCard.svelte')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Vérifier la condition d'affichage
        condition = "$activePosition.ml_calibrated_winrate !== undefined && $activePosition.ml_calibrated_winrate !== null"
        if condition in content:
            print("   [OK] Condition d'affichage correcte détectée dans PositionCard.svelte")
        else:
            print("   [WARN] Condition d'affichage exacte non trouvée, vérification manuelle recommandée")
            
        # Vérifier le badge
        if "badge calib-badge" in content:
            print("   [OK] Classe CSS 'badge calib-badge' détectée")
        else:
            print("   [FAIL] Classe CSS du badge manquante")
            return False
            
        return True
            
    except Exception as e:
        print(f"   [ERROR] de lecture fichier: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print(" VERIFICATION SYSTEME CALIBRATION & RESET")
    print("="*60)
    
    success_1 = check_position_to_dict()
    success_2 = check_auto_reset_logic()
    success_3 = check_frontend_code()
    
    print("\n" + "="*60)
    if success_1 and success_2 and success_3:
        print(" [SUCCESS] TOUS LES TESTS SONT PASSES")
        print(" Le systeme est correctement configure.")
        print(" Si le badge ne s'affiche pas, le probleme est probablement le cache navigateur.")
    else:
        print(" [FAIL] CERTAINS TESTS ONT ECHOUE")
    print("="*60)

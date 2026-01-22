#!/usr/bin/env python3
"""
🔧 Test du système d'auto-reset de la calibration ML

Ce script teste et démontre le nouveau système d'auto-reset automatique
de la calibration when un nouveau modèle GB est détecté.

Usage:
    python test_calibration_auto_reset.py
"""

import sys
import os
import asyncio
import logging

# Ajouter le répertoire du projet au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_model_info_detection():
    """Test la détection des informations du modèle actuel"""
    print("\n=== TEST 1: Détection Info Modèle ===")
    
    try:
        from ml.calibration import MLCalibrationManager
        
        calibration_manager = MLCalibrationManager()
        model_info = calibration_manager.get_current_model_info()
        
        print(f"[OK] Modèle détecté:")
        print(f"   Timestamp: {model_info.get('timestamp', 'unknown')}")
        print(f"   Type: {model_info.get('model_type', 'unknown')}")
        print(f"   Features: {model_info.get('n_features', 0)}")
        print(f"   Métriques: {model_info.get('metrics', {})}")
        
        return model_info
        
    except Exception as e:
        print(f"[ERROR] Erreur détection modèle: {e}")
        return None

def test_calibration_version_check():
    """Test la vérification de version de calibration"""
    print("\n=== TEST 2: Version Calibration Actuelle ===")
    
    try:
        from ml.calibration import MLCalibrationManager
        
        calibration_manager = MLCalibrationManager()
        last_version = calibration_manager.get_last_calibration_model_version()
        
        print(f"Dernière version calibrée: {last_version}")
        
        return last_version
        
    except Exception as e:
        print(f"[ERROR] Erreur vérification version: {e}")
        return None

def test_auto_reset_detection():
    """Test la détection automatique et reset"""
    print("\n=== TEST 3: Auto-Reset Detection ===")
    
    try:
        from ml.calibration import MLCalibrationManager
        
        calibration_manager = MLCalibrationManager()
        
        print("[INFO] Vérification changement modèle...")
        reset_performed = calibration_manager.check_model_change_and_auto_reset()
        
        if reset_performed:
            print("[OK] Reset automatique effectué!")
        else:
            print("[INFO] Pas de reset nécessaire")
            
        return reset_performed
        
    except Exception as e:
        print(f"[ERROR] Erreur auto-reset: {e}")
        return False

def test_should_take_trade_with_auto_reset():
    """Test should_take_trade qui inclut l'auto-reset"""
    print("\n=== TEST 4: Should Take Trade avec Auto-Reset ===")
    
    try:
        from ml.calibration import MLCalibrationManager
        
        calibration_manager = MLCalibrationManager()
        
        # Test avec différentes confidences
        test_cases = [
            ("LONG", 50.0),
            ("SHORT", 45.0),
            ("LONG", 60.0)
        ]
        
        for direction, confidence in test_cases:
            print(f"\nTest: {direction} avec confidence {confidence}%")
            should_take, calibrated_wr, reason = calibration_manager.should_take_trade(direction, confidence)
            
            print(f"   Résultat: {'[ACCEPT]' if should_take else '[REJECT]'}")
            print(f"   WR Calibré: {calibrated_wr}%")
            print(f"   Raison: {reason}")
        
    except Exception as e:
        print(f"[ERROR] Erreur test should_take_trade: {e}")

def test_manual_reset():
    """Test le reset manuel pour comparaison"""
    print("\n=== TEST 5: Reset Manuel (Comparaison) ===")
    
    try:
        from ml.calibration import MLCalibrationManager
        
        calibration_manager = MLCalibrationManager()
        
        print("[INFO] Exécution reset manuel...")
        success = calibration_manager.reset_calibration("test_manual_reset")
        
        if success:
            print("[OK] Reset manuel réussi")
        else:
            print("[ERROR] Reset manuel échoué")
            
        return success
        
    except Exception as e:
        print(f"[ERROR] Erreur reset manuel: {e}")
        return False

def print_summary(model_info, last_version, auto_reset_performed):
    """Affiche un résumé des résultats"""
    print("\n" + "="*60)
    print("\n=== RESUMÉ DES TESTS ===")
    print("="*60)
    
    if model_info:
        model_timestamp = model_info.get('timestamp', 'unknown')
        print(f"Modèle Actuel: {model_timestamp}")
        print(f"Features: {model_info.get('n_features', 0)}")
    else:
        model_timestamp = 'unknown'
        print("[ERROR] Modèle non détecté")
    
    print(f"Dernière Calibration: {last_version}")
    
    if model_timestamp != 'unknown' and last_version:
        if model_timestamp == last_version:
            print("[OK] Modèle et calibration synchronisés")
        else:
            print("[WARNING] DÉSYNCHRONISATION DÉTECTÉE!")
            print(f"   Modèle: {model_timestamp}")
            print(f"   Calibration: {last_version}")
    
    if auto_reset_performed:
        print("[OK] Auto-reset EXÉCUTÉ - Calibration mise à jour")
    else:
        print("[INFO] Auto-reset non nécessaire")
    
    print("\n**RECOMMANDATIONS:**")
    if model_info and model_info.get('timestamp') == '2025-12-20T00:41:39.610296':
        print("[OK] Nouveau modèle GB du 20/12/2025 détecté correctement")
    
    if last_version is None:
        print("[INFO] Première utilisation - calibration va apprendre progressivement")
    elif auto_reset_performed:
        print("[OK] Calibration reset - statistiques fraîches pour nouveau modèle")
    
    print("="*60)

def main():
    """Fonction principale de test"""
    print("=== TEST AUTO-RESET CALIBRATION ML ===")
    print("Objectif: Vérifier que la calibration se reset automatiquement")
    print("           quand un nouveau modèle GB est détecté")
    
    # Exécuter tous les tests
    model_info = test_model_info_detection()
    last_version = test_calibration_version_check()
    auto_reset_performed = test_auto_reset_detection()
    
    test_should_take_trade_with_auto_reset()
    test_manual_reset()
    
    # Résumé final
    print_summary(model_info, last_version, auto_reset_performed)

if __name__ == "__main__":
    main()

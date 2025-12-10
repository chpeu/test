#!/usr/bin/env python3
"""
Verification complete des parametres HistGradientBoosting
- Verifie config_overrides.json
- Verifie TRADING_CONFIG charge
- Verifie le modele sauvegarde
- Teste le seuil de confiance
"""

import os
import sys
import json

# Ajouter le chemin racine
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_check(name, expected, actual, unit=""):
    match = expected == actual
    icon = "[OK]" if match else "[FAIL]"
    exp_str = f"{expected}{unit}"
    act_str = f"{actual}{unit}"
    status = "OK" if match else f"MISMATCH (attendu: {exp_str})"
    print(f"  {icon} {name}: {act_str} {status if not match else ''}")
    return match

def verify_config_overrides():
    """Vérifier config_overrides.json"""
    print_header("1. VÉRIFICATION config_overrides.json")
    
    config_path = os.path.join(ROOT_DIR, "config_overrides.json")
    
    if not os.path.exists(config_path):
        print("  [FAIL] Fichier config_overrides.json introuvable!")
        return False, {}
    
    with open(config_path, 'r') as f:
        overrides = json.load(f)
    
    # Paramètres attendus (valeurs optimisées)
    expected_params = {
        'gb_max_depth': 4,
        'gb_learning_rate': 0.08,
        'gb_min_samples_leaf': 50,
        'gb_max_iter': 75,
        'gb_n_features': 20,
        'gb_l2_regularization': 0.5,
        'gb_min_confidence': 0.45,
        'gb_filter_enabled': True,
        'gb_model_type': 'histgb'
    }
    
    all_ok = True
    found_params = {}
    
    for param, expected in expected_params.items():
        actual = overrides.get(param)
        found_params[param] = actual
        if actual is None:
            print(f"  [FAIL] {param}: MANQUANT")
            all_ok = False
        elif isinstance(expected, float):
            # Comparaison float avec tolérance
            if abs(actual - expected) < 0.0001:
                print(f"  [OK] {param}: {actual}")
            else:
                print(f"  [FAIL] {param}: {actual} (attendu: {expected})")
                all_ok = False
        else:
            if actual == expected:
                print(f"  [OK] {param}: {actual}")
            else:
                print(f"  [FAIL] {param}: {actual} (attendu: {expected})")
                all_ok = False
    
    return all_ok, found_params

def verify_trading_config():
    """Vérifier que TRADING_CONFIG est correctement chargé"""
    print_header("2. VÉRIFICATION TRADING_CONFIG (runtime)")
    
    try:
        from config import TRADING_CONFIG
        
        params_to_check = [
            'gb_max_depth',
            'gb_learning_rate', 
            'gb_min_samples_leaf',
            'gb_max_iter',
            'gb_n_features',
            'gb_l2_regularization',
            'gb_min_confidence',
            'gb_filter_enabled',
            'gb_model_type'
        ]
        
        all_ok = True
        for param in params_to_check:
            value = TRADING_CONFIG.get(param)
            if value is not None:
                print(f"  [OK] {param}: {value}")
            else:
                print(f"  [FAIL] {param}: NON DEFINI dans TRADING_CONFIG")
                all_ok = False
        
        return all_ok, TRADING_CONFIG
        
    except Exception as e:
        print(f"  [FAIL] Erreur import config: {e}")
        return False, {}

def verify_model_metadata():
    """Vérifier les métadonnées du modèle sauvegardé"""
    print_header("3. VÉRIFICATION MODÈLE SAUVEGARDÉ")
    
    metadata_path = os.path.join(ROOT_DIR, "optimization", "saved_models", "best_classifier_metadata.json")
    
    if not os.path.exists(metadata_path):
        print("  [WARN] Fichier metadata introuvable - modele pas encore entraine?")
        return False, {}
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    print(f"  Date entrainement: {metadata.get('training_date', 'N/A')}")
    print(f"  Type modele: {metadata.get('model_type', 'N/A')}")
    print(f"  Features: {metadata.get('n_features_selected', 'N/A')}")
    
    # Métriques
    metrics = metadata.get('metrics', {})
    print(f"\n  Metriques:")
    print(f"     - Test Accuracy: {metrics.get('test_accuracy', 0)*100:.1f}%")
    print(f"     - F1 Score: {metrics.get('f1_score', 0):.3f}")
    print(f"     - Precision: {metrics.get('precision', 0):.3f}")
    print(f"     - Recall: {metrics.get('recall', 0):.3f}")
    print(f"     - ROC-AUC: {metrics.get('roc_auc', 0):.3f}")
    
    # Hyperparamètres du modèle
    hyperparams = metadata.get('hyperparameters', {})
    if hyperparams:
        print(f"\n  Hyperparametres modele:")
        for k, v in hyperparams.items():
            print(f"     - {k}: {v}")
    
    return True, metadata

def verify_confidence_threshold():
    """Tester le seuil de confiance"""
    print_header("4. TEST SEUIL DE CONFIANCE")
    
    try:
        from config import TRADING_CONFIG
        import numpy as np
        
        threshold = TRADING_CONFIG.get('gb_min_confidence', 0.5)
        filter_enabled = TRADING_CONFIG.get('gb_filter_enabled', True)
        
        print(f"  Seuil configure: {threshold*100:.1f}%")
        print(f"  Filtre active: {'OUI' if filter_enabled else 'NON'}")
        
        # Simuler des prédictions
        test_probas = [0.30, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 0.80]
        
        print(f"\n  Simulation filtrage (seuil = {threshold*100:.0f}%):")
        print(f"  {'Proba':<10} {'Décision':<15} {'Action'}")
        print(f"  {'-'*40}")
        
        accepted = 0
        rejected = 0
        
        for proba in test_probas:
            if filter_enabled:
                if proba >= threshold:
                    decision = "[OK] ACCEPTE"
                    action = "Trade exécuté"
                    accepted += 1
                else:
                    decision = "[X] REJETE"
                    action = f"Confiance trop basse ({proba*100:.0f}% < {threshold*100:.0f}%)"
                    rejected += 1
            else:
                decision = "[-] BYPASS"
                action = "Filtre désactivé"
                accepted += 1
            
            print(f"  {proba*100:>5.0f}%     {decision:<15} {action}")
        
        print(f"\n  Resume: {accepted} acceptes, {rejected} rejetes")
        
        # Vérifier la cohérence
        if filter_enabled and threshold == 0.45:
            # Probas >= 0.45: 0.45, 0.50, 0.55, 0.60, 0.70, 0.80 = 6 accepted
            # Probas < 0.45: 0.30, 0.40 = 2 rejected
            expected_accepted = 6
            expected_rejected = 2
            if accepted == expected_accepted and rejected == expected_rejected:
                print(f"  [OK] Comportement du seuil CORRECT")
                return True
            else:
                print(f"  [FAIL] Comportement inattendu! (attendu: {expected_accepted} acceptes, {expected_rejected} rejetes)")
                return False
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] Erreur test seuil: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_model_loaded():
    """Vérifier que le modèle peut être chargé"""
    print_header("5. TEST CHARGEMENT MODÈLE")
    
    model_path = os.path.join(ROOT_DIR, "optimization", "saved_models", "best_classifier_latest.pkl")
    
    if not os.path.exists(model_path):
        print("  [WARN] Modele non trouve - pas encore entraine?")
        return False
    
    try:
        import joblib
        model = joblib.load(model_path)
        
        print(f"  [OK] Modele charge: {type(model).__name__}")
        
        # Vérifier si c'est un Pipeline
        if hasattr(model, 'named_steps'):
            print(f"  Pipeline etapes: {list(model.named_steps.keys())}")
            
            # Vérifier le modèle final
            if 'model' in model.named_steps:
                final_model = model.named_steps['model']
                print(f"  Modele final: {type(final_model).__name__}")
                
                # Paramètres HistGradientBoosting
                if hasattr(final_model, 'max_iter'):
                    print(f"     - max_iter: {final_model.max_iter}")
                if hasattr(final_model, 'max_depth'):
                    print(f"     - max_depth: {final_model.max_depth}")
                if hasattr(final_model, 'learning_rate'):
                    print(f"     - learning_rate: {final_model.learning_rate}")
                if hasattr(final_model, 'min_samples_leaf'):
                    print(f"     - min_samples_leaf: {final_model.min_samples_leaf}")
                if hasattr(final_model, 'l2_regularization'):
                    print(f"     - l2_regularization: {final_model.l2_regularization}")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] Erreur chargement modele: {e}")
        return False

def run_verification():
    """Exécuter toutes les vérifications"""
    print("\n" + "="*60)
    print("  VERIFICATION COMPLETE HISTGRADIENTBOOSTING")
    print("="*60)
    
    results = {}
    
    # 1. Config overrides
    ok1, params1 = verify_config_overrides()
    results['config_overrides'] = ok1
    
    # 2. Trading config
    ok2, params2 = verify_trading_config()
    results['trading_config'] = ok2
    
    # 3. Modèle metadata
    ok3, metadata = verify_model_metadata()
    results['model_metadata'] = ok3
    
    # 4. Seuil confiance
    ok4 = verify_confidence_threshold()
    results['confidence_threshold'] = ok4
    
    # 5. Chargement modèle
    ok5 = verify_model_loaded()
    results['model_load'] = ok5
    
    # Résumé
    print_header("RESUME VERIFICATION")
    
    all_ok = True
    for check, passed in results.items():
        icon = "[OK]" if passed else "[FAIL]"
        print(f"  {icon} {check}: {'OK' if passed else 'ECHEC'}")
        if not passed:
            all_ok = False
    
    print(f"\n  {'='*40}")
    if all_ok:
        print("  [OK] TOUTES LES VERIFICATIONS PASSEES")
        print("  Le systeme HistGradientBoosting est correctement configure!")
    else:
        print("  [WARN] CERTAINES VERIFICATIONS ONT ECHOUE")
        print("  Verifiez les erreurs ci-dessus.")
    
    return all_ok

if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)

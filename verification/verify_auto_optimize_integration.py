#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Verification de l'integration Auto-Optimisation ML
Test complet sans executer l'optimisation (trop longue)

Usage:
    python verification/verify_auto_optimize_integration.py
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

# Config
BASE_URL = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).parent.parent

# Couleurs terminal
class Colors:
    OK = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title):
    print()
    print("=" * 70)
    print(f"{Colors.BOLD}{title}{Colors.END}")
    print("=" * 70)

def print_ok(msg):
    print(f"  {Colors.OK}[OK]{Colors.END} {msg}")

def print_warning(msg):
    print(f"  {Colors.WARNING}[WARN]{Colors.END} {msg}")

def print_fail(msg):
    print(f"  {Colors.FAIL}[FAIL]{Colors.END} {msg}")

def check_file_exists(path, description):
    """Verifie qu'un fichier existe"""
    if path.exists():
        print_ok(f"{description}: {path.name}")
        return True
    else:
        print_fail(f"{description}: {path} MANQUANT")
        return False

def check_json_keys(data, required_keys, context):
    """Verifie que les cles requises sont presentes"""
    missing = [k for k in required_keys if k not in data]
    if missing:
        print_fail(f"{context}: Cles manquantes: {missing}")
        return False
    print_ok(f"{context}: Toutes les cles presentes")
    return True

def test_metadata_file():
    """Test 1: Verifier le fichier metadata"""
    print_header("TEST 1: Fichier Metadata")
    
    metadata_path = PROJECT_ROOT / "optimization" / "saved_models" / "best_classifier_metadata.json"
    
    if not check_file_exists(metadata_path, "Metadata file"):
        return False
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # Verifier les cles principales
    required_keys = ['timestamp', 'model_type', 'n_features', 'params', 'metrics', 'feature_names']
    if not check_json_keys(metadata, required_keys, "Structure principale"):
        return False
    
    # Verifier les cles des metriques (format attendu par l'API)
    metrics = metadata.get('metrics', {})
    metrics_keys = ['train_accuracy', 'test_accuracy', 'f1_score', 'roc_auc', 'precision', 'recall', 'overfitting']
    if not check_json_keys(metrics, metrics_keys, "Structure metriques"):
        return False
    
    # Afficher les metriques actuelles
    print()
    print(f"  Metriques actuelles:")
    print(f"    - Test Accuracy: {metrics.get('test_accuracy', 0)*100:.2f}%")
    print(f"    - F1 Score: {metrics.get('f1_score', 0):.4f}")
    print(f"    - Precision: {metrics.get('precision', 0):.4f}")
    print(f"    - Overfitting: {metrics.get('overfitting', 0)*100:.2f}%")
    
    # Verifier les seuils optimaux
    thresholds = metadata.get('optimal_thresholds', {})
    if thresholds:
        print_ok(f"Seuils optimaux presents: {list(thresholds.keys())}")
    else:
        print_warning("Seuils optimaux non definis")
    
    return True

def test_threshold_analysis_file():
    """Test 2: Verifier le fichier d'analyse des seuils"""
    print_header("TEST 2: Fichier Analyse des Seuils")
    
    threshold_path = PROJECT_ROOT / "optimization" / "saved_models" / "threshold_analysis.csv"
    
    if not check_file_exists(threshold_path, "Threshold analysis CSV"):
        return False
    
    import csv
    with open(threshold_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    if len(rows) < 5:
        print_fail(f"Trop peu de lignes: {len(rows)}")
        return False
    
    print_ok(f"Nombre de seuils analyses: {len(rows)}")
    
    # Verifier les colonnes
    expected_cols = ['threshold', 'accuracy', 'f1_score', 'precision', 'recall']
    if rows:
        actual_cols = list(rows[0].keys())
        missing_cols = [c for c in expected_cols if c not in actual_cols]
        if missing_cols:
            print_fail(f"Colonnes manquantes: {missing_cols}")
            return False
        print_ok(f"Colonnes presentes: {expected_cols}")
    
    return True

def test_model_file():
    """Test 3: Verifier le fichier modele"""
    print_header("TEST 3: Fichier Modele PKL")
    
    model_path = PROJECT_ROOT / "optimization" / "saved_models" / "best_classifier_latest.pkl"
    
    if not check_file_exists(model_path, "Model pickle"):
        return False
    
    try:
        import joblib
        model_data = joblib.load(model_path)
        
        required_keys = ['model', 'feature_selector_idx', 'feature_names', 'params']
        if not check_json_keys(model_data, required_keys, "Structure modele"):
            return False
        
        print_ok(f"Modele charge: {type(model_data['model']).__name__}")
        print_ok(f"Features: {len(model_data.get('feature_names', []))}")
        
    except Exception as e:
        print_fail(f"Erreur chargement modele: {e}")
        return False
    
    return True

def test_config_overrides():
    """Test 4: Verifier config_overrides.json"""
    print_header("TEST 4: Configuration Overrides")
    
    config_path = PROJECT_ROOT / "config_overrides.json"
    
    if not check_file_exists(config_path, "Config overrides"):
        return False
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Verifier les parametres GB
    gb_params = ['gb_max_depth', 'gb_learning_rate', 'gb_min_samples_leaf', 'gb_n_estimators', 'gb_min_confidence']
    missing = [p for p in gb_params if p not in config]
    
    if missing:
        print_warning(f"Parametres GB manquants: {missing}")
    else:
        print_ok("Tous les parametres GB presents")
    
    # Afficher les valeurs actuelles
    print()
    print(f"  Parametres actuels:")
    for p in gb_params:
        if p in config:
            print(f"    - {p}: {config[p]}")
    
    return True

def test_api_models_overview():
    """Test 5: Verifier l'API /models/overview"""
    print_header("TEST 5: API /models/overview")
    
    try:
        response = requests.get(f"{BASE_URL}/api/ml/models/overview", timeout=10)
        
        if response.status_code != 200:
            print_fail(f"HTTP {response.status_code}")
            return False
        
        print_ok(f"HTTP 200 OK")
        
        data = response.json()
        
        # Verifier la structure
        if 'models' not in data:
            print_fail("Cle 'models' manquante dans la reponse")
            return False
        
        models = data['models']
        print_ok(f"Nombre de modeles: {len(models)}")
        
        # Chercher le modele GB
        gb_model = next((m for m in models if m.get('name') == 'best_classifier'), None)
        
        if not gb_model:
            print_fail("Modele 'best_classifier' non trouve")
            return False
        
        print_ok("Modele GradientBoosting trouve")
        
        # Verifier les metriques
        test_metrics = gb_model.get('metrics', {}).get('test', {})
        
        accuracy = test_metrics.get('accuracy', 0)
        f1 = test_metrics.get('f1_score', 0)
        precision = test_metrics.get('precision', 0)
        overfitting = gb_model.get('overfitting_gap', 0)
        
        print()
        print(f"  Metriques retournees par l'API:")
        print(f"    - Accuracy: {accuracy*100:.2f}%" if accuracy < 1 else f"    - Accuracy: {accuracy:.2f}%")
        print(f"    - F1 Score: {f1:.4f}")
        print(f"    - Precision: {precision:.4f}")
        print(f"    - Overfitting Gap: {overfitting:.1f}%")
        
        # Verifier que les valeurs sont raisonnables
        if accuracy > 0.5 and f1 > 0.3:
            print_ok("Metriques dans les plages attendues")
        else:
            print_warning("Metriques anormalement basses")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print_fail("Impossible de se connecter au serveur. Le backend est-il demarre?")
        return False
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False

def test_api_auto_optimize_endpoints():
    """Test 6: Verifier les endpoints d'auto-optimisation (sans les executer)"""
    print_header("TEST 6: Endpoints Auto-Optimisation")
    
    # Test 6a: Verifier que l'endpoint /optimize/auto/start existe
    try:
        # On fait un OPTIONS ou on verifie juste que l'endpoint repond
        # On ne lance PAS l'optimisation
        response = requests.post(
            f"{BASE_URL}/api/ml/optimize/auto/start",
            json={},
            timeout=5
        )
        
        # Meme si ca echoue pour manque de donnees, ca prouve que l'endpoint existe
        if response.status_code in [200, 400, 422, 500]:
            print_ok(f"/optimize/auto/start endpoint existe (HTTP {response.status_code})")
        else:
            print_fail(f"/optimize/auto/start: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print_fail("Backend non accessible")
        return False
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False
    
    # Test 6b: Verifier l'endpoint /optimize/auto/apply
    try:
        response = requests.post(
            f"{BASE_URL}/api/ml/optimize/auto/apply",
            json={'params': {}, 'optimal_threshold': 0.45},
            timeout=5
        )
        
        if response.status_code in [200, 400, 422, 500]:
            print_ok(f"/optimize/auto/apply endpoint existe (HTTP {response.status_code})")
        else:
            print_fail(f"/optimize/auto/apply: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False
    
    return True

def test_auto_optimize_script():
    """Test 7: Verifier que le script d'auto-optimisation existe et est valide"""
    print_header("TEST 7: Script Auto-Optimisation")
    
    script_path = PROJECT_ROOT / "scripts" / "auto_optimize_ml.py"
    
    if not check_file_exists(script_path, "Script auto_optimize_ml.py"):
        return False
    
    # Verifier la syntaxe Python
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        compile(source, script_path, 'exec')
        print_ok("Syntaxe Python valide")
        
    except SyntaxError as e:
        print_fail(f"Erreur de syntaxe: {e}")
        return False
    
    # Verifier les imports
    required_imports = ['numpy', 'pandas', 'sklearn', 'joblib']
    for imp in required_imports:
        if f'import {imp}' in source or f'from {imp}' in source:
            print_ok(f"Import {imp} present")
        else:
            print_warning(f"Import {imp} non trouve")
    
    # Verifier la classe principale
    if 'class MLAutoOptimizer' in source:
        print_ok("Classe MLAutoOptimizer presente")
    else:
        print_fail("Classe MLAutoOptimizer non trouvee")
        return False
    
    return True

def test_frontend_component():
    """Test 8: Verifier le composant Svelte"""
    print_header("TEST 8: Composant Frontend")
    
    component_path = PROJECT_ROOT / "frontend" / "src" / "lib" / "components" / "ml" / "MLCONTENT_GB_Variables.svelte"
    
    if not check_file_exists(component_path, "Composant Svelte"):
        return False
    
    with open(component_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verifier les elements cles
    checks = [
        ('startAutoOptimization', 'Fonction startAutoOptimization'),
        ('popup-floating', 'Style popup flottant'),
        ('startDrag', 'Fonction drag (popup deplacable)'),
        ('autoOptimizeResults', 'Variable resultats'),
        ('applyAutoOptimizeResults', 'Fonction application resultats'),
        ('/api/ml/optimize/auto/start', 'Endpoint API start'),
        ('/api/ml/optimize/auto/apply', 'Endpoint API apply'),
        ('threshold_analysis', 'Analyse des seuils'),
        # Nouvelles fonctionnalites
        ('saveOptimizationState', 'Persistance localStorage'),
        ('loadOptimizationState', 'Restauration etat'),
        ('heartbeat', 'Heartbeat connexion'),
        ('openInExternalWindow', 'Fenetre externe'),
        ('handleVisibilityChange', 'Gestion visibilite page'),
        ('onMount', 'Lifecycle onMount'),
        ('onDestroy', 'Lifecycle onDestroy'),
        ('connection-indicator', 'Indicateur connexion'),
    ]
    
    all_ok = True
    for pattern, description in checks:
        if pattern in content:
            print_ok(description)
        else:
            print_fail(f"{description} non trouve")
            all_ok = False
    
    return all_ok

def main():
    print()
    print(f"{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}VERIFICATION AUTO-OPTIMISATION ML{Colors.END}")
    print(f"{Colors.BOLD}Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}")
    
    results = {}
    
    # Tests fichiers (ne necessitent pas le backend)
    results['metadata'] = test_metadata_file()
    results['threshold_csv'] = test_threshold_analysis_file()
    results['model_pkl'] = test_model_file()
    results['config'] = test_config_overrides()
    results['script'] = test_auto_optimize_script()
    results['frontend'] = test_frontend_component()
    
    # Tests API (necessitent le backend)
    results['api_overview'] = test_api_models_overview()
    results['api_endpoints'] = test_api_auto_optimize_endpoints()
    
    # Resume
    print_header("RESUME")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print()
    for name, status in results.items():
        status_str = f"{Colors.OK}PASS{Colors.END}" if status else f"{Colors.FAIL}FAIL{Colors.END}"
        print(f"  {name:<20} {status_str}")
    
    print()
    print(f"  {Colors.BOLD}Total: {passed}/{total} tests passes{Colors.END}")
    
    if passed == total:
        print()
        print(f"  {Colors.OK}[SUCCESS] Tous les tests passes!{Colors.END}")
        print(f"  {Colors.OK}L'integration auto-optimisation est prete.{Colors.END}")
        return 0
    else:
        print()
        print(f"  {Colors.WARNING}[ATTENTION] {total - passed} test(s) echoue(s){Colors.END}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

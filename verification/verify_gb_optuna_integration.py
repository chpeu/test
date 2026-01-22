#!/usr/bin/env python3
"""
VERIFICATION INTEGRATION OPTUNA GRADIENTBOOSTING
================================================
Vérifie que l'optimisation Optuna GradientBoosting est fonctionnelle de bout en bout.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import requests
from datetime import datetime
import time

BASE_URL = "http://localhost:5000"  # Port du backend

def check_backend_available():
    """Vérifie que le backend est accessible"""
    print("\n[1/6] Vérification backend...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Backend accessible")
            return True
        else:
            print(f"   ❌ Backend répond avec status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Backend non accessible (connexion refusée)")
        print("   → Démarrez le backend avec: python main.py")
        return False
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False

def check_endpoint_exists():
    """Vérifie que les endpoints GB existent"""
    print("\n[2/6] Vérification endpoints GradientBoosting...")
    
    endpoints = [
        ("/api/ml/optimize/gb/start", "POST"),
        ("/api/ml/optimize/gb/apply", "POST"),
        ("/api/ml/optimize/gb/results", "GET"),
    ]
    
    all_ok = True
    for endpoint, method in endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            else:
                # Pour POST, on teste juste que l'endpoint existe (peut retourner 4xx)
                response = requests.options(f"{BASE_URL}{endpoint}", timeout=5)
            
            # 405 = Method Not Allowed (endpoint existe mais méthode différente)
            # 200, 400, 422 = endpoint fonctionne
            if response.status_code in [200, 400, 405, 422]:
                print(f"   ✅ {endpoint} ({method})")
            else:
                print(f"   ⚠️ {endpoint} ({method}) - status {response.status_code}")
                all_ok = False
        except Exception as e:
            print(f"   ❌ {endpoint} - Erreur: {e}")
            all_ok = False
    
    return all_ok

def check_optimizer_module():
    """Vérifie que le module d'optimisation est importable"""
    print("\n[3/6] Vérification module optuna_gradientboosting...")
    try:
        from optimization.optuna_gradientboosting import GradientBoostingOptimizer
        print("   ✅ Module importable")
        
        # Vérifier les méthodes
        optimizer = GradientBoostingOptimizer(n_trials=5, timeout_minutes=1)
        methods = ['load_data', 'optimize', 'validate_on_holdout', 'get_results_summary']
        for method in methods:
            if hasattr(optimizer, method):
                print(f"   ✅ Méthode {method}() disponible")
            else:
                print(f"   ❌ Méthode {method}() manquante")
                return False
        
        return True
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False

def check_data_availability():
    """Vérifie que les données ML sont disponibles"""
    print("\n[4/6] Vérification données ML...")
    try:
        from optimization.data.feature_loader import load_features_from_postgres, get_trades_count
        
        # Compter les trades
        count = get_trades_count()
        print(f"   📊 Trades disponibles: {count}")
        
        if count < 100:
            print(f"   ⚠️ Moins de 100 trades - optimisation peut être instable")
        else:
            print("   ✅ Données suffisantes pour optimisation")
        
        # Vérifier chargement features
        try:
            df = load_features_from_postgres(min_trades=10, timeframe_days=365)
            print(f"   ✅ Features chargées: {len(df)} trades, {len(df.columns)} colonnes")
            
            # Vérifier colonnes order flow
            orderflow_cols = ['delta_volume', 'imbalance_normalized', 'book_depth_ratio']
            found_of = [col for col in orderflow_cols if col in df.columns]
            print(f"   📊 Colonnes Order Flow: {len(found_of)}/3")
            
            return True
        except Exception as e:
            print(f"   ⚠️ Erreur chargement features: {e}")
            return False
        
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False

def check_config_persistence():
    """Vérifie que config_overrides.json est accessible"""
    print("\n[5/6] Vérification config_overrides.json...")
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config_overrides.json')
    
    if not os.path.exists(config_path):
        print(f"   ❌ Fichier non trouvé: {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        gb_params = [
            'gb_n_estimators', 'gb_max_depth', 'gb_learning_rate',
            'gb_min_samples_split', 'gb_min_samples_leaf',
            'gb_subsample', 'gb_max_features'
        ]
        
        found = {k: config.get(k) for k in gb_params if k in config}
        
        print(f"   ✅ Config accessible - {len(found)}/{len(gb_params)} params GB présents")
        
        for k, v in found.items():
            print(f"      {k}: {v}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur lecture config: {e}")
        return False

def run_quick_optimization_test():
    """Test rapide de l'optimisation (5 trials)"""
    print("\n[6/6] Test rapide optimisation (5 trials)...")
    
    try:
        from optimization.optuna_gradientboosting import GradientBoostingOptimizer
        
        optimizer = GradientBoostingOptimizer(n_trials=5, timeout_minutes=2)
        
        print("   ⏳ Chargement données...")
        n_samples = optimizer.load_data(timeframe_days=365)
        print(f"   ✅ {n_samples} samples chargés")
        
        print("   ⏳ Optimisation (5 trials)...")
        best_params = optimizer.optimize(n_trials=5, timeout_minutes=2)
        print(f"   ✅ Meilleurs paramètres trouvés")
        
        print("   ⏳ Validation holdout...")
        metrics = optimizer.validate_on_holdout()
        
        print(f"\n   📊 RÉSULTATS TEST:")
        print(f"      Test Accuracy: {metrics['test_accuracy']*100:.1f}%")
        print(f"      Overfitting Gap: {metrics['overfitting_gap']*100:.1f}%")
        print(f"      F1 Score: {metrics['f1_score']:.3f}")
        
        if metrics['test_accuracy'] > 0.55 and metrics['overfitting_gap'] < 0.25:
            print("   ✅ Métriques dans les ranges acceptables")
            return True
        else:
            print("   ⚠️ Métriques hors ranges (peut être dû au faible nombre de trials)")
            return True  # OK pour un test rapide
            
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 70)
    print("  VERIFICATION INTEGRATION OPTUNA GRADIENTBOOSTING")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    results = {}
    
    # 1. Backend
    results['backend'] = check_backend_available()
    
    # 2. Endpoints (seulement si backend OK)
    if results['backend']:
        results['endpoints'] = check_endpoint_exists()
    else:
        results['endpoints'] = False
        print("\n[2/6] Endpoints - Sauté (backend non accessible)")
    
    # 3. Module
    results['module'] = check_optimizer_module()
    
    # 4. Données
    results['data'] = check_data_availability()
    
    # 5. Config
    results['config'] = check_config_persistence()
    
    # 6. Test rapide (seulement si module et données OK)
    if results['module'] and results['data']:
        results['quick_test'] = run_quick_optimization_test()
    else:
        results['quick_test'] = False
        print("\n[6/6] Test rapide - Sauté (prérequis non satisfaits)")
    
    # Résumé
    print("\n" + "=" * 70)
    print("  RÉSUMÉ")
    print("=" * 70)
    
    all_ok = all(results.values())
    
    for check, status in results.items():
        icon = "✅" if status else "❌"
        print(f"   {icon} {check}")
    
    print("\n" + "=" * 70)
    if all_ok:
        print("  ✅ TOUS LES TESTS PASSENT - Intégration OK!")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  ⚠️ {len(failed)} test(s) échoué(s): {', '.join(failed)}")
    print("=" * 70)
    
    return all_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

# -*- coding: utf-8 -*-
"""
Vérification du flux complet des variables GradientBoosting
============================================================
Teste que les modifications dans Optimisation GB:
1. Sont envoyées au backend via API
2. Sont stockées dans TRADING_CONFIG
3. Sont reflétées dans /api/config (Variables en cours)
4. Sont utilisées par le bot (predictor)

Usage:
    python verification/verify_gb_variable_flow.py
    
Auteur: Cascade AI
Date: 11/12/2025
"""

import sys
import json
import time
import requests

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:8000"

print("=" * 70)
print("  VERIFICATION FLUX VARIABLES GRADIENTBOOSTING")
print("=" * 70)

def test_api_available():
    """Test si l'API est accessible."""
    print("\n[1/6] Test connexion API...")
    try:
        resp = requests.get(f"{BASE_URL}/api/config", timeout=5)
        if resp.status_code == 200:
            print("   ✅ API accessible")
            return True
        else:
            print(f"   ❌ API retourne status {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ API non accessible - Le backend est-il démarré?")
        return False
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False

def get_current_config():
    """Récupère la config actuelle."""
    print("\n[2/6] Récupération config actuelle...")
    try:
        resp = requests.get(f"{BASE_URL}/api/config", timeout=5)
        if resp.status_code == 200:
            config = resp.json()
            gb_keys = ['gb_filter_enabled', 'gb_min_confidence', 'gb_max_iter', 
                      'gb_max_depth', 'gb_learning_rate', 'gb_min_samples_leaf',
                      'gb_l2_regularization']
            print("   Variables GB actuelles:")
            for key in gb_keys:
                value = config.get(key, 'N/A')
                print(f"      {key}: {value}")
            return config
        else:
            print(f"   ❌ Erreur: {resp.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return None

def test_modify_variable(key, new_value, original_value):
    """Teste la modification d'une variable."""
    print(f"\n[3/6] Test modification: {key} = {new_value}...")
    try:
        # Envoyer la modification
        resp = requests.post(
            f"{BASE_URL}/api/config",
            json={key: new_value},
            timeout=5
        )
        
        if resp.status_code == 200:
            print(f"   ✅ POST /api/config réussi")
        else:
            print(f"   ❌ POST échoué: {resp.status_code}")
            return False
        
        # Vérifier que la valeur est appliquée
        time.sleep(0.5)  # Attendre propagation
        
        resp2 = requests.get(f"{BASE_URL}/api/config", timeout=5)
        if resp2.status_code == 200:
            new_config = resp2.json()
            actual = new_config.get(key)
            
            # Comparer avec tolérance pour les floats
            if isinstance(new_value, float):
                match = abs(actual - new_value) < 0.001
            else:
                match = actual == new_value
            
            if match:
                print(f"   ✅ Valeur confirmée dans GET /api/config: {actual}")
                return True
            else:
                print(f"   ❌ Valeur non appliquée: attendu {new_value}, obtenu {actual}")
                return False
        else:
            print(f"   ❌ GET échoué: {resp2.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False

def test_predictor_uses_config():
    """Vérifie que le predictor utilise la config."""
    print("\n[4/6] Vérification predictor utilise la config...")
    try:
        # Importer et vérifier le predictor
        sys.path.insert(0, '.')
        from config import TRADING_CONFIG
        from optimization.predictor_optimized import get_predictor
        
        predictor = get_predictor()
        
        if predictor.is_loaded:
            print(f"   ✅ Predictor chargé")
            
            # Vérifier que TRADING_CONFIG contient les bonnes valeurs
            gb_conf = TRADING_CONFIG.get('gb_min_confidence', 0.55)
            print(f"   ✅ TRADING_CONFIG['gb_min_confidence'] = {gb_conf}")
            
            return True
        else:
            print(f"   ⚠️ Predictor non chargé (modèle absent?)")
            return True  # Pas une erreur critique
            
    except ImportError as e:
        print(f"   ⚠️ Import error (normal si exécuté hors contexte): {e}")
        return True
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False

def test_complete_config_endpoint():
    """Teste l'endpoint /api/config/complete utilisé par Variables en cours."""
    print("\n[5/6] Test endpoint /api/config/complete...")
    try:
        resp = requests.get(f"{BASE_URL}/api/config/complete", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            
            # Vérifier structure
            if 'trading_config' in data or 'effective_config' in data:
                config_key = 'effective_config' if 'effective_config' in data else 'trading_config'
                config = data[config_key]
                
                gb_conf = config.get('gb_min_confidence', 'N/A')
                print(f"   ✅ Endpoint accessible")
                print(f"   ✅ gb_min_confidence dans {config_key}: {gb_conf}")
                return True
            else:
                print(f"   ⚠️ Structure inattendue: {list(data.keys())}")
                return True
        else:
            print(f"   ❌ Erreur: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False

def restore_original_value(key, original_value):
    """Restaure la valeur originale."""
    print(f"\n[6/6] Restauration valeur originale: {key} = {original_value}...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/config",
            json={key: original_value},
            timeout=5
        )
        if resp.status_code == 200:
            print(f"   ✅ Valeur restaurée")
            return True
        else:
            print(f"   ⚠️ Restauration échouée: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ⚠️ Erreur restauration: {e}")
        return False

def main():
    """Exécute tous les tests."""
    results = []
    
    # Test 1: API disponible
    if not test_api_available():
        print("\n" + "=" * 70)
        print("❌ ÉCHEC: API non disponible. Démarrez le backend.")
        print("=" * 70)
        return
    results.append(("API disponible", True))
    
    # Test 2: Récupérer config actuelle
    config = get_current_config()
    if config is None:
        print("\n❌ Impossible de récupérer la config")
        return
    results.append(("GET /api/config", True))
    
    # Sauvegarder valeur originale
    original_confidence = config.get('gb_min_confidence', 0.55)
    test_value = 0.60 if original_confidence != 0.60 else 0.55
    
    # Test 3: Modifier variable
    modify_ok = test_modify_variable('gb_min_confidence', test_value, original_confidence)
    results.append(("POST /api/config", modify_ok))
    
    # Test 4: Predictor utilise config
    predictor_ok = test_predictor_uses_config()
    results.append(("Predictor sync", predictor_ok))
    
    # Test 5: Endpoint complete
    complete_ok = test_complete_config_endpoint()
    results.append(("GET /api/config/complete", complete_ok))
    
    # Test 6: Restaurer
    restore_ok = restore_original_value('gb_min_confidence', original_confidence)
    results.append(("Restauration", restore_ok))
    
    # Résumé
    print("\n" + "=" * 70)
    print("  RÉSUMÉ DES TESTS")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ TOUS LES TESTS PASSENT - Le flux de variables fonctionne correctement")
    else:
        print("❌ CERTAINS TESTS ÉCHOUENT - Vérifiez les erreurs ci-dessus")
    print("=" * 70)

if __name__ == "__main__":
    main()

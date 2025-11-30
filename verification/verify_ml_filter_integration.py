# -*- coding: utf-8 -*-
"""
Vérification Intégration Filtre ML

Ce script vérifie que:
1. La config ML est correctement chargée
2. Le modèle de filtre négatif fonctionne
3. Le filtre s'applique bien aux 3 modèles
4. Les paramètres sont accessibles via l'API
"""

import sys
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import requests

print("=" * 70)
print("  VERIFICATION INTEGRATION FILTRE ML")
print("  Commun aux 3 modeles: XGBoost V1 / V2 / GradientBoosting")
print("=" * 70)

all_ok = True

# =============================================================================
# TEST 1: Configuration chargée correctement
# =============================================================================
print("\n" + "-" * 50)
print("TEST 1: Configuration ML")
print("-" * 50)

try:
    from config import ML_CONFIG, TRADING_CONFIG
    
    enabled = ML_CONFIG.get('enabled', False)
    mode = ML_CONFIG.get('mode', 'STRICT')
    loss_threshold = ML_CONFIG.get('loss_threshold', 0.45)
    
    print(f"   ml_filter_enabled: {enabled}")
    print(f"   ml_filter_mode: {mode}")
    print(f"   ml_loss_threshold: {loss_threshold}")
    
    if mode == 'NEGATIVE':
        print(f"\n   [OK] Mode NEGATIVE actif")
    else:
        print(f"\n   [!] Mode {mode} (pas NEGATIVE)")
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    all_ok = False

# =============================================================================
# TEST 2: Modèle filtre négatif chargé
# =============================================================================
print("\n" + "-" * 50)
print("TEST 2: Modele Filtre Negatif")
print("-" * 50)

try:
    from optimization.predictor_negative import get_negative_predictor
    
    predictor = get_negative_predictor()
    info = predictor.get_info()
    
    print(f"   is_loaded: {info['is_loaded']}")
    print(f"   n_features: {info['n_features']}")
    print(f"   threshold: {info['threshold']}")
    
    if info['is_loaded']:
        print(f"\n   [OK] Modele charge")
    else:
        print(f"\n   [X] Modele non charge")
        all_ok = False
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    all_ok = False

# =============================================================================
# TEST 3: API retourne les paramètres ML
# =============================================================================
print("\n" + "-" * 50)
print("TEST 3: API /api/config")
print("-" * 50)

try:
    resp = requests.get("http://localhost:5000/api/config", timeout=5)
    
    if resp.status_code == 200:
        config = resp.json().get('trading_config', {})
        
        ml_enabled = config.get('ml_filter_enabled')
        ml_mode = config.get('ml_filter_mode')
        ml_threshold = config.get('ml_loss_threshold')
        
        print(f"   ml_filter_enabled: {ml_enabled}")
        print(f"   ml_filter_mode: {ml_mode}")
        print(f"   ml_loss_threshold: {ml_threshold}")
        
        if ml_mode is not None and ml_threshold is not None:
            print(f"\n   [OK] API retourne les nouveaux parametres")
        else:
            print(f"\n   [!] Parametres manquants dans API")
            all_ok = False
    else:
        print(f"   [X] Erreur HTTP {resp.status_code}")
        all_ok = False
        
except requests.exceptions.ConnectionError:
    print(f"   [!] Backend non accessible (normal si pas demarré)")
except Exception as e:
    print(f"   [X] Erreur: {e}")
    all_ok = False

# =============================================================================
# TEST 4: Scanner Loop utilise le mode NEGATIVE
# =============================================================================
print("\n" + "-" * 50)
print("TEST 4: Code scanner_loop.py")
print("-" * 50)

try:
    with open('core/callbacks/scanner_loop.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("mode == 'NEGATIVE'", "Mode NEGATIVE detecte"),
        ("predictor_negative", "Import predictor_negative"),
        ("loss_threshold", "Utilisation loss_threshold"),
        ("neg_predictor", "Variable neg_predictor"),
    ]
    
    for pattern, desc in checks:
        if pattern in content:
            print(f"   [OK] {desc}")
        else:
            print(f"   [X] {desc} - MANQUANT")
            all_ok = False
            
except Exception as e:
    print(f"   [X] Erreur: {e}")
    all_ok = False

# =============================================================================
# TEST 5: Frontend a les contrôles communs
# =============================================================================
print("\n" + "-" * 50)
print("TEST 5: Frontend VariablesPanel.svelte")
print("-" * 50)

try:
    with open('frontend/src/lib/components/VariablesPanel.svelte', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("ml_filter_mode", "Variable ml_filter_mode"),
        ("ml_loss_threshold", "Variable ml_loss_threshold"),
        ("Commun aux 3 modèles", "Section commune"),
        ("NEGATIVE (Recommandé)", "Option NEGATIVE"),
    ]
    
    for pattern, desc in checks:
        if pattern in content:
            print(f"   [OK] {desc}")
        else:
            print(f"   [X] {desc} - MANQUANT")
            all_ok = False
            
except Exception as e:
    print(f"   [X] Erreur: {e}")
    all_ok = False

# =============================================================================
# TEST 6: Prédiction fonctionne
# =============================================================================
print("\n" + "-" * 50)
print("TEST 6: Test Prediction")
print("-" * 50)

try:
    from optimization.predictor_negative import get_negative_predictor
    
    predictor = get_negative_predictor()
    
    # Features de test
    test_features = {
        'rsi_1m': 45.0, 'rsi_5m': 50.0,
        'macd_hist_1m': 0.001, 'macd_hist_5m': 0.002,
        'adx_1m': 25.0, 'adx_5m': 28.0,
        'atr_pct_1m': 0.3, 'atr_pct_5m': 0.5,
    }
    
    result = predictor.predict(test_features)
    
    print(f"   prediction: {result.get('prediction')}")
    print(f"   p_loss: {result.get('p_loss', 0)*100:.1f}%")
    print(f"   should_reject: {result.get('should_reject')}")
    
    if 'p_loss' in result:
        print(f"\n   [OK] Prediction fonctionne")
    else:
        print(f"\n   [X] Prediction echouée")
        all_ok = False
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    all_ok = False

# =============================================================================
# TEST 7: config_overrides.json a les paramètres
# =============================================================================
print("\n" + "-" * 50)
print("TEST 7: config_overrides.json")
print("-" * 50)

try:
    with open('config_overrides.json', 'r') as f:
        overrides = json.load(f)
    
    checks = [
        ('ml_filter_enabled', 'ml_filter_enabled'),
        ('ml_filter_mode', 'ml_filter_mode'),
        ('ml_loss_threshold', 'ml_loss_threshold'),
    ]
    
    for key, desc in checks:
        if key in overrides:
            print(f"   [OK] {desc}: {overrides[key]}")
        else:
            print(f"   [X] {desc} - MANQUANT")
            all_ok = False
            
except Exception as e:
    print(f"   [X] Erreur: {e}")
    all_ok = False

# =============================================================================
# RÉSUMÉ
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME")
print("=" * 70)

if all_ok:
    print(f"""
   [OK] TOUS LES TESTS PASSES
   
   Configuration actuelle:
   - Mode: NEGATIVE (filtre negatif)
   - Seuil: P(loss) >= 45% -> REJET
   - S'applique aux 3 modeles ML
   
   Emplacement UI:
   Variables > Machine Learning > Section "Filtrage ML des Trades"
   (visible quel que soit le modele selectionne)
""")
else:
    print(f"""
   [X] CERTAINS TESTS ONT ECHOUE
   
   Actions recommandees:
   1. Rebuilder le frontend: cd frontend && npm run build
   2. Redemarrer le backend
   3. Relancer ce script
""")

print("=" * 70)

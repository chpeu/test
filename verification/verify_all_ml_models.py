# -*- coding: utf-8 -*-
"""
Boucle de Vérification Complète des Modèles ML

Vérifie:
1. Chargement de tous les modèles
2. Prédictions fonctionnelles
3. Performance sur données test
4. Cohérence du filtre négatif
"""

import sys
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import numpy as np
import pandas as pd
from datetime import datetime, timezone

print("=" * 70)
print("  BOUCLE DE VERIFICATION COMPLETE - MODELES ML")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

results = {}
all_passed = True

# =============================================================================
# TEST 1: Configuration ML
# =============================================================================
print("\n" + "-" * 50)
print("[1/7] CONFIGURATION ML")
print("-" * 50)

try:
    from config import ML_CONFIG, TRADING_CONFIG
    
    results['config'] = {
        'enabled': ML_CONFIG.get('enabled', False),
        'mode': ML_CONFIG.get('mode', 'STRICT'),
        'loss_threshold': ML_CONFIG.get('loss_threshold', 0.45),
        'min_confidence': ML_CONFIG.get('min_confidence', 0.6),
    }
    
    print(f"   ml_filter_enabled: {results['config']['enabled']}")
    print(f"   ml_filter_mode: {results['config']['mode']}")
    print(f"   ml_loss_threshold: {results['config']['loss_threshold']}")
    print(f"   ml_min_confidence: {results['config']['min_confidence']}")
    print(f"\n   [OK] Configuration chargee")
    
except Exception as e:
    print(f"   [X] Erreur: {e}")
    all_passed = False

# =============================================================================
# TEST 2: XGBoost V1
# =============================================================================
print("\n" + "-" * 50)
print("[2/7] XGBOOST V1 (Classification)")
print("-" * 50)

try:
    from optimization.predictor import get_predictor
    
    predictor_v1 = get_predictor()
    
    # Attribut: loaded (pas is_loaded)
    if hasattr(predictor_v1, 'loaded') and predictor_v1.loaded:
        print(f"   Modele: {predictor_v1.model_name}")
        print(f"   Features: {len(predictor_v1.feature_names) if predictor_v1.feature_names else 'N/A'}")
        
        # Test prediction
        test_features = {'rsi_1m': 45, 'rsi_5m': 50, 'macd_hist_1m': 0.001}
        result = predictor_v1.predict(test_features)
        
        if result:
            print(f"   Test prediction: {result.get('prediction')} ({result.get('confidence', 0)*100:.1f}%)")
            print(f"\n   [OK] XGBoost V1 fonctionne")
            results['v1'] = {'loaded': True, 'working': True}
        else:
            print(f"   [!] Prediction retourne None")
            results['v1'] = {'loaded': True, 'working': False}
    else:
        print(f"   [!] Modele non charge")
        results['v1'] = {'loaded': False, 'working': False}
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    results['v1'] = {'loaded': False, 'working': False, 'error': str(e)}
    all_passed = False

# =============================================================================
# TEST 3: XGBoost V2
# =============================================================================
print("\n" + "-" * 50)
print("[3/7] XGBOOST V2 (Regression PNL%)")
print("-" * 50)

try:
    from optimization.predictor_v2 import get_predictor_v2
    
    predictor_v2 = get_predictor_v2()
    
    if hasattr(predictor_v2, 'loaded') and predictor_v2.loaded:
        print(f"   Modele: {predictor_v2.model_name}")
        
        # Test prediction
        test_features = {'rsi_1m': 45, 'rsi_5m': 50, 'macd_hist_1m': 0.001}
        result = predictor_v2.predict(test_features, return_classification=True)
        
        if result:
            print(f"   Test prediction: {result.get('prediction')} (PNL: {result.get('predicted_pnl', 0):.2f}%)")
            print(f"\n   [OK] XGBoost V2 fonctionne")
            results['v2'] = {'loaded': True, 'working': True}
        else:
            print(f"   [!] Prediction retourne None")
            results['v2'] = {'loaded': True, 'working': False}
    else:
        print(f"   [!] Modele non charge")
        results['v2'] = {'loaded': False, 'working': False}
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    results['v2'] = {'loaded': False, 'working': False, 'error': str(e)}

# =============================================================================
# TEST 4: GradientBoosting
# =============================================================================
print("\n" + "-" * 50)
print("[4/7] GRADIENTBOOSTING (Classification optimisee)")
print("-" * 50)

try:
    from optimization.predictor_optimized import get_predictor as get_gb_predictor
    
    predictor_gb = get_gb_predictor()
    
    if hasattr(predictor_gb, 'is_loaded') and predictor_gb.is_loaded:
        print(f"   Modele charge")
        
        # Test prediction
        test_features = {'rsi_1m': 45, 'rsi_5m': 50, 'macd_hist_1m': 0.001}
        should_trade, confidence = predictor_gb.predict(test_features)
        
        print(f"   Test prediction: {'TRADE' if should_trade else 'NO TRADE'} ({confidence*100:.1f}%)")
        print(f"\n   [OK] GradientBoosting fonctionne")
        results['gb'] = {'loaded': True, 'working': True}
    else:
        print(f"   [!] Modele non charge")
        results['gb'] = {'loaded': False, 'working': False}
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    results['gb'] = {'loaded': False, 'working': False, 'error': str(e)}

# =============================================================================
# TEST 5: Filtre Négatif
# =============================================================================
print("\n" + "-" * 50)
print("[5/7] FILTRE NEGATIF")
print("-" * 50)

try:
    from optimization.predictor_negative import get_negative_predictor
    
    neg_predictor = get_negative_predictor()
    
    if neg_predictor.is_loaded:
        info = neg_predictor.get_info()
        print(f"   Features: {info['n_features']}")
        print(f"   Seuil: {info['threshold']}")
        
        # Test prediction avec features temporelles
        test_features = {
            'rsi_1m': 45, 'rsi_5m': 50,
            'macd_hist_1m': 0.001, 'macd_hist_5m': 0.002,
            'adx_1m': 25, 'adx_5m': 28,
            'atr_pct_1m': 0.3, 'atr_pct_5m': 0.5,
        }
        result = neg_predictor.predict(test_features)
        
        print(f"   Test P(loss): {result.get('p_loss', 0)*100:.1f}%")
        print(f"   Reject: {result.get('should_reject', False)}")
        print(f"\n   [OK] Filtre Negatif fonctionne")
        results['negative'] = {'loaded': True, 'working': True}
    else:
        print(f"   [!] Modele non charge")
        results['negative'] = {'loaded': False, 'working': False}
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    results['negative'] = {'loaded': False, 'working': False, 'error': str(e)}
    all_passed = False

# =============================================================================
# TEST 6: Evaluation Performance
# =============================================================================
print("\n" + "-" * 50)
print("[6/7] EVALUATION PERFORMANCE (sur donnees test)")
print("-" * 50)

try:
    from optimization.data.feature_loader import load_features_from_postgres
    from sklearn.metrics import accuracy_score
    
    # Charger données test
    df = load_features_from_postgres(timeframe_days=90, min_trades=1)
    
    if len(df) >= 50:
        # Split
        split_idx = int(len(df) * 0.8)
        X_test = df.iloc[split_idx:]
        y_test = df['target_win'].iloc[split_idx:]
        
        print(f"   Donnees test: {len(X_test)} trades")
        print(f"   Win rate baseline: {y_test.mean()*100:.1f}%")
        
        # Evaluer chaque modele
        model_results = {}
        
        # GradientBoosting
        if results.get('gb', {}).get('working'):
            y_pred = []
            for i in range(len(X_test)):
                features = X_test.iloc[i].to_dict()
                pred, _ = predictor_gb.predict(features)
                y_pred.append(1 if pred else 0)
            acc = accuracy_score(y_test, y_pred)
            model_results['GradientBoosting'] = acc
            print(f"   GradientBoosting Accuracy: {acc*100:.1f}%")
        
        # Filtre Negatif (win rate après filtrage)
        if results.get('negative', {}).get('working'):
            kept_wins = 0
            kept_total = 0
            threshold = results['config']['loss_threshold']
            
            for i in range(len(X_test)):
                features = X_test.iloc[i].to_dict()
                result = neg_predictor.predict(features, threshold=threshold)
                
                if not result.get('should_reject', False):
                    kept_total += 1
                    if y_test.iloc[i] == 1:
                        kept_wins += 1
            
            if kept_total > 0:
                filtered_wr = kept_wins / kept_total
                gain = filtered_wr - y_test.mean()
                model_results['Filtre Negatif'] = filtered_wr
                print(f"   Filtre Negatif WR: {filtered_wr*100:.1f}% (+{gain*100:.1f}%)")
                print(f"   Trades conserves: {kept_total}/{len(X_test)} ({kept_total/len(X_test)*100:.0f}%)")
        
        results['performance'] = model_results
        print(f"\n   [OK] Evaluation terminee")
    else:
        print(f"   [!] Pas assez de donnees ({len(df)} trades)")
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# TEST 7: Coherence Scanner Loop
# =============================================================================
print("\n" + "-" * 50)
print("[7/7] COHERENCE CODE SCANNER")
print("-" * 50)

try:
    with open('core/callbacks/scanner_loop.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        "mode == 'NEGATIVE'": False,
        "predictor_negative": False,
        "ML_CONFIG": False,
        "loss_threshold": False,
    }
    
    for pattern in checks:
        if pattern in content:
            checks[pattern] = True
            print(f"   [OK] {pattern}")
        else:
            print(f"   [X] {pattern} - MANQUANT")
            all_passed = False
    
    if all(checks.values()):
        print(f"\n   [OK] Scanner integre correctement")
    else:
        print(f"\n   [!] Integration incomplete")
        
except Exception as e:
    print(f"   [X] Erreur: {e}")

# =============================================================================
# RESUME
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME VERIFICATION")
print("=" * 70)

print(f"""
   MODELES:
   --------
   XGBoost V1:      {'[OK]' if results.get('v1', {}).get('working') else '[X]'}
   XGBoost V2:      {'[OK]' if results.get('v2', {}).get('working') else '[X]'}
   GradientBoosting: {'[OK]' if results.get('gb', {}).get('working') else '[X]'}
   Filtre Negatif:  {'[OK]' if results.get('negative', {}).get('working') else '[X]'}
   
   CONFIGURATION:
   --------------
   Mode: {results.get('config', {}).get('mode', 'N/A')}
   Seuil P(loss): {results.get('config', {}).get('loss_threshold', 'N/A')}
   Actif: {results.get('config', {}).get('enabled', False)}
   
   PERFORMANCE:
   ------------""")

for model, score in results.get('performance', {}).items():
    print(f"   {model}: {score*100:.1f}%")

if all_passed:
    print(f"""
   [OK] TOUS LES TESTS PASSES
   
   Le systeme ML est operationnel.
   Configuration recommandee appliquee.
""")
else:
    print(f"""
   [!] CERTAINS TESTS ONT ECHOUE
   
   Actions:
   1. Verifier les modeles manquants
   2. Reentrainer si necessaire
   3. Redemarrer le backend
""")

print("=" * 70)

# =============================================================================
# EXPORT RESULTATS
# =============================================================================
import json

report = {
    'timestamp': datetime.now().isoformat(),
    'all_passed': all_passed,
    'results': {
        'config': results.get('config', {}),
        'models': {
            'v1': results.get('v1', {}),
            'v2': results.get('v2', {}),
            'gb': results.get('gb', {}),
            'negative': results.get('negative', {}),
        },
        'performance': results.get('performance', {}),
    }
}

with open('ml_verification_report.json', 'w') as f:
    json.dump(report, f, indent=2, default=str)

print(f"\nRapport sauvegarde: ml_verification_report.json")

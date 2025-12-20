#!/usr/bin/env python3
"""
🔍 SCRIPT DE VÉRIFICATION NOUVEAU MODÈLE GB
============================================
Teste que le nouveau modèle HistGradientBoostingClassifier optimisé 
fonctionne correctement après redémarrage.
"""
import os
import sys
import json
from pathlib import Path

# Force UTF-8 for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ajouter le projet au path
sys.path.insert(0, str(Path(__file__).parent))

def test_model_loading():
    """Test 1: Vérifier le chargement du nouveau modèle"""
    print("🔍 TEST 1: Chargement du nouveau modèle GB...")
    
    try:
        from optimization.predictor_optimized import get_predictor
        predictor = get_predictor()
        
        if predictor.is_loaded:
            print(f"   ✅ Modèle chargé avec succès")
            print(f"   📊 Type: {type(predictor.model).__name__}")
            
            # Vérifier les métadonnées
            if predictor.metadata:
                timestamp = predictor.metadata.get('timestamp', 'Inconnu')
                model_type = predictor.metadata.get('model_type', 'Inconnu')
                metrics = predictor.metadata.get('metrics', {})
                f1_score = metrics.get('f1_score', 0)
                overfitting = metrics.get('overfitting', 0)
                
                print(f"   📅 Date: {timestamp}")
                print(f"   🎯 Type: {model_type}")
                print(f"   📈 F1 Score: {f1_score:.4f}")
                print(f"   🛡️ Overfitting: {overfitting:.2%}")
                
                # Vérifier si c'est le nouveau modèle
                if '2025-12-20' in timestamp:
                    print("   🔥 NOUVEAU MODÈLE OPTIMISÉ CONFIRMÉ!")
                    return True
                else:
                    print("   ⚠️ Ancien modèle détecté")
                    return False
            else:
                print("   ⚠️ Métadonnées non disponibles")
                return False
        else:
            print("   ❌ Modèle non chargé")
            return False
            
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False

def test_prediction():
    """Test 2: Test de prédiction avec features factices"""
    print("\n🎯 TEST 2: Test de prédiction...")
    
    try:
        from optimization.predictor_optimized import get_predictor
        predictor = get_predictor()
        
        if not predictor.is_loaded:
            print("   ❌ Modèle non disponible")
            return False
        
        # Features factices pour test
        test_features = {
            'di_minus_1m': 25.5,
            'di_gap_1m': 12.3,
            'bb_distance_to_lower_5m': 0.05,
            'bb_distance_to_upper_5m': 0.12,
            'ema_trend_strength_1m': 0.8,
            'macd_hist_prev_5m': 0.002,
            'ema_trend_strength_5m': 0.7,
            'rsi_change_1m': 2.5,
            'rsi_prev_1m': 48.5,
            'rsi_5m': 52.0,
            'hour': 14,
            'volume_spike_5m': 1.5,
            'ema_diff_pct_1m': 0.15,
            'momentum_divergence': 0.3,
            'bb_width_1m': 0.08,
            'delta_volume': 1.2,
            'macd_hist_5m': 0.001,
            'atr_pct_5m': 0.25,
            'di_gap_5m': 8.7,
            'bb_distance_to_lower_1m': 0.03
        }
        
        # Test avec seuil par défaut
        should_trade, confidence = predictor.predict(test_features, threshold=0.45)
        
        print(f"   📊 Prédiction: should_trade={should_trade}")
        print(f"   🎯 Confidence: {confidence:.4f} ({confidence*100:.2f}%)")
        print(f"   📏 Seuil utilisé: 45%")
        
        # Test avec seuil optimal recommandé
        should_trade_opt, _ = predictor.predict(test_features, threshold=0.47)
        print(f"   🎯 Avec seuil optimal (47%): {should_trade_opt}")
        
        print("   ✅ Test de prédiction réussi")
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur prédiction: {e}")
        return False

def test_config_ml():
    """Test 3: Vérifier la configuration ML"""
    print("\n⚙️ TEST 3: Configuration ML...")
    
    try:
        from config import TRADING_CONFIG
        
        # Composants ML
        gb_enabled = TRADING_CONFIG.get('gb_filter_enabled', False)
        gb_confidence = TRADING_CONFIG.get('gb_min_confidence', 0.5)
        threshold_opt = TRADING_CONFIG.get('threshold_optimizer_enabled', False)
        ml_calibration = TRADING_CONFIG.get('ml_calibration_enabled', False)
        drift_detection = TRADING_CONFIG.get('drift_detection_enabled', False)
        
        print(f"   🌳 GB Filter: {'✅' if gb_enabled else '❌'} ({gb_confidence:.2%})")
        print(f"   🎯 Threshold Optimizer: {'✅' if threshold_opt else '❌'}")
        print(f"   📊 ML Calibration: {'✅' if ml_calibration else '❌'}")
        print(f"   🔍 Drift Detection: {'✅' if drift_detection else '❌'}")
        
        all_enabled = gb_enabled and threshold_opt and ml_calibration
        
        if all_enabled:
            print("   🔥 SYSTÈME ML COMPLÈTEMENT ACTIVÉ!")
            return True
        else:
            print("   ⚠️ Certains composants ML désactivés")
            return False
            
    except Exception as e:
        print(f"   ❌ Erreur config: {e}")
        return False

def main():
    """Fonction principale de vérification"""
    print("🎯 VÉRIFICATION NOUVEAU MODÈLE GB OPTIMISÉ")
    print("=" * 60)
    
    tests = [
        ("Chargement Modèle", test_model_loading),
        ("Test Prédiction", test_prediction),
        ("Configuration ML", test_config_ml)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        result = test_func()
        if result:
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 RÉSULTATS: {passed}/{total} tests réussis")
    
    if passed == total:
        print("🎉 NOUVEAU MODÈLE GB PARFAITEMENT OPÉRATIONNEL!")
    else:
        print("⚠️ Certains composants nécessitent attention")
    
    return passed == total

if __name__ == "__main__":
    main()

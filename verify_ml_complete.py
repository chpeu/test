#!/usr/bin/env python3
"""
Vérification complète du système ML GradientBoosting
"""
import sys
sys.path.append('.')
import json
import joblib
import pandas as pd
from pathlib import Path
from datetime import datetime

def main():
    print('='*70)
    print('VERIFICATION COMPLETE ML GRADIENT BOOSTING')  
    print('='*70)

    # 1. Vérifier le modèle chargé par le système
    print('\n1. MODELE CHARGE PAR LE SYSTEME:')
    try:
        from optimization.predictor_optimized import get_predictor
        predictor = get_predictor()
        
        if predictor.is_loaded:
            print('   [OK] Statut: CHARGE')
            print(f'   Type modele: {type(predictor.model).__name__}')
            print(f'   Features definies: {len(predictor.feature_cols) if predictor.feature_cols else 0}')
            if predictor.feature_cols:
                print(f'   Premieres features: {predictor.feature_cols[:3]}')
        else:
            print('   [ERROR] Statut: NON CHARGE')
    except Exception as e:
        print(f'   [ERROR] ERREUR: {e}')

    # 2. Vérifier le fichier modèle
    print('\n2. FICHIER MODELE (best_classifier_latest.pkl):')
    model_path = Path('optimization/saved_models/best_classifier_latest.pkl')
    if model_path.exists():
        model_data = joblib.load(model_path)
        model = model_data.get('model')
        
        print('   [OK] Fichier existe: OUI')
        print(f'   Type: {type(model).__name__}')
        print(f'   Features attendues: {model.n_features_in_}')
        feature_names = model_data.get('feature_names', [])
        print(f'   Feature names: {len(feature_names)}')
        
        # Vérifier cohérence
        if predictor and predictor.feature_cols:
            match_features = set(predictor.feature_cols) == set(feature_names)
            print(f'   Cohérence features: {"[OK] OUI" if match_features else "[ERROR] NON"}')
    else:
        print('   [ERROR] Fichier existe: NON')

    # 3. Vérifier les métadonnées
    print('\n3. METADONNEES MODELE:')
    meta_path = Path('optimization/saved_models/best_classifier_metadata.json')
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        timestamp = metadata.get('timestamp', 'inconnue')
        print(f'   Date entrainement: {timestamp}')
        metrics = metadata.get('metrics', {})
        print(f'   Test accuracy: {metrics.get("test_accuracy", 0)*100:.1f}%')
        print(f'   F1 score: {metrics.get("f1_score", 0)*100:.1f}%')
        print(f'   ROC AUC: {metrics.get("roc_auc", 0)*100:.1f}%')
        print(f'   Overfitting: {metrics.get("overfitting", 0)*100:.1f}%')
    else:
        print('   [ERROR] Fichier metadata: NON TROUVE')

    # 4. Test de prédiction avec données réelles
    print('\n4. TEST PREDICTION AVEC DONNEES REELLES:')
    if predictor and predictor.is_loaded:
        # Créer features de test réalistes
        test_features = {
            'di_minus_1m': 25.5,
            'di_gap_1m': 8.2,  
            'bb_distance_to_lower_5m': 0.015,
            'bb_distance_to_upper_5m': 0.032,
            'ema_trend_strength_1m': 0.008,
            'macd_hist_prev_5m': 0.0015,
            'ema_trend_strength_5m': 0.012,
            'rsi_change_1m': -2.1,
            'rsi_prev_1m': 58.3,
            'rsi_5m': 62.1,
            'hour': 14,
            'volume_spike_5m': 1.8,
            'ema_diff_pct_1m': 0.005,
            'momentum_divergence': 0.025,
            'bb_width_1m': 0.018,
            'delta_volume': 0.3,
            'macd_hist_5m': 0.002,
            'atr_pct_5m': 0.015,
            'di_gap_5m': 12.1,
            'bb_distance_to_lower_1m': 0.008
        }
        
        try:
            should_trade, confidence = predictor.predict(test_features, threshold=0.5)
            print(f'   [OK] Prediction reussie')
            print(f'   Should trade: {should_trade}')
            print(f'   Confidence: {confidence:.4f} ({confidence*100:.2f}%)')
            
            # Test avec différents seuils
            thresholds = [0.45, 0.5, 0.55, 0.6]
            print(f'   Tests avec differents seuils:')
            for th in thresholds:
                should, conf = predictor.predict(test_features, threshold=th)
                print(f'      Seuil {th*100:.0f}%: {"[ACCEPT]" if should else "[REJECT]"} (conf: {conf*100:.1f}%)')
                
        except Exception as e:
            print(f'   [ERROR] ERREUR prediction: {e}')
    else:
        print('   [WARN] Predictor non disponible')

    # 5. Vérifier la configuration GB
    print('\n5. CONFIGURATION GB:')
    try:
        from config import TRADING_CONFIG
        
        gb_enabled = TRADING_CONFIG.get('gb_filter_enabled', False)
        gb_confidence = TRADING_CONFIG.get('gb_min_confidence', 0.5)
        
        print(f'   gb_filter_enabled: {gb_enabled}')
        print(f'   gb_min_confidence: {gb_confidence*100:.0f}%')
        
        if gb_enabled:
            print('   [OK] Filtre GB ACTIVE en configuration')
        else:
            print('   [WARN] Filtre GB DESACTIVE en configuration')
            
    except Exception as e:
        print(f'   [ERROR] ERREUR config: {e}')

    print('\n' + '='*70)
    print('VERIFICATION TERMINEE')
    print('='*70)

if __name__ == "__main__":
    main()

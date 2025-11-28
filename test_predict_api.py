"""
Script de test pour l'endpoint de prediction ML
"""

import requests
import json

# Test endpoint
url = "http://localhost:5000/api/ml/predict"

# Exemple de features d'une opportunite (avec valeurs realistes)
features = {
    # Features 1m
    'rsi_1m': 65.5,
    'rsi_change_1m': 2.3,
    'macd_1m': 0.0012,
    'macd_signal_1m': 0.0008,
    'macd_momentum_1m': 0.0004,
    'bb_upper_1m': 0.9985,
    'bb_middle_1m': 0.9970,
    'bb_lower_1m': 0.9955,
    'bb_width_1m': 0.0030,
    'bb_distance_to_upper_1m': 0.0015,
    'bb_distance_to_lower_1m': 0.0015,
    'ema_9_1m': 0.9972,
    'ema_21_1m': 0.9968,
    'ema_diff_pct_1m': 0.04,
    'atr_1m': 0.0008,
    'atr_pct_1m': 0.08,
    'volume_1m': 125000,
    'volume_ma_1m': 100000,
    'volume_ratio_1m': 1.25,
    
    # Features 5m
    'rsi_5m': 62.8,
    'rsi_change_5m': 1.8,
    'macd_5m': 0.0015,
    'macd_signal_5m': 0.0010,
    'macd_momentum_5m': 0.0005,
    'bb_upper_5m': 0.9990,
    'bb_middle_5m': 0.9970,
    'bb_lower_5m': 0.9950,
    'bb_width_5m': 0.0040,
    'bb_distance_to_upper_5m': 0.0020,
    'bb_distance_to_lower_5m': 0.0020,
    'ema_9_5m': 0.9973,
    'ema_21_5m': 0.9965,
    'ema_diff_pct_5m': 0.08,
    'atr_5m': 0.0012,
    'atr_pct_5m': 0.12,
    'volume_5m': 550000,
    'volume_ma_5m': 480000,
    'volume_ratio_5m': 1.15,
    
    # Features divergence
    'rsi_divergence': 2.7,
    'macd_divergence': -0.0003,
    'volume_divergence': 10.0,
    
    # Features contexte
    'volatility_regime': 0.8,
    'trend_strength': 0.6,
    'market_condition': 1,
}

print("Test de l'endpoint /api/ml/predict")
print("=" * 60)
print("\nEnvoi de features pour prediction...")

try:
    response = requests.post(url, json=features)
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        print("\n" + "=" * 60)
        print("PREDICTION ML")
        print("=" * 60)
        
        # Prediction principale
        prediction = data['prediction']
        win_prob = data['win_probability']
        confidence = data['confidence']
        
        emoji = "🟢" if prediction == 'win' else "🔴"
        print(f"\n{emoji} Prediction: {prediction.upper()}")
        print(f"   Win Probability: {win_prob:.1%}")
        print(f"   Loss Probability: {data['loss_probability']:.1%}")
        print(f"   Confidence: {confidence:.1%}")
        
        # Modele utilise
        print(f"\nModele: {data['model_name']}")
        
        # Performance du modele
        if 'model_performance' in data and data['model_performance']:
            perf = data['model_performance']
            print(f"\nPerformance du modele:")
            print(f"   Test Accuracy: {perf['test_accuracy']:.1%}")
            print(f"   Test F1: {perf['test_f1']:.1%}")
        
        # Top features pour cette prediction
        if data.get('top_features'):
            print(f"\nTop Features influentes:")
            for i, feat in enumerate(data['top_features'][:3], 1):
                print(f"   {i}. {feat['feature']}: {feat['importance']:.1f}")
        
        # Decision
        print("\n" + "=" * 60)
        if prediction == 'win' and confidence > 0.7:
            print("RECOMMANDATION: Trade recommande (haute confiance)")
        elif prediction == 'win' and confidence > 0.6:
            print("RECOMMANDATION: Trade acceptable (confiance moderee)")
        elif prediction == 'loss' and confidence > 0.7:
            print("RECOMMANDATION: Eviter ce trade (haute confiance loss)")
        else:
            print("RECOMMANDATION: Incertain - plus de donnees necessaires")
        print("=" * 60)
        
        print("\nTest reussi!")
        
    else:
        print(f"\nErreur: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("\nErreur: Le serveur n'est pas demarre sur http://localhost:5000")
    print("   Demarrez le serveur avec: npm run dev")
except Exception as e:
    print(f"\nErreur: {e}")

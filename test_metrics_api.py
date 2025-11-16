"""
Script de test pour l'endpoint metriques ML
"""

import requests
import json

# Test endpoint
url = "http://localhost:5000/api/ml/models/metrics/xgboost_v1"

print("Test de l'endpoint /api/ml/models/metrics/xgboost_v1")
print("=" * 60)

try:
    response = requests.get(url)
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"\nModele: {data['model_name']}")
        print(f"Entraine le: {data['trained_at']}")
        
        print(f"\nPerformance Test:")
        print(f"  - Accuracy: {data['performance']['test']['accuracy']:.1%}")
        print(f"  - F1 Score: {data['performance']['test']['f1']:.1%}")
        print(f"  - ROC-AUC: {data['performance']['test']['roc_auc']:.1%}")
        print(f"  - Overfitting Gap: {data['performance']['overfitting_gap']:.1%}")
        
        print(f"\nTop 5 Features:")
        for i, feat in enumerate(data['top_features'][:5], 1):
            print(f"  {i}. {feat['feature']}: {feat['importance']:.1f}%")
        
        print(f"\nEvaluation Qualite:")
        qa = data['quality_assessment']
        print(f"  - Overfitting: {qa['overfitting']}")
        print(f"  - Performance: {qa['test_performance']}")
        print(f"  - Donnees: {qa['data_sufficiency']}")
        
        print(f"\nRecommandations:")
        for rec in data['recommendations']:
            priority_mark = "[HIGH]" if rec['priority'] == 'high' else "[MED]" if rec['priority'] == 'medium' else "[LOW]"
            print(f"  {priority_mark} [{rec['type'].upper()}] {rec['message']}")
        
        print(f"\nTest reussi!")
        
    else:
        print(f"\nErreur: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("\nErreur: Le serveur n'est pas demarre sur http://localhost:5000")
    print("   Demarrez le serveur avec: npm run dev")
except Exception as e:
    print(f"\nErreur: {e}")

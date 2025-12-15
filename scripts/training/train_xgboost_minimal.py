"""Script minimal pour entraîner XGBoost sans toutes les dépendances"""
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Import direct sans passer par optimization.__init__
sys.path.insert(0, '/home/user/test')

from optimization.models.xgboost_trainer import XGBoostTrainer

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 ENTRAÎNEMENT XGBOOST - PARAMÈTRES OPTIMISÉS")
    print("="*60 + "\n")

    trainer = XGBoostTrainer()

    # Entraîner avec les nouveaux paramètres optimisés
    results = trainer.train(
        timeframe_days=30,
        min_trades=50,
        # Les paramètres optimisés sont déjà les valeurs par défaut
        # dans xgboost_trainer.py
    )

    print("\n" + "=" * 60)
    print("🎯 ENTRAÎNEMENT XGBOOST TERMINÉ")
    print("=" * 60)
    print(f"\n📊 Métriques Test:")
    print(f"  - Accuracy:  {results['metrics']['test']['accuracy']:.3f}")
    print(f"  - Precision: {results['metrics']['test']['precision']:.3f}")
    print(f"  - Recall:    {results['metrics']['test']['recall']:.3f}")
    print(f"  - F1 Score:  {results['metrics']['test']['f1']:.3f}")
    print(f"  - ROC-AUC:   {results['metrics']['test']['roc_auc']:.3f}")

    print(f"\n📊 Métriques Train:")
    print(f"  - Accuracy:  {results['metrics']['train']['accuracy']:.3f}")
    print(f"  - F1 Score:  {results['metrics']['train']['f1']:.3f}")

    gap = (results['metrics']['train']['f1'] - results['metrics']['test']['f1']) * 100
    print(f"\n⚖️ Overfitting Gap: {gap:.1f}%")

    print(f"\n🔝 Top 10 Features:")
    for i, feat in enumerate(results['feature_importance'][:10], 1):
        print(f"  {i}. {feat['feature']}: {feat['importance']:.4f}")

    print(f"\n💾 Modèle sauvegardé: {results['model_name']}")
    print("=" * 60 + "\n")

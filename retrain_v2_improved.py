"""
Script de réentraînement XGBoost V2 avec paramètres optimisés
"""
from optimization.models.xgboost_trainer_v2 import XGBoostTrainerV2

print("\n" + "=" * 80)
print("  REENTRAINEMENT XGBOOST V2 - PARAMETRES OPTIMISES")
print("=" * 80)

print("\n[INFO] Parametres:")
print("  - timeframe_days: 210 (7 mois de donnees)")
print("  - min_trades: 50 (moins restrictif)")
print("  - filter_marginal_trades: False (garder tous les trades)")
print("  - max_features: 40 (plus de features)")

print("\n[INFO] Demarrage entrainement...")

trainer = XGBoostTrainerV2(model_name='xgboost_v2')

results = trainer.train(
    timeframe_days=210,
    min_trades=50,
    filter_marginal_trades=False,
    max_features=40,
)

print("\n" + "=" * 80)
print("  RESULTATS FINAUX")
print("=" * 80)

if results.get('status') == 'success':
    metrics = results.get('metrics', {})
    test_metrics = metrics.get('test', {})
    train_metrics = metrics.get('train', {})
    gaps = metrics.get('gaps', {})
    
    print(f"\n[TRAIN]")
    print(f"  Accuracy:  {train_metrics.get('accuracy', 0):.3f}")
    print(f"  ROC-AUC:   {train_metrics.get('roc_auc', 0):.3f}")
    print(f"  F1 Score:  {train_metrics.get('f1_score', 0):.3f}")
    
    print(f"\n[TEST]")
    print(f"  Accuracy:  {test_metrics.get('accuracy', 0):.3f}")
    print(f"  ROC-AUC:   {test_metrics.get('roc_auc', 0):.3f}")
    print(f"  F1 Score:  {test_metrics.get('f1_score', 0):.3f}")
    
    print(f"\n[GAPS]")
    print(f"  Accuracy:  {gaps.get('accuracy', 0):.3f}")
    print(f"  ROC-AUC:   {gaps.get('roc_auc', 0):.3f}")
    
    # Evaluation
    test_acc = test_metrics.get('accuracy', 0)
    acc_gap = gaps.get('accuracy', 1.0)
    
    print("\n" + "=" * 80)
    print("  EVALUATION")
    print("=" * 80)
    
    if test_acc >= 0.65 and acc_gap < 0.15:
        print("\n[OK] EXCELLENT ! Metriques conformes aux objectifs")
        print("     -> Test Accuracy >= 65%")
        print("     -> Overfitting Gap < 15%")
        print("\n[INFO] Vous pouvez maintenant lancer Optuna V2 pour optimiser:")
        print("       python -c \"from optimization.optuna_v2_tuner import run_optuna_v2_optimization; run_optuna_v2_optimization(n_trials=50)\"")
    elif test_acc >= 0.60:
        print("\n[INFO] BON ! Metriques acceptables")
        print(f"     -> Test Accuracy: {test_acc:.1%} (objectif: >= 65%)")
        print(f"     -> Gap: {acc_gap:.1%} (objectif: < 15%)")
        print("\n[INFO] Recommandation: Lancer Optuna V2 pour ameliorer")
    else:
        print("\n[WARNING] INSUFFISANT ! Metriques trop faibles")
        print(f"     -> Test Accuracy: {test_acc:.1%} (objectif: >= 60%)")
        print("\n[INFO] Recommandations:")
        print("  1. Verifier distribution WIN/LOSS dans trades")
        print("  2. Augmenter encore timeframe_days (270+)")
        print("  3. Verifier qualite des features")
else:
    print("\n[ERROR] Entrainement a echoue")
    print(f"Status: {results.get('status')}")
    print(f"Message: {results.get('message', 'N/A')}")

print("\n" + "=" * 80)

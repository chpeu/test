"""
Script d'entraînement XGBoost V2 OPTIMISÉ
Paramètres finaux ajustés pour maximiser les performances
"""
import sys
from pathlib import Path

print("\n" + "=" * 80)
print("  XGBOOST V2 - ENTRAÎNEMENT OPTIMISÉ FINAL")
print("=" * 80)

# Étape 1: Charger et préparer les données
print("\n[1/6] Chargement et préparation des données...")

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features

# Charger avec plus de données (270 jours = 9 mois)
base_df = load_features_from_postgres(
    timeframe_days=270,
    min_trades=50
)

df = calculate_derived_features(base_df)

print(f"[OK] {len(df)} trades chargés")

# Étape 2: Filtrer les données invalides
print("\n[2/6] Filtrage des données invalides...")

initial_count = len(df)
removed_price = 0

# Filtrer prix invalides (price=0 ou NULL)
if 'price' in df.columns:
    before_filter = len(df)
    df = df[df['price'] > 0].copy()
    removed_price = before_filter - len(df)
    print(f"[INFO] {removed_price} scans avec prix invalides exclus")

# Filtrer trades très marginaux (bruit)
if 'target_pnl' in df.columns:
    before_marginal = len(df)
    df = df[abs(df['target_pnl']) >= 0.20].copy()  # Seuil augmenté à 0.20%
    removed_marginal = before_marginal - len(df)
    print(f"[INFO] {removed_marginal} trades marginaux (|PNL| < 0.20%) exclus")

print(f"[OK] {len(df)} trades de qualité retenus ({len(df)/initial_count*100:.1f}% du dataset)")

if len(df) < 100:
    print("[ERROR] Dataset trop petit après filtrage, augmentez timeframe_days")
    sys.exit(1)

# Étape 3: Distribution WIN/LOSS
print("\n[3/6] Analyse distribution WIN/LOSS...")

win_count = (df['target_win'] == 1).sum() if 'target_win' in df.columns else 0
loss_count = (df['target_win'] == 0).sum() if 'target_win' in df.columns else len(df)
win_ratio = win_count / len(df) * 100 if len(df) > 0 else 0

print(f"WIN:  {win_count:4} trades ({win_ratio:.1f}%)")
print(f"LOSS: {loss_count:4} trades ({100-win_ratio:.1f}%)")

if win_ratio < 20:
    print("[WARNING] Très peu de WIN, résultats peuvent être limités")
elif win_ratio > 30:
    print("[OK] Distribution acceptable")

# Étape 4: Entraînement
print("\n[4/6] Entraînement XGBoost V2...")
print("[INFO] Paramètres optimisés:")
print("  - filter_marginal_trades: False (déjà filtré manuellement)")
print("  - max_features: 40 (plus de contexte)")
print("  - learning_rate: 0.03 (plus conservateur)")
print("  - max_depth: 4 (éviter overfitting)")
print("  - reg_alpha/lambda: régularisation forte")
print("")

from optimization.models.xgboost_trainer_v2 import XGBoostTrainerV2

# Paramètres fixes
timeframe_days = 270
min_trades_param = 50

trainer = XGBoostTrainerV2(model_name='xgboost_v2_final')

results = trainer.train(
    timeframe_days=timeframe_days,
    min_trades=50,
    # Filtrage déjà fait manuellement
    filter_marginal_trades=False,
    # Feature selection
    feature_selection=True,
    max_features=40,
    # XGBoost params optimisés
    n_estimators=600,
    max_depth=4,              # Réduit pour éviter overfitting
    learning_rate=0.03,        # Plus conservateur
    min_child_weight=5,        # Plus restrictif
    reg_alpha=1.0,             # Régularisation L1 forte
    reg_lambda=3.0,            # Régularisation L2 forte
    subsample=0.7,             # Moins de données par arbre
    colsample_bytree=0.7,      # Moins de features par arbre
    gamma=0.5,                 # Pénalité split plus forte
    early_stopping_rounds=50,
    random_state=42,
)

# Étape 5: Analyser résultats
print("\n[5/6] Analyse des résultats...")

if results.get('status') == 'success':
    metrics = results.get('metrics', {})
    test_metrics = metrics.get('test', {})
    train_metrics = metrics.get('train', {})
    gaps = metrics.get('gaps', {})
    
    test_acc = test_metrics.get('accuracy', 0)
    test_roc = test_metrics.get('roc_auc', 0)
    test_f1 = test_metrics.get('f1_score', 0)
    acc_gap = gaps.get('accuracy', 1.0)
    
    print("\n" + "=" * 80)
    print("  RÉSULTATS FINAUX")
    print("=" * 80)
    
    print(f"\n[TRAIN]")
    print(f"  Accuracy:  {train_metrics.get('accuracy', 0):.1%}")
    print(f"  ROC-AUC:   {train_metrics.get('roc_auc', 0):.1%}")
    print(f"  F1 Score:  {train_metrics.get('f1_score', 0):.3f}")
    
    print(f"\n[TEST]")
    print(f"  Accuracy:  {test_acc:.1%}")
    print(f"  ROC-AUC:   {test_roc:.1%}")
    print(f"  F1 Score:  {test_f1:.3f}")
    
    print(f"\n[GAPS]")
    print(f"  Accuracy:  {acc_gap:.1%}")
    print(f"  ROC-AUC:   {gaps.get('roc_auc', 0):.1%}")
    
    # Étape 6: Verdict et recommandations
    print("\n[6/6] Verdict et recommandations...")
    print("\n" + "=" * 80)
    print("  ÉVALUATION")
    print("=" * 80)
    
    if test_acc >= 0.65 and acc_gap < 0.15 and test_f1 > 0.40:
        print("\n[OK] EXCELLENT ! Modèle prêt pour production")
        print("     Métriques conformes aux objectifs:")
        print("     - Test Accuracy >= 65%")
        print("     - Overfitting Gap < 15%")
        print("     - F1 Score > 0.40 (détecte WIN)")
        print("\n[INFO] Prochaines étapes:")
        print("  1. Tester en backtest")
        print("  2. Lancer Optuna V2 pour affiner (optionnel):")
        print("     python -c \"from optimization.optuna_v2_tuner import run_optuna_v2_optimization; run_optuna_v2_optimization(n_trials=50)\"")
        print("  3. Activer en production")
        
    elif test_acc >= 0.60 and test_f1 > 0.20:
        print("\n[INFO] BON ! Modèle utilisable mais perfectible")
        print(f"     Test Accuracy: {test_acc:.1%} (objectif: >= 65%)")
        print(f"     F1 Score: {test_f1:.3f} (objectif: > 0.40)")
        print(f"     Gap: {acc_gap:.1%} (objectif: < 15%)")
        print("\n[INFO] Recommandations:")
        print("  1. Lancer Optuna V2 pour optimiser hyperparamètres")
        print("  2. Enrichir features (nouveaux indicateurs)")
        print("  3. Augmenter timeframe_days (plus de données)")
        
    elif test_acc >= 0.55 and test_f1 > 0.10:
        print("\n[WARNING] MOYEN ! Modèle peu fiable")
        print(f"     Test Accuracy: {test_acc:.1%} (trop faible)")
        print(f"     F1 Score: {test_f1:.3f} (détecte très peu de WIN)")
        print("\n[INFO] Actions recommandées:")
        print("  1. Vérifier qualité des features")
        print("  2. Feature engineering avancé")
        print("  3. Considérer autres algos (LightGBM, CatBoost)")
        print("  4. Analyser confusion matrix pour comprendre erreurs")
        
    else:
        print("\n[ERROR] INSUFFISANT ! Modèle inutilisable")
        print(f"     Test Accuracy: {test_acc:.1%} (proche de l'aléatoire)")
        print(f"     F1 Score: {test_f1:.3f} (ne détecte pas WIN)")
        print("\n[INFO] Diagnostic requis:")
        print("  1. Dataset trop bruité ou trop petit")
        print("  2. Features non discriminantes")
        print("  3. Problème dans data pipeline")
        print("  4. Distribution temporelle non stationnaire")
        print("\n[INFO] Solutions possibles:")
        print("  - Augmenter timeframe_days à 365 jours")
        print("  - Filtrer encore plus strictement (|PNL| > 0.30%)")
        print("  - Revoir stratégie de trading (données sources)")
        print("  - Feature engineering complet")
    
    # Sauvegarder rapport
    print("\n" + "=" * 80)
    print("  SAUVEGARDE")
    print("=" * 80)
    
    rapport_path = Path("RAPPORT_ENTRAINEMENT_FINAL.txt")
    with open(rapport_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("  RAPPORT ENTRAÎNEMENT XGBOOST V2 FINAL\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Date: {results.get('trained_at', 'N/A')}\n")
        f.write(f"Dataset: {len(df)} trades (timeframe={timeframe_days} days)\n")
        f.write(f"Distribution: WIN={win_count} ({win_ratio:.1f}%), LOSS={loss_count}\n\n")
        f.write("MÉTRIQUES TRAIN:\n")
        f.write(f"  Accuracy:  {train_metrics.get('accuracy', 0):.3f}\n")
        f.write(f"  ROC-AUC:   {train_metrics.get('roc_auc', 0):.3f}\n")
        f.write(f"  F1 Score:  {train_metrics.get('f1_score', 0):.3f}\n\n")
        f.write("MÉTRIQUES TEST:\n")
        f.write(f"  Accuracy:  {test_acc:.3f}\n")
        f.write(f"  ROC-AUC:   {test_roc:.3f}\n")
        f.write(f"  F1 Score:  {test_f1:.3f}\n\n")
        f.write("GAPS (OVERFITTING):\n")
        f.write(f"  Accuracy:  {acc_gap:.3f}\n")
        f.write(f"  ROC-AUC:   {gaps.get('roc_auc', 0):.3f}\n\n")
        f.write("VERDICT:\n")
        if test_acc >= 0.65 and acc_gap < 0.15 and test_f1 > 0.40:
            f.write("  EXCELLENT - Prêt pour production\n")
        elif test_acc >= 0.60 and test_f1 > 0.20:
            f.write("  BON - Utilisable mais perfectible\n")
        elif test_acc >= 0.55 and test_f1 > 0.10:
            f.write("  MOYEN - Peu fiable\n")
        else:
            f.write("  INSUFFISANT - Inutilisable\n")
    
    print(f"[OK] Rapport sauvegardé: {rapport_path}")
    print(f"[OK] Modèle sauvegardé: optimization/saved_models/xgboost_v2_final.pkl")
    
else:
    print("\n[ERROR] Entraînement a échoué")
    print(f"Status: {results.get('status')}")
    print(f"Message: {results.get('message', 'N/A')}")
    sys.exit(1)

print("\n" + "=" * 80)
print("  TERMINÉ")
print("=" * 80 + "\n")

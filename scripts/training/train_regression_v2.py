"""
Script d'entraînement XGBoost V2 - RÉGRESSION (PNL%)
Au lieu de classifier WIN/LOSS, prédire PNL% directement
"""
import sys
from pathlib import Path
import numpy as np

print("\n" + "=" * 80)
print("  XGBOOST V2 - RÉGRESSION PNL%")
print("=" * 80)

# Étape 1: Charger et préparer les données
print("\n[1/6] Chargement et préparation des données...")

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features

# Charger avec plus de données (270 jours)
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
    df = df[abs(df['target_pnl']) >= 0.20].copy()  # Seuil 0.20%
    removed_marginal = before_marginal - len(df)
    print(f"[INFO] {removed_marginal} trades marginaux (|PNL| < 0.20%) exclus")

print(f"[OK] {len(df)} trades de qualité retenus ({len(df)/initial_count*100:.1f}% du dataset)")

if len(df) < 100:
    print("[ERROR] Dataset trop petit après filtrage, augmentez timeframe_days")
    sys.exit(1)

# Étape 3: Analyser distribution PNL
print("\n[3/6] Analyse distribution PNL...")

if 'target_pnl' in df.columns:
    pnl_mean = df['target_pnl'].mean()
    pnl_std = df['target_pnl'].std()
    pnl_min = df['target_pnl'].min()
    pnl_max = df['target_pnl'].max()
    
    win_count = (df['target_pnl'] > 0).sum()
    loss_count = (df['target_pnl'] <= 0).sum()
    win_ratio = win_count / len(df) * 100
    
    print(f"PNL Distribution:")
    print(f"  Mean:  {pnl_mean:+.3f}%")
    print(f"  Std:   {pnl_std:.3f}%")
    print(f"  Min:   {pnl_min:+.3f}%")
    print(f"  Max:   {pnl_max:+.3f}%")
    print(f"\nWIN/LOSS:")
    print(f"  WIN:   {win_count:4} trades ({win_ratio:.1f}%)")
    print(f"  LOSS:  {loss_count:4} trades ({100-win_ratio:.1f}%)")

# Étape 4: Entraînement RÉGRESSION
print("\n[4/6] Entraînement XGBoost Régression...")
print("[INFO] Différence clé vs classification:")
print("  - Prédire PNL% directement (régression)")
print("  - Pas de class weights (inutile pour régression)")
print("  - Objectif: minimiser MAE / maximiser R²")
print("")

from optimization.utils.temporal_split import temporal_train_test_split
from optimization.data.preprocessor import FeaturePreprocessor
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import logging

logger = logging.getLogger(__name__)

# Paramètres
timeframe_days = 270
test_size = 0.2
validation_size = 0.1

# Split temporel
train_df, val_df, test_df = temporal_train_test_split(
    df,
    target_col='target_pnl',  # PNL% au lieu de target_win
    test_size=test_size,
    validation_size=validation_size,
    timestamp_col='timestamp'
)

# Séparer X, y
exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
feature_cols = [col for col in train_df.columns if col not in exclude_cols]

X_train = train_df[feature_cols].copy()
y_train = train_df['target_pnl'].copy()  # PNL% (régression)

X_val = val_df[feature_cols].copy()
y_val = val_df['target_pnl'].copy()

X_test = test_df[feature_cols].copy()
y_test = test_df['target_pnl'].copy()

print(f"[INFO] Split temporel:")
print(f"  Train: {len(X_train)} samples")
print(f"  Val:   {len(X_val)} samples")
print(f"  Test:  {len(X_test)} samples")

# Feature selection (top-K)
max_features = 40
print(f"\n[INFO] Sélection top {max_features} features...")

from sklearn.feature_selection import mutual_info_regression  # Régression!

mi_scores = mutual_info_regression(
    X_train.fillna(0),
    y_train,
    random_state=42
)

import pandas as pd
mi_df = pd.DataFrame({
    'feature': feature_cols,
    'mi_score': mi_scores
}).sort_values('mi_score', ascending=False)

selected_features = mi_df.head(max_features)['feature'].tolist()

print(f"[OK] Top 10 features:")
for i, row in mi_df.head(10).iterrows():
    print(f"  {i+1}. {row['feature']}: {row['mi_score']:.4f}")

# Filtrer datasets
X_train = X_train[selected_features]
X_val = X_val[selected_features]
X_test = X_test[selected_features]

# Preprocessing
print("\n[INFO] Preprocessing (imputation + scaling)...")

preprocessor = FeaturePreprocessor(scaler_type='robust')
X_train_scaled, _ = preprocessor.fit_transform(
    pd.concat([X_train, y_train.rename('target_pnl')], axis=1),
    target_col='target_pnl'
)

X_val_scaled = preprocessor.transform(X_val)
X_test_scaled = preprocessor.transform(X_test)

# Entraîner modèle RÉGRESSION
print("\n[INFO] Entraînement XGBRegressor...")

model = XGBRegressor(
    n_estimators=600,
    max_depth=4,
    learning_rate=0.03,
    min_child_weight=5,
    reg_alpha=1.0,
    reg_lambda=3.0,
    subsample=0.7,
    colsample_bytree=0.7,
    gamma=0.5,
    random_state=42,
    objective='reg:squarederror',  # Régression!
    eval_metric='mae',
    n_jobs=-1
)

# Entraîner avec early stopping
eval_set = [(X_val_scaled, y_val)]

model.fit(
    X_train_scaled, 
    y_train,
    eval_set=eval_set,
    early_stopping_rounds=50,
    verbose=False
)

print(f"[OK] Entraînement terminé")

# Étape 5: Évaluer RÉGRESSION
print("\n[5/6] Évaluation régression...")

# Prédictions
y_train_pred = model.predict(X_train_scaled)
y_val_pred = model.predict(X_val_scaled)
y_test_pred = model.predict(X_test_scaled)

# Métriques régression
train_mae = mean_absolute_error(y_train, y_train_pred)
train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
train_r2 = r2_score(y_train, y_train_pred)

val_mae = mean_absolute_error(y_val, y_val_pred)
val_rmse = np.sqrt(mean_squared_error(y_val, y_val_pred))
val_r2 = r2_score(y_val, y_val_pred)

test_mae = mean_absolute_error(y_test, y_test_pred)
test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
test_r2 = r2_score(y_test, y_test_pred)

print("\n" + "=" * 80)
print("  RÉSULTATS RÉGRESSION")
print("=" * 80)

print(f"\n[TRAIN]")
print(f"  MAE:   {train_mae:.3f}%")
print(f"  RMSE:  {train_rmse:.3f}%")
print(f"  R²:    {train_r2:.3f}")

print(f"\n[VAL]")
print(f"  MAE:   {val_mae:.3f}%")
print(f"  RMSE:  {val_rmse:.3f}%")
print(f"  R²:    {val_r2:.3f}")

print(f"\n[TEST]")
print(f"  MAE:   {test_mae:.3f}%")
print(f"  RMSE:  {test_rmse:.3f}%")
print(f"  R²:    {test_r2:.3f}")

# Étape 6: Classifier ensuite avec seuil
print("\n[6/6] Classification avec seuil optimisé...")

# Tester différents seuils
thresholds = [0.15, 0.20, 0.25, 0.30]
best_threshold = None
best_f1 = 0

print("\n[INFO] Test de différents seuils:")

from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

for threshold in thresholds:
    # Prédire WIN si PNL prédite > threshold
    y_test_pred_class = (y_test_pred > threshold).astype(int)
    y_test_actual_class = (y_test > 0).astype(int)
    
    accuracy = accuracy_score(y_test_actual_class, y_test_pred_class)
    precision = precision_score(y_test_actual_class, y_test_pred_class, zero_division=0)
    recall = recall_score(y_test_actual_class, y_test_pred_class, zero_division=0)
    f1 = f1_score(y_test_actual_class, y_test_pred_class, zero_division=0)
    
    print(f"  Seuil {threshold:.2f}%: Acc={accuracy:.1%}, Prec={precision:.1%}, Rec={recall:.1%}, F1={f1:.3f}")
    
    if f1 > best_f1:
        best_f1 = f1
        best_threshold = threshold

print(f"\n[OK] Meilleur seuil: {best_threshold:.2f}% (F1={best_f1:.3f})")

# Métriques finales avec meilleur seuil
y_test_pred_class = (y_test_pred > best_threshold).astype(int)
y_test_actual_class = (y_test > 0).astype(int)

final_accuracy = accuracy_score(y_test_actual_class, y_test_pred_class)
final_precision = precision_score(y_test_actual_class, y_test_pred_class, zero_division=0)
final_recall = recall_score(y_test_actual_class, y_test_pred_class, zero_division=0)
final_f1 = f1_score(y_test_actual_class, y_test_pred_class, zero_division=0)

print("\n" + "=" * 80)
print("  MÉTRIQUES CLASSIFICATION FINALES")
print("=" * 80)

print(f"\nSeuil optimal: {best_threshold:.2f}%")
print(f"Accuracy:  {final_accuracy:.1%}")
print(f"Precision: {final_precision:.1%}")
print(f"Recall:    {final_recall:.1%}")
print(f"F1 Score:  {final_f1:.3f}")

# Verdict
print("\n" + "=" * 80)
print("  VERDICT")
print("=" * 80)

if test_r2 > 0.30 and test_mae < 0.60 and final_f1 > 0.30:
    print("\n[OK] EXCELLENT ! Régression réussie")
    print("     Métriques conformes:")
    print(f"     - R² > 0.30 ({test_r2:.3f})")
    print(f"     - MAE < 0.60% ({test_mae:.3f}%)")
    print(f"     - F1 > 0.30 ({final_f1:.3f})")
    print("\n[INFO] Prochaines étapes:")
    print("  1. Sauvegarder modèle")
    print("  2. Tester en backtest")
    print("  3. Déployer en production")
    
elif test_r2 > 0.20 and test_mae < 0.80:
    print("\n[INFO] BON ! Régression acceptable")
    print(f"     R²: {test_r2:.3f} (objectif: > 0.30)")
    print(f"     MAE: {test_mae:.3f}% (objectif: < 0.60%)")
    print(f"     F1: {final_f1:.3f} (objectif: > 0.30)")
    print("\n[INFO] Recommandations:")
    print("  1. Augmenter timeframe_days (365+)")
    print("  2. Affiner hyperparamètres")
    print("  3. Feature engineering supplémentaire")
    
else:
    print("\n[WARNING] INSUFFISANT ! Régression peu prédictive")
    print(f"     R²: {test_r2:.3f} (objectif: > 0.30)")
    print(f"     MAE: {test_mae:.3f}% (objectif: < 0.60%)")
    print(f"     F1: {final_f1:.3f} (objectif: > 0.30)")
    print("\n[INFO] Actions recommandées:")
    print("  1. Augmenter dataset (365 jours)")
    print("  2. Classifier en 3 classes (BIG_WIN/NEUTRAL/BIG_LOSS)")
    print("  3. Vérifier qualité des données")
    print("  4. Walk-forward validation")

# Sauvegarder rapport
print("\n" + "=" * 80)
print("  SAUVEGARDE")
print("=" * 80)

rapport_path = Path("RAPPORT_REGRESSION_V2.txt")
with open(rapport_path, 'w', encoding='utf-8') as f:
    f.write("=" * 80 + "\n")
    f.write("  RAPPORT RÉGRESSION XGBOOST V2\n")
    f.write("=" * 80 + "\n\n")
    f.write(f"Dataset: {len(df)} trades (timeframe={timeframe_days} days)\n\n")
    f.write("MÉTRIQUES RÉGRESSION:\n")
    f.write(f"  Train MAE:  {train_mae:.3f}%\n")
    f.write(f"  Train RMSE: {train_rmse:.3f}%\n")
    f.write(f"  Train R²:   {train_r2:.3f}\n\n")
    f.write(f"  Test MAE:   {test_mae:.3f}%\n")
    f.write(f"  Test RMSE:  {test_rmse:.3f}%\n")
    f.write(f"  Test R²:    {test_r2:.3f}\n\n")
    f.write("MÉTRIQUES CLASSIFICATION:\n")
    f.write(f"  Seuil optimal: {best_threshold:.2f}%\n")
    f.write(f"  Accuracy:  {final_accuracy:.3f}\n")
    f.write(f"  Precision: {final_precision:.3f}\n")
    f.write(f"  Recall:    {final_recall:.3f}\n")
    f.write(f"  F1 Score:  {final_f1:.3f}\n\n")
    f.write("VERDICT:\n")
    if test_r2 > 0.30 and test_mae < 0.60 and final_f1 > 0.30:
        f.write("  EXCELLENT - Régression réussie\n")
    elif test_r2 > 0.20 and test_mae < 0.80:
        f.write("  BON - Régression acceptable\n")
    else:
        f.write("  INSUFFISANT - Régression peu prédictive\n")

print(f"[OK] Rapport sauvegardé: {rapport_path}")

# Sauvegarder modèle
from pathlib import Path
import joblib

model_dir = Path("optimization/saved_models")
model_dir.mkdir(parents=True, exist_ok=True)

model_path = model_dir / "xgboost_v2_regression.pkl"
joblib.dump(model, model_path)
print(f"[OK] Modèle sauvegardé: {model_path}")

preprocessor_path = model_dir / "preprocessor_v2_regression.pkl"
preprocessor.save(preprocessor_path)
print(f"[OK] Preprocessor sauvegardé: {preprocessor_path}")

print("\n" + "=" * 80)
print("  TERMINÉ")
print("=" * 80 + "\n")

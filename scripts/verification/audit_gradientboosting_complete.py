#!/usr/bin/env python3
"""
🔬 AUDIT COMPLET DU MODÈLE GRADIENTBOOSTING
============================================
Script d'analyse objective pour vérifier:
1. Validité des métriques actuelles
2. Présence d'overfitting
3. Performance réelle vs hasard
4. Stabilité temporelle
5. Possibilités d'amélioration
"""

import os
import sys
import json
import pickle
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import (
    cross_val_score, StratifiedKFold, TimeSeriesSplit,
    train_test_split, learning_curve
)
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    brier_score_loss
)
from sklearn.dummy import DummyClassifier
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

# Chemins
PROJECT_ROOT = Path(__file__).parent
MODELS_PATH = PROJECT_ROOT / "optimization" / "saved_models"
METADATA_FILE = MODELS_PATH / "gradient_boosting_optimized_metadata.json"
MODEL_FILE = MODELS_PATH / "gradient_boosting_optimized.pkl"

# Couleurs console
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

def print_ok(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_warn(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.ENDC}")


def load_data_from_db():
    """Charger les données depuis PostgreSQL"""
    print_header("1. CHARGEMENT DES DONNÉES")
    
    try:
        # Utiliser le même loader que l'optimisation
        from optimization.data.feature_loader import load_features_from_postgres
        from optimization.data.feature_engineering import calculate_derived_features
        
        df = load_features_from_postgres(timeframe_days=180, min_trades=1)
        print_ok(f"Données brutes chargées: {len(df)} lignes")
        
        # Feature engineering
        df = calculate_derived_features(df)
        print_ok(f"Après feature engineering: {len(df)} lignes, {len(df.columns)} colonnes")
        
        return df
    except Exception as e:
        print_warn(f"Erreur chargement PostgreSQL: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: charger depuis CSV si disponible
        csv_path = PROJECT_ROOT / "data" / "training_data.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            print_ok(f"Données CSV chargées: {len(df)} lignes")
            return df
        else:
            print_error("Aucune source de données disponible")
            return None


def load_metadata():
    """Charger les métadonnées du modèle"""
    if METADATA_FILE.exists():
        with open(METADATA_FILE) as f:
            return json.load(f)
    return None


def prepare_features(df, selected_features):
    """Préparer les features pour l'analyse"""
    print_header("2. PRÉPARATION DES FEATURES")
    
    # Vérifier la colonne target
    target_col = None
    for col in ['target_win', 'result', 'win', 'target', 'outcome']:
        if col in df.columns:
            target_col = col
            break
    
    if target_col is None:
        # Créer target depuis pnl_pct ou target_pnl si disponible
        if 'target_pnl' in df.columns:
            df['target'] = (df['target_pnl'] > 0).astype(int)
            target_col = 'target'
            print_info("Target créé depuis target_pnl")
        elif 'pnl_pct' in df.columns:
            df['target'] = (df['pnl_pct'] > 0).astype(int)
            target_col = 'target'
            print_info("Target créé depuis pnl_pct")
        else:
            print_error("Pas de colonne target trouvée")
            return None, None, None, None
    
    # Mapper vers 0/1 si nécessaire
    if df[target_col].dtype == 'object':
        df['target'] = df[target_col].map({'WIN': 1, 'LOSS': 0, 'win': 1, 'loss': 0})
    elif df[target_col].dtype == 'bool':
        df['target'] = df[target_col].astype(int)
    else:
        df['target'] = df[target_col]
    
    # Vérifier features disponibles
    available_features = [f for f in selected_features if f in df.columns]
    missing_features = [f for f in selected_features if f not in df.columns]
    
    print_info(f"Features disponibles: {len(available_features)}/{len(selected_features)}")
    if missing_features:
        print_warn(f"Features manquantes: {missing_features[:5]}...")
    
    # Filtrer données valides
    df_clean = df[available_features + ['target']].dropna()
    
    X = df_clean[available_features].values
    y = df_clean['target'].values
    
    # Vérifier distribution
    n_win = (y == 1).sum()
    n_loss = (y == 0).sum()
    ratio = n_win / len(y) * 100
    
    print_ok(f"Échantillons valides: {len(y)}")
    print_info(f"Distribution: {n_win} WIN ({ratio:.1f}%) / {n_loss} LOSS ({100-ratio:.1f}%)")
    
    return X, y, available_features, df_clean


def test_1_cross_validation_rigoureux(X, y, hyperparams):
    """Test 1: Validation croisée k-fold stratifiée"""
    print_header("TEST 1: VALIDATION CROISÉE STRATIFIÉE (K-FOLD)")
    
    # Scaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Modèle avec hyperparamètres optimisés
    model = GradientBoostingClassifier(
        n_estimators=hyperparams.get('n_estimators', 271),
        max_depth=hyperparams.get('max_depth', 6),
        learning_rate=hyperparams.get('learning_rate', 0.217),
        min_samples_split=hyperparams.get('min_samples_split', 48),
        min_samples_leaf=hyperparams.get('min_samples_leaf', 38),
        subsample=hyperparams.get('subsample', 0.734),
        max_features=hyperparams.get('max_features', 'sqrt'),
        random_state=42
    )
    
    # K-Fold stratifié (5 et 10 folds)
    results = {}
    
    for k in [5, 10]:
        cv = StratifiedKFold(n_splits=k, shuffle=True, random_state=42)
        
        scores_acc = cross_val_score(model, X_scaled, y, cv=cv, scoring='accuracy')
        scores_f1 = cross_val_score(model, X_scaled, y, cv=cv, scoring='f1')
        scores_auc = cross_val_score(model, X_scaled, y, cv=cv, scoring='roc_auc')
        
        results[k] = {
            'accuracy': (scores_acc.mean(), scores_acc.std()),
            'f1': (scores_f1.mean(), scores_f1.std()),
            'roc_auc': (scores_auc.mean(), scores_auc.std())
        }
        
        print(f"\n📊 {k}-Fold Stratifié:")
        print(f"   Accuracy: {scores_acc.mean():.4f} ± {scores_acc.std():.4f}")
        print(f"   F1 Score: {scores_f1.mean():.4f} ± {scores_f1.std():.4f}")
        print(f"   ROC AUC:  {scores_auc.mean():.4f} ± {scores_auc.std():.4f}")
    
    # Verdict
    avg_acc = results[5]['accuracy'][0]
    if avg_acc > 0.60:
        print_ok(f"CV Accuracy {avg_acc:.1%} > 60% = MODÈLE UTILE")
    elif avg_acc > 0.55:
        print_warn(f"CV Accuracy {avg_acc:.1%} entre 55-60% = LÉGÈRE UTILITÉ")
    else:
        print_error(f"CV Accuracy {avg_acc:.1%} < 55% = PAS MIEUX QUE LE HASARD")
    
    return results


def test_2_time_series_split(X, y, hyperparams, df_clean):
    """Test 2: Validation temporelle (éviter look-ahead bias)"""
    print_header("TEST 2: VALIDATION TEMPORELLE (TIME SERIES SPLIT)")
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = GradientBoostingClassifier(
        n_estimators=hyperparams.get('n_estimators', 271),
        max_depth=hyperparams.get('max_depth', 6),
        learning_rate=hyperparams.get('learning_rate', 0.217),
        min_samples_split=hyperparams.get('min_samples_split', 48),
        min_samples_leaf=hyperparams.get('min_samples_leaf', 38),
        subsample=hyperparams.get('subsample', 0.734),
        max_features=hyperparams.get('max_features', 'sqrt'),
        random_state=42
    )
    
    # Time Series Split (5 splits)
    tscv = TimeSeriesSplit(n_splits=5)
    
    fold_results = []
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X_scaled)):
        X_train, X_test = X_scaled[train_idx], X_scaled[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        
        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_proba)
        
        fold_results.append({'fold': fold+1, 'acc': acc, 'f1': f1, 'auc': auc, 'n_test': len(y_test)})
        print(f"   Fold {fold+1}: Acc={acc:.3f}, F1={f1:.3f}, AUC={auc:.3f} (n={len(y_test)})")
    
    # Moyenne
    avg_acc = np.mean([r['acc'] for r in fold_results])
    avg_f1 = np.mean([r['f1'] for r in fold_results])
    avg_auc = np.mean([r['auc'] for r in fold_results])
    
    print(f"\n📊 Moyenne Time Series:")
    print(f"   Accuracy: {avg_acc:.4f}")
    print(f"   F1 Score: {avg_f1:.4f}")
    print(f"   ROC AUC:  {avg_auc:.4f}")
    
    # Vérifier dégradation temporelle
    first_fold = fold_results[0]['acc']
    last_fold = fold_results[-1]['acc']
    degradation = first_fold - last_fold
    
    if degradation > 0.1:
        print_warn(f"⚠️ Dégradation temporelle détectée: {degradation:.1%}")
        print_info("Le modèle se dégrade sur les données récentes")
    else:
        print_ok("Pas de dégradation temporelle significative")
    
    return {'avg_acc': avg_acc, 'avg_f1': avg_f1, 'avg_auc': avg_auc, 'folds': fold_results}


def test_3_comparison_baseline(X, y):
    """Test 3: Comparaison avec baselines"""
    print_header("TEST 3: COMPARAISON AVEC BASELINES")
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, stratify=y, random_state=42
    )
    
    baselines = {
        'Hasard (most_frequent)': DummyClassifier(strategy='most_frequent'),
        'Hasard (stratified)': DummyClassifier(strategy='stratified'),
        'Hasard (uniform)': DummyClassifier(strategy='uniform')
    }
    
    results = {}
    for name, clf in baselines.items():
        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        results[name] = acc
        print(f"   {name}: {acc:.4f}")
    
    # Notre modèle
    from sklearn.ensemble import GradientBoostingClassifier
    our_model = GradientBoostingClassifier(random_state=42)
    our_model.fit(X_train, y_train)
    our_acc = accuracy_score(y_test, our_model.predict(X_test))
    results['GradientBoosting'] = our_acc
    print(f"\n   🎯 GradientBoosting: {our_acc:.4f}")
    
    # Amélioration vs hasard
    best_baseline = max([v for k, v in results.items() if 'Hasard' in k])
    improvement = (our_acc - best_baseline) / best_baseline * 100
    
    if improvement > 15:
        print_ok(f"Amélioration vs hasard: +{improvement:.1f}% = SIGNIFICATIF")
    elif improvement > 5:
        print_warn(f"Amélioration vs hasard: +{improvement:.1f}% = MARGINAL")
    else:
        print_error(f"Amélioration vs hasard: +{improvement:.1f}% = NON SIGNIFICATIF")
    
    return results


def test_4_overfitting_detection(X, y, hyperparams):
    """Test 4: Détection d'overfitting via learning curves"""
    print_header("TEST 4: DÉTECTION D'OVERFITTING")
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = GradientBoostingClassifier(
        n_estimators=hyperparams.get('n_estimators', 271),
        max_depth=hyperparams.get('max_depth', 6),
        learning_rate=hyperparams.get('learning_rate', 0.217),
        random_state=42
    )
    
    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, stratify=y, random_state=42
    )
    
    model.fit(X_train, y_train)
    
    train_acc = accuracy_score(y_train, model.predict(X_train))
    test_acc = accuracy_score(y_test, model.predict(X_test))
    
    print(f"   Accuracy Train: {train_acc:.4f}")
    print(f"   Accuracy Test:  {test_acc:.4f}")
    
    gap = train_acc - test_acc
    print(f"   Gap (Train-Test): {gap:.4f}")
    
    if gap > 0.15:
        print_error(f"⚠️ OVERFITTING SÉVÈRE: Gap {gap:.1%}")
        print_info("Le modèle mémorise les données d'entraînement")
    elif gap > 0.08:
        print_warn(f"⚠️ Overfitting modéré: Gap {gap:.1%}")
    else:
        print_ok(f"Pas d'overfitting significatif: Gap {gap:.1%}")
    
    return {'train_acc': train_acc, 'test_acc': test_acc, 'gap': gap}


def test_5_calibration(X, y, hyperparams):
    """Test 5: Calibration des probabilités"""
    print_header("TEST 5: CALIBRATION DES PROBABILITÉS")
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, stratify=y, random_state=42
    )
    
    model = GradientBoostingClassifier(
        n_estimators=hyperparams.get('n_estimators', 271),
        max_depth=hyperparams.get('max_depth', 6),
        learning_rate=hyperparams.get('learning_rate', 0.217),
        random_state=42
    )
    
    model.fit(X_train, y_train)
    y_proba = model.predict_proba(X_test)[:, 1]
    
    # Brier Score (plus bas = mieux calibré)
    brier = brier_score_loss(y_test, y_proba)
    print(f"   Brier Score: {brier:.4f} (plus bas = mieux)")
    
    # Analyser la fiabilité des prédictions à haute confiance
    high_conf_mask = (y_proba > 0.7) | (y_proba < 0.3)
    if high_conf_mask.sum() > 10:
        high_conf_acc = accuracy_score(y_test[high_conf_mask], (y_proba[high_conf_mask] > 0.5).astype(int))
        print(f"   Accuracy haute confiance (>70%): {high_conf_acc:.4f} ({high_conf_mask.sum()} samples)")
    
    # Bins de confiance
    print("\n   📊 Fiabilité par niveau de confiance:")
    bins = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
    for low, high in bins:
        mask = (y_proba >= low) & (y_proba < high)
        if mask.sum() >= 5:
            bin_acc = accuracy_score(y_test[mask], (y_proba[mask] > 0.5).astype(int))
            print(f"      Conf {low:.0%}-{high:.0%}: Accuracy {bin_acc:.1%} (n={mask.sum()})")
    
    if brier < 0.20:
        print_ok("Bonnes probabilités calibrées")
    else:
        print_warn("Probabilités mal calibrées - ne pas se fier aux %")
    
    return {'brier_score': brier}


def test_6_feature_importance(X, y, feature_names, hyperparams):
    """Test 6: Analyse des features importantes"""
    print_header("TEST 6: IMPORTANCE DES FEATURES")
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = GradientBoostingClassifier(
        n_estimators=hyperparams.get('n_estimators', 271),
        max_depth=hyperparams.get('max_depth', 6),
        learning_rate=hyperparams.get('learning_rate', 0.217),
        random_state=42
    )
    
    model.fit(X_scaled, y)
    
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1]
    
    print("\n   🏆 Top 10 features les plus importantes:")
    for i in range(min(10, len(feature_names))):
        idx = indices[i]
        print(f"      {i+1}. {feature_names[idx]}: {importances[idx]:.4f}")
    
    # Vérifier concentration
    top5_importance = sum(importances[indices[:5]])
    print(f"\n   📊 Concentration: Top 5 = {top5_importance:.1%} de l'importance totale")
    
    if top5_importance > 0.7:
        print_warn("Haute concentration sur quelques features - risque de fragilité")
    else:
        print_ok("Importance bien distribuée")
    
    return {feature_names[i]: importances[i] for i in indices[:10]}


def test_7_monte_carlo_stability(X, y, hyperparams, n_iterations=20):
    """Test 7: Stabilité Monte Carlo (différents splits)"""
    print_header("TEST 7: STABILITÉ MONTE CARLO")
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    results = []
    for seed in range(n_iterations):
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, stratify=y, random_state=seed
        )
        
        model = GradientBoostingClassifier(
            n_estimators=hyperparams.get('n_estimators', 271),
            max_depth=hyperparams.get('max_depth', 6),
            learning_rate=hyperparams.get('learning_rate', 0.217),
            random_state=42
        )
        
        model.fit(X_train, y_train)
        acc = accuracy_score(y_test, model.predict(X_test))
        results.append(acc)
    
    mean_acc = np.mean(results)
    std_acc = np.std(results)
    min_acc = np.min(results)
    max_acc = np.max(results)
    
    print(f"   {n_iterations} itérations avec différents splits:")
    print(f"   Accuracy moyenne: {mean_acc:.4f}")
    print(f"   Écart-type: {std_acc:.4f}")
    print(f"   Min/Max: {min_acc:.4f} / {max_acc:.4f}")
    
    if std_acc < 0.03:
        print_ok("Modèle stable (faible variance)")
    elif std_acc < 0.05:
        print_warn("Variance modérée")
    else:
        print_error("Haute variance - résultats instables")
    
    return {'mean': mean_acc, 'std': std_acc, 'min': min_acc, 'max': max_acc}


def test_8_improvement_suggestions(X, y, cv_results, overfitting_results):
    """Test 8: Suggestions d'amélioration"""
    print_header("TEST 8: SUGGESTIONS D'AMÉLIORATION")
    
    suggestions = []
    
    # Vérifier si plus de données aiderait
    n_samples = len(y)
    if n_samples < 1000:
        suggestions.append(f"📈 Plus de données: Seulement {n_samples} échantillons. Viser 2000+")
    
    # Vérifier overfitting
    if overfitting_results['gap'] > 0.10:
        suggestions.append("🔽 Réduire max_depth (essayer 4-5 au lieu de 6)")
        suggestions.append("🔽 Augmenter min_samples_leaf (essayer 50-60)")
        suggestions.append("📉 Réduire n_estimators (essayer 150-200)")
    
    # Vérifier variance
    cv_std = cv_results[5]['accuracy'][1]
    if cv_std > 0.04:
        suggestions.append("🎲 Haute variance: Essayer ensembling (BaggingClassifier)")
    
    # Distribution déséquilibrée
    win_ratio = (y == 1).sum() / len(y)
    if win_ratio < 0.4 or win_ratio > 0.6:
        suggestions.append(f"⚖️ Déséquilibre {win_ratio:.1%} WIN: Essayer class_weight='balanced'")
    
    # Suggestions génériques
    suggestions.append("🧪 Essayer d'autres modèles: RandomForest, XGBoost, LightGBM")
    suggestions.append("📊 Ajouter features: sentiment, volume profile, market regime")
    suggestions.append("⏰ Feature lag: Inclure valeurs t-1, t-2 pour capturer dynamique")
    
    for i, suggestion in enumerate(suggestions, 1):
        print(f"   {i}. {suggestion}")
    
    return suggestions


def generate_final_verdict(all_results):
    """Générer le verdict final"""
    print_header("🎯 VERDICT FINAL")
    
    cv_acc = all_results['cv'][5]['accuracy'][0]
    ts_acc = all_results['time_series']['avg_acc']
    gap = all_results['overfitting']['gap']
    mc_std = all_results['monte_carlo']['std']
    
    print(f"\n📊 RÉSUMÉ DES TESTS:")
    print(f"   CV Accuracy (5-fold): {cv_acc:.1%}")
    print(f"   Time Series Accuracy: {ts_acc:.1%}")
    print(f"   Gap Train-Test: {gap:.1%}")
    print(f"   Monte Carlo Std: {mc_std:.4f}")
    
    # Score global
    score = 0
    max_score = 5
    
    if cv_acc > 0.58:
        score += 1
        print_ok("CV Accuracy > 58%")
    else:
        print_error("CV Accuracy < 58%")
    
    if ts_acc > 0.55:
        score += 1
        print_ok("Time Series Accuracy > 55%")
    else:
        print_error("Time Series Accuracy < 55%")
    
    if gap < 0.12:
        score += 1
        print_ok("Pas d'overfitting sévère")
    else:
        print_error("Overfitting détecté")
    
    if mc_std < 0.04:
        score += 1
        print_ok("Modèle stable")
    else:
        print_warn("Modèle instable")
    
    # Amélioration vs hasard
    baseline_acc = 0.5  # Hasard
    if cv_acc > baseline_acc + 0.08:
        score += 1
        print_ok(f"Amélioration significative vs hasard (+{(cv_acc-baseline_acc)*100:.1f}%)")
    else:
        print_error("Amélioration insuffisante vs hasard")
    
    print(f"\n{'='*60}")
    print(f"   SCORE GLOBAL: {score}/{max_score}")
    print(f"{'='*60}")
    
    if score >= 4:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ VERDICT: MODÈLE UTILE - Recommandé pour filtrage{Colors.ENDC}")
        print(f"   Le modèle offre une amélioration réelle par rapport au hasard.")
        print(f"   Suggestion: Utiliser avec confiance > 60%")
    elif score >= 3:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️ VERDICT: UTILITÉ MARGINALE - À utiliser avec précaution{Colors.ENDC}")
        print(f"   Le modèle offre une légère amélioration mais n'est pas fiable.")
        print(f"   Suggestion: Utiliser uniquement pour filtrer les trades à haute confiance (>70%)")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ VERDICT: MODÈLE NON RECOMMANDÉ{Colors.ENDC}")
        print(f"   Le modèle n'offre pas d'amélioration significative vs le hasard.")
        print(f"   Suggestion: Désactiver le filtre ML ou réentraîner avec plus de données")
    
    return score


def main():
    """Exécution de l'audit complet"""
    print(f"\n{'='*60}")
    print(f"🔬 AUDIT COMPLET DU MODÈLE GRADIENTBOOSTING")
    print(f"   Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Charger métadonnées
    metadata = load_metadata()
    if not metadata:
        print_error("Métadonnées non trouvées")
        return
    
    print(f"\n📋 Modèle: {metadata.get('model_name')}")
    print(f"   Entraîné le: {metadata.get('trained_at')}")
    print(f"   Métriques annoncées: Acc={metadata['metrics']['test']['accuracy']:.1%}, F1={metadata['metrics']['test']['f1']:.2f}")
    
    hyperparams = metadata.get('hyperparameters', {})
    selected_features = metadata.get('selected_features', [])
    
    # Charger données
    df = load_data_from_db()
    if df is None:
        return
    
    # Préparer features
    result = prepare_features(df, selected_features)
    if result[0] is None:
        return
    
    X, y, feature_names, df_clean = result
    
    # Exécuter tous les tests
    all_results = {}
    
    all_results['cv'] = test_1_cross_validation_rigoureux(X, y, hyperparams)
    all_results['time_series'] = test_2_time_series_split(X, y, hyperparams, df_clean)
    all_results['baseline'] = test_3_comparison_baseline(X, y)
    all_results['overfitting'] = test_4_overfitting_detection(X, y, hyperparams)
    all_results['calibration'] = test_5_calibration(X, y, hyperparams)
    all_results['features'] = test_6_feature_importance(X, y, feature_names, hyperparams)
    all_results['monte_carlo'] = test_7_monte_carlo_stability(X, y, hyperparams)
    
    test_8_improvement_suggestions(X, y, all_results['cv'], all_results['overfitting'])
    
    # Verdict final
    score = generate_final_verdict(all_results)
    
    # Sauvegarder résultats
    results_file = PROJECT_ROOT / "audit_gradientboosting_results.json"
    
    # Convertir numpy pour JSON
    def convert_numpy(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, dict):
            return {k: convert_numpy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy(i) for i in obj]
        elif isinstance(obj, tuple):
            return tuple(convert_numpy(i) for i in obj)
        return obj
    
    with open(results_file, 'w') as f:
        json.dump(convert_numpy(all_results), f, indent=2)
    
    print(f"\n📁 Résultats sauvegardés: {results_file}")
    
    return all_results


if __name__ == "__main__":
    main()

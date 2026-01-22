#!/usr/bin/env python3
"""
🚀 ENTRAÎNEMENT XGBOOST OPTIMISÉ

Version optimisée de XGBoost avec les mêmes améliorations que GradientBoosting.
Compare XGBoost vs GradientBoosting pour choisir le meilleur.
"""
import logging
import sys
import json
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from xgboost import XGBClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_and_prepare_data():
    """Charger et préparer les données"""
    logger.info("📊 Chargement données...")
    
    from optimization.data.feature_loader import load_features_from_postgres
    from optimization.data.feature_engineering import calculate_derived_features
    
    base_df = load_features_from_postgres(timeframe_days=120, min_trades=30)
    df = calculate_derived_features(base_df)
    
    logger.info(f"✅ {len(df)} samples chargés")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Feature engineering optimisé"""
    logger.info("🔧 Feature engineering...")
    
    # Features temporelles (CRITIQUE!)
    if 'timestamp' in df.columns:
        ts = pd.to_datetime(df['timestamp'])
        df['hour'] = ts.dt.hour
        df['day_of_week'] = ts.dt.dayofweek
        df['good_hour'] = df['hour'].isin([2, 12, 16]).astype(int)
        df['bad_hour'] = df['hour'].isin([4, 23, 18]).astype(int)
        df['asian_session'] = df['hour'].isin(range(0, 8)).astype(int)
        df['european_session'] = df['hour'].isin(range(8, 16)).astype(int)
        df['american_session'] = df['hour'].isin(range(16, 24)).astype(int)
    
    # Features momentum
    if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
        df['rsi_momentum'] = df['rsi_1m'] - df['rsi_5m']
        df['rsi_oversold'] = (df['rsi_1m'] < 30).astype(int)
        df['rsi_overbought'] = (df['rsi_1m'] > 70).astype(int)
    
    if 'macd_hist_1m' in df.columns and 'macd_hist_5m' in df.columns:
        df['macd_momentum'] = df['macd_hist_1m'] - df['macd_hist_5m']
        df['macd_aligned'] = ((df['macd_hist_1m'] > 0) == (df['macd_hist_5m'] > 0)).astype(int)
    
    if 'atr_pct_1m' in df.columns:
        df['high_volatility'] = (df['atr_pct_1m'] > df['atr_pct_1m'].median()).astype(int)
    
    if 'adx_1m' in df.columns:
        df['strong_trend'] = (df['adx_1m'] > 25).astype(int)
        df['weak_trend'] = (df['adx_1m'] < 20).astype(int)
    
    if 'volume_ratio_1m' in df.columns:
        df['volume_spike'] = (df['volume_ratio_1m'] > 1.5).astype(int)
    
    return df


def prepare_features(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Nettoyer et préparer features"""
    exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                   'is_opportunity', 'date']
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    feature_cols = [c for c in numeric_cols if c not in exclude_cols]
    
    # Supprimer colonnes constantes
    constant_cols = [c for c in feature_cols if df[c].nunique() <= 1]
    feature_cols = [c for c in feature_cols if c not in constant_cols]
    
    # Supprimer colonnes avec trop de NULL
    high_null = [c for c in feature_cols if df[c].isnull().sum() / len(df) > 0.3]
    feature_cols = [c for c in feature_cols if c not in high_null]
    
    logger.info(f"✅ {len(feature_cols)} features retenues")
    
    X = df[feature_cols].fillna(0).values
    y = df['target_win'].astype(int).values
    
    return X, y, feature_cols


def temporal_split(df, X, y):
    """Split temporel"""
    n = len(df)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)
    
    if 'timestamp' in df.columns:
        sort_idx = df['timestamp'].argsort().values
        X = X[sort_idx]
        y = y[sort_idx]
    
    return (X[:train_end], X[train_end:val_end], X[val_end:],
            y[:train_end], y[train_end:val_end], y[val_end:])


def train_and_compare():
    """Entraîner et comparer XGBoost vs GradientBoosting"""
    logger.info("=" * 70)
    logger.info("🔬 COMPARAISON XGBOOST vs GRADIENTBOOSTING")
    logger.info("=" * 70)
    
    # Préparer données
    df = load_and_prepare_data()
    df = engineer_features(df)
    X, y, feature_cols = prepare_features(df)
    X_train, X_val, X_test, y_train, y_val, y_test = temporal_split(df, X, y)
    
    logger.info(f"\n📊 Split: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
    logger.info(f"   Win rate: Train={y_train.mean():.1%}, Val={y_val.mean():.1%}, Test={y_test.mean():.1%}")
    
    # Scaler
    scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    results = {}
    
    # ========== XGBOOST OPTIMISÉ ==========
    logger.info("\n" + "=" * 50)
    logger.info("🎯 XGBOOST OPTIMISÉ")
    logger.info("=" * 50)
    
    xgb_model = XGBClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.03,
        min_child_weight=15,
        reg_alpha=5.0,
        reg_lambda=8.0,
        subsample=0.7,
        colsample_bytree=0.6,
        gamma=2.0,
        scale_pos_weight=1.2,  # Ajuster pour classes déséquilibrées
        random_state=42,
        eval_metric='logloss',
        use_label_encoder=False
    )
    
    xgb_model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_val_scaled, y_val)],
        verbose=False
    )
    
    xgb_train_pred = xgb_model.predict(X_train_scaled)
    xgb_test_pred = xgb_model.predict(X_test_scaled)
    
    xgb_train_acc = accuracy_score(y_train, xgb_train_pred)
    xgb_test_acc = accuracy_score(y_test, xgb_test_pred)
    xgb_test_f1 = f1_score(y_test, xgb_test_pred, zero_division=0)
    xgb_test_prec = precision_score(y_test, xgb_test_pred, zero_division=0)
    
    logger.info(f"   Train Accuracy: {xgb_train_acc:.1%}")
    logger.info(f"   Test Accuracy:  {xgb_test_acc:.1%}")
    logger.info(f"   Gap:            {xgb_train_acc - xgb_test_acc:.1%}")
    logger.info(f"   Test F1:        {xgb_test_f1:.3f}")
    logger.info(f"   Test Precision: {xgb_test_prec:.3f}")
    
    results['xgboost'] = {
        'train_acc': xgb_train_acc,
        'test_acc': xgb_test_acc,
        'test_f1': xgb_test_f1,
        'test_precision': xgb_test_prec
    }
    
    # ========== GRADIENTBOOSTING ==========
    logger.info("\n" + "=" * 50)
    logger.info("🎯 GRADIENTBOOSTING")
    logger.info("=" * 50)
    
    gb_model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.03,
        min_samples_split=30,
        min_samples_leaf=15,
        subsample=0.7,
        max_features=0.5,
        random_state=42,
        validation_fraction=0.15,
        n_iter_no_change=30
    )
    
    gb_model.fit(X_train_scaled, y_train)
    
    gb_train_pred = gb_model.predict(X_train_scaled)
    gb_test_pred = gb_model.predict(X_test_scaled)
    
    gb_train_acc = accuracy_score(y_train, gb_train_pred)
    gb_test_acc = accuracy_score(y_test, gb_test_pred)
    gb_test_f1 = f1_score(y_test, gb_test_pred, zero_division=0)
    gb_test_prec = precision_score(y_test, gb_test_pred, zero_division=0)
    
    logger.info(f"   Train Accuracy: {gb_train_acc:.1%}")
    logger.info(f"   Test Accuracy:  {gb_test_acc:.1%}")
    logger.info(f"   Gap:            {gb_train_acc - gb_test_acc:.1%}")
    logger.info(f"   Test F1:        {gb_test_f1:.3f}")
    logger.info(f"   Test Precision: {gb_test_prec:.3f}")
    
    results['gradientboosting'] = {
        'train_acc': gb_train_acc,
        'test_acc': gb_test_acc,
        'test_f1': gb_test_f1,
        'test_precision': gb_test_prec
    }
    
    # ========== COMPARAISON ==========
    logger.info("\n" + "=" * 70)
    logger.info("📊 COMPARAISON FINALE")
    logger.info("=" * 70)
    
    logger.info(f"\n{'Métrique':<20} {'XGBoost':<15} {'GradientBoosting':<15} {'Gagnant':<15}")
    logger.info("-" * 65)
    
    xgb_wins = 0
    gb_wins = 0
    
    for metric in ['test_acc', 'test_f1', 'test_precision']:
        xgb_val = results['xgboost'][metric]
        gb_val = results['gradientboosting'][metric]
        winner = 'XGBoost' if xgb_val > gb_val else 'GradientBoosting' if gb_val > xgb_val else 'Égalité'
        
        if winner == 'XGBoost':
            xgb_wins += 1
        elif winner == 'GradientBoosting':
            gb_wins += 1
        
        metric_name = metric.replace('test_', '').replace('_', ' ').title()
        logger.info(f"{metric_name:<20} {xgb_val:<15.3f} {gb_val:<15.3f} {winner:<15}")
    
    # Gap (moins c'est mieux)
    xgb_gap = results['xgboost']['train_acc'] - results['xgboost']['test_acc']
    gb_gap = results['gradientboosting']['train_acc'] - results['gradientboosting']['test_acc']
    gap_winner = 'XGBoost' if xgb_gap < gb_gap else 'GradientBoosting'
    logger.info(f"{'Overfitting Gap':<20} {xgb_gap:<15.3f} {gb_gap:<15.3f} {gap_winner:<15}")
    
    logger.info("\n" + "=" * 70)
    overall_winner = 'XGBoost' if xgb_wins > gb_wins else 'GradientBoosting'
    logger.info(f"🏆 GAGNANT: {overall_winner}")
    logger.info("=" * 70)
    
    # Sauvegarder le meilleur
    models_dir = Path("optimization/saved_models")
    models_dir.mkdir(parents=True, exist_ok=True)
    
    if xgb_test_acc >= gb_test_acc:
        best_model = xgb_model
        best_name = 'xgboost'
        best_metrics = results['xgboost']
    else:
        best_model = gb_model
        best_name = 'gradientboosting'
        best_metrics = results['gradientboosting']
    
    # Pipeline
    pipeline = Pipeline([
        ('scaler', scaler),
        ('model', best_model)
    ])
    
    # Sauvegarder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = models_dir / f"best_classifier_{timestamp}.pkl"
    latest_path = models_dir / "best_classifier_latest.pkl"
    
    joblib.dump(pipeline, model_path)
    joblib.dump(pipeline, latest_path)
    
    metadata = {
        'timestamp': timestamp,
        'best_model': best_name,
        'metrics': best_metrics,
        'feature_cols': feature_cols,
        'comparison': results
    }
    
    with open(models_dir / "best_classifier_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"\n💾 Meilleur modèle ({best_name}) sauvegardé: {latest_path}")
    
    return results


def main():
    results = train_and_compare()
    
    # Succès si au moins un modèle > 55%
    best_acc = max(results['xgboost']['test_acc'], results['gradientboosting']['test_acc'])
    if best_acc >= 0.55:
        logger.info("\n✅ SUCCÈS: Modèle performant créé!")
        sys.exit(0)
    else:
        logger.warning("\n⚠️ Modèles peu performants")
        sys.exit(1)


if __name__ == "__main__":
    main()

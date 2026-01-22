#!/usr/bin/env python3
"""
OPTUNA GRADIENTBOOSTING OPTIMIZER
=================================
Optimisation des hyperparamètres GradientBoosting avec validation rigoureuse.

Garanties:
- Cross-validation 5-fold stratifiée (pas de data leakage)
- Holdout test set séparé (20% jamais vu pendant l'optimisation)
- Score composite pénalisant l'overfitting
- Métriques répétables (seeds fixes)
- Early stopping si overfitting détecté
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold, train_test_split
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from datetime import datetime
import json
import logging
import warnings
import joblib

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# Constantes
RANDOM_STATE = 42
CV_FOLDS = 5
TEST_SIZE = 0.2  # 20% holdout
MIN_TRADES_REQUIRED = 100


class GradientBoostingOptimizer:
    """Optimiseur Optuna pour GradientBoosting avec validation rigoureuse"""
    
    def __init__(self, n_trials: int = 100, timeout_minutes: int = 30, use_histgb: bool = False):
        self.n_trials = n_trials
        self.timeout = timeout_minutes * 60
        self.use_histgb = use_histgb  # HistGradientBoosting = 10x plus rapide
        self.study = None
        self.best_params = None
        self.best_metrics = None
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.feature_names = None
        
        if use_histgb:
            logger.info("⚡ Mode HistGradientBoosting activé (10x plus rapide)")
        
    def load_data(self, timeframe_days: int = 365):
        """Charge les données depuis PostgreSQL"""
        from optimization.data.feature_loader import load_features_from_postgres
        
        logger.info(f"📊 Chargement des données (timeframe={timeframe_days} jours)...")
        
        df = load_features_from_postgres(
            min_trades=MIN_TRADES_REQUIRED,
            timeframe_days=timeframe_days,
            include_open_trades=False
        )
        
        if len(df) < MIN_TRADES_REQUIRED:
            raise ValueError(f"Pas assez de trades: {len(df)} < {MIN_TRADES_REQUIRED}")
        
        # Préparer features
        exclude_cols = [
            'scan_id', 'timestamp', 'symbol', 'opportunity_direction',
            'target_win', 'target_pnl', 'is_opportunity',
            'reject_reason_category'
        ]
        
        feature_cols = [col for col in df.columns 
                        if col not in exclude_cols 
                        and df[col].dtype in ['float64', 'int64', 'float32', 'int32']]
        
        X = df[feature_cols].fillna(0)
        y = df['target_win'].dropna().astype(int)
        
        # Aligner X et y
        valid_idx = y.index
        X = X.loc[valid_idx]
        
        self.feature_names = feature_cols
        
        # Split train/test AVANT optimisation (holdout)
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
        )
        
        logger.info(f"✅ Données chargées: {len(X)} trades, {len(feature_cols)} features")
        logger.info(f"   Train: {len(self.X_train)}, Test (holdout): {len(self.X_test)}")
        logger.info(f"   Win rate: {y.mean()*100:.1f}%")
        
        return len(X)
    
    def objective(self, trial: optuna.Trial) -> float:
        """Fonction objectif pour Optuna avec score composite anti-overfitting"""
        
        if self.use_histgb:
            # HistGradientBoosting - paramètres légèrement différents
            params = {
                'max_iter': trial.suggest_int('n_estimators', 50, 500, step=25),       # = n_estimators
                'max_depth': trial.suggest_int('max_depth', 2, 6),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.30, log=True),
                'min_samples_leaf': trial.suggest_int('min_samples_leaf', 10, 80, step=10),
                'l2_regularization': trial.suggest_float('l2_regularization', 0.0, 1.0, step=0.1),
                'max_bins': 255,
                'random_state': RANDOM_STATE
            }
            model = HistGradientBoostingClassifier(**params)
        else:
            # GradientBoosting standard (plages alignées avec sliders frontend)
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 500, step=25),      # Slider: 50-500
                'max_depth': trial.suggest_int('max_depth', 2, 6),                         # Select: 2-6
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.30, log=True), # Slider: 0.01-0.30
                'min_samples_split': trial.suggest_int('min_samples_split', 10, 120, step=10), # Slider: 10-120
                'min_samples_leaf': trial.suggest_int('min_samples_leaf', 10, 80, step=10),  # Slider: 10-80
                'subsample': trial.suggest_float('subsample', 0.5, 1.0, step=0.05),        # Slider: 0.5-1.0
                'max_features': trial.suggest_float('max_features', 0.3, 1.0, step=0.1),   # Slider: 0.3-1.0
                'random_state': RANDOM_STATE
            }
            model = GradientBoostingClassifier(**params)
        
        # Cross-validation stratifiée sur le train set uniquement
        cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
        
        # Scores CV
        cv_scores = cross_val_score(model, self.X_train, self.y_train, cv=cv, scoring='accuracy')
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()
        
        # Entraîner sur tout le train set pour mesurer overfitting
        model.fit(self.X_train, self.y_train)
        train_acc = model.score(self.X_train, self.y_train)
        
        # Overfitting gap
        gap = train_acc - cv_mean
        
        # Pénaliser fortement l'overfitting
        # Score composite: CV accuracy - pénalité overfitting - pénalité instabilité
        # Plus le gap est grand, plus on pénalise
        overfitting_penalty = max(0, gap - 0.10) * 2  # Pénaliser si gap > 10%
        stability_penalty = cv_std * 0.5  # Pénaliser l'instabilité
        
        composite_score = cv_mean - overfitting_penalty - stability_penalty
        
        # Early pruning si overfitting sévère
        if gap > 0.30:
            raise optuna.TrialPruned()
        
        # Stocker métriques pour analyse
        trial.set_user_attr('cv_mean', cv_mean)
        trial.set_user_attr('cv_std', cv_std)
        trial.set_user_attr('train_acc', train_acc)
        trial.set_user_attr('overfitting_gap', gap)
        
        return composite_score
    
    def optimize(self, n_trials: int = None, timeout_minutes: int = None) -> dict:
        """Lance l'optimisation Optuna"""
        
        if self.X_train is None:
            raise ValueError("Données non chargées. Appelez load_data() d'abord.")
        
        n_trials = n_trials or self.n_trials
        timeout = (timeout_minutes or self.timeout // 60) * 60
        
        logger.info(f"🚀 Démarrage optimisation: {n_trials} trials, timeout={timeout//60}min")
        
        # Créer étude Optuna
        sampler = TPESampler(seed=RANDOM_STATE)
        pruner = MedianPruner(n_startup_trials=10, n_warmup_steps=5)
        
        self.study = optuna.create_study(
            direction='maximize',
            sampler=sampler,
            pruner=pruner,
            study_name='gradientboosting_optimization'
        )
        
        # Optimiser
        self.study.optimize(
            self.objective,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=True,
            n_jobs=1  # Séquentiel pour reproductibilité
        )
        
        self.best_params = self.study.best_params
        
        logger.info(f"✅ Optimisation terminée: {len(self.study.trials)} trials")
        logger.info(f"   Meilleur score composite: {self.study.best_value:.4f}")
        
        return self.best_params
    
    def validate_on_holdout(self) -> dict:
        """Validation finale sur le holdout test set (jamais vu pendant l'optimisation)"""
        
        if self.best_params is None:
            raise ValueError("Pas de meilleurs paramètres. Appelez optimize() d'abord.")
        
        logger.info("🔬 Validation sur holdout test set...")
        
        # Entraîner modèle final avec best params
        if self.use_histgb:
            # Convertir n_estimators -> max_iter pour HistGB
            params = {k: v for k, v in self.best_params.items()}
            if 'n_estimators' in params:
                params['max_iter'] = params.pop('n_estimators')
            # Supprimer les params non supportés par HistGB
            for key in ['min_samples_split', 'subsample', 'max_features']:
                params.pop(key, None)
            params['random_state'] = RANDOM_STATE
            final_model = HistGradientBoostingClassifier(**params)
        else:
            final_model = GradientBoostingClassifier(
                **self.best_params,
                random_state=RANDOM_STATE
            )
        final_model.fit(self.X_train, self.y_train)
        
        # Prédictions sur holdout
        y_pred = final_model.predict(self.X_test)
        y_proba = final_model.predict_proba(self.X_test)[:, 1]
        
        # Métriques sur train
        train_acc = final_model.score(self.X_train, self.y_train)
        
        # Métriques sur holdout (VRAIES métriques)
        test_acc = accuracy_score(self.y_test, y_pred)
        f1 = f1_score(self.y_test, y_pred)
        precision = precision_score(self.y_test, y_pred)
        recall = recall_score(self.y_test, y_pred)
        roc_auc = roc_auc_score(self.y_test, y_proba)
        
        # Overfitting gap final
        overfitting_gap = train_acc - test_acc
        
        self.best_metrics = {
            'train_accuracy': round(train_acc, 4),
            'test_accuracy': round(test_acc, 4),
            'overfitting_gap': round(overfitting_gap, 4),
            'f1_score': round(f1, 4),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'roc_auc': round(roc_auc, 4),
            'n_train_samples': len(self.X_train),
            'n_test_samples': len(self.X_test),
            'n_features': len(self.feature_names)
        }
        
        logger.info(f"📊 Métriques finales (holdout):")
        logger.info(f"   Train accuracy: {train_acc*100:.2f}%")
        logger.info(f"   Test accuracy:  {test_acc*100:.2f}%")
        logger.info(f"   Overfitting gap: {overfitting_gap*100:.2f}%")
        logger.info(f"   F1 Score: {f1:.4f}")
        logger.info(f"   Precision: {precision:.4f}")
        logger.info(f"   Recall: {recall:.4f}")
        logger.info(f"   ROC AUC: {roc_auc:.4f}")
        
        # Sauvegarder le modèle final
        self._save_model(final_model)
        
        return self.best_metrics
    
    def _save_model(self, model):
        """Sauvegarde le modèle et les métadonnées"""
        save_dir = os.path.join(os.path.dirname(__file__), 'saved_models')
        os.makedirs(save_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Sauvegarder modèle
        model_path = os.path.join(save_dir, f'gb_optuna_{timestamp}.pkl')
        joblib.dump(model, model_path)
        
        # Sauvegarder aussi comme "latest"
        latest_path = os.path.join(save_dir, 'gb_optuna_latest.pkl')
        joblib.dump(model, latest_path)
        
        # Métadonnées
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'best_params': self.best_params,
            'metrics': self.best_metrics,
            'n_trials': len(self.study.trials) if self.study else 0,
            'feature_names': self.feature_names,
            'model_path': model_path
        }
        
        metadata_path = os.path.join(save_dir, 'gb_optuna_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"💾 Modèle sauvegardé: {model_path}")
        
    def get_results_summary(self) -> dict:
        """Retourne un résumé complet des résultats"""
        
        if self.study is None:
            return {'error': 'Optimisation non effectuée'}
        
        # Top 5 trials
        top_trials = sorted(
            self.study.trials,
            key=lambda t: t.value if t.value else -999,
            reverse=True
        )[:5]
        
        return {
            'status': 'completed',
            'timestamp': datetime.now().isoformat(),
            'best_params': self.best_params,
            'best_score_composite': round(self.study.best_value, 4),
            'metrics_holdout': self.best_metrics,
            'n_trials_completed': len([t for t in self.study.trials if t.value]),
            'n_trials_pruned': len([t for t in self.study.trials if t.state == optuna.trial.TrialState.PRUNED]),
            'top_5_trials': [
                {
                    'trial': t.number,
                    'score': round(t.value, 4) if t.value else None,
                    'cv_mean': round(t.user_attrs.get('cv_mean', 0), 4),
                    'overfitting_gap': round(t.user_attrs.get('overfitting_gap', 0), 4),
                    'params': t.params
                }
                for t in top_trials if t.value
            ]
        }


def run_optimization(n_trials: int = 100, timeout_minutes: int = 30, timeframe_days: int = 365) -> dict:
    """Point d'entrée pour lancer l'optimisation"""
    
    print("=" * 70)
    print("  OPTUNA GRADIENTBOOSTING OPTIMIZER")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    optimizer = GradientBoostingOptimizer(n_trials=n_trials, timeout_minutes=timeout_minutes)
    
    # Charger données
    n_samples = optimizer.load_data(timeframe_days=timeframe_days)
    print(f"\n📊 {n_samples} trades chargés")
    
    # Optimiser
    print(f"\n🚀 Optimisation: {n_trials} trials (max {timeout_minutes}min)...")
    best_params = optimizer.optimize()
    
    print("\n" + "=" * 70)
    print("  MEILLEURS HYPERPARAMÈTRES")
    print("=" * 70)
    for k, v in best_params.items():
        print(f"   {k}: {v}")
    
    # Validation finale
    print("\n" + "=" * 70)
    print("  VALIDATION HOLDOUT (métriques réelles)")
    print("=" * 70)
    metrics = optimizer.validate_on_holdout()
    
    # Résumé
    results = optimizer.get_results_summary()
    
    # Sauvegarder résultats
    results_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'optuna_gb_results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Résultats sauvegardés: {results_path}")
    
    print("\n" + "=" * 70)
    print("  RÉSUMÉ FINAL")
    print("=" * 70)
    print(f"   Test Accuracy (holdout): {metrics['test_accuracy']*100:.2f}%")
    print(f"   Overfitting Gap: {metrics['overfitting_gap']*100:.2f}%")
    print(f"   F1 Score: {metrics['f1_score']:.4f}")
    print(f"   Trials complétés: {results['n_trials_completed']}")
    print(f"   Trials pruned (overfitting): {results['n_trials_pruned']}")
    print("=" * 70)
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Optuna GradientBoosting Optimizer')
    parser.add_argument('--trials', type=int, default=100, help='Nombre de trials')
    parser.add_argument('--timeout', type=int, default=30, help='Timeout en minutes')
    parser.add_argument('--days', type=int, default=365, help='Timeframe en jours')
    
    args = parser.parse_args()
    
    results = run_optimization(
        n_trials=args.trials,
        timeout_minutes=args.timeout,
        timeframe_days=args.days
    )

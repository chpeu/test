#!/usr/bin/env python3
"""
🔄 BOUCLE OPTIMISATION + ENTRAÎNEMENT AUTOMATIQUE
=================================================
Optimise les hyperparamètres puis entraîne le modèle
avec les meilleurs paramètres trouvés.

Usage:
    python scripts/optimize_and_train_loop.py --trials 100 --metric f1_score
    python scripts/optimize_and_train_loop.py --trials 200 --metric trading_composite
"""

import sys
import os
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

import optuna
from optuna.samplers import TPESampler
import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import f1_score, accuracy_score, precision_score, recall_score, roc_auc_score
from xgboost import XGBClassifier

from optimization.ml_pipeline import prepare_training_dataset, split_training_dataset
from optimization.data.feature_loader import build_config_filter_conditions

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MLOptimizerLoop:
    """
    Boucle d'optimisation et entraînement ML.
    
    1. Charge les données filtrées (même config)
    2. Optimise les hyperparamètres avec Optuna
    3. Entraîne le modèle final avec les meilleurs params
    4. Sauvegarde les résultats
    """
    
    def __init__(
        self,
        metric: str = "f1_score",
        n_trials: int = 100,
        timeframe_days: int = 365,
        use_filtered_data: bool = True,  # True = trades même config
        output_dir: str = "data"
    ):
        self.metric = metric
        self.n_trials = n_trials
        self.timeframe_days = timeframe_days
        self.use_filtered_data = use_filtered_data
        self.output_dir = Path(output_dir)
        
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.best_params = None
        self.best_score = None
        self.final_metrics = None
        
    def load_data(self):
        """
        Charge et prépare les données d'entraînement.
        
        IMPORTANT: Utilise le MÊME filtre complet que le compteur UI
        (build_config_filter_conditions) pour garantir la cohérence.
        Le nombre de trades doit correspondre au compteur "Trades ML utilisables".
        """
        logger.info(f"📥 Chargement données (filtered={self.use_filtered_data}, days={self.timeframe_days})")
        logger.info("   ⚠️ Utilise le filtre complet de build_config_filter_conditions()")
        
        dataset = prepare_training_dataset(
            timeframe_days=self.timeframe_days,
            min_trades=100,
            include_engineered=True
        )
        
        # Split train/test
        self.X_train, self.X_test, self.y_train, self.y_test = split_training_dataset(
            dataset.X, dataset.y,
            test_size=0.2,
            random_state=42
        )
        
        logger.info(f"✅ Données chargées: {len(self.X_train)} train, {len(self.X_test)} test")
        logger.info(f"   Distribution train: {self.y_train.value_counts().to_dict()}")
        logger.info(f"   Distribution test: {self.y_test.value_counts().to_dict()}")
        
        return self
    
    def _create_objective(self):
        """Crée la fonction objectif Optuna."""
        
        def objective(trial):
            # Hyperparamètres à optimiser
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'max_depth': trial.suggest_int('max_depth', 2, 6),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 15),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'colsample_bylevel': trial.suggest_float('colsample_bylevel', 0.6, 1.0),
                'reg_alpha': trial.suggest_float('reg_alpha', 0.01, 15.0, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 0.01, 15.0, log=True),
                'gamma': trial.suggest_float('gamma', 0.0, 5.0),
                'scale_pos_weight': trial.suggest_float('scale_pos_weight', 0.8, 1.5),
            }
            
            model = XGBClassifier(
                **params,
                objective='binary:logistic',
                eval_metric='logloss',
                use_label_encoder=False,
                random_state=42,
                n_jobs=-1
            )
            
            # Cross-validation
            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            
            if self.metric == 'f1_score':
                scores = cross_val_score(model, self.X_train, self.y_train, cv=cv, scoring='f1')
            elif self.metric == 'accuracy':
                scores = cross_val_score(model, self.X_train, self.y_train, cv=cv, scoring='accuracy')
            elif self.metric == 'roc_auc':
                scores = cross_val_score(model, self.X_train, self.y_train, cv=cv, scoring='roc_auc')
            elif self.metric == 'trading_composite':
                # Métrique composite : 0.4*accuracy + 0.4*f1 + 0.2*(1-overfitting)
                acc_scores = cross_val_score(model, self.X_train, self.y_train, cv=cv, scoring='accuracy')
                f1_scores = cross_val_score(model, self.X_train, self.y_train, cv=cv, scoring='f1')
                
                # Estimer overfitting
                model.fit(self.X_train, self.y_train)
                train_acc = accuracy_score(self.y_train, model.predict(self.X_train))
                cv_acc = np.mean(acc_scores)
                overfitting = max(0, train_acc - cv_acc)
                
                scores = 0.4 * acc_scores + 0.4 * f1_scores + 0.2 * (1 - overfitting)
            else:
                scores = cross_val_score(model, self.X_train, self.y_train, cv=cv, scoring='f1')
            
            return np.mean(scores)
        
        return objective
    
    def optimize(self):
        """Lance l'optimisation Optuna."""
        logger.info(f"🔍 Démarrage optimisation Optuna ({self.n_trials} trials, metric={self.metric})")
        
        study = optuna.create_study(
            direction='maximize',
            sampler=TPESampler(seed=42),
            study_name=f"xgb_optimize_{self.metric}"
        )
        
        objective = self._create_objective()
        
        study.optimize(
            objective,
            n_trials=self.n_trials,
            show_progress_bar=True,
            callbacks=[self._log_progress]
        )
        
        self.best_params = study.best_params
        self.best_score = study.best_value
        
        logger.info(f"✅ Optimisation terminée!")
        logger.info(f"   Best score ({self.metric}): {self.best_score:.4f}")
        logger.info(f"   Best params: {json.dumps(self.best_params, indent=2)}")
        
        # Sauvegarder résultats Optuna
        self._save_optuna_results(study)
        
        return self
    
    def _log_progress(self, study, trial):
        """Callback pour logger la progression."""
        if trial.number % 10 == 0:
            logger.info(f"   Trial {trial.number}: {trial.value:.4f} (best: {study.best_value:.4f})")
    
    def train_final_model(self):
        """Entraîne le modèle final avec les meilleurs paramètres."""
        if self.best_params is None:
            raise ValueError("Aucun paramètre optimisé. Lancez optimize() d'abord.")
        
        logger.info("🎯 Entraînement modèle final avec meilleurs paramètres...")
        
        model = XGBClassifier(
            **self.best_params,
            objective='binary:logistic',
            eval_metric='logloss',
            use_label_encoder=False,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(
            self.X_train, self.y_train,
            eval_set=[(self.X_test, self.y_test)],
            verbose=False
        )
        
        # Évaluer sur test set
        y_pred = model.predict(self.X_test)
        y_pred_proba = model.predict_proba(self.X_test)[:, 1]
        
        train_pred = model.predict(self.X_train)
        
        self.final_metrics = {
            'train_accuracy': accuracy_score(self.y_train, train_pred),
            'test_accuracy': accuracy_score(self.y_test, y_pred),
            'precision': precision_score(self.y_test, y_pred),
            'recall': recall_score(self.y_test, y_pred),
            'f1_score': f1_score(self.y_test, y_pred),
            'roc_auc': roc_auc_score(self.y_test, y_pred_proba),
            'overfitting_gap': accuracy_score(self.y_train, train_pred) - accuracy_score(self.y_test, y_pred),
            'n_train_samples': len(self.X_train),
            'n_test_samples': len(self.X_test),
            'n_features': self.X_train.shape[1]
        }
        
        logger.info("=" * 60)
        logger.info("📊 MÉTRIQUES FINALES")
        logger.info("=" * 60)
        logger.info(f"   Train Accuracy: {self.final_metrics['train_accuracy']:.2%}")
        logger.info(f"   Test Accuracy:  {self.final_metrics['test_accuracy']:.2%}")
        logger.info(f"   Overfitting:    {self.final_metrics['overfitting_gap']:.2%}")
        logger.info(f"   Precision:      {self.final_metrics['precision']:.2%}")
        logger.info(f"   Recall:         {self.final_metrics['recall']:.2%}")
        logger.info(f"   F1 Score:       {self.final_metrics['f1_score']:.4f}")
        logger.info(f"   ROC-AUC:        {self.final_metrics['roc_auc']:.4f}")
        logger.info("=" * 60)
        
        # Sauvegarder modèle
        self._save_model(model)
        
        return self
    
    def _save_optuna_results(self, study):
        """Sauvegarde les résultats Optuna."""
        results = {
            'status': 'completed',
            'timestamp': datetime.now().isoformat(),
            'metric': self.metric,
            'best_params': self.best_params,
            'best_score': self.best_score,
            'n_trials': self.n_trials,
            'use_filtered_data': self.use_filtered_data,
            'n_train_samples': len(self.X_train),
            'top_5_trials': [
                {
                    'trial': t.number,
                    'score': t.value,
                    'params': t.params
                }
                for t in sorted(study.trials, key=lambda t: t.value or 0, reverse=True)[:5]
            ]
        }
        
        output_file = self.output_dir / f"optuna_loop_results_{self.metric}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"💾 Résultats Optuna sauvegardés: {output_file}")
    
    def _save_model(self, model):
        """Sauvegarde le modèle et ses métadonnées."""
        import joblib
        
        model_dir = ROOT_DIR / "optimization" / "saved_models"
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Sauvegarder modèle
        model_path = model_dir / "best_classifier_latest.pkl"
        joblib.dump(model, model_path)
        
        # Sauvegarder métadonnées
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'metric_optimized': self.metric,
            'best_params': self.best_params,
            'best_cv_score': self.best_score,
            'final_metrics': self.final_metrics,
            'n_trials': self.n_trials,
            'use_filtered_data': self.use_filtered_data,
            'feature_names': list(self.X_train.columns)
        }
        
        metadata_path = model_dir / "best_classifier_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"💾 Modèle sauvegardé: {model_path}")
        logger.info(f"💾 Métadonnées sauvegardées: {metadata_path}")
        
        # Mettre à jour config_overrides.json avec les nouveaux params
        self._update_config_overrides()
    
    def _update_config_overrides(self):
        """Met à jour config_overrides.json avec les params optimisés."""
        config_path = ROOT_DIR / "config_overrides.json"
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except:
            config = {}
        
        # Mapper les params vers les clés ml_*
        param_mapping = {
            'n_estimators': 'ml_n_estimators',
            'max_depth': 'ml_max_depth',
            'learning_rate': 'ml_learning_rate',
            'min_child_weight': 'ml_min_child_weight',
            'reg_alpha': 'ml_reg_alpha',
            'reg_lambda': 'ml_reg_lambda',
            'subsample': 'ml_subsample',
            'colsample_bytree': 'ml_colsample_bytree',
            'colsample_bylevel': 'ml_colsample_bylevel',
            'gamma': 'ml_gamma',
            'scale_pos_weight': 'ml_scale_pos_weight'
        }
        
        for optuna_key, config_key in param_mapping.items():
            if optuna_key in self.best_params:
                config[config_key] = self.best_params[optuna_key]
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"✅ config_overrides.json mis à jour avec les nouveaux paramètres ML")
    
    def run(self):
        """Exécute la boucle complète: load -> optimize -> train."""
        logger.info("=" * 60)
        logger.info("🚀 DÉMARRAGE BOUCLE OPTIMISATION + ENTRAÎNEMENT")
        logger.info("=" * 60)
        
        self.load_data()
        self.optimize()
        self.train_final_model()
        
        logger.info("=" * 60)
        logger.info("✅ BOUCLE TERMINÉE AVEC SUCCÈS")
        logger.info("=" * 60)
        
        return self.final_metrics


def main():
    parser = argparse.ArgumentParser(description="Boucle optimisation + entraînement ML")
    parser.add_argument('--trials', type=int, default=100, help="Nombre de trials Optuna")
    parser.add_argument('--metric', type=str, default='f1_score', 
                       choices=['f1_score', 'accuracy', 'roc_auc', 'trading_composite'],
                       help="Métrique à optimiser")
    parser.add_argument('--days', type=int, default=365, help="Fenêtre temporelle en jours")
    parser.add_argument('--all-data', action='store_true', 
                       help="Utiliser tous les trades (pas seulement ceux avec même config)")
    
    args = parser.parse_args()
    
    optimizer = MLOptimizerLoop(
        metric=args.metric,
        n_trials=args.trials,
        timeframe_days=args.days,
        use_filtered_data=not args.all_data
    )
    
    metrics = optimizer.run()
    
    print("\n" + "=" * 60)
    print("RESULTATS FINAUX")
    print("=" * 60)
    print(json.dumps(metrics, indent=2, default=str))


if __name__ == "__main__":
    main()

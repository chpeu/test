"""
Optimisation d'hyperparamètres ML avec Optuna
Support multi-CPU/GPU pour performances maximales
"""
import logging
import time
import json
import os
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import numpy as np
from pathlib import Path

import optuna
from optuna.pruners import MedianPruner, HyperbandPruner
from optuna.samplers import TPESampler
from optuna.trial import Trial
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import xgboost as xgb

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features
from optimization.data.preprocessor import FeaturePreprocessor
from config import ML_CONFIG, TRADING_CONFIG

logger = logging.getLogger(__name__)


class TradingMetric:
    """
    Métrique custom pour le trading qui combine:
    - F1-score (équilibre précision/recall)
    - Win rate (taux de victoires)
    - ROC AUC (capacité de discrimination)
    """
    
    @staticmethod
    def calculate(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray) -> float:
        """
        Calcule métrique custom pour le trading
        
        Args:
            y_true: Labels réels (0=loss, 1=win)
            y_pred: Prédictions binaires
            y_proba: Probabilités de classe 1
            
        Returns:
            Score composite (0-1, plus haut = meilleur)
        """
        try:
            # F1-score (équilibre precision/recall) - poids 40%
            f1 = f1_score(y_true, y_pred, zero_division=0)
            
            # Win rate (accuracy sur classe 1 uniquement) - poids 30%
            win_mask = y_true == 1
            if win_mask.sum() > 0:
                win_rate = (y_pred[win_mask] == 1).mean()
            else:
                win_rate = 0.0
            
            # ROC AUC (capacité discrimination) - poids 20%
            try:
                auc = roc_auc_score(y_true, y_proba)
            except:
                auc = 0.5
            
            # Recall (éviter de manquer des wins) - poids 10%
            recall = recall_score(y_true, y_pred, zero_division=0)
            
            # Score composite pondéré
            composite_score = (
                0.40 * f1 +
                0.30 * win_rate +
                0.20 * auc +
                0.10 * recall
            )
            
            return composite_score
            
        except Exception as e:
            logger.error(f"Erreur calcul métrique: {e}")
            return 0.0


class HyperparameterTuner:
    """
    Optimiseur d'hyperparamètres avec support multi-CPU/GPU
    Utilise Optuna avec optimisation bayésienne (TPE)
    """
    
    def __init__(
        self,
        study_name: str = "xgboost_trading_optimization",
        storage: Optional[str] = None,
        n_trials: int = 100,
        timeout: Optional[int] = None,
        n_jobs: int = -1,
        gpu_id: Optional[int] = None,
        metric: str = "trading_composite",
        cv_folds: int = 5,
        pruning: bool = True
    ):
        """
        Args:
            study_name: Nom de l'étude Optuna
            storage: URL de stockage (sqlite:///optuna.db ou postgresql://...)
            n_trials: Nombre d'essais max
            timeout: Timeout en secondes (None = illimité)
            n_jobs: Nombre de CPU (-1 = tous, 1 = séquentiel)
            gpu_id: ID du GPU à utiliser (None = CPU, 0 = GPU 0)
            metric: Métrique à optimiser (trading_composite, f1_score, accuracy)
            cv_folds: Nombre de folds pour validation croisée
            pruning: Activer pruning automatique
        """
        self.study_name = study_name
        self.n_trials = n_trials
        self.timeout = timeout
        self.n_jobs = n_jobs
        self.gpu_id = gpu_id
        self.metric = metric
        self.cv_folds = cv_folds
        self.pruning = pruning
        
        # Storage par défaut: PostgreSQL si disponible, sinon SQLite
        if storage is None:
            # Essayer PostgreSQL (même DB que trading data)
            try:
                from core.postgresql_datalogger import PostgreSQLDataLogger
                db_config = PostgreSQLDataLogger.get_db_config()
                storage = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
                logger.info("📊 Optuna: Utilisation de PostgreSQL pour stockage")
            except:
                # Fallback: SQLite local
                storage = "sqlite:///optuna_studies.db"
                logger.info("📊 Optuna: Utilisation de SQLite pour stockage")
        
        self.storage = storage
        
        # Sampler et Pruner
        sampler = TPESampler(
            n_startup_trials=10,  # Random pour les 10 premiers
            multivariate=True,  # Corrélations entre hyperparams
            seed=42
        )
        
        if pruning:
            # HyperbandPruner: Plus agressif, meilleur pour beaucoup d'essais
            pruner = HyperbandPruner(
                min_resource=1,
                max_resource=cv_folds,
                reduction_factor=3
            )
        else:
            pruner = optuna.pruners.NopPruner()
        
        # Créer ou charger étude
        self.study = optuna.create_study(
            study_name=study_name,
            storage=storage,
            sampler=sampler,
            pruner=pruner,
            direction="maximize",
            load_if_exists=True
        )
        
        logger.info(
            f"🎯 HyperparameterTuner initialisé:\n"
            f"  - Study: {study_name}\n"
            f"  - Storage: {storage}\n"
            f"  - Trials: {n_trials}\n"
            f"  - CPUs: {n_jobs if n_jobs > 0 else os.cpu_count()}\n"
            f"  - GPU: {'GPU ' + str(gpu_id) if gpu_id is not None else 'CPU only'}\n"
            f"  - Metric: {metric}\n"
            f"  - CV Folds: {cv_folds}\n"
            f"  - Pruning: {pruning}"
        )
    
    def _suggest_hyperparameters(self, trial: Trial) -> Dict[str, Any]:
        """
        Définir l'espace de recherche des hyperparamètres
        
        Args:
            trial: Trial Optuna
            
        Returns:
            Dict d'hyperparamètres suggérés
        """
        params = {
            # Profondeur et structure
            'max_depth': trial.suggest_int('max_depth', 2, 6),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 20),
            
            # Régularisation L1/L2
            'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 10.0),
            'reg_lambda': trial.suggest_float('reg_lambda', 1.0, 15.0),
            
            # Échantillonnage
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'colsample_bylevel': trial.suggest_float('colsample_bylevel', 0.5, 1.0),
            
            # Learning
            'learning_rate': trial.suggest_float('learning_rate', 0.005, 0.05, log=True),
            'n_estimators': trial.suggest_int('n_estimators', 200, 1000, step=100),
            
            # Autres params XGBoost
            'gamma': trial.suggest_float('gamma', 0.0, 5.0),
            'scale_pos_weight': trial.suggest_float('scale_pos_weight', 0.8, 1.5),
        }
        
        # Params GPU si disponible
        if self.gpu_id is not None:
            params['tree_method'] = 'gpu_hist'
            params['gpu_id'] = self.gpu_id
            params['predictor'] = 'gpu_predictor'
        else:
            params['tree_method'] = 'hist'  # Histogram-based (rapide CPU)
            params['n_jobs'] = -1  # Multi-threading
        
        return params
    
    def _objective(self, trial: Trial, X: np.ndarray, y: np.ndarray) -> float:
        """
        Fonction objectif à optimiser
        
        Args:
            trial: Trial Optuna
            X: Features (déjà preprocessed)
            y: Labels
            
        Returns:
            Score à maximiser
        """
        # Suggérer hyperparamètres
        params = self._suggest_hyperparameters(trial)
        
        # Validation croisée stratifiée
        cv = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=42)
        scores = []
        
        for fold_idx, (train_idx, val_idx) in enumerate(cv.split(X, y)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]
            
            # Entraîner modèle
            model = xgb.XGBClassifier(
                **params,
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss'
            )
            
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=50,
                verbose=False
            )
            
            # Prédictions
            y_pred = model.predict(X_val)
            y_proba = model.predict_proba(X_val)[:, 1]
            
            # Calculer métrique
            if self.metric == "trading_composite":
                score = TradingMetric.calculate(y_val, y_pred, y_proba)
            elif self.metric == "f1_score":
                score = f1_score(y_val, y_pred, zero_division=0)
            elif self.metric == "accuracy":
                score = accuracy_score(y_val, y_pred)
            elif self.metric == "roc_auc":
                score = roc_auc_score(y_val, y_proba)
            else:
                score = f1_score(y_val, y_pred, zero_division=0)
            
            scores.append(score)
            
            # Pruning: arrêter tôt si mauvais résultats
            trial.report(score, fold_idx)
            if trial.should_prune():
                raise optuna.TrialPruned()
        
        # Score moyen sur tous les folds
        mean_score = np.mean(scores)
        std_score = np.std(scores)
        
        # Log résultats
        logger.info(
            f"[Trial {trial.number}] {self.metric}={mean_score:.4f} (±{std_score:.4f}) | "
            f"max_depth={params['max_depth']}, lr={params['learning_rate']:.4f}"
        )
        
        return mean_score
    
    def optimize(
        self,
        X: np.ndarray,
        y: np.ndarray,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Lancer optimisation
        
        Args:
            X: Features (déjà preprocessed et selected)
            y: Labels
            show_progress: Afficher barre de progression
            
        Returns:
            Dict contenant best_params, best_score, study
        """
        logger.info(f"🚀 Démarrage optimisation hyperparamètres...")
        logger.info(f"📊 Dataset: {X.shape[0]} samples, {X.shape[1]} features")
        logger.info(f"📊 Distribution: {(y==1).sum()} wins, {(y==0).sum()} losses")
        
        start_time = time.time()
        
        # Callback pour afficher progression
        def callback(study, trial):
            if trial.state == optuna.trial.TrialState.COMPLETE:
                logger.info(
                    f"✅ Trial {trial.number}/{self.n_trials} complete | "
                    f"Best score: {study.best_value:.4f}"
                )
            elif trial.state == optuna.trial.TrialState.PRUNED:
                logger.info(f"✂️ Trial {trial.number} pruned (early stopping)")
        
        # Optimiser
        self.study.optimize(
            lambda trial: self._objective(trial, X, y),
            n_trials=self.n_trials,
            timeout=self.timeout,
            n_jobs=self.n_jobs,
            callbacks=[callback] if show_progress else None,
            show_progress_bar=show_progress
        )
        
        elapsed = time.time() - start_time
        
        # Résultats
        best_params = self.study.best_params
        best_score = self.study.best_value
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🏆 OPTIMISATION TERMINÉE EN {elapsed/60:.1f} minutes")
        logger.info(f"{'='*80}")
        logger.info(f"📊 Trials completés: {len([t for t in self.study.trials if t.state == optuna.trial.TrialState.COMPLETE])}")
        logger.info(f"✂️ Trials pruned: {len([t for t in self.study.trials if t.state == optuna.trial.TrialState.PRUNED])}")
        logger.info(f"\n🏆 MEILLEURS HYPERPARAMÈTRES:")
        for param, value in best_params.items():
            logger.info(f"  - {param}: {value}")
        logger.info(f"\n📈 Best {self.metric}: {best_score:.4f}")
        logger.info(f"{'='*80}\n")
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'best_trial': self.study.best_trial,
            'study': self.study,
            'elapsed_time': elapsed,
            'n_trials': len(self.study.trials)
        }
    
    def save_best_params(
        self,
        filepath: str = "config_overrides.json",
        prefix: str = "ml_"
    ):
        """
        Sauvegarder meilleurs paramètres dans config_overrides.json
        
        Args:
            filepath: Chemin du fichier config
            prefix: Préfixe des paramètres ML
        """
        try:
            # Charger config existante
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # Ajouter meilleurs params
            best_params = self.study.best_params
            for param, value in best_params.items():
                config_key = f"{prefix}{param}"
                config[config_key] = value
            
            # Sauvegarder
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"💾 Meilleurs paramètres sauvegardés dans {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde paramètres: {e}")
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """
        Récupérer historique d'optimisation
        
        Returns:
            Liste de dicts avec infos de chaque trial
        """
        history = []
        for trial in self.study.trials:
            history.append({
                'number': trial.number,
                'value': trial.value,
                'params': trial.params,
                'state': trial.state.name,
                'datetime': trial.datetime_start
            })
        return history
    
    @staticmethod
    def load_and_prepare_data(
        min_samples: int = 1000,
        max_samples: Optional[int] = None
    ) -> tuple:
        """
        Charger et préparer données pour optimisation
        
        Args:
            min_samples: Nombre minimum de samples requis
            max_samples: Limite de samples (pour rapidité, None = tous)
            
        Returns:
            (X_preprocessed, y, feature_names)
        """
        logger.info("📥 Chargement et préparation des données...")
        
        # Charger features depuis PostgreSQL
        df_features = load_features_from_postgres(
            min_trades=min_samples,
            max_trades=max_samples
        )
        
        if df_features is None or len(df_features) < min_samples:
            raise ValueError(
                f"Pas assez de données: {len(df_features) if df_features is not None else 0} < {min_samples}"
            )
        
        logger.info(f"📊 Données chargées: {len(df_features)} samples")
        
        # Feature engineering
        df_engineered = calculate_derived_features(df_features)
        
        # Renommer target_win en target pour compatibilité
        if 'target_win' in df_engineered.columns:
            df_engineered = df_engineered.rename(columns={'target_win': 'target'})
        
        # Vérifier que target existe
        if 'target' not in df_engineered.columns:
            raise ValueError("Colonne 'target' manquante dans les features (besoin de 'target_win' depuis PostgreSQL)")
        
        # Preprocessing (le preprocessor sépare X et y en interne)
        preprocessor = FeaturePreprocessor()
        X_preprocessed_df, y = preprocessor.fit_transform(df_engineered, target_col='target')
        
        # Convertir en numpy arrays
        X_preprocessed = X_preprocessed_df.values
        y = y.values
        feature_names = X_preprocessed_df.columns.tolist()
        
        logger.info(f"✅ Données préparées: {X_preprocessed.shape[0]} samples, {X_preprocessed.shape[1]} features")
        logger.info(f"📊 Distribution: {(y==1).sum()} wins ({(y==1).mean()*100:.1f}%), {(y==0).sum()} losses")
        
        return X_preprocessed, y, feature_names


def run_optimization(
    n_trials: int = 100,
    timeout: Optional[int] = None,
    n_jobs: int = -1,
    gpu_id: Optional[int] = None,
    metric: str = "trading_composite",
    save_config: bool = True,
    max_samples: Optional[int] = None
) -> Dict[str, Any]:
    """
    Fonction helper pour lancer optimisation complète
    
    Args:
        n_trials: Nombre d'essais
        timeout: Timeout en secondes
        n_jobs: Nombre de CPU (-1 = tous)
        gpu_id: ID GPU (None = CPU)
        metric: Métrique à optimiser
        save_config: Sauvegarder meilleurs params dans config
        max_samples: Limite de samples pour rapidité
        
    Returns:
        Résultats d'optimisation
    """
    # Charger données
    X, y, feature_names = HyperparameterTuner.load_and_prepare_data(
        max_samples=max_samples
    )
    
    # Créer tuner
    tuner = HyperparameterTuner(
        n_trials=n_trials,
        timeout=timeout,
        n_jobs=n_jobs,
        gpu_id=gpu_id,
        metric=metric
    )
    
    # Optimiser
    results = tuner.optimize(X, y)
    
    # Sauvegarder si demandé
    if save_config:
        tuner.save_best_params()
    
    return results

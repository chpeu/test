"""
Optuna Hyperparameter Tuner pour GradientBoosting / HistGradientBoosting
Recherche automatique des meilleurs hyperparamètres
"""

import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner
import numpy as np
import pandas as pd
import logging
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Literal
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import RobustScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, make_scorer
from sklearn.utils.class_weight import compute_class_weight
from sklearn.feature_selection import SelectKBest, f_classif

logger = logging.getLogger(__name__)

# Répertoire pour sauvegarder les résultats
OPTIMIZATION_DIR = Path(__file__).parent / "saved_models"
OPTIMIZATION_DIR.mkdir(parents=True, exist_ok=True)


class GradientBoostingOptunaOptimizer:
    """
    Optimiseur Optuna pour GradientBoosting / HistGradientBoosting
    Trouve automatiquement les meilleurs hyperparamètres
    
    model_type:
        - 'gb': GradientBoostingClassifier (standard, plus lent)
        - 'histgb': HistGradientBoostingClassifier (10x plus rapide, performances similaires)
    """
    
    def __init__(
        self,
        n_trials: int = 100,
        timeout_minutes: int = 30,
        cv_folds: int = 5,
        model_type: Literal['gb', 'histgb'] = 'gb',
        random_state: int = 42
    ):
        self.n_trials = n_trials
        self.timeout_seconds = timeout_minutes * 60
        self.cv_folds = cv_folds
        self.model_type = model_type
        self.random_state = random_state
        
        self.study: Optional[optuna.Study] = None
        self.best_params: Optional[Dict[str, Any]] = None
        self.best_score: float = 0.0
        self.optimization_history: list = []
        
        # État de l'optimisation
        self.is_running = False
        self.current_trial = 0
        self.start_time: Optional[float] = None
        
        logger.info(f"🔧 Optimiseur initialisé: model_type={model_type} ({'10x plus rapide' if model_type == 'histgb' else 'standard'})")
        
    def _create_objective(self, X: np.ndarray, y: np.ndarray):
        """Crée la fonction objectif pour Optuna avec gestion du déséquilibre"""
        
        # 🔥 FIX: Calculer les poids des classes pour gérer le déséquilibre
        class_weights = compute_class_weight('balanced', classes=np.unique(y), y=y)
        class_weight_dict = dict(zip(np.unique(y), class_weights))
        sample_weights = np.array([class_weight_dict[label] for label in y])
        
        # 🔥 FIX: Sélection de features AGGRESSIVE pour réduire dimensionalité et overfitting
        n_features_original = X.shape[1]
        # Réduire à 25 features max pour éviter overfitting avec petit dataset
        k_features = min(25, n_features_original)
        selector = SelectKBest(f_classif, k=k_features)
        X_selected = selector.fit_transform(X, y)
        logger.info(f"📊 Features réduites: {n_features_original} → {X_selected.shape[1]} (agressif pour réduire overfitting)")
        
        def objective(trial: optuna.Trial) -> float:
            # Paramètres communs - plages TRÈS conservatrices pour éviter overfitting
            n_estimators = trial.suggest_int('n_estimators', 100, 250, step=50)  # Réduit
            max_depth = trial.suggest_int('max_depth', 2, 3)  # Max 3 pour éviter surfit
            learning_rate = trial.suggest_float('learning_rate', 0.01, 0.05, log=True)  # Plus lent
            min_samples_leaf = trial.suggest_int('min_samples_leaf', 30, 50, step=5)  # Plus élevé pour régulariser
            
            # Créer le modèle selon le type
            if self.model_type == 'histgb':
                # HistGradientBoosting - 10x plus rapide
                # Note: HistGB a des paramètres légèrement différents
                model = HistGradientBoostingClassifier(
                    max_iter=n_estimators,
                    max_depth=max_depth,
                    learning_rate=learning_rate,
                    min_samples_leaf=min_samples_leaf,
                    l2_regularization=trial.suggest_float('l2_regularization', 0.0, 1.0),
                    max_bins=255,  # Optimisé pour vitesse
                    random_state=self.random_state,
                    early_stopping=True,
                    n_iter_no_change=10,
                    validation_fraction=0.1
                )
            else:
                # GradientBoosting standard
                min_samples_split = trial.suggest_int('min_samples_split', 10, 50, step=5)
                subsample = trial.suggest_float('subsample', 0.6, 0.9, step=0.05)
                max_features = trial.suggest_float('max_features', 0.4, 0.8, step=0.1)
                
                model = GradientBoostingClassifier(
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    learning_rate=learning_rate,
                    min_samples_split=min_samples_split,
                    min_samples_leaf=min_samples_leaf,
                    subsample=subsample,
                    max_features=max_features,
                    random_state=self.random_state,
                    validation_fraction=0.15,
                    n_iter_no_change=30
                )
            
            # Créer le pipeline
            pipeline = Pipeline([
                ('scaler', RobustScaler()),
                ('classifier', model)
            ])
            
            # Cross-validation stratifiée
            cv = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_state)
            
            try:
                # 🔥 FIX: Cross-validation manuelle pour éviter les problèmes de sample_weight dans pipeline
                from sklearn.metrics import f1_score as f1_metric, precision_score as prec_metric
                
                f1_scores = []
                precision_scores = []
                fold_errors = 0
                
                for train_idx, val_idx in cv.split(X_selected, y):
                    try:
                        X_cv_train, X_cv_val = X_selected[train_idx], X_selected[val_idx]
                        y_cv_train, y_cv_val = y[train_idx], y[val_idx]
                        sw_cv_train = sample_weights[train_idx]
                        
                        # Scaler
                        scaler_cv = RobustScaler()
                        X_cv_train_scaled = scaler_cv.fit_transform(X_cv_train)
                        X_cv_val_scaled = scaler_cv.transform(X_cv_val)
                        
                        # Clone du modèle pour ce fold
                        from sklearn.base import clone
                        model_cv = clone(model)
                        
                        # Fit avec sample_weight
                        model_cv.fit(X_cv_train_scaled, y_cv_train, sample_weight=sw_cv_train)
                        
                        # Predict
                        y_pred = model_cv.predict(X_cv_val_scaled)
                        
                        # Scores
                        f1 = f1_metric(y_cv_val, y_pred, zero_division=0)
                        prec = prec_metric(y_cv_val, y_pred, zero_division=0)
                        
                        f1_scores.append(f1)
                        precision_scores.append(prec)
                    except Exception as fold_e:
                        fold_errors += 1
                        # Utiliser des valeurs par défaut pour ce fold
                        f1_scores.append(0.3)
                        precision_scores.append(0.3)
                
                # Si tous les folds ont échoué, retourner score bas
                if fold_errors == self.cv_folds:
                    return 0.1
                
                f1_scores = np.array(f1_scores)
                precision_scores = np.array(precision_scores)
                
                # Score composite: 60% precision + 40% f1 (trading = precision plus importante)
                combined_scores = 0.6 * precision_scores + 0.4 * f1_scores
                mean_score = np.mean(combined_scores)
                std_score = np.std(combined_scores)
                
                # Mettre à jour l'état
                self.current_trial = trial.number + 1
                
                # Logger le progrès
                if trial.number % 10 == 0:
                    avg_f1 = np.mean(f1_scores)
                    avg_prec = np.mean(precision_scores)
                    logger.info(
                        f"Trial {trial.number}: Score={mean_score:.4f} (F1={avg_f1:.3f}, Prec={avg_prec:.3f}) | "
                        f"depth={max_depth}, lr={learning_rate:.4f}, "
                        f"n_est={n_estimators}"
                    )
                
                # Pruning early si le score est trop bas
                trial.report(mean_score, step=0)
                if trial.should_prune():
                    raise optuna.TrialPruned()
                
                return mean_score
                
            except Exception as e:
                logger.warning(f"Trial {trial.number} échoué: {e}")
                return 0.0
        
        return objective
    
    def optimize(
        self, 
        X: np.ndarray, 
        y: np.ndarray,
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Lance l'optimisation Optuna
        
        Args:
            X: Features (déjà préprocessées)
            y: Labels
            callback: Fonction appelée à chaque trial (pour le frontend)
            
        Returns:
            Dict avec les meilleurs paramètres et métriques
        """
        self.is_running = True
        self.start_time = time.time()
        self.current_trial = 0
        
        logger.info(f"🚀 Démarrage optimisation Optuna GradientBoosting")
        logger.info(f"   - Trials: {self.n_trials}")
        logger.info(f"   - Timeout: {self.timeout_seconds // 60} minutes")
        logger.info(f"   - CV Folds: {self.cv_folds}")
        logger.info(f"   - Dataset: {X.shape[0]} samples, {X.shape[1]} features")
        
        try:
            # Créer l'étude Optuna
            sampler = TPESampler(seed=self.random_state)
            pruner = MedianPruner(n_startup_trials=10, n_warmup_steps=0)
            
            self.study = optuna.create_study(
                direction='maximize',
                sampler=sampler,
                pruner=pruner,
                study_name='gb_hyperopt'
            )
            
            # Callback pour tracker le progrès
            def trial_callback(study, trial):
                self.optimization_history.append({
                    'trial': trial.number,
                    'value': trial.value if trial.value else 0,
                    'params': trial.params,
                    'state': str(trial.state)
                })
                if callback:
                    callback(trial.number, self.n_trials, trial.value)
            
            # Lancer l'optimisation
            self.study.optimize(
                self._create_objective(X, y),
                n_trials=self.n_trials,
                timeout=self.timeout_seconds,
                callbacks=[trial_callback],
                show_progress_bar=False,
                n_jobs=1  # Séquentiel car GradientBoosting utilise déjà le parallélisme
            )
            
            # Extraire les meilleurs paramètres
            self.best_params = self.study.best_params
            self.best_score = self.study.best_value
            
            # Calculer les stats
            elapsed_time = time.time() - self.start_time
            completed_trials = len([t for t in self.study.trials if t.state == optuna.trial.TrialState.COMPLETE])
            pruned_trials = len([t for t in self.study.trials if t.state == optuna.trial.TrialState.PRUNED])
            
            result = {
                'success': True,
                'best_params': self.best_params,
                'best_score': self.best_score,
                'n_trials_completed': completed_trials,
                'n_trials_pruned': pruned_trials,
                'elapsed_seconds': elapsed_time,
                'optimization_history': self.optimization_history[-20:]  # Derniers 20 trials
            }
            
            logger.info(f"✅ Optimisation terminée en {elapsed_time:.1f}s")
            logger.info(f"   - Best F1 Score: {self.best_score:.4f}")
            logger.info(f"   - Trials: {completed_trials} completed, {pruned_trials} pruned")
            logger.info(f"   - Best params: {self.best_params}")
            
            # Sauvegarder les résultats
            self._save_optimization_results(result)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur optimisation Optuna: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'best_params': None,
                'best_score': 0.0
            }
        finally:
            self.is_running = False
    
    def _save_optimization_results(self, result: Dict[str, Any]):
        """Sauvegarde les résultats de l'optimisation"""
        try:
            output_file = OPTIMIZATION_DIR / "gb_optuna_results.json"
            
            save_data = {
                'timestamp': datetime.now().isoformat(),
                'best_params': result['best_params'],
                'best_score': result['best_score'],
                'n_trials': result.get('n_trials_completed', 0),
                'elapsed_seconds': result.get('elapsed_seconds', 0)
            }
            
            with open(output_file, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            logger.info(f"✅ Résultats sauvegardés: {output_file}")
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde résultats: {e}")
    
    def train_with_best_params(
        self, 
        X_train: np.ndarray, 
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray
    ) -> Tuple[Pipeline, Dict[str, float]]:
        """
        Entraîne un modèle avec les meilleurs paramètres trouvés
        
        Returns:
            Tuple (pipeline entraîné, métriques)
        """
        if not self.best_params:
            raise ValueError("Aucun paramètre optimal trouvé. Lancer optimize() d'abord.")
        
        logger.info(f"🎯 Entraînement avec les meilleurs paramètres...")
        
        # Créer le pipeline final
        pipeline = Pipeline([
            ('scaler', RobustScaler()),
            ('classifier', GradientBoostingClassifier(
                **self.best_params,
                random_state=self.random_state
            ))
        ])
        
        # Entraîner
        pipeline.fit(X_train, y_train)
        
        # Évaluer
        y_pred_train = pipeline.predict(X_train)
        y_pred_test = pipeline.predict(X_test)
        
        metrics = {
            'train_accuracy': accuracy_score(y_train, y_pred_train),
            'test_accuracy': accuracy_score(y_test, y_pred_test),
            'train_f1': f1_score(y_train, y_pred_train, average='macro'),
            'test_f1': f1_score(y_test, y_pred_test, average='macro'),
            'test_precision': precision_score(y_test, y_pred_test, average='macro'),
            'test_recall': recall_score(y_test, y_pred_test, average='macro'),
            'overfitting_gap': accuracy_score(y_train, y_pred_train) - accuracy_score(y_test, y_pred_test)
        }
        
        logger.info(f"✅ Métriques finales:")
        logger.info(f"   - Train Accuracy: {metrics['train_accuracy']*100:.1f}%")
        logger.info(f"   - Test Accuracy: {metrics['test_accuracy']*100:.1f}%")
        logger.info(f"   - Test F1: {metrics['test_f1']:.3f}")
        logger.info(f"   - Overfitting Gap: {metrics['overfitting_gap']*100:.1f}%")
        
        return pipeline, metrics
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne l'état actuel de l'optimisation"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        return {
            'is_running': self.is_running,
            'current_trial': self.current_trial,
            'total_trials': self.n_trials,
            'progress_pct': (self.current_trial / self.n_trials * 100) if self.n_trials > 0 else 0,
            'elapsed_seconds': elapsed,
            'best_score_so_far': self.best_score if self.best_score else 0,
            'best_params_so_far': self.best_params
        }


def load_last_optimization_results() -> Optional[Dict[str, Any]]:
    """Charge les derniers résultats d'optimisation"""
    try:
        results_file = OPTIMIZATION_DIR / "gb_optuna_results.json"
        if results_file.exists():
            with open(results_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Erreur chargement résultats: {e}")
    return None


# Instance globale pour le suivi
_optimizer_instance: Optional[GradientBoostingOptunaOptimizer] = None


def get_optimizer_instance() -> GradientBoostingOptunaOptimizer:
    """Récupère ou crée l'instance de l'optimiseur"""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = GradientBoostingOptunaOptimizer()
    return _optimizer_instance

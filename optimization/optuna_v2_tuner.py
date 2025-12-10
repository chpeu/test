"""
Optuna Hyperparameter Tuning V2 - Compatible avec XGBoost V2 Enhanced

Différences vs V1 (ml/hyperparameter_tuning.py):
✅ Temporal split au lieu de StratifiedKFold (évite data leakage)
✅ Filtrage marginal trades
✅ Features avancées (contexte + historique)
✅ Walk-forward validation option
✅ Compatible ensemble XGBoost + LightGBM
"""
import logging
import time
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
import numpy as np
import pandas as pd

import optuna
from optuna.pruners import HyperbandPruner
from optuna.samplers import TPESampler
from optuna.trial import Trial
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, precision_score, recall_score
import xgboost as xgb

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering_advanced import calculate_all_advanced_features
from optimization.data.preprocessor import FeaturePreprocessor, handle_class_imbalance
from optimization.utils.temporal_split import temporal_train_test_split

logger = logging.getLogger(__name__)


class OptunaV2Tuner:
    """
    Hyperparameter Tuner V2 avec temporal split

    Compatible avec toutes les améliorations V2 Enhanced
    """

    def __init__(
        self,
        study_name: str = "xgboost_v2_enhanced_optimization",
        storage: Optional[str] = None,
        n_trials: int = 100,
        timeout: Optional[int] = None,
        metric: str = "trading_composite",
        pruning: bool = True
    ):
        """
        Args:
            study_name: Nom de l'étude Optuna
            storage: URL de stockage (postgresql://... ou sqlite://...)
            n_trials: Nombre d'essais max
            timeout: Timeout en secondes
            metric: Métrique à optimiser
            pruning: Activer pruning automatique
        """
        self.study_name = study_name
        self.n_trials = n_trials
        self.timeout = timeout
        self.metric = metric
        self.pruning = pruning

        # Storage par défaut: SQLite
        if storage is None:
            storage = "sqlite:///optuna_v2_studies.db"
            logger.info("📊 Optuna V2: Utilisation de SQLite pour stockage")

        self.storage = storage

        # Sampler et Pruner
        sampler = TPESampler(
            n_startup_trials=10,
            multivariate=True,
            seed=42
        )

        pruner = HyperbandPruner() if pruning else optuna.pruners.NopPruner()

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
            f"🎯 OptunaV2Tuner initialisé:\n"
            f"  - Study: {study_name}\n"
            f"  - Storage: {storage}\n"
            f"  - Trials: {n_trials}\n"
            f"  - Metric: {metric}\n"
            f"  - Pruning: {pruning}"
        )

    def _suggest_hyperparameters(self, trial: Trial) -> Dict[str, Any]:
        """
        Espace de recherche hyperparamètres (optimisé pour éviter overfitting)
        
        🔥 V2.1: Espace élargi + fix scale_pos_weight
        """
        params = {
            # Structure (limité pour éviter overfitting)
            'max_depth': trial.suggest_int('max_depth', 2, 7),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 15),

            # Régularisation (plus forte pour éviter overfitting)
            'reg_alpha': trial.suggest_float('reg_alpha', 0.1, 15.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 0.5, 15.0, log=True),

            # Échantillonnage
            'subsample': trial.suggest_float('subsample', 0.5, 0.95),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 0.95),
            'colsample_bylevel': trial.suggest_float('colsample_bylevel', 0.5, 0.95),

            # Learning
            'learning_rate': trial.suggest_float('learning_rate', 0.005, 0.15, log=True),
            'n_estimators': trial.suggest_int('n_estimators', 100, 1000, step=50),

            # Autres
            'gamma': trial.suggest_float('gamma', 0.0, 10.0),
            
            # 🔥 FIX: Multiplicateur au lieu de valeur absolue (évite écrasement)
            'scale_pos_weight_mult': trial.suggest_float('scale_pos_weight_mult', 0.7, 1.5),
            
            # 🔥 NEW: Paramètres supplémentaires
            'max_bin': trial.suggest_int('max_bin', 128, 512, step=64),
            'grow_policy': trial.suggest_categorical('grow_policy', ['depthwise', 'lossguide']),
        }

        return params

    def _calculate_metric(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray,
        pnl_values: Optional[np.ndarray] = None
    ) -> float:
        """
        Calculer métrique selon configuration
        
        🔥 V2.1: Ajout métriques trading (profit_factor, precision)
        
        trading_composite: 0.35*F1 + 0.25*Accuracy + 0.20*ROC-AUC + 0.10*Recall + 0.10*Precision
        trading_profit: Optimise pour profit réel si pnl_values fourni
        """
        f1 = f1_score(y_true, y_pred, zero_division=0)
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        
        try:
            auc = roc_auc_score(y_true, y_proba)
        except:
            auc = 0.5
        
        if self.metric == "trading_composite":
            # Score composite équilibré
            score = (
                0.35 * f1 +
                0.25 * accuracy +
                0.20 * auc +
                0.10 * recall +
                0.10 * precision
            )
            return score
        
        elif self.metric == "trading_profit" and pnl_values is not None:
            # 🔥 NEW: Optimiser pour profit réel
            predicted_wins = y_pred == 1
            if predicted_wins.sum() > 0:
                # Profit moyen des trades prédits gagnants
                avg_profit = pnl_values[predicted_wins].mean()
                # Win rate réel des prédictions
                actual_win_rate = y_true[predicted_wins].mean()
                # Score = profit * win_rate * precision
                score = max(0, avg_profit) * actual_win_rate * precision
                return score
            return 0.0
        
        elif self.metric == "f1_score":
            return f1
        
        elif self.metric == "accuracy":
            return accuracy
        
        elif self.metric == "roc_auc":
            return auc
        
        elif self.metric == "precision":
            return precision
        
        else:
            return f1

    def _objective(
        self,
        trial: Trial,
        X_train: pd.DataFrame,
        X_val: pd.DataFrame,
        X_test: pd.DataFrame,
        y_train: pd.Series,
        y_val: pd.Series,
        y_test: pd.Series,
        pnl_val: Optional[pd.Series] = None
    ) -> float:
        """
        Fonction objectif (temporal split)
        
        🔥 V2.1: Ajout pénalité overfitting + métriques avancées
        
        Entraîne sur train, valide sur val, évalue sur test
        """
        # Suggérer hyperparamètres
        params = self._suggest_hyperparameters(trial)
        
        # 🔥 FIX: Calculer scale_pos_weight de base puis appliquer multiplicateur
        class_weights = handle_class_imbalance(y_train, strategy="balanced")
        base_spw = class_weights.get(1, 1.0) / class_weights.get(0, 1.0)
        spw_mult = params.pop('scale_pos_weight_mult', 1.0)
        params['scale_pos_weight'] = base_spw * spw_mult
        
        # Extraire grow_policy et max_bin (pas supportés par tous les tree_method)
        grow_policy = params.pop('grow_policy', 'depthwise')
        max_bin = params.pop('max_bin', 256)
        
        # Entraîner modèle sur train
        model = xgb.XGBClassifier(
            **params,
            tree_method='hist',
            grow_policy=grow_policy,
            max_bin=max_bin,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss',
            early_stopping_rounds=30
        )
        
        try:
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
        except Exception as e:
            logger.warning(f"Trial {trial.number} failed: {e}")
            raise optuna.TrialPruned()
        
        # Évaluer sur train (pour détecter overfitting)
        y_train_pred = model.predict(X_train)
        y_train_proba = model.predict_proba(X_train)[:, 1]
        train_score = self._calculate_metric(y_train, y_train_pred, y_train_proba)
        
        # Évaluer sur validation
        y_val_pred = model.predict(X_val)
        y_val_proba = model.predict_proba(X_val)[:, 1]
        val_score = self._calculate_metric(
            y_val, y_val_pred, y_val_proba,
            pnl_values=pnl_val.values if pnl_val is not None else None
        )
        
        # Évaluer sur test (pour monitoring, pas pour optimisation)
        y_test_pred = model.predict(X_test)
        y_test_proba = model.predict_proba(X_test)[:, 1]
        test_score = self._calculate_metric(y_test, y_test_pred, y_test_proba)
        
        # 🔥 NEW: Calculer gap overfitting
        overfit_gap = train_score - val_score
        
        # 🔥 NEW: Pénaliser overfitting sévèrement
        if overfit_gap > 0.20:
            # Overfitting sévère: pénalité 50%
            final_score = val_score * 0.5
            logger.warning(f"[Trial {trial.number}] ⚠️ OVERFITTING: gap={overfit_gap:.3f} → score pénalisé")
        elif overfit_gap > 0.15:
            # Overfitting modéré: pénalité 25%
            final_score = val_score * 0.75
            logger.info(f"[Trial {trial.number}] ⚠️ Overfitting modéré: gap={overfit_gap:.3f}")
        elif overfit_gap > 0.10:
            # Overfitting léger: pénalité 10%
            final_score = val_score * 0.90
        else:
            # Bon généralisation
            final_score = val_score
        
        # Log détaillé
        logger.info(
            f"[Trial {trial.number}] {self.metric}: "
            f"train={train_score:.4f}, val={val_score:.4f}, test={test_score:.4f}, "
            f"gap={overfit_gap:.3f}, final={final_score:.4f} | "
            f"depth={params['max_depth']}, lr={params['learning_rate']:.4f}, "
            f"reg_α={params['reg_alpha']:.2f}, reg_λ={params['reg_lambda']:.2f}"
        )
        
        # Stocker métriques supplémentaires
        trial.set_user_attr('train_score', train_score)
        trial.set_user_attr('val_score', val_score)
        trial.set_user_attr('test_score', test_score)
        trial.set_user_attr('overfit_gap', overfit_gap)
        
        return final_score

    def optimize(
        self,
        timeframe_days: int = 120,
        min_trades: int = 100,
        filter_marginal_trades: bool = True,
        marginal_threshold: float = 0.15,
        max_features: int = 40,
        test_size: float = 0.2,
        validation_size: float = 0.1,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Lancer optimisation complète avec temporal split

        Returns:
            Dict contenant best_params, best_score, etc.
        """
        logger.info("=" * 90)
        logger.info("🚀 OPTUNA V2 ENHANCED - Optimisation Hyperparamètres")
        logger.info("=" * 90)

        start_time = time.time()

        # 1. Charger données
        logger.info(f"\n📥 Chargement données...")

        base_df = load_features_from_postgres(
            timeframe_days=timeframe_days,
            min_trades=min_trades
        )

        logger.info(f"✅ {len(base_df)} trades chargés")

        # 2. Feature engineering avancé
        logger.info(f"\n🔧 Feature engineering avancé...")

        df = calculate_all_advanced_features(base_df)

        # 3. Filtrer marginal trades
        if filter_marginal_trades and 'target_pnl' in df.columns:
            logger.info(f"\n🔍 Filtrage trades marginaux...")

            initial_count = len(df)
            df = df[abs(df['target_pnl']) >= marginal_threshold].copy()

            logger.info(f"✂️ {initial_count - len(df)} trades exclus")

        # 4. Temporal split
        logger.info(f"\n📅 Temporal split...")

        train_df, val_df, test_df = temporal_train_test_split(
            df,
            target_col='target_win',
            test_size=test_size,
            validation_size=validation_size
        )

        # 5. Preprocessing
        logger.info(f"\n🔧 Preprocessing...")

        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
        feature_cols = [col for col in train_df.columns if col not in exclude_cols]

        X_train = train_df[feature_cols].copy()
        y_train = train_df['target_win'].copy()

        X_val = val_df[feature_cols].copy()
        y_val = val_df['target_win'].copy()

        X_test = test_df[feature_cols].copy()
        y_test = test_df['target_win'].copy()

        # Feature selection (top-K)
        from sklearn.feature_selection import mutual_info_classif

        logger.info(f"\n🔍 Feature selection (top {max_features})...")

        mi_scores = mutual_info_classif(
            X_train.fillna(X_train.median()),
            y_train,
            random_state=42
        )

        mi_df = pd.DataFrame({
            'feature': feature_cols,
            'mi_score': mi_scores
        }).sort_values('mi_score', ascending=False)

        selected_features = mi_df.head(max_features)['feature'].tolist()

        X_train = X_train[selected_features]
        X_val = X_val[selected_features]
        X_test = X_test[selected_features]

        # Preprocessing (scaling)
        preprocessor = FeaturePreprocessor(scaler_type='robust')

        X_train_scaled, _ = preprocessor.fit_transform(
            pd.concat([X_train, y_train.rename('target_win')], axis=1)
        )
        X_val_scaled = preprocessor.transform(X_val)
        X_test_scaled = preprocessor.transform(X_test)

        logger.info(f"✅ Données prêtes: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")

        # 6. Optimisation Optuna
        logger.info(f"\n🎯 Optimisation Optuna ({self.n_trials} trials)...")

        def callback(study, trial):
            if trial.state == optuna.trial.TrialState.COMPLETE:
                logger.info(f"✅ Trial {trial.number}/{self.n_trials} | Best: {study.best_value:.4f}")

        self.study.optimize(
            lambda trial: self._objective(
                trial,
                X_train_scaled, X_val_scaled, X_test_scaled,
                y_train, y_val, y_test
            ),
            n_trials=self.n_trials,
            timeout=self.timeout,
            callbacks=[callback] if show_progress else None,
            show_progress_bar=show_progress,
            n_jobs=1  # Pas de parallélisme (data leakage entre trials)
        )

        elapsed = time.time() - start_time

        # Résultats
        best_params = self.study.best_params
        best_score = self.study.best_value

        logger.info(f"\n{'='*90}")
        logger.info(f"🏆 OPTIMISATION TERMINÉE EN {elapsed/60:.1f} minutes")
        logger.info(f"{'='*90}")
        logger.info(f"\n🏆 MEILLEURS HYPERPARAMÈTRES:")
        for param, value in best_params.items():
            logger.info(f"  - {param}: {value}")
        logger.info(f"\n📈 Best {self.metric}: {best_score:.4f}")
        logger.info(f"{'='*90}\n")

        return {
            'best_params': best_params,
            'best_score': best_score,
            'best_trial': self.study.best_trial,
            'study': self.study,
            'elapsed_time': elapsed,
            'n_trials': len(self.study.trials),
            'selected_features': selected_features
        }

    def save_best_params(
        self,
        filepath: str = "config_overrides.json",
        prefix: str = "ml_"
    ):
        """
        Sauvegarder meilleurs paramètres dans config
        """
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    config = json.load(f)
            else:
                config = {}

            # Ajouter meilleurs params
            best_params = self.study.best_params

            # Créer section ml_params_to_apply
            config['ml_params_to_apply'] = {
                **best_params,
                '_source': 'optuna_v2_enhanced',
                '_metric': self.metric,
                '_study': self.study_name,
                '_optimized_at': datetime.now().isoformat()
            }

            # Aussi sauvegarder en direct (ml_xxx)
            for param, value in best_params.items():
                config_key = f"{prefix}{param}"
                config[config_key] = value

            # Sauvegarder
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=2)

            logger.info(f"💾 Meilleurs paramètres sauvegardés dans {filepath}")

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde: {e}")


def run_optuna_v2_optimization(
    n_trials: int = 100,
    timeout: Optional[int] = None,
    metric: str = "trading_composite",
    save_config: bool = True,
    timeframe_days: int = 120,
    min_trades: int = 100,
    max_features: int = 40
) -> Dict[str, Any]:
    """
    Helper pour lancer optimisation V2 Enhanced

    Usage:
        results = run_optuna_v2_optimization(n_trials=50, max_features=40)
    """
    tuner = OptunaV2Tuner(
        n_trials=n_trials,
        timeout=timeout,
        metric=metric
    )

    results = tuner.optimize(
        timeframe_days=timeframe_days,
        min_trades=min_trades,
        max_features=max_features
    )

    if save_config:
        tuner.save_best_params()

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Exemple: optimisation 50 trials
    results = run_optuna_v2_optimization(
        n_trials=50,
        max_features=40,
        save_config=True
    )

    print(f"\n✅ Optimisation terminée !")
    print(f"✅ Best score: {results['best_score']:.4f}")
    print(f"✅ Meilleurs params sauvegardés dans config_overrides.json")

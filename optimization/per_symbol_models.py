#!/usr/bin/env python3
"""
🎯 MODÈLES ML INDIVIDUALISÉS PAR PAIRE
=======================================
Système permettant d'avoir un modèle GradientBoosting optimisé
pour chaque paire du top 5-10, avec:
- Hyperparamètres spécifiques
- Seuil de confiance adapté
- Métriques indépendantes

Les paires peu tradées utilisent le modèle global par défaut.
"""

import os
import json
import joblib
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field

from sklearn.model_selection import cross_val_score, StratifiedKFold, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

logger = logging.getLogger(__name__)

# Chemins
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_PATH = PROJECT_ROOT / "optimization" / "saved_models" / "per_symbol"
MODELS_PATH.mkdir(parents=True, exist_ok=True)

# Configuration
RANDOM_SEED = 42
MIN_TRADES_FOR_INDIVIDUAL_MODEL = 80  # Minimum trades pour créer un modèle dédié (augmenté pour robustesse)
TOP_SYMBOLS_COUNT = 10  # Maximum de modèles individuels
MIN_ACCURACY_IMPROVEMENT = 0.02  # Minimum +2% accuracy vs global pour utiliser modèle individuel


@dataclass
class SymbolModelConfig:
    """Configuration d'un modèle par symbole"""
    symbol: str
    enabled: bool = True
    min_confidence: float = 0.55
    hyperparameters: Dict = field(default_factory=lambda: {
        'n_estimators': 150,
        'max_depth': 3,
        'learning_rate': 0.03,
        'min_samples_split': 50,
        'min_samples_leaf': 30,
        'subsample': 0.7,
        'max_features': 0.5,
        'random_state': RANDOM_SEED
    })


@dataclass
class SymbolModelMetrics:
    """Métriques d'un modèle par symbole"""
    symbol: str
    n_trades: int = 0
    train_accuracy: float = 0.0
    test_accuracy: float = 0.0
    cv_accuracy: float = 0.0
    cv_f1: float = 0.0
    cv_roc_auc: float = 0.0
    optimal_threshold: float = 0.55
    trained_at: str = ""
    

class PerSymbolModelManager:
    """
    Gestionnaire des modèles individualisés par paire
    
    Usage:
        manager = PerSymbolModelManager()
        
        # Entraîner les modèles pour les top symboles
        manager.train_top_symbols()
        
        # Prédiction (utilise modèle spécifique si disponible, sinon global)
        should_trade, confidence = manager.predict("BTC/USDT", features)
    """
    
    def __init__(self):
        self.models: Dict[str, Pipeline] = {}
        self.configs: Dict[str, SymbolModelConfig] = {}
        self.metrics: Dict[str, SymbolModelMetrics] = {}
        self.global_model: Optional[Pipeline] = None
        self.global_threshold: float = 0.55
        self.feature_names: List[str] = []
        
        # Charger modèles existants
        self._load_existing_models()
    
    def _load_existing_models(self):
        """Charge les modèles existants depuis le disque"""
        # Charger modèle global
        global_path = PROJECT_ROOT / "optimization" / "saved_models" / "gradient_boosting_anti_overfit.pkl"
        if global_path.exists():
            try:
                self.global_model = joblib.load(global_path)
                logger.info(f"✅ Modèle global chargé: {global_path}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur chargement modèle global: {e}")
        
        # Charger metadata global pour features
        global_meta_path = global_path.with_suffix('.json').name.replace('.pkl', '_metadata.json')
        meta_path = PROJECT_ROOT / "optimization" / "saved_models" / "gradient_boosting_anti_overfit_metadata.json"
        if meta_path.exists():
            try:
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                self.feature_names = meta.get('selected_features', [])
                self.global_threshold = meta.get('optimal_threshold', 0.55)
            except:
                pass
        
        # Charger modèles par symbole
        if MODELS_PATH.exists():
            for model_file in MODELS_PATH.glob("*.pkl"):
                symbol = model_file.stem.replace("_model", "").replace("_", "/")
                try:
                    self.models[symbol] = joblib.load(model_file)
                    
                    # Charger config/metrics
                    config_file = model_file.with_suffix('.json')
                    if config_file.exists():
                        with open(config_file, 'r') as f:
                            data = json.load(f)
                        self.configs[symbol] = SymbolModelConfig(
                            symbol=symbol,
                            min_confidence=data.get('optimal_threshold', 0.55),
                            hyperparameters=data.get('hyperparameters', {})
                        )
                        self.metrics[symbol] = SymbolModelMetrics(
                            symbol=symbol,
                            n_trades=data.get('n_trades', 0),
                            test_accuracy=data.get('test_accuracy', 0),
                            cv_accuracy=data.get('cv_accuracy', 0),
                            cv_f1=data.get('cv_f1', 0),
                            optimal_threshold=data.get('optimal_threshold', 0.55),
                            trained_at=data.get('trained_at', '')
                        )
                    
                    logger.info(f"✅ Modèle {symbol} chargé")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur chargement modèle {symbol}: {e}")
    
    def get_top_symbols(self, min_trades: int = MIN_TRADES_FOR_INDIVIDUAL_MODEL) -> List[Tuple[str, int]]:
        """
        Récupère les symboles avec le plus de trades
        
        Returns:
            Liste de tuples (symbol, count) triée par count décroissant
        """
        try:
            from optimization.data.feature_loader import load_features_from_postgres
            
            df = load_features_from_postgres(timeframe_days=180, min_trades=1)
            
            if 'symbol' not in df.columns:
                logger.warning("Colonne 'symbol' non trouvée dans les données")
                return []
            
            # Compter trades par symbole
            symbol_counts = df['symbol'].value_counts()
            
            # Filtrer par minimum et limiter au top N
            top_symbols = [
                (symbol, count) 
                for symbol, count in symbol_counts.items() 
                if count >= min_trades
            ][:TOP_SYMBOLS_COUNT]
            
            logger.info(f"📊 Top {len(top_symbols)} symboles avec ≥{min_trades} trades:")
            for symbol, count in top_symbols:
                logger.info(f"   {symbol}: {count} trades")
            
            return top_symbols
            
        except Exception as e:
            logger.error(f"❌ Erreur get_top_symbols: {e}")
            return []
    
    def train_symbol_model(
        self, 
        symbol: str,
        optimize_hyperparams: bool = False,
        n_trials: int = 30
    ) -> Optional[SymbolModelMetrics]:
        """
        Entraîne un modèle pour un symbole spécifique
        
        Args:
            symbol: Symbole de la paire (ex: "BTC/USDT")
            optimize_hyperparams: Si True, optimise les hyperparamètres avec Optuna
            n_trials: Nombre de trials Optuna si optimisation
            
        Returns:
            SymbolModelMetrics ou None si échec
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 ENTRAÎNEMENT MODÈLE: {symbol}")
        logger.info(f"{'='*60}")
        
        try:
            from optimization.data.feature_loader import load_features_from_postgres
            from optimization.data.feature_engineering import calculate_derived_features
            
            # Charger données pour ce symbole uniquement
            df = load_features_from_postgres(timeframe_days=180, min_trades=1)
            df = df[df['symbol'] == symbol].copy()
            
            if len(df) < MIN_TRADES_FOR_INDIVIDUAL_MODEL:
                logger.warning(f"⚠️ Pas assez de trades pour {symbol}: {len(df)} < {MIN_TRADES_FOR_INDIVIDUAL_MODEL}")
                return None
            
            logger.info(f"   Trades chargés: {len(df)}")
            
            # Feature engineering
            df = calculate_derived_features(df)
            
            # Utiliser les mêmes features que le modèle global
            if not self.feature_names:
                self.feature_names = [
                    "di_plus_1m", "bb_distance_to_upper_5m", "ema_diff_pct_1m", "rsi_1m",
                    "di_plus_5m", "ema_diff_pct_5m", "bb_distance_to_upper_1m", "bb_distance_to_lower_1m",
                    "atr_pct_1m", "rsi_5m", "bb_width_5m", "bb_distance_to_lower_5m",
                    "macd_momentum_5m", "trend_strength_1m", "rsi_prev_5m", "volatility_momentum_product",
                    "di_gap_1m", "macd_hist_prev_1m", "rsi_prev_1m", "macd_hist_1m",
                    "trend_strength_5m", "momentum_divergence", "bb_width_1m", "di_minus_5m",
                    "momentum_5m", "momentum_1m", "volume_divergence", "adx_5m"
                ]
            
            available_features = [f for f in self.feature_names if f in df.columns]
            
            X = df[available_features].copy()
            y = df['target_win'].astype(int).copy()
            
            # Nettoyer
            X = X.replace([np.inf, -np.inf], np.nan)
            
            # Split temporel 80/20
            split_idx = int(len(df) * 0.8)
            X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
            
            logger.info(f"   Train: {len(X_train)} | Test: {len(X_test)}")
            logger.info(f"   Win rate global: {y.mean()*100:.1f}%")
            
            # Hyperparamètres (fixes ou optimisés)
            if optimize_hyperparams:
                params = self._optimize_hyperparams(X_train, y_train, n_trials)
            else:
                # Utiliser paramètres par défaut ou existants
                if symbol in self.configs:
                    params = self.configs[symbol].hyperparameters
                else:
                    params = {
                        'n_estimators': 150,
                        'max_depth': 3,
                        'learning_rate': 0.03,
                        'min_samples_split': 50,
                        'min_samples_leaf': 30,
                        'subsample': 0.7,
                        'max_features': 0.5,
                        'random_state': RANDOM_SEED
                    }
            
            # Créer pipeline
            imputer = SimpleImputer(strategy='median')
            scaler = StandardScaler()
            model = GradientBoostingClassifier(**params)
            
            pipeline = Pipeline([
                ('imputer', imputer),
                ('scaler', scaler),
                ('classifier', model)
            ])
            
            # Entraîner
            pipeline.fit(X_train, y_train)
            
            # Évaluer
            train_pred = pipeline.predict(X_train)
            test_pred = pipeline.predict(X_test)
            test_proba = pipeline.predict_proba(X_test)[:, 1]
            
            train_acc = accuracy_score(y_train, train_pred)
            test_acc = accuracy_score(y_test, test_pred)
            test_f1 = f1_score(y_test, test_pred)
            
            # Cross-validation
            cv = StratifiedKFold(n_splits=min(5, len(X_train) // 10), shuffle=True, random_state=RANDOM_SEED)
            cv_scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring='accuracy')
            cv_f1_scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring='f1')
            
            # Trouver seuil optimal
            optimal_threshold = self._find_optimal_threshold(y_test, test_proba)
            
            # Comparer avec modèle global
            global_acc = None
            improvement = 0.0
            use_individual = True
            
            if self.global_model is not None:
                try:
                    global_pred = self.global_model.predict(X_test)
                    global_acc = accuracy_score(y_test, global_pred)
                    improvement = test_acc - global_acc
                    
                    # Vérifier si amélioration suffisante
                    if improvement < MIN_ACCURACY_IMPROVEMENT:
                        use_individual = False
                        logger.warning(
                            f"   ⚠️ Modèle individuel pas assez meilleur que global "
                            f"(+{improvement:.1%} < +{MIN_ACCURACY_IMPROVEMENT:.0%} requis)"
                        )
                except Exception as e:
                    logger.debug(f"   Impossible de comparer avec modèle global: {e}")
            
            logger.info(f"\n   📊 RÉSULTATS {symbol}:")
            logger.info(f"   Train Accuracy: {train_acc:.1%}")
            logger.info(f"   Test Accuracy:  {test_acc:.1%}")
            if global_acc:
                logger.info(f"   Global Accuracy: {global_acc:.1%} (sur même test)")
                logger.info(f"   Amélioration:   {'+' if improvement > 0 else ''}{improvement:.1%}")
            logger.info(f"   CV Accuracy:    {cv_scores.mean():.1%} ± {cv_scores.std():.1%}")
            logger.info(f"   Test F1:        {test_f1:.3f}")
            logger.info(f"   Seuil optimal:  {optimal_threshold:.0%}")
            logger.info(f"   Utiliser:       {'✅ OUI' if use_individual else '❌ NON (global meilleur)'}")
            
            # Sauvegarder seulement si meilleur que global
            if not use_individual:
                logger.info(f"   → Modèle individuel NON sauvegardé, utilisation du global")
                return None
            
            # Sauvegarder
            self._save_symbol_model(symbol, pipeline, params, {
                'n_trades': len(df),
                'train_accuracy': float(train_acc),
                'test_accuracy': float(test_acc),
                'global_accuracy': float(global_acc) if global_acc else None,
                'improvement_vs_global': float(improvement),
                'cv_accuracy': float(cv_scores.mean()),
                'cv_f1': float(cv_f1_scores.mean()),
                'optimal_threshold': float(optimal_threshold),
                'trained_at': datetime.now().isoformat()
            })
            
            # Mettre en cache
            self.models[symbol] = pipeline
            self.configs[symbol] = SymbolModelConfig(
                symbol=symbol,
                min_confidence=optimal_threshold,
                hyperparameters=params
            )
            
            metrics = SymbolModelMetrics(
                symbol=symbol,
                n_trades=len(df),
                train_accuracy=train_acc,
                test_accuracy=test_acc,
                cv_accuracy=cv_scores.mean(),
                cv_f1=cv_f1_scores.mean(),
                optimal_threshold=optimal_threshold,
                trained_at=datetime.now().isoformat()
            )
            self.metrics[symbol] = metrics
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Erreur entraînement {symbol}: {e}", exc_info=True)
            return None
    
    def _optimize_hyperparams(self, X_train: pd.DataFrame, y_train: pd.Series, n_trials: int) -> Dict:
        """Optimise les hyperparamètres avec Optuna"""
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)
            
            def objective(trial):
                params = {
                    'n_estimators': trial.suggest_int('n_estimators', 50, 200),
                    'max_depth': trial.suggest_int('max_depth', 2, 5),
                    'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.15),
                    'min_samples_split': trial.suggest_int('min_samples_split', 30, 100),
                    'min_samples_leaf': trial.suggest_int('min_samples_leaf', 20, 60),
                    'subsample': trial.suggest_float('subsample', 0.5, 0.9),
                    'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', 0.5]),
                    'random_state': RANDOM_SEED
                }
                
                pipeline = Pipeline([
                    ('imputer', SimpleImputer(strategy='median')),
                    ('scaler', StandardScaler()),
                    ('classifier', GradientBoostingClassifier(**params))
                ])
                
                cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_SEED)
                scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring='f1')
                return scores.mean()
            
            study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
            study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
            
            best_params = study.best_params
            best_params['random_state'] = RANDOM_SEED
            
            logger.info(f"   Meilleurs hyperparamètres trouvés (F1={study.best_value:.3f})")
            return best_params
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur optimisation, utilisation params par défaut: {e}")
            return {
                'n_estimators': 150,
                'max_depth': 3,
                'learning_rate': 0.03,
                'min_samples_split': 50,
                'min_samples_leaf': 30,
                'subsample': 0.7,
                'max_features': 0.5,
                'random_state': RANDOM_SEED
            }
    
    def _find_optimal_threshold(self, y_true: pd.Series, y_proba: np.ndarray) -> float:
        """Trouve le seuil de confiance optimal"""
        best_threshold = 0.55
        best_score = 0
        
        for threshold in np.arange(0.45, 0.75, 0.05):
            y_pred = (y_proba >= threshold).astype(int)
            
            # Score combiné: F1 + bonus si précision > 60%
            f1 = f1_score(y_true, y_pred)
            precision = precision_score(y_true, y_pred, zero_division=0)
            
            score = f1 + (0.1 if precision > 0.60 else 0)
            
            if score > best_score:
                best_score = score
                best_threshold = threshold
        
        return best_threshold
    
    def _save_symbol_model(self, symbol: str, pipeline: Pipeline, params: Dict, metrics: Dict):
        """Sauvegarde le modèle et ses métadonnées"""
        # Nom de fichier sécurisé
        safe_name = symbol.replace("/", "_").replace(":", "_")
        
        model_path = MODELS_PATH / f"{safe_name}_model.pkl"
        config_path = MODELS_PATH / f"{safe_name}_model.json"
        
        # Sauvegarder modèle
        joblib.dump(pipeline, model_path)
        
        # Sauvegarder config/metrics
        with open(config_path, 'w') as f:
            json.dump({
                'symbol': symbol,
                'hyperparameters': params,
                **metrics
            }, f, indent=2)
        
        logger.info(f"   ✅ Modèle sauvegardé: {model_path}")
    
    def train_top_symbols(self, optimize: bool = False) -> Dict[str, SymbolModelMetrics]:
        """
        Entraîne des modèles pour tous les top symboles
        
        Args:
            optimize: Si True, optimise les hyperparamètres pour chaque symbole
            
        Returns:
            Dict des métriques par symbole
        """
        top_symbols = self.get_top_symbols()
        results = {}
        
        for symbol, count in top_symbols:
            metrics = self.train_symbol_model(symbol, optimize_hyperparams=optimize)
            if metrics:
                results[symbol] = metrics
        
        # Résumé
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 RÉSUMÉ ENTRAÎNEMENT {len(results)} MODÈLES")
        logger.info(f"{'='*60}")
        
        for symbol, m in results.items():
            logger.info(f"   {symbol}: Acc={m.test_accuracy:.1%}, F1={m.cv_f1:.3f}, Seuil={m.optimal_threshold:.0%}")
        
        return results
    
    def predict(self, symbol: str, features: Dict) -> Tuple[bool, float]:
        """
        Prédit si un trade doit être pris
        
        Args:
            symbol: Symbole de la paire
            features: Dict des features
            
        Returns:
            Tuple (should_trade, confidence)
        """
        # Utiliser modèle spécifique si disponible
        if symbol in self.models and symbol in self.configs:
            model = self.models[symbol]
            threshold = self.configs[symbol].min_confidence
            model_type = "INDIVIDUEL"
        elif self.global_model is not None:
            model = self.global_model
            threshold = self.global_threshold
            model_type = "GLOBAL"
        else:
            logger.warning(f"⚠️ Aucun modèle disponible pour {symbol}")
            return True, 0.5  # Autoriser par défaut
        
        try:
            # Préparer features
            X = pd.DataFrame([features])
            
            # S'assurer que les features sont dans le bon ordre
            if self.feature_names:
                missing = set(self.feature_names) - set(X.columns)
                for col in missing:
                    X[col] = 0
                X = X[self.feature_names]
            
            # Prédire
            proba = model.predict_proba(X)[0, 1]
            should_trade = proba >= threshold
            
            logger.info(
                f"🎯 Prédiction {symbol} ({model_type}): "
                f"P(win)={proba:.1%}, seuil={threshold:.0%} → {'✅ TRADE' if should_trade else '❌ SKIP'}"
            )
            
            return should_trade, proba
            
        except Exception as e:
            logger.error(f"❌ Erreur prédiction {symbol}: {e}")
            return True, 0.5  # Autoriser par défaut en cas d'erreur
    
    def get_model_info(self, symbol: str) -> Optional[Dict]:
        """Retourne les infos d'un modèle"""
        if symbol in self.metrics:
            m = self.metrics[symbol]
            c = self.configs.get(symbol)
            return {
                'symbol': symbol,
                'type': 'individual',
                'n_trades': m.n_trades,
                'test_accuracy': m.test_accuracy,
                'cv_f1': m.cv_f1,
                'optimal_threshold': m.optimal_threshold,
                'trained_at': m.trained_at,
                'hyperparameters': c.hyperparameters if c else {}
            }
        return None
    
    def get_all_models_info(self) -> Dict:
        """Retourne les infos de tous les modèles"""
        return {
            'global': {
                'loaded': self.global_model is not None,
                'threshold': self.global_threshold,
                'features_count': len(self.feature_names)
            },
            'individual_models': {
                symbol: self.get_model_info(symbol)
                for symbol in self.models.keys()
            },
            'total_individual': len(self.models)
        }


# Singleton
_per_symbol_manager: Optional[PerSymbolModelManager] = None


def get_per_symbol_manager() -> PerSymbolModelManager:
    """Récupère l'instance singleton"""
    global _per_symbol_manager
    if _per_symbol_manager is None:
        _per_symbol_manager = PerSymbolModelManager()
    return _per_symbol_manager

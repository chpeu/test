"""
🤖 ML OPTIMIZER - Optimisation par ML (Optuna)
Trouve paramètres optimaux via exploration intelligente

Fonctionnalités :
- Optuna (TPE Sampler)
- Walk-Forward pour éviter overfitting
- Multi-objectifs (Sharpe + Winrate)
- Persistence études
- Visualisation
"""

import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner
from backtesting.engine import BacktestEngine
from core.analytics_database import AnalyticsDatabase
from typing import Dict, Optional, List, Callable
import logging
import json
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


class MLOptimizer:
    """
    Optimiseur ML pour paramètres trading
    
    Utilise Optuna pour trouver config optimale
    """
    
    def __init__(
        self,
        backtest_engine: BacktestEngine,
        analytics_db: Optional[AnalyticsDatabase] = None,
        study_name: str = "trading_optimization",
        storage: Optional[str] = None
    ):
        """
        Initialiser ML Optimizer
        
        Args:
            backtest_engine: Instance BacktestEngine
            analytics_db: Analytics DB
            study_name: Nom étude Optuna
            storage: Storage Optuna (sqlite:///optuna.db)
        """
        self.backtest_engine = backtest_engine
        self.analytics_db = analytics_db
        self.study_name = study_name
        
        # Storage par défaut
        if storage is None:
            storage_path = Path("optimization_studies")
            storage_path.mkdir(exist_ok=True)
            storage = f"sqlite:///{storage_path / 'optuna.db'}"
        
        self.storage = storage
        
        # Créer ou charger étude
        self.study = optuna.create_study(
            study_name=study_name,
            storage=storage,
            direction='maximize',  # Maximiser objectif
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(),
            load_if_exists=True
        )
        
        logger.info(f"🤖 ML Optimizer initialisé | Étude: {study_name} | Storage: {storage}")
    
    def optimize(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        n_trials: int = 100,
        objective_func: Optional[Callable] = None,
        param_space: Optional[Dict] = None
    ) -> Dict:
        """
        Optimiser paramètres
        
        Args:
            symbols: Symboles à backtest
            start_date: Date début
            end_date: Date fin
            n_trials: Nombre trials Optuna
            objective_func: Fonction objectif custom
            param_space: Espace paramètres custom
        
        Returns:
            Dict avec meilleurs paramètres + métriques
        """
        logger.info(f"🤖 Début optimisation | Trials: {n_trials} | {start_date} → {end_date}")
        
        # Fonction objectif par défaut
        if objective_func is None:
            objective_func = self._default_objective
        
        # Espace paramètres par défaut
        if param_space is None:
            param_space = self._default_param_space()
        
        # Créer closure pour passer contexte
        def objective(trial: optuna.Trial) -> float:
            return objective_func(
                trial=trial,
                backtest_engine=self.backtest_engine,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                param_space=param_space
            )
        
        # Lancer optimisation
        self.study.optimize(
            objective,
            n_trials=n_trials,
            show_progress_bar=True,
            n_jobs=1  # Pas de parallélisation (ccxt non thread-safe)
        )
        
        # Meilleurs paramètres
        best_params = self.study.best_params
        best_value = self.study.best_value
        
        logger.info(f"✅ Optimisation terminée")
        logger.info(f"  Meilleur objectif: {best_value:.4f}")
        logger.info(f"  Paramètres: {json.dumps(best_params, indent=2)}")
        
        # Sauvegarder résultats
        results = {
            'best_params': best_params,
            'best_value': best_value,
            'n_trials': len(self.study.trials),
            'study_name': self.study_name
        }
        
        if self.analytics_db:
            self._save_optimization_results(results)
        
        return results
    
    def _default_objective(
        self,
        trial: optuna.Trial,
        backtest_engine: BacktestEngine,
        symbols: List[str],
        start_date: str,
        end_date: str,
        param_space: Dict
    ) -> float:
        """
        Fonction objectif par défaut
        
        Optimise Sharpe Ratio (avec pénalité drawdown)
        """
        # Suggérer paramètres
        config = {}
        for param_name, param_config in param_space.items():
            param_type = param_config['type']
            
            if param_type == 'float':
                config[param_name] = trial.suggest_float(
                    param_name,
                    param_config['low'],
                    param_config['high'],
                    step=param_config.get('step')
                )
            elif param_type == 'int':
                config[param_name] = trial.suggest_int(
                    param_name,
                    param_config['low'],
                    param_config['high'],
                    step=param_config.get('step', 1)
                )
            elif param_type == 'categorical':
                config[param_name] = trial.suggest_categorical(
                    param_name,
                    param_config['choices']
                )
        
        # Backtest avec config
        results = backtest_engine.run_backtest(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            config=config
        )
        
        # Objectif composite
        sharpe = results.get('sharpe_ratio', 0)
        max_dd = results.get('max_drawdown', 100)
        winrate = results.get('winrate', 0) / 100
        total_trades = results.get('total_trades', 0)
        
        # Pénalités
        if total_trades < 10:
            # Pas assez de trades (stratégie trop selective)
            return -100
        
        if max_dd > 30:
            # Drawdown trop élevé
            return -100
        
        # Score composite: Sharpe * (1 - drawdown_penalty) + winrate_bonus
        drawdown_penalty = max_dd / 100
        winrate_bonus = winrate * 0.5
        
        score = sharpe * (1 - drawdown_penalty) + winrate_bonus
        
        return score
    
    def _default_param_space(self) -> Dict:
        """
        Espace paramètres par défaut
        
        Returns:
            Dict définissant ranges pour chaque param
        """
        return {
            # TP/SL
            'tp_pct_fixed': {'type': 'float', 'low': 0.3, 'high': 1.5, 'step': 0.1},
            'sl_pct_fixed': {'type': 'float', 'low': 0.2, 'high': 1.0, 'step': 0.1},
            
            # ATR multipliers
            'tp_atr_mult': {'type': 'float', 'low': 1.0, 'high': 3.0, 'step': 0.2},
            'sl_atr_mult': {'type': 'float', 'low': 0.5, 'high': 2.0, 'step': 0.1},
            
            # Early invalidation
            'early_invalidation_threshold_pct': {'type': 'float', 'low': -0.15, 'high': -0.05, 'step': 0.01},
            
            # Spread
            'max_spread_bps': {'type': 'int', 'low': 5, 'high': 30, 'step': 5},
            
            # Orderbook imbalance
            'orderbook_imbalance_threshold': {'type': 'float', 'low': 1.2, 'high': 2.0, 'step': 0.1},
            
            # Recovery mode
            'recovery_max_consecutive_losses': {'type': 'int', 'low': 2, 'high': 5, 'step': 1},
            'recovery_pause_duration': {'type': 'int', 'low': 300, 'high': 1800, 'step': 300},
            
            # Mode TP/SL
            'tp_sl_mode': {'type': 'categorical', 'choices': ['FIXED', 'ATR']}
        }
    
    def walk_forward_optimize(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        train_period_days: int = 90,
        test_period_days: int = 30,
        n_trials_per_period: int = 50
    ) -> Dict:
        """
        Walk-Forward Optimization (évite overfitting)
        
        Pour chaque période:
        1. Optimiser sur train
        2. Tester sur test
        
        Args:
            symbols: Symboles
            start_date: Date début globale
            end_date: Date fin globale
            train_period_days: Durée train
            test_period_days: Durée test
            n_trials_per_period: Trials par période
        
        Returns:
            Dict avec résultats par période
        """
        logger.info(f"🔄 Walk-Forward Optimization: {start_date} → {end_date}")
        
        # Générer périodes
        periods = self.backtest_engine._generate_walk_forward_periods(
            start_date, end_date, train_period_days, test_period_days
        )
        
        results_list = []
        
        for i, (train_start, train_end, test_start, test_end) in enumerate(periods):
            logger.info(f"\n📊 Période {i+1}/{len(periods)}")
            logger.info(f"  Train: {train_start} → {train_end}")
            logger.info(f"  Test:  {test_start} → {test_end}")
            
            # 1. Optimiser sur train
            logger.info(f"🤖 Optimisation sur train...")
            opt_results = self.optimize(
                symbols=symbols,
                start_date=train_start,
                end_date=train_end,
                n_trials=n_trials_per_period
            )
            
            best_params = opt_results['best_params']
            
            # 2. Tester sur test avec meilleurs params
            logger.info(f"📊 Test sur période test...")
            test_results = self.backtest_engine.run_backtest(
                symbols=symbols,
                start_date=test_start,
                end_date=test_end,
                config=best_params
            )
            
            period_results = {
                'period': i + 1,
                'train_period': (train_start, train_end),
                'test_period': (test_start, test_end),
                'train_objective': opt_results['best_value'],
                'test_winrate': test_results['winrate'],
                'test_profit_factor': test_results['profit_factor'],
                'test_sharpe': test_results['sharpe_ratio'],
                'test_max_dd': test_results['max_drawdown'],
                'best_params': best_params
            }
            
            results_list.append(period_results)
            
            logger.info(f"  Test Winrate: {test_results['winrate']:.1f}%")
            logger.info(f"  Test Sharpe: {test_results['sharpe_ratio']:.2f}")
        
        # Moyennes
        avg_winrate = np.mean([r['test_winrate'] for r in results_list])
        avg_sharpe = np.mean([r['test_sharpe'] for r in results_list])
        avg_pf = np.mean([r['test_profit_factor'] for r in results_list])
        
        logger.info(f"\n✅ Walk-Forward Optimization terminé")
        logger.info(f"  Winrate moyen: {avg_winrate:.1f}%")
        logger.info(f"  Sharpe moyen: {avg_sharpe:.2f}")
        logger.info(f"  Profit Factor moyen: {avg_pf:.2f}")
        
        return {
            'periods': results_list,
            'avg_winrate': avg_winrate,
            'avg_sharpe': avg_sharpe,
            'avg_profit_factor': avg_pf,
            'total_periods': len(results_list)
        }
    
    def _save_optimization_results(self, results: Dict):
        """Sauvegarder résultats optimisation dans Analytics DB"""
        # TODO: Implémenter table optimization_results dans Analytics DB
        pass
    
    def get_best_trials(self, n: int = 10) -> List[optuna.Trial]:
        """
        Obtenir N meilleurs trials
        
        Args:
            n: Nombre trials
        
        Returns:
            Liste trials
        """
        return sorted(
            self.study.trials,
            key=lambda t: t.value if t.value is not None else -float('inf'),
            reverse=True
        )[:n]
    
    def plot_optimization_history(self, save_path: Optional[str] = None):
        """
        Tracer historique optimisation
        
        Args:
            save_path: Chemin sauvegarde (optionnel)
        """
        try:
            import matplotlib.pyplot as plt
            
            fig = optuna.visualization.matplotlib.plot_optimization_history(self.study)
            
            if save_path:
                plt.savefig(save_path)
                logger.info(f"📊 Graphique sauvegardé: {save_path}")
            else:
                plt.show()
        
        except ImportError:
            logger.warning("⚠️ matplotlib non installé, impossible de tracer graphique")
    
    def plot_param_importances(self, save_path: Optional[str] = None):
        """
        Tracer importance paramètres
        
        Args:
            save_path: Chemin sauvegarde
        """
        try:
            import matplotlib.pyplot as plt
            
            fig = optuna.visualization.matplotlib.plot_param_importances(self.study)
            
            if save_path:
                plt.savefig(save_path)
                logger.info(f"📊 Graphique sauvegardé: {save_path}")
            else:
                plt.show()
        
        except ImportError:
            logger.warning("⚠️ matplotlib non installé")


# ==================== HELPER ====================

def create_ml_optimizer(
    initial_capital: float = 1000.0,
    data_path: str = "historical_data",
    study_name: str = "trading_optimization"
) -> MLOptimizer:
    """
    Factory pour créer ML Optimizer
    
    Args:
        initial_capital: Capital initial backtest
        data_path: Chemin données historiques
        study_name: Nom étude Optuna
    
    Returns:
        Instance MLOptimizer
    """
    from backtesting.engine import create_backtest_engine
    
    backtest_engine = create_backtest_engine(
        initial_capital=initial_capital,
        data_path=data_path
    )
    
    return MLOptimizer(
        backtest_engine=backtest_engine,
        study_name=study_name
    )


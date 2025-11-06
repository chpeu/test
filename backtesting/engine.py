"""
📊 BACKTESTING ENGINE - Moteur de backtesting complet
Hérite AbstractTradingManager

Fonctionnalités :
- Backtest sur données historiques
- Optimisations (cache, parallélisation)
- Walk-forward analysis
- Métriques complètes
- Intégration Analytics DB

Utilisé par ML Optimizer pour tester configs
"""

from trading.abstract_trading_manager import AbstractTradingManager, TradingPosition
from core.analytics_database import AnalyticsDatabase
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from functools import lru_cache
import logging
import time
import pandas as pd
import numpy as np
from pathlib import Path
import json
import hashlib

logger = logging.getLogger(__name__)


class BacktestEngine(AbstractTradingManager):
    """
    Moteur de backtesting
    
    Lit données historiques et simule trading
    Compatible avec Paper Trading (même logique TP/SL)
    """
    
    def __init__(
        self,
        initial_capital: float = 1000.0,
        data_path: str = "historical_data",
        analytics_db: Optional[AnalyticsDatabase] = None,
        use_cache: bool = True,
        config: Optional[Dict] = None
    ):
        """
        Initialiser Backtest Engine
        
        Args:
            initial_capital: Capital initial
            data_path: Chemin données historiques
            analytics_db: Analytics DB pour logging
            use_cache: Utiliser cache indicateurs
            config: Configuration trading (seuils, etc.)
        """
        super().__init__(initial_capital)
        
        self.data_path = Path(data_path)
        self.analytics_db = analytics_db
        self.use_cache = use_cache
        
        # Override config si fourni
        if config:
            self.config.update(config)
        
        # Données historiques
        self.historical_data: Dict[str, pd.DataFrame] = {}
        self.current_index: Dict[str, int] = {}
        
        # Backtest ID unique
        self.backtest_id = self._generate_backtest_id()
        self.session_id = f"backtest_{int(time.time())}"
        
        # Métriques
        self.equity_curve: List[float] = [initial_capital]
        self.timestamps: List[float] = []
        
        logger.info(f"📊 Backtest Engine initialisé | ID: {self.backtest_id} | Cache: {use_cache}")
    
    def _generate_backtest_id(self) -> str:
        """Générer ID unique pour ce backtest"""
        config_str = json.dumps(self.config, sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]
        timestamp = int(time.time())
        return f"bt_{timestamp}_{config_hash}"
    
    # ==================== DATA LOADING ====================
    
    def load_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = '1m'
    ) -> pd.DataFrame:
        """
        Charger données historiques pour un symbole
        
        Args:
            symbol: Symbole (ex: 'BTC/USDT:USDT')
            start_date: Date début (YYYY-MM-DD)
            end_date: Date fin (YYYY-MM-DD)
            timeframe: Timeframe (1m, 5m, etc.)
        
        Returns:
            DataFrame avec colonnes: timestamp, open, high, low, close, volume
        """
        # Construire chemin fichier
        safe_symbol = symbol.replace('/', '_').replace(':', '_')
        filename = self.data_path / f"{safe_symbol}_{timeframe}_{start_date}_{end_date}.csv"
        
        # Charger depuis CSV
        if filename.exists():
            df = pd.read_csv(filename)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            logger.info(f"✅ Données chargées: {symbol} | {len(df)} candles | {start_date} → {end_date}")
            return df
        else:
            logger.warning(f"⚠️ Fichier non trouvé: {filename}")
            # Retourner DataFrame vide avec bonnes colonnes
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    def preload_data(self, symbols: List[str], start_date: str, end_date: str):
        """
        Précharger données pour plusieurs symboles
        
        Args:
            symbols: Liste symboles
            start_date: Date début
            end_date: Date fin
        """
        for symbol in symbols:
            df = self.load_historical_data(symbol, start_date, end_date)
            if not df.empty:
                self.historical_data[symbol] = df
                self.current_index[symbol] = 0
        
        logger.info(f"✅ {len(self.historical_data)} symboles préchargés")
    
    # ==================== IMPLÉMENTATION ABSTRAITE ====================
    
    def execute_order(self, order: Dict) -> Dict:
        """
        Exécuter ordre (SIMULATION - données historiques)
        
        Args:
            order: {'type': 'BUY'/'SELL', 'symbol': ..., 'size': ...}
        
        Returns:
            {'executed': True, 'price': ..., 'timestamp': ...}
        """
        symbol = order['symbol']
        order_type = order['type']
        
        # Prix actuel (depuis données historiques)
        price = self.get_current_price(symbol)
        
        # Appliquer slippage
        adjusted_price = self.apply_fees_slippage(price, order_type)
        
        # Timestamp actuel
        timestamp = self.get_current_timestamp(symbol)
        
        return {
            'executed': True,
            'price': adjusted_price,
            'timestamp': timestamp,
            'simulated': True,
            'backtest_id': self.backtest_id
        }
    
    def get_current_price(self, symbol: str) -> float:
        """
        Obtenir prix actuel (depuis données historiques)
        
        Args:
            symbol: Symbole
        
        Returns:
            Prix close de la candle actuelle
        """
        if symbol not in self.historical_data:
            logger.error(f"❌ Symbole {symbol} pas préchargé")
            return 0.0
        
        df = self.historical_data[symbol]
        idx = self.current_index.get(symbol, 0)
        
        if idx >= len(df):
            return 0.0
        
        return df.iloc[idx]['close']
    
    def get_current_timestamp(self, symbol: str) -> float:
        """Obtenir timestamp actuel"""
        if symbol not in self.historical_data:
            return time.time()
        
        df = self.historical_data[symbol]
        idx = self.current_index.get(symbol, 0)
        
        if idx >= len(df):
            return time.time()
        
        return df.iloc[idx]['timestamp'].timestamp()
    
    # ==================== BACKTESTING LOOP ====================
    
    def run_backtest(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        strategy_func=None,
        config: Optional[Dict] = None
    ) -> Dict:
        """
        Exécuter backtest complet
        
        Args:
            symbols: Liste symboles à trader
            start_date: Date début (YYYY-MM-DD)
            end_date: Date fin (YYYY-MM-DD)
            strategy_func: Fonction stratégie (optionnel)
            config: Config trading (optionnel)
        
        Returns:
            Dict avec métriques (winrate, profit_factor, equity_curve, etc.)
        """
        logger.info(f"📊 Début backtest: {start_date} → {end_date} | {len(symbols)} symboles")
        
        # Override config si fourni
        if config:
            self.config.update(config)
        
        # Précharger données
        self.preload_data(symbols, start_date, end_date)
        
        if not self.historical_data:
            logger.error("❌ Aucune donnée historique chargée")
            return {'error': 'No data'}
        
        # Déterminer longueur min
        min_length = min(len(df) for df in self.historical_data.values())
        
        # Boucle principale (bar-by-bar)
        for i in range(min_length):
            # Avancer index pour tous symboles
            for symbol in self.historical_data.keys():
                self.current_index[symbol] = i
            
            # Vérifier position active
            if self.active_position:
                self._check_position_tick()
            
            # Chercher setups (si pas de position)
            if not self.active_position and strategy_func:
                setup = strategy_func(self, symbols)
                if setup:
                    self._open_position_from_setup(setup)
            
            # Logger equity
            if i % 100 == 0:  # Tous les 100 candles
                self.equity_curve.append(self.capital)
                self.timestamps.append(self.get_current_timestamp(symbols[0]))
        
        # Fermer position restante
        if self.active_position:
            self.close_position('END_BACKTEST')
        
        # Calculer métriques
        results = self._calculate_backtest_metrics()
        
        # Logger dans Analytics DB
        if self.analytics_db:
            self._save_backtest_results(results)
        
        logger.info(f"✅ Backtest terminé | Trades: {results['total_trades']} | Winrate: {results['winrate']:.1f}%")
        
        return results
    
    def _check_position_tick(self):
        """Vérifier position à chaque tick"""
        if not self.active_position:
            return
        
        position = self.active_position
        current_price = self.get_current_price(position.symbol)
        
        if current_price <= 0:
            return
        
        # Early invalidation
        elapsed = self.get_current_timestamp(position.symbol) - position.start_time
        if elapsed <= 30:
            if self.check_early_invalidation(position, current_price):
                self.close_position('EARLY_INVALIDATION', current_price)
                return
        
        # Break-even
        self.update_break_even(position, current_price)
        
        # Trailing
        pnl_pct = self.calculate_pnl_pct(position, current_price)
        if pnl_pct > 0.25:
            self.update_trailing_stop(position, current_price)
        
        # TP/SL
        reason = self.check_tp_sl(position, current_price)
        if reason:
            self.close_position(reason, current_price)
    
    def _open_position_from_setup(self, setup: Dict):
        """Ouvrir position depuis setup détecté"""
        self.open_position(
            symbol=setup['symbol'],
            direction=setup['direction'],
            entry=setup['entry'],
            size=setup['size'],
            sl=setup['sl'],
            tp=setup['tp'],
            condition_types=setup.get('condition_types', []),
            atr=setup.get('atr'),
            atr5m=setup.get('atr5m')
        )
    
    # ==================== MÉTRIQUES ====================
    
    def _calculate_backtest_metrics(self) -> Dict:
        """Calculer métriques complètes du backtest"""
        stats = self.get_stats()
        
        # Equity curve
        equity_array = np.array(self.equity_curve)
        returns = np.diff(equity_array) / equity_array[:-1]
        
        # Max drawdown
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max
        max_drawdown = abs(drawdown.min()) * 100 if len(drawdown) > 0 else 0
        
        # Sharpe Ratio (annualisé, 252 jours trading)
        sharpe = 0
        if len(returns) > 0 and returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252 * 1440)  # 1440 min/jour
        
        # Sortino Ratio (seulement downside volatility)
        downside_returns = returns[returns < 0]
        sortino = 0
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino = (returns.mean() / downside_returns.std()) * np.sqrt(252 * 1440)
        
        return {
            **stats,
            'backtest_id': self.backtest_id,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'equity_curve': self.equity_curve,
            'timestamps': self.timestamps,
            'config': self.config,
            'session_id': self.session_id
        }
    
    def _save_backtest_results(self, results: Dict):
        """Sauvegarder résultats dans Analytics DB"""
        if not self.analytics_db:
            return
        
        # Sauvegarder tous les trades avec flag is_backtest=True
        for trade in self.closed_trades:
            trade_data = {
                **trade,
                'trading_mode': 'BACKTEST',
                'is_backtest': True,
                'backtest_id': self.backtest_id,
                'session_id': self.session_id
            }
            
            try:
                self.analytics_db.insert_trade(trade_data)
            except Exception as e:
                logger.error(f"❌ Erreur save trade: {e}")
    
    # ==================== HOOKS ====================
    
    def on_position_opened(self, position: TradingPosition):
        """Hook position ouverte"""
        # Silencieux en backtest (trop verbeux)
        pass
    
    def on_position_closed(self, position: TradingPosition, result: Dict):
        """Hook position fermée"""
        # Silencieux en backtest
        pass
    
    # ==================== WALK-FORWARD ANALYSIS ====================
    
    def walk_forward_analysis(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        train_period_days: int = 90,
        test_period_days: int = 30,
        strategy_func=None
    ) -> Dict:
        """
        Walk-Forward Analysis (pour éviter overfitting)
        
        Args:
            symbols: Symboles
            start_date: Date début globale
            end_date: Date fin globale
            train_period_days: Durée période train
            test_period_days: Durée période test
            strategy_func: Fonction stratégie
        
        Returns:
            Dict avec résultats par période + moyenne
        """
        logger.info(f"🔄 Walk-Forward Analysis: {start_date} → {end_date}")
        
        # Générer périodes
        periods = self._generate_walk_forward_periods(
            start_date, end_date, train_period_days, test_period_days
        )
        
        results_list = []
        
        for i, (train_start, train_end, test_start, test_end) in enumerate(periods):
            logger.info(f"\n📊 Période {i+1}/{len(periods)}")
            logger.info(f"  Train: {train_start} → {train_end}")
            logger.info(f"  Test:  {test_start} → {test_end}")
            
            # Backtest sur période test
            # (En pratique, on optimiserait sur train, puis testerait sur test)
            results = self.run_backtest(symbols, test_start, test_end, strategy_func)
            results['period'] = i + 1
            results['train_period'] = (train_start, train_end)
            results['test_period'] = (test_start, test_end)
            results_list.append(results)
            
            # Reset pour prochaine période
            self.capital = self.initial_capital
            self.closed_trades = []
            self.equity_curve = [self.initial_capital]
        
        # Moyennes
        avg_winrate = np.mean([r['winrate'] for r in results_list])
        avg_profit_factor = np.mean([r['profit_factor'] for r in results_list])
        avg_sharpe = np.mean([r['sharpe_ratio'] for r in results_list])
        
        logger.info(f"\n✅ Walk-Forward terminé")
        logger.info(f"  Winrate moyen: {avg_winrate:.1f}%")
        logger.info(f"  Profit Factor moyen: {avg_profit_factor:.2f}")
        logger.info(f"  Sharpe moyen: {avg_sharpe:.2f}")
        
        return {
            'periods': results_list,
            'avg_winrate': avg_winrate,
            'avg_profit_factor': avg_profit_factor,
            'avg_sharpe': avg_sharpe,
            'total_periods': len(results_list)
        }
    
    def _generate_walk_forward_periods(
        self,
        start_date: str,
        end_date: str,
        train_days: int,
        test_days: int
    ) -> List[Tuple[str, str, str, str]]:
        """Générer périodes train/test pour walk-forward"""
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        periods = []
        current = start
        
        while current < end:
            train_start = current
            train_end = current + timedelta(days=train_days)
            test_start = train_end
            test_end = test_start + timedelta(days=test_days)
            
            if test_end > end:
                break
            
            periods.append((
                train_start.strftime('%Y-%m-%d'),
                train_end.strftime('%Y-%m-%d'),
                test_start.strftime('%Y-%m-%d'),
                test_end.strftime('%Y-%m-%d')
            ))
            
            # Avancer (test devient train)
            current = test_start
        
        return periods


# ==================== HELPER ====================

def create_backtest_engine(
    initial_capital: float = 1000.0,
    data_path: str = "historical_data",
    analytics_db: Optional[AnalyticsDatabase] = None,
    config: Optional[Dict] = None
) -> BacktestEngine:
    """
    Factory pour créer Backtest Engine
    
    Args:
        initial_capital: Capital initial
        data_path: Chemin données
        analytics_db: Analytics DB
        config: Config trading
    
    Returns:
        Instance BacktestEngine
    """
    return BacktestEngine(
        initial_capital=initial_capital,
        data_path=data_path,
        analytics_db=analytics_db,
        config=config
    )


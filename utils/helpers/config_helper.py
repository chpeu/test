"""
🔥 SPRINT 1.5: ConfigHelper

Pattern 2 - TRADING_CONFIG.get() (312+ occurrences)

Helper pour centraliser l'accès aux paramètres de configuration trading.

Avant (main.py, lignes 620-640):
```python
account_size = TRADING_CONFIG.get('account_size', 1000.0)
risk_per_trade = TRADING_CONFIG.get('risk_per_trade', 2.0) / 100
tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
atr_min = TRADING_CONFIG.get('atr_min', 0.15)
# ... 10+ lignes supplémentaires
```

Après:
```python
params = ConfigHelper.get_trading_params()
account_size = params['account_size']
risk_per_trade = params['risk_per_trade']
```

Impact: -200 à -300 lignes de code dupliqué
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigHelper:
    """Helper pour accès centralisé aux configurations trading"""

    @staticmethod
    def get_trading_params(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Récupérer tous les paramètres trading courants

        Args:
            config: Config dict (si None, utilise TRADING_CONFIG global)

        Returns:
            Dict avec tous les paramètres trading standardisés
        """
        if config is None:
            try:
                from config import TRADING_CONFIG
                config = TRADING_CONFIG
            except ImportError:
                logger.warning("⚠️ TRADING_CONFIG non disponible, utilisation valeurs par défaut")
                config = {}

        return {
            # Account & Risk
            'account_size': config.get('account_size', 1000.0),
            'risk_per_trade': config.get('risk_per_trade', 2.0) / 100,  # Converti en décimal
            'max_position_size': config.get('max_position_size', 500.0),

            # TP/SL Configuration
            'tp_sl_mode': config.get('tp_sl_mode', 'FIXE'),
            'sl_percent': config.get('sl_percent', 0.25),
            'tp_percent': config.get('tp_percent', 0.6),

            # ATR Constraints
            'atr_min': config.get('atr_min', 0.15),
            'atr_max': config.get('atr_max', 1.5),

            # Trading Features
            'use_confluence': config.get('use_confluence', False),
            'use_trailing_stop': config.get('use_trailing_stop', True),
            'volume_multiplier': config.get('volume_multiplier', 1.0),

            # Timeframes
            'trend_timeframe': config.get('trend_timeframe', '15m'),
            'entry_timeframe': config.get('entry_timeframe', '1m'),

            # Filters
            'min_volume_24h': config.get('min_volume_24h', 1000000),
            'max_spread_pct': config.get('max_spread_pct', 0.1),
            'min_liquidity_score': config.get('min_liquidity_score', 0.5),

            # ML/Advanced
            'use_ml_model': config.get('use_ml_model', False),
            'ml_confidence_threshold': config.get('ml_confidence_threshold', 0.7),

            # Scaling
            'enable_scaling': config.get('enable_scaling', False),
            'scale_factor': config.get('scale_factor', 1.5),
            'max_scale_count': config.get('max_scale_count', 3),
        }

    @staticmethod
    def get_scanner_params(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Récupérer paramètres scanner

        Args:
            config: Config dict (si None, utilise TRADING_CONFIG global)

        Returns:
            Dict avec paramètres scanner
        """
        if config is None:
            try:
                from config import TRADING_CONFIG
                config = TRADING_CONFIG
            except ImportError:
                logger.warning("⚠️ TRADING_CONFIG non disponible, utilisation valeurs par défaut")
                config = {}

        return {
            'scan_interval': config.get('scan_interval', 60),
            'top_pairs_count': config.get('top_pairs_count', 10),
            'min_score': config.get('min_score', 70),
            'scan_mode': config.get('scan_mode', 'QUALITY'),
            'excluded_symbols': config.get('excluded_symbols', []),
            'required_confirmations': config.get('required_confirmations', 3),
        }

    @staticmethod
    def get_position_params(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Récupérer paramètres position management

        Args:
            config: Config dict (si None, utilise TRADING_CONFIG global)

        Returns:
            Dict avec paramètres position management
        """
        if config is None:
            try:
                from config import TRADING_CONFIG
                config = TRADING_CONFIG
            except ImportError:
                logger.warning("⚠️ TRADING_CONFIG non disponible, utilisation valeurs par défaut")
                config = {}

        return {
            'max_position_duration': config.get('max_position_duration', 3600),  # 1h en secondes
            'enable_breakeven': config.get('enable_breakeven', True),
            'breakeven_trigger_pct': config.get('breakeven_trigger_pct', 0.3),
            'enable_partial_tp': config.get('enable_partial_tp', False),
            'partial_tp_percent': config.get('partial_tp_percent', 50),
            'partial_tp_trigger': config.get('partial_tp_trigger', 0.4),
        }

    @staticmethod
    def get_api_params(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Récupérer paramètres API/Exchange

        Args:
            config: Config dict (si None, utilise TRADING_CONFIG global)

        Returns:
            Dict avec paramètres API
        """
        if config is None:
            try:
                from config import TRADING_CONFIG
                config = TRADING_CONFIG
            except ImportError:
                logger.warning("⚠️ TRADING_CONFIG non disponible, utilisation valeurs par défaut")
                config = {}

        return {
            'exchange': config.get('exchange', 'mexc'),
            'testnet': config.get('testnet', False),
            'rate_limit': config.get('rate_limit', 10),
            'timeout': config.get('timeout', 30000),
            'enable_rate_limit': config.get('enableRateLimit', True),
        }

    @staticmethod
    def get_param(key: str, default: Any = None, config: Optional[Dict[str, Any]] = None) -> Any:
        """
        Récupérer un paramètre spécifique de la config

        Args:
            key: Clé du paramètre
            default: Valeur par défaut
            config: Config dict (si None, utilise TRADING_CONFIG global)

        Returns:
            Valeur du paramètre ou default
        """
        if config is None:
            try:
                from config import TRADING_CONFIG
                config = TRADING_CONFIG
            except ImportError:
                logger.warning(f"⚠️ TRADING_CONFIG non disponible, retour default pour {key}")
                return default

        return config.get(key, default)

    @staticmethod
    def get_all_params(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Récupérer TOUS les paramètres en un seul appel

        Args:
            config: Config dict (si None, utilise TRADING_CONFIG global)

        Returns:
            Dict complet avec tous les paramètres
        """
        return {
            **ConfigHelper.get_trading_params(config),
            **ConfigHelper.get_scanner_params(config),
            **ConfigHelper.get_position_params(config),
            **ConfigHelper.get_api_params(config),
        }

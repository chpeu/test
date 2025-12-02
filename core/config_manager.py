"""
Gestionnaire de configuration persistante

Permet de sauvegarder les modifications de configuration dans un fichier JSON
et de les charger au démarrage. Fournit validation et accès typé.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from threading import RLock
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TradingConfigSection:
    """
    Trading configuration with type hints, defaults, and validation.

    This dataclass provides type-safe access to trading configuration
    and validates values to prevent runtime errors.
    """

    # Fee and slippage
    fee_per_trade: float = 0.0004
    use_slippage_calculation: bool = True

    # Timeouts and intervals
    position_timeout: int = 300  # seconds
    check_interval: float = 0.1  # seconds
    scan_interval: int = 30  # seconds
    scalability_interval: int = 90  # seconds

    # Excluded symbols
    excluded_symbols: List[str] = field(default_factory=list)

    # Volume settings
    volume_multiplier_range: tuple = (0.10, 2.00)
    volume_multiplier: float = 0.95

    # TP/SL settings
    tp_sl_mode: str = "FIXE"  # FIXE or ATR
    tp_percent: float = 0.50
    sl_percent: float = 0.20
    break_even_trigger: float = 0.3
    trailing_distance: float = 0.15

    # ATR mode
    atr_mult_tp: float = 1.5
    atr_mult_sl: float = 1.0
    atr_min: float = 0.15
    atr_max: float = 1.5

    # Trend analysis
    trend_timeframe: str = "15m"

    # Entry conditions
    min_conditions: int = 6
    dynamic_tolerance_adx_high: float = 30
    dynamic_tolerance_adx_low: float = 25

    # Scoring system
    use_weighted_scoring: bool = True
    min_score_required: float = 6.5
    min_score_adx_high: float = 6.0
    min_score_adx_low: float = 7.0

    # Technical patterns
    use_breakout: bool = True
    use_snr: bool = True
    use_wick: bool = True
    use_divergence: bool = True

    # Candle patterns
    use_engulfing: bool = True
    use_hammer: bool = True
    use_shooting_star: bool = True
    use_doji: bool = True
    use_marubozu: bool = True
    use_morning_star: bool = True
    use_evening_star: bool = True

    # Filter thresholds
    snr_threshold: float = 0.15
    breakout_threshold: float = 0.25
    wick_ratio_max: float = 4.5
    di_gap_min: float = 4.0
    di_gap_adx_threshold: float = 25

    # ATR filters
    optimal_atr_min_1m: float = 0.12
    optimal_atr_max_1m: float = 0.75
    optimal_atr_min_5m: float = 0.22
    optimal_atr_max_5m: float = 1.4

    # Scanner settings
    top_pairs_limit: int = 20
    balance_score_min: float = 0.7

    # Confluence (multi-timeframe)
    use_confluence: bool = False

    def validate(self) -> None:
        """
        Validate configuration values.

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate percentages
        if not 0 <= self.fee_per_trade <= 1:
            raise ValueError(f"fee_per_trade must be between 0 and 1, got {self.fee_per_trade}")

        if self.tp_percent <= 0:
            raise ValueError(f"tp_percent must be positive, got {self.tp_percent}")

        if self.sl_percent <= 0:
            raise ValueError(f"sl_percent must be positive, got {self.sl_percent}")

        # Validate intervals
        if self.check_interval <= 0:
            raise ValueError(f"check_interval must be positive, got {self.check_interval}")

        if self.scan_interval <= 0:
            raise ValueError(f"scan_interval must be positive, got {self.scan_interval}")

        # Validate timeframe
        valid_timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        if self.trend_timeframe not in valid_timeframes:
            raise ValueError(
                f"trend_timeframe must be one of {valid_timeframes}, got {self.trend_timeframe}"
            )

        # Validate TP/SL mode
        valid_modes = ['FIXE', 'ATR']
        if self.tp_sl_mode not in valid_modes:
            raise ValueError(f"tp_sl_mode must be one of {valid_modes}, got {self.tp_sl_mode}")

        # Validate volume multiplier
        if self.volume_multiplier <= 0:
            raise ValueError(f"volume_multiplier must be positive, got {self.volume_multiplier}")


class ConfigManager:
    """
    Gestionnaire de configuration avec sauvegarde persistante, validation et accès typé.

    Features:
    - Thread-safe configuration management
    - Persistent storage of overrides
    - Type-safe access via .trading property
    - Validation of configuration values
    - Backwards compatible with dict-style access
    """

    def __init__(self, config_file: str = "config_overrides.json"):
        self.config_file = Path(config_file)
        self.overrides = {}
        self.lock = RLock()  # Utiliser RLock pour éviter deadlock
        self._trading_config: Optional[TradingConfigSection] = None
        self._base_config: Optional[Dict[str, Any]] = None
        self.load_overrides()

    def load_overrides(self) -> None:
        """Charger les overrides depuis le fichier JSON"""
        if not self.config_file.exists():
            logger.info(f"📄 Fichier {self.config_file} n'existe pas, création avec config par défaut")
            self.overrides = {}
            return

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.overrides = json.load(f)
            logger.info(f"✅ Configuration chargée depuis {self.config_file} ({len(self.overrides)} overrides)")
        except Exception as e:
            logger.error(f"❌ Erreur chargement config depuis {self.config_file}: {e}")
            self.overrides = {}

    def save_overrides(self) -> bool:
        """Sauvegarder les overrides dans le fichier JSON"""
        try:
            with self.lock:
                # Atomic write: écrire dans un fichier temporaire puis renommer
                temp_file = self.config_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.overrides, f, indent=2, ensure_ascii=False)

                # Remplacer l'ancien fichier
                temp_file.replace(self.config_file)

            logger.info(f"💾 Configuration sauvegardée dans {self.config_file} ({len(self.overrides)} overrides)")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde config dans {self.config_file}: {e}")
            return False

    def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mettre à jour la configuration avec les nouvelles valeurs

        Args:
            updates: Dictionnaire des nouvelles valeurs

        Returns:
            Dictionnaire des valeurs mises à jour
        """
        updated = {}

        with self.lock:
            for key, value in updates.items():
                # Ignorer les valeurs None
                if value is None:
                    continue

                # Sauvegarder l'override
                self.overrides[key] = value
                updated[key] = value

            # Sauvegarder dans le fichier
            if updated:
                self.save_overrides()

        return updated

    def get_config(self, defaults: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtenir la configuration complète (defaults + overrides)

        Args:
            defaults: Configuration par défaut

        Returns:
            Configuration complète (defaults + overrides)
        """
        with self.lock:
            # Store base config for later use
            if self._base_config is None:
                self._base_config = defaults

            # Merger defaults avec overrides
            config = {**defaults, **self.overrides}

            # Build typed config if not already done
            if self._trading_config is None:
                self._build_trading_config(config)

            return config

    def _build_trading_config(self, config: Dict[str, Any]) -> None:
        """Build typed trading configuration from dict."""
        try:
            # Filter only keys that exist in TradingConfigSection
            config_fields = set(TradingConfigSection.__dataclass_fields__.keys())
            typed_config_data = {k: v for k, v in config.items() if k in config_fields}

            self._trading_config = TradingConfigSection(**typed_config_data)
            self._trading_config.validate()

            logger.debug("✅ Typed trading configuration built and validated")
        except Exception as e:
            logger.warning(f"⚠️ Failed to build typed config: {e}. Using defaults.")
            self._trading_config = TradingConfigSection()

    @property
    def trading(self) -> TradingConfigSection:
        """
        Access type-safe trading configuration.

        Returns:
            TradingConfigSection with validated configuration

        Example:
            config = get_config_manager()
            max_pairs = config.trading.top_pairs_limit
            use_confluence = config.trading.use_confluence
        """
        if self._trading_config is None:
            # Try to build from base config
            if self._base_config is not None:
                merged = {**self._base_config, **self.overrides}
                self._build_trading_config(merged)
            else:
                # Fallback to defaults
                self._trading_config = TradingConfigSection()

        return self._trading_config

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key (backwards compatible).

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            config = get_config_manager()
            max_pairs = config.get('top_pairs_limit', 20)
        """
        with self.lock:
            # Try overrides first
            if key in self.overrides:
                return self.overrides[key]

            # Try typed config
            if self._trading_config and hasattr(self._trading_config, key):
                return getattr(self._trading_config, key)

            # Try base config
            if self._base_config and key in self._base_config:
                return self._base_config[key]

            return default

    def reset_to_defaults(self) -> None:
        """Réinitialiser tous les overrides"""
        with self.lock:
            self.overrides = {}
            self.save_overrides()
        logger.info("🔄 Configuration réinitialisée aux valeurs par défaut")

    def reset_key(self, key: str) -> bool:
        """
        Réinitialiser une seule clé

        Args:
            key: Clé à réinitialiser

        Returns:
            True si la clé existait, False sinon
        """
        with self.lock:
            if key in self.overrides:
                del self.overrides[key]
                self.save_overrides()
                logger.info(f"🔄 Clé '{key}' réinitialisée")
                return True
            return False

    def get_overrides(self) -> Dict[str, Any]:
        """Obtenir tous les overrides actuels"""
        with self.lock:
            return self.overrides.copy()


# Instance globale
_config_manager = None

def get_config_manager() -> ConfigManager:
    """Obtenir l'instance globale du ConfigManager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

"""
🔥 SPRINT 1.5: DataLoggerHelper

Pattern 6 - Data Logger Integration (300-400 lignes)

Helper pour simplifier l'intégration avec DataLogger ML/Analytics.

Avant (core/analyzer.py, lignes 756-776):
```python
try:
    from backend.ml.data_logger import DataLogger
    data_logger = DataLogger()

    if data_logger and data_logger.is_running:
        scan_uuid = await data_logger.log_scan(
            symbol=symbol,
            price=current_price,
            # ... 20+ paramètres
        )
except Exception as e:
    logger.debug(f"Erreur log_scan (non-bloquant): {e}")
    scan_uuid = None
```

Après:
```python
scan_uuid = await DataLoggerHelper.safe_log_scan(
    symbol=symbol,
    price=current_price,
    # ... paramètres
)
```

Impact: -300 à -400 lignes de code dupliqué
"""

from typing import Dict, Any, Optional
import logging
import sys

logger = logging.getLogger(__name__)


class DataLoggerHelper:
    """Helper pour intégration DataLogger (ML/Analytics)"""

    _data_logger_instance = None
    _import_attempted = False

    @classmethod
    def _get_data_logger(cls):
        """
        Récupérer instance DataLogger (lazy loading avec cache)

        Returns:
            DataLogger instance ou None si non disponible
        """
        if 'pytest' in sys.modules:
            return None
        if not cls._import_attempted:
            cls._import_attempted = True
            try:
                from backend.ml.data_logger import DataLogger
                cls._data_logger_instance = DataLogger()
                logger.info("✅ DataLogger initialisé")
            except ImportError:
                logger.debug("ℹ️ DataLogger non disponible (backend.ml non importé)")
                cls._data_logger_instance = None
            except Exception as e:
                logger.warning(f"⚠️ Erreur initialisation DataLogger: {e}")
                cls._data_logger_instance = None

        return cls._data_logger_instance

    @classmethod
    def is_available(cls) -> bool:
        """
        Vérifier si DataLogger est disponible et running

        Returns:
            True si DataLogger prêt à utiliser
        """
        logger_instance = cls._get_data_logger()
        return logger_instance is not None and getattr(logger_instance, 'is_running', False)

    @classmethod
    async def safe_log_scan(
        cls,
        symbol: str,
        price: float,
        **kwargs
    ) -> Optional[str]:
        """
        Logger un scan (Point A) de manière sûre

        Args:
            symbol: Symbole de la paire
            price: Prix actuel
            **kwargs: Autres paramètres (indicators_1m, indicators_5m, etc.)

        Returns:
            scan_uuid si succès, None sinon (NON-BLOQUANT)
        """
        try:
            logger_instance = cls._get_data_logger()
            if logger_instance and logger_instance.is_running:
                return await logger_instance.log_scan(
                    symbol=symbol,
                    price=price,
                    **kwargs
                )
        except Exception as e:
            logger.debug(f"Erreur log_scan pour {symbol} (non-bloquant): {e}")

        return None

    @classmethod
    async def safe_log_micro_confirmation(
        cls,
        scan_log_id: str,
        symbol: str,
        current_price: float,
        **kwargs
    ) -> Optional[str]:
        """
        Logger une micro-confirmation (Point B) de manière sûre

        Args:
            scan_log_id: UUID du scan (Point A)
            symbol: Symbole
            current_price: Prix actuel
            **kwargs: Autres paramètres (candles_data, etc.)

        Returns:
            confirmation_uuid si succès, None sinon (NON-BLOQUANT)
        """
        try:
            logger_instance = cls._get_data_logger()
            if logger_instance and logger_instance.is_running:
                return await logger_instance.log_micro_confirmation(
                    scan_log_id=scan_log_id,
                    symbol=symbol,
                    current_price=current_price,
                    **kwargs
                )
        except Exception as e:
            logger.debug(f"Erreur log_micro_confirmation pour {symbol} (non-bloquant): {e}")

        return None

    @classmethod
    async def safe_log_opportunity(
        cls,
        scan_log_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        **kwargs
    ) -> Optional[str]:
        """
        Logger une opportunité (Point C) de manière sûre

        Args:
            scan_log_id: UUID du scan (Point A)
            symbol: Symbole
            direction: Direction (LONG/SHORT)
            entry_price: Prix d'entrée prévu
            **kwargs: Autres paramètres (stop_loss, take_profit, etc.)

        Returns:
            opportunity_uuid si succès, None sinon (NON-BLOQUANT)
        """
        try:
            logger_instance = cls._get_data_logger()
            if logger_instance and logger_instance.is_running:
                return await logger_instance.log_opportunity(
                    scan_log_id=scan_log_id,
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    **kwargs
                )
        except Exception as e:
            logger.debug(f"Erreur log_opportunity pour {symbol} (non-bloquant): {e}")

        return None

    @classmethod
    async def safe_log_trade_entry(
        cls,
        opportunity_log_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        **kwargs
    ) -> Optional[str]:
        """
        Logger une entrée de trade (Point D) de manière sûre

        Args:
            opportunity_log_id: UUID de l'opportunité (Point C)
            symbol: Symbole
            direction: Direction (LONG/SHORT)
            entry_price: Prix d'entrée réel
            quantity: Quantité tradée
            **kwargs: Autres paramètres (order_id, leverage, etc.)

        Returns:
            trade_uuid si succès, None sinon (NON-BLOQUANT)
        """
        try:
            logger_instance = cls._get_data_logger()
            if logger_instance and logger_instance.is_running:
                return await logger_instance.log_trade_entry(
                    opportunity_log_id=opportunity_log_id,
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    quantity=quantity,
                    **kwargs
                )
        except Exception as e:
            logger.debug(f"Erreur log_trade_entry pour {symbol} (non-bloquant): {e}")

        return None

    @classmethod
    async def safe_log_trade_exit(
        cls,
        trade_log_id: str,
        symbol: str,
        exit_price: float,
        pnl: float,
        reason: str,
        **kwargs
    ) -> Optional[str]:
        """
        Logger une sortie de trade de manière sûre

        Args:
            trade_log_id: UUID du trade (Point D)
            symbol: Symbole
            exit_price: Prix de sortie
            pnl: P&L en pourcentage
            reason: Raison de sortie (TP, SL, etc.)
            **kwargs: Autres paramètres

        Returns:
            exit_uuid si succès, None sinon (NON-BLOQUANT)
        """
        try:
            logger_instance = cls._get_data_logger()
            if logger_instance and logger_instance.is_running:
                return await logger_instance.log_trade_exit(
                    trade_log_id=trade_log_id,
                    symbol=symbol,
                    exit_price=exit_price,
                    pnl=pnl,
                    reason=reason,
                    **kwargs
                )
        except Exception as e:
            logger.debug(f"Erreur log_trade_exit pour {symbol} (non-bloquant): {e}")

        return None

    @classmethod
    async def safe_log_frontend_data(
        cls,
        symbol: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Logger des données frontend de manière sûre

        Args:
            symbol: Symbole
            data: Données à logger

        Returns:
            True si succès, False sinon (NON-BLOQUANT)
        """
        try:
            logger_instance = cls._get_data_logger()
            if logger_instance and logger_instance.is_running:
                await logger_instance.log_frontend_data(symbol=symbol, data=data)
                return True
        except Exception as e:
            logger.debug(f"Erreur log_frontend_data pour {symbol} (non-bloquant): {e}")

        return False

    @classmethod
    def reset_instance(cls):
        """Reset instance DataLogger (pour tests)"""
        cls._data_logger_instance = None
        cls._import_attempted = False

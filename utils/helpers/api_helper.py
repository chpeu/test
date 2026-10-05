"""
🔥 SPRINT 1.5: APIHelper

Patterns 4 & 12 - Price Validation + API Call Protection

Helper pour validation de prix et appels API avec protection.

Avant (position_manager.py, lignes 935-963):
```python
if exit_price is None or exit_price <= 0:
    logger.warning(f"⚠️ Exit price invalide ({exit_price}) pour {symbol}")
    cached_price = self.get_cached_price(symbol, max_age_ms=30000)
    if cached_price and cached_price > 0:
        exit_price = cached_price
        exit_price_source = "cache"
    else:
        exit_price = self.active_position.entry
        exit_price_source = "entry_fallback"
```

Après:
```python
exit_price, source = APIHelper.validate_price_with_fallback(
    price=exit_price,
    symbol=symbol,
    fallback_price=position.entry,
    cache_manager=self
)
```

Impact: -80 à -200 lignes de code dupliqué
"""

from typing import Optional, Tuple, Callable, Any
import logging

logger = logging.getLogger(__name__)


class APIHelper:
    """Helper pour appels API et validation de prix"""

    @staticmethod
    def validate_price_with_fallback(
        price: Optional[float],
        symbol: str,
        fallback_price: float,
        cache_manager: Optional[Any] = None,
        max_age_ms: int = 30000
    ) -> Tuple[float, str]:
        """
        Valider un prix et retourner fallback si invalide

        Args:
            price: Prix à valider
            symbol: Symbole de la paire
            fallback_price: Prix de secours
            cache_manager: Manager avec méthode get_cached_price() (optionnel)
            max_age_ms: Age max du cache en ms

        Returns:
            Tuple (prix_validé, source)
            source: "api", "cache", ou "fallback"

        Exemple:
        ```python
        price, source = APIHelper.validate_price_with_fallback(
            price=current_price,
            symbol="BTC/USDT",
            fallback_price=50000.0,
            cache_manager=self
        )
        ```
        """
        # Prix valide → retour direct
        if price and price > 0:
            return price, "api"

        # Prix invalide → logger warning
        logger.warning(f"⚠️ Prix invalide ({price}) pour {symbol}")

        # Tentative cache
        if cache_manager and hasattr(cache_manager, 'get_cached_price'):
            try:
                cached = cache_manager.get_cached_price(symbol, max_age_ms=max_age_ms)
                if cached and cached > 0:
                    logger.info(f"✅ Prix {symbol} récupéré du cache: {cached}")
                    return cached, "cache"
            except Exception as e:
                logger.debug(f"Erreur récupération cache pour {symbol}: {e}")

        # Fallback final
        logger.warning(f"⚠️ Utilisation fallback price pour {symbol}: {fallback_price}")
        return fallback_price, "fallback"

    @staticmethod
    def validate_price_simple(price: Optional[float], symbol: str = None) -> bool:
        """
        Validation simple d'un prix

        Args:
            price: Prix à valider
            symbol: Symbole (optionnel, pour logging)

        Returns:
            True si prix valide, False sinon
        """
        is_valid = price is not None and price > 0

        if not is_valid and symbol:
            logger.warning(f"⚠️ Prix invalide pour {symbol}: {price}")

        return is_valid

    @staticmethod
    def safe_get_float(
        data: dict,
        key: str,
        default: float = 0.0,
        symbol: Optional[str] = None
    ) -> float:
        """
        Récupérer et convertir une valeur float depuis dict

        Args:
            data: Dict contenant les données
            key: Clé à récupérer
            default: Valeur par défaut
            symbol: Symbole (optionnel, pour logging)

        Returns:
            Float value ou default si erreur

        Exemple:
        ```python
        price = APIHelper.safe_get_float(ticker, 'lastPrice', 0.0, symbol="BTC/USDT")
        ```
        """
        try:
            value = data.get(key, default)

            # Conversion en float
            if value is None:
                return default

            float_value = float(value)

            # Check NaN
            if float_value != float_value:  # NaN check
                if symbol:
                    logger.warning(f"⚠️ Valeur NaN pour {key} ({symbol}), utilisation default")
                return default

            return float_value

        except (ValueError, TypeError) as e:
            if symbol:
                logger.warning(f"⚠️ Erreur conversion {key} pour {symbol}: {e}")
            return default

    @staticmethod
    def safe_get_int(
        data: dict,
        key: str,
        default: int = 0,
        symbol: Optional[str] = None
    ) -> int:
        """
        Récupérer et convertir une valeur int depuis dict

        Args:
            data: Dict contenant les données
            key: Clé à récupérer
            default: Valeur par défaut
            symbol: Symbole (optionnel, pour logging)

        Returns:
            Int value ou default si erreur
        """
        try:
            value = data.get(key, default)

            if value is None:
                return default

            return int(value)

        except (ValueError, TypeError) as e:
            if symbol:
                logger.warning(f"⚠️ Erreur conversion {key} pour {symbol}: {e}")
            return default

    @staticmethod
    async def api_call_with_protection(
        api_method: Callable,
        *args,
        method_name: Optional[str] = None,
        default_return: Any = None,
        protection_wrapper: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Appel API générique avec protection

        Args:
            api_method: Méthode API à appeler
            *args: Args positionnels
            method_name: Nom de la méthode (pour logging)
            default_return: Valeur par défaut si erreur
            protection_wrapper: Wrapper de protection (ex: fetch_with_all_protections)
            **kwargs: Args nommés

        Returns:
            Résultat de l'appel API ou default_return

        Exemple:
        ```python
        ticker = await APIHelper.api_call_with_protection(
            self.exchange.fetch_ticker,
            "BTC/USDT",
            method_name="fetch_ticker",
            default_return=None,
            protection_wrapper=fetch_with_all_protections
        )
        ```
        """
        method_name = method_name or getattr(api_method, '__name__', 'API call')

        try:
            if protection_wrapper:
                # Wrapper avec protection (circuit breaker, retry, etc.)
                async def _fetch():
                    return await api_method(*args, **kwargs)

                return await protection_wrapper(_fetch)
            else:
                # Appel direct
                return await api_method(*args, **kwargs)

        except Exception as e:
            logger.error(f"❌ Erreur {method_name}: {e}")
            return default_return

    @staticmethod
    def extract_price_from_ticker(
        ticker: Optional[dict],
        symbol: Optional[str] = None,
        price_key: str = 'lastPrice'
    ) -> Optional[float]:
        """
        Extraire prix depuis ticker avec validation

        Args:
            ticker: Ticker data
            symbol: Symbole (pour logging)
            price_key: Clé du prix ('lastPrice', 'last', 'close', etc.)

        Returns:
            Prix validé ou None

        Exemple:
        ```python
        price = APIHelper.extract_price_from_ticker(ticker, "BTC/USDT")
        ```
        """
        if not ticker:
            if symbol:
                logger.warning(f"⚠️ Ticker manquant pour {symbol}")
            return None

        # Tenter plusieurs clés possibles
        price_keys = [price_key, 'last', 'close', 'price']

        for key in price_keys:
            price = APIHelper.safe_get_float(ticker, key, 0.0, symbol)
            if price > 0:
                return price

        if symbol:
            logger.warning(f"⚠️ Aucun prix valide trouvé dans ticker pour {symbol}")

        return None

    @staticmethod
    def check_nan(value: float, default: float = 0.0) -> float:
        """
        Vérifier NaN et retourner default si NaN

        Args:
            value: Valeur à vérifier
            default: Valeur par défaut si NaN

        Returns:
            value ou default si NaN
        """
        if isinstance(value, float) and value != value:  # NaN check
            return default
        return value

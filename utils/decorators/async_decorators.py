"""
🔥 SPRINT 1.5: Async Decorators

Pattern 5 - Async Exception Wrapping (100+ fonctions)

Décorateurs pour simplifier la gestion d'erreurs dans les fonctions async.

Avant (api/mexc.py, lignes 38-48):
```python
async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
    async def _fetch():
        return await self.exchange.fetch_ticker(symbol)

    try:
        return await fetch_with_all_protections(_fetch)
    except Exception as e:
        if DEBUG_ENABLED:
            print(f"❌ Erreur fetch_ticker {symbol}: {e}")
        return None
```

Après:
```python
@async_safe(default_return=None, log_errors=True)
async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
    async def _fetch():
        return await self.exchange.fetch_ticker(symbol)
    return await fetch_with_all_protections(_fetch)
```

Impact: -250 à -350 lignes de code dupliqué
"""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union
import os

logger = logging.getLogger(__name__)

# DEBUG_ENABLED global check
DEBUG_ENABLED = os.getenv('DEBUG', '0') == '1'

T = TypeVar('T')


def async_safe(
    default_return: Any = None,
    log_errors: bool = True,
    log_level: str = 'error',
    suppress_errors: bool = False
):
    """
    Décorateur pour gestion sûre des erreurs dans fonctions async

    Args:
        default_return: Valeur retournée en cas d'erreur
        log_errors: Logger les erreurs (si DEBUG_ENABLED=True)
        log_level: Niveau de log ('debug', 'info', 'warning', 'error')
        suppress_errors: Supprimer les exceptions (toujours retourner default_return)

    Returns:
        Décorateur

    Exemple:
    ```python
    @async_safe(default_return=None, log_errors=True)
    async def fetch_data(symbol: str) -> Optional[Dict]:
        return await api.fetch(symbol)
    ```
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Logging (seulement si DEBUG_ENABLED)
                if log_errors and DEBUG_ENABLED:
                    log_func = getattr(logger, log_level, logger.error)

                    # Extraire nom fonction et premier arg (souvent symbol)
                    func_name = func.__name__
                    first_arg = args[1] if len(args) > 1 else args[0] if args else None

                    if first_arg and isinstance(first_arg, str):
                        log_func(f"❌ Erreur {func_name} ({first_arg}): {e}")
                    else:
                        log_func(f"❌ Erreur {func_name}: {e}")

                # Re-raise si pas de suppression
                if not suppress_errors:
                    raise

                return default_return

        return wrapper
    return decorator


def log_errors(log_level: str = 'error', log_in_debug_only: bool = True):
    """
    Décorateur pour logger les erreurs (sans les supprimer)

    Args:
        log_level: Niveau de log ('debug', 'info', 'warning', 'error')
        log_in_debug_only: Logger seulement si DEBUG_ENABLED=True

    Returns:
        Décorateur

    Exemple:
    ```python
    @log_errors(log_level='warning')
    async def critical_operation():
        # erreurs loggées mais propagées
        pass
    ```
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Logger seulement si conditions remplies
                should_log = not log_in_debug_only or DEBUG_ENABLED

                if should_log:
                    log_func = getattr(logger, log_level, logger.error)
                    func_name = func.__name__
                    log_func(f"❌ Erreur {func_name}: {e}")

                # Toujours re-raise
                raise

        return wrapper
    return decorator


def suppress_errors(default_return: Any = None, log_errors: bool = True):
    """
    Décorateur pour supprimer TOUTES les erreurs (retour default_return)

    Args:
        default_return: Valeur retournée en cas d'erreur
        log_errors: Logger les erreurs (si DEBUG_ENABLED=True)

    Returns:
        Décorateur

    Exemple:
    ```python
    @suppress_errors(default_return=0.0, log_errors=True)
    async def get_funding_rate(symbol: str) -> float:
        # TOUJOURS retourne un float, même sur erreur
        return await api.fetch_funding_rate(symbol)
    ```

    Utilisation: Pour fonctions non-critiques (métriques optionnelles, etc.)
    """
    return async_safe(
        default_return=default_return,
        log_errors=log_errors,
        suppress_errors=True
    )


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Décorateur pour retry automatique avec backoff exponentiel

    Args:
        max_retries: Nombre max de retries
        delay: Délai initial entre retries (secondes)
        backoff: Facteur multiplicateur pour delay
        exceptions: Types d'exceptions à retry

    Returns:
        Décorateur

    Exemple:
    ```python
    @retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
    async def unreliable_api_call():
        return await api.fetch()
    ```
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        # Dernier essai → re-raise
                        raise

                    # Log retry
                    if DEBUG_ENABLED:
                        logger.warning(
                            f"⚠️ {func.__name__} échec (tentative {attempt + 1}/{max_retries + 1}), "
                            f"retry dans {current_delay}s: {e}"
                        )

                    # Attendre avant retry
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            # Ne devrait jamais arriver ici
            return None

        return wrapper
    return decorator


def timeout(seconds: float):
    """
    Décorateur pour timeout sur fonction async

    Args:
        seconds: Timeout en secondes

    Returns:
        Décorateur

    Exemple:
    ```python
    @timeout(30.0)
    async def long_operation():
        # Max 30 secondes
        await process()
    ```
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                if DEBUG_ENABLED:
                    logger.error(f"⏱️ Timeout {func.__name__} après {seconds}s")
                raise

        return wrapper
    return decorator

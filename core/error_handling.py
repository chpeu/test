"""
Error Handling Decorators and Utilities

This module provides decorators and utilities for standardized error handling
across the Trade Cursor application.

Key Features:
- @handle_errors: Automatic retry with exponential backoff
- @log_errors: Error logging with context
- @suppress_errors: Silent error handling with fallback
- Async and sync function support
"""

import asyncio
import logging
import functools
from typing import Callable, TypeVar, Optional, Tuple, Type, Any, Union
from datetime import datetime

from core.exceptions import (
    TradeCursorError,
    is_retryable,
    get_retry_delay,
    map_exception,
    NetworkError,
    RateLimitError,
    CircuitBreakerError,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# MAIN ERROR HANDLING DECORATOR
# ============================================================================

def handle_errors(
    *,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None,
    max_retries: int = 3,
    backoff_base: float = 2.0,
    max_backoff: float = 60.0,
    default_value: Any = None,
    log_level: str = "error",
    reraise: bool = True,
    on_retry: Optional[Callable] = None,
    on_failure: Optional[Callable] = None,
):
    """
    Decorator for standardized error handling with retry logic.

    This decorator:
    1. Catches exceptions and categorizes them
    2. Retries retryable exceptions with exponential backoff
    3. Logs errors with full context
    4. Optionally returns default value on failure
    5. Supports both sync and async functions

    Args:
        retry_on: Tuple of exception types to retry on.
                  If None, uses is_retryable() to determine.
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_base: Base for exponential backoff (default: 2.0)
        max_backoff: Maximum backoff time in seconds (default: 60.0)
        default_value: Value to return if all retries fail (if not None, won't reraise)
        log_level: Logging level for errors ('debug', 'info', 'warning', 'error', 'critical')
        reraise: Whether to reraise exception after exhausting retries (default: True)
        on_retry: Callback function called before each retry: on_retry(attempt, exception, delay)
        on_failure: Callback function called after all retries fail: on_failure(exception)

    Returns:
        Decorated function with error handling

    Example:
        >>> @handle_errors(
        ...     retry_on=(NetworkError, RateLimitError),
        ...     max_retries=3,
        ...     log_level="warning"
        ... )
        ... async def fetch_price(symbol: str) -> float:
        ...     return await exchange.get_price(symbol)
        ...
        >>> price = await fetch_price("BTC/USDT")  # Auto-retries on network errors

        >>> @handle_errors(
        ...     max_retries=0,
        ...     default_value=[],
        ...     log_level="error"
        ... )
        ... def get_trade_history() -> list:
        ...     return database.query_trades()
        ...
        >>> trades = get_trade_history()  # Returns [] on error
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Determine if function is async
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                last_exception = None
                func_name = func.__name__

                for attempt in range(max_retries + 1):
                    try:
                        # Execute function
                        result = await func(*args, **kwargs)
                        return result

                    except Exception as e:
                        last_exception = e

                        # Convert to TradeCursorError if needed
                        if not isinstance(e, TradeCursorError):
                            e = map_exception(e)

                        # Determine if we should retry
                        should_retry = False

                        if attempt < max_retries:
                            if retry_on is not None:
                                # Explicit retry list
                                should_retry = isinstance(e, retry_on)
                            else:
                                # Use is_retryable() helper
                                should_retry = is_retryable(e)

                        if should_retry:
                            # Calculate retry delay
                            delay = get_retry_delay(e, attempt, backoff_base)
                            delay = min(delay, max_backoff)

                            # Log retry
                            log_method = getattr(logger, log_level)
                            log_method(
                                f"{func_name} failed (attempt {attempt + 1}/{max_retries + 1}): "
                                f"{type(e).__name__}: {e}. "
                                f"Retrying in {delay:.1f}s...",
                                extra={
                                    'function': func_name,
                                    'attempt': attempt + 1,
                                    'max_retries': max_retries + 1,
                                    'exception_type': type(e).__name__,
                                    'exception_message': str(e),
                                    'retry_delay': delay,
                                    'context': getattr(e, 'context', {}),
                                }
                            )

                            # Callback before retry
                            if on_retry:
                                try:
                                    if asyncio.iscoroutinefunction(on_retry):
                                        await on_retry(attempt + 1, e, delay)
                                    else:
                                        on_retry(attempt + 1, e, delay)
                                except Exception as callback_error:
                                    logger.warning(
                                        f"on_retry callback failed: {callback_error}"
                                    )

                            # Wait before retry
                            await asyncio.sleep(delay)

                        else:
                            # Not retryable or max retries reached
                            log_method = getattr(logger, log_level)
                            log_method(
                                f"{func_name} failed permanently: "
                                f"{type(e).__name__}: {e}",
                                exc_info=True,
                                extra={
                                    'function': func_name,
                                    'exception_type': type(e).__name__,
                                    'exception_message': str(e),
                                    'attempts': attempt + 1,
                                    'context': getattr(e, 'context', {}),
                                }
                            )

                            # Callback on failure
                            if on_failure:
                                try:
                                    if asyncio.iscoroutinefunction(on_failure):
                                        await on_failure(e)
                                    else:
                                        on_failure(e)
                                except Exception as callback_error:
                                    logger.warning(
                                        f"on_failure callback failed: {callback_error}"
                                    )

                            # Return default or reraise
                            if default_value is not None:
                                return default_value
                            if reraise:
                                raise
                            return None

                # All retries exhausted
                if last_exception:
                    logger.error(
                        f"{func_name} failed after {max_retries + 1} attempts",
                        exc_info=True,
                        extra={
                            'function': func_name,
                            'total_attempts': max_retries + 1,
                            'final_exception': type(last_exception).__name__,
                        }
                    )

                    # Callback on failure
                    if on_failure:
                        try:
                            if asyncio.iscoroutinefunction(on_failure):
                                await on_failure(last_exception)
                            else:
                                on_failure(last_exception)
                        except Exception as callback_error:
                            logger.warning(f"on_failure callback failed: {callback_error}")

                    # Return default or reraise
                    if default_value is not None:
                        return default_value
                    if reraise:
                        raise last_exception
                    return None

            return async_wrapper

        else:
            # Synchronous version
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                last_exception = None
                func_name = func.__name__

                for attempt in range(max_retries + 1):
                    try:
                        # Execute function
                        result = func(*args, **kwargs)
                        return result

                    except Exception as e:
                        last_exception = e

                        # Convert to TradeCursorError if needed
                        if not isinstance(e, TradeCursorError):
                            e = map_exception(e)

                        # Determine if we should retry
                        should_retry = False

                        if attempt < max_retries:
                            if retry_on is not None:
                                should_retry = isinstance(e, retry_on)
                            else:
                                should_retry = is_retryable(e)

                        if should_retry:
                            # Calculate retry delay
                            delay = get_retry_delay(e, attempt, backoff_base)
                            delay = min(delay, max_backoff)

                            # Log retry
                            log_method = getattr(logger, log_level)
                            log_method(
                                f"{func_name} failed (attempt {attempt + 1}/{max_retries + 1}): "
                                f"{type(e).__name__}: {e}. "
                                f"Retrying in {delay:.1f}s...",
                                extra={
                                    'function': func_name,
                                    'attempt': attempt + 1,
                                    'exception_type': type(e).__name__,
                                    'context': getattr(e, 'context', {}),
                                }
                            )

                            # Callback before retry
                            if on_retry:
                                try:
                                    on_retry(attempt + 1, e, delay)
                                except Exception as callback_error:
                                    logger.warning(f"on_retry callback failed: {callback_error}")

                            # Wait before retry (sync)
                            import time
                            time.sleep(delay)

                        else:
                            # Not retryable or max retries reached
                            log_method = getattr(logger, log_level)
                            log_method(
                                f"{func_name} failed permanently: {type(e).__name__}: {e}",
                                exc_info=True,
                                extra={
                                    'function': func_name,
                                    'exception_type': type(e).__name__,
                                    'context': getattr(e, 'context', {}),
                                }
                            )

                            # Callback on failure
                            if on_failure:
                                try:
                                    on_failure(e)
                                except Exception as callback_error:
                                    logger.warning(f"on_failure callback failed: {callback_error}")

                            # Return default or reraise
                            if default_value is not None:
                                return default_value
                            if reraise:
                                raise
                            return None

                # All retries exhausted
                if last_exception:
                    logger.error(
                        f"{func_name} failed after {max_retries + 1} attempts",
                        exc_info=True
                    )

                    # Callback on failure
                    if on_failure:
                        try:
                            on_failure(last_exception)
                        except Exception as callback_error:
                            logger.warning(f"on_failure callback failed: {callback_error}")

                    # Return default or reraise
                    if default_value is not None:
                        return default_value
                    if reraise:
                        raise last_exception
                    return None

            return sync_wrapper

    return decorator


# ============================================================================
# SIMPLIFIED DECORATORS
# ============================================================================

def log_errors(
    log_level: str = "error",
    reraise: bool = True,
    include_traceback: bool = True
):
    """
    Simplified decorator that just logs errors without retry.

    Args:
        log_level: Logging level
        reraise: Whether to reraise exception
        include_traceback: Whether to include full traceback

    Example:
        >>> @log_errors(log_level="warning", reraise=False)
        ... def risky_operation():
        ...     # Errors logged but not raised
        ...     pass
    """
    return handle_errors(
        max_retries=0,
        log_level=log_level,
        reraise=reraise
    )


def suppress_errors(default_value: Any = None, log_level: str = "warning"):
    """
    Decorator that suppresses errors and returns default value.

    Useful for non-critical operations that shouldn't crash the app.

    Args:
        default_value: Value to return on error
        log_level: Logging level for errors

    Example:
        >>> @suppress_errors(default_value={})
        ... def get_optional_data():
        ...     # Returns {} if fails
        ...     return risky_api_call()
    """
    return handle_errors(
        max_retries=0,
        default_value=default_value,
        log_level=log_level,
        reraise=False
    )


def retry_on_network_error(max_retries: int = 3):
    """
    Decorator for network operations with automatic retry.

    Retries on: NetworkError, RateLimitError, CircuitBreakerError

    Args:
        max_retries: Maximum retry attempts

    Example:
        >>> @retry_on_network_error(max_retries=5)
        ... async def fetch_from_api():
        ...     return await api.get_data()
    """
    return handle_errors(
        retry_on=(NetworkError, RateLimitError, CircuitBreakerError),
        max_retries=max_retries,
        log_level="warning"
    )


# ============================================================================
# CONTEXT MANAGER FOR ERROR HANDLING
# ============================================================================

class ErrorContext:
    """
    Context manager for error handling with automatic logging.

    Example:
        >>> async with ErrorContext(
        ...     operation="Opening position",
        ...     symbol="BTC/USDT",
        ...     on_error=lambda e: send_alert(f"Failed: {e}")
        ... ):
        ...     await open_position()
    """

    def __init__(
        self,
        operation: str,
        log_level: str = "error",
        reraise: bool = True,
        on_error: Optional[Callable[[Exception], None]] = None,
        **context_data
    ):
        """
        Initialize error context.

        Args:
            operation: Description of operation being performed
            log_level: Logging level for errors
            reraise: Whether to reraise exceptions
            on_error: Callback on error: on_error(exception)
            **context_data: Additional context data for logging
        """
        self.operation = operation
        self.log_level = log_level
        self.reraise = reraise
        self.on_error = on_error
        self.context_data = context_data
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        logger.debug(
            f"Starting: {self.operation}",
            extra={'operation': self.operation, **self.context_data}
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()

        if exc_type is None:
            # Success
            logger.debug(
                f"Completed: {self.operation} (took {duration:.2f}s)",
                extra={
                    'operation': self.operation,
                    'duration': duration,
                    **self.context_data
                }
            )
            return True

        # Error occurred
        if not isinstance(exc_val, TradeCursorError):
            exc_val = map_exception(exc_val)

        log_method = getattr(logger, self.log_level)
        log_method(
            f"Failed: {self.operation} - {type(exc_val).__name__}: {exc_val} "
            f"(took {duration:.2f}s)",
            exc_info=True,
            extra={
                'operation': self.operation,
                'duration': duration,
                'exception_type': type(exc_val).__name__,
                'exception_message': str(exc_val),
                'context': getattr(exc_val, 'context', {}),
                **self.context_data
            }
        )

        # Callback
        if self.on_error:
            try:
                self.on_error(exc_val)
            except Exception as callback_error:
                logger.warning(f"on_error callback failed: {callback_error}")

        # Suppress or reraise
        return not self.reraise

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def safe_gather(*aws, return_exceptions: bool = True, log_errors: bool = True):
    """
    Wrapper around asyncio.gather that logs errors.

    Args:
        *aws: Awaitables to gather
        return_exceptions: Whether to return exceptions instead of raising
        log_errors: Whether to log exceptions

    Returns:
        List of results (or exceptions if return_exceptions=True)

    Example:
        >>> results = await safe_gather(
        ...     fetch_btc_price(),
        ...     fetch_eth_price(),
        ...     fetch_sol_price()
        ... )
    """
    results = await asyncio.gather(*aws, return_exceptions=return_exceptions)

    if log_errors and return_exceptions:
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                if not isinstance(result, TradeCursorError):
                    result = map_exception(result)

                logger.error(
                    f"Task {i} failed: {type(result).__name__}: {result}",
                    extra={
                        'task_index': i,
                        'exception_type': type(result).__name__,
                        'context': getattr(result, 'context', {}),
                    }
                )

    return results


def create_error_logger(name: str, extra_context: Optional[dict] = None):
    """
    Create a logger with automatic context injection.

    Args:
        name: Logger name
        extra_context: Context to add to all log messages

    Returns:
        Configured logger

    Example:
        >>> position_logger = create_error_logger(
        ...     "position_manager",
        ...     extra_context={'component': 'position_management'}
        ... )
        >>> position_logger.error("Position failed", extra={'position_id': 'pos_123'})
    """
    base_logger = logging.getLogger(name)

    class ContextLogger:
        def __init__(self, logger, context):
            self._logger = logger
            self._context = context or {}

        def _log(self, level, msg, *args, **kwargs):
            extra = kwargs.get('extra', {})
            extra.update(self._context)
            kwargs['extra'] = extra
            getattr(self._logger, level)(msg, *args, **kwargs)

        def debug(self, msg, *args, **kwargs):
            self._log('debug', msg, *args, **kwargs)

        def info(self, msg, *args, **kwargs):
            self._log('info', msg, *args, **kwargs)

        def warning(self, msg, *args, **kwargs):
            self._log('warning', msg, *args, **kwargs)

        def error(self, msg, *args, **kwargs):
            self._log('error', msg, *args, **kwargs)

        def critical(self, msg, *args, **kwargs):
            self._log('critical', msg, *args, **kwargs)

    return ContextLogger(base_logger, extra_context)

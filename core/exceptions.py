"""
Custom Exception Hierarchy for Trade Cursor

This module defines a comprehensive exception hierarchy for the trading bot,
replacing broad 'except Exception' patterns with specific, actionable exceptions.

Design Principles:
- All custom exceptions inherit from TradeCursorError
- Exceptions are organized by domain (API, Position, Market, etc.)
- Each exception carries context for debugging and recovery
- Retryable vs non-retryable exceptions are clearly distinguished
"""

from typing import Optional, Dict, Any


# ============================================================================
# BASE EXCEPTION
# ============================================================================

class TradeCursorError(Exception):
    """
    Base exception for all Trade Cursor errors.

    All custom exceptions should inherit from this class.
    This allows catching all application-specific errors with a single except clause.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize exception with message and optional context.

        Args:
            message: Human-readable error description
            context: Additional context (symbol, position_id, etc.)
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


# ============================================================================
# CONFIGURATION ERRORS
# ============================================================================

class ConfigurationError(TradeCursorError):
    """
    Configuration-related errors.

    Raised when:
    - Config file missing or corrupted
    - Required environment variables not set
    - Invalid configuration values
    - Schema validation failures

    Non-retryable: Requires manual intervention
    """
    pass


class ValidationError(ConfigurationError):
    """
    Data validation errors.

    Raised when:
    - Input parameters fail validation
    - Data type mismatches
    - Value out of acceptable range

    Non-retryable: Caller must fix input
    """
    pass


# ============================================================================
# MARKET DATA ERRORS
# ============================================================================

class MarketDataError(TradeCursorError):
    """
    Market data retrieval or processing errors.

    Base class for all market data related issues.
    """
    pass


class PriceDataError(MarketDataError):
    """
    Price data specific errors.

    Raised when:
    - Price is None or invalid
    - Price <= 0
    - Extreme price movements (possible data error)
    - Stale price data

    Potentially retryable: May be temporary WebSocket issue
    """

    def __init__(
        self,
        message: str,
        symbol: Optional[str] = None,
        price: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if symbol:
            context['symbol'] = symbol
        if price is not None:
            context['price'] = price
        super().__init__(message, context)


class IndicatorCalculationError(MarketDataError):
    """
    Technical indicator calculation errors.

    Raised when:
    - Insufficient data for calculation
    - Mathematical errors (division by zero)
    - NaN/Inf values in results

    Retryable: Wait for more data
    """
    pass


class InsufficientDataError(MarketDataError):
    """
    Not enough historical data for analysis.

    Raised when:
    - OHLCV data too short for indicator period
    - Missing candles in historical data

    Retryable: Wait for more data to accumulate
    """

    def __init__(
        self,
        message: str,
        required_periods: Optional[int] = None,
        available_periods: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if required_periods:
            context['required_periods'] = required_periods
        if available_periods:
            context['available_periods'] = available_periods
        super().__init__(message, context)


# ============================================================================
# POSITION MANAGEMENT ERRORS
# ============================================================================

class PositionError(TradeCursorError):
    """
    Position management errors.

    Base class for all position-related issues.
    """
    pass


class PositionAlreadyExistsError(PositionError):
    """
    Attempt to open position when one already exists.

    Raised when:
    - Trying to open second position (single-position mode)
    - Position not properly closed before opening new one

    Non-retryable: Must close existing position first
    """

    def __init__(
        self,
        message: str = "Position already exists",
        existing_position_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if existing_position_id:
            context['existing_position_id'] = existing_position_id
        super().__init__(message, context)


class PositionNotFoundError(PositionError):
    """
    Attempt to access non-existent position.

    Raised when:
    - Position ID doesn't exist in database
    - Position was already closed
    - Invalid position reference

    Non-retryable: Position doesn't exist
    """

    def __init__(
        self,
        message: str = "Position not found",
        position_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if position_id:
            context['position_id'] = position_id
        super().__init__(message, context)


class InvalidPositionStateError(PositionError):
    """
    Position in invalid state for requested operation.

    Raised when:
    - Trying to close already closed position
    - Trying to update cancelled position
    - State transition not allowed

    Non-retryable: Invalid operation for current state
    """

    def __init__(
        self,
        message: str,
        current_state: Optional[str] = None,
        requested_action: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if current_state:
            context['current_state'] = current_state
        if requested_action:
            context['requested_action'] = requested_action
        super().__init__(message, context)


class PositionSizingError(PositionError):
    """
    Position sizing calculation errors.

    Raised when:
    - Calculated size below minimum
    - Size above maximum allowed
    - Insufficient capital
    - Invalid risk parameters

    Non-retryable: Requires parameter adjustment
    """

    def __init__(
        self,
        message: str,
        calculated_size: Optional[float] = None,
        min_size: Optional[float] = None,
        max_size: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if calculated_size:
            context['calculated_size'] = calculated_size
        if min_size:
            context['min_size'] = min_size
        if max_size:
            context['max_size'] = max_size
        super().__init__(message, context)


# ============================================================================
# ORDER EXECUTION ERRORS
# ============================================================================

class OrderExecutionError(TradeCursorError):
    """
    Order execution errors.

    Base class for order-related issues.
    """
    pass


class OrderRejectedError(OrderExecutionError):
    """
    Order rejected by exchange.

    Raised when:
    - Insufficient balance
    - Invalid order parameters
    - Market closed
    - Position limits exceeded

    Potentially retryable: Depends on rejection reason
    """

    def __init__(
        self,
        message: str,
        order_id: Optional[str] = None,
        reason: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if order_id:
            context['order_id'] = order_id
        if reason:
            context['reason'] = reason
        super().__init__(message, context)


class OrderTimeoutError(OrderExecutionError):
    """
    Order execution timeout.

    Raised when:
    - Order not filled within timeout period
    - Exchange not responding
    - Network latency too high

    Retryable: Temporary network issue
    """

    def __init__(
        self,
        message: str = "Order execution timeout",
        timeout_seconds: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if timeout_seconds:
            context['timeout_seconds'] = timeout_seconds
        super().__init__(message, context)


class InsufficientBalanceError(OrderExecutionError):
    """
    Insufficient account balance.

    Raised when:
    - Not enough USDT for order
    - Margin requirement not met
    - Balance reserved for other orders

    Non-retryable: Requires deposit or position closure
    """

    def __init__(
        self,
        message: str = "Insufficient balance",
        required_balance: Optional[float] = None,
        available_balance: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if required_balance:
            context['required_balance'] = required_balance
        if available_balance:
            context['available_balance'] = available_balance
        super().__init__(message, context)


# ============================================================================
# API & NETWORK ERRORS
# ============================================================================

class APIError(TradeCursorError):
    """
    Exchange API errors.

    Base class for API-related issues.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
        endpoint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if status_code:
            context['status_code'] = status_code
        if response:
            context['response'] = response
        if endpoint:
            context['endpoint'] = endpoint
        super().__init__(message, context)


class RateLimitError(APIError):
    """
    API rate limit exceeded.

    Raised when:
    - Too many requests to exchange API
    - Rate limit headers indicate limit reached
    - 429 HTTP status code

    Retryable: Wait and retry with backoff
    """

    def __init__(
        self,
        message: str = "API rate limit exceeded",
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if retry_after:
            context['retry_after_seconds'] = retry_after
        super().__init__(message, context=context)


class AuthenticationError(APIError):
    """
    API authentication failure.

    Raised when:
    - Invalid API key
    - API secret incorrect
    - Token expired
    - Signature mismatch

    Non-retryable: Requires credential update
    """
    pass


class NetworkError(TradeCursorError):
    """
    Network connectivity errors.

    Raised when:
    - Connection timeout
    - DNS resolution failure
    - Socket errors
    - SSL/TLS errors

    Retryable: Temporary network issue
    """
    pass


# ============================================================================
# WEBSOCKET ERRORS
# ============================================================================

class WebSocketError(TradeCursorError):
    """
    WebSocket connection errors.

    Base class for WebSocket-related issues.
    """
    pass


class WebSocketDisconnectedError(WebSocketError):
    """
    WebSocket connection lost.

    Raised when:
    - Connection dropped
    - Server closed connection
    - Network interruption

    Retryable: Reconnect automatically
    """

    def __init__(
        self,
        message: str = "WebSocket disconnected",
        close_code: Optional[int] = None,
        close_reason: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if close_code:
            context['close_code'] = close_code
        if close_reason:
            context['close_reason'] = close_reason
        super().__init__(message, context)


class WebSocketMessageError(WebSocketError):
    """
    Invalid WebSocket message.

    Raised when:
    - Message parsing failed
    - Unexpected message format
    - Missing required fields

    Non-retryable: Log and skip message
    """
    pass


# ============================================================================
# DATABASE ERRORS
# ============================================================================

class DatabaseError(TradeCursorError):
    """
    Database operation errors.

    Base class for database-related issues.
    """
    pass


class DatabaseConnectionError(DatabaseError):
    """
    Database connection failure.

    Raised when:
    - Cannot connect to database
    - Connection pool exhausted
    - Connection timeout

    Retryable: Temporary connection issue
    """
    pass


class DatabaseCorruptionError(DatabaseError):
    """
    Database file corruption detected.

    Raised when:
    - SQLite database corrupted
    - Integrity check failed
    - Cannot read database file

    Potentially recoverable: Restore from backup
    """

    def __init__(
        self,
        message: str = "Database corruption detected",
        db_path: Optional[str] = None,
        backup_available: bool = False,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if db_path:
            context['db_path'] = db_path
        context['backup_available'] = backup_available
        super().__init__(message, context)


class DatabaseIntegrityError(DatabaseError):
    """
    Database integrity constraint violation.

    Raised when:
    - Unique constraint violated
    - Foreign key constraint violated
    - Check constraint failed

    Non-retryable: Data integrity issue
    """
    pass


# ============================================================================
# NOTIFICATION ERRORS
# ============================================================================

class NotificationError(TradeCursorError):
    """
    Notification delivery errors.

    Base class for notification-related issues.
    """
    pass


class TelegramError(NotificationError):
    """
    Telegram bot errors.

    Raised when:
    - Invalid bot token
    - Chat ID not found
    - Message send failed
    - API timeout

    Non-critical: Log and continue (don't block trading)
    """

    def __init__(
        self,
        message: str,
        telegram_error_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if telegram_error_code:
            context['telegram_error_code'] = telegram_error_code
        super().__init__(message, context)


# ============================================================================
# CIRCUIT BREAKER ERRORS
# ============================================================================

class CircuitBreakerError(TradeCursorError):
    """
    Circuit breaker opened (too many failures).

    Raised when:
    - Failure threshold exceeded
    - Circuit in OPEN state
    - System protecting itself from cascade failures

    Retryable: Wait for circuit to close
    """

    def __init__(
        self,
        message: str = "Circuit breaker opened",
        failure_count: Optional[int] = None,
        wait_seconds: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        context = context or {}
        if failure_count:
            context['failure_count'] = failure_count
        if wait_seconds:
            context['wait_seconds'] = wait_seconds
        super().__init__(message, context)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_retryable(exception: Exception) -> bool:
    """
    Determine if an exception is retryable.

    Args:
        exception: The exception to check

    Returns:
        True if the exception is likely temporary and retrying may succeed
    """
    retryable_exceptions = (
        NetworkError,
        RateLimitError,
        OrderTimeoutError,
        WebSocketDisconnectedError,
        DatabaseConnectionError,
        CircuitBreakerError,
        InsufficientDataError,
        PriceDataError,
    )

    return isinstance(exception, retryable_exceptions)


def get_retry_delay(exception: Exception, attempt: int, base: float = 2.0) -> float:
    """
    Calculate retry delay based on exception type and attempt number.

    Args:
        exception: The exception that occurred
        attempt: Current retry attempt (0-based)
        base: Base for exponential backoff

    Returns:
        Delay in seconds before retry
    """
    # Special cases with explicit retry-after
    if isinstance(exception, RateLimitError):
        retry_after = exception.context.get('retry_after_seconds')
        if retry_after:
            return float(retry_after)

    if isinstance(exception, CircuitBreakerError):
        wait_seconds = exception.context.get('wait_seconds')
        if wait_seconds:
            return float(wait_seconds)

    # Exponential backoff: base^attempt (max 60 seconds)
    delay = min(base ** attempt, 60.0)

    return delay


# ============================================================================
# EXCEPTION MAPPING (for converting external exceptions)
# ============================================================================

EXCEPTION_MAPPING = {
    # Network/Connection errors
    ConnectionError: NetworkError,
    TimeoutError: NetworkError,
    OSError: NetworkError,

    # Value errors
    ValueError: ValidationError,
    TypeError: ValidationError,

    # Key errors
    KeyError: ConfigurationError,
}


def map_exception(exception: Exception, message: Optional[str] = None) -> TradeCursorError:
    """
    Map standard Python exception to Trade Cursor exception.

    Args:
        exception: The original exception
        message: Optional custom message (default: use original message)

    Returns:
        Corresponding TradeCursorError subclass
    """
    exc_type = type(exception)

    # If already a TradeCursorError, return as-is
    if isinstance(exception, TradeCursorError):
        return exception

    # Map to custom exception
    custom_exc_class = EXCEPTION_MAPPING.get(exc_type, TradeCursorError)

    msg = message or str(exception)

    return custom_exc_class(msg, context={'original_exception': exc_type.__name__})

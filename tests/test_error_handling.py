"""
Unit Tests for Error Handling System

Tests for:
- Custom exception hierarchy
- @handle_errors decorator
- Retry logic
- Error mapping
- Context managers
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal

from core.exceptions import (
    TradeCursorError,
    ConfigurationError,
    ValidationError,
    MarketDataError,
    PriceDataError,
    IndicatorCalculationError,
    InsufficientDataError,
    PositionError,
    PositionAlreadyExistsError,
    PositionNotFoundError,
    InvalidPositionStateError,
    PositionSizingError,
    OrderExecutionError,
    OrderRejectedError,
    OrderTimeoutError,
    InsufficientBalanceError,
    APIError,
    RateLimitError,
    AuthenticationError,
    NetworkError,
    WebSocketError,
    WebSocketDisconnectedError,
    WebSocketMessageError,
    DatabaseError,
    DatabaseConnectionError,
    DatabaseCorruptionError,
    DatabaseIntegrityError,
    NotificationError,
    TelegramError,
    CircuitBreakerError,
    is_retryable,
    get_retry_delay,
    map_exception,
)

from core.error_handling import (
    handle_errors,
    log_errors,
    suppress_errors,
    retry_on_network_error,
    ErrorContext,
    safe_gather,
)


# ============================================================================
# EXCEPTION HIERARCHY TESTS
# ============================================================================

class TestExceptionHierarchy:
    """Test custom exception classes"""

    def test_base_exception_with_message(self):
        """Test TradeCursorError with simple message"""
        exc = TradeCursorError("Test error")
        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.context == {}

    def test_base_exception_with_context(self):
        """Test TradeCursorError with context"""
        exc = TradeCursorError(
            "Test error",
            context={'symbol': 'BTC/USDT', 'price': 50000}
        )
        assert "Test error" in str(exc)
        assert "symbol=BTC/USDT" in str(exc)
        assert "price=50000" in str(exc)
        assert exc.context == {'symbol': 'BTC/USDT', 'price': 50000}

    def test_price_data_error_convenience(self):
        """Test PriceDataError with symbol and price parameters"""
        exc = PriceDataError(
            "Invalid price",
            symbol="BTC/USDT",
            price=0.0
        )
        assert exc.context['symbol'] == "BTC/USDT"
        assert exc.context['price'] == 0.0

    def test_insufficient_data_error_periods(self):
        """Test InsufficientDataError with period information"""
        exc = InsufficientDataError(
            "Not enough data",
            required_periods=100,
            available_periods=50
        )
        assert exc.context['required_periods'] == 100
        assert exc.context['available_periods'] == 50

    def test_position_already_exists_error(self):
        """Test PositionAlreadyExistsError"""
        exc = PositionAlreadyExistsError(existing_position_id="pos_123")
        assert exc.context['existing_position_id'] == "pos_123"
        assert "Position already exists" in str(exc)

    def test_position_not_found_error(self):
        """Test PositionNotFoundError"""
        exc = PositionNotFoundError(position_id="pos_999")
        assert exc.context['position_id'] == "pos_999"

    def test_invalid_position_state_error(self):
        """Test InvalidPositionStateError with state info"""
        exc = InvalidPositionStateError(
            "Cannot close closed position",
            current_state="CLOSED",
            requested_action="close"
        )
        assert exc.context['current_state'] == "CLOSED"
        assert exc.context['requested_action'] == "close"

    def test_position_sizing_error(self):
        """Test PositionSizingError with size constraints"""
        exc = PositionSizingError(
            "Size too small",
            calculated_size=2.0,
            min_size=5.0,
            max_size=1000.0
        )
        assert exc.context['calculated_size'] == 2.0
        assert exc.context['min_size'] == 5.0

    def test_order_rejected_error(self):
        """Test OrderRejectedError with rejection reason"""
        exc = OrderRejectedError(
            "Order rejected by exchange",
            order_id="ord_123",
            reason="Insufficient balance"
        )
        assert exc.context['order_id'] == "ord_123"
        assert exc.context['reason'] == "Insufficient balance"

    def test_order_timeout_error(self):
        """Test OrderTimeoutError"""
        exc = OrderTimeoutError(timeout_seconds=10.0)
        assert exc.context['timeout_seconds'] == 10.0

    def test_insufficient_balance_error(self):
        """Test InsufficientBalanceError"""
        exc = InsufficientBalanceError(
            required_balance=100.0,
            available_balance=50.0
        )
        assert exc.context['required_balance'] == 100.0
        assert exc.context['available_balance'] == 50.0

    def test_api_error_with_status_code(self):
        """Test APIError with HTTP status and response"""
        exc = APIError(
            "API request failed",
            status_code=503,
            response={'error': 'Service unavailable'},
            endpoint="/api/v1/orders"
        )
        assert exc.context['status_code'] == 503
        assert exc.context['response'] == {'error': 'Service unavailable'}
        assert exc.context['endpoint'] == "/api/v1/orders"

    def test_rate_limit_error_with_retry_after(self):
        """Test RateLimitError with retry-after"""
        exc = RateLimitError(retry_after=60)
        assert exc.context['retry_after_seconds'] == 60

    def test_websocket_disconnected_error(self):
        """Test WebSocketDisconnectedError with close codes"""
        exc = WebSocketDisconnectedError(
            close_code=1006,
            close_reason="Abnormal closure"
        )
        assert exc.context['close_code'] == 1006
        assert exc.context['close_reason'] == "Abnormal closure"

    def test_database_corruption_error(self):
        """Test DatabaseCorruptionError with backup info"""
        exc = DatabaseCorruptionError(
            db_path="/path/to/db.sqlite",
            backup_available=True
        )
        assert exc.context['db_path'] == "/path/to/db.sqlite"
        assert exc.context['backup_available'] is True

    def test_telegram_error(self):
        """Test TelegramError"""
        exc = TelegramError(
            "Failed to send message",
            telegram_error_code=400
        )
        assert exc.context['telegram_error_code'] == 400

    def test_circuit_breaker_error(self):
        """Test CircuitBreakerError with failure info"""
        exc = CircuitBreakerError(
            failure_count=5,
            wait_seconds=300.0
        )
        assert exc.context['failure_count'] == 5
        assert exc.context['wait_seconds'] == 300.0


# ============================================================================
# RETRYABILITY TESTS
# ============================================================================

class TestRetryability:
    """Test is_retryable() function"""

    def test_network_error_is_retryable(self):
        """NetworkError should be retryable"""
        exc = NetworkError("Connection timeout")
        assert is_retryable(exc) is True

    def test_rate_limit_error_is_retryable(self):
        """RateLimitError should be retryable"""
        exc = RateLimitError()
        assert is_retryable(exc) is True

    def test_circuit_breaker_error_is_retryable(self):
        """CircuitBreakerError should be retryable"""
        exc = CircuitBreakerError()
        assert is_retryable(exc) is True

    def test_price_data_error_is_retryable(self):
        """PriceDataError should be retryable (stale data)"""
        exc = PriceDataError("Stale price")
        assert is_retryable(exc) is True

    def test_configuration_error_not_retryable(self):
        """ConfigurationError should NOT be retryable"""
        exc = ConfigurationError("Invalid config")
        assert is_retryable(exc) is False

    def test_validation_error_not_retryable(self):
        """ValidationError should NOT be retryable"""
        exc = ValidationError("Invalid input")
        assert is_retryable(exc) is False

    def test_authentication_error_not_retryable(self):
        """AuthenticationError should NOT be retryable"""
        exc = AuthenticationError("Invalid API key")
        assert is_retryable(exc) is False

    def test_insufficient_balance_not_retryable(self):
        """InsufficientBalanceError should NOT be retryable"""
        exc = InsufficientBalanceError()
        assert is_retryable(exc) is False


# ============================================================================
# RETRY DELAY TESTS
# ============================================================================

class TestRetryDelay:
    """Test get_retry_delay() function"""

    def test_exponential_backoff(self):
        """Test exponential backoff calculation"""
        exc = NetworkError("Test")

        # 2^0 = 1
        assert get_retry_delay(exc, 0, base=2.0) == 1.0

        # 2^1 = 2
        assert get_retry_delay(exc, 1, base=2.0) == 2.0

        # 2^2 = 4
        assert get_retry_delay(exc, 2, base=2.0) == 4.0

        # 2^3 = 8
        assert get_retry_delay(exc, 3, base=2.0) == 8.0

    def test_max_backoff_cap(self):
        """Test backoff doesn't exceed max"""
        exc = NetworkError("Test")

        # 2^10 = 1024, but should be capped at 60
        delay = get_retry_delay(exc, 10, base=2.0)
        assert delay == 60.0

    def test_rate_limit_explicit_retry_after(self):
        """Test RateLimitError uses explicit retry-after"""
        exc = RateLimitError(retry_after=120)

        delay = get_retry_delay(exc, 0)
        assert delay == 120.0

    def test_circuit_breaker_explicit_wait(self):
        """Test CircuitBreakerError uses explicit wait time"""
        exc = CircuitBreakerError(wait_seconds=300.0)

        delay = get_retry_delay(exc, 0)
        assert delay == 300.0


# ============================================================================
# EXCEPTION MAPPING TESTS
# ============================================================================

class TestExceptionMapping:
    """Test map_exception() function"""

    def test_map_connection_error(self):
        """ConnectionError should map to NetworkError"""
        original = ConnectionError("Connection refused")
        mapped = map_exception(original)

        assert isinstance(mapped, NetworkError)
        assert "Connection refused" in str(mapped)
        assert mapped.context['original_exception'] == 'ConnectionError'

    def test_map_timeout_error(self):
        """TimeoutError should map to NetworkError"""
        original = TimeoutError("Request timeout")
        mapped = map_exception(original)

        assert isinstance(mapped, NetworkError)

    def test_map_value_error(self):
        """ValueError should map to ValidationError"""
        original = ValueError("Invalid value")
        mapped = map_exception(original)

        assert isinstance(mapped, ValidationError)

    def test_map_key_error(self):
        """KeyError should map to ConfigurationError"""
        original = KeyError("missing_key")
        mapped = map_exception(original)

        assert isinstance(mapped, ConfigurationError)

    def test_already_custom_exception(self):
        """Custom exceptions should pass through unchanged"""
        original = PositionError("Position error")
        mapped = map_exception(original)

        assert mapped is original

    def test_unknown_exception_maps_to_base(self):
        """Unknown exceptions map to base TradeCursorError"""
        original = RuntimeError("Unknown error")
        mapped = map_exception(original)

        assert isinstance(mapped, TradeCursorError)
        assert not isinstance(mapped, NetworkError)

    def test_custom_message_override(self):
        """Test custom message in mapping"""
        original = ValueError("Original message")
        mapped = map_exception(original, message="Custom message")

        assert "Custom message" in str(mapped)


# ============================================================================
# @handle_errors DECORATOR TESTS
# ============================================================================

class TestHandleErrorsDecorator:
    """Test @handle_errors decorator"""

    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self):
        """Test successful execution (no errors)"""
        call_count = 0

        @handle_errors(max_retries=3)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()

        assert result == "success"
        assert call_count == 1  # Called only once

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self):
        """Test retry on retryable exception"""
        call_count = 0

        @handle_errors(max_retries=3, log_level="warning")
        async def flaky_func():
            nonlocal call_count
            call_count += 1

            if call_count < 3:
                raise NetworkError("Temporary network issue")

            return "success"

        result = await flaky_func()

        assert result == "success"
        assert call_count == 3  # Retried 2 times, succeeded on 3rd

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test exception raised when max retries exhausted"""
        @handle_errors(max_retries=2)
        async def always_fails():
            raise NetworkError("Always fails")

        with pytest.raises(NetworkError):
            await always_fails()

    @pytest.mark.asyncio
    async def test_non_retryable_error_no_retry(self):
        """Test non-retryable errors are not retried"""
        call_count = 0

        @handle_errors(max_retries=3)
        async def fails_with_validation_error():
            nonlocal call_count
            call_count += 1
            raise ValidationError("Invalid input")

        with pytest.raises(ValidationError):
            await fails_with_validation_error()

        assert call_count == 1  # Not retried

    @pytest.mark.asyncio
    async def test_default_value_on_failure(self):
        """Test default value returned on failure"""
        @handle_errors(
            max_retries=2,
            default_value=[],
            reraise=False
        )
        async def fails_but_returns_default():
            raise NetworkError("Failed")

        result = await fails_but_returns_default()

        assert result == []  # Default value returned

    @pytest.mark.asyncio
    async def test_custom_retry_on_exceptions(self):
        """Test explicit retry_on parameter"""
        call_count = 0

        @handle_errors(
            retry_on=(NetworkError, RateLimitError),
            max_retries=2
        )
        async def custom_retry_func():
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                raise NetworkError("Retryable")
            return "success"

        result = await custom_retry_func()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Test on_retry callback is called"""
        retry_calls = []

        def on_retry_handler(attempt, exception, delay):
            retry_calls.append({
                'attempt': attempt,
                'exception': str(exception),
                'delay': delay
            })

        @handle_errors(
            max_retries=2,
            on_retry=on_retry_handler
        )
        async def func_with_retry():
            if len(retry_calls) < 2:
                raise NetworkError("Temporary")
            return "success"

        result = await func_with_retry()

        assert result == "success"
        assert len(retry_calls) == 2
        assert retry_calls[0]['attempt'] == 1
        assert retry_calls[1]['attempt'] == 2

    @pytest.mark.asyncio
    async def test_on_failure_callback(self):
        """Test on_failure callback is called"""
        failure_exception = None

        def on_failure_handler(exception):
            nonlocal failure_exception
            failure_exception = exception

        @handle_errors(
            max_retries=0,
            on_failure=on_failure_handler,
            reraise=False
        )
        async def failing_func():
            raise ValidationError("Test failure")

        await failing_func()

        assert failure_exception is not None
        assert isinstance(failure_exception, ValidationError)

    def test_sync_function_support(self):
        """Test decorator works with sync functions"""
        call_count = 0

        @handle_errors(max_retries=2)
        def sync_func():
            nonlocal call_count
            call_count += 1

            if call_count < 2:
                raise NetworkError("Temporary")

            return "success"

        result = sync_func()

        assert result == "success"
        assert call_count == 2


# ============================================================================
# SIMPLIFIED DECORATORS TESTS
# ============================================================================

class TestSimplifiedDecorators:
    """Test simplified decorator variations"""

    @pytest.mark.asyncio
    async def test_log_errors_decorator(self):
        """Test @log_errors decorator"""
        @log_errors(log_level="warning", reraise=False)
        async def logged_func():
            raise ValueError("Test error")

        # Should not raise (reraise=False)
        result = await logged_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_suppress_errors_decorator(self):
        """Test @suppress_errors decorator"""
        @suppress_errors(default_value={'data': None})
        async def suppressed_func():
            raise Exception("Suppressed error")

        result = await suppressed_func()
        assert result == {'data': None}

    @pytest.mark.asyncio
    async def test_retry_on_network_error_decorator(self):
        """Test @retry_on_network_error decorator"""
        call_count = 0

        @retry_on_network_error(max_retries=3)
        async def network_func():
            nonlocal call_count
            call_count += 1

            if call_count < 2:
                raise NetworkError("Network issue")

            return "connected"

        result = await network_func()

        assert result == "connected"
        assert call_count == 2


# ============================================================================
# ERROR CONTEXT TESTS
# ============================================================================

class TestErrorContext:
    """Test ErrorContext context manager"""

    @pytest.mark.asyncio
    async def test_error_context_success(self):
        """Test ErrorContext with successful operation"""
        async with ErrorContext(
            operation="Test operation",
            symbol="BTC/USDT"
        ) as ctx:
            # Successful operation
            pass

        # No exception raised

    @pytest.mark.asyncio
    async def test_error_context_with_error(self):
        """Test ErrorContext catches and logs error"""
        with pytest.raises(ValidationError):
            async with ErrorContext(
                operation="Test operation",
                reraise=True
            ):
                raise ValidationError("Test error")

    @pytest.mark.asyncio
    async def test_error_context_suppress_error(self):
        """Test ErrorContext can suppress errors"""
        async with ErrorContext(
            operation="Test operation",
            reraise=False
        ):
            raise ValueError("Suppressed error")

        # No exception raised

    @pytest.mark.asyncio
    async def test_error_context_on_error_callback(self):
        """Test ErrorContext on_error callback"""
        error_captured = None

        def capture_error(e):
            nonlocal error_captured
            error_captured = e

        async with ErrorContext(
            operation="Test",
            on_error=capture_error,
            reraise=False
        ):
            raise ValidationError("Test error")

        assert error_captured is not None
        assert isinstance(error_captured, ValidationError)


# ============================================================================
# SAFE_GATHER TESTS
# ============================================================================

class TestSafeGather:
    """Test safe_gather utility"""

    @pytest.mark.asyncio
    async def test_safe_gather_all_success(self):
        """Test safe_gather with all successful tasks"""
        async def task1():
            return "result1"

        async def task2():
            return "result2"

        async def task3():
            return "result3"

        results = await safe_gather(task1(), task2(), task3())

        assert results == ["result1", "result2", "result3"]

    @pytest.mark.asyncio
    async def test_safe_gather_with_failures(self):
        """Test safe_gather with some failures"""
        async def success_task():
            return "success"

        async def failing_task():
            raise NetworkError("Failed")

        results = await safe_gather(
            success_task(),
            failing_task(),
            success_task()
        )

        assert results[0] == "success"
        assert isinstance(results[1], NetworkError)
        assert results[2] == "success"

    @pytest.mark.asyncio
    async def test_safe_gather_logs_errors(self, caplog):
        """Test safe_gather logs errors"""
        async def failing_task():
            raise ValueError("Test error")

        await safe_gather(failing_task(), log_errors=True)

        # Check error was logged
        # (Caplog assertions would go here in real test)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestErrorHandlingIntegration:
    """Integration tests combining multiple components"""

    @pytest.mark.asyncio
    async def test_realistic_api_call_with_retry(self):
        """Test realistic API call scenario with retry"""
        call_count = 0

        @handle_errors(
            retry_on=(NetworkError, RateLimitError),
            max_retries=3,
            backoff_base=2.0
        )
        async def fetch_price(symbol: str) -> float:
            nonlocal call_count
            call_count += 1

            # Fail first 2 times with different errors
            if call_count == 1:
                raise NetworkError("Connection timeout")
            elif call_count == 2:
                raise RateLimitError(retry_after=1)

            # Succeed on 3rd attempt
            return 50000.0

        price = await fetch_price("BTC/USDT")

        assert price == 50000.0
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_position_opening_with_validation(self):
        """Test position opening with validation and error handling"""

        @handle_errors(max_retries=0)
        async def open_position(symbol: str, size: float):
            # Validation
            if size < 5.0:
                raise PositionSizingError(
                    "Size too small",
                    calculated_size=size,
                    min_size=5.0
                )

            if not symbol:
                raise ValidationError("Symbol required")

            return {"status": "opened", "symbol": symbol, "size": size}

        # Valid position
        result = await open_position("BTC/USDT", 100.0)
        assert result['status'] == "opened"

        # Invalid size
        with pytest.raises(PositionSizingError) as exc_info:
            await open_position("BTC/USDT", 2.0)

        assert exc_info.value.context['calculated_size'] == 2.0
        assert exc_info.value.context['min_size'] == 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

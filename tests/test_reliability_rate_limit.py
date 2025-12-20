
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from tenacity import RetryError
from api.reliability import fetch_with_retry, AdaptiveCircuitBreaker, RateLimitError
from ccxt.base.errors import ExchangeError

@pytest.mark.asyncio
async def test_fetch_with_retry_converts_exchange_error_510():
    """Test que fetch_with_retry convertit ExchangeError 510 en RateLimitError"""
    
    # Mock fonction qui lève ExchangeError 510
    mock_func = AsyncMock(side_effect=ExchangeError('mexc {"success":false,"code":510,"message":"Requests are too frequent"}'))
    
    # Patcher DEBUG_ENABLED pour s'assurer que les logs passent
    with patch('api.reliability.DEBUG_ENABLED', True):
        # Doit lever RetryError (tenacity) contenant RateLimitError
        with pytest.raises(RetryError) as excinfo:
            await fetch_with_retry(mock_func)
        
        # Vérifier que la cause finale est bien notre RateLimitError convertie
        last_exception = excinfo.value.last_attempt.exception()
        assert isinstance(last_exception, RateLimitError)
        assert "Exchange Rate Limit" in str(last_exception)

@pytest.mark.asyncio
async def test_circuit_breaker_handles_exchange_error_510():
    """Test que le Circuit Breaker gère ExchangeError 510 comme WARNING"""
    
    cb = AdaptiveCircuitBreaker()
    
    # Mock l'objet circuit breaker interne pour éviter le bug de pybreaker 'gen' not defined
    cb._circuit_breaker = Mock()
    async def mock_call_async(func, *args, **kwargs):
        return await func(*args, **kwargs)
    cb._circuit_breaker.call_async = AsyncMock(side_effect=mock_call_async)
    
    mock_func = AsyncMock(side_effect=ExchangeError('mexc {"success":false,"code":510,"message":"Requests are too frequent"}'))
    
    # Mock logger pour vérifier qu'on n'a pas d'ERROR
    with patch('api.reliability.logger') as mock_logger, \
         patch('api.reliability.DEBUG_ENABLED', True):
        
        # Should raise RateLimitError (converted from ExchangeError)
        with pytest.raises(RateLimitError):
            await cb.call_async(mock_func)
            
        # Vérifier qu'on a un WARNING et pas un ERROR
        assert mock_logger.warning.called
        assert not mock_logger.error.called
        
        args, _ = mock_logger.warning.call_args
        # Circuit breaker should log "Rate limit atteint" for RateLimitError
        assert "Rate limit atteint" in args[0]

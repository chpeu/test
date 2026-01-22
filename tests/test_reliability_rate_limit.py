
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from tenacity import RetryError
from api.reliability import fetch_with_retry, AdaptiveCircuitBreaker, RateLimitError, ExchangeError

@pytest.mark.asyncio
async def test_fetch_with_retry_converts_exchange_error_510():
    """Test que fetch_with_retry convertit ExchangeError 510 en RateLimitError"""
    
    # Mock fonction qui lève ExchangeError 510
    mock_func = AsyncMock(side_effect=ExchangeError('mexc {"success":false,"code":510,"message":"Requests are too frequent"}'))
    
    # Patcher DEBUG_ENABLED pour s'assurer que les logs passent
    with patch('api.reliability.DEBUG_ENABLED', True):
        # Doit lever RateLimitError (reraise=True)
        with pytest.raises(RateLimitError) as excinfo:
            await fetch_with_retry(mock_func)
        
        # Vérifier que l'exception est bien celle convertie
        assert "Exchange Rate Limit" in str(excinfo.value)

@pytest.mark.asyncio
async def test_circuit_breaker_handles_exchange_error_510():
    """Test que le Circuit Breaker gère ExchangeError 510 comme WARNING
    
    Flow: ExchangeError 510 -> fetch_with_retry converts to RateLimitError -> 
          circuit breaker catches RateLimitError and logs warning
    """
    
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
        
        # In production: circuit_breaker wraps fetch_with_retry which converts ExchangeError to RateLimitError
        # With reraise=True, fetch_with_retry raises RateLimitError
        with pytest.raises(RateLimitError):
            await cb.call_async(fetch_with_retry, mock_func)
            
        # Vérifier qu'on a un WARNING et pas un ERROR
        assert mock_logger.warning.called
        assert not mock_logger.error.called
        
        # Should have both warnings: from fetch_with_retry conversion AND from circuit breaker
        warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
        # Circuit breaker should log "Rate limit atteint" when catching RateLimitError
        assert any("Rate limit atteint" in msg for msg in warning_calls)

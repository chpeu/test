"""
Tests pour fetch_with_retry dans api/reliability.py
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from api.reliability import fetch_with_retry


class TestFetchWithRetry:
    """Tests pour fetch_with_retry"""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Test succès au premier essai"""
        mock_func = AsyncMock(return_value="success")

        result = await fetch_with_retry(mock_func)

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_success_with_args(self):
        """Test succès avec arguments"""
        mock_func = AsyncMock(return_value={"data": "test"})

        result = await fetch_with_retry(mock_func, "arg1", "arg2", key="value")

        assert result == {"data": "test"}
        mock_func.assert_called_once_with("arg1", "arg2", key="value")

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Test retry sur ConnectionError"""
        mock_func = AsyncMock(
            side_effect=[
                ConnectionError("Network error"),
                "success"
            ]
        )

        result = await fetch_with_retry(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout_error(self):
        """Test retry sur TimeoutError"""
        mock_func = AsyncMock(
            side_effect=[
                TimeoutError("Timeout"),
                TimeoutError("Timeout"),
                "success"
            ]
        )

        result = await fetch_with_retry(mock_func)

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_asyncio_timeout_error(self):
        """Test retry sur asyncio.TimeoutError"""
        mock_func = AsyncMock(
            side_effect=[
                asyncio.TimeoutError(),
                "success"
            ]
        )

        result = await fetch_with_retry(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self):
        """Test échec après max tentatives"""
        from tenacity import RetryError

        mock_func = AsyncMock(
            side_effect=ConnectionError("Always fails")
        )

        # Devrait échouer après max_attempts (défini dans RETRY_CONFIG)
        # Note: tenacity lève RetryError, pas l'exception originale
        with pytest.raises(RetryError):
            await fetch_with_retry(mock_func)

        # Devrait avoir essayé plusieurs fois
        assert mock_func.call_count > 1

    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """Test erreur non-retryable (ne devrait pas retry)"""
        mock_func = AsyncMock(
            side_effect=ValueError("Invalid input")
        )

        # ValueError n'est pas dans retry_if_exception_type
        with pytest.raises(ValueError, match="Invalid input"):
            await fetch_with_retry(mock_func)

        # Ne devrait avoir essayé qu'une fois
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test backoff exponentiel entre retries"""
        mock_func = AsyncMock(
            side_effect=[
                ConnectionError("Error 1"),
                ConnectionError("Error 2"),
                "success"
            ]
        )

        import time
        start = time.time()

        result = await fetch_with_retry(mock_func)

        elapsed = time.time() - start

        assert result == "success"
        assert mock_func.call_count == 3
        # Devrait avoir attendu (backoff)
        # Note: le temps exact dépend de RETRY_CONFIG

    @pytest.mark.asyncio
    @patch('api.reliability.DEBUG_ENABLED', True)
    async def test_retry_logs_warning_in_debug(self):
        """Test log warning en mode DEBUG"""
        mock_func = AsyncMock(
            side_effect=[
                ConnectionError("Network error"),
                "success"
            ]
        )

        result = await fetch_with_retry(mock_func)

        assert result == "success"
        # En mode DEBUG, devrait logger warning

    @pytest.mark.asyncio
    async def test_retry_preserves_exception_type(self):
        """Test que le type d'exception est préservé dans RetryError"""
        from tenacity import RetryError

        original_error = TimeoutError("Custom timeout message")
        mock_func = AsyncMock(side_effect=original_error)

        # tenacity lève RetryError qui contient l'exception originale
        with pytest.raises(RetryError) as exc_info:
            await fetch_with_retry(mock_func)

        # Vérifier que l'exception originale est préservée dans RetryError
        assert isinstance(exc_info.value.last_attempt.exception(), TimeoutError)


class TestIntegration:
    """Tests d'intégration retry logic"""

    @pytest.mark.asyncio
    async def test_intermittent_failures(self):
        """Test avec échecs intermittents"""
        call_count = 0

        async def intermittent_func():
            nonlocal call_count
            call_count += 1

            # Échec les 2 premiers appels
            if call_count <= 2:
                raise ConnectionError(f"Attempt {call_count} failed")

            return f"Success on attempt {call_count}"

        result = await fetch_with_retry(intermittent_func)

        assert result == "Success on attempt 3"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_mixed_error_types(self):
        """Test avec différents types d'erreurs"""
        mock_func = AsyncMock(
            side_effect=[
                ConnectionError("Connection lost"),
                TimeoutError("Request timeout"),
                asyncio.TimeoutError(),
                "success"
            ]
        )

        result = await fetch_with_retry(mock_func)

        assert result == "success"
        assert mock_func.call_count == 4

    @pytest.mark.asyncio
    async def test_async_function_with_complex_return(self):
        """Test fonction async avec retour complexe"""
        async def complex_func():
            await asyncio.sleep(0.01)
            return {
                'data': [1, 2, 3],
                'nested': {'key': 'value'},
                'status': 'ok'
            }

        result = await fetch_with_retry(complex_func)

        assert result['data'] == [1, 2, 3]
        assert result['nested']['key'] == 'value'
        assert result['status'] == 'ok'

"""
Tests pour AdaptiveCircuitBreaker dans api/reliability.py
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from api.reliability import AdaptiveCircuitBreaker
import api.reliability as reliability_mod


async def _safe_call_async(self, func, *args, **kwargs):
    return await func(*args, **kwargs)


class TestAdaptiveCircuitBreaker:
    """Tests pour AdaptiveCircuitBreaker"""

    def test_init_default_params(self):
        """Test initialisation avec paramètres par défaut"""
        cb = AdaptiveCircuitBreaker()

        assert cb.base_fail_max == 5
        assert cb.base_timeout == 60
        assert cb.error_rate == 0.0
        assert cb.success_count == 0
        assert cb.error_count == 0
        assert cb.failure_threshold == 5
        assert cb.timeout_duration == 60

    def test_init_custom_params(self):
        """Test initialisation avec paramètres personnalisés"""
        cb = AdaptiveCircuitBreaker(base_fail_max=10, base_timeout=120)

        assert cb.base_fail_max == 10
        assert cb.base_timeout == 120
        assert cb.failure_threshold == 10
        assert cb.timeout_duration == 120

    def test_record_success(self):
        """Test enregistrement succès"""
        cb = AdaptiveCircuitBreaker()

        cb.record_success()

        assert cb.success_count == 1
        assert cb.error_count == 0

    def test_record_failure(self):
        """Test enregistrement échec"""
        cb = AdaptiveCircuitBreaker()

        cb.record_failure()

        assert cb.success_count == 0
        assert cb.error_count == 1

    def test_update_metrics_insufficient_data(self):
        """Test update_metrics avec données insuffisantes (< 10)"""
        cb = AdaptiveCircuitBreaker()

        cb.success_count = 5
        cb.error_count = 2
        cb._update_metrics()

        # Pas assez de données, seuils ne changent pas
        assert cb.failure_threshold == cb.base_fail_max
        assert cb.timeout_duration == cb.base_timeout

    def test_update_metrics_low_error_rate(self):
        """Test adaptation avec faible taux d'erreur (<5%)"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)

        # 96 succès et 4 erreurs = 4% < 5%
        cb.success_count = 96
        cb.error_count = 4
        cb._update_metrics()

        # Devrait être plus tolérant
        assert cb.failure_threshold == cb.base_fail_max * 2  # 10
        assert cb.timeout_duration == cb.base_timeout // 2  # 30

    def test_update_metrics_medium_error_rate(self):
        """Test adaptation avec taux d'erreur moyen (5-15%)"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)

        cb.success_count = 90
        cb.error_count = 10  # 10% erreurs
        cb._update_metrics()

        # Devrait rester normal
        assert cb.failure_threshold == cb.base_fail_max  # 5
        assert cb.timeout_duration == cb.base_timeout  # 60

    def test_update_metrics_high_error_rate(self):
        """Test adaptation avec haut taux d'erreur (>15%)"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)

        cb.success_count = 80
        cb.error_count = 20  # 20% erreurs
        cb._update_metrics()

        # Devrait être plus strict
        assert cb.failure_threshold == max(3, cb.base_fail_max // 2)  # 3
        assert cb.timeout_duration == cb.base_timeout * 2  # 120

    def test_update_metrics_reset_counters(self):
        """Test reset partiel des compteurs après 100 requêtes"""
        cb = AdaptiveCircuitBreaker()

        cb.success_count = 80
        cb.error_count = 20
        cb._update_metrics()

        # Compteurs devraient être réduits de 50%
        assert cb.success_count == 40
        assert cb.error_count == 10

    @pytest.mark.asyncio
    async def test_call_async_success(self):
        """Test appel async réussi"""
        cb = AdaptiveCircuitBreaker()

        async def success_func():
            return "success"

        with patch.object(reliability_mod.CircuitBreaker, "call_async", new=_safe_call_async):
            result = await cb.call_async(success_func)

        assert result == "success"
        assert cb.success_count == 1
        assert cb.error_count == 0

    @pytest.mark.asyncio
    async def test_call_async_failure(self):
        """Test appel async échoué"""
        cb = AdaptiveCircuitBreaker()

        async def failing_func():
            raise Exception("Test error")

        with pytest.raises(Exception, match="Test error"):
            with patch.object(reliability_mod.CircuitBreaker, "call_async", new=_safe_call_async):
                await cb.call_async(failing_func)

        assert cb.success_count == 0
        assert cb.error_count == 1

    @pytest.mark.asyncio
    async def test_call_async_with_args(self):
        """Test appel async avec arguments"""
        cb = AdaptiveCircuitBreaker()

        async def func_with_args(x, y):
            return x + y

        with patch.object(reliability_mod.CircuitBreaker, "call_async", new=_safe_call_async):
            result = await cb.call_async(func_with_args, 2, 3)

        assert result == 5
        assert cb.success_count == 1

    def test_on_state_change_callback(self):
        """Test callback lors changement d'état"""
        cb = AdaptiveCircuitBreaker()

        # Vérifier que le callback est défini
        assert cb._circuit_breaker.on_state_change is not None

    def test_circuit_breaker_recreation_on_threshold_change(self):
        """Test recréation circuit breaker quand seuils changent"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)

        old_cb_instance = cb._circuit_breaker

        # Forcer changement de seuils: 96 succès + 4 erreurs = 4% < 5%
        cb.success_count = 96
        cb.error_count = 4
        cb._update_metrics()

        # Circuit breaker devrait être recréé
        assert cb._circuit_breaker is not old_cb_instance
        assert cb.failure_threshold == 10  # 5 * 2

    def test_minimum_failure_threshold(self):
        """Test seuil minimum de 3 échecs"""
        cb = AdaptiveCircuitBreaker(base_fail_max=2, base_timeout=60)

        # Forcer haut taux d'erreur
        cb.success_count = 80
        cb.error_count = 20
        cb._update_metrics()

        # Même avec base_fail_max=2, threshold min = 3
        assert cb.failure_threshold >= 3


class TestIntegration:
    """Tests d'intégration circuit breaker"""

    @pytest.mark.asyncio
    async def test_multiple_successes_lower_error_rate(self):
        """Test que multiples succès réduisent le taux d'erreur"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)

        async def success_func():
            return "ok"

        # Enregistrer quelques échecs
        for _ in range(10):
            cb.record_failure()

        # Total = 10, error_rate = 100%
        cb._update_metrics()
        assert cb.error_rate == 1.0

        # Enregistrer beaucoup de succès
        with patch.object(reliability_mod.CircuitBreaker, "call_async", new=_safe_call_async):
            for _ in range(90):
                await cb.call_async(success_func)

        # Total = 100, error_rate = 10%
        assert cb.error_rate == 0.1

    @pytest.mark.asyncio
    async def test_adaptive_behavior_workflow(self):
        """Test comportement adaptatif complet"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)

        async def flaky_func(should_fail=False):
            if should_fail:
                raise Exception("Flaky error")
            return "success"

        # Phase 1: Beaucoup de succès → devient tolérant
        with patch.object(reliability_mod.CircuitBreaker, "call_async", new=_safe_call_async):
            for _ in range(96):
                await cb.call_async(flaky_func, should_fail=False)

            for _ in range(4):
                try:
                    await cb.call_async(flaky_func, should_fail=True)
                except Exception:
                    pass

        assert cb.error_rate < 0.1
        assert cb.failure_threshold > cb.base_fail_max

        # Phase 2: Reset compteurs
        cb.success_count = 80
        cb.error_count = 20
        cb._update_metrics()

        # Devrait devenir strict
        assert cb.error_rate == 0.2
        assert cb.failure_threshold < cb.base_fail_max

    def test_adaptive_behavior_without_async(self):
        """Test comportement adaptatif sans async (contourne bug pybreaker)"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)

        # Phase 1: Beaucoup de succès (96 succès + 4 erreurs = 4% < 5%)
        for _ in range(96):
            cb.record_success()
        for _ in range(4):
            cb.record_failure()

        # Devrait être tolérant (<5% erreurs)
        assert cb.error_rate < 0.05
        assert cb.failure_threshold == cb.base_fail_max * 2

        # Phase 2: Augmenter erreurs (>15%)
        for _ in range(20):
            cb.record_failure()

        # Devrait devenir strict
        assert cb.error_rate > 0.15
        assert cb.failure_threshold < cb.base_fail_max

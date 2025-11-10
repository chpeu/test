"""
Tests pour core/scheduler.py
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from core.scheduler import Scheduler


class TestScheduler:
    """Tests pour Scheduler"""

    def test_init(self):
        """Test initialisation"""
        scheduler = Scheduler()
        assert scheduler.scanner_task is None
        assert scheduler.position_check_task is None
        assert scheduler.scalability_refresh_task is None
        assert scheduler.is_running is False
        assert scheduler.scanner_callback is None
        assert scheduler.position_check_callback is None
        assert scheduler.scalability_refresh_callback is None

    def test_set_scanner_callback(self):
        """Test définition callback scanner"""
        scheduler = Scheduler()
        callback = AsyncMock()
        scheduler.set_scanner_callback(callback)
        assert scheduler.scanner_callback == callback

    def test_set_position_check_callback(self):
        """Test définition callback position check"""
        scheduler = Scheduler()
        callback = AsyncMock()
        scheduler.set_position_check_callback(callback)
        assert scheduler.position_check_callback == callback

    def test_set_scalability_refresh_callback(self):
        """Test définition callback scalability refresh"""
        scheduler = Scheduler()
        callback = AsyncMock()
        scheduler.set_scalability_refresh_callback(callback)
        assert scheduler.scalability_refresh_callback == callback

    @pytest.mark.asyncio
    async def test_start_with_callbacks(self):
        """Test démarrage avec callbacks"""
        scheduler = Scheduler()

        scanner_callback = AsyncMock()
        position_callback = AsyncMock()
        scalability_callback = AsyncMock()

        scheduler.set_scanner_callback(scanner_callback)
        scheduler.set_position_check_callback(position_callback)
        scheduler.set_scalability_refresh_callback(scalability_callback)

        scheduler.start()

        assert scheduler.is_running is True
        assert scheduler.scanner_task is not None
        assert scheduler.position_check_task is not None
        assert scheduler.scalability_refresh_task is not None

        # Cleanup
        scheduler.stop()
        await asyncio.sleep(0.1)

    def test_start_already_running(self):
        """Test démarrage quand déjà démarré"""
        scheduler = Scheduler()
        scheduler.is_running = True

        # Ne devrait pas créer de nouvelles tâches
        scheduler.start()

        assert scheduler.scanner_task is None
        assert scheduler.position_check_task is None
        assert scheduler.scalability_refresh_task is None

    def test_start_without_callbacks(self):
        """Test démarrage sans callbacks"""
        scheduler = Scheduler()

        scheduler.start()

        assert scheduler.is_running is True
        # Les tâches ne devraient pas être créées sans callbacks
        assert scheduler.scanner_task is None
        assert scheduler.position_check_task is None
        assert scheduler.scalability_refresh_task is None

        scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test arrêt scheduler"""
        scheduler = Scheduler()

        scanner_callback = AsyncMock()
        scheduler.set_scanner_callback(scanner_callback)

        scheduler.start()
        assert scheduler.is_running is True

        scheduler.stop()
        assert scheduler.is_running is False

        # Attendre que les tâches se terminent
        await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_scanner_loop_execution(self):
        """Test exécution boucle scanner"""
        scheduler = Scheduler()
        call_count = 0

        async def scanner_callback():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                scheduler.stop()

        scheduler.set_scanner_callback(scanner_callback)

        # Mock sleep pour accélérer
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            async def fast_sleep(seconds):
                if scheduler.is_running and seconds == 45:
                    await asyncio.sleep(0.01)  # Très court
                else:
                    await asyncio.sleep(0.01)

            mock_sleep.side_effect = fast_sleep

            scheduler.start()

            # Attendre que les callbacks soient appelés
            await asyncio.sleep(0.1)
            scheduler.stop()

            # Le callback devrait avoir été appelé au moins une fois
            assert call_count >= 1

    @pytest.mark.asyncio
    async def test_position_check_loop_execution(self):
        """Test exécution boucle position check"""
        scheduler = Scheduler()
        call_count = 0

        async def position_callback():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                scheduler.stop()

        scheduler.set_position_check_callback(position_callback)

        # Mock sleep pour accélérer
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            async def fast_sleep(seconds):
                if scheduler.is_running and seconds == 0.1:
                    await asyncio.sleep(0.01)
                else:
                    await asyncio.sleep(0.01)

            mock_sleep.side_effect = fast_sleep

            scheduler.start()

            # Attendre que les callbacks soient appelés
            await asyncio.sleep(0.1)
            scheduler.stop()

            # Le callback devrait avoir été appelé plusieurs fois
            assert call_count >= 1

    @pytest.mark.asyncio
    async def test_scalability_refresh_loop_execution(self):
        """Test exécution boucle scalability refresh"""
        scheduler = Scheduler()
        call_count = 0

        async def scalability_callback():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                scheduler.stop()

        scheduler.set_scalability_refresh_callback(scalability_callback)

        # Mock sleep pour accélérer
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            async def fast_sleep(seconds):
                if scheduler.is_running and seconds == 90:
                    await asyncio.sleep(0.01)
                else:
                    await asyncio.sleep(0.01)

            mock_sleep.side_effect = fast_sleep

            scheduler.start()

            # Attendre que les callbacks soient appelés
            await asyncio.sleep(0.1)
            scheduler.stop()

            # Le callback devrait avoir été appelé au moins une fois
            assert call_count >= 1

    @pytest.mark.asyncio
    async def test_scanner_loop_error_handling(self):
        """Test gestion erreurs dans scanner loop"""
        scheduler = Scheduler()
        call_count = 0

        async def failing_callback():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            scheduler.stop()

        scheduler.set_scanner_callback(failing_callback)

        # Mock sleep pour accélérer
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            async def fast_sleep(seconds):
                await asyncio.sleep(0.01)

            mock_sleep.side_effect = fast_sleep

            scheduler.start()

            # Attendre que l'erreur soit gérée
            await asyncio.sleep(0.2)
            scheduler.stop()

            # Le callback devrait avoir été appelé malgré l'erreur
            assert call_count >= 1

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test arrêt quand pas démarré"""
        scheduler = Scheduler()
        assert scheduler.is_running is False

        # Ne devrait pas lever d'exception
        scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_multiple_start_stop_cycles(self):
        """Test cycles multiples start/stop"""
        scheduler = Scheduler()

        callback = AsyncMock()
        scheduler.set_scanner_callback(callback)

        # Cycle 1
        scheduler.start()
        assert scheduler.is_running is True
        scheduler.stop()
        assert scheduler.is_running is False
        await asyncio.sleep(0.1)

        # Cycle 2
        scheduler.start()
        assert scheduler.is_running is True
        scheduler.stop()
        assert scheduler.is_running is False
        await asyncio.sleep(0.1)


# Tests d'intégration
class TestSchedulerIntegration:
    """Tests d'intégration pour Scheduler"""

    @pytest.mark.asyncio
    async def test_all_loops_running_concurrently(self):
        """Test toutes les boucles tournent en parallèle"""
        scheduler = Scheduler()

        scanner_calls = 0
        position_calls = 0
        scalability_calls = 0

        async def scanner_cb():
            nonlocal scanner_calls
            scanner_calls += 1

        async def position_cb():
            nonlocal position_calls
            position_calls += 1

        async def scalability_cb():
            nonlocal scalability_calls
            scalability_calls += 1

        scheduler.set_scanner_callback(scanner_cb)
        scheduler.set_position_check_callback(position_cb)
        scheduler.set_scalability_refresh_callback(scalability_cb)

        # Mock sleep pour accélérer toutes les boucles
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            async def fast_sleep(seconds):
                await asyncio.sleep(0.01)

            mock_sleep.side_effect = fast_sleep

            scheduler.start()

            # Laisser tourner un peu
            await asyncio.sleep(0.2)
            scheduler.stop()

            # Toutes les boucles devraient avoir été appelées
            assert scanner_calls >= 1
            assert position_calls >= 1
            assert scalability_calls >= 1

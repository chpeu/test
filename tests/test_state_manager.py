"""
🔥 SPRINT 1.4: Tests pour StateManager

Tests pour:
- Application state (is_scanning, active_position, stats, etc.)
- Component instances (scanner, analyzer, position_manager, etc.)
- Thread safety
- Locks
- Serialization
"""
import pytest
import asyncio
from unittest.mock import Mock
from threading import Thread
import time

# Import modules à tester
from core.state_manager import (
    StateManager,
    get_state_manager,
    reset_state_manager,
    TradingStats,
    ApplicationState
)


class TestTradingStats:
    """Tests pour TradingStats"""

    def test_initial_state(self):
        """Test état initial"""
        stats = TradingStats()
        assert stats.total_trades == 0
        assert stats.wins == 0
        assert stats.losses == 0
        assert stats.winrate == 0.0

    def test_winrate_calculation(self):
        """Test calcul winrate"""
        stats = TradingStats(total_trades=10, wins=7, losses=3)
        assert stats.winrate == 70.0

    def test_winrate_zero_trades(self):
        """Test winrate avec zéro trades"""
        stats = TradingStats(total_trades=0, wins=0, losses=0)
        assert stats.winrate == 0.0


class TestApplicationState:
    """Tests pour ApplicationState"""

    def test_initial_state(self):
        """Test état initial"""
        state = ApplicationState()
        assert state.is_scanning is False
        assert state.active_position is None
        assert isinstance(state.stats, TradingStats)
        assert state.top_pairs == []
        assert state.logs == []
        assert state.trade_history == []
        assert state.close_failure_count == 0
        assert state.close_failure_symbol is None
        assert state.backend_reboot_in_progress is False
        assert state.session_id is not None

    def test_session_id_unique(self):
        """Test que session_id est unique"""
        state1 = ApplicationState()
        state2 = ApplicationState()
        assert state1.session_id != state2.session_id


class TestStateManager:
    """Tests pour StateManager"""

    def setup_method(self):
        """Setup avant chaque test"""
        reset_state_manager()
        self.state = StateManager()

    def test_singleton(self):
        """Test pattern singleton"""
        state1 = get_state_manager()
        state2 = get_state_manager()
        assert state1 is state2

    def test_scanning_state(self):
        """Test gestion scanning state"""
        assert self.state.is_scanning is False

        self.state.set_scanning(True)
        assert self.state.is_scanning is True

        self.state.set_scanning(False)
        assert self.state.is_scanning is False

    def test_active_position(self):
        """Test gestion active position"""
        assert self.state.active_position is None

        position = {"symbol": "BTC/USDT", "side": "LONG", "entry": 50000.0}
        self.state.set_active_position(position)
        assert self.state.active_position == position

        self.state.set_active_position(None)
        assert self.state.active_position is None

    def test_stats(self):
        """Test gestion stats"""
        stats = self.state.stats
        assert stats.total_trades == 0
        assert stats.winrate == 0.0

        self.state.update_stats(total_trades=10, wins=7, losses=3)
        updated_stats = self.state.stats
        assert updated_stats.total_trades == 10
        assert updated_stats.wins == 7
        assert updated_stats.losses == 3
        assert updated_stats.winrate == 70.0

    def test_top_pairs(self):
        """Test gestion top pairs"""
        assert self.state.top_pairs == []

        pairs = [
            {"symbol": "BTC/USDT", "score": 95},
            {"symbol": "ETH/USDT", "score": 90},
        ]
        self.state.set_top_pairs(pairs)
        assert self.state.top_pairs == pairs

        # Vérifier copie (pas de référence)
        pairs.append({"symbol": "SOL/USDT", "score": 85})
        assert len(self.state.top_pairs) == 2

    def test_logs(self):
        """Test gestion logs"""
        assert self.state.logs == []

        log1 = {"level": "INFO", "message": "Test 1"}
        log2 = {"level": "ERROR", "message": "Test 2"}

        self.state.add_log(log1)
        assert len(self.state.logs) == 1

        self.state.add_log(log2)
        assert len(self.state.logs) == 2

        self.state.clear_logs()
        assert self.state.logs == []

    def test_trade_history(self):
        """Test gestion trade history"""
        assert self.state.trade_history == []

        trade1 = {"symbol": "BTC/USDT", "pnl": 100.0}
        trade2 = {"symbol": "ETH/USDT", "pnl": -50.0}

        self.state.add_trade(trade1)
        assert len(self.state.trade_history) == 1

        self.state.add_trade(trade2)
        assert len(self.state.trade_history) == 2

        new_history = [{"symbol": "SOL/USDT", "pnl": 200.0}]
        self.state.set_trade_history(new_history)
        assert len(self.state.trade_history) == 1

    def test_close_failure(self):
        """Test gestion close failures"""
        assert self.state.close_failure_count == 0
        assert self.state._app_state.close_failure_symbol is None

        self.state.increment_close_failure("BTC/USDT")
        assert self.state.close_failure_count == 1

        self.state.increment_close_failure("BTC/USDT")
        assert self.state.close_failure_count == 2

        self.state.reset_close_failure()
        assert self.state.close_failure_count == 0

    def test_backend_reboot(self):
        """Test backend reboot flag"""
        assert self.state.backend_reboot_in_progress is False

        self.state.set_backend_reboot(True)
        assert self.state.backend_reboot_in_progress is True

        self.state.set_backend_reboot(False)
        assert self.state.backend_reboot_in_progress is False

    def test_session_id(self):
        """Test session ID"""
        session_id = self.state.session_id
        assert session_id is not None
        assert isinstance(session_id, str)

    def test_component_instances(self):
        """Test gestion instances de composants"""
        # Scanner
        scanner_mock = Mock()
        self.state.set_scanner(scanner_mock)
        assert self.state.get_scanner() is scanner_mock

        # Analyzer
        analyzer_mock = Mock()
        self.state.set_analyzer(analyzer_mock)
        assert self.state.get_analyzer() is analyzer_mock

        # Position Manager
        pm_mock = Mock()
        self.state.set_position_manager(pm_mock)
        assert self.state.get_position_manager() is pm_mock

        # Price Provider
        pp_mock = Mock()
        self.state.set_price_provider(pp_mock)
        assert self.state.get_price_provider() is pp_mock

        # Scheduler
        scheduler_mock = Mock()
        self.state.set_scheduler(scheduler_mock)
        assert self.state.get_scheduler() is scheduler_mock

        # Trade DB
        db_mock = Mock()
        self.state.set_trade_db(db_mock)
        assert self.state.get_trade_db() is db_mock

        # Analytics DB
        analytics_mock = Mock()
        self.state.set_analytics_db(analytics_mock)
        assert self.state.get_analytics_db() is analytics_mock

        # Notification Manager
        notif_mock = Mock()
        self.state.set_notification_manager(notif_mock)
        assert self.state.get_notification_manager() is notif_mock

        # Live Order Manager
        lom_mock = Mock()
        self.state.set_live_order_manager(lom_mock)
        assert self.state.get_live_order_manager() is lom_mock

    @pytest.mark.asyncio
    async def test_locks(self):
        """Test async locks"""
        # Position lock
        async with self.state.lock("position"):
            # Lock acquis
            assert self.state.lock("position").locked() is True

        # Lock relâché après context
        assert self.state.lock("position").locked() is False

        # Scanner lock
        async with self.state.lock("scanner"):
            assert self.state.lock("scanner").locked() is True

        # State lock
        async with self.state.lock("state"):
            assert self.state.lock("state").locked() is True

    def test_invalid_lock(self):
        """Test lock invalide"""
        with pytest.raises(ValueError):
            self.state.lock("invalid_lock")

    def test_to_dict(self):
        """Test serialization to dict"""
        # Setup state
        self.state.set_scanning(True)
        self.state.set_active_position({"symbol": "BTC/USDT"})
        self.state.update_stats(total_trades=10, wins=7, losses=3)
        self.state.set_top_pairs([{"symbol": "BTC/USDT"}])

        # Serialize
        state_dict = self.state.to_dict()

        # Verify structure
        assert state_dict["is_scanning"] is True
        assert state_dict["active_position"] == {"symbol": "BTC/USDT"}
        assert state_dict["stats"]["total_trades"] == 10
        assert state_dict["stats"]["wins"] == 7
        assert state_dict["stats"]["winrate"] == 70.0
        assert state_dict["top_pairs"] == [{"symbol": "BTC/USDT"}]

    def test_cleanup(self):
        """Test cleanup"""
        # Setup state
        self.state.set_scanning(True)
        self.state.set_active_position({"symbol": "BTC/USDT"})
        self.state.add_trade({"symbol": "ETH/USDT"})

        # Cleanup
        self.state.cleanup()

        # Verify reset
        assert self.state.is_scanning is False
        assert self.state.active_position is None
        assert self.state.trade_history == []

    def test_thread_safety(self):
        """Test thread safety of concurrent access"""
        results = []

        def increment_trades():
            """Incrementer total_trades 100 fois"""
            for _ in range(100):
                stats = self.state.stats
                self.state.update_stats(total_trades=stats.total_trades + 1)

        # Lancer 5 threads en parallèle
        threads = []
        for _ in range(5):
            thread = Thread(target=increment_trades)
            threads.append(thread)
            thread.start()

        # Attendre completion
        for thread in threads:
            thread.join()

        # Vérifier que le compteur est correct (5 threads * 100 incréments)
        # Note: Peut être < 500 à cause de race conditions si pas thread-safe
        # Avec le Lock, devrait être exactement 500
        assert self.state.stats.total_trades == 500

    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_access(self):
        """Test que les locks empêchent l'accès concurrent"""
        access_count = 0

        async def critical_section():
            nonlocal access_count
            async with self.state.lock("position"):
                # Simuler opération longue
                current = access_count
                await asyncio.sleep(0.01)
                access_count = current + 1

        # Lancer 10 coroutines en parallèle
        await asyncio.gather(*[critical_section() for _ in range(10)])

        # Sans lock, access_count pourrait être < 10 (race condition)
        # Avec lock, devrait être exactement 10
        assert access_count == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

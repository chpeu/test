"""
Tests pour les routes scanner avec Dependency Injection
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock
from api.routes.scanner import get_scanner, get_analyzer, get_app_state, get_ws_manager
import api.routes.scanner as scanner_routes


@pytest.fixture
def client():
    """Client de test FastAPI"""
    from main import app
    return TestClient(app)


@pytest.fixture
def mock_scanner():
    """Mock pour scanner"""
    scanner = AsyncMock()
    scanner.scan_top_pairs = AsyncMock(return_value=['BTC/USDT:USDT', 'ETH/USDT:USDT'])
    scanner.is_scanning = False
    return scanner


@pytest.fixture
def mock_analyzer():
    """Mock pour analyzer"""
    analyzer = Mock()
    return analyzer


@pytest.fixture
def mock_app_state():
    """Mock pour app_state"""
    return {'top_pairs': ['BTC/USDT:USDT'], 'scanner_running': False}


class TestTopPairsRoute:
    """Tests pour GET /api/scanner/top-pairs"""

    def test_get_top_pairs_with_data(self, client, mock_app_state):
        """Test récupération des top pairs avec données"""
        from main import app

        # Override dependency
        app.dependency_overrides[get_app_state] = lambda: mock_app_state

        try:
            response = client.get("/api/scanner/top-pairs")

            assert response.status_code == 200
            data = response.json()
            assert 'pairs' in data
            assert len(data['pairs']) > 0
        finally:
            app.dependency_overrides.clear()

    def test_get_top_pairs_empty(self, client):
        """Test récupération des top pairs sans données"""
        from main import app

        # Override avec état vide
        app.dependency_overrides[get_app_state] = lambda: {}

        try:
            response = client.get("/api/scanner/top-pairs")

            assert response.status_code == 200
            data = response.json()
            assert data['pairs'] == []
        finally:
            app.dependency_overrides.clear()


class TestStartScannerRoute:
    """Tests pour POST /api/scanner/start"""

    def test_start_scanner_success(self, client, mock_scanner, mock_app_state):
        """Test démarrage scanner avec succès"""
        from main import app

        # Override dependencies
        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_app_state] = lambda: mock_app_state
        app.dependency_overrides[get_ws_manager] = lambda: None

        try:
            response = client.post("/api/scanner/start", json={"top_n": 10})

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'started'
            assert data['top_n'] == 10
            assert 'pairs' in data

            # Vérifier que scan_top_pairs a été appelé
            mock_scanner.scan_top_pairs.assert_called_once_with(n=10)
        finally:
            app.dependency_overrides.clear()

    def test_start_scanner_default_top_n(self, client, mock_scanner, mock_app_state):
        """Test démarrage scanner avec top_n par défaut"""
        from main import app

        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_app_state] = lambda: mock_app_state
        app.dependency_overrides[get_ws_manager] = lambda: None

        try:
            response = client.post("/api/scanner/start", json={})

            assert response.status_code == 200
            data = response.json()
            assert data['top_n'] == 20  # Défaut
        finally:
            app.dependency_overrides.clear()

    def test_start_scanner_error_handling(self, client, mock_app_state):
        """Test gestion d'erreur lors du démarrage"""
        from main import app

        # Scanner qui échoue
        error_scanner = AsyncMock()
        error_scanner.scan_top_pairs = AsyncMock(side_effect=Exception("Scanner error"))
        error_scanner.is_scanning = False

        app.dependency_overrides[get_scanner] = lambda: error_scanner
        app.dependency_overrides[get_app_state] = lambda: mock_app_state
        app.dependency_overrides[get_ws_manager] = lambda: None

        try:
            response = client.post("/api/scanner/start", json={"top_n": 10})

            assert response.status_code == 500
            data = response.json()
            assert 'error' in data
        finally:
            app.dependency_overrides.clear()

    def test_start_scanner_without_dependencies(self, client):
        """Test démarrage scanner sans dépendances disponibles"""
        from main import app

        # Ne pas injecter les dépendances (simuler indisponibilité)
        # get_scanner lèvera une HTTPException 503

        response = client.post("/api/scanner/start", json={"top_n": 10})

        # Devrait retourner 503 (Service Unavailable)
        assert response.status_code == 503


class TestAnalyzeSymbolRoute:
    """Tests pour GET /api/scanner/analyze/{symbol}"""

    def test_analyze_symbol_basic(self, client, mock_analyzer):
        """Test analyse d'un symbole"""
        from main import app

        app.dependency_overrides[get_analyzer] = lambda: mock_analyzer

        try:
            response = client.get("/api/scanner/analyze/BTCUSDT")

            assert response.status_code == 200
            data = response.json()
            assert data['symbol'] == 'BTCUSDT'
            assert data['status'] == 'pending'
        finally:
            app.dependency_overrides.clear()

    def test_analyze_symbol_with_params(self, client, mock_analyzer):
        """Test analyse avec paramètres"""
        from main import app

        app.dependency_overrides[get_analyzer] = lambda: mock_analyzer

        try:
            response = client.get(
                "/api/scanner/analyze/ETHUSDT"
                "?tf=5m&use_confluence=true&volume_multiplier=1.5"
            )

            assert response.status_code == 200
            data = response.json()
            assert data['symbol'] == 'ETHUSDT'
        finally:
            app.dependency_overrides.clear()

    def test_analyze_symbol_without_analyzer(self, client):
        """Test analyse sans analyzer disponible"""
        response = client.get("/api/scanner/analyze/BTCUSDT")

        # Devrait retourner 503 si analyzer non disponible
        assert response.status_code == 503


class TestStopScannerRoute:
    """Tests pour POST /api/scanner/stop et helper perform_stop_scanner"""

    def test_stop_scanner_success_stops_scheduler_price_ws_and_emits(self, client, mock_scanner):
        from main import app

        scheduler = Mock()
        scheduler.stop_async = AsyncMock()

        price_provider = Mock()
        price_provider.stop_websocket = AsyncMock()

        ws_manager = Mock()
        ws_manager.emit = AsyncMock()

        class _State:
            def __init__(self):
                self._is_scanning = True

            def get_scheduler(self):
                return scheduler

            async def stop_async(self):
                return None

            def set_is_scanning(self, v: bool):
                self._is_scanning = v

            def get_price_provider(self):
                return price_provider

            def get_ws_manager(self):
                return ws_manager

        state = _State()

        scanner_routes._app_state = {'is_scanning': True, 'scanner_running': True}
        scanner_routes._price_provider = price_provider

        import core.state_manager as state_manager

        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_ws_manager] = lambda: ws_manager
        try:
            # Patch get_state_manager used internally
            original_get_state_manager = state_manager.get_state_manager
            state_manager.get_state_manager = lambda: state

            response = client.post("/api/scanner/stop")
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'stopped'
            assert data['is_scanning'] is False

            scheduler.stop_async.assert_awaited_once()
            price_provider.stop_websocket.assert_awaited_once()
            assert scanner_routes._app_state['is_scanning'] is False
            assert scanner_routes._app_state['scanner_running'] is False

            assert ws_manager.emit.await_count >= 2
        finally:
            app.dependency_overrides.clear()
            state_manager.get_state_manager = original_get_state_manager
            scanner_routes._app_state = None
            scanner_routes._price_provider = None

    def test_stop_scanner_price_ws_stop_error_is_ignored(self, client, mock_scanner):
        from main import app

        scheduler = Mock()
        scheduler.stop_async = AsyncMock()

        price_provider = Mock()
        price_provider.stop_websocket = AsyncMock(side_effect=Exception("stop failed"))

        ws_manager = Mock()
        ws_manager.emit = AsyncMock()

        class _State:
            def get_scheduler(self):
                return scheduler

            def set_is_scanning(self, v: bool):
                return None

            def get_price_provider(self):
                return price_provider

            def get_ws_manager(self):
                return ws_manager

        state = _State()

        scanner_routes._app_state = {'is_scanning': True, 'scanner_running': True}
        scanner_routes._price_provider = price_provider

        import core.state_manager as state_manager

        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_ws_manager] = lambda: ws_manager
        try:
            original_get_state_manager = state_manager.get_state_manager
            state_manager.get_state_manager = lambda: state

            response = client.post("/api/scanner/stop")
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'stopped'

            scheduler.stop_async.assert_awaited_once()
            price_provider.stop_websocket.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()
            state_manager.get_state_manager = original_get_state_manager
            scanner_routes._app_state = None
            scanner_routes._price_provider = None

    @pytest.mark.asyncio
    async def test_perform_stop_scanner_stops_scheduler_price_ws_emits_and_logs(self, monkeypatch: pytest.MonkeyPatch):
        scheduler = Mock()
        scheduler.stop_async = AsyncMock()

        price_provider = Mock()
        price_provider.stop_websocket = AsyncMock()

        ws_manager = Mock()
        ws_manager.emit = AsyncMock()

        class _State:
            def __init__(self):
                self.is_scanning = False
            
            def get_scheduler(self):
                return scheduler

            def set_is_scanning(self, v: bool):
                self.is_scanning = bool(v)

            def get_price_provider(self):
                return price_provider

            def get_ws_manager(self):
                return ws_manager

        import core.state_manager as state_manager
        original_get_state_manager = state_manager.get_state_manager
        state_manager.get_state_manager = lambda: _State()

        import utils.logging_utils as logging_utils
        add_log = AsyncMock()
        monkeypatch.setattr(logging_utils, "add_log", add_log)

        try:
            result = await scanner_routes.perform_stop_scanner()
            assert result['status'] == 'stopped'
            assert result['is_scanning'] is False
            scheduler.stop_async.assert_awaited_once()
            price_provider.stop_websocket.assert_awaited_once()
            assert ws_manager.emit.await_count >= 2
            assert add_log.await_count >= 1  # perform_stop_scanner logs multiple times
        finally:
            state_manager.get_state_manager = original_get_state_manager

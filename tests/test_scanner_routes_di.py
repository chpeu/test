"""
Tests pour les routes scanner avec Dependency Injection
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, Mock
from api.routes.scanner import get_scanner, get_analyzer, get_app_state, get_ws_manager


@pytest_asyncio.fixture
async def client():
    """Client HTTPX async pour FastAPI"""
    from main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


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

    @pytest.mark.asyncio
    async def test_get_top_pairs_with_data(self, client, mock_app_state):
        """Test récupération des top pairs avec données"""
        from main import app

        # Override dependency
        app.dependency_overrides[get_app_state] = lambda: mock_app_state

        try:
            response = await client.get("/api/scanner/top-pairs")

            assert response.status_code == 200
            data = response.json()
            assert 'pairs' in data
            assert len(data['pairs']) > 0
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_top_pairs_empty(self, client):
        """Test récupération des top pairs sans données"""
        from main import app

        # Override avec état vide
        app.dependency_overrides[get_app_state] = lambda: {}

        try:
            response = await client.get("/api/scanner/top-pairs")

            assert response.status_code == 200
            data = response.json()
            assert data['pairs'] == []
        finally:
            app.dependency_overrides.clear()


class TestStartScannerRoute:
    """Tests pour POST /api/scanner/start"""

    @pytest.mark.asyncio
    async def test_start_scanner_success(self, client, mock_scanner, mock_app_state):
        """Test démarrage scanner avec succès"""
        from main import app

        # Override dependencies
        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_app_state] = lambda: mock_app_state
        app.dependency_overrides[get_ws_manager] = lambda: None

        try:
            response = await client.post("/api/scanner/start", json={"top_n": 10})

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'started'
            assert data['top_n'] == 10
            assert 'pairs' in data

            # Vérifier que scan_top_pairs a été appelé
            mock_scanner.scan_top_pairs.assert_called_once_with(n=10)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_start_scanner_default_top_n(self, client, mock_scanner, mock_app_state):
        """Test démarrage scanner avec top_n par défaut"""
        from main import app

        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_app_state] = lambda: mock_app_state
        app.dependency_overrides[get_ws_manager] = lambda: None

        try:
            response = await client.post("/api/scanner/start", json={})

            assert response.status_code == 200
            data = response.json()
            assert data['top_n'] == 20  # Défaut
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_start_scanner_error_handling(self, client, mock_app_state):
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
            response = await client.post("/api/scanner/start", json={"top_n": 10})

            assert response.status_code == 500
            data = response.json()
            assert 'error' in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_start_scanner_without_dependencies(self, client):
        """Test démarrage scanner sans dépendances disponibles"""
        from main import app

        # Ne pas injecter les dépendances (simuler indisponibilité)
        # get_scanner lèvera une HTTPException 503

        response = await client.post("/api/scanner/start", json={"top_n": 10})

        # Devrait retourner 503 (Service Unavailable)
        assert response.status_code == 503


class TestAnalyzeSymbolRoute:
    """Tests pour GET /api/scanner/analyze/{symbol}"""

    @pytest.mark.asyncio
    async def test_analyze_symbol_basic(self, client, mock_analyzer):
        """Test analyse d'un symbole"""
        from main import app

        app.dependency_overrides[get_analyzer] = lambda: mock_analyzer

        try:
            response = await client.get("/api/scanner/analyze/BTCUSDT")

            assert response.status_code == 200
            data = response.json()
            assert data['symbol'] == 'BTCUSDT'
            assert data['status'] == 'pending'
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_analyze_symbol_with_params(self, client, mock_analyzer):
        """Test analyse avec paramètres"""
        from main import app

        app.dependency_overrides[get_analyzer] = lambda: mock_analyzer

        try:
            response = await client.get(
                "/api/scanner/analyze/ETHUSDT"
                "?tf=5m&use_confluence=true&volume_multiplier=1.5"
            )

            assert response.status_code == 200
            data = response.json()
            assert data['symbol'] == 'ETHUSDT'
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_analyze_symbol_without_analyzer(self, client):
        """Test analyse sans analyzer disponible"""
        response = await client.get("/api/scanner/analyze/BTCUSDT")

        # Devrait retourner 503 si analyzer non disponible
        assert response.status_code == 503

"""
Tests pour vérifier les headers X-Deprecated sur endpoints REST legacy
Ces endpoints fonctionnent toujours en fallback mais sont deprecated au profit de WebSocket
"""
import pytest
from fastapi.testclient import TestClient


class TestDeprecatedRestEndpoints:
    """Tests pour les endpoints REST deprecated"""

    @pytest.fixture
    def client(self):
        """Fixture pour créer un TestClient FastAPI"""
        from main import app
        return TestClient(app)

    def test_api_start_has_deprecated_header(self, client):
        """
        Test: /api/start a le header X-Deprecated
        """
        response = client.post("/api/start")

        # Vérifier le status (devrait fonctionner)
        assert response.status_code == 200

        # Vérifier les headers X-Deprecated
        assert "x-deprecated" in response.headers
        assert response.headers["x-deprecated"] == "true"
        assert "x-deprecated-alternative" in response.headers
        assert "WebSocket" in response.headers["x-deprecated-alternative"]
        assert "x-deprecated-version" in response.headers
        assert response.headers["x-deprecated-version"] == "v7.0"

    def test_api_stop_has_deprecated_header(self, client):
        """
        Test: /api/stop a le header X-Deprecated
        """
        response = client.post("/api/stop")

        assert response.status_code == 200
        assert "x-deprecated" in response.headers
        assert response.headers["x-deprecated"] == "true"
        assert "x-deprecated-alternative" in response.headers
        assert "stop_scanner" in response.headers["x-deprecated-alternative"]

    def test_api_scanner_start_has_deprecated_header(self, client):
        """
        Test: /api/scanner/start a le header X-Deprecated
        """
        response = client.post("/api/scanner/start", json={"top_n": 20})

        # Peut retourner 400 si déjà en cours, mais header doit être présent
        assert "x-deprecated" in response.headers
        assert response.headers["x-deprecated"] == "true"
        assert "start_scanner" in response.headers["x-deprecated-alternative"]

    def test_api_position_close_has_deprecated_header(self, client):
        """
        Test: /api/position/close a le header X-Deprecated
        """
        response = client.post("/api/position/close")

        # Peut retourner 400 si pas de position active, mais header doit être présent
        assert "x-deprecated" in response.headers
        assert response.headers["x-deprecated"] == "true"
        assert "close_position" in response.headers["x-deprecated-alternative"]

    def test_api_log_config_has_deprecated_header(self, client):
        """
        Test: /api/log/config a le header X-Deprecated
        """
        response = client.post("/api/log/config", json={
            "key": "test_key",
            "value": "test_value"
        })

        assert response.status_code == 200
        assert "x-deprecated" in response.headers
        assert response.headers["x-deprecated"] == "true"
        assert "log_config" in response.headers["x-deprecated-alternative"]

    def test_api_config_update_has_deprecated_header(self, client):
        """
        Test: /api/config/update a le header X-Deprecated
        """
        response = client.post("/api/config/update", json={
            "volume_multiplier": 1.0
        })

        assert response.status_code == 200
        assert "x-deprecated" in response.headers
        assert response.headers["x-deprecated"] == "true"
        assert "update_config" in response.headers["x-deprecated-alternative"]

    def test_deprecated_endpoints_still_work(self, client):
        """
        Test: Les endpoints deprecated fonctionnent toujours (fallback)
        Vérifie que les headers sont présents mais l'endpoint fonctionne
        """
        # Test /api/config/update
        response = client.post("/api/config/update", json={
            "volume_multiplier": 0.95
        })

        # Devrait fonctionner normalement
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True or "updated" in data

        # Mais avec headers deprecated
        assert "x-deprecated" in response.headers
        assert response.headers["x-deprecated"] == "true"

    def test_all_deprecated_endpoints_have_alternative(self, client):
        """
        Test: Tous les endpoints deprecated indiquent l'alternative WebSocket
        """
        deprecated_endpoints = [
            ("/api/start", "POST", {}),
            ("/api/stop", "POST", {}),
            ("/api/scanner/start", "POST", {"top_n": 20}),
            ("/api/log/config", "POST", {"key": "test", "value": "test"}),
            ("/api/config/update", "POST", {"volume_multiplier": 1.0}),
        ]

        for endpoint, method, data in deprecated_endpoints:
            if method == "POST":
                response = client.post(endpoint, json=data)
            else:
                response = client.get(endpoint)

            # Header X-Deprecated doit être présent
            assert "x-deprecated" in response.headers, f"{endpoint} missing X-Deprecated header"
            assert response.headers["x-deprecated"] == "true", f"{endpoint} X-Deprecated != true"

            # Alternative doit être spécifiée
            assert "x-deprecated-alternative" in response.headers, f"{endpoint} missing alternative"
            alternative = response.headers["x-deprecated-alternative"]
            assert "WebSocket" in alternative or "command" in alternative, \
                f"{endpoint} alternative doesn't mention WebSocket or command"

    def test_non_deprecated_endpoints_no_header(self, client):
        """
        Test: Les endpoints non-deprecated n'ont PAS le header X-Deprecated
        """
        response = client.get("/api/scanner/top-pairs")

        # Cet endpoint n'est pas deprecated (lecture simple)
        assert "x-deprecated" not in response.headers or response.headers.get("x-deprecated") != "true"


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

"""
Tests du verrou de visite (`api/safety_lock.py`).

Pourquoi ces tests : le verrou est la seule chose qui empeche un clic perdu,
depuis une interface exposee sur Tailscale ou le reseau local, de lancer une
vraie session de trading. Les trois portes (`POST /api/start`,
`POST /api/scanner/start`, commande WebSocket `start_scanner`) doivent refuser
AVANT tout bootstrap : si le refus arrivait apres `ensure_instances()`, le bot
serait quand meme demarre.
"""
import pytest
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.safety_lock import scan_lock_active


# ---------------------------------------------------------------- verrou lui-meme


@pytest.mark.parametrize("valeur,attendu", [("1", True), ("true", True), ("OUI", True), ("Yes", True), ("0", False), ("faux", False), ("", False)])
def test_le_verrou_se_le_selon_la_valeur_d_environnement(monkeypatch, valeur, attendu):
    monkeypatch.setenv("VISITE_SANS_SCAN", valeur)
    assert scan_lock_active() is attendu


def test_le_verrou_est_ferme_quand_la_variable_absente(monkeypatch):
    monkeypatch.delenv("VISITE_SANS_SCAN", raising=False)
    assert scan_lock_active() is False


def test_le_verrou_se_relit_a_chaque_appel(monkeypatch):
    """Pas de redemarrage du serveur necessaire pour armer ou desarmer le verrou."""
    monkeypatch.setenv("VISITE_SANS_SCAN", "0")
    assert scan_lock_active() is False
    monkeypatch.setenv("VISITE_SANS_SCAN", "1")
    assert scan_lock_active() is True


# ---------------------------------------------------------------- portes REST


@pytest.fixture
def app_avec_routes():
    from unittest.mock import MagicMock

    from api.routes import dashboard, scanner

    app = FastAPI()
    app.include_router(dashboard.router)
    app.include_router(scanner.router)

    from api.auth import verify_api_key

    async def _sans_cle():
        return {"user": "visiteur"}

    app.dependency_overrides[verify_api_key] = _sans_cle
    # Sans scanner instance, la route repond 503 avant meme d'entrer dans le corps
    # (FastAPI resout les dependances d'abord) : on fourni un scanner factice pour
    # tester le verrou lui-meme, pas l'indisponibilite du scanner.
    app.dependency_overrides[scanner.get_scanner] = lambda: MagicMock()
    app.dependency_overrides[scanner.get_app_state] = lambda: {"top_pairs": [], "is_scanning": False}
    app.dependency_overrides[scanner.get_ws_manager] = lambda: None
    return app


@pytest.fixture
def client(app_avec_routes):
    return TestClient(app_avec_routes)


@pytest.mark.parametrize("route", ["/api/start", "/api/scanner/start"])
def test_porte_rest_refusee_et_bot_ne_demarre_pas(monkeypatch, client, route):
    import core.bootstrap as bootstrap

    bouchon = AsyncMock()
    monkeypatch.setattr(bootstrap, "ensure_instances", bouchon, raising=False)
    monkeypatch.setenv("VISITE_SANS_SCAN", "1")

    reponse = client.post(route)

    assert reponse.status_code == 403
    corps = reponse.json()
    assert corps["success"] is False
    assert corps["locked"] is True
    assert "VISITE_SANS_SCAN" in corps["error"]
    # le refus doit arriver AVANT l'initialisation du bot
    assert bouchon.await_count == 0


def test_sans_le_verrou_la_porte_n_est_pas_bloquee_par_cette_logique(monkeypatch, client):
    """Contre-echantillon : si le verrou n'est pas arme, ce n'est pas lui qui repond."""
    import core.bootstrap as bootstrap

    monkeypatch.setattr(bootstrap, "ensure_instances", AsyncMock(), raising=False)
    monkeypatch.delenv("VISITE_SANS_SCAN", raising=False)

    reponse = client.post("/api/scanner/start")

    assert reponse.status_code != 403


# ---------------------------------------------------------------- porte WebSocket


@pytest.mark.asyncio
async def test_commande_websocket_start_scanner_refusee(monkeypatch):
    import core.bootstrap as bootstrap

    init = AsyncMock()
    monkeypatch.setattr(bootstrap, "init_instances", init, raising=False)
    monkeypatch.setenv("VISITE_SANS_SCAN", "1")

    from api.routes.websocket import handle_client_command

    resultat = await handle_client_command("start_scanner", {})

    assert resultat["status"] == "error"
    assert resultat["locked"] is True
    assert resultat["is_scanning"] is False
    assert init.await_count == 0

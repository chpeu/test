"""Tests du conseiller IA locale.

Aucun reseau : on remplace urlopen par un faux llama-swap, pour verifier la
seule regle qui compte — on n'appelle jamais un modele qui n'est pas deja en
memoire, et on ne poste rien quand il n'y a rien de charge.
"""

import json
import urllib.error

import pytest

from ml import conseiller_ia


class FausseReponse:
    def __init__(self, donnees):
        self._corps = json.dumps(donnees).encode("utf-8")

    def read(self):
        return self._corps

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def echangeur(inventaire, reponse_chat=None, erreur=None):
    """Fabrique un urlopen faux de journal des appels (url, donnees envoyees)."""
    appels = []

    def faux_urlopen(requete, timeout=None):
        url = getattr(requete, "full_url", str(requete))
        corps_envoye = None
        data = getattr(requete, "data", None)
        if data:
            corps_envoye = json.loads(data.decode("utf-8"))
        appels.append((url, corps_envoye))
        if erreur:
            raise erreur
        if url.endswith("/models"):
            return FausseReponse(inventaire)
        if reponse_chat is None:
            raise urllib.error.URLError("pas de reponse attendue")
        return FausseReponse(reponse_chat)

    return faux_urlopen, appels


def inventaire(**statuts):
    return {
        "data": [
            {"id": nom, "status": {"value": statut}} for nom, statut in statuts.items()
        ]
    }


@pytest.fixture
def sans_reseau(monkeypatch):
    monkeypatch.delenv("IA_LOCALE_URL", raising=False)


def test_retient_le_modele_deja_charge(monkeypatch, sans_reseau):
    faux, appels = echangeur(inventaire(**{"petit": "unloaded", "principal": "loaded"}))
    monkeypatch.setattr(conseiller_ia.urllib.request, "urlopen", faux)
    assert conseiller_ia.modele_charge() == "principal"
    assert [a[0] for a in appels] == ["http://127.0.0.1:1234/v1/models"]


def test_refuse_si_rien_n_est_charge(monkeypatch, sans_reseau):
    faux, appels = echangeur(inventaire(**{"petit": "unloaded"}))
    monkeypatch.setattr(conseiller_ia.urllib.request, "urlopen", faux)
    assert conseiller_ia.modele_charge() is None
    assert conseiller_ia.demander_avis("quoi de neuf ?")["ok"] is False
    # la regle : une seule lecture d'inventaire, AUCUN envoi vers /chat/completions
    assert all(not url.endswith("/chat/completions") for url, _ in appels)


def test_poste_bien_le_modele_charge(monkeypatch, sans_reseau):
    reponse = {"choices": [{"message": {"content": "3 trades perdants sur 5."}}]}
    faux, appels = echangeur(inventaire(**{"principal": "loaded"}), reponse_chat=reponse)
    monkeypatch.setattr(conseiller_ia.urllib.request, "urlopen", faux)
    resultat = conseiller_ia.demander_avis("Bilan ?", "trade1\ntrade2")
    assert resultat["ok"] is True
    assert resultat["texte"] == "3 trades perdants sur 5."
    url_postee, corps = appels[-1]
    assert url_postee.endswith("/chat/completions")
    assert corps["model"] == "principal"


def test_service_injoignable_ne_casse_rien(monkeypatch, sans_reseau):
    monkeypatch.setattr(
        conseiller_ia.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("port ferm�")),
    )
    etat = conseiller_ia.etat()
    assert etat["service_joignable"] is False
    assert etat["modele"] is None
    assert conseiller_ia.demander_avis("allo")["ok"] is False


def test_url_personnalisee(monkeypatch):
    monkeypatch.setenv("IA_LOCALE_URL", "http://192.168.1.9:9999/v1/")
    assert conseiller_ia.modele_charge() is None  # personne a cette adresse


def test_resume_trades_vide():
    assert "Aucun trade" in conseiller_ia.resumer_trades([])
    texte = conseiller_ia.resumer_trades([{"symbol": "BTCUSDT", "pnl": -1.2, "exit_reason": "SL"}])
    assert "BTCUSDT" in texte and "SL" in texte


def test_routes_reponnent_sans_llama(monkeypatch):
    """Les trois routes existent et ne plantent pas quand llama-swap est absent."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routes.ia import router

    monkeypatch.setenv("IA_LOCALE_URL", "http://127.0.0.1:1/v1")  # port ferm� volontairement
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    etat = client.get("/api/ia/etat").json()
    assert etat["service_joignable"] is False
    assert client.post("/api/ia/avis", json={"question": ""}).status_code == 400
    avis = client.post("/api/ia/avis", json={"question": "Comment vas-tu ?"}).json()
    assert avis["ok"] is False
    bilan = client.post("/api/ia/bilan", json={"limite": 5}).json()
    assert bilan["ok"] is False and bilan["nb_trades"] == 0

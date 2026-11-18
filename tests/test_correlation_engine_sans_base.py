"""Le moteur de corrélations doit respecter POSTGRES_ENABLED=false.

Avant le 18/11/2026, il se connectait quand même à localhost:5432 : l'interface
affichait une carte rouge « Erreur connexion DB » sur une machine sans base,
alors que .env dit explicitement que le journal PostgreSQL est désactivé.
"""

import pytest

from core.analysis import correlation_engine


@pytest.fixture(autouse=True)
def environnement_sans_base(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_ENABLED", "false")


def test_aucune_tentative_de_connexion_quand_c_est_desactive(monkeypatch):
    appelee = []

    def piege(*args, **kwargs):
        appelee.append((args, kwargs))
        raise AssertionError("psycopg2.connect ne doit pas être appelé")

    monkeypatch.setattr(correlation_engine.psycopg2, "connect", piege)

    moteur = correlation_engine.CorrelationEngine()
    assert moteur._get_db_connection() is None
    assert appelee == []


def test_les_analyses_rendent_vide_sans_crier(monkeypatch, caplog):
    monkeypatch.setattr(
        correlation_engine.psycopg2,
        "connect",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("connexion interdite ici")),
    )
    moteur = correlation_engine.CorrelationEngine()
    assert moteur.analyze_by_session(days=7) == []
    assert moteur.analyze_by_local_regime(days=7) == []
    # le mot d'erreur ne doit plus sortir en ERROR : c'est un état normal ici
    assert "Erreur connexion DB" not in caplog.text


def test_une_url_de_base_explicite_est_quand_meme_ecoutee(monkeypatch):
    """DATABASE_URL reste la porte de secours : si elle existe, on essaie."""
    tentatives = []

    def piege(*args, **kwargs):
        tentatives.append(kwargs or args)
        raise RuntimeError("base absente, mais la tentative a bien eu lieu")

    monkeypatch.setenv("DATABASE_URL", "postgresql://quelquun@ailleurs/ma_base")
    monkeypatch.setattr(correlation_engine.psycopg2, "connect", piege)
    moteur = correlation_engine.CorrelationEngine()
    assert moteur._get_db_connection() is None
    assert len(tentatives) == 1

"""Lancé par uvicorn, le robot ne doit pas lire 'main:app' comme un numéro de port.

Le 18/11/2026, demarrer avec `uvicorn main:app` cassait la base des trades :
le code prenait sys.argv[1] (ici 'main:app') et faisait int() dessus, ce qui
levait « invalid literal for int() » et laissait TradeDatabase non initialise.
"""

import sys

import pytest

from core.analytics_database import AnalyticsDatabase
from core.database import TradeDatabase


@pytest.fixture
def argv_uvicorn(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["uvicorn", "main:app"])
    monkeypatch.chdir(tmp_path)


def test_base_des_trades_demarre_quand_meme(argv_uvicorn):
    base = TradeDatabase()
    try:
        assert base.db_path == "trades_instance_5000.db"
        assert base.conn is not None
    finally:
        base.close()


def test_base_analytique_demarre_quand_meme(argv_uvicorn):
    base = AnalyticsDatabase()
    try:
        assert base.instance_port == 5000
        assert base.conn is not None
    finally:
        base.close()


def test_le_numero_de_port_explicite_est_toujours_ecoute(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["main.py", "5007"])
    monkeypatch.chdir(tmp_path)
    base = TradeDatabase()
    try:
        assert base.db_path == "trades_instance_5007.db"
    finally:
        base.close()

"""
Tests du verrou de visite (`utils/visit_lock.py` + `api/safety_lock.py`).

Pourquoi ces tests existent : le projet n'a pas de mode « papier » réel
(`PAPER_TRADING_MODE` n'est lu nulle part) et `core/bootstrap.py` lance la boucle
de scan tout seul a l'etape 7. Le verrou est la seule chose qui empeche un
serveur lance pour une visite d'ouvrir des positions sur l'echange.
"""

from unittest.mock import Mock

import pytest

from api.safety_lock import lock_response
from utils.visit_lock import arm_scheduler_at_boot, scan_lock_active


class TestPredicate:
    @pytest.mark.parametrize("valeur", ["1", "true", "TRUE", "oui", "yes", " 1 "])
    def test_verrou_arme(self, monkeypatch, valeur):
        monkeypatch.setenv("VISITE_SANS_SCAN", valeur)
        assert scan_lock_active() is True

    @pytest.mark.parametrize("valeur", ["", "0", "false", "non", "n'importe quoi"])
    def test_verrou_desarme(self, monkeypatch, valeur):
        monkeypatch.setenv("VISITE_SANS_SCAN", valeur)
        assert scan_lock_active() is False

    def test_variable_absente_desarme_le_verrou(self, monkeypatch):
        monkeypatch.delenv("VISITE_SANS_SCAN", raising=False)
        assert scan_lock_active() is False


class TestDemarrageAuBoot:
    """`core/bootstrap.py` appelle ceci a l'etape 7 : c'est la porte silencieuse."""

    def test_le_scheduler_ne_demarre_pas_en_mode_visite(self, monkeypatch):
        monkeypatch.setenv("VISITE_SANS_SCAN", "1")
        sched = Mock()
        state = Mock()

        demarre = arm_scheduler_at_boot(sched, state)

        sched.start.assert_not_called()
        state.set_is_scanning.assert_called_once_with(False)
        assert demarre is False

    def test_le_scheduler_demarre_sans_le_verrou(self, monkeypatch):
        monkeypatch.delenv("VISITE_SANS_SCAN", raising=False)
        sched = Mock()
        state = Mock()

        demarre = arm_scheduler_at_boot(sched, state)

        sched.start.assert_called_once()
        state.set_is_scanning.assert_called_once_with(True)
        assert demarre is True


class TestReponseHTTP:
    def test_la_reponse_de_refus_est_explicite(self):
        reponse = lock_response()
        assert reponse.status_code == 403

        import json

        corps = json.loads(reponse.body)
        assert corps["locked"] is True
        assert corps["success"] is False
        assert "VISITE_SANS_SCAN" in corps["error"]

"""La calibration ML doit recevoir chaque trade fermé, quel que soit le chemin d'écriture.

Pourquoi ce fichier existe : l'appel à la calibration était rangé dans la
branche « thread de repli » de la fermeture de position (le cas où il n'y a pas
de boucle asynchrone en cours). En marche réelle la boucle asynchrone est presque
toujours là, donc l'écriture passait par l'autre branche et la calibration
n'était jamais prévenue. Mesure du 18/11/2026 : **2 trades comptés pour 54 trades
fermés** dans `ml_calibration` (somme de `total_trades` = 2), alors même que
toutes les confiance ML enregistrées valaient 40,9-59,1 %, bien au-dessus du
seuil de 30 % exigé par l'appel. Le robot restait donc « en phase d'apprentissage
» alors qu'il avait dépassé son propre seuil de 30 trades.
"""

import inspect
import types

import pytest

import ml.calibration
from core.position_manager import PositionManager


class FauxGestionnaire:
    """Enregistre ce que la fermeture de position lui envoie."""

    def __init__(self):
        self.appels = []

    def update_calibration(self, **kwargs):
        self.appels.append(kwargs)


def _position_avec(confiance_ml, direction="LONG"):
    return types.SimpleNamespace(
        symbol="TEST/USDT:USDT",
        direction=direction,
        ml_confidence=confiance_ml,
        live_execution_mode="PAPER",
        start_time=1_700_000_000,
    )


def _manager_sans_ecriture_base(confiance_ml):
    """Un PositionManager réduit au strict nécessaire pour ce test."""
    manager = PositionManager.__new__(PositionManager)
    manager.active_position = _position_avec(confiance_ml)
    manager.live_order_manager = None
    return manager


@pytest.fixture
def faux_gestionnaire(monkeypatch):
    gestionnaire = FauxGestionnaire()
    monkeypatch.setattr(
        ml.calibration, "get_calibration_manager", lambda: gestionnaire
    )
    return gestionnaire


def test_un_gain_nourrit_la_calibration(faux_gestionnaire):
    manager = _manager_sans_ecriture_base(51.0)
    manager._mettre_a_jour_calibration_ml(net_pnl_pct=0.72, net_pnl_usdt=0.11)

    assert len(faux_gestionnaire.appels) == 1
    appel = faux_gestionnaire.appels[0]
    assert appel["win"] is True
    assert appel["ml_confidence"] == pytest.approx(51.0)
    assert appel["direction"] == "LONG"
    assert appel["is_dry_run"] is True


def test_une_perte_nourrit_la_calibration_aussi(faux_gestionnaire):
    manager = _manager_sans_ecriture_base(44.5)
    manager._mettre_a_jour_calibration_ml(net_pnl_pct=-0.35, net_pnl_usdt=-0.05)

    assert len(faux_gestionnaire.appels) == 1
    assert faux_gestionnaire.appels[0]["win"] is False


def test_confiance_en_decimal_est_convertie_en_pourcentage(faux_gestionnaire):
    manager = _manager_sans_ecriture_base(0.53)
    manager._mettre_a_jour_calibration_ml(net_pnl_pct=0.20, net_pnl_usdt=0.03)

    assert faux_gestionnaire.appels[0]["ml_confidence"] == pytest.approx(53.0)


def test_sous_30_de_confiance_on_ne_compte_rien(faux_gestionnaire):
    manager = _manager_sans_ecriture_base(22.0)
    manager._mettre_a_jour_calibration_ml(net_pnl_pct=0.20, net_pnl_usdt=0.03)

    assert faux_gestionnaire.appels == []


def test_la_mise_a_jour_ne_depend_pas_du_trade_id():
    """Le garde-fou : l'appel ne doit pas se retrouver dans une branche d'écriture.

    Les deux chemins d'écriture du journal (boucle asynchrone, thread de repli)
    ne donnent pas le même `trade_id`. Tant que la calibration est appelée avant
    l'écriture, elle ne peut pas être perdue par l'un des deux.
    """
    source = inspect.getsource(PositionManager.close_position)
    position_appel = source.find("self._mettre_a_jour_calibration_ml(")
    position_ecriture = source.find("log_trade_async(")

    assert position_appel != -1, "close_position n'appelle plus la calibration"
    assert position_ecriture != -1, "close_position n'écrit plus le trade en base"
    assert position_appel < position_ecriture, (
        "la calibration doit être mise à jour AVANT l'écriture du trade : "
        "rangée après, elle retombe sous la dépendance d'un seul chemin d'écriture"
    )

    source_module = inspect.getsource(inspect.getmodule(PositionManager))
    assert source_module.count("calib_manager.update_calibration(") == 1, (
        "deux endroits mettent à jour la calibration : l'un des deux se retrouvera "
        "côté d'une branche, comme la fuite des 52 trades sur 54 du 18/11/2026"
    )

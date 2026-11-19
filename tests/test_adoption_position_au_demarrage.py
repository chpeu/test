"""Le robot doit reprendre la position qui court déjà sur l'échange.

Mesure du 19/11/2026 : rien ne faisait ce travail. Le robot consultait les
positions de l'échange pour les afficher dans l'interface, mais ne les reprenait
jamais à sa charge. Après un plantage, une coupure réseau ou un redémarrage
manuel, la position réelle restait sans surveillance — plus de stop suiveur, plus
de take-profit partiel, plus de sortie temporelle — et le robot pouvait ouvrir
une deuxième position à côté.
"""

import pytest

from config import TRADING_CONFIG
from core.position_manager import PositionConfig, PositionManager


class FauxEchange:
    def __init__(self, positions=None, erreur=None):
        self._positions = positions if positions is not None else []
        self._erreur = erreur

    def fetch_positions(self, *args, **kwargs):
        if self._erreur:
            raise self._erreur
        return self._positions


class FauxGestionnaire:
    def __init__(self, positions=None, erreur=None, dry_run=False):
        self.exchange = FauxEchange(positions, erreur)
        self.dry_run = dry_run
        self.stops_poses = []

    def _poser_stop_echange(self, symbole, sens, prix):
        self.stops_poses.append((symbole, sens, prix))
        return True, prix


def une_position_echange(symbole="ZEC/USDT:USDT", sens="long", entree=10.0, contrats=100.0):
    return {
        "symbol": symbole,
        "side": sens,
        "entryPrice": entree,
        "contracts": contrats,
    }


def un_gerant(gestionnaire_live=None) -> PositionManager:
    return PositionManager(config=PositionConfig(), live_order_manager=gestionnaire_live)


# ── rien à reprendre en essai à blanc ────────────────────────────────────────


def test_essai_a_blanc_ne_consulte_pas_lechange():
    gestionnaire = FauxGestionnaire(positions=[une_position_echange()], dry_run=True)
    resultat = un_gerant(gestionnaire).adopter_positions_au_demarrage()
    assert resultat == {"adoptees": 0, "bloque": None}


def test_aucune_position_ouverte_ne_bloque_rien():
    resultat = un_gerant(FauxGestionnaire(positions=[])).adopter_positions_au_demarrage()
    assert resultat == {"adoptees": 0, "bloque": None}


# ── la reprise ───────────────────────────────────────────────────────────────


def test_une_position_longue_est_reprise_et_surveillee():
    gestionnaire = FauxGestionnaire(positions=[une_position_echange()])
    manager = un_gerant(gestionnaire)

    resultat = manager.adopter_positions_au_demarrage()
    position = manager.active_position

    assert resultat["adoptees"] == 1
    assert position is not None
    assert position.symbol == "ZEC/USDT:USDT"
    assert position.direction == "LONG"
    assert position.size == pytest.approx(1000.0)  # 100 contrats × 10,0
    assert position.sl < position.entry < position.tp
    assert position.adoptee_au_demarrage is True
    # le filet de sécurité est re-posé chez MEXC pour une position reprise
    assert gestionnaire.stops_poses == [("ZEC/USDT:USDT", "LONG", position.sl)]


def test_une_position_courte_a_son_stop_au_dessus():
    manager = un_gerant(FauxGestionnaire(positions=[une_position_echange(sens="short")]))
    manager.adopter_positions_au_demarrage()

    position = manager.active_position
    assert position.direction == "SHORT"
    assert position.sl > position.entry > position.tp


def test_les_tailles_sont_coherentes_apres_reprise():
    """Sans ça, les pourcentages du trade repris seraient faux dès la fermeture."""
    manager = un_gerant(FauxGestionnaire(positions=[une_position_echange()]))
    manager.adopter_positions_au_demarrage()

    position = manager.active_position
    assert position.size_initial_usdt == pytest.approx(position.size)
    assert position.size_remaining_contracts == pytest.approx(position.size_initial_contracts)


# ── ce qui n'est pas clair bloque au lieu de deviner ─────────────────────────


def test_deux_positions_bloquent_les_ouvertures():
    gestionnaire = FauxGestionnaire(
        positions=[une_position_echange(), une_position_echange(symbole="ONE/USDT:USDT")]
    )
    manager = un_gerant(gestionnaire)

    resultat = manager.adopter_positions_au_demarrage()
    assert manager.active_position is None
    assert "2 positions" in resultat["bloque"]
    assert "2 positions" in manager._blocage_adoption


def test_echange_injoignable_bloque_les_ouvertures():
    """Sans réponse, impossible de savoir si une position court : on n'ouvre pas."""
    manager = un_gerant(FauxGestionnaire(erreur=TimeoutError("mexc indisponible")))

    resultat = manager.adopter_positions_au_demarrage()
    assert manager.active_position is None
    assert "mexc indisponible" in resultat["bloque"]


def test_position_illisible_bloque_les_ouvertures():
    manager = un_gerant(FauxGestionnaire(positions=[{"symbol": "X", "contracts": "???"}]))
    assert manager.adopter_positions_au_demarrage()["bloque"]
    assert manager.active_position is None


def test_une_fois_bloque_le_robot_ne_peut_plus_ouvrir(monkeypatch):
    import core.frais_paires as frais

    monkeypatch.setattr(frais, "verifier_prise", lambda symbole: (True, ""))
    manager = un_gerant(FauxGestionnaire(erreur=TimeoutError("mexc indisponible")))
    manager.adopter_positions_au_demarrage()

    assert manager.open_position(
        symbol="ZEC/USDT:USDT", direction="LONG", entry=10.0, size=15.0
    ) is None


def test_la_reprise_peut_etre_coupee_par_reglage(monkeypatch):
    monkeypatch.setitem(TRADING_CONFIG, "adopte_positions_au_demarrage", False)
    gestionnaire = FauxGestionnaire(positions=[une_position_echange()])
    assert un_gerant(gestionnaire).adopter_positions_au_demarrage()["adoptees"] == 0


# ── branchement ──────────────────────────────────────────────────────────────


def test_le_demarrage_appelle_bien_la_reprise():
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "core" / "bootstrap.py").read_text(
        encoding="utf-8"
    )
    assert "adopter_positions_au_demarrage(" in source, (
        "le démarrage ne reprend plus les positions de l'échange : après un "
        "redémarrage, une position réelle redevient invisible pour le robot"
    )


def test_le_chemin_d_ouverture_respecte_le_blocage():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "core" / "position_manager.py"
    ).read_text(encoding="utf-8")
    assert "_blocage_adoption" in source


def test_les_reglages_sont_actifs_par_defaut():
    assert TRADING_CONFIG["adopte_positions_au_demarrage"] is True
    assert TRADING_CONFIG["adoptee_stop_echange"] is True

"""Le papier doit payer exactement ce que le live paierait.

Ce fichier fige la parite papier / live, valeur par valeur, d'apres les mesures du
19/11/2026 sur 101 trades fermes et sur le carnet d'ordres reel de MEXC :

    frais taker reels      : 0,006 % en moyenne (la plupart des paires a 0 frais)
    spread mesure          : 0,020 % par prise (pire cas 0,051 %)
    depassement du stop    : 0,160 % par stop (pire cas 0,83 %)
    financement            : 0,0001 % par prise sur les prises courtes
    glissement non facture : 21 prises sur 102 payaient 0 de glissement

Chaque trou est ferme cote moteur ; ce fichier empeche qu'il se rouvre.
"""

import time
from pathlib import Path

import pytest

from config import TRADING_CONFIG
from core.position_manager import PositionConfig, Position, PositionManager


SOURCE = (Path(__file__).resolve().parent.parent / "core" / "position_manager.py").read_text(
    encoding="utf-8"
)


# ── les reglages de papier portent les valeurs mesurees, pas des suppositions ─


def test_le_glissement_plancher_vaut_le_spread_mesure():
    assert float(TRADING_CONFIG["papier_glissement_min_pct"]) == pytest.approx(0.02, abs=0.005)


def test_le_depassement_de_stop_vaut_la_mesure_des_51_stops():
    assert float(TRADING_CONFIG["papier_depassement_stop_pct"]) == pytest.approx(0.16, abs=0.03)


def test_les_couts_mesures_sont_actifs():
    assert TRADING_CONFIG["papier_frais_financement_actif"] is True


# ── le financement des perpetuels est compte ─────────────────────────────────


class FaussePosition:
    """Deux sources de taux, deux unités assumées :

    - `taux_scanner` : ce que le scanner connaît à l'entrée, en % par 8 h (0.01 = 0,01 %) ;
    - `taux_ccxt` : celui de l'ordre live, déjà en fraction (0.0001 = 0,01 %).
    """

    def __init__(self, direction="LONG", heures=8.0, taux=None, taux_ccxt=None):
        self.direction = direction
        self.start_time = time.time() - heures * 3600
        self.scalability_data = {"fundingRate": taux} if taux is not None else {}
        if taux_ccxt is not None:
            self.funding_rate_at_entry = taux_ccxt


def test_long_de_huit_heures_paie_le_financement():
    usdt = PositionManager._financement_papier_usdt(FaussePosition(taux=0.01), 100.0, False)
    assert usdt == pytest.approx(0.01)  # 0,01 % de 100 USDT


def test_short_de_huit_heures_encaisse_le_financement():
    usdt = PositionManager._financement_papier_usdt(
        FaussePosition(direction="SHORT", taux=0.01), 100.0, False
    )
    assert usdt == pytest.approx(-0.01)


def test_trois_heures_paient_trois_huitiemes_du_financement():
    usdt = PositionManager._financement_papier_usdt(
        FaussePosition(heures=3.0, taux=0.01), 100.0, False
    )
    assert usdt == pytest.approx(0.01 * 3 / 8)


def test_taux_ccxt_en_fraction_revient_au_meme_montant():
    fraction = PositionManager._financement_papier_usdt(
        FaussePosition(taux_ccxt=0.0001), 100.0, False
    )
    pourcentage = PositionManager._financement_papier_usdt(
        FaussePosition(taux=0.01), 100.0, False
    )
    assert fraction == pytest.approx(pourcentage) == pytest.approx(0.01)


def test_sans_taux_connu_rien_n_est_invente():
    assert PositionManager._financement_papier_usdt(FaussePosition(), 100.0, False) == 0.0


def test_en_live_le_financement_vient_de_lechange_pas_du_robot():
    assert PositionManager._financement_papier_usdt(FaussePosition(taux=0.01), 100.0, True) == 0.0


# ── le glissement ne peut plus etre gratuit ─────────────────────────────────


def _fermer_sans_donnees_de_scalabilite(monkeypatch):
    manager = PositionManager(config=PositionConfig(use_slippage_calculation=True))
    manager.active_position = Position(
        symbol="ZEC/USDT:USDT", direction="LONG", entry=10.0, size=100.0, sl=9.9, tp=10.2
    )
    manager.active_position.start_time = time.time() - 120

    monkeypatch.setattr("core.callbacks.scanner_loop.get_pg_datalogger", lambda: None)
    monkeypatch.setattr(
        "threading.Thread",
        lambda *a, **k: type("T", (), {"start": lambda self: None})(),
    )
    import core.frais_paires as frais

    monkeypatch.setattr(frais, "lire_frais", lambda symbole: (0.0, 0.0))

    return manager.close_position(exit_price=10.1, reason="TP")


@pytest.fixture
def ferme_papier(monkeypatch):
    return _fermer_sans_donnees_de_scalabilite(monkeypatch)


def test_prise_sans_donnees_de_scalabilite_paie_le_glissement_mesure(ferme_papier):
    """21 prises sur 102 ne payaient aucun glissement : la porte est fermee."""
    assert ferme_papier["slippage_pct"] == pytest.approx(float(TRADING_CONFIG["papier_glissement_min_pct"]))


def test_paie_a_0_frais_ne_paie_aucun_frais_en_papier(ferme_papier):
    assert ferme_papier["fees"] == pytest.approx(0.0)


# ── les horodatages: meme reference pour l'entree et la sortie ───────────────


def test_entree_et_sortie_ecrites_dans_la_meme_reference_de_temps():
    """Sortie avant entree = 102 trades sur 102 : l'entree etait en heure locale.

    `datetime.fromtimestamp(x)` sans `tz=` donne l'heure locale ; la base est en
    TIMESTAMPTZ. Toutes les durees (sortie temporelle, stagnation, financement,
    statistiques de detention) etaient fausses.
    """
    endroits = [i for i in range(len(SOURCE)) if SOURCE.startswith("datetime.fromtimestamp(", i)]
    assert endroits, "le test n'a plus rien à kontroler"
    for index in endroits:
        fenetre = SOURCE[index : index + 160]
        assert "tz=timezone.utc" in fenetre, (
            f"un horodatage d'entree est repasse en heure locale (position {index})"
        )


def test_les_couts_sont_tous_cumules_a_la_fermeture():
    assert "self._financement_papier_usdt(" in SOURCE
    assert "self._depassement_stop_usdt(" in SOURCE
    assert "papier_glissement_min_pct" in SOURCE

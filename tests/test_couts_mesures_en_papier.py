"""Les coûts du papier viennent de la mesure, et les pourcentages d'une seule taille.

Trois bugs mesurés le 19/11/2026 :

  1. `net_pnl_pct` était calculé sur une taille différente de celle écrite en base
     (16,5 USDT contre 9,9 pour SHIB) : 4,17 points d'écart sur un trade, et 0,25 %
     par prise d'écart qui n'étaient pas des coûts. Le tableau de bord, la
     calibration ML et le classement de paires lisent ces pourcentages.
  2. `(fee_per_trade or 0.0004) * 100` : `fee_per_trade` vaut 0.00 parce que les
     paires sont dans la zone « 0 frais » de MEXC, et le `or` transformait ce zéro
     légitime en 0,0004. Le robot facturait 0,04 % par jambe sur des paires où il
     ne paie rien.
  3. Un stop papier se remplissait exactement au prix prévu. Mesure sur 51 stops :
     la bougie dépasse en moyenne de 0,160 % (pire cas 0,83 %).
"""

from types import SimpleNamespace

import pytest

from config import TRADING_CONFIG
from core.position_manager import PositionManager


# ── 1. une seule taille pour tous les pourcentages ───────────────────────────


def une_position(**champs):
    base = dict(size=9.9, size_initial_usdt=16.5, size_executed_usdt=16.5, partial_tp_sold=False)
    base.update(champs)
    return SimpleNamespace(**base)


def test_la_taille_engagee_prend_le_pas_quand_elle_differe():
    """Le `size_usdt` écrit en base et le dénominateur du pourcentage doivent être le même."""
    position = une_position()
    assert PositionManager._taille_de_reference_pour_centards(position) == pytest.approx(9.9)


def test_avec_un_take_profit_partiel_on_garde_la_taille_initiale():
    """Après une vente partielle, `size` a fondu : le % serait gonflé sinon."""
    position = une_position(size=5.9, partial_tp_sold=True)
    assert PositionManager._taille_de_reference_pour_centards(position) == pytest.approx(16.5)


def test_tailles_coherentes_pas_de_correction():
    position = une_position(size=16.4, size_initial_usdt=16.5)
    assert PositionManager._taille_de_reference_pour_centards(position) == pytest.approx(16.5)


def test_le_pourcentage_net_correspond_aux_USDT_ecrits():
    """Le cas réel mesuré : 1,0047 USDT nets pour 9,9 USDT engagés = 10,15 % (pas 6,09 %)."""
    taille = PositionManager._taille_de_reference_pour_centards(une_position())
    assert 1.0047 / taille * 100 == pytest.approx(10.1485, abs=0.01)


# ── 2. les frais pris chez MEXC, pas dans un défaut ──────────────────────────


def test_paie_a_0_frais_ne_facture_rien(monkeypatch):
    import core.frais_paires as frais

    monkeypatch.setattr(frais, "lire_frais", lambda symbole: (0.0, 0.0))
    assert PositionManager._taux_de_frais_pour_centards("ZEC/USDT:USDT") == 0.0


def test_paie_payante_facture_le_taux_reel(monkeypatch):
    import core.frais_paires as frais

    monkeypatch.setattr(frais, "lire_frais", lambda symbole: (0.0004, 0.0002))
    assert PositionManager._taux_de_frais_pour_centards("SOL/USDT:USDT") == pytest.approx(0.04)


def test_frais_inconnus_ne_reinventent_pas_0_04_pourcent(monkeypatch):
    """Le cœur du bug : `0.00 or 0.0004` → 0,04 % sur une paire à 0 frais."""
    import core.frais_paires as frais
    import utils.effective_config as config_effectif

    monkeypatch.setattr(frais, "lire_frais", lambda symbole: (None, None))
    monkeypatch.setattr(config_effectif, "get_effective_value", lambda cle: 0.0)
    assert PositionManager._taux_de_frais_pour_centards("X/USDT:USDT") == 0.0


def test_reglage_de_frais_conserve_si_la_table_n_a_pas_la_paie(monkeypatch):
    import core.frais_paires as frais
    import utils.effective_config as config_effectif

    monkeypatch.setattr(frais, "lire_frais", lambda symbole: (None, None))
    monkeypatch.setattr(config_effectif, "get_effective_value", lambda cle: 0.0002)
    assert PositionManager._taux_de_frais_pour_centards("X/USDT:USDT") == pytest.approx(0.02)


# ── 3. le dépassement du stop est payé en papier ─────────────────────────────


def test_un_stop_papier_paie_le_depassement_mesure():
    montant = PositionManager._depassement_stop_usdt("SL", 10.0, False)
    assert montant == pytest.approx(10.0 * TRADING_CONFIG["papier_depassement_stop_pct"] / 100)


@pytest.mark.parametrize("raison", ["TS", "TP", "TIME_BASED_EXIT", ""])
def test_les_autres_sorties_ne_paient_pas_le_depassement(raison):
    assert PositionManager._depassement_stop_usdt(raison, 10.0, False) == 0.0


def test_un_prix_rempli_reel_ne_paie_pas_de_depassement_estime():
    """En live, c'est l'échange qui donne le prix : plus d'estimation par-dessus."""
    assert PositionManager._depassement_stop_usdt("SL", 10.0, True) == 0.0


def test_le_reglage_de_depassement_restera_mesurable():
    valeur = float(TRADING_CONFIG["papier_depassement_stop_pct"])
    assert 0.0 <= valeur <= 0.5, "au-delà, on ne corrige plus : on fabrique la performance"


# ── branchement : les trois helpers doivent rester dans le chemin de fermeture ─


def test_la_fermeture_utilise_bien_les_trois_helpers():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "core" / "position_manager.py"
    ).read_text(encoding="utf-8")
    for helper in (
        "_taille_de_reference_pour_centards(",
        "_taux_de_frais_pour_centards(",
        "_depassement_stop_usdt(",
    ):
        assert source.count(helper) >= 2, (
            f"{helper} n'est plus appelé dans le chemin de fermeture : les coûts "
            "estimes et les deux tailles reviennent en service"
        )

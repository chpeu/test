"""Le tri « paires à 0 frais » doit suivre MEXC, pas le cache de ccxt.

Mesuré le 19/11/2026 : 95 prises sur des paires à 0 frais (+10,27 % cumulés),
3 prises sur SOL payante (-0,14 %), et 0 USDT de frais écrit sur les 98 trades.
La cause : `load_markets()` renvoie le cache de la première connexion, donc le
tri tournait avec des frais figés depuis le démarrage alors que MEXC déplace des
contrats dentro/fuori de sa zone « 0 frais » sans prévenir.
"""

import time
from pathlib import Path

import pytest

import core.frais_paires as frais
from config import TRADING_CONFIG
from core.frais_paires import MAJEURES, paire_acceptable, verifier_prise


# ── la logique du tri ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "symbole,taker,attendu",
    [
        ("ZEC/USDT:USDT", 0.0, True),          # zone 0 frais : acceptée
        ("SOL/USDT:USDT", 0.0004, False),      # payante : refusée par défaut
        ("QNT/USDT:USDT", None, False),        # frais inconnus : on ne devine pas
    ],
)
def test_le_tri_accepte_uniquement_le_0_frais(symbole, taker, attendu):
    assert paire_acceptable(symbole, taker) is attendu


def test_les_majeures_ne_sont_plus_dispensees_par_defaut():
    """BTC/ETH/SOL payent leur frais : la dispense doit être un choix explicite."""
    for majeure in MAJEURES:
        assert paire_acceptable(majeure, 0.0004) is False
        assert paire_acceptable(majeure, 0.0004, autoriser_payantes=True) is True


def test_liste_blanche_et_plafond_autorisent_une_exception():
    assert paire_acceptable("XRP/USDT:USDT", 0.0004, liste_blanche=["XRP/USDT:USDT"]) is True
    assert paire_acceptable("XRP/USDT:USDT", 0.0004, max_pct=0.1) is True


# ── la porte d'ouverture ─────────────────────────────────────────────────────


@pytest.fixture
def table(fake):
    """Remplace la table des frais lue chez MEXC pour la durée du test."""
    ancien = frais._table
    frais._table = dict(fake)
    yield
    frais._table = ancien


@pytest.fixture
def fake():
    return {
        "ZEC/USDT:USDT": (0.0, 0.0),
        "SOL/USDT:USDT": (0.0004, 0.0002),
    }


def test_une_paie_devenue_payante_est_refusee_a_l_ouverture(table):
    """Le cœur du bug : le dictionnaire ccxt disait encore 0, MEXC disait 0,04 %."""
    autorise, motif = verifier_prise("SOL/USDT:USDT")
    assert autorise is False
    assert "0.040 %" in motif


def test_une_paie_a_0_frais_passe(table):
    autorise, motif = verifier_prise("ZEC/USDT:USDT")
    assert (autorise, motif) == (True, "")


def test_paie_absente_de_la_table_est_refusee(table):
    autorise, motif = verifier_prise("INCONNUE/USDT:USDT")
    assert autorise is False
    assert "frais inconnus" in motif


def test_les_frais_sont_notes_sur_la_prise(table):
    """Sans ces colonnes remplies, une prise payante est invisible dans les comptes."""
    from core.frais_paires import lire_frais

    taker, maker = lire_frais("SOL/USDT:USDT")
    assert (taker, maker) == (0.0004, 0.0002)
    assert round(15.0 * taker, 6) == 0.006  # 15 USDT × 0,04 %


# ── la table doit vieillir et se recharger ───────────────────────────────────


@pytest.mark.asyncio
async def test_une_table_jeune_ne_declenche_pas_de_relecture(monkeypatch):
    appels = []

    async def fausse_relecture():
        appels.append(1)
        return {"A/USDT:USDT": (0.0, 0.0)}

    monkeypatch.setattr(frais, "_recharger", fausse_relecture)
    monkeypatch.setattr(frais, "_table", {"A/USDT:USDT": (0.0, 0.0)})
    monkeypatch.setattr(frais, "_horodatage", time.monotonic())

    await frais.table_frais()
    assert appels == []


@pytest.mark.asyncio
async def test_une_table_vieille_declenche_la_relecture(monkeypatch):
    appels = []

    async def fausse_relecture():
        appels.append(1)
        return {"A/USDT:USDT": (0.0, 0.0)}

    monkeypatch.setattr(frais, "_recharger", fausse_relecture)
    monkeypatch.setattr(frais, "_table", {"A/USDT:USDT": (0.0, 0.0)})
    monkeypatch.setattr(frais, "_horodatage", time.monotonic() - 3600)

    await frais.table_frais()
    assert appels == [1]


@pytest.mark.asyncio
async def test_une_panne_reseau_ne_fait_pas_fuire_de_prise_payante(monkeypatch):
    """Table vide + réseau en panne : la décision refuse, elle n'invente pas un 0."""

    async def relecture_en_pannc():
        raise TimeoutError("mexc indisponible")

    monkeypatch.setattr(frais, "_recharger", relecture_en_pannc)
    monkeypatch.setattr(frais, "_table", {})

    table = await frais.table_frais(force=True)
    assert table == {}
    assert paire_acceptable("ZEC/USDT:USDT", table.get("ZEC/USDT:USDT", (None,))[0]) is False


# ── branchement : les deux portes doivent rester câblées ─────────────────────


def test_le_trie_de_paires_consulte_la_table_relue():
    source = (Path(__file__).resolve().parent.parent / "core" / "scanner.py").read_text(encoding="utf-8")
    assert "table_frais(" in source, "le tri des paires est revenu au cache ccxt"


def test_l_ouverture_d_une_prise_consulte_les_frais():
    source = (
        Path(__file__).resolve().parent.parent / "core" / "position_manager.py"
    ).read_text(encoding="utf-8")
    assert "verifier_prise(" in source, "la porte de frais a sauté du chemin d'ouverture"


def test_les_reglages_de_frais_existent_et_sont_stricts():
    assert TRADING_CONFIG["entree_frais_max_pct"] == 0.0
    assert TRADING_CONFIG["entree_autoriser_paires_payantes"] is False
    assert 1.0 <= float(TRADING_CONFIG["frais_actualiser_minutes"]) <= 15.0, (
        "MEXC change ses taux entre deux appels (mesuré : SOL à 0,04 % puis 0,02 % "
        "en 20 minutes) : une table qui vieillit de 30 minutes n'est plus une mesure"
    )

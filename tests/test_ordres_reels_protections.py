"""Protections et lectures d'appoint du chemin des ordres réels.

Troisième vague de tests du fichier `trading/live_order_manager_futures.py`
(objectif : sortir ce fichier de la zone « à peine testé »). Ce fichier-ci
s'occupe des fonctions autour des ordres : la vérification de taille après
envoi, l'ordre de protection posé sur l'échange, le calcul du filet quand le
robot n'a pas de stop, les minimums de contrat, le levier, les soldes, et le
mécanisme de reprise après erreur réseau.

Rien de tout ça n'appelle MEXC : les échange et client bypass sont des objets
faux qui enregistrent.
"""

import asyncio

import ccxt
import pytest

import trading.live_order_manager_futures as module
from config import TRADING_CONFIG
from trading.live_order_manager_futures import (
    LiveOrderManagerFutures,
    retry_with_backoff,
)
from trading.mexc_futures_bypass import ContractSpec, OrderSide

from tests.test_ordres_reels_bypass import (
    PAIRE,
    FauxBypass,
    FaussePosition,
    construire,
    specs_standard,
)

PAIRE_BYPASS = "BTC_USDT"


# ---------------------------------------------------------------- verification
def test_verification_de_taille_en_mode_bypass(monkeypatch):
    """Après un envoi, on relit la taille réellement ouverte chez MEXC."""
    faux = FauxBypass(positions=[FaussePosition(hold_vol=0.75)])
    gestionnaire = construire(monkeypatch, faux)

    verification = gestionnaire._verify_position_size(PAIRE, 64_000.0, retries=1, delay_sec=0)

    assert verification["contracts"] == 0.75
    assert verification["size_usdt"] == pytest.approx(0.75 * 64_000.0)
    assert verification["entry_price"] == 64_000.0


def test_verification_de_taille_en_mode_ccxt(monkeypatch):
    class FauxEchange:
        verbose = False

        def fetch_positions(self, symboles=None):
            return [
                {
                    "symbol": PAIRE,
                    "contracts": 2.0,
                    "entryPrice": 3_000.0,
                    "contractSize": 1.0,
                }
            ]

    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token="j", default_leverage=2, dry_run=False, use_bypass=False
    )
    gestionnaire.exchange = FauxEchange()

    verification = gestionnaire._verify_position_size(PAIRE, 2_900.0, retries=1, delay_sec=0)

    assert verification["contracts"] == 2.0
    assert verification["size_usdt"] == pytest.approx(6_000.0)


def test_verification_de_taille_absente_en_essai_a_blanc(monkeypatch):
    faux = FauxBypass(positions=[FaussePosition()])
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: faux)
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token="j", dry_run=True, use_bypass=True
    )
    gestionnaire.bypass_client = faux

    assert gestionnaire._verify_position_size(PAIRE, 64_000.0) is None
    assert gestionnaire._verify_position_size(PAIRE, 64_000.0, retries=1, delay_sec=0) is None


def test_verification_de_taille_sans_position(monkeypatch):
    faux = FauxBypass(positions=[])
    gestionnaire = construire(monkeypatch, faux)

    assert gestionnaire._verify_position_size(PAIRE, 64_000.0, retries=1, delay_sec=0) is None


# ------------------------------------------------------- ordre de protection SL
def test_ordre_sl_simule_en_essai_a_blanc(monkeypatch):
    faux = FauxBypass()
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: faux)
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token="j", dry_run=True, use_bypass=True
    )
    gestionnaire.bypass_client = faux

    resultat = asyncio.run(
        gestionnaire.place_stop_loss_order(PAIRE, "LONG", 62_000.0, 64_000.0)
    )

    assert resultat.success is True
    assert faux.envois == [], "un ordre de protection a été envoyé pendant un essai à blanc"


def test_ordre_sl_refuse_sans_position_a_proteger(monkeypatch):
    faux = FauxBypass(positions=[])
    gestionnaire = construire(monkeypatch, faux)

    resultat = asyncio.run(
        gestionnaire.place_stop_loss_order(PAIRE, "LONG", 62_000.0, 64_000.0)
    )

    assert resultat.success is False
    assert faux.envois == []


def test_ordre_sl_place_le_filet_chez_mexc(monkeypatch):
    faux = FauxBypass(positions=[FaussePosition(hold_vol=1.0)])
    gestionnaire = construire(monkeypatch, faux)

    resultat = asyncio.run(
        gestionnaire.place_stop_loss_order(PAIRE, "LONG", 62_000.0, 64_000.0)
    )

    # Le contournement ne sait pas poser d'ordre de stop séparé : il attache le
    # stop à l'ouverture (voir test_ouverture_long...) et, ici, il reconnaît
    # qu'il protège seulement en surveillant le prix en direct.
    assert resultat.success is True, resultat.error_message
    assert resultat.order_id.startswith("sl_realtime")
    assert [e for e in faux.envois if "side" in e] == [], (
        "le contournement ne doit pas envoyer un ordre au marché pour un stop"
    )


def test_ordre_sl_impossible_sans_bypass(monkeypatch):
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )

    resultat = asyncio.run(
        gestionnaire.place_stop_loss_order(PAIRE, "LONG", 62_000.0, 64_000.0)
    )

    assert resultat.success is False


# --------------------------------------------------------- le filet côté échange
def test_filet_calcule_quand_le_robot_n_a_pas_de_stop(monkeypatch):
    """Sans stop côté robot, on pose quand même un filet basé sur l'ATR moyen."""
    faux = FauxBypass()
    monkeypatch.setitem(TRADING_CONFIG, "atr_min", 0.15)
    monkeypatch.setitem(TRADING_CONFIG, "atr_max", 1.5)
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=20.0, bot_sl_price=None
    )

    ordre = [e for e in faux.envois if "side" in e][0]
    assert resultat.success is True, resultat.error_message
    distance = (64_000.0 - ordre["stop_loss_price"]) / 64_000.0
    # la largeur vient des réglages ATR vivants : on vérifie la bande utile, pas la valeur
    assert 0.001 < distance < 0.05, "le filet ATR doit rester dans une bande utile"


def test_filet_long_toujours_plus_large_que_le_stop_du_robot(monkeypatch):
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    gestionnaire.open_position(
        symbol=PAIRE, direction="SHORT", entry_price=64_000.0, size_usdt=20.0, bot_sl_price=66_000.0
    )

    ordre = [e for e in faux.envois if "side" in e][0]
    assert ordre["side"] == OrderSide.OPEN_SHORT
    assert ordre["stop_loss_price"] > 66_000.0, "filet SHORT au-dessus du stop du robot"
    assert ordre["stop_loss_price"] == pytest.approx(66_400.0, rel=1e-3)


def test_stop_ultra_serre_force_a_une_distance_minimale(monkeypatch):
    """Un stop collé au prix d'entrée serait déclenché par le seul spread."""
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    gestionnaire.open_position(
        symbol=PAIRE,
        direction="LONG",
        entry_price=64_000.0,
        size_usdt=20.0,
        bot_sl_price=63_999.9,
    )

    ordre = [e for e in faux.envois if "side" in e][0]
    distance = (64_000.0 - ordre["stop_loss_price"]) / 64_000.0
    assert distance >= 0.0005, "0,05 % minimum, sinon le filet saute sur le spread"


def test_filet_plafonne_quand_le_stop_du_robot_est_enorme():
    """Un robot qui demande un stop à 80 % ne doit pas faire poser n'importe quoi."""
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )

    # stop du robot à 90 % -> filet plafonné à 50 %, jamais plus large
    assert gestionnaire._prix_stop_echange("LONG", 100.0, 10.0) == pytest.approx(50.0)
    assert gestionnaire._prix_stop_echange("SHORT", 100.0, 190.0) == pytest.approx(150.0)
    assert gestionnaire._prix_stop_echange("LONG", 100.0, None) is None
    assert gestionnaire._prix_stop_echange("LONG", None, 90.0) is None
    assert gestionnaire._prix_stop_echange("LONG", 100.0, 100.0) is None


# --------------------------------------------------------- minimums de contrat
def test_minimum_de_contrat_bloque_l_ouverture(monkeypatch):
    """Sous le minimum de l'instrument, on refuse avant d'envoyer."""

    class FauxEchange:
        verbose = False
        markets = {
            PAIRE: {
                "limits": {"amount": {"min": 1.0, "max": 100.0}},
                "contractSize": 1,
                "maker": 0.0,
                "taker": 0.0,
            }
        }

        def load_markets(self):
            return self.markets

        def market(self, symbole):
            return self.markets.get(symbole)

        def amount_to_precision(self, symbole, montant):
            return float(montant)

        def create_order(self, **kw):  # ne doit jamais être appelé ici
            raise AssertionError("un ordre a été envoyé sous le minimum de contrat")

    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, default_leverage=1, dry_run=False, use_bypass=False
    )
    gestionnaire.exchange = FauxEchange()

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=20.0, bot_sl_price=63_000.0
    )

    assert resultat.success is False
    assert "insuffisante" in (resultat.error_message or "").lower()


def test_prix_d_entree_invalide_refuse(monkeypatch):
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=0.0, size_usdt=20.0, bot_sl_price=62_000.0
    )

    assert resultat.success is False
    assert faux.envois == []


# ------------------------------------------------ levier, reprises, lectures
def test_levier_enregistre_en_essai_a_blanc(monkeypatch):
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token="j", dry_run=True, use_bypass=True
    )

    assert asyncio.run(gestionnaire.set_leverage(PAIRE, 500)) is True
    assert gestionnaire._leverage_cache[PAIRE] == 125, "levier ramené dans les bornes MEXC"


def test_levier_envoye_au_compte_en_mode_bypass(monkeypatch):
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    assert asyncio.run(gestionnaire.set_leverage(PAIRE, 5)) is True
    assert any("levier" in e for e in faux.envois)


def test_reprise_apres_erreur_reseau():
    """Une erreur passagère est réessayée, une erreur franche remonte."""

    tentatives = {"n": 0}

    @retry_with_backoff(max_retries=3, base_delay=0.01)
    def fragile():
        tentatives["n"] += 1
        if tentatives["n"] < 3:
            raise ccxt.NetworkError("réseau instable")
        return "ok"

    assert fragile() == "ok"
    assert tentatives["n"] == 3

    @retry_with_backoff(max_retries=2, base_delay=0.01)
    def refuse():
        raise ccxt.ExchangeError("ordre refusé")

    with pytest.raises(ccxt.ExchangeError):
        refuse()


def test_soldes_ccxt_et_erreur(monkeypatch):
    class FauxEchange:
        verbose = False

        def fetch_balance(self):
            return {"USDT": {"free": 120.0, "total": 175.0}}

    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )
    gestionnaire.exchange = FauxEchange()

    assert gestionnaire.get_balance() == 120.0
    assert gestionnaire.get_balance_total() == 175.0
    assert gestionnaire.get_funding_rate(PAIRE) is None, "pas de funding chez ce faux échange"


def test_lecture_de_positions_sans_echange_renvoie_rien(monkeypatch):
    """Ni échange, ni bypass : on rend une liste vide, on ne casse pas."""
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )

    assert gestionnaire.get_all_positions() == []
    assert gestionnaire.emergency_close_all() == []


def test_funding_rate_venu_de_l_echange(monkeypatch):
    class FauxEchange:
        verbose = False

        def fetch_funding_rate(self, symbole):
            return {"fundingRate": 0.0001}

    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )
    gestionnaire.exchange = FauxEchange()

    assert gestionnaire.get_funding_rate(PAIRE) == pytest.approx(0.01)


class EchangePourProtections:
    """Échange CCXT faux : position ouverte + ordres enregistrés."""

    def __init__(self, erreurs=None, position_vide=False):
        self.appels = []
        self.erreurs = list(erreurs or [])
        self.position_vide = position_vide
        self.verbose = False
        self.markets = {
            PAIRE: {
                "limits": {"amount": {"min": 0.001}},
                "contractSize": 1,
                "maker": 0.0,
                "taker": 0.0,
            }
        }

    def load_markets(self):
        return self.markets

    def market(self, symbole):
        return self.markets.get(symbole)

    def amount_to_precision(self, symbole, montant):
        return float(montant)

    def fetch_positions(self, symboles=None):
        if self.position_vide:
            return []
        return [
            {
                "symbol": PAIRE,
                "contracts": 1.0,
                "entryPrice": 64_000.0,
                "markPrice": 65_000.0,
                "liquidationPrice": 60_000.0,
                "side": "long",
            }
        ]

    def fetch_funding_rate(self, symbole):
        return {"fundingRate": 0.0001}

    def create_order(self, **kw):
        self.appels.append(kw)
        if self.erreurs:
            raise self.erreurs.pop(0)
        return {
            "id": "O1",
            "status": "closed",
            "average": 65_000.0,
            "price": 65_000.0,
            "filled": kw.get("amount"),
            "fee": {"cost": 0.0},
        }


def test_lecture_position_repliee_par_le_bypass_quand_ccxt_tombe(monkeypatch):
    """Si la lecture CCXT échoue, la lecture bypass prend le relais."""

    class EchangeCoupe:
        verbose = False

        def fetch_positions(self, symboles=None):
            raise ccxt.NetworkError("réseau coupé")

    faux = FauxBypass(positions=[FaussePosition(hold_vol=1.0)])
    gestionnaire = construire(monkeypatch, faux)
    gestionnaire.exchange = EchangeCoupe()

    position = gestionnaire.get_position(PAIRE)

    assert position is not None
    assert position["contracts"] == 1.0


def test_proteccote_ccxt_attache_stop_et_take_profit(monkeypatch):
    """Les deux ordres de protection partent avec reduceOnly, en sens de sortie."""
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )
    échange = EchangePourProtections()
    gestionnaire.exchange = échange

    assert gestionnaire.set_stop_loss_take_profit(
        PAIRE, "LONG", stop_loss_price=62_000.0, take_profit_price=68_000.0
    ) is True

    types = [o["type"] for o in échange.appels]
    assert "stop_market" in types
    assert "take_profit_market" in types
    assert all(o["side"] == "sell" for o in échange.appels), "une sortie de LONG vend"
    assert all(o["params"]["reduceOnly"] for o in échange.appels)


def test_protection_impossible_sans_position(monkeypatch):
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )
    gestionnaire.exchange = EchangePourProtections(position_vide=True)

    assert gestionnaire.set_stop_loss_take_profit(PAIRE, "LONG", stop_loss_price=62_000.0) is False


def test_fermeture_ccxt_reessaie_apres_un_timeout(monkeypatch):
    """Une coupure réseau ne doit pas laisser la position ouverte sans essai."""
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )
    échange = EchangePourProtections(erreurs=[ccxt.NetworkError("réseau coupé")])
    gestionnaire.exchange = échange

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    assert resultat.success is True, resultat.error_message
    assert len(échange.appels) == 2, "deux tentatives attendues"
    assert resultat.actual_pnl_usdt == pytest.approx(1_000.0)


def test_lecture_position_en_mode_ccxt_seul(monkeypatch):
    """Sans bypass du tout, la lecture passe par la branche CCXT seule."""
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )
    gestionnaire.exchange = EchangePourProtections()

    position = gestionnaire.get_position(PAIRE, prefer_ccxt=False)

    assert position is not None
    assert position["contracts"] == 1.0
    assert position["mark_price"] == 65_000.0


def test_solde_replie_par_le_bypass_quand_ccxt_tombe(monkeypatch):
    """Le solde doit rester lisible même si la voie CCXT est bloquée."""
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    class EchangeCoupe:
        verbose = False

        def fetch_balance(self):
            raise ccxt.NetworkError("réseau coupé")

    gestionnaire.exchange = EchangeCoupe()

    assert gestionnaire.get_balance() == 250.0
    assert gestionnaire.get_balance_total() == 300.0


def test_sante_signale_les_garde_fous_absents(monkeypatch):
    """Un client sans surveillance de jeton doit le dire, pas mentir."""
    faux = FauxBypass()
    faux.token_monitor = None
    faux.rate_limiter = None
    gestionnaire = construire(monkeypatch, faux)

    sante = gestionnaire.get_health_status()

    assert sante["token_monitor"]["enabled"] is False
    assert sante["rate_limiter"]["enabled"] is False


def test_protection_refusee_quand_l_echange_grince(monkeypatch):
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )
    gestionnaire.exchange = EchangePourProtections(erreurs=[ccxt.ExchangeError("marché fermé")])

    assert gestionnaire.set_stop_loss_take_profit(PAIRE, "LONG", stop_loss_price=62_000.0) is False


def test_protection_refusee_sans_moyen_d_ecrire(monkeypatch):
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: FauxBypass())
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=False, use_bypass=False
    )

    assert gestionnaire.set_stop_loss_take_profit(PAIRE, "LONG", stop_loss_price=62_000.0) is False


def test_filet_arrondi_corrige_quand_il_touche_le_prix_d_entree(monkeypatch):
    """Sur un instrument à gros pas, l'arrondi peut coller le filet au prix d'entrée."""
    spec = ContractSpec(
        symbol="BTC_USDT",
        min_vol=0.001,
        max_vol=1000.0,
        vol_unit=0.001,
        price_unit=100.0,
        price_precision=0,
        vol_precision=3,
        contract_size=1.0,
    )
    faux = FauxBypass(spec=spec)
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE,
        direction="LONG",
        entry_price=64_000.0,
        size_usdt=20.0,
        bot_sl_price=63_999.5,
    )

    ordre = [e for e in faux.envois if "side" in e][0]
    assert resultat.success is True, resultat.error_message
    assert ordre["stop_loss_price"] < 64_000.0, "le filet doit rester sous le prix d'entrée"


def test_formes_de_symboles_acceptees():
    """BTC/USDT, BTC/USDT:USDT et BTC_USDT doivent tous se retrouver."""
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=True, use_bypass=False
    )

    assert gestionnaire._convert_symbol_to_futures("BTC/USDT") == "BTC/USDT:USDT"
    assert gestionnaire._convert_symbol_to_futures("BTC/USDT:USDT") == "BTC/USDT:USDT"
    assert gestionnaire._convert_symbol_to_bypass("BTC/USDT:USDT") == "BTC_USDT"
    assert gestionnaire._convert_symbol_to_bypass("BTC/USDT") == "BTC_USDT"


def test_arret_sur_les_arondis_de_contrat():
    """Le spécial de contrat arrondit au pas de l'instrument, jamais au-dessus du max."""
    spec = specs_standard()
    assert spec.round_volume(0.0019) == 0.001
    assert spec.round_volume(5_000.0) == 1_000.0, "plafonné au max du contrat"
    assert spec.round_price(64_000.04) == 64_000.0

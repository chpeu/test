"""Le chemin des ordres réels, testé pour de vrai.

Mesuré le 19/11/2026 : `trading/live_order_manager_futures.py` n'était couvert qu'à
21 %, avec 350 lignes de `open_position` et 231 lignes de `close_position` jamais
exécutées par un test. Les tests existants vérifiaient surtout que les fonctions
*existent* (`hasattr`) sans jamais les appeler. Or c'est exactement ce chemin-là
qui envoie l'argent chez MEXC.

Ce fichier appelle les vraies fonctions avec un faux échange, en mode réel
(`dry_run=False`), et vérifie ce qui doit se passer quand ça marche et quand ça
rate : ordre envoyé avec le levier, stop posé côté échange, position refermée si
le stop est refusé, aucune position fantôme après, aucune ouverture en essai à
blanc, fermetures toujours autorisées même pare-feu ouvert.

Aucun réseau : l'échange est un objet faux qui enregistre ce qu'on lui demande.
"""

import ccxt
import pytest

from config import TRADING_CONFIG
from trading.live_order_manager_futures import (
    FuturesOrderResult,
    LiveOrderManagerFutures,
)

PAIRE = "BTC/USDT:USDT"


class FauxEchange:
    """Un échange qui note ce qu'on lui demande au lieu d'appeler MEXC."""

    def __init__(self, positions=None, erreur_creation=None, ordre_refuse=False):
        self.appels = []
        self.positions = positions if positions is not None else []
        self.erreur_creation = erreur_creation
        self.ordre_refuse = ordre_refuse
        self.verbose = False
        self.markets = {
            PAIRE: {
                "limits": {"amount": {"min": 0.001}},
                "contractSize": 1,
                "maker": 0.0,
                "taker": 0.0,
            }
        }

    # --- lectures ---------------------------------------------------------
    def load_markets(self):
        return self.markets

    def market(self, symbole):
        return self.markets.get(symbole)

    def amount_to_precision(self, symbole, montant):
        return float(montant)

    def fetch_positions(self, symboles=None):
        self.appels.append({"methode": "fetch_positions", "symboles": symboles})
        return self.positions

    def fetch_funding_rate(self, symbole):
        return {"fundingRate": 0.0001}

    # --- écritures --------------------------------------------------------
    def create_order(self, **kw):
        self.appels.append(kw)
        if self.erreur_creation:
            raise self.erreur_creation
        if self.ordre_refuse:
            raise ccxt.ExchangeError("MEXC refuse l'ordre: stop non autorisé")
        return {
            "id": f"ORD{len(self.appels)}",
            "status": "closed",
            "average": 65_000.0,
            "price": 65_000.0,
            "filled": kw.get("amount"),
            "fee": {"cost": 0.0},
        }

    def ordres(self):
        return [a for a in self.appels if "type" in a]


def position_chez_maxe(contrats=0.5, liquidation=60_000.0, marque=65_000.0):
    return [
        {
            "symbol": PAIRE,
            "contracts": contrats,
            "entryPrice": 64_000.0,
            "markPrice": marque,
            "liquidationPrice": liquidation,
            "side": "long",
        }
    ]


@pytest.fixture
def gestionnaire_reel(monkeypatch):
    """Un gestionnaire en mode réel, sans connexion ni websocket."""
    monkeypatch.setitem(TRADING_CONFIG, "live_exige_stop_echange", True)
    gestionnaire = LiveOrderManagerFutures(
        api_key=None,
        api_secret=None,
        browser_token=None,
        default_leverage=3,
        dry_run=False,
        use_bypass=False,
    )
    return gestionnaire


def brancher(gestionnaire, faux):
    gestionnaire.exchange = faux
    return faux


def test_essai_a_blanc_ne_rien_envoyer(monkeypatch):
    """Le mode essai ne doit jamais atteindre l'échange."""
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=True, use_bypass=False
    )
    faux = brancher(gestionnaire, FauxEchange(positions=position_chez_maxe()))

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=100.0, bot_sl_price=63_000.0
    )

    assert isinstance(resultat, FuturesOrderResult)
    assert faux.ordres() == [], "un ordre est parti chez l'échange pendant un essai à blanc"
    assert gestionnaire.stats["orders_placed"] == 0


def test_en_reel_l_ordre_et_le_stop_partent(gestionnaire_reel):
    """L'ordre d'ouverture et le filet de sécurité vont tous les deux chez MEXC."""
    faux = brancher(gestionnaire_reel, FauxEchange(positions=position_chez_maxe()))

    resultat = gestionnaire_reel.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=120.0, bot_sl_price=62_000.0
    )

    assert resultat.success is True
    ordres = faux.ordres()
    ouverture = [o for o in ordres if o["type"] == "market"][0]
    assert ouverture["side"] == "buy"
    assert ouverture["params"]["leverage"] == "3"
    assert ouverture["params"]["openType"] == 1
    assert ouverture["params"]["positionType"] == 1

    stop = [o for o in ordres if o["type"] == "stop_market"]
    assert stop, "le stop côté échange n'a jamais été envoyé"
    assert stop[0]["side"] == "sell", "un stop de LONG doit vendre"
    assert stop[0]["params"]["reduceOnly"] is True
    assert resultat.exchange_stop_price


def test_stop_refuse_la_prise_est_refermee_et_pas_la(gestionnaire_reel):
    """Stop refusé deux fois -> on referme, et le résultat dit « échec ».

    C'est le bug trouvé en écrivant ces tests : l'ordre partait, le stop était
    refusé, la position était refermée dans la foulée — et le gestionnaire
    répondait quand même « succès ». Le robot gardait donc une position que
    l'échange n'avait plus.
    """
    faux = brancher(gestionnaire_reel, FauxEchange(positions=[]))  # pas de position -> stop refusé

    resultat = gestionnaire_reel.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=120.0, bot_sl_price=62_000.0
    )

    fermetures = [
        o
        for o in faux.ordres()
        if o["type"] == "market" and o["params"].get("reduceOnly") is True
    ]
    assert fermetures, "la position nue n'a pas été refermée chez MEXC"
    assert fermetures[0]["side"] == "sell"
    assert resultat.success is False
    assert resultat.auto_fermee_sans_stop is True
    assert "referm" in (resultat.error_message or "")


def test_un_echec_reseau_ne_compte_pas_comme_prise(gestionnaire_reel):
    """Timeout réseau -> pas de position, un échec de plus, et le pare-feu compte."""
    faux = brancher(
        gestionnaire_reel, FauxEchange(erreur_creation=ccxt.NetworkError("réseau coupé"))
    )

    resultat = gestionnaire_reel.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=100.0, bot_sl_price=63_000.0
    )

    assert resultat.success is False
    assert len(faux.ordres()) == 2, "deux tentatives, pas plus"
    assert gestionnaire_reel.stats["orders_failed"] == 1
    assert gestionnaire_reel.stats["orders_filled"] == 0
    assert gestionnaire_reel.stats["orders_placed"] == 0
    assert gestionnaire_reel.circuit_breaker.failure_count >= 1


def test_fermeture_toujours_autorisee_pare_feu_ouvert(gestionnaire_reel):
    """Pare-feu ouvert = plus d'ouverture, mais la fermeture reste possible.

    Une position déjà ouverte doit pouvoir sortir même quand les ordres d'entrée
    sont gelés : bloquer la sortie serait la pire des choses.
    """
    faux = brancher(gestionnaire_reel, FauxEchange(positions=position_chez_maxe()))
    for _ in range(5):
        gestionnaire_reel.circuit_breaker.record_failure()

    ouverture = gestionnaire_reel.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=100.0, bot_sl_price=63_000.0
    )
    assert ouverture.success is False
    assert "Circuit breaker" in (ouverture.error_message or "")

    fermeture = gestionnaire_reel.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=0.5
    )
    assert fermeture.success is True
    ordres_de_sortie = [
        o for o in faux.ordres() if o["type"] == "market" and o["params"].get("reduceOnly")
    ]
    assert ordres_de_sortie, "la fermeture a été bloquée par le pare-feu"


def test_fermeture_partielle_utilise_la_quantite_demantee(gestionnaire_reel):
    faux = brancher(gestionnaire_reel, FauxEchange(positions=position_chez_maxe(contrats=1.0)))

    gestionnaire_reel.close_position(
        symbol=PAIRE,
        direction="LONG",
        entry_price=64_000.0,
        current_price=65_000.0,
        size_amount=1.0,
        partial_pct=50.0,
    )

    sortie = [o for o in faux.ordres() if o["params"].get("reduceOnly")]
    assert sortie, "aucun ordre de fermeture partielle envoyé"
    assert 0 < sortie[0]["amount"] <= 1.0


def test_pnl_reel_calcule_dans_le_bon_sens(gestionnaire_reel):
    """Un LONG rempli plus haut doit donner un gain positif."""
    brancher(gestionnaire_reel, FauxEchange(positions=position_chez_maxe()))

    resultat = gestionnaire_reel.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=64_500.0, size_amount=0.5
    )

    assert resultat.success is True
    assert resultat.actual_pnl_usdt > 0


def test_risque_de_liquidation_long(gestionnaire_reel):
    """LONG : le prix de liquidation est en dessous, la distance se mesure vers le bas."""
    brancher(gestionnaire_reel, FauxEchange(positions=position_chez_maxe(liquidation=64_000.0)))

    a_risque, distance = gestionnaire_reel.check_liquidation_risk(PAIRE, threshold_pct=5.0)

    assert distance == pytest.approx(1.538, abs=0.01)
    assert a_risque is True


def test_risque_de_liquidation_short(gestionnaire_reel):
    """SHORT : le prix de liquidation est au-dessus, la distance se mesure vers le haut."""
    brancher(
        gestionnaire_reel,
        FauxEchange(
            positions=[
                {
                    "symbol": PAIRE,
                    "contracts": 0.5,
                    "entryPrice": 64_000.0,
                    "markPrice": 65_000.0,
                    "liquidationPrice": 66_000.0,
                    "side": "short",
                }
            ]
        ),
    )

    a_risque, distance = gestionnaire_reel.check_liquidation_risk(PAIRE, threshold_pct=5.0)

    assert distance == pytest.approx(1.538, abs=0.01)
    assert a_risque is True


def test_pas_de_position_pas_de_risque(gestionnaire_reel):
    brancher(gestionnaire_reel, FauxEchange(positions=[]))
    a_risque, distance = gestionnaire_reel.check_liquidation_risk(PAIRE)
    assert a_risque is False
    assert distance == 100.0


def test_urgence_referme_toutes_les_positions(gestionnaire_reel):
    """Bouton d'urgence : chaque position ouverte reçoit son ordre de sortie."""
    faux = brancher(
        gestionnaire_reel,
        FauxEchange(
            positions=[
                {"symbol": PAIRE, "contracts": 0.5, "side": "long", "entryPrice": 64_000.0},
                {
                    "symbol": "ETH/USDT:USDT",
                    "contracts": 2.0,
                    "side": "short",
                    "entryPrice": 3_000.0,
                },
            ]
        ),
    )

    gestionnaire_reel.emergency_close_all()

    sorties = [o for o in faux.ordres() if o["params"].get("reduceOnly")]
    symboles = {o["symbol"] for o in sorties}
    assert PAIRE in symboles
    assert len(sorties) >= 2


def test_rien_a_lire_en_essai_a_blanc():
    """En essai à blanc, ces lectures ne doivent pas toucher l'échange."""
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token=None, dry_run=True, use_bypass=False
    )
    faux = brancher(gestionnaire, FauxEchange(positions=position_chez_maxe()))

    assert gestionnaire.get_all_positions() == []
    assert faux.appels == [], "une lecture a atteint l'échange en essai à blanc"


def test_la_solde_sans_ordre_est_ecrite_dans_le_gestionnaire_de_position():
    """Filet sur le correctif côté robot : la prise refermée est soldée, pas gardée.

    Sans ça, `core/position_manager.py` continue de suivre une position que
    l'échange n'a plus, puis envoie un ordre de fermeture sur du vide à la sortie.
    """
    import inspect

    from core.position_manager import PositionManager

    source = inspect.getsource(PositionManager.open_position)
    assert "auto_fermee_sans_stop" in source
    assert "STOP_ECHANGE_IMPOSSIBLE" in source
    assert "skip_order=True" in source, "la solde ne doit pas renvoyer d'ordre chez MEXC"

"""Le mode bypass (jeton navigateur) des ordres réels, testé pour de vrai.

Le robot utilisera ce chemin-là en trading réel si un jeton navigateur est
configuré : `use_bypass=True`, donc `self.exchange` reste à None. Or la branche
bypass de `open_position` (environ 600 lignes) et celle de `close_position`
n'étaient exécutées par aucun test.

Écriture de ces tests = deux bugs sortis (mesuré 19/11/2026) :

- `get_all_positions()` appelait `self.exchange.fetch_positions()` sans regarder
  le mode bypass : `self.exchange` valant None, la fonction renvoyait une liste
  vide, donc le bouton « fermer tout » ne fermait rien ;
- `emergency_close_all()` faisait de même et n'envoyait aucun ordre en mode
  bypass. Les deux passent maintenant par la même porte de sortie que le reste
  (`close_position`), qui connaît les deux modes.

Aucun réseau : le faux client bypass enregistre ce qu'on lui demande.
"""

from types import SimpleNamespace

import ccxt
import pytest

import trading.live_order_manager_futures as module
from config import TRADING_CONFIG
from trading.live_order_manager_futures import LiveOrderManagerFutures
from trading.mexc_futures_bypass import ContractSpec, OrderSide, OrderType

PAIRE = "BTC/USDT:USDT"
PAIRE_BYPASS = "BTC_USDT"


class FaussePosition:
    """Une position telle que le client bypass la renvoie."""

    def __init__(
        self,
        symbol=PAIRE_BYPASS,
        hold_vol=1.0,
        hold_avg_price=64_000.0,
        position_type=1,
        mark_price=65_000.0,
        unrealized_pnl=5.0,
        liquidate_price=60_000.0,
        margin=100.0,
        leverage=3,
    ):
        self.symbol = symbol
        self.hold_vol = hold_vol
        self.hold_avg_price = hold_avg_price
        self.position_type = position_type
        self.mark_price = mark_price
        self.unrealized_pnl = unrealized_pnl
        self.liquidate_price = liquidate_price
        self.margin = margin
        self.leverage = leverage


def specs_standard():
    """Spécial de contrat au format BTC : 1 contrat = 1 token, pas à 0,1."""
    return ContractSpec(
        symbol=PAIRE_BYPASS,
        min_vol=0.001,
        max_vol=1000.0,
        vol_unit=0.001,
        price_unit=0.1,
        price_precision=1,
        vol_precision=3,
        contract_size=1.0,
    )


class FauxBypass:
    def __init__(
        self,
        spec=None,
        positions=None,
        echec_envoi=False,
        rejet_silencieux=False,
        ordre_rejete=False,
        prix_rempli=None,
    ):
        self.envois = []
        self.lectures = 0
        self.spec = spec if spec is not None else specs_standard()
        self.positions = list(positions or [])
        self.echec_envoi = echec_envoi
        self.rejet_silencieux = rejet_silencieux
        self.ordre_rejete = ordre_rejete
        self.prix_rempli = prix_rempli
        self._numero = 0
        self.token_monitor = SimpleNamespace(
            last_check_time=0.0, check_interval=300, is_token_valid=True
        )
        self.rate_limiter = SimpleNamespace(
            current_rate=1.0,
            min_rate=0.5,
            max_rate=5.0,
            consecutive_429s=0,
            consecutive_200s=3,
        )

    async def get_contract_spec(self, symbol=None):
        return self.spec

    async def set_leverage(self, **kw):
        self.envois.append({"levier": kw})
        return True

    async def submit_order(self, **kw):
        self.envois.append(kw)
        if self.echec_envoi:
            return SimpleNamespace(
                success=False,
                order_id=None,
                data=None,
                error_message="compte refusé par MEXC",
            )
        self._numero += 1
        return SimpleNamespace(
            success=True,
            order_id=str(self._numero),
            data={"orderId": self._numero},
            error_message=None,
        )

    async def get_order(self, order_id):
        if self.rejet_silencieux:
            return {"success": False, "code": 1001, "message": "ordre introuvable"}
        if self.ordre_rejete:
            return {"success": True, "data": {"state": 4}}
        return {"success": True, "data": {"state": 2, "dealAvgPrice": self.prix_rempli}}

    async def get_open_positions(self, symbol=None):
        self.lectures += 1
        if symbol is None:
            return list(self.positions)
        return [p for p in self.positions if p.symbol == symbol]

    async def get_account_asset(self, currency="USDT"):
        return SimpleNamespace(available_balance=250.0, frozen_balance=50.0)


def construire(monkeypatch, faux):
    """Un gestionnaire en mode bypass, sans réseau."""
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: faux)
    monkeypatch.setitem(TRADING_CONFIG, "live_exige_stop_echange", True)
    gestionnaire = LiveOrderManagerFutures(
        api_key=None,
        api_secret=None,
        browser_token="jeton-faux",
        default_leverage=3,
        dry_run=False,
        use_bypass=True,
    )
    gestionnaire.bypass_client = faux
    gestionnaire._read_rate_limit_sec = 0.0  # pas d'attente dans les tests
    return gestionnaire


def test_ouverture_long_part_avec_le_filet_de_securite(monkeypatch):
    """L'ordre et le prix du stop partent dans le même envoi, sans take profit."""
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE,
        direction="LONG",
        entry_price=64_000.0,
        size_usdt=20.0,
        bot_sl_price=62_000.0,
    )

    ordre = [e for e in faux.envois if "side" in e][0]
    assert resultat.success is True, resultat.error_message
    assert ordre["side"] == OrderSide.OPEN_LONG
    assert ordre["order_type"] == OrderType.MARKET
    assert ordre["leverage"] == 3
    assert ordre["take_profit_price"] is None, "le take profit reste la main du robot"
    # Le filet chez MEXC doit être PLUS LARGE que le stop du robot : sinon
    # l'échange coupe avant le robot et le suivi devient faux.
    assert ordre["stop_loss_price"] < 62_000.0, "le filet doit rester sous le stop du robot"
    assert ordre["stop_loss_price"] == pytest.approx(61_600.0, rel=1e-3)


def test_le_levier_est_regie_avant_ordre(monkeypatch):
    """Marge isolée : sans levier réglé avant, MEXC refuse ou sur-levier."""
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=20.0, bot_sl_price=62_000.0
    )

    assert "levier" in faux.envois[0], "le levier aurait dû être réglé en premier"
    assert faux.envois[0]["levier"]["leverage"] == 3


def test_taille_minimale_relevee_a_6_usdt(monkeypatch):
    """20 USDT sur BTC arrondi à 0 contrat -> la taille est remontée au minimum."""
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=20.0, bot_sl_price=62_000.0
    )

    ordre = [e for e in faux.envois if "side" in e][0]
    valeur_envoyee = ordre["vol"] * ordre["price"] * faux.spec.contract_size
    assert ordre["vol"] == 0.001, "arrondi au pas de contrat attendu"
    assert valeur_envoyee >= 6.0, "MEXC refuse sous 5 USDT, la marge est à 6"
    assert resultat.filled_size_usdt >= 6.0


def test_rejet_silencieux_ne_compte_pas_comme_prise(monkeypatch):
    """MEXC accepte l'envoi puis ne retrouve pas l'ordre -> échec, échec compté."""
    faux = FauxBypass(rejet_silencieux=True, positions=[FaussePosition(hold_vol=1.0)])
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=20.0, bot_sl_price=62_000.0
    )

    assert resultat.success is False
    assert "Rejet silencieux" in (resultat.error_message or "")
    assert gestionnaire.stats["orders_failed"] == 1
    assert gestionnaire.stats["orders_filled"] == 0
    assert gestionnaire.circuit_breaker.failure_count == 1


def test_ordre_explicitement_rejete(monkeypatch):
    faux = FauxBypass(ordre_rejete=True)
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=20.0, bot_sl_price=62_000.0
    )

    assert resultat.success is False
    assert "rejeté" in (resultat.error_message or "").lower()
    assert gestionnaire.circuit_breaker.failure_count == 1


def test_refus_de_envoi_remonte_la_raison(monkeypatch):
    faux = FauxBypass(echec_envoi=True)
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=20.0, bot_sl_price=62_000.0
    )

    assert resultat.success is False
    assert "compte refusé par MEXC" in (resultat.error_message or "")


def test_le_prix_rempli_reel_est_utilise(monkeypatch):
    """Le prix payé vraiment vient de MEXC, pas du prix demandé."""
    faux = FauxBypass(prix_rempli=65_000.0)
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=20.0, bot_sl_price=62_000.0
    )

    assert resultat.filled_price == 65_000.0
    assert resultat.actual_slippage_pct == pytest.approx(1.5625, abs=0.01)


def test_specs_absentes_arrondi_basique(monkeypatch):
    """Sans spécial de contrat, on garde un ordre utilisable, pas un ordre vide."""
    faux = FauxBypass(spec=None)
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=10.0, size_usdt=25.0, bot_sl_price=9.0
    )

    ordre = [e for e in faux.envois if "side" in e][0]
    assert resultat.success is True, resultat.error_message
    assert ordre["vol"] > 0


def test_fermeture_long_envoie_reduce_only(monkeypatch):
    faux = FauxBypass(positions=[FaussePosition(hold_vol=1.0)])
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    ordre = [e for e in faux.envois if "side" in e][-1]
    assert resultat.success is True, resultat.error_message
    assert ordre["side"] == OrderSide.CLOSE_LONG
    assert ordre["reduce_only"] is True, "une fermeture ne doit jamais rouvrir de place"


def test_fermeture_short_envoie_dans_l_autre_sens(monkeypatch):
    faux = FauxBypass(positions=[FaussePosition(hold_vol=2.0, position_type=2)])
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="SHORT", entry_price=64_000.0, current_price=63_000.0, size_amount=2.0
    )

    ordre = [e for e in faux.envois if "side" in e][-1]
    assert resultat.success is True, resultat.error_message
    assert ordre["side"] == OrderSide.CLOSE_SHORT


def test_on_ne_ferme_pas_plus_que_ce_qu_on_a(monkeypatch):
    """Garde-fou : fermer 2 contrats alors qu'on en tient 0,4 -> on ajuste à 0,4."""
    faux = FauxBypass(positions=[FaussePosition(hold_vol=0.4)])
    gestionnaire = construire(monkeypatch, faux)

    gestionnaire.close_position(
        symbol=PAIRE,
        direction="LONG",
        entry_price=64_000.0,
        current_price=65_000.0,
        size_amount=2.0,
        partial_pct=50.0,
    )

    ordre = [e for e in faux.envois if "side" in e][-1]
    assert ordre["vol"] == pytest.approx(0.4)


def test_position_disparue_compte_comme_fermee(monkeypatch):
    """Filet déclenché chez MEXC pendant la fermeture : la place est bien fermée."""
    faux = FauxBypass(rejet_silencieux=True, positions=[])
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    assert resultat.success is True
    assert resultat.order_id == "sl_exchange_race_condition"


def test_lecture_des_positions_en_mode_bypass(monkeypatch):
    """Bug corrigé : cette lecture renvoyait une liste vide en mode bypass."""
    faux = FauxBypass(
        positions=[
            FaussePosition(hold_vol=1.0),
            FaussePosition(
                symbol="ETH_USDT",
                hold_vol=2.0,
                hold_avg_price=3_000.0,
                position_type=2,
                mark_price=2_950.0,
            ),
        ]
    )
    gestionnaire = construire(monkeypatch, faux)

    positions = gestionnaire.get_all_positions()

    assert len(positions) == 2
    assert positions[0]["side"] == "long"
    assert positions[0]["mark_price"] == 65_000.0
    assert positions[1]["side"] == "short"
    assert positions[1]["size"] == 2.0


def test_urgence_referme_tout_en_mode_bypass(monkeypatch):
    """Le bouton d'urgence doit fermer, même sans accès CCXT."""
    faux = FauxBypass(
        positions=[
            FaussePosition(hold_vol=1.0),
            FaussePosition(symbol="ETH_USDT", hold_vol=2.0, position_type=2, hold_avg_price=3_000.0),
        ]
    )
    gestionnaire = construire(monkeypatch, faux)

    resultats = gestionnaire.emergency_close_all()

    sorties = [e for e in faux.envois if e.get("reduce_only")]
    assert len(sorties) == 2, "une position est restée ouverte après l'urgence"
    assert {o["side"] for o in sorties} == {OrderSide.CLOSE_LONG, OrderSide.CLOSE_SHORT}
    assert all(r.success for r in resultats), [r.error_message for r in resultats]


def test_fermeture_rejetee_alors_qu_on_tient_toujours_la_place(monkeypatch):
    """Refus explicite + position encore là : c'est un échec, pas une sortie."""
    faux = FauxBypass(ordre_rejete=True, positions=[FaussePosition(hold_vol=1.0)])
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    assert resultat.success is False
    assert "rejet" in (resultat.error_message or "").lower()
    assert gestionnaire.stats["orders_failed"] == 1


def test_prix_de_sortie_reel_utilise_pas_le_prix_demande(monkeypatch):
    """Le prix obtenu chez MEXC remplace le prix demandé, et l'écart est mesuré."""
    faux = FauxBypass(positions=[FaussePosition(hold_vol=1.0)], prix_rempli=65_500.0)
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    assert resultat.filled_price == 65_500.0
    assert resultat.actual_slippage_pct == pytest.approx(0.769, abs=0.01)


def test_deja_fermee_du_cote_de_mexc_compte_comme_sortie(monkeypatch):
    """Code 2009 : la place n'existe plus, donc la fermeture est réussie."""

    class BypassDejaFermee(FauxBypass):
        async def submit_order(self, **kw):
            self.envois.append(kw)
            return SimpleNamespace(
                success=False,
                order_id=None,
                data=None,
                error_message="code 2009: Position is nonexistent or closed",
            )

    faux = BypassDejaFermee(positions=[])
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    assert resultat.success is True
    assert resultat.order_id == "already_closed"


def test_fermeture_rejetee_mais_place_deja_disparue(monkeypatch):
    """Refus explicite + plus rien chez MEXC : le filet a fait le travail."""
    faux = FauxBypass(ordre_rejete=True, positions=[])
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    assert resultat.success is True
    assert resultat.order_id == "sl_exchange_race_condition"


def test_partiel_impossible_force_a_fermer_le_reste(monkeypatch):
    """Un take profit partiel plus petit que le pas du contrat ferme quand même 100 %.

    Sans ce repli, la part restante resterait ouverte sans surveillance : le robot
    croirait avoir pris son profit et il garderait une miette de position.
    """
    spec = ContractSpec(
        symbol="DOGE_USDT",
        min_vol=1.0,
        max_vol=1e9,
        vol_unit=1.0,
        price_unit=0.0001,
        price_precision=4,
        vol_precision=0,
        contract_size=1.0,
    )
    faux = FauxBypass(spec=spec, positions=[FaussePosition(symbol="DOGE_USDT", hold_vol=1.0)])
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: faux)
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token="j", dry_run=False, use_bypass=True
    )
    gestionnaire.bypass_client = faux
    gestionnaire._read_rate_limit_sec = 0.0

    resultat = gestionnaire.close_position(
        symbol="DOGE/USDT:USDT",
        direction="LONG",
        entry_price=0.3,
        current_price=0.32,
        size_amount=1.0,
        partial_pct=10.0,
    )

    ordre = [e for e in faux.envois if "side" in e][-1]
    assert resultat.success is True, resultat.error_message
    assert resultat.forced_full_close is True
    assert ordre["vol"] == 1.0, "10 % d'un seul contrat = 0 -> on ferme le contrat entier"


def test_fermeture_sans_special_de_contrat(monkeypatch):
    """Sans infos de contrat, on arrondit simplement, on ne bloque pas la sortie."""
    faux = FauxBypass(spec=None, positions=[FaussePosition()])
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    assert resultat.success is True, resultat.error_message
    assert [e for e in faux.envois if e.get("reduce_only")]


def test_urgence_qui_n_est_pas_reussie_le_dit(monkeypatch):
    """Si MEXC plante pendant l'urgence, chaque échec est remonté, pas avalé."""

    class BypassQuiExplose(FauxBypass):
        async def submit_order(self, **kw):
            self.envois.append(kw)
            raise ccxt.NetworkError("réseau coupé")

    faux = BypassQuiExplose(positions=[FaussePosition(hold_vol=1.0)])
    gestionnaire = construire(monkeypatch, faux)

    resultats = gestionnaire.emergency_close_all()

    assert len(resultats) == 1
    assert resultats[0].success is False


def test_soldes_venus_du_compte_bypass(monkeypatch):
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    assert gestionnaire.get_balance() == 250.0
    assert gestionnaire.get_balance_total() == 300.0, "total = disponible + marge bloquée"


def test_position_lue_en_mode_bypass(monkeypatch):
    faux = FauxBypass(positions=[FaussePosition(hold_vol=1.0)])
    gestionnaire = construire(monkeypatch, faux)

    position = gestionnaire.get_position(PAIRE)

    assert position is not None
    assert position["contracts"] == 1.0
    assert position["entry_price"] == 64_000.0
    assert position["mark_price"] == 65_000.0
    assert position["side"] == "long"

    sync = gestionnaire.sync_position(PAIRE)
    assert sync["size"] == pytest.approx(64_000.0)


def test_tableau_de_sante(monkeypatch):
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    sante = gestionnaire.get_health_status()

    assert sante["mode"] == "bypass"
    assert sante["circuit_breaker"]["enabled"] is True
    assert sante["token_monitor"]["enabled"] is True
    assert sante["rate_limiter"]["enabled"] is True
    assert sante["system"]["success_rate_pct"] == 0.0


def test_contrat_de_mille_tokens_converti_en_contrats(monkeypatch):
    """Sur un contrat à 1000 tokens l'unité, la taille est divisée par 1000."""
    spec = ContractSpec(
        symbol="SHIB_USDT",
        min_vol=1.0,
        max_vol=1e9,
        vol_unit=1.0,
        price_unit=0.000001,
        price_precision=6,
        vol_precision=0,
        contract_size=1000.0,
    )
    faux = FauxBypass(spec=spec)
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: faux)
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token="j", default_leverage=3, dry_run=False, use_bypass=True
    )
    gestionnaire.bypass_client = faux
    gestionnaire._read_rate_limit_sec = 0.0

    resultat = gestionnaire.open_position(
        symbol="SHIB/USDT:USDT",
        direction="LONG",
        entry_price=0.00002,
        size_usdt=20.0,
        bot_sl_price=0.000019,
    )

    ordre = [e for e in faux.envois if "side" in e][0]
    assert resultat.success is True, resultat.error_message
    assert ordre["vol"] == 1_000.0, "20 USDT / 0,00002 / 1000 = 1000 contrats"
    assert resultat.contract_size == 1000.0
    assert resultat.filled_size_usdt == pytest.approx(1_000.0 * 0.00002 * 1000.0)


def test_taille_demands_depassant_le_compte_refusee(monkeypatch):
    """100 000 USDT de marge sur un compte à 250 USDT : on refuse, on n'envoie pas."""
    faux = FauxBypass()
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.open_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, size_usdt=100_000.0, bot_sl_price=62_000.0
    )

    assert resultat.success is False
    assert [e for e in faux.envois if "side" in e] == [], "l'ordre ne devait pas partir"


def test_fermeture_simulee_en_essai_a_blanc(monkeypatch):
    """La fermeture papier calcule le gain, sans toucher l'échange."""
    faux = FauxBypass(positions=[FaussePosition()])
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: faux)
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token="j", dry_run=True, use_bypass=True
    )
    gestionnaire.bypass_client = faux

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    assert resultat.success is True
    assert resultat.order_id.startswith("dry_run_close_futures")
    assert gestionnaire.stats["total_pnl_usdt"] == pytest.approx(1_000.0)
    assert faux.envois == [], "une fermeture a atteint l'échange pendant un essai à blanc"


def test_rejet_silencieux_de_fermeture_alors_que_la_place_est_la(monkeypatch):
    """Envoi accepté, ordre introuvable, et la place est toujours ouverte : échec."""
    faux = FauxBypass(rejet_silencieux=True, positions=[FaussePosition(hold_vol=1.0)])
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    assert resultat.success is False
    assert "Rejet silencieux fermeture" in (resultat.error_message or "")
    assert gestionnaire.stats["orders_failed"] == 1


def test_refus_de_fermeture_remonte_la_raison(monkeypatch):
    """Un refus qui n'est pas « déjà fermée » doit rester un échec visible."""

    class BypassRefus(FauxBypass):
        async def submit_order(self, **kw):
            self.envois.append(kw)
            return SimpleNamespace(
                success=False,
                order_id=None,
                data=None,
                error_message="marge insuffisante pour modifier la position",
            )

    faux = BypassRefus(positions=[FaussePosition(hold_vol=1.0)])
    gestionnaire = construire(monkeypatch, faux)

    resultat = gestionnaire.close_position(
        symbol=PAIRE, direction="LONG", entry_price=64_000.0, current_price=65_000.0, size_amount=1.0
    )

    assert resultat.success is False
    assert "marge insuffisante" in (resultat.error_message or "")


def test_fermeture_sur_contrat_de_mille_tokens(monkeypatch):
    """Fermer des tokens sur un contrat à 1000 : la quantité est convertie."""
    spec = ContractSpec(
        symbol="SHIB_USDT",
        min_vol=1.0,
        max_vol=1e9,
        vol_unit=1.0,
        price_unit=0.000001,
        price_precision=6,
        vol_precision=0,
        contract_size=1000.0,
    )
    faux = FauxBypass(spec=spec, positions=[FaussePosition(symbol="SHIB_USDT", hold_vol=1000.0)])
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: faux)
    gestionnaire = LiveOrderManagerFutures(
        api_key=None, api_secret=None, browser_token="j", dry_run=False, use_bypass=True
    )
    gestionnaire.bypass_client = faux
    gestionnaire._read_rate_limit_sec = 0.0

    resultat = gestionnaire.close_position(
        symbol="SHIB/USDT:USDT",
        direction="LONG",
        entry_price=0.00002,
        current_price=0.000021,
        size_amount=1000.0,
    )

    ordre = [e for e in faux.envois if "side" in e][-1]
    assert resultat.success is True, resultat.error_message
    assert ordre["vol"] > 0
    assert ordre["reduce_only"] is True


def test_rien_ne_bouge_en_essai_a_blanc(monkeypatch):
    faux = FauxBypass(positions=[FaussePosition()])
    monkeypatch.setattr(module, "MexcFuturesBypass", lambda **kw: faux)
    gestionnaire = LiveOrderManagerFutures(
        api_key=None,
        api_secret=None,
        browser_token="jeton-faux",
        dry_run=True,
        use_bypass=True,
    )
    gestionnaire.bypass_client = faux

    assert gestionnaire.get_all_positions() == []
    assert gestionnaire.get_balance() == 0.0
    assert gestionnaire.get_position(PAIRE) is None
    assert gestionnaire.emergency_close_all()[0].order_id == "emergency_dry_run"
    assert faux.lectures == 0, "une lecture a atteint l'échange en essai à blanc"

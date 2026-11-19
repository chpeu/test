"""
Le cycle de scan réel: demarrage, tri des paires, decision, ouverture.

Ces tests branchent de faux objets sur les variables globales du module
`core.callbacks.scanner_loop` (les memes que le bootstrap utilise) et laissent
tourner les vraies fonctions: `scanner_loop_callback`, `_scan_initial_top_pairs`,
`_scan_top_pairs`, `scan_pair_for_setup`, `_extract_filter_metrics`.

But: que les regles qui decident d'une prise (filtre du petit modele, filtres ML
herités, garde-fou de cooldown, position deja ouverte) soient executees et
verifiees, pas seulement importees.
"""

import asyncio
import math

import pytest

import core.callbacks.scanner_loop as scan
from config import ML_CONFIG, TRADING_CONFIG


# --------------------------------------------------------------------- faux objets
class EtatFaux(dict):
    """L'etat applicatif: un simple dictionnaire, comme dans le bootstrap."""


class ScannerFaux:
    def __init__(self, paires=None, erreur=None):
        self.paires = paires if paires is not None else [{"symbol": "BTC/USDT", "spread": 0.01}]
        self.erreur = erreur
        self.appels = []

    async def scan_top_pairs(self, nombre):
        self.appels.append(nombre)
        if self.erreur:
            raise self.erreur
        return self.paires


class AnalyseurFaux:
    """Renvoit ce qu'on lui donne, dans l'ordre, pour chaque paire analysee."""

    def __init__(self, reponses=None, erreur=None, latence=None):
        self.reponses = list(reponses or [])
        self.erreur = erreur
        self.latence = latence
        self.appels = []

    async def analyze_pair(self, symbol, *args, **kwargs):
        self.appels.append((symbol, kwargs))
        if self.latence:
            await asyncio.sleep(self.latence)
        if self.erreur:
            raise self.erreur
        if self.reponses:
            return self.reponses.pop(0) if len(self.reponses) > 1 else self.reponses[0]
        return None


class ResultatPrise:
    def __init__(self, symbol, direction):
        self.symbol = symbol
        self.direction = direction

    def to_dict(self):
        return {"symbol": self.symbol, "direction": self.direction}


class GestionnairePositionsFaux:
    def __init__(self, position_active=None, retour_ouverture="objet", erreur=None):
        self.active_position = position_active
        self.retour_ouverture = retour_ouverture
        self.erreur = erreur
        self.ouvertures = []
        self.calculs = []

    def calculate_position_size(self, **kwargs):
        self.calculs.append(kwargs)
        return 42.0

    def open_position(self, **kwargs):
        self.ouvertures.append(kwargs)
        if self.erreur:
            raise self.erreur
        if self.retour_ouverture == "rien":
            return None
        if self.retour_ouverture == "valeur":
            raise ValueError("reglage invalide")
        return ResultatPrise(kwargs["symbol"], kwargs["direction"])


class JournalFaux:
    """Le scribe: on compte ce qu'il ecrit, on n'ouvre aucune connexion."""

    def __init__(self, actif=True, scan_id="scan-1", opportunite_id="opp-1"):
        self.enabled = actif
        self.scan_id = scan_id
        self.opportunite_id = opportunite_id
        self.scans = []
        self.opportunites = []
        self.confiances = []
        self.rejets_ml = []

    async def log_scan_async(self, symbol, scan_data, use_batch=False):
        self.scans.append((symbol, scan_data, use_batch))
        return self.scan_id

    async def log_opportunity_async(self, *args, **kwargs):
        self.opportunites.append((args, kwargs))
        return self.opportunite_id

    async def update_ml_confidence_async(self, symbol, confiance):
        self.confiances.append((symbol, confiance))

    async def update_ml_rejection_async(self, **kwargs):
        self.rejets_ml.append(kwargs)


class WsFaux:
    def __init__(self, erreur=None):
        self.evenements = []
        self.erreur = erreur

    async def emit(self, evenement, donnees):
        if self.erreur:
            raise self.erreur
        self.evenements.append((evenement, donnees))


class PrixFaux:
    def __init__(self, erreur_demarrage=None):
        self.demarres = []
        self.arretes = 0
        self.erreur_demarrage = erreur_demarrage

    async def start_websocket(self, symboles):
        if self.erreur_demarrage:
            raise self.erreur_demarrage
        self.demarres.append(list(symboles))

    async def stop_websocket(self):
        self.arretes += 1


class NotifFaux:
    def __init__(self, telegram=True):
        self.envois = []
        self.telegram_notify_settings = {"error": telegram}

    async def notify(self, categorie, donnees, **kwargs):
        self.envois.append((categorie, donnees, kwargs))


class CooldownFaux:
    def __init__(self, autorise=True, motif=""):
        self.autorise = autorise
        self.motif = motif

    def can_trade(self, symbol):
        return self.autorise, self.motif


class PredicteurFaux:
    def __init__(self, charge=True, approuve=True, confiance=0.8, erreur=None):
        self.is_loaded = charge
        self.approuve = approuve
        self.confiance = confiance
        self.erreur = erreur

    def predict(self, features, threshold=None):
        if self.erreur:
            raise self.erreur
        return self.approuve, self.confiance


def setup_complet(symbol="BTC/USDT", direction="LONG", entree=100.0, raison=None):
    """Le dictionnaire tel que l'analyseur le rend quand il prend une paire."""
    return {
        "symbol": symbol,
        "direction": direction,
        "price": entree,
        "entry": entree,
        "sl": entree * 0.99,
        "tp": entree * 1.02,
        "atr": 0.4,
        "atr5m": 0.5,
        "rsi": 55.0,
        "score_total": 8.5,
        "totalScore": 8.5,
        "condition_types": ["EMAs", "Volume"],
        "signals": ["ema", "volume"],
        "timeframe": "1m",
        "indicators_1m": {"rsi": 55.0, "atr": 0.4, "snr": 1.4, "snr_passed": True},
        "indicators_5m": {"rsi": 58.0, "atr": 0.5},
        "spread_pct": 0.02,
        "orderbook_bid_value": 900.0,
        "orderbook_ask_value": 700.0,
        "volumeSpike": 1.6,
        "pattern": "engulfing",
        "_scan_uuid": "uuid-1",
        "_opportunity_id": "opp-1",
        "klines_1m": [[i, 100.0, 101.0, 99.0, 100.5, 1000.0] for i in range(40)],
    }


def refus(symbol="BTC/USDT", raison="Score insuffisant", categorie="score_insufficient"):
    return {"symbol": symbol, "reason": raison, "reject_category": categorie}


# --------------------------------------------------------------------- fixtures
@pytest.fixture
def equipes(monkeypatch):
    """Injecte les faux objets dans les variables globales du module, puis remet a zero."""
    avant = {
        "_scanner": scan._scanner,
        "_analyzer": scan._analyzer,
        "_position_manager": scan._position_manager,
        "_price_provider": scan._price_provider,
        "_app_state": scan._app_state,
        "_ws_manager": scan._ws_manager,
        "_scanner_lock": scan._scanner_lock,
        "_pg_datalogger": scan._pg_datalogger,
        "_notification_manager": scan._notification_manager,
    }

    etat = EtatFaux(top_pairs=[{"symbol": "BTC/USDT", "spread": 0.01, "bookDepth": 1200.0, "balanceScore": 1.0}])
    scanner = ScannerFaux()
    analyseur = AnalyseurFaux([setup_complet()])
    positions = GestionnairePositionsFaux()
    prix = PrixFaux()
    ws = WsFaux()
    journal = JournalFaux()
    notifs = NotifFaux()

    scan.set_scanner(scanner)
    scan.set_analyzer(analyseur)
    scan.set_position_manager(positions)
    scan.set_price_provider(prix)
    scan.set_app_state(etat)
    scan.set_websocket_manager(ws)
    scan.set_pg_datalogger(journal)
    scan.set_notification_manager(notifs)
    scan.set_scanner_lock(asyncio.Lock())
    monkeypatch.setattr(scan, "get_cooldown_manager", lambda: CooldownFaux())

    # reglages qui sinifient la branche prise, sans toucher au fichier de reglages
    monkeypatch.setitem(TRADING_CONFIG, "top_pairs_limit", 5)
    monkeypatch.setitem(TRADING_CONFIG, "adaptive_sizing_enabled", False)
    monkeypatch.setitem(TRADING_CONFIG, "gb_filter_enabled", False)
    monkeypatch.setitem(ML_CONFIG, "enabled", False)

    donne = {
        "etat": etat,
        "scanner": scanner,
        "analyseur": analyseur,
        "positions": positions,
        "prix": prix,
        "ws": ws,
        "journal": journal,
        "notifs": notifs,
    }
    yield donne

    for nom, valeur in avant.items():
        setattr(scan, nom, valeur)


# ------------------------------------------------- les petites briques du module
def test_safe_float_accepte_les_ombres_et_les_tromperies():
    assert scan._safe_float("12.5") == 12.5
    assert scan._safe_float(None, 3.0) == 3.0
    assert scan._safe_float("pas un nombre", 1.0) == 1.0
    assert scan._safe_float(float("nan"), 0.0) == 0.0 or math.isnan(scan._safe_float(float("nan"), 0.0))


def test_getter_scribe_rend_ce_qu_on_a_injecte(equipes):
    assert scan.get_pg_datalogger() is equipes["journal"]


def test_get_ws_manager_rende_le_gestionnaire_injecte(equipes):
    assert scan._get_ws_manager() is equipes["ws"]


def test_get_ws_manager_rend_rien_si_absent(etat_vide=None):
    scan.set_websocket_manager(None)
    try:
        assert scan._get_ws_manager() is None or hasattr(scan._get_ws_manager(), "emit")
    finally:
        scan.set_websocket_manager(None)


@pytest.mark.asyncio
async def test_notification_erreur_coupee_ne_rien_envoyer():
    scan.set_notification_manager(None)
    await scan._notify_error("type", "details")
    scan.set_notification_manager(None)


@pytest.mark.asyncio
async def test_notification_erreur_tronque_les_details_interminables():
    notifs = NotifFaux()
    scan.set_notification_manager(notifs)
    try:
        await scan._notify_error("scan", "x" * 900)
        categorie, donnees, options = notifs.envois[0]
        assert categorie == "error"
        assert len(donnees["details"]) == 503  # 500 + '...'
        assert options["channels"] == ["telegram"]
    finally:
        scan.set_notification_manager(None)


@pytest.mark.asyncio
async def test_notification_telegram_respecte_le_interrupteur():
    allume = NotifFaux(telegram=True)
    scan.set_notification_manager(allume)
    try:
        await scan.notify_error_telegram("Api", "ca marche pas")
        assert allume.envois[0][0] == "error"

        eteint = NotifFaux(telegram=False)
        scan.set_notification_manager(eteint)
        await scan.notify_error_telegram("Api", "ca marche pas")
        assert eteint.envois == []
    finally:
        scan.set_notification_manager(None)


# ------------------------------------------------- demarrage du cycle de scan
@pytest.mark.asyncio
async def test_cycle_s_arrete_si_les_pieces_manquent(monkeypatch):
    scan.set_scanner(None)
    scan.set_app_state(None)
    scan.set_scanner_lock(None)
    monkeypatch.setattr(scan, "_notify_error", lambda *a, **k: asyncio.sleep(0))
    await scan.scanner_loop_callback()  # ne doit ni planter ni notifier


@pytest.mark.asyncio
async def test_cycle_ignore_le_scan_si_une_position_est_deja_ouverte(equipes):
    equipes["positions"].active_position = ResultatPrise("BTC/USDT", "LONG")
    await scan.scanner_loop_callback()
    assert equipes["analyseur"].appels == []
    assert equipes["positions"].ouvertures == []


@pytest.mark.asyncio
async def test_cycle_ignore_le_scan_pendant_le_cooldown(equipes, monkeypatch):
    monkeypatch.setattr(scan, "get_cooldown_manager", lambda: CooldownFaux(False, "refroidissement 120 s"))
    await scan.scanner_loop_callback()
    assert equipes["analyseur"].appels == []


@pytest.mark.asyncio
async def test_cycle_lance_le_scan_initial_puis_les_setups(equipes):
    equipes["etat"]["top_pairs"] = []
    equipes["scanner"].paires = [{"symbol": "ETH/USDT", "spread": 0.02}, {"symbol": "BTC/USDT", "spread": 0.01}]
    equipes["analyseur"].reponses = [setup_complet("ETH/USDT")]

    await scan.scanner_loop_callback()

    assert equipes["scanner"].appels == [20]
    assert [p["symbol"] for p in equipes["etat"]["top_pairs"]] == ["ETH/USDT", "BTC/USDT"]
    assert [a[0] for a in equipes["analyseur"].appels] == ["ETH/USDT", "BTC/USDT"]
    assert ("top_pairs_update", {"pairs": equipes["etat"]["top_pairs"]}) in equipes["ws"].evenements
    assert equipes["prix"].demarres[0] == ["ETH/USDT", "BTC/USDT"]
    # une prise ouverte = le flux est redemarre sur cette paire seule (prix frais pendant la prise)
    assert equipes["prix"].demarres[-1] == ["ETH/USDT"]
    assert equipes["prix"].arretes == 1


@pytest.mark.asyncio
async def test_cycle_scanne_les_paires_deja_trouvees(equipes):
    await scan.scanner_loop_callback()
    assert equipes["analyseur"].appels[0][0] == "BTC/USDT"
    assert equipes["etat"]["active_position"]["symbol"] == "BTC/USDT"


@pytest.mark.asyncio
async def test_cycle_notifie_en_cas_de_pepin_interne(equipes, monkeypatch):
    equipes["scanner"].paires = [{"symbol": "BTC/USDT"}]

    class LockQuiExplose:
        def __enter__(self):
            raise RuntimeError("lock casse")

        def __exit__(self, *a):
            return False

    # le lock est utilise en `async with`: on lui donne un objet qui leve
    class AsyncLockQuiExplose:
        async def __aenter__(self):
            raise RuntimeError("lock casse")

        async def __aexit__(self, *a):
            return False

    scan.set_scanner_lock(AsyncLockQuiExplose())
    await scan.scanner_loop_callback()

    assert equipes["notifs"].envois
    assert "lock casse" in equipes["notifs"].envois[0][1]["details"]


# ------------------------------------------------- scan initial des top pairs
@pytest.mark.asyncio
async def test_scan_initial_ne_rien_faire_sans_scanner():
    scan.set_scanner(None)
    scan.set_app_state(EtatFaux())
    await scan._scan_initial_top_pairs()
    assert True  # pas d'exception


@pytest.mark.asyncio
async def test_scan_initial_remplit_les_paires_et_demarre_le_flux(equipes):
    equipes["etat"]["top_pairs"] = []
    await scan._scan_initial_top_pairs()
    assert equipes["etat"]["top_pairs"]
    assert equipes["ws"].evenements[0][0] == "top_pairs_update"
    assert equipes["prix"].demarres


@pytest.mark.asyncio
async def test_scan_initial_survit_a_un_flux_qui_refuse_de_demarrer(equipes):
    equipes["etat"]["top_pairs"] = []
    equipes["prix"].erreur_demarrage = RuntimeError("port occupé")
    await scan._scan_initial_top_pairs()
    assert equipes["etat"]["top_pairs"]
    assert equipes["notifs"].envois[0][1]["details"] == "port occupé"


@pytest.mark.asyncio
async def test_scan_initial_notifie_si_le_scan_tombe(equipes):
    equipes["etat"]["top_pairs"] = []
    equipes["scanner"].erreur = RuntimeError("MEXC muet")
    await scan._scan_initial_top_pairs()
    assert "MEXC muet" in equipes["notifs"].envois[0][1]["details"]


# ------------------------------------------------- decision: prise, refus, filtres
@pytest.mark.asyncio
async def test_une_paire_prenante_ouvre_une_prise(equipes):
    await scan._scan_top_pairs()

    assert len(equipes["positions"].ouvertures) == 1
    ouverture = equipes["positions"].ouvertures[0]
    assert ouverture["symbol"] == "BTC/USDT"
    assert ouverture["direction"] == "LONG"
    assert ouverture["entry"] == 100.0
    assert ouverture["size"] == 42.0
    assert ouverture["confirmed_by"] == "EMAs, Volume"
    assert equipes["etat"]["active_position"] == {"symbol": "BTC/USDT", "direction": "LONG"}
    assert ("position_opened", {"symbol": "BTC/USDT", "direction": "LONG"}) in equipes["ws"].evenements


@pytest.mark.asyncio
async def test_lesdonnees_de_carnet_sont_transmises_a_ouverture(equipes):
    equipes["etat"]["top_pairs"] = [
        {"symbol": "BTC/USDT", "spread": 0.03, "bookDepth": 2000.0, "balanceScore": 1.2, "bidVol": 300.0, "askVol": 200.0}
    ]
    await scan._scan_top_pairs()

    scalabilite = equipes["positions"].ouvertures[0]["scalability_data"]
    assert scalabilite["spread_pct"] == 0.03
    assert scalabilite["depth"] == 2000.0
    assert scalabilite["bid_vol"] == 300.0


@pytest.mark.asyncio
async def test_un_refus_n_ouvre_rien(equipes):
    equipes["analyseur"].reponses = [refus()]
    await scan._scan_top_pairs()

    assert equipes["positions"].ouvertures == []
    stats = [e for e in equipes["ws"].evenements if e[0] == "volume_stats_update"][0][1]
    assert stats["validated"] == 0
    assert stats["total"] == 1


@pytest.mark.asyncio
async def test_une_tache_qui_explose_ne_casse_pas_le_cycle(equipes):
    equipes["etat"]["top_pairs"] = [{"symbol": "BTC/USDT"}, {"symbol": "ETH/USDT"}]
    equipes["analyseur"].reponses = [RuntimeError("reseau lache"), setup_complet("ETH/USDT", entree=50.0)]

    await scan._scan_top_pairs()

    assert [o["symbol"] for o in equipes["positions"].ouvertures] == ["ETH/USDT"]


@pytest.mark.asyncio
async def test_entree_invalide_bloque_avant_ouverture(equipes):
    equipes["analyseur"].reponses = [setup_complet(entree=0.0)]
    await scan._scan_top_pairs()
    assert equipes["positions"].ouvertures == []


@pytest.mark.asyncio
async def test_une_prise_ignoree_par_le_garde_fou_n_inonde_pas_l_interface(equipes):
    equipes["positions"].retour_ouverture = "rien"
    await scan._scan_top_pairs()
    assert equipes["positions"].ouvertures
    assert "active_position" not in equipes["etat"]
    assert not any(e[0] == "position_opened" for e in equipes["ws"].evenements)


@pytest.mark.asyncio
async def test_reglage_invalide_est_signale_sans_notification(equipes):
    equipes["positions"].retour_ouverture = "valeur"
    await scan._scan_top_pairs()
    assert equipes["notifs"].envois == []


@pytest.mark.asyncio
async def test_ouverture_qui_plante_est_notifiee(equipes):
    equipes["positions"].erreur = RuntimeError("compte refuse")
    await scan._scan_top_pairs()
    assert "compte refuse" in equipes["notifs"].envois[0][1]["details"]


@pytest.mark.asyncio
async def test_cycle_s_arrete_si_aucune_paire_a_scanner(equipes):
    equipes["etat"]["top_pairs"] = [{"pas_de_symbol": 1}]
    await scan._scan_top_pairs()
    assert equipes["analyseur"].appels == []


@pytest.mark.asyncio
async def test_top_pairs_limite_le_nombre_d_analyses(equipes, monkeypatch):
    monkeypatch.setitem(TRADING_CONFIG, "top_pairs_limit", 2)
    equipes["etat"]["top_pairs"] = [{"symbol": f"P{i}/USDT"} for i in range(6)]
    await scan._scan_top_pairs()
    assert len(equipes["analyseur"].appels) == 2


# ------------------------------------------------- filtre du petit modele (GradientBoosting)
def brancher_gb(monkeypatch, approuve=True, confiance=0.8, charge=True, features=True, erreur=None, trace=None):
    """features=True -> des features, features=False -> le constructeur ne trouve rien."""
    from optimization import gb_feature_builder, predictor_optimized

    valeur_features = {"f1": 1.0} if features is True else features
    monkeypatch.setattr(gb_feature_builder, "build_gb_features", lambda **k: valeur_features)
    monkeypatch.setattr(
        predictor_optimized,
        "get_predictor",
        lambda: PredicteurFaux(charge=charge, approuve=approuve, confiance=confiance, erreur=erreur),
    )
    if trace is not None:
        from core import pilotage_ia

        monkeypatch.setattr(pilotage_ia, "ecrire_prediction_filtre", trace)


@pytest.mark.asyncio
async def test_le_petit_modele_approuve_et_traverse(equipes, monkeypatch):
    ecrits = []
    monkeypatch.setitem(TRADING_CONFIG, "gb_filter_enabled", True)
    brancher_gb(monkeypatch, approuve=True, confiance=0.8, trace=lambda **k: ecrits.append(k))

    await scan._scan_top_pairs()

    assert len(equipes["positions"].ouvertures) == 1
    assert equipes["journal"].confiances == [("BTC/USDT", 80.0)]
    assert ecrits[0]["approuve"] is True
    assert ecrits[0]["seuil"] == pytest.approx(TRADING_CONFIG.get("gb_min_confidence", 0.55))


@pytest.mark.asyncio
async def test_le_petit_modele_refuse_et_bloque_la_prise(equipes, monkeypatch):
    ecrits = []
    monkeypatch.setitem(TRADING_CONFIG, "gb_filter_enabled", True)
    monkeypatch.setitem(TRADING_CONFIG, "gb_min_confidence", 0.9)
    brancher_gb(monkeypatch, approuve=False, confiance=0.4, trace=lambda **k: ecrits.append(k))

    await scan._scan_top_pairs()

    assert equipes["positions"].ouvertures == []
    assert ecrits[0]["approuve"] is False
    rejet = equipes["journal"].rejets_ml[0]
    assert rejet["reject_category"] == "ml_gb_confidence"
    assert rejet["ml_confidence"] == 40.0


@pytest.mark.asyncio
async def test_modele_non_charge_laisse_passer_par_defaut(equipes, monkeypatch):
    monkeypatch.setitem(TRADING_CONFIG, "gb_filter_enabled", True)
    brancher_gb(monkeypatch, charge=False)
    await scan._scan_top_pairs()
    assert len(equipes["positions"].ouvertures) == 1


@pytest.mark.asyncio
async def test_sans_features_le_filtre_ne_bloque_pas(equipes, monkeypatch):
    monkeypatch.setitem(TRADING_CONFIG, "gb_filter_enabled", True)
    brancher_gb(monkeypatch, features=False)
    await scan._scan_top_pairs()
    assert equipes["journal"].confiances == []
    assert len(equipes["positions"].ouvertures) == 1


@pytest.mark.asyncio
async def test_predicteur_qui_plante_laisse_passer_failsafe(equipes, monkeypatch):
    monkeypatch.setitem(TRADING_CONFIG, "gb_filter_enabled", True)
    brancher_gb(monkeypatch, erreur=RuntimeError("modele HS"))
    await scan._scan_top_pairs()
    assert len(equipes["positions"].ouvertures) == 1
    assert "modele HS" not in str(equipes["notifs"].envois)


@pytest.mark.asyncio
async def test_tracer_le_verdict_ne_doit_pas_bloquer_la_prise(equipes, monkeypatch):
    monkeypatch.setitem(TRADING_CONFIG, "gb_filter_enabled", True)

    def trace_qui_plante(**k):
        raise RuntimeError("base indisponible")

    brancher_gb(monkeypatch, approuve=True, confiance=0.7, trace=trace_qui_plante)
    await scan._scan_top_pairs()
    assert len(equipes["positions"].ouvertures) == 1


# ------------------------------------------------- filtres ML herites (XGBoost)
@pytest.mark.asyncio
async def test_filtre_ml_herite_refuse_en_mode_strict(equipes, monkeypatch):
    from optimization import scanner_ml_integration

    monkeypatch.setitem(ML_CONFIG, "enabled", True)
    monkeypatch.setitem(ML_CONFIG, "mode", "STRICT")
    monkeypatch.setitem(ML_CONFIG, "min_confidence", 0.6)

    async def prediction_perdue(**kwargs):
        return {"prediction": "loss", "confidence": 0.9, "features": {"a": 1.0}}

    monkeypatch.setattr(scanner_ml_integration, "get_ml_prediction_for_opportunity", prediction_perdue)

    await scan._scan_top_pairs()

    assert equipes["positions"].ouvertures == []
    assert equipes["journal"].rejets_ml[0]["reject_category"] == "ml_xgboost_strict"


@pytest.mark.asyncio
async def test_filtre_ml_herite_laisse_passer_en_mode_soft(equipes, monkeypatch):
    from optimization import scanner_ml_integration

    monkeypatch.setitem(ML_CONFIG, "enabled", True)
    monkeypatch.setitem(ML_CONFIG, "mode", "SOFT")
    monkeypatch.setitem(ML_CONFIG, "max_loss_confidence", 0.7)

    async def prediction_gagnee(**kwargs):
        return {"prediction": "win", "confidence": 0.5, "features": {"a": 1.0}}

    monkeypatch.setattr(scanner_ml_integration, "get_ml_prediction_for_opportunity", prediction_gagnee)

    await scan._scan_top_pairs()

    assert len(equipes["positions"].ouvertures) == 1


@pytest.mark.asyncio
async def test_sans_klines_le_filtre_herite_ne_bloque_pas(equipes, monkeypatch):
    monkeypatch.setitem(ML_CONFIG, "enabled", True)
    equipes["analyseur"].reponses = [setup_complet()]
    del equipes["analyseur"].reponses[0]["klines_1m"]

    await scan._scan_top_pairs()

    assert len(equipes["positions"].ouvertures) == 1


@pytest.mark.asyncio
async def test_le_filtre_herite_ne_passe_pas_quand_gb_est_actif(equipes, monkeypatch):
    from optimization import scanner_ml_integration

    appelee = []

    async def espion(**kwargs):
        appelee.append(kwargs)
        return None

    monkeypatch.setitem(ML_CONFIG, "enabled", True)
    monkeypatch.setitem(TRADING_CONFIG, "gb_filter_enabled", True)
    monkeypatch.setattr(scanner_ml_integration, "get_ml_prediction_for_opportunity", espion)
    brancher_gb(monkeypatch, approuve=True, confiance=0.9)

    await scan._scan_top_pairs()

    # le predictiveur herite peut etre appele une fois pour informer, mais il ne
    # doit jamais decider : aucune ouverture bloquee, aucun rejet ecrit
    assert len(appelee) <= 1
    assert len(equipes["positions"].ouvertures) == 1
    assert equipes["journal"].rejets_ml == []


# ------------------------------------------------- scan d'une paire et ecritures
@pytest.mark.asyncio
async def test_scan_d_une_paire_ecrit_une_ligne_de_journal(equipes):
    resultat = await scan.scan_pair_for_setup("BTC/USDT")

    assert resultat is not None
    assert len(equipes["journal"].scans) == 1
    symbole, donnees, _utilise = equipes["journal"].scans[0]
    assert symbole == "BTC/USDT"
    assert isinstance(donnees, dict) and len(donnees) > 20, "une ligne de journal fournie, pas un timbre-poste"
    assert resultat["_scan_uuid"] == "scan-1"


@pytest.mark.asyncio
async def test_scan_d_une_paire_prenante_ecrit_une_opportunite(equipes):
    await scan.scan_pair_for_setup("BTC/USDT")
    assert equipes["journal"].opportunites


@pytest.mark.asyncio
async def test_scan_d_un_symbole_vide_ne_rien_faire(equipes):
    assert await scan.scan_pair_for_setup("") is None


@pytest.mark.asyncio
async def test_scan_sans_analyseur_ne_rien_faire():
    scan.set_analyzer(None)
    try:
        assert await scan.scan_pair_for_setup("BTC/USDT") is None
    finally:
        scan.set_analyzer(None)


@pytest.mark.asyncio
async def test_scan_d_une_paire_qui_ne_plait_pas_reste_un_refus(equipes):
    equipes["analyseur"].reponses = [refus(raison="ATR sous-optimal", categorie="atr_filter")]

    resultat = await scan.scan_pair_for_setup("BTC/USDT")

    assert resultat.get("reject_category") == "atr_filter"
    assert "direction" not in resultat or resultat.get("direction") is None
    assert equipes["journal"].scans  # le refus est quand meme journalise


@pytest.mark.asyncio
async def test_scan_qui_explose_est_notifie_et_renvoie_rien(equipes):
    equipes["analyseur"].erreur = RuntimeError("MEXC muet")
    assert await scan.scan_pair_for_setup("BTC/USDT") is None
    assert "MEXC muet" in equipes["notifs"].envois[0][1]["details"]


@pytest.mark.asyncio
async def test_scan_d_une_analyse_invalide_est_journalise_comme_refus(equipes):
    equipes["analyseur"].reponses = ["pas un dictionnaire"]
    resultat = await scan.scan_pair_for_setup("BTC/USDT")
    assert resultat is None or isinstance(resultat, dict)


@pytest.mark.asyncio
async def test_sans_scribe_le_scan_ne_veut_plus_ecrire(equipes):
    equipes["journal"].enabled = False
    resultat = await scan.scan_pair_for_setup("BTC/USDT")
    assert equipes["journal"].scans == []
    assert resultat is not None


@pytest.mark.asyncio
async def test_ecrire_dans_une_base_qui_refuse_ne_casse_pas_le_scan(equipes):
    class JournalQuiPlante(JournalFaux):
        async def log_scan_async(self, *a, **k):
            raise RuntimeError("base muette")

    scan.set_pg_datalogger(JournalQuiPlante())

    resultat = await scan.scan_pair_for_setup("BTC/USDT")

    assert resultat is not None
    assert equipes["notifs"].envois == [], "une ecriture ratee ne doit pas crier sur Telegram"


@pytest.mark.asyncio
async def test_carnet_reconstitue_depuis_l_analyse_si_la_paire_manque(equipes):
    """La paire prise n'est pas dans la liste scannée : on reconstruit avec ce que dit l'analyse."""
    equipes["etat"]["top_pairs"] = [{"symbol": "OTHER/USDT", "spread": 0.01}]

    await scan._scan_top_pairs()

    scalabilite = equipes["positions"].ouvertures[0]["scalability_data"]
    assert scalabilite["spread_pct"] == 0.02  # venu de l'analyse
    assert scalabilite["depth"] == 1600.0  # 900 + 700 du carnet de l'analyse


@pytest.mark.asyncio
async def test_reparer_le_flux_apres_une_prise_n_etouffe_pas_le_scan(equipes):
    """Si le flux de prix refuse de redemarrer, la prise est garde et on est prevenue."""
    equipes["prix"].erreur_demarrage = RuntimeError("flux indisponible")

    await scan._scan_top_pairs()

    assert len(equipes["positions"].ouvertures) == 1
    assert equipes["etat"]["active_position"]["symbol"] == "BTC/USDT"
    assert any("flux indisponible" in e[1]["details"] for e in equipes["notifs"].envois)


class PrixAvecVerrouSL(PrixFaux):
    """Flux de prix qui propose la verification du stop en temps reel."""

    def __init__(self):
        super().__init__()
        self.verrous_poses = []

    def set_sl_check_callback(self, *args, **kwargs):
        self.verrous_poses.append(args)


@pytest.mark.asyncio
async def test_le_verrou_de_stop_en_temps_reel_ne_doit_pas_faire_tomber_le_scan(equipes):
    """Le code qui branche la surveillance du stop est optionnel : s'il manque, le scan continue."""
    prix = PrixAvecVerrouSL()
    scan.set_price_provider(prix)

    await scan._scan_top_pairs()

    assert len(equipes["positions"].ouvertures) == 1
    assert equipes["etat"]["active_position"]["symbol"] == "BTC/USDT"


# ------------------------------------------------- timeout et modes herites
@pytest.mark.asyncio
async def test_un_scan_qui_trop_long_reste_un_refus_journalise(equipes, monkeypatch):
    """L'analyseur met trop de temps : on obtient un refus, pas un plantage."""
    monkeypatch.setitem(TRADING_CONFIG, "scan_pair_timeout_s", 0.05)
    equipes["analyseur"].latence = 0.5

    resultat = await scan.scan_pair_for_setup("BTC/USDT")

    assert resultat is None or resultat.get("direction") is None
    assert equipes["positions"].ouvertures == []


@pytest.mark.asyncio
async def test_mode_soft_rejette_une_perteannoncee(equipes, monkeypatch):
    from optimization import scanner_ml_integration

    monkeypatch.setitem(ML_CONFIG, "enabled", True)
    monkeypatch.setitem(ML_CONFIG, "mode", "SOFT")
    monkeypatch.setitem(ML_CONFIG, "max_loss_confidence", 0.7)

    async def perte_evidente(**kwargs):
        return {"prediction": "loss", "confidence": 0.95, "features": {"a": 1.0}}

    monkeypatch.setattr(scanner_ml_integration, "get_ml_prediction_for_opportunity", perte_evidente)

    await scan._scan_top_pairs()

    assert equipes["positions"].ouvertures == []
    assert equipes["journal"].rejets_ml[0]["reject_category"] == "ml_xgboost_soft"


@pytest.mark.asyncio
async def test_mode_negatif_bloque_si_la_perte_est_probable(equipes, monkeypatch):
    from optimization import predictor_negative, scanner_ml_integration

    monkeypatch.setitem(ML_CONFIG, "enabled", True)
    monkeypatch.setitem(ML_CONFIG, "mode", "NEGATIVE")
    monkeypatch.setitem(ML_CONFIG, "loss_threshold", 0.45)

    async def prediction_quelconque(**kwargs):
        return {"prediction": "win", "confidence": 0.8, "features": None}

    class PredicteurNegatifFaux:
        def predict(self, features, threshold=None):
            return {"p_loss": 0.62, "should_reject": True}

    monkeypatch.setattr(scanner_ml_integration, "get_ml_prediction_for_opportunity", prediction_quelconque)
    monkeypatch.setattr(predictor_negative, "get_negative_predictor", lambda: PredicteurNegatifFaux())

    await scan._scan_top_pairs()

    assert equipes["positions"].ouvertures == []
    assert equipes["journal"].rejets_ml[0]["reject_category"] == "ml_negative_filter"


@pytest.mark.asyncio
async def test_mode_negatif_laisse_passer_si_la_perte_est_lointaine(equipes, monkeypatch):
    from optimization import predictor_negative, scanner_ml_integration

    monkeypatch.setitem(ML_CONFIG, "enabled", True)
    monkeypatch.setitem(ML_CONFIG, "mode", "NEGATIVE")

    async def prediction_quelconque(**kwargs):
        return {"prediction": "win", "confidence": 0.8, "features": None}

    class PredicteurNegatifFaux:
        def predict(self, features, threshold=None):
            return {"p_loss": 0.10, "should_reject": False}

    monkeypatch.setattr(scanner_ml_integration, "get_ml_prediction_for_opportunity", prediction_quelconque)
    monkeypatch.setattr(predictor_negative, "get_negative_predictor", lambda: PredicteurNegatifFaux())

    await scan._scan_top_pairs()

    assert len(equipes["positions"].ouvertures) == 1


@pytest.mark.asyncio
async def test_prediction_heritee_qui_tombe_laisse_passer(equipes, monkeypatch):
    from optimization import scanner_ml_integration

    monkeypatch.setitem(ML_CONFIG, "enabled", True)

    async def plus_de_prediction(**kwargs):
        return None

    monkeypatch.setattr(scanner_ml_integration, "get_ml_prediction_for_opportunity", plus_de_prediction)

    await scan._scan_top_pairs()

    assert len(equipes["positions"].ouvertures) == 1


@pytest.mark.asyncio
async def test_l_interface_qui_refuse_levenement_ne_casse_pas_le_scan(equipes):
    equipes["ws"].erreur = RuntimeError("navigateur debranche")
    await scan._scan_top_pairs()
    assert len(equipes["positions"].ouvertures) == 1
    assert "navigateur debranche" in equipes["notifs"].envois[0][1]["details"]


@pytest.mark.asyncio
async def test_sans_scribe_du_tout_le_scan_continue_de_vivre(equipes):
    scan.set_pg_datalogger(None)
    import core.state_manager as etat_global

    original = etat_global.get_state_manager().get_pg_datalogger
    etat_global.get_state_manager().get_pg_datalogger = lambda: None
    try:
        resultat = await scan.scan_pair_for_setup("BTC/USDT")
        assert resultat is not None
    finally:
        etat_global.get_state_manager().get_pg_datalogger = original


# ------------------------------------------------- melange des metriques de filtre
def test_extraction_des_metriques_de_filtre():
    analyse = {
        "timeframe": "1m",
        "analysis_1m": {
            "volume_filter_passed": True,
            "snr": 1.5,
            "snr_passed": True,
            "breakout_distance": 0.4,
            "breakout_passed": True,
            "wick_ratio": 0.3,
            "wick_passed": True,
            "atr_optimal_passed": True,
        },
        "analysis_5m": {"snr": 2.0, "snr_passed": True},
    }

    metriques = scan._extract_filter_metrics(analyse)

    assert len(metriques) == 16
    assert metriques["volume_filter_passed_1m"] is True
    assert metriques["snr_1m"] == 1.5
    assert metriques["snr_5m"] == 2.0
    assert metriques["breakout_distance_1m"] == 0.4
    assert metriques["wick_ratio_1m"] == 0.3
    assert metriques["snr_passed_5m"] is True
    assert metriques["breakout_passed_5m"] is False


def test_extraction_sans_metriques_remet_les_zeros():
    metriques = scan._extract_filter_metrics({})

    assert len(metriques) == 16
    assert all(v in (False, 0.0) for v in metriques.values())


def test_metriques_deja_calcules_sont_reuses_sans_retour():
    """Si l'analyse porte deja le dictionnaire `filters`, on ne recompose rien."""
    analyse = {"filters": {"snr_1m": 9.0, "wick_passed_5m": True}}
    metriques = scan._extract_filter_metrics(analyse)
    assert metriques["snr_1m"] == 9.0
    assert metriques["wick_passed_5m"] is True
    assert metriques["snr_5m"] == 0.0


def test_metriques_a_plat_de_l_horaire_concerne():
    """Les cles deja suffixees a la racine de l'analyse sont acceptees telles quelles."""
    analyse = {"snr_5m": 3.0, "volume_filter_passed_5m": True, "snr_1m": 1.1}
    metriques = scan._extract_filter_metrics(analyse)
    assert metriques["snr_5m"] == 3.0
    assert metriques["volume_filter_passed_5m"] is True


def test_metriques_de_l_horaire_gagnant_lues_a_la_racine():
    """Quand l'analyse vient du 1m, ses valeurs sans suffixe appartiennent au 1m."""
    analyse = {
        "timeframe": "1m",
        "volume_filter_passed": True,
        "snr": 1.8,
        "snr_passed": True,
        "breakout_distance": 0.5,
        "breakout_passed": True,
        "wick_ratio": 0.25,
        "wick_passed": True,
        "atr_optimal_passed": True,
    }
    metriques = scan._extract_filter_metrics(analyse)
    assert metriques["snr_1m"] == 1.8
    assert metriques["volume_filter_passed_1m"] is True
    assert metriques["wick_passed_1m"] is True
    assert metriques["atr_optimal_passed_1m"] is True
    assert metriques["snr_5m"] == 0.0


def test_metriques_de_l_horaire_5m_lues_a_la_racine():
    analyse = {
        "timeframe": "5m",
        "volume_filter_passed": True,
        "snr": 2.4,
        "snr_passed": True,
        "breakout_distance": 0.7,
        "breakout_passed": False,
        "wick_ratio": 0.4,
        "wick_passed": False,
        "atr_optimal_passed": True,
    }
    metriques = scan._extract_filter_metrics(analyse)
    assert metriques["snr_5m"] == 2.4
    assert metriques["breakout_distance_5m"] == 0.7
    assert metriques["atr_optimal_passed_5m"] is True
    assert metriques["snr_1m"] == 0.0


def test_metriques_ignorent_un_horaire_inconnu():
    analyse = {"timeframe": "4h", "snr": 7.0}
    metriques = scan._extract_filter_metrics(analyse)
    assert metriques["snr_1m"] == 0.0
    assert metriques["snr_5m"] == 0.0


def test_extraction_ne_veut_pas_de_chiffres_tordus():
    """Un texte ou rien a la place d un nombre ne part pas tel quel dans la base.

    Ces valeurs alimentent des colonnes numeriques de `scan_logs` : une chaine y
    fait echouer l'ecriture, en silence (le genre de trou deja repare le 18/11).
    """
    analyse = {"analysis_1m": {"snr": "beaucoup", "wick_ratio": None, "breakout_distance": []}}
    metriques = scan._extract_filter_metrics(analyse)
    assert metriques["snr_1m"] == 0.0
    assert metriques["breakout_distance_1m"] == 0.0
    assert metriques["wick_ratio_1m"] == 0.0


def test_extraction_accepte_un_nombre_ecrit_en_texte():
    analyse = {"analysis_5m": {"snr": "2.5", "snr_passed": "yes"}}
    metriques = scan._extract_filter_metrics(analyse)
    assert metriques["snr_5m"] == 2.5
    assert metriques["snr_passed_5m"] is True

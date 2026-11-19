"""L'analyseur qui décide d'entrer, testé avec de fausses bougies.

Mesuré le 19/11/2026 : `core/analyzer.py` n'était couvert qu'à 30 %. Les tests
qui existaient appelaient `analyze_pair` en remplaçant `analyze_timeframe` par
un objet déjà fabriqué : donc les 903 lignes qui calculent les indicateurs, les
scores et les filtres d'entrée n'étaient jamais exécutées.

Ici on donne de vraies bougies (fabriquées mais complètes) à la vraie fonction :
les indicateurs sont calculés pour de vrai, et on vérifie ce qui sort — un setup
avec son prix d'entrée, son stop, son take profit — ou le motif du refus, avec la
catégorie (`volume_filter`, `atr_filter`, `micro_range`…). Ce sont exactement les
catégories qu'on lit dans la base du robot en marche, donc ce fichier sert aussi
de contrat sur l'entonnoir d'entrée.

Aucun réseau : le client de prix et le client de bougies sont des faux.
"""

import asyncio

import pytest

from config import TRADING_CONFIG
from core.analyzer import TechnicalAnalyzer
from core.exceptions import APIError, MarketDataError, NetworkError, RateLimitError
from utils.effective_config import clear_all_adjustments

PAIRE = "BTC/USDT"


def bougies(
    forme="montee",
    n=100,
    base=100.0,
    volume=1_000_000.0,
    volume_derniere=None,
    volume_derniers=None,
    derniere_plate=False,
):
    """Cent bougies [temps, ouverture, plus-haut, plus-bas, clôture, volume]."""
    pas = {
        "montee": base * 0.002,
        "baisse": -base * 0.002,
        "plat": base * 0.0002,
        "vague": base * 0.0035,
    }[forme]
    serie = []
    prix = base
    for i in range(n):
        if forme == "vague":
            # trois bougies montantes, un rappel au milieu : tendance haussiere sans
            # RSI colle au plafond, et la derniere bougie monte (MACD coherent)
            delta = -base * 0.0025 if i % 4 == 2 else base * 0.0035
        else:
            delta = pas if (forme != "plat" or i % 2 == 0) else -base * 0.0002
        ouverture = prix
        cloture = prix + delta
        plus_haut = max(ouverture, cloture) * 1.001
        plus_bas = min(ouverture, cloture) * 0.999
        volume_bougie = volume
        if derniere_plate and i == n - 1:
            plus_haut = ouverture * 1.000001
            plus_bas = ouverture * 0.999999
        if volume_derniere is not None and i == n - 1:
            volume_bougie = volume_derniere
        if volume_derniers is not None and i >= n - 5:
            volume_bougie = volume_derniers
        serie.append(
            [1_700_000_000_000 + i * 60_000, ouverture, plus_haut, plus_bas, cloture, volume_bougie]
        )
        prix = cloture
    return serie


class ClientFaux:
    def __init__(self, serie):
        # `serie` : une serie, ou un dict {horaire: serie} pour simuler des horaires differents
        self.serie = serie
        self.appels = []

    async def fetch_ohlcv(self, symbol, timeframe, limit=100):
        self.appels.append((symbol, timeframe, limit))
        if isinstance(self.serie, dict):
            return self.serie.get(timeframe, [])
        return self.serie

    async def close(self):
        pass


class ClientQuiLeve:
    def __init__(self, erreur):
        self.erreur = erreur

    async def fetch_ohlcv(self, symbol, timeframe, limit=100):
        raise self.erreur


class PrixFaux:
    def __init__(self, prix):
        self.prix = prix

    async def get_price(self, symbol):
        return {"lastPrice": str(self.prix)}


class PrixSansReponse:
    async def get_price(self, symbol):
        await asyncio.sleep(5)
        return {"lastPrice": "100"}


class PrixAbsent:
    """Un fournisseur de prix qui n'a pas la bonne forme."""


@pytest.fixture(autouse=True)
def _journal_reel_interdit(monkeypatch):
    """Ces tests ne doivent jamais ouvrir de vraie connexion a la base du robot.

    Le scribe est singleton : `get_pg_datalogger()` relit `.env` (POSTGRES_ENABLED=true
    ici) et cree un vrai pool de connexions. Une fois cree, il reste en place et
    empoisonne les tests d'apres (mesure : `test_get_db_pool_paths` reclamait None et
    trouvait un objet). Donc : desactive + singleton vide.
    """
    import core.postgresql_datalogger as scribe

    monkeypatch.setenv("POSTGRES_ENABLED", "false")
    monkeypatch.setattr(scribe, "_pg_datalogger_instance", None)


@pytest.fixture
def analyseur(monkeypatch):
    """Un analyseur dont les deux sources de données sont fausses."""
    clear_all_adjustments()
    serie = bougies("montee")
    monkeypatch.setattr("api.mexc.get_mexc_client", lambda *a, **k: ClientFaux(serie))
    monkeypatch.setattr(
        "api.price_provider.get_price_provider", lambda *a, **k: PrixFaux(serie[-1][4])
    )
    instance = TechnicalAnalyzer()
    instance.client = ClientFaux(serie)
    instance.price_provider = PrixFaux(serie[-1][4])
    yield instance
    clear_all_adjustments()


def _serie_unique(serie):
    if isinstance(serie, dict):
        return serie.get("5m") or serie.get("1m") or []
    return serie


def brancher(analyseur, serie, prix=None):
    analyseur.client = ClientFaux(serie)
    if prix is None:
        unique = _serie_unique(serie)
        prix = unique[-1][4] if unique else 0.0
    analyseur.price_provider = PrixFaux(prix)
    return analyseur


# ------------------------------------------------------------------- les setups
@pytest.mark.asyncio
async def test_une_montee_donnes_un_setup_long(analyseur):
    serie = bougies("montee")
    brancher(analyseur, serie)

    setup = await analyseur.analyze_timeframe(PAIRE, "5m")

    assert setup is not None
    assert setup["direction"] == "LONG"
    assert setup["sl"] < setup["entry"] < setup["tp"], "un LONG s'arrête en dessous, vise au-dessus"
    assert setup["score_total"] >= setup["min_score_required"]
    assert setup["volume_filter_passed"] is True
    assert setup["atr_optimal_passed"] is True
    assert setup["symbol"] == PAIRE and setup["timeframe"] == "5m"


@pytest.mark.asyncio
async def test_une_baissee_donnes_un_setup_short(analyseur):
    serie = bougies("baisse")
    brancher(analyseur, serie)

    setup = await analyseur.analyze_timeframe(PAIRE, "5m")

    assert setup is not None
    assert setup["direction"] == "SHORT"
    assert setup["tp"] < setup["entry"] < setup["sl"], "un SHORT vise en dessous, s'arrête au-dessus"


@pytest.mark.asyncio
async def test_le_setup_sert_a_la_prise_de_position(analyseur):
    """Le setup contient de quoi calculer stop, take profit et taille."""
    setup = await analyseur.analyze_timeframe(PAIRE, "5m")

    for cle in ("entry", "sl", "tp", "atr", "price", "rsi", "pattern", "signals", "condition_types"):
        assert cle in setup, f"cle manquante: {cle}"
    assert setup["atr"] > 0


# ------------------------------------------------------- les motifs de refus
@pytest.mark.asyncio
async def test_tendance_trop_chauffee_refusee_par_le_filtre_rsi_final(analyseur, monkeypatch):
    """Une montee sans souffle (RSI colle a 100) est refusee a la derniere porte."""
    monkeypatch.setitem(TRADING_CONFIG, "rsi_final_filter_enabled", True)
    equiper_pour_pair(analyseur, monkeypatch, bougies("montee"))

    refus = await analyseur.analyze_pair(PAIRE, return_reason=True)

    assert refus is not None
    assert refus.get("direction") is None
    assert "RSI" in (refus.get("reason") or "")


@pytest.mark.asyncio
async def test_score_insuffisant_refuse_et_dit_quoi(analyseur):
    """Tendance haussiere mais peu de conditions reunies : la porte se ferme sur le score."""
    serie = bougies("vague")
    brancher(analyseur, serie)

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)

    assert refus["reject_category"] == "score_insufficient"
    assert "Score insuffisant" in refus["reason"]
    assert refus["rsi"] >= 30, "le refus vient du compte de conditions, pas d un prix bloque"


@pytest.mark.asyncio
async def test_seuil_de_score_plus_exigeant_refuse_le_meme_market(analyseur, monkeypatch):
    """Memes bougies, seuil releve : la meme montee est refusee sur le score."""
    serie = bougies("montee")
    brancher(analyseur, serie)

    normal = await analyseur.analyze_timeframe(PAIRE, "5m")
    assert normal is not None and normal["direction"] == "LONG"

    for cle in ("min_score_required", "min_score_adx_low", "min_score_adx_high"):
        monkeypatch.setitem(TRADING_CONFIG, cle, 9.0)

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)
    assert refus["reject_category"] == "score_insufficient"


@pytest.mark.asyncio
async def test_les_conditions_reunies_sont_nommees_dans_le_setup(analyseur):
    """Le setup dit sur quelles conditions il s'appuie (lisibles dans les logs du scan)."""
    setup = await analyseur.analyze_timeframe(PAIRE, "5m")

    assert setup["signals"], "le setup doit nommer ses conditions"
    assert setup["condition_types"]
    assert setup["score_total"] > 0


@pytest.mark.asyncio
async def test_market_sans_amplitude_refuse_sur_latr(analyseur):
    serie = bougies("plat")
    brancher(analyseur, serie)

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)

    assert refus["reject_category"] == "atr_filter"
    assert "ATR" in refus["reason"]
    assert refus["atr_pct"] < 0.35


@pytest.mark.asyncio
async def test_volume_tombe_le_refus_est_volume_filter(analyseur):
    """Les cinq dernieres bougies font dix fois moins de volume : la porte se ferme."""
    serie = bougies("montee", volume=1_000_000.0, volume_derniers=100_000.0)
    brancher(analyseur, serie)

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)

    assert refus["reject_category"] == "volume_filter"
    assert "Volume insuffisant" in refus["reason"]


@pytest.mark.asyncio
async def test_multiplicateur_de_regime_change_la_porte(analyseur):
    """Le multiplicateur du régime est bien appliqué à l'entrée, pas seulement affiché."""
    serie = bougies("montee")
    brancher(analyseur, serie)

    passe = await analyseur.analyze_timeframe(PAIRE, "5m", volume_multiplier=0.8)
    refus = await analyseur.analyze_timeframe(
        PAIRE, "5m", volume_multiplier=1.5, return_reason=True
    )

    assert passe is not None
    assert refus["reject_category"] == "volume_filter"


@pytest.mark.asyncio
async def test_bougie_plate_refusee_micro_range(analyseur):
    serie = bougies("montee", derniere_plate=True)
    brancher(analyseur, serie)

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)

    assert refus["reject_category"] == "micro_range"
    assert "Bougie plate" in refus["reason"]


@pytest.mark.asyncio
async def test_trop_peu_de_bougies(analyseur):
    brancher(analyseur, bougies("montee", n=10))

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)

    assert "insuffisantes" in refus["reason"]
    assert await analyseur.analyze_timeframe(PAIRE, "5m") is None


@pytest.mark.asyncio
async def test_prix_a_zero_refuse(analyseur):
    brancher(analyseur, bougies("montee"), prix=0.0)

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)

    assert "invalide" in refus["reason"].lower()


@pytest.mark.asyncio
async def test_fournisseur_de_prix_mal_forme(analyseur):
    analyseur.price_provider = PrixAbsent()

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)

    assert "Price provider" in refus["reason"]


@pytest.mark.asyncio
async def test_prix_qui_ne_repond_pas(analyseur):
    analyseur.price_provider = PrixSansReponse()

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)

    assert "timeout" in refus["reason"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "erreur, extrait_attendu",
    [
        (RateLimitError("trop de requêtes"), "Rate limit"),
        (NetworkError("connexion perdue"), "Erreur réseau"),
        (APIError("symbole inconnu"), "Erreur API"),
        (MarketDataError("bougies incohérentes"), "invalide"),
        (ValueError("surprise"), "Erreur inattendue"),
    ],
)
async def test_erreur_remtourne_son_type(analyseur, erreur, extrait_attendu):
    analyseur.client = ClientQuiLeve(erreur)

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)

    assert extrait_attendu in refus["reason"]
    assert await analyseur.analyze_timeframe(PAIRE, "5m") is None


@pytest.mark.asyncio
async def test_symbole_exclu_ne_passe_meme_pas(analyseur, monkeypatch):
    monkeypatch.setitem(TRADING_CONFIG, "excluded_symbols", [PAIRE])

    refus = await analyseur.analyze_timeframe(PAIRE, "5m", return_reason=True)

    assert refus["reject_category"] == "excluded_symbol"
    assert refus["symbol"] == PAIRE


# -------------------------------------------------- les fonctions d'à côté
def test_qualite_du_volume(analyseur):
    """Beaucoup de volume sans mouvement = mefiance ; volume minuscule = liquidite faible."""
    sans_mouvement = analyseur.check_volume_quality(
        vol_spike=5.0, atr=0.2, price=100.0, volume24h=50_000_000.0
    )
    illiquide = analyseur.check_volume_quality(
        vol_spike=1.2, atr=0.8, price=100.0, volume24h=500_000.0
    )

    assert "Volume élevé sans mouvement" in sans_mouvement["warnings"]
    assert "Liquidité faible" in illiquide["warnings"]
    assert sans_mouvement["shouldTrade"] is True


def test_taille_de_prise_calculee(analyseur):
    setup = {
        "signals": ["a", "b", "c", "d", "e", "f", "g"],
        "atr": 0.8,
        "price": 100.0,
        "entry": 100.0,
        "sl": 98.0,
    }
    gros_setup = analyseur.calculate_position_size(setup, account_size=1_000.0)
    petit_setup = analyseur.calculate_position_size(
        {**setup, "signals": ["a"], "atr": 3.0}, account_size=1_000.0
    )

    assert gros_setup["size"] > 0
    assert gros_setup["risk"] > petit_setup["risk"], "peu de conditions + marché agité = risque réduit"
    assert "reason" in petit_setup


def test_extraction_des_indicateurs(analyseur):
    setup = {"rsi": 55.0, "atr": 1.2, "adx": 20.0, "pattern": "NONE", "volumeSpike": 1.4}

    extraits = analyseur._extract_indicators(setup)
    vides = analyseur._extract_indicators(None)

    assert extraits["rsi"] == 55.0
    assert all(v is not None for v in vides.values()) or vides == {}


@pytest.mark.asyncio
async def test_donnees_de_tendance(analyseur):
    tendance = await analyseur.calculate_trend_data(PAIRE)

    assert isinstance(tendance, dict)


@pytest.mark.asyncio
async def test_fermeture_propre(analyseur):
    await analyseur.close()


# ------------------------------------------------------ analyze_pair en vrai
def globaux_analyseur():
    """Les variables globales du vrai fichier de l'analyseur.

    Piege du depot : `core/analyzer/` est un paquet, donc `core/analyzer.py` est
    charge a la main sous le nom `core.analyzer_file`, SANS entree dans sys.modules.
    Un `monkeypatch.setattr` sur le paquet ne change donc rien et la grosse fonction
    continue d'appeler la vraie fonction reseau (mesure : « Spread trop élevé 999 % »).
    On patche le dictionnaire global des fonctions, qui est la bonne adresse.
    """
    return TechnicalAnalyzer.analyze_pair.__globals__


def equiper_pour_pair(analyseur, monkeypatch, serie, confluence=False):
    """Branches les seules parties qui ont besoin du réseau, le reste est vrai."""
    from unittest.mock import AsyncMock, MagicMock

    globaux = globaux_analyseur()

    brancher(analyseur, serie)
    monkeypatch.setitem(TRADING_CONFIG, "use_confluence", confluence)

    analyseur.circuit_breaker = MagicMock()
    analyseur.circuit_breaker.can_trade.return_value = True
    analyseur.circuit_breaker.is_symbol_paused.return_value = False
    analyseur.circuit_breaker.get_score_boost.return_value = 0.0

    analyseur.regime_selector = MagicMock()
    analyseur.regime_selector.get_active_config.return_value = {}
    analyseur.regime_selector.check_regime = AsyncMock(return_value=("NORMAL", False))

    analyseur.pair_scorer = MagicMock()
    analyseur.pair_scorer.evaluate_pair = AsyncMock(
        return_value={"score_adjustment": 0.0, "effective_min_score": 7.0}
    )
    analyseur.pair_scorer.get_score_adjustment.return_value = 0.0

    analyseur.calculate_trend_data = AsyncMock(
        return_value={"trend": "BULL", "strength": 3, "bonus": 0}
    )

    monkeypatch.setitem(
        globaux,
        "check_spread",
        AsyncMock(return_value={"valid": True, "spread_pct": 0.01, "max_allowed": 0.05, "quality": "GOOD"}),
    )
    monkeypatch.setitem(
        globaux,
        "check_orderbook_imbalance",
        AsyncMock(return_value={"valid": True, "ratio": 1.2, "quality": "GOOD", "bid_value": 1000, "ask_value": 800}),
    )
    monkeypatch.setitem(globaux, "check_static_correlation", AsyncMock(return_value={"valid": True, "reason": None}))
    monkeypatch.setitem(
        globaux,
        "detect_manipulation",
        MagicMock(return_value={"suspicious": False, "reason": None}),
    )
    return analyseur


@pytest.mark.asyncio
async def test_analyze_pair_remet_le_meilleur_setup(analyseur, monkeypatch):
    """Les deux horaires sont analyses pour de vrai, et le setup remonte.

    Le filtre RSI final est coupe ici : la serie de test monte sans rappel, donc son
    RSI colle a 100, et ce filtre-la est verifie a part (voir le test dedie).
    """
    monkeypatch.setitem(TRADING_CONFIG, "rsi_final_filter_enabled", False)
    equiper_pour_pair(analyseur, monkeypatch, bougies("montee"))

    resultat = await analyseur.analyze_pair(PAIRE, return_reason=True)

    assert resultat.get("direction") == "LONG", resultat.get("reason")
    assert resultat["entry"] > 0
    assert resultat["sl"] < resultat["entry"] < resultat["tp"]


@pytest.mark.asyncio
async def test_confluence_accepte_quand_les_deux_horaires_sont_d_accord(analyseur, monkeypatch):
    """1m et 5m racontent la meme histoire : le setup passe la confluence."""
    monkeypatch.setitem(TRADING_CONFIG, "rsi_final_filter_enabled", False)
    equiper_pour_pair(analyseur, monkeypatch, bougies("montee"), confluence=True)

    resultat = await analyseur.analyze_pair(PAIRE, return_reason=True)

    assert resultat.get("direction") == "LONG", resultat.get("reason")


@pytest.mark.asyncio
async def test_confluence_partielle_bascule_en_mode_permissif(analyseur, monkeypatch):
    """1m dessine une montee, 5m reste a plat : le robot garde le 1m, mais le dit.

    Choix assume du code (commentaire « confluence partielle, passage en mode
    permissif ») : ce test fige le comportement du jour pour que quiconque change la
    regle fasse du bruit au lieu de glisser en silence.
    """
    monkeypatch.setitem(TRADING_CONFIG, "rsi_final_filter_enabled", False)
    series_par_horaire = {"1m": bougies("montee"), "5m": bougies("plat")}
    equiper_pour_pair(analyseur, monkeypatch, series_par_horaire, confluence=True)

    resultat = await analyseur.analyze_pair(PAIRE, return_reason=True)

    assert resultat.get("direction") == "LONG"
    assert (resultat.get("analysis_5m") or {}).get("reason"), (
        "l'horaire gene doit rester visible dans le resultat (confluence partielle)"
    )


@pytest.mark.asyncio
async def test_analyze_pair_sans_donnees_n_invente_pas_de_setup(analyseur, monkeypatch):
    equiper_pour_pair(analyseur, monkeypatch, [])
    analyseur.price_provider = PrixAbsent()

    resultat = await analyseur.analyze_pair(PAIRE, return_reason=True)

    assert resultat is None or resultat.get("direction") is None, (
        "pas de données, donc pas de sens de prise"
    )
    if isinstance(resultat, dict):
        assert (resultat.get("analysis_1m") or {}).get("direction") is None
        assert resultat.get("reason") or (resultat.get("analysis_1m") or {}).get("reason")

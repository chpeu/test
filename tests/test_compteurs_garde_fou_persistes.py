"""Les garde-fous doivent survivre à un redémarrage.

Mesure du 19/11/2026 : `TradingCircuitBreaker` comptait les prises du jour, les
pertes consécutives, le PnL du jour et l'état (pause / arrêt) **en mémoire
seulement**. Redémarrer le robot — plantage, coupure réseau, mise à jour —
remettait tout à zéro : 40 prises interdites redevenaient 40 prises autorisées,
et une série de pertes qui avait déclenché la pause repartait de zéro. Les
plafonds de dégâts étaient donc effaçables par un simple redémarrage.
"""

import contextlib
from datetime import date, datetime, timedelta

import pytest

from config import TRADING_CONFIG
from core.trading_circuit_breaker import CircuitBreakerState, TradingCircuitBreaker


class FauxCurseur:
    def __init__(self, magasin):
        self.magasin = magasin
        self.ligne = None

    def execute(self, requete, params=None):
        if requete.strip().upper().startswith("SELECT"):
            self.ligne = self.magasin.get("ligne")
        else:
            self.magasin["ecritures"].append((requete, params))

    def fetchone(self):
        return self.ligne

    def close(self):
        pass


class FauxConnection:
    def __init__(self, magasin):
        self.magasin = magasin

    def cursor(self):
        return FauxCurseur(self.magasin)

    def commit(self):
        self.magasin["commits"] = self.magasin.get("commits", 0) + 1


@pytest.fixture
def magasin(monkeypatch):
    """Une fausse base en mémoire : on voit ce qui est écrit et ce qui est relu."""
    store = {"ecritures": [], "commits": 0, "ligne": None}

    @contextlib.contextmanager
    def connexion_journal():
        yield FauxConnection(store)

    import core.postgresql_datalogger as scribe

    monkeypatch.setattr(scribe, "connexion_journal", connexion_journal)
    monkeypatch.setattr(scribe, "_pg_datalogger_instance", ScribeActif())
    monkeypatch.setitem(TRADING_CONFIG, "trading_cb_persister", True)
    return store


class ScribeActif:
    enabled = True


def un_garde_fou(**reglages) -> TradingCircuitBreaker:
    reglages.setdefault("max_consecutive_losses", 5)
    reglages.setdefault("max_trades_per_day", 40)
    return TradingCircuitBreaker(**reglages)


# ── l'écriture des compteurs ─────────────────────────────────────────────────


def test_chaque_trade_enregistre_les_compteurs(magasin):
    garde_fou = un_garde_fou()
    garde_fou.record_trade("ZEC/USDT:USDT", pnl_pct=-0.3, pnl_usdt=-0.045)

    assert magasin["ecritures"], "aucun compteur écrit : le redémarrage effacerait tout"
    requete, params = magasin["ecritures"][-1]
    assert "circuit_breaker_etat" in requete
    assert params[1] == 1          # trades_pris
    assert params[4] == 1          # pertes_consecutives
    assert magasin["commits"] >= 1, "la ligne n'est pas validée : elle serait perdue"


def test_chaque_changement_etat_enregistre_l_etat(magasin):
    garde_fou = un_garde_fou(max_consecutive_losses=2, pause_duration_minutes=30)
    garde_fou.record_trade("A/USDT:USDT", pnl_pct=-0.3, pnl_usdt=-0.045)
    garde_fou.record_trade("B/USDT:USDT", pnl_pct=-0.3, pnl_usdt=-0.045)

    assert garde_fou.state == CircuitBreakerState.PAUSED
    ecriture = magasin["ecritures"][-1][1]
    assert ecriture[7] == "PAUSED"
    assert ecriture[9] and "2 pertes consécutives" in ecriture[9]


def test_le_reset_manual_est_enregistre(magasin):
    garde_fou = un_garde_fou(max_consecutive_losses=1)
    garde_fou.record_trade("A/USDT:USDT", pnl_pct=-0.3, pnl_usdt=-0.045)
    garde_fou.reset()
    assert magasin["ecritures"][-1][1][7] == "ACTIVE"


# ── la relecture : c'est là que le garde-fou prouve son utilité ──────────────


def une_ligne(jour=None, prises=0, pertes_suite=0, etat="ACTIVE", motif=None, pause=None):
    return (
        jour or date.today(),
        prises,
        0,
        prises,
        pertes_suite,
        -1.5,
        -0.25,
        etat,
        pause,
        motif,
    )


def test_les_prises_du_jour_sont_retrouvees_apres_redemarrage(magasin):
    """40 prises déjà prises → le nouveau processus doit encore refuser d'ouvrir."""
    magasin["ligne"] = une_ligne(prises=40)
    nouveau = un_garde_fou(max_trades_per_day=40)

    autorise, motif = nouveau.can_open_trade(size_usdt=15.0, stop_percent=0.3)
    assert autorise is False
    assert "40 trades déjà pris" in motif


def test_la_serie_de_pertes_est_retrouvee_et_rencherit_le_score(magasin):
    magasin["ligne"] = une_ligne(prises=6, pertes_suite=3)
    nouveau = un_garde_fou(score_boost_per_loss=0.5)

    # Le scanner lit le boost sans toujours interroger le pare-feu avant :
    # la relecture doit se déclencher là aussi.
    assert nouveau.get_score_boost() == pytest.approx(1.5)
    assert nouveau.consecutive_losses == 3


def test_une_pause_en_cours_reste_en_cours(magasin):
    magasin["ligne"] = une_ligne(
        prises=6,
        pertes_suite=5,
        etat="PAUSED",
        motif="5 pertes consécutives",
        pause=datetime.now() + timedelta(minutes=20),
    )
    nouveau = un_garde_fou()

    autorise, motif = nouveau.can_open_trade(size_usdt=15.0)
    assert autorise is False
    assert "5 pertes consécutives" in motif


def test_un_arret_ne_se_releve_pas_en_redemarrant(magasin):
    """Un STOPPED d'un jour précédent reste bloquant : il se lève à la main."""
    magasin["ligne"] = une_ligne(
        jour=date.today() - timedelta(days=1),
        prises=39,
        etat="STOPPED",
        motif="Drawdown critique: -5.20%",
    )
    nouveau = un_garde_fou()

    assert nouveau.daily_trades == 0  # le jour a changé : les compteurs repartent
    autorise, motif = nouveau.can_open_trade(size_usdt=15.0)
    assert autorise is False
    assert "Drawdown critique" in motif


def test_sans_ligne_en_base_le_garde_fou_demarre_a_zero(magasin):
    nouveau = un_garde_fou()
    assert nouveau.daily_trades == 0
    assert nouveau.can_open_trade(size_usdt=15.0)[0] is True


# ── pas de base, pas de panique ──────────────────────────────────────────────


def test_sans_base_les_plafonds_restenent_en_memoire(monkeypatch):
    import core.postgresql_datalogger as scribe

    monkeypatch.setattr(scribe, "_pg_datalogger_instance", None)
    garde_fou = un_garde_fou(max_trades_per_day=1)

    assert garde_fou.can_open_trade(size_usdt=15.0)[0] is True
    garde_fou.record_trade("A/USDT:USDT", pnl_pct=0.2, pnl_usdt=0.03)
    assert garde_fou.can_open_trade(size_usdt=15.0)[0] is False


def test_une_base_morte_ne_bloque_pas_le_robot(monkeypatch):
    @contextlib.contextmanager
    def connexion_journal():
        raise ConnectionError("base indisponible")
        yield None  # pragma: no cover

    import core.postgresql_datalogger as scribe

    monkeypatch.setattr(scribe, "connexion_journal", connexion_journal)
    monkeypatch.setattr(scribe, "_pg_datalogger_instance", ScribeActif())
    monkeypatch.setitem(TRADING_CONFIG, "trading_cb_persister", True)

    garde_fou = un_garde_fou()
    assert garde_fou.can_open_trade(size_usdt=15.0)[0] is True
    garde_fou.record_trade("A/USDT:USDT", pnl_pct=-0.3, pnl_usdt=-0.045)


# ── la migration ─────────────────────────────────────────────────────────────


def test_la_migration_ajoute_sans_rien_casser():
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parent.parent
        / "database"
        / "migrations"
        / "add_compteurs_garde_fou_2026_11_19.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS circuit_breaker_etat" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql
    for defense in ("DROP TABLE", "DROP COLUMN", "TRUNCATE", "DELETE FROM"):
        assert defense not in sql.upper()

"""Les plafonds de dégâts doivent bloquer l'ouverture, pas seulement la remarquer.

Pourquoi ce fichier existe : le pare-feu de trading (pause après une série de
pertes, pause à -2 % de perte sur la journée, arrêt à -5 %) existait depuis le
début, mesurait, notait — mais `can_trade()` n'était appelé que par de vieux
scripts de vérification (`scripts/test_sprint1_integration.py`). Le chemin
d'ouverture d'une position ne lui demandait jamais son avis. Il n'y avait
davantage ni plafond de prises par jour, ni plafond de perte par prise.
"""

import inspect

from core.trading_circuit_breaker import CircuitBreakerState, TradingCircuitBreaker
from config import TRADING_CONFIG
import pytest


@pytest.fixture(autouse=True)
def garde_fou_sans_base_vivante(monkeypatch):
    # Un test unitaire ne doit jamais lire les compteurs du robot en marche.
    monkeypatch.setitem(TRADING_CONFIG, "trading_cb_persister", False)
    monkeypatch.setattr(TradingCircuitBreaker, "_log_event_to_db", lambda self, event: None)



def pare_feu(**reglages):
    return TradingCircuitBreaker(**reglages)


def test_rien_ne_bloque_tant_qu_on_restait_sous_les_plafonds():
    feu = pare_feu(max_trades_per_day=5, max_size_per_trade_usdt=50.0,
                   max_loss_per_trade_usdt=5.0)
    autorise, motif = feu.can_open_trade(size_usdt=15.0, stop_percent=0.30)
    assert autorise is True
    assert motif == ""


def test_le_plafond_de_prises_du_jour_bloque_la_suivante():
    feu = pare_feu(max_trades_per_day=3)
    for _ in range(3):
        feu.record_trade("TEST/USDT:USDT", pnl_pct=0.4, pnl_usdt=0.06)

    autorise, motif = feu.can_open_trade(size_usdt=15.0, stop_percent=0.30)
    assert autorise is False
    assert "3 trades déjà pris aujourd'hui" in motif


def test_une_prise_plus_grosse_que_le_plafond_est_refusee():
    feu = pare_feu(max_size_per_trade_usdt=50.0)
    autorise, motif = feu.can_open_trade(size_usdt=60.0, stop_percent=0.30)
    assert autorise is False
    assert "au-dessus du plafond" in motif


def test_une_prise_dont_le_stop_vait_trop_loin_est_refusee():
    """200 USDT engagés avec un stop à 1 % = 2 USDT perdus, plafond à 1 USDT."""
    feu = pare_feu(max_loss_per_trade_usdt=1.0, max_size_per_trade_usdt=1000.0)
    autorise, motif = feu.can_open_trade(size_usdt=200.0, stop_percent=1.0)
    assert autorise is False
    assert "ferait perdre 2.00 USDT" in motif


def test_la_pause_apres_une_series_de_pertes_interdit_ouvrir():
    feu = pare_feu(max_consecutive_losses=2, pause_duration_minutes=30)
    feu.record_trade("A/USDT:USDT", pnl_pct=-0.4, pnl_usdt=-0.06)
    feu.record_trade("B/USDT:USDT", pnl_pct=-0.5, pnl_usdt=-0.07)

    assert feu.state == CircuitBreakerState.PAUSED
    autorise, motif = feu.can_open_trade(size_usdt=15.0, stop_percent=0.30)
    assert autorise is False
    assert "2 pertes consécutives" in motif


def test_l_arret_apres_drawdown_critique_interdit_ouvrir():
    feu = pare_feu(daily_drawdown_stop_pct=-5.0, max_consecutive_losses=99)
    feu.record_trade("A/USDT:USDT", pnl_pct=-3.0, pnl_usdt=-30.0)
    feu.record_trade("B/USDT:USDT", pnl_pct=-3.0, pnl_usdt=-30.0)

    assert feu.state == CircuitBreakerState.STOPPED
    autorise, motif = feu.can_open_trade(size_usdt=15.0, stop_percent=0.30)
    assert autorise is False
    assert "pare-feu" in motif


def test_les_plafonds_se_reglent_a_chaud():
    feu = pare_feu(max_trades_per_day=40)
    feu.update_config(max_trades_per_day=2)
    feu.record_trade("A/USDT:USDT", pnl_pct=0.2, pnl_usdt=0.03)
    feu.record_trade("B/USDT:USDT", pnl_pct=0.2, pnl_usdt=0.03)

    autorise, motif = feu.can_open_trade(size_usdt=15.0, stop_percent=0.30)
    assert autorise is False
    assert "plafond 2" in motif


def test_interrupteur_etint_la_pause_mais_pas_les_plafonds(monkeypatch):
    """Éteindre le pare-feu coupe la pause-après-pertes, pas les plafonds."""
    from config import TRADING_CONFIG

    monkeypatch.setitem(TRADING_CONFIG, "trading_circuit_breaker_enabled", False)
    feu = pare_feu(max_consecutive_losses=2, max_trades_per_day=2)
    feu.record_trade("A/USDT:USDT", pnl_pct=-0.4, pnl_usdt=-0.06)
    feu.record_trade("B/USDT:USDT", pnl_pct=-0.5, pnl_usdt=-0.07)

    assert feu.state == CircuitBreakerState.PAUSED
    autorise, motif = feu.can_open_trade(size_usdt=15.0, stop_percent=0.30)
    assert autorise is False
    assert "trades déjà pris" in motif


def test_interrupteur_allume_bloque_des_une_pause(monkeypatch):
    from config import TRADING_CONFIG

    monkeypatch.setitem(TRADING_CONFIG, "trading_circuit_breaker_enabled", True)
    feu = pare_feu(max_consecutive_losses=2)
    feu.record_trade("A/USDT:USDT", pnl_pct=-0.4, pnl_usdt=-0.06)
    feu.record_trade("B/USDT:USDT", pnl_pct=-0.5, pnl_usdt=-0.07)

    autorise, motif = feu.can_open_trade(size_usdt=15.0, stop_percent=0.30)
    assert autorise is False
    assert "pare-feu" in motif


def test_l_ouverture_d_une_position_interroge_le_pare_feu():
    """Le garde-fou : l'appel ne doit pas disparaître du chemin d'ouverture."""
    from core.position_manager import PositionManager

    source = inspect.getsource(PositionManager.open_position)
    assert "can_open_trade(" in source, (
        "open_position ne demande plus l'avis du pare-feu : on revient au cas du "
        "18/11/2026 où pause, arrêt et plafonds étaient notés sans jamais bloquer"
    )

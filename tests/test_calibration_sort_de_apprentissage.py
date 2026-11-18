"""En essai à blanc, le robot doit quand même pouvoir sortir de l'apprentissage.

Pourquoi ce fichier existe : « ai-je assez de recul ? » se demandait en comparant
le **total pondéré** au seuil de 10 trades. Or un trade en essai à blanc porte un
poids de 0,2 (il compte moins qu'un trade réel) : il fallait donc environ **50
essais par case** pour que la calibration commence à servir. Mesure du
18/11/2026 : la case SHORT / confiance 50 % et plus contenait 22 trades réels
pour seulement 4,33 pondérés — la phase d'apprentissage ne se terminait jamais,
et le robot répondait `learning_phase` à chaque demande de décision.

La pondération garde son rôle là où elle a un sens (le pourcentage de réussite
affiché reste pondéré : un trade réel pèse plus lourd qu'un essai). La réponse à
« ai-je assez d'exemples ? », elle, se fait sur le nombre d'exemples.
"""

from datetime import datetime, timezone

import pytest

from config import TRADING_CONFIG
from ml.calibration import CalibrationStats, MLCalibrationManager


def _stats(direction, bucket, trades, pondere, winrate):
    return CalibrationStats(
        direction=direction,
        confidence_bucket=bucket,
        weighted_wins=pondere * winrate / 100,
        weighted_total=pondere,
        total_trades=trades,
        actual_winrate=winrate,
        avg_pnl_pct=0.45,
        total_pnl_usdt=1.0,
    )


@pytest.fixture
def gestionnaire_avec_cache(monkeypatch):
    """Un gestionnaire de calibration qui lit un cache préparé, sans base."""
    monkeypatch.setitem(TRADING_CONFIG, "ml_calib_min_trades", 10)
    monkeypatch.setitem(TRADING_CONFIG, "ml_calib_bucket_size", 5)
    monkeypatch.setitem(TRADING_CONFIG, "ml_calib_min_winrate", 40.0)
    monkeypatch.setitem(TRADING_CONFIG, "ml_calibration_enabled", True)

    gestionnaire = MLCalibrationManager(db_pool=None)
    # Sans base : on coupe la vérification de changement de modèle, qui sinon
    # irait chercher le scribe PostgreSQL partagé et polluerait les autres tests.
    monkeypatch.setattr(gestionnaire, "check_model_change_and_auto_reset", lambda: False)
    gestionnaire._cache = {}
    gestionnaire._cache_timestamp = datetime.now(timezone.utc)
    return gestionnaire


def test_22_essais_huit_cas_pondere_suffisent_a_apprendre(gestionnaire_avec_cache):
    """Le cas réel observé : 22 trades, 4,33 pondérés, 63,7 % de réussite."""
    gestionnaire_avec_cache._cache[("SHORT", "50+")] = _stats(
        "SHORT", "50+", trades=22, pondere=4.33, winrate=63.7
    )
    assert gestionnaire_avec_cache.get_calibrated_winrate("SHORT", 55.0) == pytest.approx(
        63.7
    )


def test_en_dessous_du_nombre_de_trades_on_garde_apprendre(gestionnaire_avec_cache):
    gestionnaire_avec_cache._cache[("LONG", "45-50")] = _stats(
        "LONG", "45-50", trades=9, pondere=1.8, winrate=40.0
    )
    assert gestionnaire_avec_cache.get_calibrated_winrate("LONG", 47.0) is None


def test_la_decision_reflechit_desormais_les_statistiques(gestionnaire_avec_cache):
    gestionnaire_avec_cache._cache[("SHORT", "50+")] = _stats(
        "SHORT", "50+", trades=22, pondere=4.33, winrate=63.7
    )
    pris, winrate, motif = gestionnaire_avec_cache.should_take_trade("SHORT", 55.0)
    assert motif != "learning_phase"
    assert pris is True
    assert winrate == pytest.approx(63.7)


def test_une_case_tres_mauvaise_est_desormais_filtrée(gestionnaire_avec_cache):
    """Avec assez d'exemples, une case qui perd souvent est écartée."""
    gestionnaire_avec_cache._cache[("LONG", "40-45")] = _stats(
        "LONG", "40-45", trades=12, pondere=2.4, winrate=12.0
    )
    pris, winrate, motif = gestionnaire_avec_cache.should_take_trade("LONG", 42.0)
    assert pris is False
    assert motif == "rejected_low_winrate"

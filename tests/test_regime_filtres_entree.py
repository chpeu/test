"""Le barème par régime doit atteindre les filtres d'entrée, même en mode FIXE.

Pourquoi ce fichier existe : le 18/11/2026, une seule liste de clés faisait
sauter tous les réglages liés à l'écart-type (ATR) quand le mode TP/SL était
« FIXE ». Elle visait les stops, mais elle gelait aussi les planchers des
filtres d'entrée. Résultat mesuré sur 1 117 analyses : le robot qualifiait le
marché de CALME, son barème CALME demande un ATR 5 min d'au moins 0,10 %, le
filtre en exigeait 0,35 % — et 63 des 79 rejets « ATR sous-optimal » seraient
passés sous son propre barème. Une seule position ouverte sur tout un après-midi.

Ce que ces tests garantissent :
  - les planchers d'ATR des filtres d'entrée suivent bien le régime ;
  - les multiplicateurs de stop, eux, restent figés en mode FIXE (l'intention
    d'origine de la règle est préservée) ;
  - en mode ATR, les multiplicateurs de stop passent (l'autre branche vit).
"""

import pytest

from config import TRADING_CONFIG
from utils.effective_config import (
    clear_all_adjustments,
    get_effective_value,
    set_regime_adjustments,
)


@pytest.fixture
def mode_fixe_regime_actif():
    """Reproduit la configuration réelle du robot ce jour-là."""
    avant = {
        "tp_sl_mode": TRADING_CONFIG.get("tp_sl_mode"),
        "market_regime_enabled": TRADING_CONFIG.get("market_regime_enabled"),
    }
    TRADING_CONFIG["tp_sl_mode"] = "FIXE"
    TRADING_CONFIG["market_regime_enabled"] = True
    clear_all_adjustments()
    yield
    clear_all_adjustments()
    for cle, valeur in avant.items():
        TRADING_CONFIG[cle] = valeur


def test_planche_atr_5min_suivie_le_regime_en_mode_fixe(mode_fixe_regime_actif):
    set_regime_adjustments({"optimal_atr_min_5m": 0.10})
    assert get_effective_value("optimal_atr_min_5m") == 0.10


def test_planche_atr_1min_suivie_le_regime_en_mode_fixe(mode_fixe_regime_actif):
    set_regime_adjustments({"optimal_atr_min_1m": 0.06})
    assert get_effective_value("optimal_atr_min_1m") == 0.06


def test_multiplicateur_de_stop_reste_fege_en_mode_fixe(mode_fixe_regime_actif):
    base = TRADING_CONFIG["atr_mult_sl"]
    set_regime_adjustments({"atr_mult_sl": base + 0.7})
    assert get_effective_value("atr_mult_sl") == base


def test_taux_de_change_de_stop_reste_fege_en_mode_fixe(mode_fixe_regime_actif):
    base = TRADING_CONFIG["sl_exchange_percent"]
    set_regime_adjustments({"sl_exchange_percent": 9.9})
    assert get_effective_value("sl_exchange_percent") == base


def test_en_mode_atr_le_multiplicateur_de_stop_passe(mode_fixe_regime_actif):
    TRADING_CONFIG["tp_sl_mode"] = "ATR"
    base = TRADING_CONFIG["atr_mult_sl"]
    set_regime_adjustments({"atr_mult_sl": base + 0.7})
    assert get_effective_value("atr_mult_sl") == base + 0.7

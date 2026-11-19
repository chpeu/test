"""Un réglage écrit dans `config.py` doit être celui que la machine utilise.

Pourquoi ce fichier existe : `config.py` n'est pas la dernière parole. Trois
endroits se suivent et le dernier gagne :

    config.py  →  config/trading_config.json  →  config_overrides.json

Le 19/11/2026, une correction de la distance de sortie (0,30 % → 0,16 %) écrite
dans `config.py` était sans effet : `config_overrides.json` — le fichier que
l'interface et les optimiseurs réécrivent — poussait cette valeur à 0,4 % et son
palier à 1,45 %. Le correctif était mort dès la naissance, et rien dans les logs
ne le disait.

Ce que ces tests garantissent : pour les réglages touchés pendant cette séance,
la valeur **déclarée dans config.py** et la valeur **vue par le programme** sont
les mêmes. Si un optimiseur ou l'interface les écarte l'une de l'autre, la
discussion repart sur un chiffre que personne n'utilise — et le test le dit.
"""

import ast
from pathlib import Path

import pytest

from config import TRADING_CONFIG

CHEMIN_CONFIG_PY = Path(__file__).resolve().parent.parent / "config.py"

# (clé, ce que la valeur commande)
REGLAGES_SURVEILLES = [
    ("trailing_min_distance", "distance la plus serrée du stop suiveur"),
    ("trailing_max_distance", "distance la plus lâche du stop suiveur"),
    ("trailing_pnl_cap", "gain où la distance maximale est atteinte"),
    ("trading_circuit_breaker_enabled", "le garde-fou tourne ou non"),
    ("trading_cb_max_consecutive_losses", "pertes consécutives avant pause"),
    ("trading_cb_daily_drawdown_pause_pct", "perte du jour déclenchant la pause"),
    ("trading_cb_daily_drawdown_stop_pct", "perte du jour déclenchant l'arrêt"),
    ("trading_cb_max_trades_per_day", "prises maximales dans la journée"),
    ("trading_cb_max_size_per_trade_usdt", "valeur maximale d'une prise"),
    ("trading_cb_max_loss_per_trade_usdt", "perte maximale d'une prise"),
    ("ml_calib_dryrun_weight", "poids d'un essai à blanc dans l'apprentissage"),
]


def valeur_declaree(cle: str):
    """Retrouve la valeur écrite en clair dans `config.py` (avant overrides)."""
    arbre = ast.parse(CHEMIN_CONFIG_PY.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Dict):
            for touche, valeur in zip(noeud.keys, noeud.values, strict=True):
                if isinstance(touche, ast.Constant) and touche.value == cle:
                    if isinstance(valeur, ast.Constant):
                        return valeur.value
                    if (
                        isinstance(valeur, ast.UnaryOp)
                        and isinstance(valeur.op, ast.USub)
                        and isinstance(valeur.operand, ast.Constant)
                    ):
                        # Les nombres négatifs s'écrivent « -2.0 » : pour Python,
                        # ce n'est pas un nombre mais une soustraction unaire.
                        return -valeur.operand.value
    return None


@pytest.mark.parametrize("cle", [c for c, _ in REGLAGES_SURVEILLES])
def test_le_reglage_declare_est_celui_utilise(cle):
    declare = valeur_declaree(cle)
    assert declare is not None, f"{cle} n'est plus écrit en clair dans config.py"
    utilise = TRADING_CONFIG.get(cle)
    assert utilise is not None, f"{cle} a disparu de la configuration en marche"
    assert utilise == declare, (
        f"{cle} : config.py écrit {declare}, le programme utilise {utilise}. "
        "Un fichier de priorité (config/trading_config.json ou "
        "config_overrides.json) a un avis différent."
    )


def test_la_config_vivante_n_heberge_plus_de_dechets_de_tests():
    """`test_key` et `number` traînaient dans la config vivante depuis un test.

    On kontrolle le fichier lui-même, pas la configuration en mémoire : un test
    qui écrit peut polluer après l'import de `config`.
    """
    import json

    chemin = Path(__file__).resolve().parent.parent / "config_overrides.json"
    if not chemin.exists():
        return
    reglages = json.loads(chemin.read_text(encoding="utf-8"))
    # `ml_metric` vient d'un vieux test de route qui postait {"metric": "accuracy"}
    # sur /api/ml/optimize/apply sans dire dans quel fichier ecrire.
    for dechet in ("test_key", "number", "ml_metric"):
        assert dechet not in reglages, (
            f"{dechet} est revenu dans config_overrides.json : un test écrit dans "
            "le fichier du robot au lieu d'un fichier temporaire"
        )

    suspects = [cle for cle in reglages if cle.startswith("test") or cle.endswith("_test")]
    assert not suspects, f"des cles de test se sont glissees dans la config vivante: {suspects}"

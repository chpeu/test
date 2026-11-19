"""Le stop de sécurité doit être réellement posé chez MEXC.

Mesure du 19/11/2026 : `open_position` calculait le prix du stop MEXC (marge
×1.2 sur le stop du robot), l'arrondissait à la précision du contrat,
l'affichait dans les logs sous « 📐 SL MEXC MARGE »… et ne l'envoyait jamais à
l'échange. La fonction qui sait le poser existait depuis le début
(`set_stop_loss_take_profit`) mais n'était appelée par personne. Résultat : en
compte réel, le stop n'existait que dans la mémoire du programme — une coupure
réseau ou un redémarrage laissait la position sans filet.
"""

from pathlib import Path


from config import TRADING_CONFIG
from trading.live_order_manager_futures import LiveOrderManagerFutures


def un_gerant(*, dry_run: bool) -> LiveOrderManagerFutures:
    """Objet vide, sans connexion ni credentials : on teste la décision, pas le réseau."""
    gestionnaire = LiveOrderManagerFutures.__new__(LiveOrderManagerFutures)
    gestionnaire.dry_run = dry_run
    gestionnaire.telegram_notifier = None
    return gestionnaire


def test_en_essai_a_blanc_rien_n_est_envoye_a_lechange():
    gestionnaire = un_gerant(dry_run=True)
    appels = []
    gestionnaire.set_stop_loss_take_profit = lambda *a, **k: appels.append(1) or True

    tente, prix = gestionnaire._poser_stop_echange("ZEC/USDT:USDT", "LONG", 14.5)
    assert (tente, prix) == (False, None)
    assert appels == []


def test_sans_prix_de_stop_rien_n_est_tente():
    gestionnaire = un_gerant(dry_run=False)
    assert gestionnaire._poser_stop_echange("ZEC/USDT:USDT", "LONG", None) == (False, None)
    assert gestionnaire._poser_stop_echange("ZEC/USDT:USDT", "LONG", 0.0) == (False, None)


def test_en_live_le_stop_part_a_lechange():
    gestionnaire = un_gerant(dry_run=False)
    recus = []

    def fausse_pose(symbol, direction, stop_loss_price=None, take_profit_price=None):
        recus.append((symbol, direction, stop_loss_price, take_profit_price))
        return True

    gestionnaire.set_stop_loss_take_profit = fausse_pose
    tente, prix = gestionnaire._poser_stop_echange("ZEC/USDT:USDT", "SHORT", 16.4)
    assert (tente, prix) == (True, 16.4)
    # pas de take-profit côté échange : la sortie appartient au robot (stop suiveur)
    assert recus == [("ZEC/USDT:USDT", "SHORT", 16.4, None)]


def test_echange_refuse_on_retente_puis_on_declare_lechec(monkeypatch):
    gestionnaire = un_gerant(dry_run=False)
    appels = []

    def pose_refusee(*args, **kwargs):
        appels.append(1)
        return False

    monkeypatch.setattr("time.sleep", lambda *_: None)
    gestionnaire.set_stop_loss_take_profit = pose_refusee

    tente, prix = gestionnaire._poser_stop_echange("ZEC/USDT:USDT", "LONG", 14.5)
    assert (tente, prix) == (True, None)
    assert len(appels) == 2, "deux tentatives, pas une seule ni trois"


def test_la_politique_interdit_une_position_nue():
    """Si le stop n'a pas pu être posé, la position venant d'ouvrir est refermée."""
    assert TRADING_CONFIG.get("live_exige_stop_echange") is True


def test_l_ouverture_appelle_bien_le_filet():
    """Garde-fou : le calcul du stop ne peut plus redevenir un simple log."""
    chemin = (
        Path(__file__).resolve().parent.parent
        / "trading"
        / "live_order_manager_futures.py"
    )
    source = chemin.read_text(encoding="utf-8")
    debut = source.index("def open_position(")
    fin = source.index("def close_position(")
    corps = source[debut:fin]
    assert "_poser_stop_echange(" in corps, (
        "le chemin d'ouverture ne pose plus de stop côté échange : la position "
        "redevient nue si le robot meurt"
    )
    assert "live_exige_stop_echange" in corps, (
        "la politique « pas de position nue » a sauté du chemin d'ouverture"
    )


def test_le_resultat_transport_le_prix_du_stop_pose():
    from dataclasses import fields

    from trading.live_order_manager_futures import FuturesOrderResult

    noms = {f.name for f in fields(FuturesOrderResult)}
    assert "exchange_stop_price" in noms

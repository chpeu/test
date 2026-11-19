"""Callback périodique : évaluer les dossiers refusés mis de côté.

Appelé par le Scheduler (voir core/scheduler.py) toutes les
`carnet_fantome_eval_minutes` minutes. Il ne prend aucune décision de trading :
il relit les dossiers notés par le carnet fantôme et écrit ce que le prix a fait
après le refus.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _client_de_prix():
    """Le client de bougies déjà utilisé par l'analyse (pas de nouvelle connexion)."""
    try:
        from core.callbacks import scanner_loop as module_scanner

        analyseur: Optional[object] = getattr(module_scanner, "_analyzer", None)
        if analyseur is not None:
            return getattr(analyseur, "client", None)
    except Exception as exc:
        logger.debug(f"Carnet fantôme: client indisponible ({exc})")
    return None


async def carnet_fantome_callback() -> None:
    from config import TRADING_CONFIG

    if not TRADING_CONFIG.get("carnet_fantome_enabled", True):
        return

    client = _client_de_prix()
    if client is None or not hasattr(client, "fetch_ohlcv"):
        logger.debug("Carnet fantôme: pas encore de client de bougies, passe sautée")
        return

    from core.carnet_fantome import evaluer_fantomes

    await evaluer_fantomes(
        client.fetch_ohlcv,
        limite=int(TRADING_CONFIG.get("carnet_fantome_limite", 30)),
        minutes_max=int(TRADING_CONFIG.get("carnet_fantome_fenetre_minutes", 60)),
    )

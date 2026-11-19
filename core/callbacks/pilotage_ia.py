"""Callback périodique du pilotage IA.

Appelé par le Scheduler (voir core/scheduler.py) toutes les `pilote_ia_minutes`
minutes. Le travail est bloquant (requêtes en base + une demande au modèle, qui
peut durer une minute) : on le fait donc tourner dans un fil à part pour ne pas
geler la boucle d'événements — le scanner continuerait de scanner pendant que
l'IA rédige son bilan.

Aucune décision de trading ici : `core/pilotage_ia.py` décide du niveau (0 à 3),
vérifie la cage et les bornes avant d'écrire quoi que ce soit.
"""

import logging

logger = logging.getLogger(__name__)


async def pilotage_ia_callback() -> None:
    from config import TRADING_CONFIG

    if not TRADING_CONFIG.get("pilote_ia_actif", True):
        return

    import asyncio

    from core.pilotage_ia import boucle

    try:
        resultat = await asyncio.to_thread(boucle)
        logger.info(f"🧠 Pilotage IA — tour terminé: {resultat}")
    except Exception as exc:  # un bilan raté ne doit pas arrêter le robot
        logger.warning(f"⚠️ Pilotage IA — tour interrompu: {type(exc).__name__}: {exc}")

"""
Verrou de visite (sans dépendance web : utilisable depuis `core/`).

But : ouvrir l'interface sur un réseau (Tailscale, LAN) pour la faire tester sans
qu'un clic perdu — ou le démarrage automatique — ne déclenche une session de
trading réelle.

Pourquoi un verrou séparé : le réglage `PAPER_TRADING_MODE` du `.env` n'est lu
nulle part ailleurs dans le projet (vérifié par recherche dans tout le dépôt) :
il n'offre donc aucun filet. Et `core/bootstrap.py` appelle `sched.start()` tout
seul à l'étape 7 : le robot se met à scanner dès l'allumage du serveur, sans
qu'on appuie sur quoi que ce soit.

Les trois portes qui peuvent mettre le robot en route sont donc :
  1. le boot (`core/bootstrap.py`, étape 7) ;
  2. `POST /api/start` et `POST /api/scanner/start` ;
  3. la commande WebSocket `start_scanner` (le bouton « Start Scanner »).

Avec le verrou armé, les trois sont refusées. Le serveur démarre, l'interface
répond (configuration, historique, statistiques, graphiques), mais aucune boucle
de scan ne tourne et aucun ordre ne peut partir.

Activation : variable d'environnement `VISITE_SANS_SCAN=1` au lancement.
Absente = comportement normal, rien ne change.
"""

import logging
import os

logger = logging.getLogger(__name__)

RAISON = (
    "Verrou de visite actif (VISITE_SANS_SCAN=1) : ni scan ni ordres depuis "
    "l'interface."
)

_VALEURS_VRAIES = ("1", "true", "oui", "yes")


def scan_lock_active() -> bool:
    """Le verrou est-il armé ? Relu à chaque appel : pas de redémarrage nécessaire."""
    return os.getenv("VISITE_SANS_SCAN", "").strip().lower() in _VALEURS_VRAIES


def log_refus(where: str) -> None:
    """Trace le refus, pour qu'on puisse le montrer après coup."""
    logger.warning(f"🔒 {where} refusé : {RAISON}")


def arm_scheduler_at_boot(sched, state) -> bool:
    """Démarre la boucle du robot au démarrage — sauf si le verrou de visite est armé.

    Renvoie `True` si le scheduler a bien été lancé. C'est la porte la plus
    importante des trois : c'est la seule que personne ne clique.
    """
    if scan_lock_active():
        log_refus("démarrage automatique du scheduler (boot)")
        state.set_is_scanning(False)
        return False

    sched.start()
    state.set_is_scanning(True)
    return True

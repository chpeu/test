"""Frais réels de chaque paire, relus chez MEXC, et décision « prise autorisée ? ».

Pourquoi ce module existe (mesuré le 19/11/2026) :

  - le tri des paires lisait `market['taker']` dans la table ccxt, et ccxt **ne
    recharge jamais cette table** : `load_markets()` renvoie le cache de la
    première connexion. La boucle de rafraîchissement tournait toutes les 90
    secondes avec des frais figés depuis le démarrage ;
  - or MEXC fait entrer et sortir des contrats de sa zone « 0 frais » sans
    prévenir. Un contrat passé payant restait tradé des jours ;
  - mesure sur la base : 95 prises sur des paires à 0 frais (+10,27 % cumulés),
    3 prises sur SOL payante (-0,14 %), et **0 USDT de frais écrit** sur les
    98 trades — donc aucun moyen de voir la fuite.

Le module garde sa propre petite copie de la table des frais (un client ccxt à
lui, rechargé toutes les `frais_actualiser_minutes`), pour ne jamais toucher au
cache partagé par le reste du robot.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Paires traditionnellement payantes, gardées seulement si on le demande.
MAJEURES = ("BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT")

_client = None
_table: Dict[str, Tuple[float, float]] = {}
_horodatage = 0.0


def _reglages() -> dict:
    from config import TRADING_CONFIG

    return {
        "actualiser_minutes": float(TRADING_CONFIG.get("frais_actualiser_minutes", 30.0)),
        "max_pct": float(TRADING_CONFIG.get("entree_frais_max_pct", 0.0)),
        "autoriser_payantes": bool(TRADING_CONFIG.get("entree_autoriser_paires_payantes", False)),
        "liste_blanche": set(TRADING_CONFIG.get("entree_paires_payantes_autorisees", []) or []),
    }


async def _recharger() -> Dict[str, Tuple[float, float]]:
    """Recharger la table des frais dans un client qui n'appartient qu'à ce module."""
    global _client, _table, _horodatage

    import ccxt.async_support as ccxt

    if _client is None:
        _client = ccxt.mexc({"options": {"defaultType": "swap"}, "timeout": 15000})

    # `load_markets()` renvoie le cache s'il existe : on vide la copie de CE
    # client uniquement. Ceux du robot ne sont pas touchés.
    _client.markets = None
    marches = await _client.load_markets()

    table = {}
    for symbole, marche in marches.items():
        if not marche.get("swap") or not marche.get("active"):
            continue
        taker = marche.get("taker")
        maker = marche.get("maker")
        if taker is None or maker is None:
            continue
        table[symbole] = (float(taker), float(maker))

    if table:
        _table = table
        _horodatage = time.monotonic()
        zero = sum(1 for t, _ in table.values() if t == 0)
        logger.info(f"💸 Table des frais MEXC relue : {len(table)} contrats · {zero} à 0 frais")
    return _table


async def table_frais(force: bool = False) -> Dict[str, Tuple[float, float]]:
    """Table {symbole: (taker, maker)}, rechargée si elle a vieilli."""
    global _table

    actualiser = _reglages()["actualiser_minutes"]
    age = time.monotonic() - _horodatage
    if force or not _table or age >= actualiser * 60:
        try:
            await _recharger()
        except Exception as erreur:  # ne jamais bloquer une décision sur un réseau capricieux
            logger.warning(f"⚠️ Lecture des frais MEXC impossible ({erreur}) — table en cache conservée")
    return _table


def paire_acceptable(
    symbole: str,
    taker: Optional[float],
    *,
    max_pct: float = 0.0,
    autoriser_payantes: bool = False,
    liste_blanche=(),
) -> bool:
    """La logique du tri, isolée pour être testable sans réseau.

    `taker` est une fraction (0.0004 = 0,04 %). `max_pct` est en points de
    pourcentage (0.0 = uniquement les paires à 0 frais).
    """
    if taker is None:
        # Frais inconnus : on ne devine pas. Sans information, on refuse —
        # une prise payante non détectée coûte plus cher qu'une occasion ratée.
        return False

    if symbole in liste_blanche:
        return True

    if taker * 100 <= max_pct:
        return True

    if autoriser_payantes and symbole in MAJEURES:
        return True

    return False


def _decision(symbole: str, reglages: dict) -> Tuple[bool, str]:
    taker = _table.get(symbole, (None, None))[0]
    if paire_acceptable(
        symbole,
        taker,
        max_pct=reglages["max_pct"],
        autoriser_payantes=reglages["autoriser_payantes"],
        liste_blanche=reglages["liste_blanche"],
    ):
        return True, taker
    if taker is None:
        return False, f"frais inconnus pour {symbole} (table MEXC introuvable)"
    return False, f"paire payante : taker {taker*100:.3f} % > {reglages['max_pct']:.2f} % autorisé"


async def autoriser_prise(symbole: str) -> Tuple[bool, str]:
    """Porte d'entrée (async) : recharge la table si elle a vieilli."""
    await table_frais()
    autorise, motif = _decision(symbole, _reglages())
    return autorise, motif if isinstance(motif, str) else ""


def verifier_prise(symbole: str) -> Tuple[bool, str]:
    """Porte d'entrée synchrone, pour le chemin d'ouverture d'une prise.

    Ne fait aucun appel réseau : le scan a rechargé la table quelques instants
    avant, donc elle est fraîche. `open_position` n'est pas une coroutine : on ne
    peut pas y attendre MEXC.
    """
    autorise, motif = _decision(symbole, _reglages())
    return autorise, motif if isinstance(motif, str) else ""


def lire_frais(symbole: str) -> Tuple[Optional[float], Optional[float]]:
    """(taker, maker) de la dernière table lue — sans appel réseau."""
    return _table.get(symbole, (None, None))


async def fermer() -> None:
    """Fermer le client de secours (utilisé à l'arrêt propre du robot)."""
    global _client
    if _client is not None:
        try:
            await _client.close()
        except Exception as erreur:  # noqa: BLE001 - nettoyage, rien à décider
            logger.debug(f"Client frais MEXC fermé avec erreur: {erreur}")
        _client = None

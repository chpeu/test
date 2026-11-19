"""Carnet fantôme : garder la trace des dossiers refusés, et leur verdict.

Le 18/11/2026, l'entonnoir mesuré disait : 8 000 analyses, ~100 signaux détectés
en 1 minute, 1 à 2 positions ouvertes. Entre les deux, des refus. Le robot note
ses prises (`trades`) et ses analyses (`scan_logs`) — mais rien sur les dossiers
écartés alors que le signal existait. Personne ne peut donc dire si un filtre fait
perdre de l'argent ou en fait gagner.

Le principe, comme un videur qui tiendrait un carnet : on note le dossier refusé
(symbole, sens, prix d'entrée, score, motif) et on laisse le prix répondre plus
tard. Une passe régulière relit les dossiers en attente, récupère les bougies de
la minute qui a suivi, et écrit le verdict : l'objectif aurait-il été touché avant
le stop ?

Ce module ne change aucune décision de trading. Il écrit dans `ghost_setups`
(voir database/migrations/add_carnet_fantome_2026_11_19.sql) et se lit avec
`scripts/lire_carnet_fantome.py`.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Motif du refus (texte libre du filtre) → famille, pour pouvoir compter.
FAMILLES = (
    ("Volume insuffisant", "volume_filter"),
    ("ATR sous-optimal", "atr_filter"),
    ("Score insuffisant", "score_insufficient"),
    ("SNR trop faible", "snr_filter"),
    ("Pas de breakout", "breakout_filter"),
    ("Pas de structure", "structure_swing"),
    ("Bougie plate", "micro_range"),
    ("RSI", "rsi_final_filter"),
    ("EMA/MACD", "ema_macd_coherence"),
    ("Orderbook", "orderbook"),
)

EN_ATTENTE = "EN_ATTENTE"
GAGNE = "GAGNE"
PERDU = "PERDU"
NEUTRE = "NEUTRE"
DONNEES_MANQUANTES = "DONNEES_MANQUANTES"


def categoriser(motif: str) -> str:
    """Range un motif de refus (texte libre) dans une famille comptable."""
    for index, famille in FAMILLES:
        if index.lower() in (motif or "").lower():
            return famille
    return "autre"


def variation(prix: float, entree: float, sens: str) -> float:
    """Écart en % entre un prix et le prix d'entrée, du point de vue du sens pris."""
    if not entree:
        return 0.0
    ecart = (prix - entree) / entree * 100.0
    return -ecart if sens == "SHORT" else ecart


def verdict(
    bougies: List[List[float]],
    entree: float,
    sens: str,
    sl_pct: float,
    tp_pct: float,
    minutes_max: int = 60,
) -> Dict[str, Any]:
    """Ce que le dossier refusé aurait donné, en parcourant les bougies dans l'ordre.

    Une bougie ccxt = [timestamp, ouverture, haut, bas, clôture, volume].
    Règle prudente : si une même bougie touche l'objectif ET le stop, on compte la
    perte — on ne sait pas dans quel ordre le prix est passé à l'intérieur.
    """
    # Marge de flottant : un prix à 0,60 % peut se calculer 0,5999999999999943.
    # Sans cette tolérance, un verdict se rate pour un cheveu.
    tolerance = 1e-9

    gain_max = 0.0
    perte_max = 0.0
    for index, bougie in enumerate(bougies[:minutes_max]):
        # `variation` retourne un pourcentage **vu du côté du gain** : en SHORT,
        # c'est la mèche basse qui rapporte. On compare donc les deux extrêmes de
        # la bougie sans parler de haut ni de bas.
        deux_cotes = (variation(bougie[2], entree, sens), variation(bougie[3], entree, sens))
        favorable = max(deux_cotes)
        defavorable = min(deux_cotes)
        gain_max = max(gain_max, favorable)
        perte_max = min(perte_max, defavorable)

        objectif_touche = favorable >= tp_pct - tolerance
        stop_touche = defavorable <= -(abs(sl_pct) - tolerance)

        if objectif_touche and stop_touche:
            return _resultat(PERDU, gain_max, perte_max, index + 1)
        if stop_touche:
            return _resultat(PERDU, gain_max, perte_max, index + 1)
        if objectif_touche:
            return _resultat(GAGNE, gain_max, perte_max, index + 1)

    return _resultat(NEUTRE, gain_max, perte_max, min(len(bougies), minutes_max))


def _resultat(statut, gain_max, perte_max, minutes) -> Dict[str, Any]:
    return {
        "statut": statut,
        "gain_max_pct": gain_max,
        "perte_max_pct": perte_max,
        "minutes_avant_verdict": float(minutes),
    }


def reglages_de_reference() -> Tuple[float, float]:
    """Stop et objectif utilisés pour juger un dossier refusé.

    On juge avec les règles du jour (mode FIXE). L'objectif déclaré peut être
    énorme (`tp_percent` est parfois réglé à 5 %, jamais atteint en une heure) :
    on le ramène à l'ordre de grandeur que le robot réalise vraiment.
    """
    from config import TRADING_CONFIG

    sl_pct = abs(float(TRADING_CONFIG.get("sl_percent", 0.22)))
    tp_pct = float(TRADING_CONFIG.get("tp_percent", 0.80))
    if tp_pct > 1.5:
        tp_pct = 0.80
    return sl_pct, tp_pct


def enregistrer_refus(
    *,
    symbole: str,
    sens: str,
    prix: float,
    motif: str,
    sl_pct: float,
    tp_pct: float,
    score: Optional[float] = None,
    score_requis: Optional[float] = None,
    atr_pct: Optional[float] = None,
    volume_spike: Optional[float] = None,
    scan_id: Optional[str] = None,
) -> bool:
    """Écrit un dossier refusé dans le carnet. Jamais bloquant pour le scanner."""
    try:
        from core.postgresql_datalogger import connexion_journal

        with connexion_journal() as cnx:
            if cnx is None:
                return False
            with cnx.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ghost_setups (
                        timestamp_scan, symbol, direction, entry_price,
                        score_total, min_score_required, reject_reason,
                        reject_category, atr_pct_1m, volume_spike_1m,
                        sl_pct, tp_pct, scan_id
                    ) VALUES (now(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        symbole,
                        sens,
                        prix,
                        score,
                        score_requis,
                        motif,
                        categoriser(motif),
                        atr_pct,
                        volume_spike,
                        sl_pct,
                        tp_pct,
                        scan_id,
                    ),
                )
            cnx.commit()
        return True
    except Exception as exc:  # le carnet ne doit jamais faire tomber un scan
        logger.debug(f"Carnet fantôme — écriture ignorée (non-bloquant): {exc}")
        return False


async def evaluer_fantomes(
    fetch_ohlcv: Callable[..., Any],
    limite: int = 30,
    minutes_max: int = 60,
    remonte_heures: int = 6,
) -> Tuple[int, int]:
    """Relit les dossiers en attente et écrit leur verdict.

    `fetch_ohlcv(symbol, timeframe, limit)` : coroutine qui rend des bougies ccxt
    (c'est la méthode du client d'analyse). Retourne (évalués, sans données).
    """
    from core.postgresql_datalogger import connexion_journal

    with connexion_journal() as cnx:
        if cnx is None:
            return (0, 0)
        with cnx.cursor() as cur:
            cur.execute(
                """
                SELECT id, symbol, direction, entry_price, sl_pct, tp_pct
                FROM ghost_setups
                WHERE statut = %s
                  AND timestamp_scan >= now() - (%s || ' hours')::interval
                  AND timestamp_scan <= now() - '70 minutes'::interval
                ORDER BY timestamp_scan DESC
                LIMIT %s
                """,
                (EN_ATTENTE, remonte_heures, limite),
            )
            dossiers = cur.fetchall()

    if not dossiers:
        return (0, 0)

    evaluates = 0
    sans_donnees = 0
    for ident, symbole, sens, entree, sl_pct, tp_pct in dossiers:
        try:
            bougies = await fetch_ohlcv(symbole, "1m", minutes_max + 20)
        except Exception as exc:
            logger.debug(f"Carnet fantôme: bougies indisponibles pour {symbole}: {exc}")
            bougies = None

        if not bougies or len(bougies) < 5:
            sans_donnees += 1
            resultat = {"statut": DONNEES_MANQUANTES}
        else:
            resultat = verdict(bougies, entree, sens, sl_pct, tp_pct, minutes_max)

        with connexion_journal() as cnx:
            if cnx is None:
                break
            with cnx.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ghost_setups
                    SET statut = %s, evalue_le = now(),
                        gain_max_pct = %s, perte_max_pct = %s,
                        minutes_avant_verdict = %s
                    WHERE id = %s
                    """,
                    (
                        resultat["statut"],
                        resultat.get("gain_max_pct"),
                        resultat.get("perte_max_pct"),
                        resultat.get("minutes_avant_verdict"),
                        ident,
                    ),
                )
            cnx.commit()

        if resultat["statut"] != DONNEES_MANQUANTES:
            evaluates += 1
        await asyncio.sleep(0.25)  # ménager la source de prix

    logger.info(
        f"👻 Carnet fantôme: {evaluates} dossiers évalués, {sans_donnees} sans données"
    )
    return (evaluates, sans_donnees)

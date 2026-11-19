"""Le pilote IA : ce qu'il a le droit de toucher, et comment on revient en arrière.

Ce module n'est PAS un cerveau. C'est la cage et les mains :

  - la **cage** : une liste courte de réglages que l'IA peut proposer, chacun avec
    ses bornes hautes et basses. Un réglage qui n'est pas dans la liste est
    refusé sans discuter, même bien justifié. La taille des prises, les plafonds
    de dégâts, les frais et le passage en réel n'en font PAS partie — ce sont eux
    qui décident de la perte maximale possible.
  - les **mains** : une seule porte pour changer un réglage (le fichier qui
    commande vraiment), qui note la valeur d'avant dans la base avant d'agir.
  - la **mémoire** : trois tables (`ia_bilans`, `ia_decisions`, `ia_avis`) pour
    pouvoir juger six mois plus tard ce qui avait été annoncé et ce que ça a donné.
  - le **thermomètre** : après chaque changement appliqué, on compare le gain
    moyen des prises avant et après. Si c'est plus mauvais, le réglage revient
    tout seul à sa valeur d'avant.

Niveaux (réglage `pilote_ia_niveau`) :
    0 = rien ne tourne
    1 = bilan écrit toutes les heures, aucune proposition
    2 = bilan + propositions écrites, un humain approuve (réglage par défaut)
    3 = bilan + propositions + application seule, avec annulation automatique
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── la cage : les seuls réglages que l'IA peut proposer ──────────────────────

REGISTRE_CAGE: Dict[str, Dict[str, Any]] = {
    "trailing_min_distance": {
        "nom": "distance minimum du stop suiveur",
        "unite": "%",
        "min": 0.05,
        "max": 0.40,
    },
    "trailing_max_distance": {
        "nom": "distance maximum du stop suiveur",
        "unite": "%",
        "min": 0.05,
        "max": 0.60,
    },
    "trailing_pnl_cap": {
        "nom": "gain atteint avant serrage maximal du stop",
        "unite": "%",
        "min": 0.20,
        "max": 3.00,
    },
    "trailing_trigger_atr_mult": {
        "nom": "moment d'enclenchement du stop suiveur",
        "unite": "×ATR",
        "min": 0.20,
        "max": 2.00,
    },
    "gb_min_confidence": {
        "nom": "confiance minimum exigée du filtre de prise",
        "unite": "%",
        "min": 0.30,
        "max": 0.70,
        "fraction": True,  # stocké en fraction (0.40 = 40 %)
    },
    "volume_multiplier": {
        "nom": "exigence de volume à l'entrée",
        "unite": "×",
        "min": 0.50,
        "max": 1.50,
    },
}

CAGE_CLEES = tuple(REGISTRE_CAGE)

CONSIGNE_PROPOSITIONS = (
    "Tu observes un robot de trading en essai à blanc. On te donne ses chiffres de la "
    "dernière heure et la liste des seuls réglages que tu as le droit de proposer, avec "
    "leurs bornes. Réponds UNIQUEMENT par un tableau JSON, sans phrase avant ni après. "
    "Chaque élément : {\"cle\": \"<une cle de la liste>\", \"valeur\": <nombre dans les bornes>, "
    "\"motif\": \"<une phrase courte avec les chiffres que tu as vus>\"}. "
    "Une seule proposition maximum. Si les chiffres ne justifient aucun changement, "
    "réponds [] : c'est la réponse attendue la plupart du temps."
)


def _config() -> Dict[str, Any]:
    from config import TRADING_CONFIG

    return TRADING_CONFIG


def actif() -> bool:
    return bool(_config().get("pilote_ia_actif", True))


def niveau() -> int:
    try:
        return int(_config().get("pilote_ia_niveau", 2))
    except (TypeError, ValueError):
        return 2


def changer_niveau(valeur: int) -> bool:
    if valeur not in (0, 1, 2, 3):
        return False
    _config()["pilote_ia_niveau"] = int(valeur)
    _ecrire_override({"pilote_ia_niveau": int(valeur)})
    logger.info(f"🧠 Pilotage IA — niveau porté à {valeur}")
    return True


# ── base : lire et écrire les traces ─────────────────────────────────────────


def _connexion():
    from core.postgresql_datalogger import connexion_journal

    return connexion_journal()


def _present() -> bool:
    import core.postgresql_datalogger as scribe

    scribe_en_place = getattr(scribe, "_pg_datalogger_instance", None)
    return bool(scribe_en_place and getattr(scribe_en_place, "enabled", False))


def _regler(cle: str) -> Optional[float]:
    from utils.effective_config import get_effective_value

    valeur = get_effective_value(cle)
    try:
        return None if valeur is None else float(valeur)
    except (TypeError, ValueError):
        return None


def cage() -> List[Dict[str, Any]]:
    return [
        {
            "cle": cle,
            "nom": regle["nom"],
            "unite": regle["unite"],
            "min": regle["min"],
            "max": regle["max"],
            "fraction": regle.get("fraction", False),
            "valeur": _regler(cle),
        }
        for cle, regle in REGISTRE_CAGE.items()
    ]


def chiffres(fenetre_minutes: int = 60) -> Dict[str, Any]:
    """Les nombres de la dernière heure, sortis de la base.

    L'IA ne voit QUE ça : jamais de chiffres inventés, jamais de marché qu'elle
    imaginerait. Ce sont les mêmes mesures que les scripts de contrôle.
    """
    bloc: Dict[str, Any] = {"fenetre_minutes": fenetre_minutes}
    if not _present():
        bloc["base_indisponible"] = True
        return bloc
    try:
        with _connexion() as c:
            cur = c.cursor()
            cur.execute(
                """
                SELECT count(*),
                       count(*) FILTER (WHERE pnl_usdt > 0),
                       coalesce(sum(pnl_usdt), 0),
                       coalesce(sum(pnl_pct), 0),
                       coalesce(avg(pnl_pct), 0)
                  FROM trades
                 WHERE timestamp_exit >= NOW() - (%s || ' minutes')::interval
                """,
                (str(fenetre_minutes),),
            )
            n, g, dollars, points, moyenne = cur.fetchone()
            bloc.update(
                {
                    "trades": int(n or 0),
                    "gagnes": int(g or 0),
                    "dollars": round(float(dollars or 0), 2),
                    "points": round(float(points or 0), 2),
                    "gain_moyen_par_prise": round(float(moyenne or 0), 3),
                }
            )

            cur.execute(
                """
                SELECT coalesce(statut, 'en attente'), count(*)
                  FROM ghost_setups
                 WHERE timestamp_scan >= NOW() - (%s || ' minutes')::interval
                 GROUP BY 1 ORDER BY 2 DESC
                """,
                (str(fenetre_minutes),),
            )
            bloc["occasions_ratees"] = {cle: int(nbr) for cle, nbr in cur.fetchall()}

            cur.execute(
                """
                SELECT direction, confidence_bucket, total_trades, actual_winrate, avg_pnl_pct
                  FROM ml_calibration
                 ORDER BY total_trades DESC LIMIT 4
                """
            )
            bloc["tranches"] = [
                {
                    "sens": r[0],
                    "tranche": r[1],
                    "trades": int(r[2] or 0),
                    "gagne_pct": round(float(r[3] or 0), 1),
                    "pnl_moyen": round(float(r[4] or 0), 3),
                }
                for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT trades_pris, pertes_consecutives, pnl_jour_pct, etat
                  FROM circuit_breaker_etat
                 ORDER BY jour DESC LIMIT 1
                """
            )
            ligne = cur.fetchone()
            if ligne:
                bloc["garde_fou"] = {
                    "prises_du_jour": int(ligne[0] or 0),
                    "pertes_de_suite": int(ligne[1] or 0),
                    "pnl_jour_pct": round(float(ligne[2] or 0), 2),
                    "etat": ligne[3],
                }
            cur.close()
    except Exception as exc:  # une mesure qui rate ne doit pas arrêter le pilote
        logger.warning(f"⚠️ Pilotage IA — chiffres incomplets: {exc}")
        bloc["mesure_partielle"] = str(exc)
    return bloc


def drapeaux(bloc: Dict[str, Any]) -> List[str]:
    """Les alertes sont calculées par le programme, pas racontées par le modèle."""
    signes: List[str] = []
    if bloc.get("trades", 0) == 0:
        signes.append("aucune prise sur la période")
    pertes = (bloc.get("garde_fou") or {}).get("pertes_de_suite", 0)
    if pertes >= 3:
        signes.append(f"{pertes} pertes l'une après l'autre")
    if bloc.get("gain_moyen_par_prise", 0) < 0:
        signes.append("les prises de la période perdent de l'argent")
    ratees = bloc.get("occasions_ratees") or {}
    if int(ratees.get("GAGNE", 0) or 0) >= 3:
        signes.append("des occasions écartées auraient rapporté")
    for t in bloc.get("tranches", []):
        if t["trades"] >= 30 and t["pnl_moyen"] < -0.05:
            signes.append(f"la tranche {t['sens']} {t['tranche']} fait perdre de l'argent")
    return signes


def ecrire_prediction_filtre(
    symbole: str,
    approuve: bool,
    confiance: float,
    seuil: float,
    signes: Any = None,
    version_modele: str = "histgb",
) -> None:
    """Le verdict du filtre de confiance est écrit en base, pas seulement au journal.

    Mesuré le 19/11/2026 : `model_predictions` contenait 0 ligne alors que le
    filtre rejetait des prises depuis des jours. Sans trace, impossible de dire
    s'il aide ou s'il fait perdre des occasions.
    """
    if not _present():
        return
    try:
        resume = json.dumps(signes, ensure_ascii=False, default=str)[:3000] if signes else None
        with _connexion() as c:
            cur = c.cursor()
            cur.execute(
                """
                INSERT INTO model_predictions
                    (timestamp, model_version, symbol, predicted_win, win_probability,
                     confidence_score, seuil_utilise, features_used)
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    version_modele,
                    symbole,
                    bool(approuve),
                    float(confiance),
                    float(confiance),
                    float(seuil),
                    resume,
                ),
            )
            c.commit()
            cur.close()
    except Exception as exc:
        logger.warning(f"⚠️ Pilotage IA — verdict du filtre non écrit: {exc}")


def ecrire_avis(usage: str, question: str, reponse: str, modele: Optional[str], duree_ms: int) -> None:
    if not _present():
        return
    try:
        with _connexion() as c:
            cur = c.cursor()
            cur.execute(
                "INSERT INTO ia_avis (usage, question, reponse, modele, duree_ms) VALUES (%s, %s, %s, %s, %s)",
                (usage, (question or "")[:4000], (reponse or "")[:8000], modele, duree_ms),
            )
            c.commit()
            cur.close()
    except Exception as exc:
        logger.warning(f"⚠️ Pilotage IA — avis non archivé: {exc}")


def ecrire_bilan(texte: str, signes: List[str], bloc: Dict[str, Any], modele: Optional[str]) -> None:
    if not _present():
        return
    try:
        with _connexion() as c:
            cur = c.cursor()
            cur.execute(
                "INSERT INTO ia_bilans (texte, drapeaux, chiffres, modele) VALUES (%s, %s, %s, %s)",
                (texte, json.dumps(signes, ensure_ascii=False), json.dumps(bloc, ensure_ascii=False), modele),
            )
            c.commit()
            cur.close()
    except Exception as exc:
        logger.warning(f"⚠️ Pilotage IA — bilan non écrit: {exc}")


def _iso(valeur: Any) -> Optional[str]:
    """Une date peut arriver en objet datetime ou en texte : on rend du texte."""
    if valeur is None:
        return None
    return valeur.isoformat() if hasattr(valeur, "isoformat") else str(valeur)


def decisions(en_attente: bool = False, limite: int = 12) -> List[Dict[str, Any]]:
    if not _present():
        return []
    demande = """
        SELECT id, type, cle, valeur_avant, valeur_apres, motif, etat,
               applique_le, cree_le, mesures
          FROM ia_decisions
    """
    if en_attente:
        demande += " WHERE etat = 'propose'"
    demande += " ORDER BY cree_le DESC LIMIT %s"
    try:
        with _connexion() as c:
            cur = c.cursor()
            cur.execute(demande, (limite,))
            lignes = cur.fetchall()
            cur.close()
    except Exception as exc:
        logger.warning(f"⚠️ Pilotage IA — décisions illisibles: {exc}")
        return []
    out = []
    for d in lignes:
        mesures = d[9] if isinstance(d[9], dict) else {}
        out.append(
            {
                "id": d[0],
                "type": d[1],
                "cle": d[2],
                "nom": (REGISTRE_CAGE.get(d[2]) or {}).get("nom", d[2]),
                "unite": (REGISTRE_CAGE.get(d[2]) or {}).get("unite", ""),
                "avant": d[3],
                "apres": d[4],
                "motif": d[5],
                "etat": d[6],
                "applique_le": _iso(d[7]),
                "cree_le": _iso(d[8]),
                "mesure_avant": mesures.get("avant"),
                "mesure_apres": mesures.get("apres"),
                "verdict": mesures.get("verdict"),
            }
        )
    return out


def dernier_bilan() -> Optional[Dict[str, Any]]:
    if not _present():
        return None
    try:
        with _connexion() as c:
            cur = c.cursor()
            cur.execute("SELECT id, quand, texte, drapeaux, chiffres FROM ia_bilans ORDER BY quand DESC LIMIT 1")
            ligne = cur.fetchone()
            cur.close()
        if not ligne:
            return None
        return {
            "id": ligne[0],
            "heure": _iso(ligne[1]),
            "texte": ligne[2],
            "drapeaux": ligne[3] if isinstance(ligne[3], list) else [],
            "chiffres": ligne[4] if isinstance(ligne[4], dict) else {},
        }
    except Exception as exc:
        logger.warning(f"⚠️ Pilotage IA — bilan illisible: {exc}")
        return None


def bilans(limite: int = 12) -> List[Dict[str, Any]]:
    if not _present():
        return []
    try:
        with _connexion() as c:
            cur = c.cursor()
            cur.execute(
                "SELECT id, quand, texte, drapeaux FROM ia_bilans ORDER BY quand DESC LIMIT %s", (limite,)
            )
            lignes = cur.fetchall()
            cur.close()
        return [
            {
                "id": b[0],
                "heure": _iso(b[1]),
                "texte": b[2],
                "drapeaux": b[3] if isinstance(b[3], list) else [],
            }
            for b in lignes
        ]
    except Exception:
        return []


# ── la porte unique qui change un réglage ───────────────────────────────────


def _ecrire_override(changements: Dict[str, Any]) -> None:
    from utils.config_persistence import load_config_overrides, save_config_overrides

    reglages = load_config_overrides()
    reglages.update(changements)
    save_config_overrides(reglages)


def appliquer(cle: str, valeur: float) -> Tuple[bool, str]:
    """Écrit dans le fichier de réglages qui commande, en notant la valeur d'avant.

    Refuse tout ce qui n'est pas dans la cage ou hors bornes — sans exception,
    même si la proposition est bien justifiée par ailleurs.
    """
    regle = REGISTRE_CAGE.get(cle)
    if not regle:
        return False, f"réglage {cle} hors de la cage"
    try:
        valeur = float(valeur)
    except (TypeError, ValueError):
        return False, "valeur illisible"
    if not (regle["min"] <= valeur <= regle["max"]):
        return False, (
            f"{cle}: {valeur} hors bornes ({regle['min']} à {regle['max']})"
        )
    avant = _regler(cle)
    _config()[cle] = valeur
    _ecrire_override({cle: valeur})
    logger.info(
        f"🧠 Pilotage IA — {cle}: {avant} → {valeur} (bornes {regle['min']}–{regle['max']})"
    )
    return True, ""


def annuler(cle: str, valeur_avant: float) -> Tuple[bool, str]:
    ok, motif = appliquer(cle, valeur_avant)
    return ok, motif


# ── décisions : proposer, approuver, rejeter, mesurer ───────────────────────


def _demande_en_cours() -> Optional[Dict[str, Any]]:
    for d in decisions(en_attente=True, limite=1):
        return d
    return None


def _une_application_en_attente_de_mesure() -> bool:
    return any(d["etat"] == "applique" for d in decisions(limite=20))


def propositions(bloc: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """L'IA propose, le programme vérifie. Une seule proposition à la fois."""
    if niveau() < 2 or not actif():
        return []
    if _une_application_en_attente_de_mesure():
        logger.info("🧠 Pilotage IA — une modification attend sa mesure : pas de nouvelle proposition")
        return []

    bloc = bloc or chiffres()
    reglages_vivants = "; ".join(
        f"{r['cle']} = {r['valeur']} (bornes {r['min']} à {r['max']} {r['unite']})" for r in cage()
    )
    contexte = (
        f"CHIFFRES DE LA DERNIÈRE HEURE\n{json.dumps(bloc, ensure_ascii=False, indent=1)[:5000]}\n\n"
        f"SEULS RÉGLAGES AUTORISÉS\n{reglages_vivants}"
    )

    from ml.conseiller_ia import demander_avis

    depart = time.time()
    reponse = demander_avis(CONSIGNE_PROPOSITIONS, contexte=contexte, timeout=90.0)
    if not reponse.get("ok"):
        logger.info(f"🧠 Pilotage IA — pas de proposition ({reponse.get('motif')})")
        return []

    ecrire_avis("proposition", CONSIGNE_PROPOSITIONS[:200], reponse["texte"], reponse.get("modele"),
                int((time.time() - depart) * 1000))

    retenues = []
    for proposition in _lire_json(reponse["texte"]):
        cle = str(proposition.get("cle", "")).strip()
        valeur = proposition.get("valeur")
        motif = str(proposition.get("motif", ""))[:900]
        regle = REGISTRE_CAGE.get(cle)
        if not regle:
            logger.info(f"🧠 Pilotage IA — proposition refusée (hors cage): {cle}")
            continue
        try:
            valeur = float(valeur)
        except (TypeError, ValueError):
            continue
        if not (regle["min"] <= valeur <= regle["max"]):
            logger.info(f"🧠 Pilotage IA — proposition refusée (hors bornes): {cle}={valeur}")
            continue
        actuelle = _regler(cle)
        if actuelle is None or abs(actuelle - valeur) < 1e-9:
            continue
        if _enregistrer_proposition(cle, actuelle, valeur, motif):
            retenues.append({"cle": cle, "avant": actuelle, "apres": valeur, "motif": motif})
        break  # une seule proposition par tour, décidément

    if niveau() >= 3 and retenues:
        approuver(retenues[0]["id"] if "id" in retenues[0] else _derniere_id(), source="pilote")
    return retenues


def _derniere_id() -> Optional[int]:
    attente = _demande_en_cours()
    return attente["id"] if attente else None


def _enregistrer_proposition(cle: str, avant: float, apres: float, motif: str) -> bool:
    if not _present():
        return False
    try:
        with _connexion() as c:
            cur = c.cursor()
            cur.execute(
                "INSERT INTO ia_decisions (type, cle, valeur_avant, valeur_apres, motif, etat) "
                "VALUES ('reglage', %s, %s, %s, %s, 'propose')",
                (cle, avant, apres, motif),
            )
            c.commit()
            cur.close()
        return True
    except Exception as exc:
        logger.warning(f"⚠️ Pilotage IA — proposition non écrite: {exc}")
        return False


def _lire_json(texte: str) -> List[Dict[str, Any]]:
    """Le modèle écrit parfois du texte autour du JSON : on prend le premier tableau."""
    recherche = re.search(r"\[.*\]", texte, re.S)
    if not recherche:
        return []
    try:
        donnees = json.loads(recherche.group(0))
    except ValueError:
        return []
    return [d for d in donnees if isinstance(d, dict)][:3]


def approuver(decision_id: int, source: str = "humain") -> Tuple[bool, str]:
    decision = _lire_decision(decision_id)
    if not decision:
        return False, "décision inconnue"
    if decision["etat"] != "propose":
        return False, f"déjà {decision['etat']}"
    ok, motif = appliquer(decision["cle"], decision["valeur_apres"] if "valeur_apres" in decision else decision["apres"])
    if not ok:
        return False, motif
    _maj_decision(decision_id, "applique", applique=True)
    logger.info(f"🧠 Pilotage IA — décision {decision_id} appliquée (par {source})")
    return True, ""


def rejeter(decision_id: int) -> Tuple[bool, str]:
    decision = _lire_decision(decision_id)
    if not decision or decision["etat"] != "propose":
        return False, "rien à rejeter"
    _maj_decision(decision_id, "rejete")
    return True, ""


def annuler_decision(decision_id: int, motif: str = "annulation manuelle") -> Tuple[bool, str]:
    decision = _lire_decision(decision_id)
    if not decision or decision["etat"] != "applique":
        return False, "rien à annuler"
    ok, erreur = appliquer(decision["cle"], decision["valeur_avant"])
    if not ok:
        return False, erreur
    mesures = dict(decision.get("mesures") or {})
    mesures["verdict"] = motif
    _maj_decision(decision_id, "annule", annule=True, mesures=mesures)
    logger.info(f"🧠 Pilotage IA — réglage {decision['cle']} remis à {decision['valeur_avant']} ({motif})")
    return True, ""


def _lire_decision(decision_id: int) -> Optional[Dict[str, Any]]:
    if not _present():
        return None
    try:
        with _connexion() as c:
            cur = c.cursor()
            cur.execute(
                "SELECT cle, valeur_avant, valeur_apres, etat, mesures FROM ia_decisions WHERE id = %s",
                (decision_id,),
            )
            ligne = cur.fetchone()
            cur.close()
        if not ligne:
            return None
        return {
            "cle": ligne[0],
            "valeur_avant": ligne[1],
            "valeur_apres": ligne[2],
            "etat": ligne[3],
            "mesures": ligne[4] if isinstance(ligne[4], dict) else {},
            "apres": ligne[2],
        }
    except Exception:
        return None


def _maj_decision(
    decision_id: int,
    etat: str,
    applique: bool = False,
    annule: bool = False,
    mesures: Optional[Dict[str, Any]] = None,
) -> None:
    if not _present():
        return
    demande = "UPDATE ia_decisions SET etat = %s"
    valeurs: List[Any] = [etat]
    if applique:
        demande += ", applique_le = NOW()"
    if annule:
        demande += ", annule_le = NOW()"
    if mesures is not None:
        demande += ", mesures = %s"
        valeurs.append(json.dumps(mesures, ensure_ascii=False))
    demande += " WHERE id = %s"
    valeurs.append(decision_id)
    try:
        with _connexion() as c:
            cur = c.cursor()
            cur.execute(demande, tuple(valeurs))
            c.commit()
            cur.close()
    except Exception as exc:
        logger.warning(f"⚠️ Pilotage IA — décision non mise à jour: {exc}")


def mesurer_modifications() -> List[Dict[str, Any]]:
    """Compare le gain moyen des prises avant et après chaque réglage appliqué.

    Si c'est plus mauvais au-delà de la marge réglée, le réglage revient tout seul.
    C'est la seule façon honnête de savoir si l'IA a amélioré quelque chose.
    """
    fenetre = int(_config().get("pilote_ia_fenetre_prises", 20) or 20)
    marge = float(_config().get("pilote_ia_gain_minimum", 0.05) or 0.05)
    resultats = []
    for decision in decisions(limite=20):
        if decision["etat"] != "applique" or not decision["applique_le"]:
            continue
        moyenne_apres = _gain_moyen_apres(decision["applique_le"], fenetre)
        moyenne_avant = _gain_moyen_avant(decision["applique_le"], fenetre)
        if moyenne_apres is None or moyenne_avant is None:
            resultats.append({"id": decision["id"], "attend": True})
            continue
        mesures = {
            "avant": round(moyenne_avant, 4),
            "apres": round(moyenne_apres, 4),
            "verdict": "mieux" if moyenne_apres > moyenne_avant else "pire",
        }
        _maj_decision(decision["id"], "applique", mesures=mesures)
        resultats.append({"id": decision["id"], **mesures})
        if moyenne_apres < moyenne_avant - marge:
            annuler_decision(
                decision["id"],
                motif=f"mesure: {moyenne_apres:.3f} < {moyenne_avant:.3f} — retour automatique",
            )
    return resultats


def _gain_moyen_apres(depuis_iso: str, fenetre: int) -> Optional[float]:
    return _gain_moyen(">= ", depuis_iso, fenetre)


def _gain_moyen_avant(jusqu_iso: str, fenetre: int) -> Optional[float]:
    return _gain_moyen("< ", jusqu_iso, fenetre)


def _gain_moyen(sens: str, repere_iso: str, fenetre: int) -> Optional[float]:
    if not _present():
        return None
    demande = f"""
        SELECT avg(pnl_pct) FROM (
            SELECT pnl_pct FROM trades
             WHERE timestamp_exit IS NOT NULL AND timestamp_exit {sens} %s::timestamptz
             ORDER BY timestamp_exit DESC LIMIT %s
        ) x
    """
    try:
        with _connexion() as c:
            cur = c.cursor()
            cur.execute(demande, (repere_iso, fenetre))
            valeur = cur.fetchone()[0]
            cur.close()
        return None if valeur is None else float(valeur)
    except Exception:
        return None


def bilan(force: bool = False) -> Optional[Dict[str, Any]]:
    """Une phrase de synthèse par heure, avec les alertes calculées par le programme."""
    if not actif() or (niveau() < 1 and not force):
        return None
    bloc = chiffres(int(_config().get("pilote_ia_fenetre_minutes", 60) or 60))
    signes = drapeaux(bloc)

    from ml.conseiller_ia import demander_avis

    depart = time.time()
    reponse = demander_avis(
        "En trois phrases maximum, dis ce que ces chiffres montrent pour la dernière heure : "
        "ce qui marche, ce qui coince, et ce qui mérite d'être regardé. Ne propose aucun réglage.",
        contexte=json.dumps(bloc, ensure_ascii=False)[:5000],
        timeout=90.0,
    )
    texte = reponse.get("texte") or "Le modèle n'a pas répondu ; les alertes ci-dessous restent valables."
    ecrire_bilan(texte, signes, bloc, reponse.get("modele"))
    if reponse.get("ok"):
        ecrire_avis("bilan", "bilan horaire", texte, reponse.get("modele"), int((time.time() - depart) * 1000))
    logger.info(f"🧠 Pilotage IA — bilan écrit ({len(signes)} alerte(s) calculée(s))")
    return {"texte": texte, "drapeaux": signes, "chiffres": bloc}


def boucle() -> Dict[str, Any]:
    """Ce que l'ordonnanceur réveille toutes les heures."""
    if not actif():
        return {"actif": False}
    bilan()
    sortie: Dict[str, Any] = {"actif": True, "niveau": niveau()}
    if niveau() >= 2:
        sortie["propositions"] = len(propositions())
    sortie["mesures"] = mesurer_modifications()
    return sortie


def etat_pilotage() -> Dict[str, Any]:
    from ml.conseiller_ia import etat as etat_ia

    courant = etat_ia()
    decisions_recentes = decisions(limite=10)
    en_attente = [d for d in decisions_recentes if d["etat"] == "propose"]
    appliquées = [d for d in decisions_recentes if d["etat"] == "applique"]
    return {
        "actif": actif(),
        "niveau": niveau(),
        "modele": courant.get("modele"),
        "message": (
            f"{len(bilans(50))} bilans écrits · {len([d for d in decisions(limite=50) if d['etat'] == 'applique'])} "
            f"décision(s) appliquée(s) · {courant.get('message', '')}"
        ),
        "attention": (
            "une modification appliquée attend sa mesure" if appliquées else None
        ),
        "cage": cage(),
        "bilan": dernier_bilan(),
        "bilans": bilans(),
        "propositions": en_attente,
        "decisions": decisions_recentes,
    }

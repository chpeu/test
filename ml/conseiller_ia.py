"""
Conseiller IA locale — avis texte sur le robot, jamais d'ordre.

Principe de sécurite, decide le 18/11/2026 : on n'utilise QUE le modele deja
charge dans llama-swap. llama-swap change de modele a la demande, et decharger
le modele principal couterait ~1 min 30 de rechargement a toute la machine.
On ne demande donc jamais un modele par son nom "absent", et on n'appelle
aucun endpoint d'administration : seulement /v1/models (lecture) et
/v1/chat/completions (reponse).

Ce module ne connait ni les ordres, ni la bourse, ni la base de donnees :
on lui passe du texte, il rend du texte. Les routes dans api/routes/ia.py
decident quoi lui montrer.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

URL_DEFAUT = "http://127.0.0.1:1234/v1"
# Un avis sur dix trades ne doit pas transformer l'appli en conversation infinie.
LIMITE_CONTEXTE = 6000
LIMITE_REPONSE = 1200
TEMPS_ATTENTE_MODELE = 4  # /v1/models doit repondre instantanement


def url_de_base() -> str:
    return os.getenv("IA_LOCALE_URL", URL_DEFAUT).rstrip("/")


def _get(chemin: str, timeout: float) -> Optional[Dict[str, Any]]:
    requete = urllib.request.Request(url_de_base() + chemin, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            return json.loads(reponse.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.debug("conseiller_ia: /v1%s injoignable (%s)", chemin, exc)
        return None


def modele_charge() -> Optional[str]:
    """Nom du modele deja en memoire, ou None si rien n'est pret a repondre.

    llama-swap annote chaque modele : status.value = 'loaded' ou 'unloaded'.
    Un modele 'unloaded' declencherait un dechargement du modele principal :
    on le refuse explicitement.
    """
    inventaire = _get("/models", TEMPS_ATTENTE_MODELE)
    if not inventaire:
        return None
    for modeles in inventaire.get("data", []):
        if (modeles.get("status") or {}).get("value") == "loaded":
            return modeles.get("id")
    return None


def etat() -> Dict[str, Any]:
    """Ce que l'interface doit afficher : branchee ou non, et pourquoi."""
    inventaire = _get("/models", TEMPS_ATTENTE_MODELE)
    if inventaire is None:
        return {
            "service_joignable": False,
            "modele": None,
            "modeles_charges": [],
            "url": url_de_base(),
            "message": "llama-swap ne repond pas sur cette adresse.",
        }
    charges: List[str] = [
        m.get("id")
        for m in inventaire.get("data", [])
        if (m.get("status") or {}).get("value") == "loaded"
    ]
    return {
        "service_joignable": True,
        "modele": charges[0] if charges else None,
        "modeles_charges": charges,
        "url": url_de_base(),
        "message": (
            f"{len(inventaire.get('data', []))} modeles configures, {len(charges)} charge(s)."
            if charges
            else "Aucun modele charge : je n'envoie rien, pour ne pas decharger le modele principal."
        ),
    }


CONSEGNE = (
    "Tu es un observateur d'un robot de marche automatique en mode essai a blanc. "
    "Tu ne passes aucun ordre et tu ne conseille pas d'achat ni de vente : tu decris ce que "
    "le journal du robot montre, en francais, en phrases courtes, avec des chiffres quand il y "
    "en a. Si les donnees ne suffisent pas, dis-le au lieu d'inventer."
)


def demander_avis(question: str, contexte: str = "", timeout: float = 45.0) -> Dict[str, Any]:
    """Avis texte du modele deja charge. Jamais d'appel a un modele non charge.

    Retourne toujours un dict : ok, texte, modele, motif (en cas de refus).
    """
    nom = modele_charge()
    if not nom:
        return {
            "ok": False,
            "texte": "",
            "modele": None,
            "motif": "Aucun modele n'est charge : envoyer une question ferait decharger le modele principal.",
        }

    corps = {
        "model": nom,
        "messages": [
            {"role": "system", "content": CONSEGNE},
            {"role": "user", "content": (contexte[:LIMITE_CONTEXTE] + "\n\n" + question)[: LIMITE_CONTEXTE + 500]},
        ],
        "max_tokens": LIMITE_REPONSE,
        "temperature": 0.3,
        "stream": False,
    }
    requete = urllib.request.Request(
        url_de_base() + "/chat/completions",
        data=json.dumps(corps).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("conseiller_ia: echec de la demande (%s)", exc)
        return {"ok": False, "texte": "", "modele": nom, "motif": f"Le modele n'a pas repondu : {exc}"}

    choix = donnees.get("choices") or []
    texte = ((choix[0].get("message") or {}).get("content") or "").strip() if choix else ""
    if not texte:
        return {"ok": False, "texte": "", "modele": nom, "motif": "Le modele a repondu vide."}
    return {"ok": True, "texte": texte, "modele": nom, "motif": None}


def resumer_trades(trades: List[Dict[str, Any]], limite: int = 30) -> str:
    """Petit texte compact a montrer au modele (utilise par la route /bilan)."""
    if not trades:
        return "Aucun trade dans le journal sur la periode demandee."
    lignes = []
    for t in trades[-limite:]:
        lignes.append(
            f"{t.get('symbol', '?')} {t.get('side', t.get('direction', '?'))} "
            f"pnl={t.get('pnl', t.get('pnl_pct', '?'))} raison={t.get('exit_reason', t.get('exit_type', '?'))}"
        )
    return "\n".join(lignes)

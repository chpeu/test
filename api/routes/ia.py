"""
Routes IA locale — etat du conseiller, avis, bilan du journal.

Mode « fantome » assume : ces routes produisent du texte. Elles ne touchent
jamais au gestionnaire d'ordres, au scanner, ni aux regles d'entree/sortie.
Le robot continue de decider seul ; l'IA regarde par-dessus son epaule.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from ml import conseiller_ia

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ia", tags=["IA locale"])


def _trades_de_la_session(limite: int) -> List[Dict[str, Any]]:
    """Trades fermes de la session en cours, via le gestionnaire d'etat."""
    try:
        from core.state_manager import get_state_manager

        state = get_state_manager()
        db = state.get_analytics_db()
        if not db:
            return []
        trades = db.get_trades(limit=max(1, min(limite, 500)))
        sess_id = state.session_id
        if sess_id:
            trades = [t for t in trades if t.get("session_id") == sess_id]
        return trades
    except Exception as exc:  # journal indisponible : l'avis restera vide
        logger.debug("routes ia: trades indisponibles (%s)", exc)
        return []


@router.get("/etat")
async def etat() -> JSONResponse:
    """L'interface affiche ca : branchee ou non, et pourquoi."""
    return JSONResponse(conseiller_ia.etat())


@router.post("/avis")
async def avis(corps: Dict[str, Any] = Body(default={})) -> JSONResponse:
    question = str((corps or {}).get("question") or "").strip()
    if not question:
        return JSONResponse({"ok": False, "texte": "", "motif": "Question vide."}, status_code=400)
    contexte = str((corps or {}).get("contexte") or "")
    import time as _temps

    depart = _temps.time()
    reponse = conseiller_ia.demander_avis(question, contexte)
    if reponse.get("ok"):
        # Ce que l'IA a répondu est archivé : sinon on ne peut pas juger après coup
        # si elle voyait juste (mesuré 19/11/2026 : aucune trace de ses avis).
        try:
            from core.pilotage_ia import ecrire_avis

            ecrire_avis(
                "conseil",
                question,
                reponse["texte"],
                reponse.get("modele"),
                int((_temps.time() - depart) * 1000),
            )
        except Exception as exc:  # l'archivage ne doit jamais casser la réponse
            logger.debug("routes ia: avis non archivé (%s)", exc)
    return JSONResponse(reponse)


@router.post("/bilan")
async def bilan(corps: Dict[str, Any] = Body(default={})) -> JSONResponse:
    """Resume du journal + avis du modele deja charge. Aucun ordre en sortie."""
    limite = int((corps or {}).get("limite") or 30)
    trades = _trades_de_la_session(limite)
    question = (
        "Voici le journal des trades fermes. En trois phrases : ce qui marche, "
        "ce qui merite attention, et une question que je devrais me poser."
    )
    reponse = conseiller_ia.demander_avis(question, conseiller_ia.resumer_trades(trades))
    reponse["nb_trades"] = len(trades)
    return JSONResponse(reponse)


# ── pilotage : bilan horaire, propositions, application, retour en arrière ───
#
# Ce que ces routes peuvent toucher : UNIQUEMENT les réglages de la cage
# (core/pilotage_ia.REGISTRE_CAGE), avec leurs bornes vérifiées côté serveur.
# Ni la taille des prises, ni les plafonds de dégâts, ni les frais, ni le
# passage en réel — ceux-là restent hors de portée de l'IA comme des routes.


@router.get("/pilotage")
async def pilotage() -> JSONResponse:
    from core.pilotage_ia import etat_pilotage

    return JSONResponse(etat_pilotage())


@router.post("/pilotage/niveau")
async def pilotage_niveau(corps: Dict[str, Any] = Body(default={})) -> JSONResponse:
    from core.pilotage_ia import changer_niveau, etat_pilotage

    try:
        niveau = int((corps or {}).get("niveau"))
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "motif": "niveau attendu: 0, 1, 2 ou 3"}, status_code=400)
    if not changer_niveau(niveau):
        return JSONResponse({"ok": False, "motif": "niveau hors service (0 à 3)"}, status_code=400)
    return JSONResponse({**etat_pilotage(), "ok": True})


@router.post("/pilotage/bilan")
async def pilotage_bilan(corps: Dict[str, Any] = Body(default={})) -> JSONResponse:
    from core.pilotage_ia import bilan, etat_pilotage

    resultat = bilan(force=True)
    return JSONResponse({**etat_pilotage(), "ok": resultat is not None, "bilan": resultat})


@router.post("/pilotage/approuver")
async def pilotage_approuver(corps: Dict[str, Any] = Body(default={})) -> JSONResponse:
    from core.pilotage_ia import approuver, etat_pilotage

    try:
        identifiant = int((corps or {}).get("id"))
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "motif": "id manquant"}, status_code=400)
    ok, motif = approuver(identifiant, source="humain")
    return JSONResponse({**etat_pilotage(), "ok": ok, "motif": motif})


@router.post("/pilotage/rejeter")
async def pilotage_rejeter(corps: Dict[str, Any] = Body(default={})) -> JSONResponse:
    from core.pilotage_ia import rejeter, etat_pilotage

    try:
        identifiant = int((corps or {}).get("id"))
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "motif": "id manquant"}, status_code=400)
    ok, motif = rejeter(identifiant)
    return JSONResponse({**etat_pilotage(), "ok": ok, "motif": motif})


@router.post("/pilotage/annuler")
async def pilotage_annuler(corps: Dict[str, Any] = Body(default={})) -> JSONResponse:
    from core.pilotage_ia import annuler_decision, etat_pilotage

    try:
        identifiant = int((corps or {}).get("id"))
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "motif": "id manquant"}, status_code=400)
    ok, motif = annuler_decision(identifiant, motif="annulé depuis l'interface")
    return JSONResponse({**etat_pilotage(), "ok": ok, "motif": motif})

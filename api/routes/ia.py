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
    return JSONResponse(conseiller_ia.demander_avis(question, contexte))


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

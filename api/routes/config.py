"""
API Routes pour la configuration - Inclut endpoint token MEXC
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])

# Chemin du fichier de credentials
CREDENTIALS_FILE = "credentials.json"


class MexcTokenRequest(BaseModel):
    """Requête pour mettre à jour le token MEXC"""
    token: str


class MexcTokenResponse(BaseModel):
    """Réponse après mise à jour du token"""
    success: bool
    message: str
    updated_at: Optional[str] = None


@router.post("/mexc-token", response_model=MexcTokenResponse)
async def update_mexc_token(request: MexcTokenRequest):
    """
    Met à jour le token d'authentification MEXC (web cookie)
    
    Appelé par l'extension Firefox MEXC Token Helper
    """
    try:
        token = request.token.strip()
        
        if not token:
            raise HTTPException(status_code=400, detail="Token vide")
        
        if len(token) < 20:
            raise HTTPException(status_code=400, detail="Token trop court (minimum 20 caractères)")
        
        # Charger les credentials existants
        credentials = {}
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                    credentials = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Fichier {CREDENTIALS_FILE} corrompu, création nouveau")
        
        # Mettre à jour le token
        credentials['mexc_web_token'] = token
        credentials['mexc_web_token_updated_at'] = datetime.now().isoformat()
        
        # Sauvegarder
        with open(CREDENTIALS_FILE, 'w', encoding='utf-8') as f:
            json.dump(credentials, f, indent=2)
        
        logger.info(f"✅ Token MEXC mis à jour (longueur: {len(token)})")
        
        # Notifier le bypass client si disponible
        try:
            from trading.mexc_futures_bypass import MexcFuturesBypass
            # Le bypass rechargera le token au prochain appel
        except ImportError:
            pass
        
        return MexcTokenResponse(
            success=True,
            message=f"Token mis à jour avec succès ({len(token)} caractères)",
            updated_at=credentials['mexc_web_token_updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour token MEXC: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mexc-token/status")
async def get_mexc_token_status():
    """
    Vérifie le statut du token MEXC
    """
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            return {
                "has_token": False,
                "message": "Aucun fichier credentials"
            }
        
        with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
            credentials = json.load(f)
        
        token = credentials.get('mexc_web_token')
        updated_at = credentials.get('mexc_web_token_updated_at')
        
        if not token:
            return {
                "has_token": False,
                "message": "Token non configuré"
            }
        
        return {
            "has_token": True,
            "token_length": len(token),
            "token_preview": token[:10] + "..." + token[-5:] if len(token) > 20 else "***",
            "updated_at": updated_at,
            "message": "Token configuré"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur vérification token: {e}")
        return {
            "has_token": False,
            "error": str(e)
        }

"""
Module d'authentification pour l'API
Gère les API keys et la vérification des accès
"""
import os
import secrets
import threading
import logging
from typing import Dict, Optional
from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Schéma de sécurité pour l'API key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Charger les API keys depuis l'environnement
# Format: API_KEYS=key1:admin,key2:user
def load_api_keys() -> Dict[str, dict]:
    """Charge les API keys depuis les variables d'environnement"""
    keys = {}
    api_keys_str = os.getenv("API_KEYS", "")

    if not api_keys_str:
        # Générer une clé par défaut en développement
        default_key = os.getenv("DEFAULT_API_KEY")
        if not default_key:
            default_key = secrets.token_urlsafe(32)
            logger.warning("⚠️  ATTENTION: Aucune API key configurée!")
            logger.warning("   Clé générée automatiquement (masquée pour sécurité)")
            logger.warning(f"   Préfixe de la clé: {default_key[:8]}...")
            logger.warning(f"   Ajoutez DEFAULT_API_KEY=<votre_clé> dans votre .env")
            # NE PAS logger la clé complète en production!
            # Écrire dans un fichier sécurisé uniquement en mode développement
            if os.getenv("ENVIRONMENT", "development") == "development":
                try:
                    with open(".api_key_generated.txt", "w") as f:
                        f.write(f"DEFAULT_API_KEY={default_key}\n")
                    logger.info("   Clé sauvegardée dans .api_key_generated.txt (ajoutez ce fichier à .gitignore!)")
                except Exception as e:
                    logger.error(f"Erreur lors de la sauvegarde de la clé: {e}")

        keys[default_key] = {"name": "default", "roles": ["admin"]}
        return keys

    # Parser les clés depuis API_KEYS=key1:admin:user,key2:readonly
    for key_config in api_keys_str.split(","):
        parts = key_config.strip().split(":")
        if len(parts) >= 2:
            key = parts[0]
            name = parts[1] if len(parts) > 1 else "unknown"
            roles = parts[2:] if len(parts) > 2 else ["user"]
            keys[key] = {"name": name, "roles": roles}

    return keys

API_KEYS = load_api_keys()
_api_keys_lock = threading.Lock()


async def verify_api_key(api_key: str = Security(api_key_header)) -> dict:
    """
    Vérifie l'API key et retourne les informations de l'utilisateur

    Args:
        api_key: La clé API fournie dans le header X-API-Key

    Returns:
        dict: Informations de l'utilisateur (name, roles)

    Raises:
        HTTPException: Si la clé est invalide ou manquante
    """
    if not api_key:
        raise HTTPException(
            status_code=403,
            detail="API key manquante. Ajoutez le header X-API-Key"
        )

    with _api_keys_lock:
        if api_key not in API_KEYS:
            raise HTTPException(
                status_code=403,
                detail="API key invalide"
            )

        return API_KEYS[api_key]


async def verify_api_key_optional(api_key: str = Security(api_key_header)) -> Optional[dict]:
    """
    Vérifie l'API key de manière optionnelle (pour endpoints publics)

    Args:
        api_key: La clé API fournie dans le header X-API-Key

    Returns:
        dict ou None: Informations de l'utilisateur si authentifié, None sinon
    """
    if not api_key:
        return None

    with _api_keys_lock:
        if api_key not in API_KEYS:
            return None

        return API_KEYS[api_key]


def require_role(required_role: str):
    """
    Décorateur pour vérifier qu'un utilisateur a un rôle spécifique

    Usage:
        @app.get("/admin")
        async def admin_endpoint(user: dict = Depends(require_role("admin"))):
            ...
    """
    async def role_checker(user: dict = Security(verify_api_key)) -> dict:
        if required_role not in user.get("roles", []):
            raise HTTPException(
                status_code=403,
                detail=f"Rôle '{required_role}' requis"
            )
        return user
    return role_checker


def generate_api_key() -> str:
    """Génère une nouvelle API key sécurisée"""
    return secrets.token_urlsafe(32)

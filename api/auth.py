"""
Module d'authentification pour l'API
Gère les API keys et la vérification des accès
"""
import os
import secrets
from typing import Dict, Optional
from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()

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
            print(f"⚠️  ATTENTION: Aucune API key configurée!")
            print(f"   Clé générée automatiquement: {default_key}")
            print(f"   Ajoutez DEFAULT_API_KEY={default_key} dans votre .env")

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


def validate_token(token: str) -> bool:
    """Compatibilité tests: valider un token/API key (bool)."""
    if not token:
        return False
    return token in API_KEYS


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

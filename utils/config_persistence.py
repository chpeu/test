"""
Persistence de la configuration TRADING_CONFIG dans un fichier JSON
pour conserver les modifications entre redémarrages
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

CONFIG_OVERRIDES_FILE = Path(__file__).parent.parent / "config_overrides.json"


def save_config_overrides(overrides: Dict[str, Any]) -> bool:
    """
    Sauvegarder les overrides de configuration dans config_overrides.json
    
    Args:
        overrides: Dict des paramètres à persister
        
    Returns:
        True si sauvegarde réussie, False sinon
    """
    try:
        # Charger les overrides existants
        existing_overrides = load_config_overrides()
        
        # Fusionner avec les nouveaux
        existing_overrides.update(overrides)
        
        # Sauvegarder
        with open(CONFIG_OVERRIDES_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_overrides, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Config overrides sauvegardés: {len(existing_overrides)} paramètres")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde config overrides: {e}", exc_info=True)
        return False


def load_config_overrides() -> Dict[str, Any]:
    """
    Charger les overrides de configuration depuis config_overrides.json
    
    Returns:
        Dict des overrides ou {} si fichier inexistant
    """
    try:
        if not CONFIG_OVERRIDES_FILE.exists():
            return {}
        
        with open(CONFIG_OVERRIDES_FILE, 'r', encoding='utf-8') as f:
            overrides = json.load(f)
        
        logger.info(f"✅ Config overrides chargés: {len(overrides)} paramètres")
        return overrides
        
    except Exception as e:
        logger.error(f"❌ Erreur chargement config overrides: {e}", exc_info=True)
        return {}


def apply_config_overrides(trading_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Appliquer les overrides persistés sur TRADING_CONFIG
    
    Args:
        trading_config: TRADING_CONFIG à modifier
        
    Returns:
        TRADING_CONFIG modifié
    """
    try:
        overrides = load_config_overrides()
        
        if not overrides:
            logger.info("ℹ️ Aucun override de config à appliquer")
            return trading_config
        
        # Appliquer chaque override
        applied_count = 0
        # Prefixes autorisés pour nouvelles clés (config UI)
        allowed_new_prefixes = ('gb_', 'ml_', 'xgb_', 'optuna_')
        
        for key, value in overrides.items():
            if key in trading_config:
                trading_config[key] = value
                applied_count += 1
            elif key.startswith(allowed_new_prefixes):
                # Accepter nouvelles clés pour GB, ML, XGBoost, Optuna
                trading_config[key] = value
                applied_count += 1
            else:
                logger.warning(f"⚠️ Override ignoré (clé inconnue): {key}")
        
        logger.info(f"✅ {applied_count} overrides appliqués sur TRADING_CONFIG")
        return trading_config
        
    except Exception as e:
        logger.error(f"❌ Erreur application config overrides: {e}", exc_info=True)
        return trading_config


def get_config_value(key: str, default: Any = None) -> Any:
    """
    🔥 Récupérer une valeur de configuration avec priorité aux flat keys.
    
    Cette fonction garantit que les valeurs modifiées via le frontend (flat keys)
    sont toujours prioritaires sur les dictionnaires imbriqués par défaut.
    
    Args:
        key: Clé de configuration (flat key, ex: 'stagnation_exit_timeout_seconds')
        default: Valeur par défaut si non trouvée
        
    Returns:
        Valeur de la configuration
    """
    try:
        from config import TRADING_CONFIG
        
        # 1. Priorité aux flat keys (mises à jour dynamiquement via frontend)
        if key in TRADING_CONFIG:
            return TRADING_CONFIG[key]
        
        # 2. Fallback sur default
        return default
        
    except Exception as e:
        logger.warning(f"⚠️ Erreur get_config_value({key}): {e}")
        return default


def get_nested_config_value(flat_key: str, nested_dict_name: str, nested_key: str, default: Any = None) -> Any:
    """
    🔥 Récupérer une valeur de configuration avec priorité flat key > dict imbriqué.
    
    Exemple:
        get_nested_config_value('stagnation_exit_timeout_seconds', 'stagnation_exit', 'timeout_seconds', 120)
        → Retourne TRADING_CONFIG['stagnation_exit_timeout_seconds'] si existe
        → Sinon retourne TRADING_CONFIG['stagnation_exit']['timeout_seconds'] si existe
        → Sinon retourne 120
    
    Args:
        flat_key: Clé plate (ex: 'stagnation_exit_timeout_seconds')
        nested_dict_name: Nom du dict imbriqué (ex: 'stagnation_exit')
        nested_key: Clé dans le dict imbriqué (ex: 'timeout_seconds')
        default: Valeur par défaut
        
    Returns:
        Valeur de la configuration
    """
    try:
        from config import TRADING_CONFIG
        
        # 1. Priorité aux flat keys (mises à jour dynamiquement via frontend)
        if flat_key in TRADING_CONFIG:
            return TRADING_CONFIG[flat_key]
        
        # 2. Fallback sur dict imbriqué
        nested_dict = TRADING_CONFIG.get(nested_dict_name, {})
        if nested_key in nested_dict:
            return nested_dict[nested_key]
        
        # 3. Default
        return default
        
    except Exception as e:
        logger.warning(f"⚠️ Erreur get_nested_config_value({flat_key}): {e}")
        return default


def clear_config_overrides() -> bool:
    """
    Supprimer tous les overrides de configuration
    
    Returns:
        True si succès, False sinon
    """
    try:
        if CONFIG_OVERRIDES_FILE.exists():
            CONFIG_OVERRIDES_FILE.unlink()
            logger.info("✅ Config overrides supprimés")
        else:
            logger.info("ℹ️ Aucun override à supprimer")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur suppression config overrides: {e}", exc_info=True)
        return False

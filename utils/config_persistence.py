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

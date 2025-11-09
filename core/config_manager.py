"""
Gestionnaire de configuration persistante

Permet de sauvegarder les modifications de configuration dans un fichier JSON
et de les charger au démarrage.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)


class ConfigManager:
    """Gestionnaire de configuration avec sauvegarde persistante"""

    def __init__(self, config_file: str = "config_overrides.json"):
        self.config_file = Path(config_file)
        self.overrides = {}
        self.lock = Lock()
        self.load_overrides()

    def load_overrides(self) -> None:
        """Charger les overrides depuis le fichier JSON"""
        if not self.config_file.exists():
            logger.info(f"📄 Fichier {self.config_file} n'existe pas, création avec config par défaut")
            self.overrides = {}
            return

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.overrides = json.load(f)
            logger.info(f"✅ Configuration chargée depuis {self.config_file} ({len(self.overrides)} overrides)")
        except Exception as e:
            logger.error(f"❌ Erreur chargement config depuis {self.config_file}: {e}")
            self.overrides = {}

    def save_overrides(self) -> bool:
        """Sauvegarder les overrides dans le fichier JSON"""
        try:
            with self.lock:
                # Atomic write: écrire dans un fichier temporaire puis renommer
                temp_file = self.config_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.overrides, f, indent=2, ensure_ascii=False)

                # Remplacer l'ancien fichier
                temp_file.replace(self.config_file)

            logger.info(f"💾 Configuration sauvegardée dans {self.config_file} ({len(self.overrides)} overrides)")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde config dans {self.config_file}: {e}")
            return False

    def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mettre à jour la configuration avec les nouvelles valeurs

        Args:
            updates: Dictionnaire des nouvelles valeurs

        Returns:
            Dictionnaire des valeurs mises à jour
        """
        updated = {}

        with self.lock:
            for key, value in updates.items():
                # Ignorer les valeurs None
                if value is None:
                    continue

                # Sauvegarder l'override
                self.overrides[key] = value
                updated[key] = value

            # Sauvegarder dans le fichier
            if updated:
                self.save_overrides()

        return updated

    def get_config(self, defaults: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtenir la configuration complète (defaults + overrides)

        Args:
            defaults: Configuration par défaut

        Returns:
            Configuration complète (defaults + overrides)
        """
        with self.lock:
            # Merger defaults avec overrides
            config = {**defaults, **self.overrides}
            return config

    def reset_to_defaults(self) -> None:
        """Réinitialiser tous les overrides"""
        with self.lock:
            self.overrides = {}
            self.save_overrides()
        logger.info("🔄 Configuration réinitialisée aux valeurs par défaut")

    def reset_key(self, key: str) -> bool:
        """
        Réinitialiser une seule clé

        Args:
            key: Clé à réinitialiser

        Returns:
            True si la clé existait, False sinon
        """
        with self.lock:
            if key in self.overrides:
                del self.overrides[key]
                self.save_overrides()
                logger.info(f"🔄 Clé '{key}' réinitialisée")
                return True
            return False

    def get_overrides(self) -> Dict[str, Any]:
        """Obtenir tous les overrides actuels"""
        with self.lock:
            return self.overrides.copy()


# Instance globale
_config_manager = None

def get_config_manager() -> ConfigManager:
    """Obtenir l'instance globale du ConfigManager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

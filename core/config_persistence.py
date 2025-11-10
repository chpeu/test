"""
Persistence de la configuration du bot
Sauvegarde et chargement des paramètres de trading
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigPersistence:
    """Gère la persistance de la configuration"""

    def __init__(self, config_file: str = "config/trading_config.json"):
        self.config_file = Path(config_file)
        self.config_dir = self.config_file.parent
        self.backup_dir = self.config_dir / "backups"

        # Créer les répertoires si nécessaire
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def save(self, config: Dict[str, Any]) -> bool:
        """
        Sauvegarder la configuration

        Args:
            config: Dictionnaire de configuration à sauvegarder

        Returns:
            True si la sauvegarde a réussi, False sinon
        """
        try:
            # Créer une sauvegarde de la config actuelle si elle existe
            if self.config_file.exists():
                timestamp = int(time.time())
                backup_file = self.backup_dir / f"config_backup_{timestamp}.json"
                self.config_file.rename(backup_file)

                # Garder seulement les 10 dernières sauvegardes
                self._cleanup_old_backups(keep=10)

            # Sauvegarder la nouvelle config
            config_data = {
                'config': config,
                'timestamp': time.time(),
                'version': '7.0.0'
            }

            # Écrire dans un fichier temporaire d'abord
            temp_file = self.config_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            # Renommer le fichier temporaire (atomic operation)
            temp_file.replace(self.config_file)

            logger.info(f"✅ Configuration sauvegardée: {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde configuration: {e}")
            return False

    def load(self) -> Optional[Dict[str, Any]]:
        """
        Charger la configuration

        Returns:
            Dictionnaire de configuration ou None si erreur
        """
        try:
            if not self.config_file.exists():
                logger.info("ℹ️ Aucune configuration sauvegardée trouvée")
                return None

            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            config = config_data.get('config', {})
            timestamp = config_data.get('timestamp', 0)
            version = config_data.get('version', 'unknown')

            logger.info(f"✅ Configuration chargée: {len(config)} paramètres (version {version}, {time.time() - timestamp:.0f}s ago)")
            return config

        except Exception as e:
            logger.error(f"❌ Erreur chargement configuration: {e}")

            # Essayer de restaurer depuis une sauvegarde
            restored = self._restore_from_backup()
            if restored:
                return restored

            return None

    def _restore_from_backup(self) -> Optional[Dict[str, Any]]:
        """
        Restaurer depuis la sauvegarde la plus récente

        Returns:
            Dictionnaire de configuration ou None si aucune sauvegarde
        """
        try:
            # Trouver la sauvegarde la plus récente
            backups = sorted(self.backup_dir.glob("config_backup_*.json"), reverse=True)

            if not backups:
                logger.warning("⚠️ Aucune sauvegarde disponible")
                return None

            latest_backup = backups[0]
            logger.info(f"🔄 Restauration depuis sauvegarde: {latest_backup.name}")

            with open(latest_backup, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            config = config_data.get('config', {})

            # Copier la sauvegarde comme config actuelle
            latest_backup.replace(self.config_file)

            logger.info(f"✅ Configuration restaurée depuis sauvegarde")
            return config

        except Exception as e:
            logger.error(f"❌ Erreur restauration depuis sauvegarde: {e}")
            return None

    def _cleanup_old_backups(self, keep: int = 10):
        """
        Supprimer les anciennes sauvegardes

        Args:
            keep: Nombre de sauvegardes à garder
        """
        try:
            backups = sorted(self.backup_dir.glob("config_backup_*.json"), reverse=True)

            # Supprimer les sauvegardes au-delà de 'keep'
            for old_backup in backups[keep:]:
                old_backup.unlink()
                logger.debug(f"🗑️ Sauvegarde supprimée: {old_backup.name}")

        except Exception as e:
            logger.warning(f"⚠️ Erreur nettoyage sauvegardes: {e}")

    def list_backups(self) -> list:
        """
        Lister toutes les sauvegardes disponibles

        Returns:
            Liste des chemins de sauvegarde triés par date (plus récent en premier)
        """
        return sorted(self.backup_dir.glob("config_backup_*.json"), reverse=True)

    def export_config(self, export_file: str) -> bool:
        """
        Exporter la configuration vers un fichier

        Args:
            export_file: Chemin du fichier d'export

        Returns:
            True si l'export a réussi, False sinon
        """
        try:
            if not self.config_file.exists():
                logger.warning("⚠️ Aucune configuration à exporter")
                return False

            export_path = Path(export_file)
            export_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, 'r', encoding='utf-8') as src:
                config_data = json.load(src)

            with open(export_path, 'w', encoding='utf-8') as dst:
                json.dump(config_data, dst, indent=2, ensure_ascii=False)

            logger.info(f"✅ Configuration exportée: {export_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur export configuration: {e}")
            return False

    def import_config(self, import_file: str) -> Optional[Dict[str, Any]]:
        """
        Importer une configuration depuis un fichier

        Args:
            import_file: Chemin du fichier à importer

        Returns:
            Dictionnaire de configuration importée ou None si erreur
        """
        try:
            import_path = Path(import_file)

            if not import_path.exists():
                logger.error(f"❌ Fichier d'import introuvable: {import_file}")
                return None

            with open(import_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            config = config_data.get('config', {})

            # Sauvegarder la configuration importée
            self.save(config)

            logger.info(f"✅ Configuration importée: {import_path}")
            return config

        except Exception as e:
            logger.error(f"❌ Erreur import configuration: {e}")
            return None


# Instance globale
_config_persistence = None

def get_config_persistence(config_file: str = "config/trading_config.json") -> ConfigPersistence:
    """Obtenir l'instance de ConfigPersistence"""
    global _config_persistence
    if _config_persistence is None:
        _config_persistence = ConfigPersistence(config_file)
    return _config_persistence

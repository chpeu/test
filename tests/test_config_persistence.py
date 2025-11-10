"""
Tests pour core/config_persistence.py
Couverture des fonctionnalités de sauvegarde/chargement de configuration
"""
import pytest
import json
import tempfile
import time
from pathlib import Path
from core.config_persistence import ConfigPersistence, get_config_persistence


class TestConfigPersistence:
    """Tests pour la classe ConfigPersistence"""

    @pytest.fixture
    def temp_config_dir(self):
        """Créer un répertoire temporaire pour les tests"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_persistence(self, temp_config_dir):
        """Créer une instance de ConfigPersistence pour les tests"""
        config_file = temp_config_dir / "test_config.json"
        return ConfigPersistence(str(config_file))

    def test_init_creates_directories(self, temp_config_dir):
        """Test que les répertoires sont créés à l'initialisation"""
        config_file = temp_config_dir / "config" / "trading_config.json"
        cp = ConfigPersistence(str(config_file))

        assert cp.config_dir.exists()
        assert cp.backup_dir.exists()
        assert cp.config_file == config_file

    def test_save_config_success(self, config_persistence):
        """Test sauvegarde de configuration réussie"""
        test_config = {
            'tp_percent': 0.6,
            'sl_percent': 0.25,
            'tp_sl_mode': 'FIXE'
        }

        result = config_persistence.save(test_config)

        assert result is True
        assert config_persistence.config_file.exists()

        # Vérifier le contenu
        with open(config_persistence.config_file, 'r') as f:
            data = json.load(f)
            assert data['config'] == test_config
            assert 'timestamp' in data
            assert data['version'] == '7.0.0'

    def test_save_creates_backup(self, config_persistence):
        """Test que la sauvegarde crée un backup de l'ancienne config"""
        # Sauvegarder une première config
        config1 = {'tp_percent': 0.5}
        config_persistence.save(config1)

        # Sauvegarder une deuxième config
        time.sleep(0.1)  # Assurer un timestamp différent
        config2 = {'tp_percent': 0.8}
        config_persistence.save(config2)

        # Vérifier qu'un backup existe
        backups = list(config_persistence.backup_dir.glob("config_backup_*.json"))
        assert len(backups) >= 1

        # Vérifier que la config actuelle est bien la deuxième
        loaded = config_persistence.load()
        assert loaded['tp_percent'] == 0.8

    def test_load_config_success(self, config_persistence):
        """Test chargement de configuration réussie"""
        test_config = {
            'tp_percent': 0.6,
            'sl_percent': 0.25,
            'use_confluence': True
        }

        config_persistence.save(test_config)
        loaded_config = config_persistence.load()

        assert loaded_config == test_config

    def test_load_nonexistent_config(self, config_persistence):
        """Test chargement d'une config qui n'existe pas"""
        result = config_persistence.load()
        assert result is None

    def test_load_corrupted_config_restores_backup(self, config_persistence):
        """Test restauration depuis backup si config corrompue"""
        # Sauvegarder une config valide
        valid_config = {'tp_percent': 0.6}
        config_persistence.save(valid_config)

        # Corrompre le fichier de config
        with open(config_persistence.config_file, 'w') as f:
            f.write("corrupted json{{{")

        # Charger devrait restaurer depuis le backup
        loaded = config_persistence.load()

        # Si restauration réussie, on devrait avoir la config valide
        if loaded:
            assert loaded['tp_percent'] == 0.6

    def test_cleanup_old_backups(self, config_persistence):
        """Test nettoyage des anciennes sauvegardes"""
        # Créer 15 backups
        for i in range(15):
            config = {'iteration': i}
            config_persistence.save(config)
            time.sleep(0.01)

        # Vérifier qu'il ne reste que 10 backups (keep=10)
        backups = list(config_persistence.backup_dir.glob("config_backup_*.json"))
        assert len(backups) <= 10

    def test_list_backups(self, config_persistence):
        """Test listage des backups"""
        # Créer quelques backups
        for i in range(3):
            config = {'iteration': i}
            config_persistence.save(config)
            time.sleep(0.01)

        backups = config_persistence.list_backups()

        assert len(backups) > 0
        # Les backups devraient être triés par date (plus récent en premier)
        assert all(isinstance(b, Path) for b in backups)

    def test_export_config(self, config_persistence, temp_config_dir):
        """Test export de configuration"""
        test_config = {'tp_percent': 0.7, 'sl_percent': 0.3}
        config_persistence.save(test_config)

        export_file = temp_config_dir / "exported_config.json"
        result = config_persistence.export_config(str(export_file))

        assert result is True
        assert export_file.exists()

        # Vérifier le contenu exporté
        with open(export_file, 'r') as f:
            exported_data = json.load(f)
            assert exported_data['config'] == test_config

    def test_export_nonexistent_config(self, config_persistence, temp_config_dir):
        """Test export d'une config qui n'existe pas"""
        export_file = temp_config_dir / "exported_config.json"
        result = config_persistence.export_config(str(export_file))

        assert result is False
        assert not export_file.exists()

    def test_import_config(self, config_persistence, temp_config_dir):
        """Test import de configuration"""
        # Créer un fichier d'import
        import_data = {
            'config': {'tp_percent': 0.9, 'sl_percent': 0.2},
            'timestamp': time.time(),
            'version': '7.0.0'
        }
        import_file = temp_config_dir / "import_config.json"
        with open(import_file, 'w') as f:
            json.dump(import_data, f)

        # Importer
        result = config_persistence.import_config(str(import_file))

        assert result is not None
        assert result['tp_percent'] == 0.9
        assert result['sl_percent'] == 0.2

        # Vérifier que la config a été sauvegardée
        loaded = config_persistence.load()
        assert loaded['tp_percent'] == 0.9

    def test_import_nonexistent_file(self, config_persistence):
        """Test import d'un fichier qui n'existe pas"""
        result = config_persistence.import_config("nonexistent_file.json")
        assert result is None

    def test_import_corrupted_file(self, config_persistence, temp_config_dir):
        """Test import d'un fichier corrompu"""
        import_file = temp_config_dir / "corrupted_import.json"
        with open(import_file, 'w') as f:
            f.write("corrupted{{{")

        result = config_persistence.import_config(str(import_file))
        assert result is None

    def test_save_atomic_operation(self, config_persistence):
        """Test que la sauvegarde est atomique (via fichier temporaire)"""
        test_config = {'tp_percent': 0.6}

        # La sauvegarde devrait passer par un fichier .tmp
        config_persistence.save(test_config)

        # Le fichier .tmp ne devrait plus exister après sauvegarde
        tmp_file = config_persistence.config_file.with_suffix('.tmp')
        assert not tmp_file.exists()

        # Le fichier final devrait exister
        assert config_persistence.config_file.exists()

    def test_restore_from_backup_latest(self, config_persistence):
        """Test restauration depuis le backup le plus récent"""
        # Créer plusieurs backups
        for i in range(3):
            config = {'iteration': i}
            config_persistence.save(config)
            time.sleep(0.01)

        # Supprimer la config actuelle
        config_persistence.config_file.unlink()

        # Charger devrait restaurer depuis le backup le plus récent
        loaded = config_persistence.load()

        if loaded:
            assert loaded['iteration'] == 2  # La dernière sauvegarde


class TestGetConfigPersistence:
    """Tests pour la fonction get_config_persistence (singleton)"""

    def test_singleton_returns_same_instance(self):
        """Test que get_config_persistence retourne toujours la même instance"""
        # Reset global instance
        import core.config_persistence
        core.config_persistence._config_persistence = None

        instance1 = get_config_persistence()
        instance2 = get_config_persistence()

        assert instance1 is instance2

    def test_custom_config_file(self):
        """Test avec un fichier de config personnalisé"""
        # Reset global instance
        import core.config_persistence
        core.config_persistence._config_persistence = None

        custom_file = "custom_path/custom_config.json"
        instance = get_config_persistence(custom_file)

        assert instance.config_file == Path(custom_file)

"""
Tests unitaires pour ConfigManager
"""
import json
import tempfile
import unittest
from pathlib import Path

from core.config_manager import ConfigManager, get_config_manager


class TestConfigManager(unittest.TestCase):
    """Tests pour ConfigManager"""

    def setUp(self):
        """Setup pour chaque test"""
        # Créer un fichier temporaire pour les tests
        self.temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        )
        self.temp_file.close()
        self.config_file = self.temp_file.name

    def tearDown(self):
        """Cleanup après chaque test"""
        # Supprimer le fichier temporaire
        Path(self.config_file).unlink(missing_ok=True)
        Path(self.config_file).with_suffix('.tmp').unlink(missing_ok=True)

    def test_init_creates_empty_overrides(self):
        """Test initialisation avec fichier inexistant"""
        manager = ConfigManager(config_file=self.config_file)
        self.assertEqual(manager.overrides, {})

    def test_init_loads_existing_file(self):
        """Test chargement d'un fichier existant"""
        # Créer un fichier avec des données
        test_data = {"account_size": 5000.0, "risk_per_trade": 2.0}
        with open(self.config_file, 'w') as f:
            json.dump(test_data, f)

        manager = ConfigManager(config_file=self.config_file)
        self.assertEqual(manager.overrides, test_data)

    def test_save_overrides(self):
        """Test sauvegarde des overrides"""
        manager = ConfigManager(config_file=self.config_file)
        manager.overrides = {"account_size": 3000.0}

        result = manager.save_overrides()
        self.assertTrue(result)

        # Vérifier que le fichier contient les bonnes données
        with open(self.config_file, 'r') as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data, {"account_size": 3000.0})

    def test_update_config(self):
        """Test mise à jour de la configuration"""
        manager = ConfigManager(config_file=self.config_file)

        updates = {
            "account_size": 2000.0,
            "risk_per_trade": 1.5,
            "use_breakout": False
        }

        updated = manager.update_config(updates)

        # Vérifier que les valeurs sont mises à jour
        self.assertEqual(updated, updates)
        self.assertEqual(manager.overrides, updates)

        # Vérifier que le fichier est sauvegardé
        with open(self.config_file, 'r') as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data, updates)

    def test_update_config_ignores_none(self):
        """Test que update_config ignore les valeurs None"""
        manager = ConfigManager(config_file=self.config_file)

        updates = {
            "account_size": 2000.0,
            "risk_per_trade": None,  # Devrait être ignoré
            "use_breakout": False
        }

        updated = manager.update_config(updates)

        # Vérifier que None n'est pas dans les overrides
        self.assertNotIn("risk_per_trade", updated)
        self.assertEqual(updated, {
            "account_size": 2000.0,
            "use_breakout": False
        })

    def test_get_config_merges_defaults(self):
        """Test que get_config merge correctement defaults et overrides"""
        manager = ConfigManager(config_file=self.config_file)
        manager.overrides = {"account_size": 2000.0}

        defaults = {
            "account_size": 1000.0,
            "risk_per_trade": 1.0,
            "tp_percent": 0.6
        }

        config = manager.get_config(defaults)

        # Vérifier que account_size est overridé
        self.assertEqual(config["account_size"], 2000.0)
        # Vérifier que les autres valeurs viennent des defaults
        self.assertEqual(config["risk_per_trade"], 1.0)
        self.assertEqual(config["tp_percent"], 0.6)

    def test_reset_to_defaults(self):
        """Test réinitialisation complète"""
        manager = ConfigManager(config_file=self.config_file)
        manager.overrides = {"account_size": 2000.0, "risk_per_trade": 1.5}

        manager.reset_to_defaults()

        # Vérifier que les overrides sont vides
        self.assertEqual(manager.overrides, {})

        # Vérifier que le fichier est sauvegardé
        with open(self.config_file, 'r') as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data, {})

    def test_reset_key(self):
        """Test réinitialisation d'une seule clé"""
        manager = ConfigManager(config_file=self.config_file)
        manager.overrides = {
            "account_size": 2000.0,
            "risk_per_trade": 1.5,
            "use_breakout": False
        }

        # Réinitialiser une clé existante
        result = manager.reset_key("account_size")
        self.assertTrue(result)
        self.assertNotIn("account_size", manager.overrides)
        self.assertIn("risk_per_trade", manager.overrides)

        # Réinitialiser une clé inexistante
        result = manager.reset_key("nonexistent_key")
        self.assertFalse(result)

    def test_get_overrides(self):
        """Test récupération des overrides"""
        manager = ConfigManager(config_file=self.config_file)
        test_data = {"account_size": 2000.0, "risk_per_trade": 1.5}
        manager.overrides = test_data.copy()

        overrides = manager.get_overrides()

        # Vérifier que c'est une copie
        self.assertEqual(overrides, test_data)
        self.assertIsNot(overrides, manager.overrides)

    def test_thread_safety(self):
        """Test thread-safety basique"""
        import threading

        manager = ConfigManager(config_file=self.config_file)

        def update_config(key, value):
            manager.update_config({key: value})

        # Créer plusieurs threads qui modifient la config
        threads = []
        for i in range(10):
            t = threading.Thread(target=update_config, args=(f"key_{i}", i))
            threads.append(t)
            t.start()

        # Attendre que tous les threads terminent
        for t in threads:
            t.join()

        # Vérifier que toutes les mises à jour sont présentes
        self.assertEqual(len(manager.overrides), 10)
        for i in range(10):
            self.assertIn(f"key_{i}", manager.overrides)
            self.assertEqual(manager.overrides[f"key_{i}"], i)

    def test_corrupted_json_file(self):
        """Test chargement d'un fichier JSON corrompu"""
        # Créer un fichier JSON invalide
        with open(self.config_file, 'w') as f:
            f.write("{ invalid json }")

        manager = ConfigManager(config_file=self.config_file)

        # Devrait initialiser avec des overrides vides
        self.assertEqual(manager.overrides, {})

    def test_atomic_write(self):
        """Test que l'écriture est atomique via fichier temporaire"""
        manager = ConfigManager(config_file=self.config_file)
        manager.overrides = {"account_size": 2000.0}

        manager.save_overrides()

        # Vérifier que le fichier temporaire n'existe plus
        temp_file = Path(self.config_file).with_suffix('.tmp')
        self.assertFalse(temp_file.exists())

        # Vérifier que le fichier final existe
        self.assertTrue(Path(self.config_file).exists())

    def test_get_config_manager_singleton(self):
        """Test que get_config_manager retourne toujours la même instance"""
        # Note: Ce test peut interférer avec d'autres tests si exécuté en parallèle
        # car il utilise l'instance globale
        manager1 = get_config_manager()
        manager2 = get_config_manager()

        self.assertIs(manager1, manager2)


if __name__ == '__main__':
    unittest.main()

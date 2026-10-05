#!/usr/bin/env python3
"""
Tests de couverture pour la gestion des tokens MEXC
Vérifie l'extraction, synchronisation et validation des tokens
"""

import pytest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tools.sync_mexc_token import MEXCTokenSyncer
    from tools.validate_mexc_tokens import MEXCTokenValidator
except ImportError:
    pytest.skip("Modules tools non disponibles", allow_module_level=True)


class TestMEXCTokenSyncer:
    """Tests pour la synchronisation des tokens MEXC"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Créer les fichiers de test
        self.create_test_files()
    
    def teardown_method(self):
        """Cleanup après chaque test"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
    
    def create_test_files(self):
        """Créer les fichiers de test"""
        # mexc_tokens.json valide
        token_data = {
            "token": '{"cookies": {"uc_token": "WEB123test456"}, "type": "cookie_composite_direct"}',
            "extracted_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            "status": "active"
        }
        
        os.makedirs("tools", exist_ok=True)
        with open("tools/mexc_tokens.json", "w") as f:
            json.dump(token_data, f)
        
        # .env file
        with open(".env", "w") as f:
            f.write("MEXC_BROWSER_TOKEN=WEB_OLD_TOKEN\n")
            f.write("OTHER_VAR=value\n")
        
        # config_live_persistent.json
        config_data = {
            "trading_mode": "LIVE",
            "browser_token_mexc": "WEB_OLD_CONFIG_TOKEN"
        }
        with open("config_live_persistent.json", "w") as f:
            json.dump(config_data, f)
    
    def test_extract_token_from_composite(self):
        """Test extraction du token depuis un token composite"""
        syncer = MEXCTokenSyncer()
        
        composite_token = '{"cookies": {"uc_token": "WEB123test456"}, "type": "cookie_composite_direct"}'
        extracted = syncer.extract_token_from_composite(composite_token)
        
        assert extracted == "WEB123test456"
    
    def test_get_current_token_valid(self):
        """Test récupération d'un token valide"""
        syncer = MEXCTokenSyncer()
        token = syncer.get_current_token()
        
        assert token == "WEB123test456"
    
    def test_get_current_token_expired(self):
        """Test récupération d'un token expiré"""
        # Créer un token expiré
        token_data = {
            "token": '{"cookies": {"uc_token": "WEB123expired"}, "type": "cookie_composite_direct"}',
            "extracted_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() - timedelta(hours=1)).isoformat(),
            "status": "active"
        }
        
        with open("tools/mexc_tokens.json", "w") as f:
            json.dump(token_data, f)
        
        syncer = MEXCTokenSyncer()
        token = syncer.get_current_token()
        
        assert token is None
    
    def test_update_env_file(self):
        """Test mise à jour du fichier .env"""
        syncer = MEXCTokenSyncer()
        success = syncer.update_env_file("WEB_NEW_TOKEN")
        
        assert success is True
        
        # Vérifier que le token a été mis à jour
        with open(".env", "r") as f:
            content = f.read()
            assert "MEXC_BROWSER_TOKEN=WEB_NEW_TOKEN" in content
            assert "OTHER_VAR=value" in content
    
    def test_update_config_live_persistent(self):
        """Test mise à jour du fichier config_live_persistent.json"""
        syncer = MEXCTokenSyncer()
        success = syncer.update_config_live_persistent("WEB_NEW_CONFIG_TOKEN")
        
        assert success is True
        
        # Vérifier que le token a été mis à jour
        with open("config_live_persistent.json", "r") as f:
            config_data = json.load(f)
            assert config_data["browser_token_mexc"] == "WEB_NEW_CONFIG_TOKEN"
            assert config_data["trading_mode"] == "LIVE"  # Autres champs préservés
    
    def test_sync_complete(self):
        """Test synchronisation complète"""
        syncer = MEXCTokenSyncer()
        success = syncer.sync()
        
        assert success is True
        
        # Vérifier que les deux fichiers ont été mis à jour
        with open(".env", "r") as f:
            env_content = f.read()
            assert "MEXC_BROWSER_TOKEN=WEB123test456" in env_content
        
        with open("config_live_persistent.json", "r") as f:
            config_data = json.load(f)
            assert config_data["browser_token_mexc"] == "WEB123test456"
    
    def test_sync_missing_files(self):
        """Test synchronisation avec fichiers manquants"""
        # Supprimer les fichiers
        os.remove(".env")
        os.remove("config_live_persistent.json")
        
        syncer = MEXCTokenSyncer()
        success = syncer.sync()
        
        # Doit échouer car .env manquant
        assert success is False


class TestMEXCTokenValidator:
    """Tests pour la validation des tokens MEXC"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup après chaque test"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
    
    def create_consistent_files(self, token="WEB123consistent"):
        """Créer des fichiers avec des tokens cohérents"""
        # mexc_tokens.json
        token_data = {
            "token": f'{{"cookies": {{"uc_token": "{token}"}}, "type": "cookie_composite_direct"}}',
            "extracted_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            "status": "active"
        }
        
        os.makedirs("tools", exist_ok=True)
        with open("tools/mexc_tokens.json", "w") as f:
            json.dump(token_data, f)
        
        # .env
        with open(".env", "w") as f:
            f.write(f"MEXC_BROWSER_TOKEN={token}\n")
        
        # config_live_persistent.json
        config_data = {
            "browser_token_mexc": token
        }
        with open("config_live_persistent.json", "w") as f:
            json.dump(config_data, f)
    
    def test_validate_consistent_tokens(self):
        """Test validation avec tokens cohérents"""
        self.create_consistent_files()
        
        validator = MEXCTokenValidator()
        success = validator.validate_all()
        
        assert success is True
        assert len(validator.errors) == 0
    
    def test_validate_inconsistent_tokens(self):
        """Test validation avec tokens incohérents"""
        # Créer des fichiers avec tokens différents
        os.makedirs("tools", exist_ok=True)
        
        token_data = {
            "token": '{"cookies": {"uc_token": "WEB123token1"}, "type": "cookie_composite_direct"}',
            "extracted_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            "status": "active"
        }
        with open("tools/mexc_tokens.json", "w") as f:
            json.dump(token_data, f)
        
        with open(".env", "w") as f:
            f.write("MEXC_BROWSER_TOKEN=WEB123token2\n")
        
        config_data = {"browser_token_mexc": "WEB123token3"}
        with open("config_live_persistent.json", "w") as f:
            json.dump(config_data, f)
        
        validator = MEXCTokenValidator()
        success = validator.validate_all()
        
        assert success is False
        assert len(validator.errors) > 0
        assert any("TOKENS DIFFÉRENTS" in error for error in validator.errors)
    
    def test_validate_expired_token(self):
        """Test validation avec token expiré"""
        token_data = {
            "token": '{"cookies": {"uc_token": "WEB123expired"}, "type": "cookie_composite_direct"}',
            "extracted_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() - timedelta(hours=1)).isoformat(),
            "status": "active"
        }
        
        os.makedirs("tools", exist_ok=True)
        with open("tools/mexc_tokens.json", "w") as f:
            json.dump(token_data, f)
        
        with open(".env", "w") as f:
            f.write("MEXC_BROWSER_TOKEN=WEB123expired\n")
        
        validator = MEXCTokenValidator()
        success = validator.validate_all()
        
        assert success is False
        assert any("Token expiré" in error for error in validator.errors)
    
    def test_validate_missing_files(self):
        """Test validation avec fichiers manquants"""
        validator = MEXCTokenValidator()
        success = validator.validate_all()
        
        assert success is False
        assert any("Aucun token trouvé" in error for error in validator.errors)


class TestMEXCTokenIntegration:
    """Tests d'intégration pour le workflow complet"""
    
    def test_full_workflow_simulation(self):
        """Test simulation d'un workflow complet d'extraction → synchronisation → validation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # 1. Simuler extraction (créer mexc_tokens.json)
                token_data = {
                    "token": '{"cookies": {"uc_token": "WEB123workflow"}, "type": "cookie_composite_direct"}',
                    "extracted_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
                    "status": "active"
                }
                
                os.makedirs("tools", exist_ok=True)
                with open("tools/mexc_tokens.json", "w") as f:
                    json.dump(token_data, f)
                
                # 2. Créer fichiers cibles avec anciens tokens
                with open(".env", "w") as f:
                    f.write("MEXC_BROWSER_TOKEN=WEB_OLD_TOKEN\n")
                
                config_data = {"browser_token_mexc": "WEB_OLD_CONFIG_TOKEN"}
                with open("config_live_persistent.json", "w") as f:
                    json.dump(config_data, f)
                
                # 3. Synchronisation
                syncer = MEXCTokenSyncer()
                sync_success = syncer.sync()
                assert sync_success is True
                
                # 4. Validation
                validator = MEXCTokenValidator()
                validation_success = validator.validate_all()
                assert validation_success is True
                
                # 5. Vérifier résultats finaux
                with open(".env", "r") as f:
                    assert "MEXC_BROWSER_TOKEN=WEB123workflow" in f.read()
                
                with open("config_live_persistent.json", "r") as f:
                    config = json.load(f)
                    assert config["browser_token_mexc"] == "WEB123workflow"
                    
            finally:
                os.chdir(original_cwd)


# Tests de régression pour éviter les problèmes futurs
class TestMEXCRegressionPrevention:
    """Tests pour éviter les régressions du problème original"""
    
    def test_token_paths_consistency(self):
        """Test que tous les scripts utilisent les mêmes chemins"""
        # Vérifier que sync_mexc_token cherche dans tools/
        syncer = MEXCTokenSyncer()
        assert syncer.token_file == "tools/mexc_tokens.json"
        
        # Vérifier que validator utilise les mêmes chemins
        validator = MEXCTokenValidator()
        assert validator.token_file == "tools/mexc_tokens.json"
        assert validator.env_file == ".env"
        assert validator.config_file == "config_live_persistent.json"
    
    @patch('sys.argv', ['script.py', '--fix'])
    def test_validator_fix_suggestion(self, capsys):
        """Test que le validator suggère les bonnes commandes de fix"""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                from tools.validate_mexc_tokens import main
                
                # Lancer la validation avec des fichiers manquants
                exit_code = main()
                
                assert exit_code == 1  # Échec attendu
                
                captured = capsys.readouterr()
                assert "python tools/mexc_token_extractor.py once" in captured.out
                assert "python tools/sync_mexc_token.py" in captured.out
                
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Tests pour le module d'authentification API (api/auth.py)
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from api.auth import (
    load_api_keys,
    verify_api_key,
    verify_api_key_optional,
    require_role,
    generate_api_key
)


class TestLoadApiKeys:
    """Tests pour la fonction load_api_keys"""

    def test_load_api_keys_from_env(self):
        """Test chargement clés depuis variable d'environnement"""
        with patch.dict(os.environ, {'API_KEYS': 'key1:admin:admin,key2:user:user'}):
            keys = load_api_keys()

            assert 'key1' in keys
            assert keys['key1']['name'] == 'admin'
            assert 'admin' in keys['key1']['roles']

            assert 'key2' in keys
            assert keys['key2']['name'] == 'user'
            assert 'user' in keys['key2']['roles']

    def test_load_api_keys_default_key(self):
        """Test génération clé par défaut si aucune clé configurée"""
        with patch.dict(os.environ, {'DEFAULT_API_KEY': 'test_default_key'}, clear=True):
            keys = load_api_keys()

            assert 'test_default_key' in keys
            assert keys['test_default_key']['name'] == 'default'
            assert 'admin' in keys['test_default_key']['roles']

    def test_load_api_keys_auto_generate(self):
        """Test génération automatique si aucune configuration"""
        with patch.dict(os.environ, {}, clear=True):
            with patch('api.auth.logger') as mock_logger:
                keys = load_api_keys()

                assert len(keys) == 1
                # Vérifier qu'un avertissement a été loggé
                assert mock_logger.warning.called

                # Récupérer la clé générée
                generated_key = list(keys.keys())[0]
                assert keys[generated_key]['name'] == 'default'
                assert 'admin' in keys[generated_key]['roles']

    def test_load_api_keys_multiple_roles(self):
        """Test parsing de plusieurs rôles"""
        with patch.dict(os.environ, {'API_KEYS': 'key1:superadmin:admin:user:readonly'}):
            keys = load_api_keys()

            assert 'key1' in keys
            assert keys['key1']['name'] == 'superadmin'
            assert 'admin' in keys['key1']['roles']
            assert 'user' in keys['key1']['roles']
            assert 'readonly' in keys['key1']['roles']

    def test_load_api_keys_minimal_format(self):
        """Test format minimal key:name"""
        with patch.dict(os.environ, {'API_KEYS': 'key1:testuser'}):
            keys = load_api_keys()

            assert 'key1' in keys
            assert keys['key1']['name'] == 'testuser'
            # Devrait avoir le rôle par défaut 'user'
            assert 'user' in keys['key1']['roles']


class TestVerifyApiKey:
    """Tests pour la fonction verify_api_key"""

    @pytest.mark.asyncio
    async def test_verify_api_key_valid(self):
        """Test vérification avec clé valide"""
        with patch.dict(os.environ, {'API_KEYS': 'valid_key:admin:admin'}):
            # Recharger les clés
            import api.auth
            api.auth.API_KEYS = load_api_keys()

            result = await verify_api_key('valid_key')

            assert result['name'] == 'admin'
            assert 'admin' in result['roles']

    @pytest.mark.asyncio
    async def test_verify_api_key_missing(self):
        """Test vérification sans clé (None)"""
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(None)

        assert exc_info.value.status_code == 403
        assert "manquante" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self):
        """Test vérification avec clé invalide"""
        with patch.dict(os.environ, {'API_KEYS': 'valid_key:admin:admin'}):
            # Recharger les clés
            import api.auth
            api.auth.API_KEYS = load_api_keys()

            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key('invalid_key')

            assert exc_info.value.status_code == 403
            assert "invalide" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_api_key_empty_string(self):
        """Test vérification avec chaîne vide"""
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key('')

        assert exc_info.value.status_code == 403


class TestVerifyApiKeyOptional:
    """Tests pour la fonction verify_api_key_optional"""

    @pytest.mark.asyncio
    async def test_verify_api_key_optional_valid(self):
        """Test vérification optionnelle avec clé valide"""
        with patch.dict(os.environ, {'API_KEYS': 'valid_key:admin:admin'}):
            # Recharger les clés
            import api.auth
            api.auth.API_KEYS = load_api_keys()

            result = await verify_api_key_optional('valid_key')

            assert result is not None
            assert result['name'] == 'admin'

    @pytest.mark.asyncio
    async def test_verify_api_key_optional_missing(self):
        """Test vérification optionnelle sans clé"""
        result = await verify_api_key_optional(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_verify_api_key_optional_invalid(self):
        """Test vérification optionnelle avec clé invalide"""
        with patch.dict(os.environ, {'API_KEYS': 'valid_key:admin:admin'}):
            # Recharger les clés
            import api.auth
            api.auth.API_KEYS = load_api_keys()

            result = await verify_api_key_optional('invalid_key')

            assert result is None


class TestRequireRole:
    """Tests pour la fonction require_role"""

    @pytest.mark.asyncio
    async def test_require_role_has_permission(self):
        """Test vérification rôle - utilisateur a le rôle requis"""
        user_data = {
            'name': 'admin',
            'roles': ['admin', 'user']
        }

        # Créer un mock asynchrone
        async def mock_verify():
            return user_data

        role_checker = require_role('admin')

        # Mock verify_api_key pour retourner user_data
        with patch('api.auth.verify_api_key', new=mock_verify):
            result = await role_checker(user_data)

            assert result == user_data

    @pytest.mark.asyncio
    async def test_require_role_missing_permission(self):
        """Test vérification rôle - utilisateur n'a pas le rôle requis"""
        user_data = {
            'name': 'user',
            'roles': ['user']
        }

        # Créer un mock asynchrone
        async def mock_verify():
            return user_data

        role_checker = require_role('admin')

        # Mock verify_api_key pour retourner user_data
        with patch('api.auth.verify_api_key', new=mock_verify):
            with pytest.raises(HTTPException) as exc_info:
                await role_checker(user_data)

            assert exc_info.value.status_code == 403
            assert "admin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_role_multiple_roles(self):
        """Test vérification rôle - utilisateur a plusieurs rôles"""
        user_data = {
            'name': 'superuser',
            'roles': ['user', 'moderator', 'admin']
        }

        # Créer un mock asynchrone
        async def mock_verify():
            return user_data

        role_checker = require_role('moderator')

        # Mock verify_api_key pour retourner user_data
        with patch('api.auth.verify_api_key', new=mock_verify):
            result = await role_checker(user_data)

            assert result == user_data

    @pytest.mark.asyncio
    async def test_require_role_empty_roles(self):
        """Test vérification rôle - utilisateur sans rôles"""
        user_data = {
            'name': 'noroles',
            'roles': []
        }

        # Créer un mock asynchrone
        async def mock_verify():
            return user_data

        role_checker = require_role('admin')

        # Mock verify_api_key pour retourner user_data
        with patch('api.auth.verify_api_key', new=mock_verify):
            with pytest.raises(HTTPException) as exc_info:
                await role_checker(user_data)

            assert exc_info.value.status_code == 403


class TestGenerateApiKey:
    """Tests pour la fonction generate_api_key"""

    def test_generate_api_key_length(self):
        """Test génération clé - vérifier longueur"""
        key = generate_api_key()

        # Les clés générées par secrets.token_urlsafe(32) ont généralement 43 caractères
        assert len(key) > 30
        assert len(key) < 50

    def test_generate_api_key_uniqueness(self):
        """Test génération clé - vérifier unicité"""
        key1 = generate_api_key()
        key2 = generate_api_key()

        assert key1 != key2

    def test_generate_api_key_format(self):
        """Test génération clé - vérifier format URL-safe"""
        key = generate_api_key()

        # Les clés générées doivent être URL-safe (alphanumériques + - et _)
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', key)

    def test_generate_api_key_multiple(self):
        """Test génération de plusieurs clés"""
        keys = [generate_api_key() for _ in range(10)]

        # Toutes les clés doivent être uniques
        assert len(keys) == len(set(keys))


class TestIntegrationAuth:
    """Tests d'intégration pour l'authentification"""

    @pytest.mark.asyncio
    async def test_full_auth_flow(self):
        """Test flux complet d'authentification"""
        # Configuration
        with patch.dict(os.environ, {'API_KEYS': 'test_key:testuser:user'}):
            # Recharger les clés
            import api.auth
            api.auth.API_KEYS = load_api_keys()

            # 1. Vérifier clé valide
            result = await verify_api_key('test_key')
            assert result['name'] == 'testuser'

            # 2. Vérifier clé invalide
            with pytest.raises(HTTPException):
                await verify_api_key('wrong_key')

            # 3. Vérifier rôle
            role_checker = require_role('user')
            async def mock_verify():
                return result
            with patch('api.auth.verify_api_key', new=mock_verify):
                user = await role_checker(result)
                assert user == result

            # 4. Vérifier rôle manquant
            role_checker_admin = require_role('admin')
            with patch('api.auth.verify_api_key', new=mock_verify):
                with pytest.raises(HTTPException):
                    await role_checker_admin(result)

    @pytest.mark.asyncio
    async def test_admin_vs_user_permissions(self):
        """Test différence permissions admin vs user"""
        # Admin
        with patch.dict(os.environ, {'API_KEYS': 'admin_key:admin:admin,user_key:user:user'}):
            import api.auth
            api.auth.API_KEYS = load_api_keys()

            # Admin peut accéder aux endpoints admin
            admin_result = await verify_api_key('admin_key')
            role_checker = require_role('admin')
            async def mock_verify_admin():
                return admin_result
            with patch('api.auth.verify_api_key', new=mock_verify_admin):
                assert await role_checker(admin_result) == admin_result

            # User ne peut pas accéder aux endpoints admin
            user_result = await verify_api_key('user_key')
            async def mock_verify_user():
                return user_result
            with patch('api.auth.verify_api_key', new=mock_verify_user):
                with pytest.raises(HTTPException) as exc_info:
                    await role_checker(user_result)
                assert exc_info.value.status_code == 403


# Tests de sécurité supplémentaires
class TestAuthSecurity:
    """Tests de sécurité pour l'authentification"""

    @pytest.mark.asyncio
    async def test_no_timing_attack_vulnerability(self):
        """Test protection contre attaques temporelles"""
        import time

        with patch.dict(os.environ, {'API_KEYS': 'valid_key:admin:admin'}):
            import api.auth
            api.auth.API_KEYS = load_api_keys()

            # Mesurer temps pour clé invalide
            start = time.time()
            try:
                await verify_api_key('invalid_key')
            except HTTPException:
                pass
            time_invalid = time.time() - start

            # Mesurer temps pour clé valide
            start = time.time()
            await verify_api_key('valid_key')
            time_valid = time.time() - start

            # Les temps devraient être similaires (pas de timing attack)
            # Note: Ce test est basique, des tests plus sophistiqués seraient nécessaires en production
            assert abs(time_valid - time_invalid) < 0.1

    def test_key_format_security(self):
        """Test format sécurisé des clés générées"""
        key = generate_api_key()

        # Vérifier qu'il n'y a pas de caractères dangereux
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '|', '`', '$', '(', ')']
        for char in dangerous_chars:
            assert char not in key

    @pytest.mark.asyncio
    async def test_api_key_case_sensitive(self):
        """Test que les clés sont sensibles à la casse"""
        with patch.dict(os.environ, {'API_KEYS': 'TestKey:admin:admin'}):
            import api.auth
            api.auth.API_KEYS = load_api_keys()

            # Clé correcte (avec majuscules)
            result = await verify_api_key('TestKey')
            assert result is not None

            # Clé avec mauvaise casse
            with pytest.raises(HTTPException):
                await verify_api_key('testkey')

            with pytest.raises(HTTPException):
                await verify_api_key('TESTKEY')

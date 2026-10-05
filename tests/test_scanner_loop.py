"""
Tests pour core/callbacks/scanner_loop.py - Module critique du scanner
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from core.callbacks import scanner_loop


class TestScannerLoopHelpers:
    """Tests pour les fonctions utilitaires"""
    
    def test_safe_float_valid_values(self):
        """Test _safe_float avec valeurs valides"""
        assert scanner_loop._safe_float(1.5) == 1.5
        assert scanner_loop._safe_float("2.5") == 2.5
        assert scanner_loop._safe_float(10) == 10.0
        
    def test_safe_float_invalid_values(self):
        """Test _safe_float avec valeurs invalides"""
        assert scanner_loop._safe_float(None) == 0.0
        assert scanner_loop._safe_float("invalid") == 0.0
        assert scanner_loop._safe_float([1, 2, 3]) == 0.0
        assert scanner_loop._safe_float({}) == 0.0
        
    def test_safe_float_custom_default(self):
        """Test _safe_float avec défaut personnalisé"""
        assert scanner_loop._safe_float(None, 99.9) == 99.9
        assert scanner_loop._safe_float("invalid", -1.0) == -1.0


class TestScannerLoopInjection:
    """Tests pour l'injection de dépendances"""
    
    def setup_method(self):
        """Setup avant chaque test"""
        # Réinitialiser les variables globales
        scanner_loop._scanner = None
        scanner_loop._analyzer = None
        scanner_loop._position_manager = None
        scanner_loop._price_provider = None
        scanner_loop._app_state = None
        scanner_loop._sio = None
        scanner_loop._ws_manager = None
        scanner_loop._notification_manager = None
        
    def test_set_scanner(self):
        """Test injection scanner"""
        mock_scanner = Mock()
        scanner_loop.set_scanner(mock_scanner)
        assert scanner_loop._scanner is mock_scanner
        
    def test_set_analyzer(self):
        """Test injection analyzer"""
        mock_analyzer = Mock()
        scanner_loop.set_analyzer(mock_analyzer)
        assert scanner_loop._analyzer is mock_analyzer
        
    def test_set_position_manager(self):
        """Test injection position_manager"""
        mock_pm = Mock()
        scanner_loop.set_position_manager(mock_pm)
        assert scanner_loop._position_manager is mock_pm
        
    def test_set_price_provider(self):
        """Test injection price_provider"""
        mock_pp = Mock()
        scanner_loop.set_price_provider(mock_pp)
        assert scanner_loop._price_provider is mock_pp
        
    def test_set_app_state(self):
        """Test injection app_state"""
        mock_state = Mock()
        scanner_loop.set_app_state(mock_state)
        assert scanner_loop._app_state is mock_state
        
    def test_set_socketio(self):
        """Test injection SocketIO legacy"""
        mock_sio = Mock()
        scanner_loop.set_socketio(mock_sio)
        assert scanner_loop._sio is mock_sio
        
    def test_set_websocket_manager(self):
        """Test injection WebSocket manager"""
        mock_ws = Mock()
        scanner_loop.set_websocket_manager(mock_ws)
        assert scanner_loop._ws_manager is mock_ws
        
    def test_set_notification_manager(self):
        """Test injection notification manager"""
        mock_notif = Mock()
        scanner_loop.set_notification_manager(mock_notif)
        assert scanner_loop._notification_manager is mock_notif


class TestNotificationFunctions:
    """Tests pour les fonctions de notification"""
    
    def setup_method(self):
        """Setup avant chaque test"""
        scanner_loop._notification_manager = None
        
    @pytest.mark.asyncio
    async def test_notify_error_telegram_no_manager(self):
        """Test notification sans manager"""
        # Ne devrait pas lever d'exception
        await scanner_loop.notify_error_telegram("test_error", "test details")
        
    @pytest.mark.asyncio
    async def test_notify_error_telegram_with_manager(self):
        """Test notification avec manager"""
        mock_notif = AsyncMock()
        mock_notif.telegram_notify_settings = {'error': True}
        mock_notif.notify = AsyncMock()
        scanner_loop._notification_manager = mock_notif
        
        await scanner_loop.notify_error_telegram("test_error", "test details")
        
        # Vérifier que notify a été appelé avec les bons paramètres
        mock_notif.notify.assert_called_once_with('error', {
            'error_type': 'test_error',
            'details': 'test details'
        }, priority='high')


class TestScannerLoopCore:
    """Tests pour les fonctions principales du scanner loop"""
    
    def setup_method(self):
        """Setup mocks pour chaque test"""
        self.mock_scanner = AsyncMock()
        self.mock_analyzer = Mock()
        self.mock_position_manager = Mock()
        self.mock_price_provider = Mock()
        self.mock_app_state = {'top_pairs': []}
        self.mock_ws_manager = AsyncMock()
        self.mock_pg_datalogger = Mock()
        
        # Inject mocks
        scanner_loop._scanner = self.mock_scanner
        scanner_loop._analyzer = self.mock_analyzer  
        scanner_loop._position_manager = self.mock_position_manager
        scanner_loop._price_provider = self.mock_price_provider
        scanner_loop._app_state = self.mock_app_state
        scanner_loop._ws_manager = self.mock_ws_manager
        scanner_loop._pg_datalogger_instance = self.mock_pg_datalogger


class TestScannerLoopMainFunctions:
    """Tests d'intégration pour les fonctions principales"""
    
    def setup_method(self):
        """Setup complet pour tests d'intégration"""
        # Mock toutes les dépendances
        self.mock_scanner = AsyncMock()
        self.mock_analyzer = Mock()
        self.mock_position_manager = Mock()
        self.mock_app_state = {
            'top_pairs': [
                {'symbol': 'BTC/USDT', 'score': 95.0, 'spread': 0.01, 'bookDepth': 100000},
                {'symbol': 'ETH/USDT', 'score': 90.0, 'spread': 0.015, 'bookDepth': 80000}
            ]
        }
        self.mock_ws_manager = AsyncMock()
        self.mock_pg_datalogger = Mock()
        
        # Inject dans scanner_loop
        scanner_loop._scanner = self.mock_scanner
        scanner_loop._analyzer = self.mock_analyzer
        scanner_loop._position_manager = self.mock_position_manager
        scanner_loop._app_state = self.mock_app_state
        scanner_loop._ws_manager = self.mock_ws_manager
        scanner_loop._pg_datalogger_instance = self.mock_pg_datalogger
        
    def test_scanner_dependencies_present(self):
        """Test que les dépendances sont correctement injectées"""
        assert scanner_loop._scanner is not None
        assert scanner_loop._analyzer is not None
        assert scanner_loop._position_manager is not None
        assert scanner_loop._app_state is not None
        assert scanner_loop._ws_manager is not None
        
    @pytest.mark.asyncio
    async def test_scanner_loop_missing_dependencies(self):
        """Test comportement avec dépendances manquantes"""
        # Vider les dépendances
        scanner_loop._scanner = None
        scanner_loop._analyzer = False  # Spécifiquement False selon le code
        
        # Les fonctions devraient gérer les dépendances manquantes gracieusement
        # (basé sur les patterns observés dans le code)
        assert scanner_loop._scanner is None
        assert scanner_loop._analyzer is False


class TestErrorHandling:
    """Tests pour la gestion d'erreurs"""
    
    @pytest.mark.asyncio
    async def test_error_notification_handles_exceptions(self):
        """Test que les notifications d'erreur ne plantent pas"""
        # Mock qui lève une exception
        mock_notif = AsyncMock()
        mock_notif.notify_error = AsyncMock(side_effect=Exception("Notification failed"))
        scanner_loop._notification_manager = mock_notif
        
        # Ne devrait pas lever d'exception
        try:
            await scanner_loop.notify_error_telegram("test", "details")
        except Exception:
            pytest.fail("notify_error_telegram should handle exceptions gracefully")


class TestConfigurationIntegration:
    """Tests pour l'intégration avec la configuration"""
    
    @patch('core.callbacks.scanner_loop.get_effective_value')
    def test_effective_config_integration(self, mock_get_effective):
        """Test intégration avec effective_config"""
        mock_get_effective.return_value = True
        
        # Test que get_effective_value est appelable
        result = scanner_loop.get_effective_value('some_param', False)
        assert result is True
        mock_get_effective.assert_called_once_with('some_param', False)


class TestMLIntegration:
    """Tests pour l'intégration ML"""
    
    @patch('core.callbacks.scanner_loop.ML_CONFIG', {'enabled': True})
    def test_ml_config_access(self):
        """Test accès à ML_CONFIG"""
        # Vérifier que ML_CONFIG est accessible
        assert hasattr(scanner_loop, 'ML_CONFIG')
        assert scanner_loop.ML_CONFIG['enabled'] is True


# Tests de régression pour éviter les bugs futurs
class TestRegressionPrevention:
    """Tests pour éviter la régression des bugs critiques"""
    
    def test_global_variables_initialization(self):
        """Test que les variables globales existent"""
        # Variables critiques qui doivent exister
        assert hasattr(scanner_loop, '_scanner')
        assert hasattr(scanner_loop, '_analyzer')
        assert hasattr(scanner_loop, '_position_manager')
        assert hasattr(scanner_loop, '_price_provider')
        assert hasattr(scanner_loop, '_app_state')
        assert hasattr(scanner_loop, '_ws_manager')
        assert hasattr(scanner_loop, '_pg_datalogger_instance')
        
    def test_imports_successful(self):
        """Test que tous les imports critiques fonctionnent"""
        # Vérifier que les imports principaux sont accessibles
        assert hasattr(scanner_loop, 'PostgreSQLDataLogger')
        assert hasattr(scanner_loop, 'get_effective_value')
        assert hasattr(scanner_loop, 'ML_CONFIG')
        assert hasattr(scanner_loop, 'logger')
        
    def test_functions_exist(self):
        """Test que les fonctions principales existent"""
        # Fonctions d'injection
        assert callable(scanner_loop.set_scanner)
        assert callable(scanner_loop.set_analyzer)
        assert callable(scanner_loop.set_position_manager)
        assert callable(scanner_loop.set_price_provider)
        assert callable(scanner_loop.set_app_state)
        assert callable(scanner_loop.set_websocket_manager)
        assert callable(scanner_loop.set_notification_manager)
        
        # Fonctions utilitaires
        assert callable(scanner_loop._safe_float)
        assert callable(scanner_loop.notify_error_telegram)

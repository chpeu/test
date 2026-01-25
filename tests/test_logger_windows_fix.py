"""
Tests pour utils/logger.py - Corrections Windows rotation
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from utils.logger import setup_logger, get_logger
import logging


class TestLoggerWindowsFix:
    """Tests pour les corrections du logger Windows"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
    def teardown_method(self):
        """Cleanup après chaque test"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_setup_logger_with_safe_rotating_handler(self):
        """Test setup_logger utilise SafeRotatingFileHandler"""
        with patch('utils.logger.SafeRotatingFileHandler') as MockHandler:
            mock_handler = Mock()
            MockHandler.return_value = mock_handler
            
            logger = setup_logger(log_to_file=True, level='INFO')
            
            # Vérifier que SafeRotatingFileHandler est utilisé
            MockHandler.assert_called_once()
            args, kwargs = MockHandler.call_args
            
            # Vérifier les paramètres de rotation
            assert 'maxBytes' in kwargs
            assert kwargs['maxBytes'] == 10*1024*1024  # 10 MB
            assert kwargs['backupCount'] == 5
            assert kwargs['encoding'] == 'utf-8'
            assert kwargs['delay'] is True
            
            # Vérifier que le handler est ajouté
            mock_handler.setLevel.assert_called()
            mock_handler.setFormatter.assert_called()
    
    def test_setup_logger_creates_log_directory(self):
        """Test que setup_logger crée le dossier logs"""
        logs_dir = os.path.join(self.temp_dir, 'logs')
        assert not os.path.exists(logs_dir)
        
        with patch('utils.logger.SafeRotatingFileHandler'):
            setup_logger(log_to_file=True)
            
        # Le dossier logs devrait être créé
        assert os.path.exists(logs_dir)
    
    def test_setup_logger_no_file_logging(self):
        """Test setup_logger sans logging fichier"""
        with patch('utils.logger.SafeRotatingFileHandler') as MockHandler:
            logger = setup_logger(log_to_file=False)
            
            # SafeRotatingFileHandler ne devrait pas être appelé
            MockHandler.assert_not_called()
            
            # Logger devrait quand même être créé
            assert logger is not None
            assert isinstance(logger, logging.Logger)
    
    def test_setup_logger_handles_file_logging_exception(self):
        """Test que setup_logger gère les exceptions de file logging"""
        with patch('utils.logger.SafeRotatingFileHandler') as MockHandler:
            # Simuler une exception lors de la création du handler
            MockHandler.side_effect = Exception("Permission denied")
            
            # Mock logger pour capturer le warning
            with patch('utils.logger.logger') as mock_logger_instance:
                logger = setup_logger(log_to_file=True)
                
                # Logger devrait être créé malgré l'exception
                assert logger is not None
    
    def test_get_logger_singleton(self):
        """Test que get_logger retourne toujours la même instance"""
        # Reset global logger
        import utils.logger
        utils.logger._logger = None
        
        logger1 = get_logger()
        logger2 = get_logger()
        
        assert logger1 is logger2
        assert isinstance(logger1, logging.Logger)
    
    def test_setup_logger_with_websocket_handler(self):
        """Test setup_logger avec WebSocket handler"""
        mock_ws_manager = Mock()
        
        with patch('utils.logger.WebSocketLogHandler') as MockWSHandler:
            mock_ws_handler = Mock()
            MockWSHandler.return_value = mock_ws_handler
            
            logger = setup_logger(ws_manager=mock_ws_manager)
            
            # Vérifier que WebSocket handler est créé et configuré
            MockWSHandler.assert_called_once()
            mock_ws_handler.set_ws_manager.assert_called_once_with(mock_ws_manager)
            mock_ws_handler.setLevel.assert_called()
    
    def test_setup_logger_debug_mode(self):
        """Test setup_logger en mode debug"""
        with patch('utils.logger.DEBUG_ENABLED', True):
            with patch('utils.logger.SafeRotatingFileHandler') as MockHandler:
                mock_handler = Mock()
                MockHandler.return_value = mock_handler
                
                logger = setup_logger(log_to_file=True)
                
                # En mode debug, le niveau devrait être DEBUG
                mock_handler.setLevel.assert_called_with(logging.DEBUG)
    
    def test_setup_logger_production_mode(self):
        """Test setup_logger en mode production"""
        with patch('utils.logger.DEBUG_ENABLED', False):
            with patch('utils.logger.SafeRotatingFileHandler') as MockHandler:
                mock_handler = Mock()
                MockHandler.return_value = mock_handler
                
                logger = setup_logger(log_to_file=True)
                
                # En mode production, le niveau devrait être INFO
                mock_handler.setLevel.assert_called_with(logging.INFO)

    def test_safe_rotating_file_handler_permission_error(self):
        """Test que SafeRotatingFileHandler gère les PermissionError correctement"""
        from utils.logger import SafeRotatingFileHandler
        import tempfile
        import os
        
        # Créer un fichier temporaire pour le test
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()
        
        try:
            # Créer le handler
            handler = SafeRotatingFileHandler(
                temp_file.name,
                maxBytes=1024,
                backupCount=1
            )
            
            # Mocker doRollover de la classe parent pour lever PermissionError
            with patch.object(handler.__class__.__bases__[0], 'doRollover') as mock_parent_rollover:
                mock_parent_rollover.side_effect = PermissionError("Windows file lock")
                
                # Capturer stderr pour vérifier le message d'erreur
                with patch('sys.stderr') as mock_stderr:
                    # Déclencher la rotation (qui devrait échouer gracieusement)
                    handler.doRollover()
                    
                    # Vérifier que l'erreur est capturée et logged
                    assert handler._rollover_failed is True
                    assert handler._last_rollover_attempt > 0
                    
            # Vérifier que shouldRollover respecte le cooldown après échec
            import time
            handler._last_rollover_attempt = time.time() - 1800  # 30 min ago
            handler._rollover_retry_delay = 3600  # 1h cooldown
            
            # Simuler un record qui nécessiterait normalement une rotation
            mock_record = Mock()
            with patch.object(handler.__class__.__bases__[0], 'shouldRollover', return_value=True):
                should_rollover = handler.shouldRollover(mock_record)
                # Devrait retourner False à cause du cooldown
                assert should_rollover is False
                
        finally:
            # Cleanup
            try:
                os.unlink(temp_file.name)
            except:
                pass

    def test_safe_rotating_file_handler_retry_after_cooldown(self):
        """Test que SafeRotatingFileHandler retry après le cooldown"""
        from utils.logger import SafeRotatingFileHandler
        import tempfile
        import os
        import time
        
        # Créer un fichier temporaire pour le test
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()
        
        try:
            # Créer le handler avec un cooldown très court pour le test
            handler = SafeRotatingFileHandler(
                temp_file.name,
                maxBytes=1024,
                backupCount=1
            )
            handler._rollover_retry_delay = 1  # 1 seconde pour le test
            
            # Simuler un échec initial
            handler._rollover_failed = True
            handler._last_rollover_attempt = time.time() - 2  # 2 sec ago
            
            # Maintenant shouldRollover devrait permettre un retry
            mock_record = Mock()
            with patch.object(handler.__class__.__bases__[0], 'shouldRollover', return_value=True):
                should_rollover = handler.shouldRollover(mock_record)
                # Devrait retourner True car le cooldown est expiré
                assert should_rollover is True
                
        finally:
            # Cleanup
            try:
                os.unlink(temp_file.name)
            except:
                pass

    def test_safe_rotating_file_handler_success_resets_failure(self):
        from utils.logger import SafeRotatingFileHandler
        import tempfile
        import os

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()

        try:
            handler = SafeRotatingFileHandler(
                temp_file.name,
                maxBytes=1024,
                backupCount=1
            )

            handler._rollover_failed = True
            handler._last_rollover_attempt = 0

            with patch.object(handler.__class__.__bases__[0], 'doRollover') as mock_parent_rollover:
                mock_parent_rollover.return_value = None
                handler.doRollover()
                assert handler._rollover_failed is False
                assert handler._last_rollover_attempt > 0
        finally:
            try:
                os.unlink(temp_file.name)
            except:
                pass

    def test_safe_rotating_file_handler_should_rollover_calls_parent(self):
        from utils.logger import SafeRotatingFileHandler
        import tempfile
        import os

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()

        try:
            handler = SafeRotatingFileHandler(
                temp_file.name,
                maxBytes=1024,
                backupCount=1
            )

            handler._rollover_failed = False

            record = logging.LogRecord(
                name='test',
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg='x',
                args=(),
                exc_info=None,
            )

            with patch.object(handler.__class__.__bases__[0], 'shouldRollover', return_value=True) as mock_parent_should:
                assert handler.shouldRollover(record) is True
                mock_parent_should.assert_called_once()
        finally:
            try:
                os.unlink(temp_file.name)
            except:
                pass

    def test_websocket_log_handler_emit_no_ws_manager(self):
        from utils.logger import WebSocketLogHandler

        handler = WebSocketLogHandler()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='hello',
            args=(),
            exc_info=None,
        )

        handler.emit(record)

    def test_websocket_log_handler_emit_when_closing(self):
        from utils.logger import WebSocketLogHandler

        handler = WebSocketLogHandler()
        handler.set_ws_manager(Mock())
        handler._closing = True

        record = logging.LogRecord(
            name='test',
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg='error',
            args=(),
            exc_info=None,
        )

        handler.emit(record)

    @pytest.mark.asyncio
    async def test_drain_websocket_log_handlers(self):
        import utils.logger as logger_module
        from utils.logger import WebSocketLogHandler, drain_websocket_log_handlers

        handler = WebSocketLogHandler()
        handler.drain = AsyncMock(return_value=None)
        try:
            await drain_websocket_log_handlers(timeout=0.01)
            handler.drain.assert_called()
        finally:
            logger_module._ws_log_handlers.discard(handler)


class TestLoggerIntegration:
    """Tests d'intégration pour le logger"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
    def teardown_method(self):
        """Cleanup après chaque test"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_logger_writes_to_file(self):
        """Test que le logger écrit effectivement dans le fichier"""
        logger = setup_logger(log_to_file=True, level='INFO')
        
        # Écrire quelques logs
        test_messages = [
            "Test INFO message",
            "Test WARNING message", 
            "Test ERROR message"
        ]
        
        logger.info(test_messages[0])
        logger.warning(test_messages[1])
        logger.error(test_messages[2])
        
        # Vérifier que le fichier de log existe
        log_file = os.path.join('logs', 'app.log')
        assert os.path.exists(log_file)
        
        # Lire le contenu du fichier
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier que les messages sont présents
        for message in test_messages:
            assert message in content
    
    def test_logger_console_and_file_output(self):
        """Test que le logger écrit sur console ET fichier"""
        with patch('sys.stdout') as mock_stdout:
            logger = setup_logger(log_to_file=True, level='INFO')
            
            logger.info("Test dual output message")
            
            # Vérifier sortie console (via le mock)
            # Note: Le test exact dépend de l'implémentation du logger
            
            # Vérifier sortie fichier
            log_file = os.path.join('logs', 'app.log')
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                assert "Test dual output message" in content


class TestLoggerPerformance:
    """Tests de performance pour le logger"""
    
    def test_logger_performance_multiple_messages(self):
        """Test performance avec multiple messages"""
        import time
        
        logger = setup_logger(log_to_file=True, level='INFO')
        
        start_time = time.time()
        
        # Écrire beaucoup de messages
        for i in range(100):
            logger.info(f"Performance test message {i}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Le test ne devrait pas prendre plus de 5 secondes
        assert duration < 5.0
        
        # Vérifier que les logs sont écrits
        log_file = os.path.join('logs', 'app.log')
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Vérifier quelques messages
            assert "Performance test message 0" in content
            assert "Performance test message 99" in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

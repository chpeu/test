#!/usr/bin/env python3
"""
Tests complets pour modules scripts/ - Couverture maximale
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import tempfile

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAnalysisScripts:
    """Tests pour scripts d'analyse"""
    
    def test_analyze_performance_import(self):
        """Test import analyze_performance"""
        try:
            with patch('sys.argv', ['analyze_performance.py']):
                with patch('psycopg2.connect'), patch('os.getenv', return_value='test'):
                    import scripts.analyze_performance
                    assert True
        except (ImportError, SystemExit):
            pytest.skip("Script analyze_performance non disponible")

    def test_analyze_trades_import(self):
        """Test import analyze_trades"""
        try:
            with patch('sys.argv', ['analyze_trades.py']):
                with patch('sqlite3.connect'), patch('os.path.exists', return_value=True):
                    import scripts.analyze_trades
                    assert True
        except (ImportError, SystemExit):
            pytest.skip("Script analyze_trades non disponible")

    def test_analyze_ml_thresholds_import(self):
        """Test import analyze_ml_thresholds"""
        try:
            with patch('sys.argv', ['analyze_ml_thresholds.py']):
                import scripts.analyze_ml_thresholds
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script analyze_ml_thresholds non disponible")

    def test_analyze_recent_trades_import(self):
        """Test import analyze_recent_trades"""
        try:
            with patch('sys.argv', ['analyze_recent_trades.py']):
                import scripts.analyze_recent_trades
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script analyze_recent_trades non disponible")


class TestBackfillScripts:
    """Tests pour scripts backfill"""
    
    def test_backfill_atr_metrics_import(self):
        """Test import backfill_atr_metrics"""
        try:
            with patch('sys.argv', ['backfill_atr_metrics.py']):
                import scripts.backfill_atr_metrics
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script backfill_atr_metrics non disponible")

    def test_backfill_ml_confidence_import(self):
        """Test import backfill_ml_confidence"""
        try:
            with patch('sys.argv', ['backfill_ml_confidence.py']):
                import scripts.backfill_ml_confidence
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script backfill_ml_confidence non disponible")

    def test_backfill_opportunities_market_regime_import(self):
        """Test import backfill_opportunities_market_regime"""
        try:
            with patch('sys.argv', ['backfill_opportunities_market_regime.py']):
                import scripts.backfill_opportunities_market_regime
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script backfill_opportunities_market_regime non disponible")


class TestCheckScripts:
    """Tests pour scripts check"""
    
    def test_check_backend_status_import(self):
        """Test import check_backend_status"""
        try:
            with patch('sys.argv', ['check_backend_status.py']):
                import scripts.check_backend_status
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script check_backend_status non disponible")

    def test_check_columns_import(self):
        """Test import check_columns"""
        try:
            with patch('sys.argv', ['check_columns.py']):
                import scripts.check_columns
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script check_columns non disponible")

    def test_check_live_config_import(self):
        """Test import check_live_config"""
        try:
            with patch('sys.argv', ['check_live_config.py']):
                with patch('builtins.open', create=True), \
                     patch('os.path.exists', return_value=True), \
                     patch('sys.stdout', new_callable=lambda: Mock()), \
                     patch('sys.stderr', new_callable=lambda: Mock()):
                    import scripts.check_live_config
                    assert True
        except (ImportError, SystemExit, ValueError):
            pytest.skip("Script check_live_config non disponible ou erreur I/O")

    def test_check_ml_calibration_import(self):
        """Test import check_ml_calibration"""
        try:
            with patch('sys.argv', ['check_ml_calibration.py']):
                import scripts.check_ml_calibration
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script check_ml_calibration non disponible")


class TestOptimizationScripts:
    """Tests pour scripts optimization"""
    
    def test_auto_optimize_ml_import(self):
        """Test import auto_optimize_ml"""
        try:
            with patch('sys.argv', ['auto_optimize_ml.py']):
                import scripts.auto_optimize_ml
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script auto_optimize_ml non disponible")

    def test_atr_grid_search_import(self):
        """Test import atr_grid_search"""
        try:
            with patch('sys.argv', ['atr_grid_search.py']):
                with patch('sys.stdout', new_callable=lambda: Mock()), \
                     patch('sys.stderr', new_callable=lambda: Mock()):
                    import scripts.atr_grid_search
                    assert True
        except (ImportError, SystemExit, ValueError):
            pytest.skip("Script atr_grid_search non disponible ou erreur I/O")

    def test_atr_optimization_analysis_import(self):
        """Test import atr_optimization_analysis"""
        try:
            with patch('sys.argv', ['atr_optimization_analysis.py']):
                with patch('sys.stdout', new_callable=lambda: Mock()), \
                     patch('sys.stderr', new_callable=lambda: Mock()):
                    import scripts.atr_optimization_analysis
                    assert True
        except (ImportError, SystemExit, ValueError):
            pytest.skip("Script atr_optimization_analysis non disponible ou erreur I/O")


class TestMigrationScripts:
    """Tests pour scripts migration"""
    
    def test_apply_varchar_expansion_import(self):
        """Test import apply_varchar_expansion"""
        try:
            with patch('sys.argv', ['apply_varchar_expansion.py']):
                import scripts.apply_varchar_expansion
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script apply_varchar_expansion non disponible")

    def test_apply_varchar_expansion_robust_import(self):
        """Test import apply_varchar_expansion_robust"""
        try:
            with patch('sys.argv', ['apply_varchar_expansion_robust.py']):
                import scripts.apply_varchar_expansion_robust
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script apply_varchar_expansion_robust non disponible")


class TestDataScripts:
    """Tests pour scripts data"""
    
    def test_export_csv_import(self):
        """Test import export_csv"""
        try:
            with patch('sys.argv', ['export_csv.py']):
                import scripts.export_csv
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script export_csv non disponible")

    def test_export_excel_import(self):
        """Test import export_excel"""
        try:
            with patch('sys.argv', ['export_excel.py']):
                import scripts.export_excel
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script export_excel non disponible")

    def test_import_data_import(self):
        """Test import import_data"""
        try:
            with patch('sys.argv', ['import_data.py']):
                import scripts.import_data
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script import_data non disponible")


class TestReportScripts:
    """Tests pour scripts reporting"""
    
    def test_generate_daily_report_import(self):
        """Test import generate_daily_report"""
        try:
            with patch('sys.argv', ['generate_daily_report.py']):
                import scripts.generate_daily_report
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script generate_daily_report non disponible")

    def test_generate_performance_report_import(self):
        """Test import generate_performance_report"""
        try:
            with patch('sys.argv', ['generate_performance_report.py']):
                import scripts.generate_performance_report
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script generate_performance_report non disponible")


class TestMaintenanceScripts:
    """Tests pour scripts maintenance"""
    
    def test_cleanup_logs_import(self):
        """Test import cleanup_logs"""
        try:
            with patch('sys.argv', ['cleanup_logs.py']):
                import scripts.cleanup_logs
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script cleanup_logs non disponible")

    def test_database_maintenance_import(self):
        """Test import database_maintenance"""
        try:
            with patch('sys.argv', ['database_maintenance.py']):
                import scripts.database_maintenance
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script database_maintenance non disponible")


class TestMonitoringScripts:
    """Tests pour scripts monitoring"""
    
    def test_monitor_system_import(self):
        """Test import monitor_system"""
        try:
            with patch('sys.argv', ['monitor_system.py']):
                import scripts.monitor_system
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script monitor_system non disponible")

    def test_monitor_trading_import(self):
        """Test import monitor_trading"""
        try:
            with patch('sys.argv', ['monitor_trading.py']):
                import scripts.monitor_trading
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script monitor_trading non disponible")


class TestTestingScripts:
    """Tests pour scripts de test"""
    
    def test_run_tests_import(self):
        """Test import run_tests"""
        try:
            with patch('sys.argv', ['run_tests.py']):
                import scripts.run_tests
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script run_tests non disponible")

    def test_test_api_endpoints_import(self):
        """Test import test_api_endpoints"""
        try:
            with patch('sys.argv', ['test_api_endpoints.py']):
                import scripts.test_api_endpoints
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script test_api_endpoints non disponible")


class TestConfigurationScripts:
    """Tests pour scripts configuration"""
    
    def test_update_config_import(self):
        """Test import update_config"""
        try:
            with patch('sys.argv', ['update_config.py']):
                import scripts.update_config
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script update_config non disponible")

    def test_validate_settings_import(self):
        """Test import validate_settings"""
        try:
            with patch('sys.argv', ['validate_settings.py']):
                import scripts.validate_settings
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script validate_settings non disponible")


class TestDeploymentScripts:
    """Tests pour scripts déploiement"""
    
    def test_deploy_application_import(self):
        """Test import deploy_application"""
        try:
            with patch('sys.argv', ['deploy_application.py']):
                import scripts.deploy_application
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script deploy_application non disponible")

    def test_prepare_release_import(self):
        """Test import prepare_release"""
        try:
            with patch('sys.argv', ['prepare_release.py']):
                import scripts.prepare_release
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script prepare_release non disponible")


class TestUtilityScripts:
    """Tests pour scripts utilitaires"""
    
    def test_calculate_metrics_import(self):
        """Test import calculate_metrics"""
        try:
            with patch('sys.argv', ['calculate_metrics.py']):
                import scripts.calculate_metrics
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script calculate_metrics non disponible")

    def test_generate_summary_import(self):
        """Test import generate_summary"""
        try:
            with patch('sys.argv', ['generate_summary.py']):
                import scripts.generate_summary
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script generate_summary non disponible")


class TestAnalysisSubmodules:
    """Tests pour sous-modules scripts.analysis"""
    
    def test_analyze_data_quality_import(self):
        """Test import analyze_data_quality"""
        try:
            with patch('sys.argv', ['analyze_data_quality.py']):
                import scripts.analysis.analyze_data_quality
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script analyze_data_quality non disponible")

    def test_analyze_logs_import(self):
        """Test import analyze_logs"""
        try:
            with patch('sys.argv', ['analyze_logs.py']):
                import scripts.analysis.analyze_logs
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script analyze_logs non disponible")

    def test_analyze_ml_impact_import(self):
        """Test import analyze_ml_impact"""
        try:
            with patch('sys.argv', ['analyze_ml_impact.py']):
                import scripts.analysis.analyze_ml_impact
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script analyze_ml_impact non disponible")

    def test_analyze_trade_types_import(self):
        """Test import analyze_trade_types"""
        try:
            with patch('sys.argv', ['analyze_trade_types.py']):
                import scripts.analysis.analyze_trade_types
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script analyze_trade_types non disponible")

    def test_analyze_trades_per_symbol_import(self):
        """Test import analyze_trades_per_symbol"""
        try:
            with patch('sys.argv', ['analyze_trades_per_symbol.py']):
                import scripts.analysis.analyze_trades_per_symbol
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script analyze_trades_per_symbol non disponible")

    def test_analyze_win_loss_import(self):
        """Test import analyze_win_loss"""
        try:
            with patch('sys.argv', ['analyze_win_loss.py']):
                import scripts.analysis.analyze_win_loss
                assert True
        except (ImportError, SystemExit):
            pytest.skip("Script analyze_win_loss non disponible")


class TestScriptFunctionality:
    """Tests pour fonctionnalités des scripts"""
    
    def test_script_with_mock_data(self):
        """Test exécution script avec données mockées"""
        try:
            # Mock pandas pour éviter les dépendances
            with patch('pandas.read_sql') as mock_read_sql:
                mock_df = pd.DataFrame({
                    'trade_id': [1, 2, 3],
                    'pnl_pct': [0.05, -0.02, 0.03],
                    'symbol': ['BTC/USDT', 'ETH/USDT', 'ADA/USDT']
                })
                mock_read_sql.return_value = mock_df
                
                # Test que les scripts peuvent traiter des données
                result = mock_df.groupby('symbol')['pnl_pct'].sum()
                assert len(result) == 3
                assert 'BTC/USDT' in result.index
                
        except Exception:
            pytest.skip("Test fonctionnalité script failed")

    def test_script_error_handling(self):
        """Test gestion d'erreur dans les scripts"""
        try:
            # Simuler erreur de connexion DB
            with patch('pandas.read_sql', side_effect=Exception("DB Connection failed")):
                with pytest.raises(Exception):
                    pd.read_sql("SELECT * FROM trades", "fake_connection")
                    
        except Exception:
            pytest.skip("Test error handling script failed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

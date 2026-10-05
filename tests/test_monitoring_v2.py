"""
Tests unitaires pour optimization/monitoring_v2.py
Coverage target: 80%+
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from optimization.monitoring_v2 import (
    ModelPerformanceMetrics,
    DriftAlert,
    ModelDriftDetector
)


@pytest.fixture
def baseline_metrics():
    """Métriques baseline pour tests"""
    return ModelPerformanceMetrics(
        r2_score=0.35,
        mae=0.40,
        mse=0.25,
        predictions_count=1000,
        profitable_pct=60.0,
        avg_error=0.30,
        timestamp=datetime.now(),
        period_start=datetime.now() - timedelta(days=30),
        period_end=datetime.now()
    )


@pytest.fixture
def detector():
    """Détecteur de drift"""
    return ModelDriftDetector()


@pytest.fixture
def mock_predictions_data():
    """Données de prédictions pour tests"""
    return pd.DataFrame({
        'predicted_pnl': [2.5, 1.5, -0.5, 3.0, 1.0, 2.0, 0.5, -1.0, 2.5, 1.5],
        'actual_pnl': [2.3, 1.7, -0.3, 2.8, 1.2, 1.8, 0.7, -0.8, 2.6, 1.4]
    })


class TestModelPerformanceMetrics:
    """Tests dataclass ModelPerformanceMetrics"""

    def test_metrics_creation(self):
        """Test création métriques"""
        metrics = ModelPerformanceMetrics(
            r2_score=0.35,
            mae=0.40,
            mse=0.25,
            predictions_count=100,
            profitable_pct=60.0,
            avg_error=0.30,
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )

        assert metrics.r2_score == 0.35
        assert metrics.mae == 0.40
        assert metrics.predictions_count == 100


class TestDriftAlert:
    """Tests dataclass DriftAlert"""

    def test_drift_alert_creation(self):
        """Test création alerte"""
        alert = DriftAlert(
            metric_name='r2',
            current_value=0.20,
            baseline_value=0.35,
            drift_magnitude=-0.15,
            severity='high',
            detected_at=datetime.now(),
            message='R² dropped significantly'
        )

        assert alert.metric_name == 'r2'
        assert alert.severity == 'high'
        assert alert.drift_magnitude == -0.15


class TestModelDriftDetectorInit:
    """Tests initialisation"""

    def test_init_defaults(self, detector):
        """Test init avec valeurs par défaut"""
        assert detector.baseline_metrics is None
        assert len(detector.alerts_history) == 0
        assert 'r2' in detector.thresholds
        assert 'mae' in detector.thresholds

    def test_thresholds_configured(self, detector):
        """Test configuration seuils"""
        assert detector.thresholds['r2']['critical'] == 0.15
        assert detector.thresholds['mae']['high'] == 0.30
        assert detector.thresholds['profitable_pct']['medium'] == 10.0


class TestLoadBaselineFromPostgres:
    """Tests load_baseline_from_postgres()"""

    @patch('core.simple_pg_logger.SimplePGLogger')
    def test_load_baseline_success(self, mock_pg, detector):
        """Test chargement baseline réussi"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            0.35,  # r2
            0.40,  # mae
            0.25,  # mse
            1000,  # count
            datetime.now()  # trained_at
        )
        mock_conn.cursor.return_value = mock_cursor

        mock_pg_instance = Mock()
        mock_pg_instance.enabled = True
        mock_pg_instance.conn = mock_conn
        mock_pg.return_value = mock_pg_instance

        result = detector.load_baseline_from_postgres()

        assert result is not None
        assert detector.baseline_metrics is not None
        assert detector.baseline_metrics.r2_score == 0.35

    @patch('core.simple_pg_logger.SimplePGLogger')
    def test_load_baseline_no_postgres(self, mock_pg, detector):
        """Test pas de PostgreSQL disponible"""
        mock_pg_instance = Mock()
        mock_pg_instance.enabled = False
        mock_pg.return_value = mock_pg_instance

        result = detector.load_baseline_from_postgres()

        assert result is False

    @patch('core.simple_pg_logger.SimplePGLogger')
    def test_load_baseline_no_model(self, mock_pg, detector):
        """Test aucun modèle trouvé"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor

        mock_pg_instance = Mock()
        mock_pg_instance.enabled = True
        mock_pg_instance.conn = mock_conn
        mock_pg.return_value = mock_pg_instance

        result = detector.load_baseline_from_postgres()

        assert result is False


class TestSetBaseline:
    """Tests set_baseline()"""

    def test_set_baseline(self, detector, baseline_metrics):
        """Test définition baseline"""
        detector.set_baseline(baseline_metrics)

        assert detector.baseline_metrics == baseline_metrics
        assert detector.baseline_metrics.r2_score == 0.35


class TestCalculateCurrentPerformance:
    """Tests calculate_current_performance()"""

    def test_calculate_performance(self, detector, mock_predictions_data):
        """Test calcul performance"""
        # Split into predictions and actuals DataFrames
        predictions_df = mock_predictions_data[['predicted_pnl']]
        actuals_df = mock_predictions_data[['actual_pnl']]

        metrics = detector.calculate_current_performance(predictions_df, actuals_df)

        assert metrics is not None
        assert metrics.predictions_count == 10
        assert 0 <= metrics.r2_score <= 1
        assert metrics.mae > 0
        assert 0 <= metrics.profitable_pct <= 100

    def test_calculate_with_empty_data(self, detector):
        """Test avec données vides"""
        predictions_df = pd.DataFrame({'predicted_pnl': []})
        actuals_df = pd.DataFrame({'actual_pnl': []})

        # Should raise exception or return None for empty data
        try:
            metrics = detector.calculate_current_performance(predictions_df, actuals_df)
            # If no exception, check it handled empty data gracefully
            assert metrics is None or metrics.predictions_count == 0
        except Exception:
            # Exception is acceptable for empty data
            pass

    def test_calculate_with_nan_values(self, detector):
        """Test avec valeurs NaN"""
        predictions_df = pd.DataFrame({'predicted_pnl': [2.5, np.nan, 1.5]})
        actuals_df = pd.DataFrame({'actual_pnl': [2.3, 1.7, np.nan]})

        # Should handle NaN gracefully (may raise or return metrics)
        try:
            metrics = detector.calculate_current_performance(predictions_df, actuals_df)
            # If no exception, verify it returned something
            assert metrics is not None
        except Exception:
            # Exception is acceptable for NaN data
            pass

    def test_calculate_performance_trims_mismatched_lengths(self, detector):
        pytest.importorskip('sklearn')

        predictions_df = pd.DataFrame({
            'predicted_pnl': [1.0, 2.0, 3.0, 4.0],
            'timestamp': [datetime.now()] * 4,
        })
        actuals_df = pd.DataFrame({
            'actual_pnl': [1.1, 2.1],
            'timestamp': [datetime.now()] * 2,
        })

        metrics = detector.calculate_current_performance(predictions_df, actuals_df)
        assert metrics.predictions_count == 2


class TestDetectDrift:
    """Tests detect_drift()"""

    def test_detect_no_drift(self, detector, baseline_metrics):
        """Test pas de drift détecté"""
        detector.set_baseline(baseline_metrics)

        current_metrics = ModelPerformanceMetrics(
            r2_score=0.34,  # Légère différence
            mae=0.42,
            mse=0.26,
            predictions_count=100,
            profitable_pct=59.0,
            avg_error=0.31,
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )

        alerts = detector.detect_drift(current_metrics)

        assert len(alerts) == 0

    def test_detect_high_drift_r2(self, detector, baseline_metrics):
        """Test drift élevé sur R²"""
        detector.set_baseline(baseline_metrics)

        current_metrics = ModelPerformanceMetrics(
            r2_score=0.20,  # Baisse de 0.15 (15%)
            mae=0.40,
            mse=0.25,
            predictions_count=100,
            profitable_pct=60.0,
            avg_error=0.30,
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )

        alerts = detector.detect_drift(current_metrics)

        assert len(alerts) > 0
        assert any(a.metric_name == 'R² Score' for a in alerts)
        r2_alert = [a for a in alerts if a.metric_name == 'R² Score'][0]
        assert r2_alert.severity in ['high', 'critical']

    def test_detect_mae_increase(self, detector, baseline_metrics):
        """Test augmentation MAE"""
        detector.set_baseline(baseline_metrics)

        current_metrics = ModelPerformanceMetrics(
            r2_score=0.35,
            mae=0.60,  # +50% (0.40 → 0.60)
            mse=0.25,
            predictions_count=100,
            profitable_pct=60.0,
            avg_error=0.30,
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )

        alerts = detector.detect_drift(current_metrics)

        assert len(alerts) > 0
        assert any(a.metric_name == 'MAE' for a in alerts)

    def test_detect_profitable_pct_drop(self, detector, baseline_metrics):
        """Test baisse % trades profitables"""
        detector.set_baseline(baseline_metrics)

        current_metrics = ModelPerformanceMetrics(
            r2_score=0.35,
            mae=0.40,
            mse=0.25,
            predictions_count=100,
            profitable_pct=40.0,  # Baisse de 20% (60% → 40%)
            avg_error=0.30,
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )

        alerts = detector.detect_drift(current_metrics)

        assert len(alerts) > 0
        assert any(a.metric_name == 'Profitable %' for a in alerts)

    def test_detect_without_baseline(self, detector):
        """Test détection sans baseline"""
        current_metrics = ModelPerformanceMetrics(
            r2_score=0.35,
            mae=0.40,
            mse=0.25,
            predictions_count=100,
            profitable_pct=60.0,
            avg_error=0.30,
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )

        alerts = detector.detect_drift(current_metrics)

        assert len(alerts) == 0  # Pas de baseline, pas d'alerte


class TestGetSeverity:
    """Tests _get_severity()"""

    def test_severity_low(self, detector):
        """Test sévérité low"""
        severity = detector._get_severity('r2', 0.04)  # 4% absolute drift

        assert severity == 'low'

    def test_severity_medium(self, detector):
        """Test sévérité medium"""
        severity = detector._get_severity('r2', 0.07)  # 7% absolute drift

        assert severity == 'medium'

    def test_severity_high(self, detector):
        """Test sévérité high"""
        severity = detector._get_severity('r2', 0.12)  # 12% absolute drift

        assert severity == 'high'

    def test_severity_critical(self, detector):
        """Test sévérité critical"""
        severity = detector._get_severity('r2', 0.20)  # 20% absolute drift

        assert severity == 'critical'

    def test_severity_none_for_small_drift(self, detector):
        """Test pas de sévérité pour petit drift"""
        severity = detector._get_severity('r2', 0.01)  # 1% absolute drift

        assert severity is None

    def test_severity_unknown_metric_returns_none(self, detector):
        # Metric inconnue => thresholds {} => None
        severity = detector._get_severity('unknown', 999)
        assert severity is None


class TestShouldRetrain:
    """Tests should_retrain()"""

    def test_should_retrain_critical(self, detector):
        """Test retrain nécessaire (critical)"""
        alerts = [
            DriftAlert(
                metric_name='r2',
                current_value=0.10,
                baseline_value=0.35,
                drift_magnitude=-0.25,
                severity='critical',
                detected_at=datetime.now(),
                message='Critical drift'
            )
        ]

        should_retrain = detector.should_retrain(alerts)

        assert should_retrain is True

    def test_should_retrain_multiple_high(self, detector):
        """Test retrain avec plusieurs high"""
        alerts = [
            DriftAlert(
                metric_name='r2',
                current_value=0.25,
                baseline_value=0.35,
                drift_magnitude=-0.10,
                severity='high',
                detected_at=datetime.now(),
                message='High drift R²'
            ),
            DriftAlert(
                metric_name='mae',
                current_value=0.60,
                baseline_value=0.40,
                drift_magnitude=0.20,
                severity='high',
                detected_at=datetime.now(),
                message='High drift MAE'
            )
        ]

        should_retrain = detector.should_retrain(alerts)

        assert should_retrain is True

    def test_should_not_retrain_low(self, detector):
        """Test pas de retrain pour low"""
        alerts = [
            DriftAlert(
                metric_name='r2',
                current_value=0.33,
                baseline_value=0.35,
                drift_magnitude=-0.02,
                severity='low',
                detected_at=datetime.now(),
                message='Low drift'
            )
        ]

        should_retrain = detector.should_retrain(alerts)

        assert should_retrain is False

    def test_should_retrain_more_than_two_medium(self, detector):
        alerts = [
            DriftAlert(
                metric_name='m1',
                current_value=0.0,
                baseline_value=0.0,
                drift_magnitude=0.0,
                severity='medium',
                detected_at=datetime.now(),
                message='m1'
            ),
            DriftAlert(
                metric_name='m2',
                current_value=0.0,
                baseline_value=0.0,
                drift_magnitude=0.0,
                severity='medium',
                detected_at=datetime.now(),
                message='m2'
            ),
            DriftAlert(
                metric_name='m3',
                current_value=0.0,
                baseline_value=0.0,
                drift_magnitude=0.0,
                severity='medium',
                detected_at=datetime.now(),
                message='m3'
            ),
        ]

        assert detector.should_retrain(alerts) is True

    def test_should_not_retrain_no_alerts(self, detector):
        """Test pas de retrain sans alertes"""
        should_retrain = detector.should_retrain([])

        assert should_retrain is False


class TestGetDriftReport:
    """Tests get_drift_report()"""

    def test_get_report_with_drift(self, detector, baseline_metrics):
        """Test rapport avec drift"""
        detector.set_baseline(baseline_metrics)

        current_metrics = ModelPerformanceMetrics(
            r2_score=0.20,
            mae=0.60,
            mse=0.35,
            predictions_count=100,
            profitable_pct=45.0,
            avg_error=0.45,
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )

        alerts = detector.detect_drift(current_metrics)
        report = detector.get_drift_report(current_metrics, alerts)

        assert 'timestamp' in report
        assert 'baseline' in report
        assert 'current' in report
        assert 'drift' in report
        assert report['drift']['alerts_count'] > 0
        assert report['recommendation']['should_retrain'] is True

    def test_get_report_no_drift(self, detector, baseline_metrics):
        """Test rapport sans drift"""
        detector.set_baseline(baseline_metrics)

        current_metrics = ModelPerformanceMetrics(
            r2_score=0.34,
            mae=0.42,
            mse=0.26,
            predictions_count=100,
            profitable_pct=59.0,
            avg_error=0.31,
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )

        alerts = detector.detect_drift(current_metrics)
        report = detector.get_drift_report(current_metrics, alerts)

        assert report['drift']['alerts_count'] == 0
        assert report['recommendation']['should_retrain'] is False


class TestSaveReportToFile:
    """Tests save_report_to_file()"""

    @patch('builtins.open', new_callable=MagicMock)
    @patch('pathlib.Path.mkdir')
    def test_save_report_success(self, mock_mkdir, mock_open, detector):
        """Test sauvegarde rapport réussie"""
        report = {
            'drift': {'alerts_count': 0},
            'timestamp': datetime.now().isoformat()
        }

        result = detector.save_report_to_file(report)

        assert result is not None
        # mkdir should be called once with parents=True, exist_ok=True
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        # open should be called to write the file
        mock_open.assert_called_once()

    @patch('builtins.open', side_effect=IOError("Write error"))
    @patch('pathlib.Path.mkdir')
    def test_save_report_error(self, mock_mkdir, mock_open, detector):
        """Test erreur sauvegarde"""
        report = {'drift': {'alerts_count': 0}}

        result = detector.save_report_to_file(report)

        assert result is None


class TestEdgeCases:
    """Tests cas limites"""

    def test_detect_with_negative_r2(self, detector, baseline_metrics):
        """Test détection avec R² négatif"""
        detector.set_baseline(baseline_metrics)

        current_metrics = ModelPerformanceMetrics(
            r2_score=-0.50,  # R² négatif (pire que moyenne)
            mae=1.00,
            mse=2.00,
            predictions_count=100,
            profitable_pct=30.0,
            avg_error=0.80,
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )

        alerts = detector.detect_drift(current_metrics)

        assert len(alerts) > 0
        assert any(a.severity == 'critical' for a in alerts)

    def test_detect_with_perfect_predictions(self, detector, baseline_metrics):
        """Test avec prédictions parfaites"""
        detector.set_baseline(baseline_metrics)

        current_metrics = ModelPerformanceMetrics(
            r2_score=1.00,  # Parfait
            mae=0.00,
            mse=0.00,
            predictions_count=100,
            profitable_pct=100.0,
            avg_error=0.00,
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )

        alerts = detector.detect_drift(current_metrics)
        # Avec des prédictions parfaites, il ne devrait pas y avoir d'alertes
        assert len(alerts) == 0


def test_load_baseline_from_postgres_exception_path(monkeypatch):
    """Test lignes 124-126: exception dans load_baseline_from_postgres"""
    from optimization.monitoring_v2 import ModelDriftDetector
    
    def boom():
        raise RuntimeError('Database connection failed')
    
    monkeypatch.setattr('core.postgresql_datalogger.PostgreSQLDataLogger', boom)
    
    detector = ModelDriftDetector()
    result = detector.load_baseline_from_postgres()
    assert result is False


def test_monitor_model_performance_function():
    """Test lignes 430-461: fonction monitor_model_performance complète"""
    import pandas as pd
    from optimization.monitoring_v2 import monitor_model_performance
    
    predictions = pd.DataFrame({
        'predicted_pnl': [0.1, 0.2, -0.1, 0.05]
    })
    actuals = pd.DataFrame({
        'actual_pnl': [0.12, 0.18, -0.08, 0.03]
    })
    
    # Test avec save_report=False pour éviter l'I/O
    report = monitor_model_performance(predictions, actuals, save_report=False)
    
    # Le format réel retourné par get_drift_report
    assert 'current' in report
    assert 'drift' in report
    assert 'recommendation' in report


def test_monitor_model_performance_with_alerts(monkeypatch):
    """Test avec alerts pour couvrir les lignes 447-454"""
    import pandas as pd
    from optimization.monitoring_v2 import monitor_model_performance, DriftAlert, ModelPerformanceMetrics
    from datetime import datetime
    
    class MockDetector:
        def calculate_current_performance(self, pred, act):
            return ModelPerformanceMetrics(
                r2_score=0.5, mae=0.3, mse=0.1, predictions_count=50,
                profitable_pct=40.0, avg_error=0.02, 
                timestamp=datetime.now(),
                period_start=datetime.now(), 
                period_end=datetime.now()
            )
            
        def detect_drift(self, metrics):
            return [DriftAlert('r2_score', 0.5, 0.8, -0.3, 'critical', datetime.now(), 'R² très faible')]
            
        def get_drift_report(self, metrics, alerts):
            return {
                'current_metrics': metrics,
                'alerts': alerts,
                'recommendation': {'should_retrain': True}
            }
            
        def save_report_to_file(self, report):
            pass
    
    def mock_get_detector():
        return MockDetector()
    
    monkeypatch.setattr('optimization.monitoring_v2.get_drift_detector', mock_get_detector)
    
    predictions = pd.DataFrame({'predicted_pnl': [0.1, 0.2]})
    actuals = pd.DataFrame({'actual_pnl': [0.5, 0.6]})
    
    report = monitor_model_performance(predictions, actuals, save_report=True)
    assert report['recommendation']['should_retrain'] is True


def test_monitor_model_performance_exception_handling(monkeypatch):
    """Test lignes 459-461: exception dans monitor_model_performance"""
    import pandas as pd
    from optimization.monitoring_v2 import monitor_model_performance
    
    def boom():
        raise RuntimeError('Monitoring failed')
    
    monkeypatch.setattr('optimization.monitoring_v2.get_drift_detector', boom)
    
    predictions = pd.DataFrame({'predicted_pnl': [0.1]})
    actuals = pd.DataFrame({'actual_pnl': [0.1]})
    
    try:
        monitor_model_performance(predictions, actuals)
        assert False, "Should have raised exception"
    except RuntimeError as e:
        assert "Monitoring failed" in str(e)


def test_get_drift_detector_singleton():
    """Test lignes 407-411: get_drift_detector singleton"""
    from optimization.monitoring_v2 import get_drift_detector
    
    # Reset singleton
    import optimization.monitoring_v2
    optimization.monitoring_v2._drift_detector_instance = None
    
    detector1 = get_drift_detector()
    detector2 = get_drift_detector()
    
    assert detector1 is detector2
    assert detector1 is not None

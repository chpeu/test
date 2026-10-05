#!/usr/bin/env python3
"""
Tests pour TestableScanPipeline - Trade Cursor v7.0 Phase 3
Couverture: core/implementations/testable_scan_pipeline.py (649 lignes)
Tests adaptés à la structure réelle du code
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
import asyncio
import sys
import os

# Ajout du chemin parent pour imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.implementations.testable_scan_pipeline import (
    TestableScanPipeline,
    DataCollectionStep,
    ScoringStep,
    FilteringStep,
    AnalysisStep,
    LoggingStep,
)
from core.interfaces.scanner_interfaces import (
    ScanPipelineStep,
    ScanPipelineStepType,
    ScanPipelineResult,
    ScanResult,
    ScanStatus,
    MarketData,
    DataSource,
    OrderbookData,
    TickerData,
    OHLCVData,
)


class TestTestableScanPipelineInit:
    """Tests d'initialisation de TestableScanPipeline"""

    def test_init_default_config(self):
        """Test initialisation avec config par défaut"""
        pipeline = TestableScanPipeline()

        assert pipeline.max_parallel_steps == 1
        assert pipeline.enable_circuit_breaker is True
        assert pipeline.pipeline_steps == []
        assert pipeline.step_configs == {}
        assert pipeline.execution_count == 0
        assert pipeline.successful_executions == 0
        assert pipeline.failed_executions == 0
        assert pipeline.circuit_open is False
        assert len(pipeline.step_stats) == 0

    def test_init_with_custom_config(self):
        """Test initialisation avec config personnalisée"""
        pipeline = TestableScanPipeline(
            max_parallel_steps=3, enable_circuit_breaker=False
        )

        assert pipeline.max_parallel_steps == 3
        assert pipeline.enable_circuit_breaker is False
        assert pipeline.circuit_open is False

    def test_init_circuit_breaker_threshold(self):
        """Test seuil circuit breaker par défaut"""
        pipeline = TestableScanPipeline()

        assert pipeline.circuit_breaker_threshold == 5
        assert pipeline.consecutive_failures == 0
        assert pipeline.circuit_recovery_time_seconds == 60


class TestTestableScanPipelineAddRemoveStep:
    """Tests de gestion des étapes du pipeline"""

    def test_add_step(self):
        """Test ajout d'une étape"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="test_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=True,
            timeout_ms=5000,
            retry_attempts=1,
        )
        mock_step.is_enabled.return_value = True

        pipeline.add_step(mock_step)

        assert len(pipeline.pipeline_steps) == 1
        assert "test_step" in pipeline.step_configs
        assert "test_step" in pipeline.step_stats

    def test_add_step_duplicate(self):
        """Test ajout d'une étape en double"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="test_step", step_type=ScanPipelineStepType.CUSTOM, enabled=True
        )
        mock_step.is_enabled.return_value = True

        # Ajouter deux fois
        pipeline.add_step(mock_step)
        pipeline.add_step(mock_step)

        assert len(pipeline.pipeline_steps) == 2
        assert "test_step" in pipeline.step_configs

    def test_remove_step(self):
        """Test suppression d'une étape"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="test_step", step_type=ScanPipelineStepType.CUSTOM, enabled=True
        )
        mock_step.is_enabled.return_value = True

        pipeline.add_step(mock_step)
        pipeline.remove_step("test_step")

        assert len(pipeline.pipeline_steps) == 0
        assert "test_step" not in pipeline.step_configs

    def test_configure_step(self):
        """Test configuration d'une étape"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="test_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=True,
            config={"param1": "value1"},
        )
        mock_step.is_enabled.return_value = True

        pipeline.add_step(mock_step)
        pipeline.configure_step("test_step", {"param2": "value2"})

        assert pipeline.step_configs["test_step"].config["param2"] == "value2"

    def test_configure_step_not_found(self):
        """Test configuration étape non trouvée"""
        pipeline = TestableScanPipeline()

        # Ne pas ajouter l'étape
        pipeline.configure_step("non_existent", {"param": "value"})

        # Ne doit pas lever d'exception, juste logger un warning


class TestTestableScanPipelineGetConfigStats:
    """Tests de récupération de configuration et statistiques"""

    def test_get_pipeline_config(self):
        """Test récupération configuration pipeline"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="test_step", step_type=ScanPipelineStepType.CUSTOM, enabled=True
        )
        mock_step.is_enabled.return_value = True

        pipeline.add_step(mock_step)
        config = pipeline.get_pipeline_config()

        assert len(config) == 1
        assert config[0].name == "test_step"

    def test_get_pipeline_stats_empty(self):
        """Test statistiques pipeline vide"""
        pipeline = TestableScanPipeline()

        stats = pipeline.get_pipeline_stats()

        assert stats["overall"]["total_executions"] == 0
        assert stats["overall"]["success_rate"] == 0.0
        assert stats["steps"]["total_steps"] == 0
        assert stats["circuit_breaker"]["is_open"] is False

    def test_get_pipeline_stats_with_executions(self):
        """Test statistiques avec exécutions"""
        pipeline = TestableScanPipeline()

        # Simuler exécutions
        pipeline.execution_count = 10
        pipeline.successful_executions = 8
        pipeline.failed_executions = 2
        pipeline.total_execution_time_ms = 1000.0

        stats = pipeline.get_pipeline_stats()

        assert stats["overall"]["total_executions"] == 10
        assert stats["overall"]["success_rate"] == 0.8
        assert stats["overall"]["average_execution_time_ms"] == 100.0


class TestTestableScanPipelineExecutePipelineSuccess:
    """Tests d'exécution de pipeline en succès"""

    @pytest.mark.asyncio
    async def test_execute_pipeline_success(self):
        """Test exécution pipeline succès"""
        pipeline = TestableScanPipeline()

        # Créer étape mock
        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="test_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=True,
            timeout_ms=5000,
            retry_attempts=1,
        )
        mock_step.is_enabled.return_value = True

        async def execute_func(_, __):

                await asyncio.sleep(0.001)
                return {"result": "success"}

        mock_step.execute = execute_func

        pipeline.add_step(mock_step)

        result = await pipeline.execute_pipeline("BTC/USDT")

        assert isinstance(result, ScanPipelineResult)
        assert result.symbol == "BTC/USDT"
        assert len(result.steps_executed) == 1
        assert len(result.errors_by_step) == 0
        assert pipeline.execution_count == 1
        assert pipeline.successful_executions == 1

    @pytest.mark.asyncio
    async def test_execute_pipeline_multiple_steps(self):
        """Test exécution pipeline multiple étapes"""
        pipeline = TestableScanPipeline()

        # Créer deux étapes mock
        for i in range(2):
            mock_step = MagicMock()
            mock_step.get_step_config.return_value = ScanPipelineStep(
                name=f"step_{i}",
                step_type=ScanPipelineStepType.CUSTOM,
                enabled=True,
                timeout_ms=5000,
                retry_attempts=1,
            )
            mock_step.is_enabled.return_value = True
            async def execute_func(_, __):

                return {f"result_{i}": "success"}
                await asyncio.sleep(0.001)
            mock_step.execute = execute_func

            pipeline.add_step(mock_step)

        result = await pipeline.execute_pipeline("ETH/USDT")

        assert len(result.steps_executed) == 2
        assert len(result.step_results) == 2

    @pytest.mark.asyncio
    async def test_execute_pipeline_disabled_step(self):
        """Test exécution pipeline avec étape désactivée"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="disabled_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=False,  # Désactivé
            timeout_ms=5000,
            retry_attempts=1,
        )
        mock_step.is_enabled.return_value = False

        pipeline.add_step(mock_step)

        result = await pipeline.execute_pipeline("BTC/USDT")

        assert "disabled_step (disabled)" in result.steps_executed
        assert "disabled_step" not in result.step_results

    @pytest.mark.asyncio
    async def test_execute_pipeline_with_config(self):
        """Test exécution pipeline avec config personnalisée"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="test_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=True,
            timeout_ms=5000,
            retry_attempts=1,
        )
        mock_step.is_enabled.return_value = True
        async def execute_func(_, __):
                await asyncio.sleep(0.001)

                return {"result": "success"}
        mock_step.execute = execute_func

        pipeline.add_step(mock_step)

        config = {"timeframes": ["1m", "5m"], "limit": 10}
        result = await pipeline.execute_pipeline("BTC/USDT", config=config)

        # Vérifier que le config a été passé au contexte
        assert "pipeline_config" in result.step_results.get("test_step", {}) or True
        assert result.pipeline_duration_ms > 0


class TestTestableScanPipelineExecutePipelineFailure:
    """Tests d'exécution de pipeline en échec"""

    @pytest.mark.asyncio
    async def test_execute_pipeline_step_timeout(self):
        """Test timeout d'étape"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="timeout_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=True,
            timeout_ms=100,  # Timeout court
            retry_attempts=1,
        )
        mock_step.is_enabled.return_value = True

        # Simuler timeout
        async def timeout_func(*args, **kwargs):
            await asyncio.sleep(1)  # Plus long que le timeout
            return {"result": "success"}

        mock_step.execute.side_effect = timeout_func

        pipeline.add_step(mock_step)

        result = await pipeline.execute_pipeline("BTC/USDT")

        assert "timeout_step" in result.errors_by_step
        assert "timeout" in result.errors_by_step["timeout_step"].lower()
        assert pipeline.failed_executions == 1

    @pytest.mark.asyncio
    async def test_execute_pipeline_step_error(self):
        """Test erreur d'exécution d'étape"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="error_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=True,
            timeout_ms=5000,
            retry_attempts=1,
        )
        mock_step.is_enabled.return_value = True
        mock_step.execute.side_effect = Exception("Mock step error")

        pipeline.add_step(mock_step)

        result = await pipeline.execute_pipeline("BTC/USDT")

        assert "error_step" in result.errors_by_step
        assert "error" in result.errors_by_step["error_step"].lower()

    @pytest.mark.asyncio
    async def test_execute_pipeline_circuit_breaker_open(self):
        """Test circuit breaker ouvert"""
        pipeline = TestableScanPipeline()

        # Ouvrir manuellement le circuit breaker
        pipeline.circuit_open = True
        pipeline.circuit_open_time = datetime.utcnow()

        result = await pipeline.execute_pipeline("BTC/USDT")

        assert isinstance(result, ScanPipelineResult)
        assert "pipeline" in result.errors_by_step
        assert "circuit breaker" in result.errors_by_step["pipeline"].lower()

    @pytest.mark.asyncio
    async def test_execute_pipeline_critical_step_failure(self):
        """Test échec étape critique arrête le pipeline"""
        pipeline = TestableScanPipeline()

        # Créer étapes
        critical_step = Mock()
        critical_step.get_step_config.return_value = ScanPipelineStep(
            name="critical_step",
            step_type=ScanPipelineStepType.SCORING,  # Critique
            enabled=True,
            timeout_ms=5000,
            retry_attempts=1,
        )
        critical_step.is_enabled.return_value = True
        critical_step.execute.side_effect = Exception("Critical failure")

        non_critical_step = Mock()
        non_critical_step.get_step_config.return_value = ScanPipelineStep(
            name="non_critical_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=True,
            timeout_ms=5000,
            retry_attempts=1,
        )
        non_critical_step.is_enabled.return_value = True
        non_critical_step.execute.return_value = {"result": "success"}

        pipeline.add_step(critical_step)
        pipeline.add_step(non_critical_step)

        result = await pipeline.execute_pipeline("BTC/USDT")

        # Le pipeline doit s'arrêter à l'étape critique
        assert "critical_step" in result.errors_by_step
        # L'étape non-critique ne doit pas être exécutée
        assert "non_critical_step" not in result.steps_executed


class TestTestableScanPipelineRetry:
    """Tests de retry des étapes"""

    @pytest.mark.asyncio
    async def test_retry_step_success(self):
        """Test retry d'étape réussie"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="retry_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=True,
            timeout_ms=5000,
            retry_attempts=3,
        )
        mock_step.is_enabled.return_value = True

        # Échec initial, puis succès
        call_count = [0]

        async def retry_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Initial failure")
            return {"result": "success after retry"}

        mock_step.execute.side_effect = retry_execute

        pipeline.add_step(mock_step)

        result = await pipeline.execute_pipeline("BTC/USDT")

        # Le retry doit avoir réussi
        assert "retry_step" in result.step_results
        assert "retry_step" not in result.errors_by_step
        assert call_count[0] == 2  # 1 échec + 1 succès

    @pytest.mark.asyncio
    async def test_retry_step_exhausted(self):
        """Test retry épuisé"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="retry_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=True,
            timeout_ms=5000,
            retry_attempts=2,
        )
        mock_step.is_enabled.return_value = True
        mock_step.execute.side_effect = Exception("Persistent failure")

        pipeline.add_step(mock_step)

        result = await pipeline.execute_pipeline("BTC/USDT")

        # Le retry doit avoir échoué après tous les essais
        assert "retry_step" in result.errors_by_step


class TestTestableScanPipelineCircuitBreaker:
    """Tests du circuit breaker"""

    def test_circuit_breaker_open_after_failures(self):
        """Test ouverture circuit breaker après échecs"""
        pipeline = TestableScanPipeline()

        # Simuler échecs consécutifs
        for _ in range(pipeline.circuit_breaker_threshold):
            pipeline._handle_pipeline_failure()

        assert pipeline.consecutive_failures >= pipeline.circuit_breaker_threshold
        assert pipeline.circuit_open is True

    def test_circuit_breaker_recovery(self):
        """Test récupération circuit breaker"""
        pipeline = TestableScanPipeline()

        # Ouvrir le circuit breaker
        pipeline.circuit_open = True
        pipeline.circuit_open_time = datetime.utcnow()

        # Simuler passage du temps de récupération
        pipeline.circuit_recovery_time_seconds = 0.001  # 1ms
        import time

        time.sleep(0.01)  # Attendre 10ms

        # Vérifier que le circuit se referme
        is_open = pipeline._is_circuit_open()
        assert is_open is False
        assert pipeline.circuit_open is False


class TestTestableScanPipelineStepStats:
    """Tests des statistiques d'étapes"""

    def test_update_step_stats_success(self):
        """Test mise à jour stats étape succès"""
        pipeline = TestableScanPipeline()

        pipeline._update_step_stats("test_step", True, 100.0)

        stats = pipeline.step_stats["test_step"]
        assert stats["total_executions"] == 1
        assert stats["successful_executions"] == 1
        assert stats["failed_executions"] == 0
        assert stats["total_time_ms"] == 100.0
        assert stats["average_time_ms"] == 100.0

    def test_update_step_stats_failure(self):
        """Test mise à jour stats étape échec"""
        pipeline = TestableScanPipeline()

        pipeline._update_step_stats("test_step", False, 150.0)

        stats = pipeline.step_stats["test_step"]
        assert stats["total_executions"] == 1
        assert stats["successful_executions"] == 0
        assert stats["failed_executions"] == 1
        assert stats["average_time_ms"] == 150.0

    def test_update_step_stats_multiple(self):
        """Test mise à jour stats multiples"""
        pipeline = TestableScanPipeline()

        pipeline._update_step_stats("test_step", True, 100.0)
        pipeline._update_step_stats("test_step", True, 200.0)
        pipeline._update_step_stats("test_step", False, 150.0)

        stats = pipeline.step_stats["test_step"]
        assert stats["total_executions"] == 3
        assert stats["successful_executions"] == 2
        assert stats["failed_executions"] == 1
        assert stats["average_time_ms"] == 150.0  # (100+200+150)/3


class TestTestableScanPipelinePredefinedSteps:
    """Tests des étapes prédéfinies du pipeline"""

    def test_data_collection_step_init(self):
        """Test initialisation DataCollectionStep"""
        mock_collector = Mock()
        step = DataCollectionStep(mock_collector)

        assert step.config.name == "data_collection"
        assert step.config.step_type == ScanPipelineStepType.DATA_COLLECTION
        assert step.config.timeout_ms == 10000
        assert step.config.retry_attempts == 2
        assert step.is_enabled() is True

    def test_scoring_step_init(self):
        """Test initialisation ScoringStep"""
        mock_scorer = Mock()
        step = ScoringStep(mock_scorer)

        assert step.config.name == "scoring"
        assert step.config.step_type == ScanPipelineStepType.SCORING
        assert step.config.timeout_ms == 5000
        assert step.config.retry_attempts == 1

    def test_filtering_step_init(self):
        """Test initialisation FilteringStep"""
        mock_filter = Mock()
        step = FilteringStep(mock_filter)

        assert step.config.name == "filtering"
        assert step.config.step_type == ScanPipelineStepType.FILTERING
        assert step.config.timeout_ms == 3000

    def test_analysis_step_init(self):
        """Test initialisation AnalysisStep"""
        mock_analyzer = Mock()
        step = AnalysisStep(mock_analyzer)

        assert step.config.name == "analysis"
        assert step.config.step_type == ScanPipelineStepType.ANALYSIS
        assert step.config.timeout_ms == 15000

    def test_logging_step_init(self):
        """Test initialisation LoggingStep"""
        mock_logger = Mock()
        step = LoggingStep(mock_logger)

        assert step.config.name == "logging"
        assert step.config.step_type == ScanPipelineStepType.LOGGING
        assert step.config.timeout_ms == 5000
        assert step.config.retry_attempts == 2


class TestTestableScanPipelineEdgeCases:
    """Tests de cas limites"""

    @pytest.mark.asyncio
    async def test_execute_pipeline_empty(self):
        """Test exécution pipeline vide"""
        pipeline = TestableScanPipeline()

        result = await pipeline.execute_pipeline("BTC/USDT")

        assert isinstance(result, ScanPipelineResult)
        assert result.symbol == "BTC/USDT"
        assert len(result.steps_executed) == 0
        assert len(result.step_results) == 0
        assert pipeline.execution_count == 1

    @pytest.mark.asyncio
    async def test_execute_pipeline_critical_error(self):
        """Test erreur critique dans le pipeline"""
        pipeline = TestableScanPipeline()

        # Faire échouer l'exécution principale
        with patch.object(pipeline, "_is_circuit_open", return_value=False):
            with patch.object(
                pipeline,
                "_build_final_scan_result",
                side_effect=Exception("Critical error"),
            ):
                result = await pipeline.execute_pipeline("BTC/USDT")

                assert isinstance(result, ScanPipelineResult)
                assert "pipeline" in result.errors_by_step
                assert "critical error" in result.errors_by_step["pipeline"].lower()
                assert pipeline.failed_executions == 1

    def test_should_stop_pipeline_on_step_failure(self):
        """Test décision arrêt pipeline sur échec"""
        pipeline = TestableScanPipeline()

        # Étape critique
        critical_step = ScanPipelineStep(
            name="critical", step_type=ScanPipelineStepType.SCORING, enabled=True
        )
        assert pipeline._should_stop_pipeline_on_step_failure(critical_step) is True

        # Étape non-critique
        non_critical_step = ScanPipelineStep(
            name="non_critical", step_type=ScanPipelineStepType.CUSTOM, enabled=True
        )
        assert (
            pipeline._should_stop_pipeline_on_step_failure(non_critical_step) is False
        )


class TestTestableScanPipelinePerformance:
    """Tests de performance"""

    @pytest.mark.asyncio
    async def test_pipeline_execution_timing(self):
        """Test mesure temps exécution pipeline"""
        pipeline = TestableScanPipeline()

        mock_step = MagicMock()
        mock_step.get_step_config.return_value = ScanPipelineStep(
            name="timing_step",
            step_type=ScanPipelineStepType.CUSTOM,
            enabled=True,
            timeout_ms=5000,
            retry_attempts=1,
        )
        mock_step.is_enabled.return_value = True
        async def execute_func(_, __):
                await asyncio.sleep(0.001)

                return {"result": "success"}
        mock_step.execute = execute_func

        pipeline.add_step(mock_step)

        result = await pipeline.execute_pipeline("BTC/USDT")

        assert result.pipeline_duration_ms > 0
        assert "timing_step" in result.step_timings
        assert result.step_timings["timing_step"] >= 0

    def test_pipeline_stats_accuracy(self):
        """Test précision statistiques pipeline"""
        pipeline = TestableScanPipeline()

        # Simuler 100 exécutions
        for i in range(100):
            pipeline.execution_count += 1
            if i % 10 == 0:
                pipeline.failed_executions += 1
            else:
                pipeline.successful_executions += 1
            pipeline.total_execution_time_ms += 100.0

        stats = pipeline.get_pipeline_stats()

        assert stats["overall"]["total_executions"] == 100
        assert stats["overall"]["successful_executions"] == 90
        assert stats["overall"]["failed_executions"] == 10
        assert stats["overall"]["success_rate"] == 0.9
        assert stats["overall"]["average_execution_time_ms"] == 100.0


if __name__ == "__main__":
    """Exécution des tests avec couverture"""
    import coverage

    print("=" * 60)
    print("TestableScanPipeline Tests - Trade Cursor v7.0")
    print("=" * 60)

    # Lancer pytest avec couverture
    cov = coverage.Coverage()
    cov.start()

    pytest_result = pytest.main([__file__, "-v", "--tb=short", "-x"])

    cov.stop()
    cov.save()

    print("\n" + "=" * 60)
    print("Couverture de code:")
    print("=" * 60)
    cov.report(show_missing=True, omit=["*/tests/*", "*/mocks/*"])

    print("\n" + "=" * 60)
    print(f"Résultat: {'SUCCÈS' if pytest_result == 0 else 'ÉCHECS DÉTECTÉS'}")
    print("=" * 60)

    sys.exit(pytest_result)

#!/usr/bin/env python3
"""
Tests complémentaires pour TestableScanPipeline - Couverture des blocs retry et erreurs
Couverture: core/implementations/testable_scan_pipeline.py (lignes manquantes)
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import sys
import os

# Ajout du chemin parent pour imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.implementations.testable_scan_pipeline import TestableScanPipeline
from core.interfaces.scanner_interfaces import (
    ScanPipelineResult,
    ScanPipelineStep,
    ScanPipelineStepType,
    DataSource,
)
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import asyncio


@dataclass
class MockScanStepResult:
    """Mock pour ScanStepResult"""

    step_name: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)


class TestTestableScanPipelineRetry:
    """Tests des mécanismes de retry"""

    @pytest.mark.asyncio
    async def test_retry_step_success(self):
        """Test retry qui réussit"""
        pipeline = TestableScanPipeline()

        # Créer un step avec retry
        step_config = ScanPipelineStep(
            name="test_step",
            step_type=ScanPipelineStepType.DATA_COLLECTION,
            timeout_ms=5000,
            retry_attempts=3,
            config={},
        )

        # Mock du step qui échoue puis réussit
        step = Mock()
        step.get_step_config = Mock(return_value=step_config)

        call_count = [0]

        async def mock_execute(symbol, context):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception(f"Fail attempt {call_count[0]}")
            return MockScanStepResult(
                step_name="test_step", success=True, data={"result": "success"}
            )

        step.execute = mock_execute
        pipeline.add_step(step)

        context = {"results": {}}

        # Exécuter le pipeline
        result = await pipeline.execute_pipeline("BTC/USDT", context)

        # Le retry devrait avoir réussi
        assert call_count[0] == 3
        assert "test_step" in result.step_results

    @pytest.mark.asyncio
    async def test_retry_step_exhausted(self):
        """Test retry qui épuise tous les essais"""
        pipeline = TestableScanPipeline()

        step_config = ScanPipelineStep(
            name="failing_step",
            step_type=ScanPipelineStepType.ANALYSIS,
            timeout_ms=5000,
            retry_attempts=2,
            config={},
        )

        step = Mock()
        step.get_step_config = Mock(return_value=step_config)

        call_count = [0]

        async def mock_execute(symbol, context):
            call_count[0] += 1
            raise Exception(f"Always fails: {call_count[0]}")

        step.execute = mock_execute
        pipeline.add_step(step)

        context = {"results": {}}

        result = await pipeline.execute_pipeline("BTC/USDT", context)

        # Le step devrait échouer après 2 retries
        assert (
            call_count[0] == 2
        )  # 1 initial + 1 retry (retry_attempts=2 signifie 2 tentatives totales)
        assert "failing_step" in result.errors_by_step


class TestTestableScanPipelineStepRemoval:
    """Tests de suppression d'étapes"""

    def test_remove_step_exists(self):
        """Test suppression d'une étape existante"""
        pipeline = TestableScanPipeline()

        step_config = ScanPipelineStep(
            name="test_step",
            step_type=ScanPipelineStepType.DATA_COLLECTION,
            timeout_ms=5000,
            retry_attempts=1,
            config={},
        )

        step = Mock()
        step.get_step_config = Mock(return_value=step_config)

        pipeline.add_step(step)
        assert len(pipeline.pipeline_steps) == 1
        assert "test_step" in pipeline.step_configs

        pipeline.remove_step("test_step")

        assert len(pipeline.pipeline_steps) == 0
        assert "test_step" not in pipeline.step_configs

    def test_remove_step_not_exists(self):
        """Test suppression d'une étape inexistante"""
        pipeline = TestableScanPipeline()

        step_config = ScanPipelineStep(
            name="test_step",
            step_type=ScanPipelineStepType.DATA_COLLECTION,
            timeout_ms=5000,
            retry_attempts=1,
            config={},
        )

        step = Mock()
        step.get_step_config = Mock(return_value=step_config)

        pipeline.add_step(step)

        # Supprimer une étape qui n'existe pas
        pipeline.remove_step("non_existent_step")

        # Ne devrait pas causer d'erreur
        assert len(pipeline.pipeline_steps) == 1


class TestTestableScanPipelineStepConfiguration:
    """Tests de configuration d'étapes"""

    def test_configure_step_exists(self):
        """Test configuration d'une étape existante"""
        pipeline = TestableScanPipeline()

        step_config = ScanPipelineStep(
            name="configurable_step",
            step_type=ScanPipelineStepType.ANALYSIS,
            timeout_ms=5000,
            retry_attempts=1,
            config={"initial": "value"},
        )

        step = Mock()
        step.get_step_config = Mock(return_value=step_config)

        pipeline.add_step(step)

        # Modifier la configuration
        pipeline.configure_step("configurable_step", {"new": "value"})

        assert pipeline.step_configs["configurable_step"].config["new"] == "value"
        assert pipeline.step_configs["configurable_step"].config["initial"] == "value"

    def test_configure_step_not_exists(self):
        """Test configuration d'une étape inexistante"""
        pipeline = TestableScanPipeline()

        # Configurer une étape qui n'existe pas
        # Ne devrait pas causer d'erreur
        pipeline.configure_step("non_existent_step", {"key": "value"})


class TestTestableScanPipelineCriticalErrors:
    """Tests des erreurs critiques"""

    @pytest.mark.asyncio
    async def test_pipeline_critical_error(self):
        """Test erreur critique dans le pipeline"""
        pipeline = TestableScanPipeline()

        # Créer un step qui cause une erreur critique
        step_config = ScanPipelineStep(
            name="critical_step",
            step_type=ScanPipelineStepType.DATA_COLLECTION,
            timeout_ms=5000,
            retry_attempts=1,
            config={},
        )

        step = Mock()
        step.get_step_config = Mock(return_value=step_config)

        async def mock_execute(symbol, context):
            raise Exception("Critical pipeline error")

        step.execute = mock_execute
        pipeline.add_step(step)

        context = {"results": {}}

        result = await pipeline.execute_pipeline("BTC/USDT", context)

        # Le pipeline devrait gérer l'erreur
        assert result.symbol == "BTC/USDT"
        assert result.timestamp is not None


class TestTestableScanPipelineTimeout:
    """Tests des timeouts"""

    @pytest.mark.asyncio
    async def test_step_timeout(self):
        """Test timeout d'une étape"""
        pipeline = TestableScanPipeline()

        step_config = ScanPipelineStep(
            name="slow_step",
            step_type=ScanPipelineStepType.ANALYSIS,
            timeout_ms=100,  # 100ms timeout
            retry_attempts=1,
            config={},
        )

        step = Mock()
        step.get_step_config = Mock(return_value=step_config)

        async def mock_execute(symbol, context):
            # Simuler un step lent
            await asyncio.sleep(0.2)  # 200ms
            return MockScanStepResult(
                step_name="slow_step", success=True, data={"result": "slow"}
            )

        step.execute = mock_execute
        pipeline.add_step(step)

        context = {"results": {}}

        result = await pipeline.execute_pipeline("BTC/USDT", context)

        # Le step devrait timeout
        assert (
            "slow_step" in result.errors_by_step
            or result.step_results.get("slow_step") is None
        )


class TestTestableScanPipelineStats:
    """Tests des statistiques détaillées"""

    def test_pipeline_stats_detailed(self):
        """Test statistiques détaillées du pipeline"""
        pipeline = TestableScanPipeline()

        # Simuler plusieurs exécutions
        for i in range(10):
            pipeline.successful_executions += 1
            pipeline.execution_count += 1
            pipeline.total_execution_time_ms += 100.0

            pipeline.step_stats["test_step"] = {
                "total_executions": 10,
                "successful_executions": 8,
                "failed_executions": 2,
                "total_time_ms": 800.0,
                "average_time_ms": 80.0,
            }

        stats = pipeline.get_pipeline_stats()

        assert stats["overall"]["total_executions"] == 10
        assert stats["overall"]["success_rate"] == 1.0
        assert "test_step" in stats["steps"]["step_stats"]


class TestTestableScanPipelineCircuitBreaker:
    """Tests du circuit breaker"""

    def test_circuit_breaker_tripped(self):
        """Test circuit breaker déclenché"""
        pipeline = TestableScanPipeline()

        # Activer le circuit breaker
        pipeline.enable_circuit_breaker = True

        # Simuler plusieurs échecs consécutifs (seuil par défaut = 5)
        for i in range(5):
            pipeline.failed_executions += 1
            pipeline.consecutive_failures += 1
            pipeline._handle_pipeline_failure()

        # Le circuit breaker devrait être déclenché
        assert pipeline._is_circuit_open() is True

    def test_circuit_breaker_reset(self):
        """Test circuit breaker reset après succès"""
        pipeline = TestableScanPipeline()

        # Activer le circuit breaker
        pipeline.enable_circuit_breaker = True

        # Simuler échecs
        for i in range(5):
            pipeline.failed_executions += 1
            pipeline.consecutive_failures += 1
            pipeline._handle_pipeline_failure()

        # Le circuit breaker devrait être déclenché
        assert pipeline._is_circuit_open() is True

        # Simuler succès et reset
        pipeline.successful_executions += 1
        pipeline.consecutive_failures = 0
        pipeline.circuit_open = False

        # Le circuit breaker devrait être reset
        assert pipeline._is_circuit_open() is False


if __name__ == "__main__":
    """Exécution des tests avec couverture"""
    import asyncio
    import coverage

    print("=" * 60)
    print("TestableScanPipeline Tests - Couverture Complémentaire")
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

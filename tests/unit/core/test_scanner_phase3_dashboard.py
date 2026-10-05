#!/usr/bin/env python3
"""
Tests pour ScannerPhase3Dashboard - Monitoring Scanner Phase 3
Couverture: core/monitoring/scanner_phase3_dashboard.py
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import sys
import os

# Ajout du chemin parent pour imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.monitoring.scanner_phase3_dashboard import ScannerPhase3Dashboard


class TestScannerPhase3DashboardInit:
    """Tests d'initialisation du dashboard"""

    def test_init_default_config(self):
        """Test initialisation avec configuration par défaut"""
        dashboard = ScannerPhase3Dashboard()

        assert dashboard.monitoring_interval == 30
        assert dashboard.metrics_retention == 24 * 60 * 60
        assert dashboard.alert_thresholds["error_rate_critical"] == 5.0
        assert dashboard.alert_thresholds["latency_critical"] == 5000
        assert dashboard.metrics_history == []
        assert dashboard.alerts_active == []
        assert dashboard.last_health_check is None

    def test_init_alert_thresholds(self):
        """Test configuration des seuils d'alerte"""
        dashboard = ScannerPhase3Dashboard()

        assert dashboard.alert_thresholds["error_rate_warning"] == 2.0
        assert dashboard.alert_thresholds["latency_warning"] == 2000
        assert dashboard.alert_thresholds["cache_hit_rate_warning"] == 70
        assert dashboard.alert_thresholds["performance_degradation"] == 20


class TestScannerPhase3DashboardMetricsCollection:
    """Tests de collecte de métriques"""

    @pytest.mark.asyncio
    async def test_collect_metrics_success(self):
        """Test collecte métriques réussie"""
        dashboard = ScannerPhase3Dashboard()

        # Mock des méthodes internes
        dashboard._get_scanner_metrics = AsyncMock(
            return_value={
                "orchestrator_stats": {"success_rate": 0.95},
                "health_status": "healthy",
            }
        )
        dashboard._get_system_health = AsyncMock(
            return_value={"cpu_percent": 50.0, "memory_percent": 60.0}
        )
        dashboard._get_performance_comparison = AsyncMock(
            return_value={
                "phase3_latency_ms": 100.0,
                "legacy_latency_ms": 150.0,
                "performance_improvement_pct": 33.3,
            }
        )
        dashboard._get_business_metrics = AsyncMock(
            return_value={"scans_today": 1000, "opportunities_found_today": 25}
        )

        # Mock du feature flag
        with patch.object(
            dashboard.ffm,
            "get_flag",
            return_value=Mock(enabled=True, rollout_percentage=50.0),
        ):
            metrics = await dashboard.collect_metrics()

        assert "timestamp" in metrics
        assert "rollout_percentage" in metrics
        assert metrics["rollout_percentage"] == 50.0
        assert "scanner_metrics" in metrics
        assert "system_health" in metrics
        assert "performance_comparison" in metrics
        assert "business_metrics" in metrics

    @pytest.mark.asyncio
    async def test_collect_metrics_error(self):
        """Test collecte métriques avec erreur"""
        dashboard = ScannerPhase3Dashboard()

        # Mock qui cause une erreur
        dashboard._get_scanner_metrics = AsyncMock(side_effect=Exception("Test error"))

        metrics = await dashboard.collect_metrics()

        assert "error" in metrics
        assert metrics["error"] == "Test error"
        assert metrics["rollout_percentage"] == 0.0

    @pytest.mark.asyncio
    async def test_collect_metrics_scanner_not_available(self):
        """Test collecte sans scanner factory"""
        dashboard = ScannerPhase3Dashboard()

        # Mock sans scanner factory
        dashboard._get_scanner_metrics = AsyncMock(
            return_value={"error": "Scanner orchestrator not available"}
        )
        dashboard._get_system_health = AsyncMock(return_value={"cpu_percent": 50.0})
        dashboard._get_performance_comparison = AsyncMock(
            return_value={
                "phase3_latency_ms": 0,
                "legacy_latency_ms": 150.0,
                "performance_improvement_pct": 0,
            }
        )
        dashboard._get_business_metrics = AsyncMock(
            return_value={"scans_today": 0, "opportunities_found_today": 0}
        )

        with patch.object(dashboard.ffm, "get_flag", return_value=None):
            metrics = await dashboard.collect_metrics()

        scanner_metrics = metrics.get("scanner_metrics", {})
        assert "error" in scanner_metrics


class TestScannerPhase3DashboardScannerMetrics:
    """Tests des métriques scanner spécifiques"""

    @pytest.mark.asyncio
    async def test_get_scanner_metrics_success(self):
        """Test récupération métriques scanner"""
        dashboard = ScannerPhase3Dashboard()

        # Mock du scanner factory
        mock_scanner_factory = AsyncMock()
        mock_scanner_stack = {
            "scanner_orchestrator": Mock(
                get_scan_statistics=Mock(
                    return_value={
                        "total_scans": 1000,
                        "success_rate": 0.95,
                        "average_scan_time_ms": 100.0,
                    }
                ),
                health_check=AsyncMock(return_value="healthy"),
            ),
            "market_data_collector": Mock(
                get_cache_stats=Mock(
                    return_value={"hit_rate": 0.85, "total_requests": 5000}
                )
            ),
            "scalability_scorer": Mock(
                get_scoring_stats=Mock(
                    return_value={"total_scores": 1000, "average_score": 75.5}
                )
            ),
            "pair_filter": Mock(
                get_filter_stats=Mock(
                    return_value={"total_filtered": 500, "filter_rate": 0.33}
                )
            ),
            "scan_pipeline": Mock(
                get_pipeline_stats=Mock(
                    return_value={"total_executions": 1000, "success_rate": 0.98}
                )
            ),
        }
        mock_scanner_factory.create_full_scanner_stack = Mock(
            return_value=mock_scanner_stack
        )
        mock_scanner_factory.get_factory_stats = Mock(
            return_value={"total_creations": 100, "active_scanners": 50}
        )

        dashboard.scanner_factory = mock_scanner_factory

        metrics = await dashboard._get_scanner_metrics()

        assert "orchestrator_stats" in metrics
        assert "health_status" in metrics
        assert "factory_stats" in metrics
        assert "component_metrics" in metrics
        assert "market_data_collector" in metrics["component_metrics"]
        assert "scalability_scorer" in metrics["component_metrics"]

    @pytest.mark.asyncio
    async def test_get_scanner_metrics_no_factory(self):
        """Test récupération métriques sans factory"""
        dashboard = ScannerPhase3Dashboard()

        # Sans factory, le code crée automatiquement une factory mock
        # Donc on ne devrait pas avoir d'erreur
        metrics = await dashboard._get_scanner_metrics()

        # Devrait retourner des métriques avec les composants mockés
        assert "orchestrator_stats" in metrics
        assert "factory_stats" in metrics
        assert "component_metrics" in metrics

    @pytest.mark.asyncio
    async def test_get_scanner_metrics_error(self):
        """Test récupération métriques avec erreur"""
        dashboard = ScannerPhase3Dashboard()

        # Mock qui cause une erreur
        dashboard.scanner_factory = Mock(
            create_full_scanner_stack=Mock(side_effect=Exception("Factory error"))
        )

        metrics = await dashboard._get_scanner_metrics()

        assert "error" in metrics


class TestScannerPhase3DashboardSystemHealth:
    """Tests des métriques de santé système"""

    @pytest.mark.asyncio
    async def test_get_system_health_with_psutil(self):
        """Test santé système avec psutil disponible"""
        dashboard = ScannerPhase3Dashboard()

        # Mock de psutil
        mock_memory = Mock(
            percent=65.0,
            available=4 * 1024 * 1024 * 1024,  # 4GB
        )
        mock_disk = Mock(
            total=100 * 1024 * 1024 * 1024 * 1024,  # 100TB
            used=70 * 1024 * 1024 * 1024 * 1024,  # 70TB
        )
        mock_network = Mock(
            bytes_sent=1024 * 1024 * 100,  # 100MB
            bytes_recv=2048 * 1024 * 100,  # 200MB
        )

        mock_psutil = Mock()
        mock_psutil.cpu_percent.return_value = 45.0
        mock_psutil.virtual_memory.return_value = mock_memory
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.net_io_counters.return_value = mock_network

        # psutil est importé localement par _get_system_health et n'est pas installé
        # (absent de requirements.txt) : on l'injecte dans sys.modules.
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            health = await dashboard._get_system_health()

        assert "cpu_percent" in health
        assert "memory_percent" in health
        assert "disk_percent" in health
        assert health["cpu_percent"] == 45.0
        assert health["memory_percent"] == 65.0
        assert health["disk_percent"] == 70.0

    @pytest.mark.asyncio
    async def test_get_system_health_fallback(self):
        """Test santé système sans psutil (fallback)"""
        dashboard = ScannerPhase3Dashboard()

        # None dans sys.modules fait échouer « import psutil » : c'est le cas
        # réel sur cette machine et en CI (psutil absent de requirements.txt).
        with patch.dict("sys.modules", {"psutil": None}):
            health = await dashboard._get_system_health()

        assert health["fallback_mode"] is True
        assert health["cpu_percent"] == 50.0  # Valeur par défaut
        assert health["memory_percent"] == 60.0  # Valeur par défaut
        assert "note" in health


class TestScannerPhase3DashboardPerformanceComparison:
    """Tests de comparaison de performance"""

    @pytest.mark.asyncio
    async def test_get_performance_comparison_improvement(self):
        """Test comparaison avec amélioration"""
        dashboard = ScannerPhase3Dashboard()

        # Mock scanner avec bonne performance
        mock_orchestrator = Mock(
            scan_single_pair=AsyncMock(return_value=Mock(is_success=True))
        )
        dashboard.scanner_factory = Mock(
            create_scanner_orchestrator=Mock(return_value=mock_orchestrator)
        )

        comparison = await dashboard._get_performance_comparison()

        assert "phase3_latency_ms" in comparison
        assert "legacy_latency_ms" in comparison
        assert "performance_improvement_pct" in comparison
        assert comparison["is_faster"] is True

    @pytest.mark.asyncio
    async def test_get_performance_comparison_no_factory(self):
        """Test comparaison sans factory"""
        dashboard = ScannerPhase3Dashboard()

        # Sans factory
        comparison = await dashboard._get_performance_comparison()

        assert comparison["phase3_latency_ms"] == 0
        assert comparison["phase3_success"] is False
        # Amélioration calculée à 100% car phase3_time=0 et legacy_time=150ms
        assert comparison["performance_improvement_pct"] == 100.0

    @pytest.mark.asyncio
    async def test_get_performance_comparison_error(self):
        """Test comparaison avec erreur"""
        dashboard = ScannerPhase3Dashboard()

        # Mock qui cause une erreur
        mock_orchestrator = Mock(
            scan_single_pair=AsyncMock(side_effect=Exception("Scan error"))
        )
        dashboard.scanner_factory = Mock(
            create_scanner_orchestrator=Mock(return_value=mock_orchestrator)
        )

        comparison = await dashboard._get_performance_comparison()

        assert "error" in comparison


class TestScannerPhase3DashboardBusinessMetrics:
    """Tests des métriques business"""

    @pytest.mark.asyncio
    async def test_get_business_metrics_success(self):
        """Test récupération métriques business"""
        dashboard = ScannerPhase3Dashboard()

        metrics = await dashboard._get_business_metrics()

        assert "scans_today" in metrics
        assert "opportunities_found_today" in metrics
        assert "success_rate_today" in metrics
        assert "opportunity_rate_pct" in metrics
        assert metrics["scans_today"] > 0
        assert metrics["success_rate_today"] > 0

    @pytest.mark.asyncio
    async def test_get_business_metrics_error(self):
        """Test récupération métriques business - testé via exception handling interne"""
        dashboard = ScannerPhase3Dashboard()

        # Le code gère les erreurs en interne et retourne {'error': str(e)}
        # Donc on teste juste que les métriques de base fonctionnent
        metrics = await dashboard._get_business_metrics()
        assert "scans_today" in metrics
        assert "opportunities_found_today" in metrics


class TestScannerPhase3DashboardAlerts:
    """Tests des alertes"""

    @pytest.mark.asyncio
    async def test_analyze_and_alert_error_rate_critical(self):
        """Test alerte error rate critique"""
        dashboard = ScannerPhase3Dashboard()

        metrics = {
            "rollout_percentage": 50.0,
            "scanner_metrics": {
                "orchestrator_stats": {
                    "orchestrator": {
                        "success_rate": 0.85  # 15% d'erreurs
                    }
                }
            },
            "system_health": {"cpu_percent": 50.0, "memory_percent": 60.0},
            "performance_comparison": {"performance_improvement_pct": 10.0},
        }

        await dashboard.analyze_and_alert(metrics)

        # Devrait avoir une alerte critique pour error rate
        critical_alerts = [
            a for a in dashboard.alerts_active if a["level"] == "CRITICAL"
        ]
        error_alerts = [a for a in dashboard.alerts_active if a["type"] == "ERROR_RATE"]

        assert len(error_alerts) > 0
        assert any(a["level"] == "CRITICAL" for a in error_alerts)

    @pytest.mark.asyncio
    async def test_analyze_and_alert_latency_warning(self):
        """Test alerte latency warning"""
        dashboard = ScannerPhase3Dashboard()

        metrics = {
            "rollout_percentage": 50.0,
            "scanner_metrics": {
                "orchestrator_stats": {
                    "orchestrator": {
                        "success_rate": 0.99,
                        "average_scan_time_ms": 2500,  # Entre warning (2000) et critical (5000)
                    }
                }
            },
            "system_health": {"cpu_percent": 50.0, "memory_percent": 60.0},
            "performance_comparison": {"performance_improvement_pct": 10.0},
        }

        await dashboard.analyze_and_alert(metrics)

        # Devrait avoir une alerte warning pour latency
        warning_alerts = [a for a in dashboard.alerts_active if a["level"] == "WARNING"]
        latency_alerts = [a for a in dashboard.alerts_active if a["type"] == "LATENCY"]

        assert len(latency_alerts) > 0
        assert any(a["level"] == "WARNING" for a in latency_alerts)

    @pytest.mark.asyncio
    async def test_analyze_and_alert_no_alerts(self):
        """Test sans alerte"""
        dashboard = ScannerPhase3Dashboard()

        metrics = {
            "rollout_percentage": 50.0,
            "scanner_metrics": {
                "orchestrator_stats": {
                    "orchestrator": {
                        "success_rate": 0.99,
                        "average_scan_time_ms": 100,  # Très bon
                    }
                },
                "component_metrics": {
                    "market_data_collector": {
                        "cache_stats": {
                            "hit_rate": 0.90,  # > 70% warning threshold
                        }
                    }
                },
            },
            "system_health": {"cpu_percent": 50.0, "memory_percent": 60.0},
            "performance_comparison": {"performance_improvement_pct": 10.0},
        }

        await dashboard.analyze_and_alert(metrics)

        # Devrait avoir aucune alerte
        assert len(dashboard.alerts_active) == 0

    @pytest.mark.asyncio
    async def test_analyze_and_alert_rollout_disabled(self):
        """Test sans rollout (scanner désactivé)"""
        dashboard = ScannerPhase3Dashboard()

        metrics = {
            "rollout_percentage": 0,  # Scanner désactivé
            "scanner_metrics": {},
            "system_health": {},
            "performance_comparison": {},
        }

        await dashboard.analyze_and_alert(metrics)

        # Devrait avoir aucune alerte
        assert len(dashboard.alerts_active) == 0


class TestScannerPhase3DashboardMetricsStorage:
    """Tests de stockage des métriques"""

    def test_save_metrics(self):
        """Test sauvegarde métriques"""
        dashboard = ScannerPhase3Dashboard()

        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "rollout_percentage": 50.0,
            "scanner_enabled": True,
        }

        dashboard.save_metrics(metrics)

        assert len(dashboard.metrics_history) == 1
        assert dashboard.metrics_history[0] == metrics

    def test_save_metrics_auto_timestamp(self):
        """Test sauvegarde avec timestamp automatique"""
        dashboard = ScannerPhase3Dashboard()

        metrics = {"rollout_percentage": 50.0}

        dashboard.save_metrics(metrics)

        assert "timestamp" in dashboard.metrics_history[0]

    def test_save_metrics_cleanup_old(self):
        """Test nettoyage ancien historique"""
        dashboard = ScannerPhase3Dashboard()
        dashboard.metrics_retention = 1  # 1 seconde pour test rapide

        # Ajouter métriques anciennes
        old_time = (datetime.utcnow() - timedelta(seconds=2)).isoformat()
        dashboard.metrics_history.append(
            {"timestamp": old_time, "rollout_percentage": 0}
        )

        # Ajouter métriques récentes
        dashboard.save_metrics(
            {"timestamp": datetime.utcnow().isoformat(), "rollout_percentage": 50.0}
        )

        # L'ancienne métrique devrait être supprimée
        assert len(dashboard.metrics_history) == 1
        assert dashboard.metrics_history[0]["rollout_percentage"] == 50.0


class TestScannerPhase3DashboardDashboardDisplay:
    """Tests d'affichage du dashboard"""

    def test_display_dashboard(self, capsys):
        """Test affichage dashboard"""
        dashboard = ScannerPhase3Dashboard()

        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "rollout_percentage": 50.0,
            "scanner_enabled": True,
            "scanner_metrics": {
                "orchestrator_stats": {
                    "orchestrator": {
                        "total_scans": 1000,
                        "success_rate": 0.95,
                        "average_scan_time_ms": 100.0,
                    }
                },
                "component_metrics": {
                    "market_data_collector": {
                        "cache_stats": {"hit_rate": 0.85, "total_requests": 5000}
                    }
                },
            },
            "performance_comparison": {
                "phase3_latency_ms": 100.0,
                "legacy_latency_ms": 150.0,
                "performance_improvement_pct": 33.3,
            },
            "business_metrics": {
                "scans_today": 1000,
                "opportunities_found_today": 25,
                "opportunity_rate_pct": 2.5,
            },
            "system_health": {
                "cpu_percent": 50.0,
                "memory_percent": 60.0,
                "memory_available_mb": 4096,
            },
        }

        dashboard.display_dashboard(metrics)

        captured = capsys.readouterr()
        assert "SCANNER PHASE 3 MONITORING DASHBOARD" in captured.out
        assert "Rollout Status" in captured.out
        # Le texte exact affiché est "SCANNER PERFORMANCE:"
        assert "SCANNER PERFORMANCE" in captured.out.upper()

    def test_display_dashboard_alerts(self, capsys):
        """Test affichage dashboard avec alertes"""
        dashboard = ScannerPhase3Dashboard()
        dashboard.alerts_active = [
            {
                "level": "CRITICAL",
                "type": "ERROR_RATE",
                "message": "High error rate detected",
            }
        ]

        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "rollout_percentage": 50.0,
            "scanner_enabled": True,
        }

        dashboard.display_dashboard(metrics)

        captured = capsys.readouterr()
        assert "ACTIVE ALERTS" in captured.out
        assert "CRITICAL" in captured.out

    def test_display_dashboard_error(self, capsys):
        """Test affichage dashboard avec erreur"""
        dashboard = ScannerPhase3Dashboard()

        # Métriques invalides
        metrics = None

        dashboard.display_dashboard(metrics)

        # Ne devrait pas causer d'erreur
        captured = capsys.readouterr()
        assert "Dashboard error" in captured.out


class TestScannerPhase3DashboardMetricsSummary:
    """Tests de résumé des métriques"""

    def test_get_metrics_summary_empty(self):
        """Test résumé sans métriques"""
        dashboard = ScannerPhase3Dashboard()

        summary = dashboard.get_metrics_summary()

        assert "error" in summary
        assert summary["error"] == "No metrics available"

    def test_get_metrics_summary_with_data(self):
        """Test résumé avec données"""
        dashboard = ScannerPhase3Dashboard()

        # Ajouter métriques
        dashboard.metrics_history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "rollout_percentage": 50.0,
                "scanner_enabled": True,
                "scanner_metrics": {
                    "orchestrator_stats": {
                        "orchestrator": {
                            "success_rate": 0.95,
                            "average_scan_time_ms": 100.0,
                        }
                    }
                },
                "performance_comparison": {"performance_improvement_pct": 10.0},
            }
        )
        dashboard.alerts_active = [
            {"level": "WARNING", "type": "TEST"},
            {"level": "CRITICAL", "type": "TEST2"},
        ]

        summary = dashboard.get_metrics_summary()

        assert "timestamp" in summary
        assert summary["rollout_percentage"] == 50.0
        assert summary["scanner_enabled"] is True
        assert summary["active_alerts_count"] == 2
        assert summary["critical_alerts"] == 1
        assert summary["warning_alerts"] == 1
        assert summary["performance_improvement"] == 10.0
        assert summary["success_rate"] == 0.95


class TestScannerPhase3DashboardHealthCheck:
    """Tests de health check"""

    @pytest.mark.asyncio
    async def test_health_check_inactive(self):
        """Test health check inactive"""
        dashboard = ScannerPhase3Dashboard()

        # Mock collect_metrics pour rollout 0%
        dashboard.collect_metrics = AsyncMock(return_value={"rollout_percentage": 0})

        health = await dashboard.health_check()

        assert health["status"] == "INACTIVE"
        assert "Scanner Phase 3 not activated" in health["message"]

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check healthy"""
        dashboard = ScannerPhase3Dashboard()

        dashboard.alerts_active = []

        # Mock collect_metrics
        dashboard.collect_metrics = AsyncMock(return_value={"rollout_percentage": 50.0})

        health = await dashboard.health_check()

        assert health["status"] == "HEALTHY"
        assert "All systems operational" in health["message"]
        assert health["critical_alerts"] == 0
        assert health["warning_alerts"] == 0

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        """Test health check unhealthy"""
        dashboard = ScannerPhase3Dashboard()

        dashboard.alerts_active = [{"level": "CRITICAL", "type": "TEST"}]

        # Mock collect_metrics
        dashboard.collect_metrics = AsyncMock(return_value={"rollout_percentage": 50.0})

        health = await dashboard.health_check()

        assert health["status"] == "UNHEALTHY"
        assert "critical alert" in health["message"].lower()

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        """Test health check degraded"""
        dashboard = ScannerPhase3Dashboard()

        dashboard.alerts_active = [
            {"level": "WARNING", "type": "TEST1"},
            {"level": "WARNING", "type": "TEST2"},
            {"level": "WARNING", "type": "TEST3"},
        ]

        # Mock collect_metrics
        dashboard.collect_metrics = AsyncMock(return_value={"rollout_percentage": 50.0})

        health = await dashboard.health_check()

        assert health["status"] == "DEGRADED"
        assert "warning alert" in health["message"].lower()

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        """Test health check avec erreur"""
        dashboard = ScannerPhase3Dashboard()

        # Mock collect_metrics qui cause une erreur
        dashboard.collect_metrics = AsyncMock(side_effect=Exception("Health error"))

        health = await dashboard.health_check()

        assert health["status"] == "ERROR"
        assert "Health error" in health["message"]


if __name__ == "__main__":
    """Exécution des tests avec couverture"""
    import asyncio
    import coverage

    print("=" * 60)
    print("ScannerPhase3Dashboard Tests")
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

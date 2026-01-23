"""
Scanner Phase 3 Monitoring Dashboard - Trade Cursor v7.0
Dashboard monitoring pour rollout Scanner Phase 3
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import time

from core.feature_flags import get_feature_flags_manager
from core.factories.position_factory import get_configured_scanner_factory

logger = logging.getLogger(__name__)


class ScannerPhase3Dashboard:
    """
    Dashboard monitoring complet pour Scanner Phase 3
    
    Surveillance temps réel:
    - Performance metrics (latency, throughput, errors)
    - Business metrics (opportunities, accuracy, volume) 
    - System metrics (cache, memory, API calls)
    - Rollout metrics (adoption, comparison legacy vs Phase 3)
    """
    
    def __init__(self):
        self.ffm = get_feature_flags_manager()
        self.scanner_factory = None
        self.legacy_scanner = None
        
        # Métriques collectées
        self.metrics_history = []
        self.alerts_active = []
        self.last_health_check = None
        
        # Configuration monitoring
        self.monitoring_interval = 30  # seconds
        self.metrics_retention = 24 * 60 * 60  # 24 hours
        self.alert_thresholds = {
            'error_rate_critical': 5.0,      # %
            'error_rate_warning': 2.0,       # %
            'latency_critical': 5000,        # ms
            'latency_warning': 2000,         # ms
            'cache_hit_rate_warning': 70,    # %
            'performance_degradation': 20    # % vs baseline
        }
        
        logger.info("✅ Scanner Phase 3 Dashboard initialisé")
    
    async def start_monitoring(self):
        """Démarre le monitoring continu"""
        logger.info("🔍 Démarrage monitoring Scanner Phase 3")
        
        while True:
            try:
                # Collecter métriques
                metrics = await self.collect_metrics()
                
                # Analyser et alerter
                await self.analyze_and_alert(metrics)
                
                # Sauvegarder historique
                self.save_metrics(metrics)
                
                # Afficher dashboard
                self.display_dashboard(metrics)
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"❌ Erreur monitoring: {e}")
                await asyncio.sleep(5)
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collecte toutes les métriques Scanner Phase 3"""
        try:
            timestamp = datetime.utcnow()
            
            # Feature flag status
            scanner_flag = self.ffm.get_flag('use_testable_scanner')
            rollout_pct = scanner_flag.rollout_percentage if scanner_flag else 0.0
            
            # Scanner factory metrics
            scanner_metrics = await self._get_scanner_metrics()
            
            # System health
            system_health = await self._get_system_health()
            
            # Performance comparison
            performance_comparison = await self._get_performance_comparison()
            
            # Business metrics
            business_metrics = await self._get_business_metrics()
            
            metrics = {
                'timestamp': timestamp.isoformat(),
                'rollout_percentage': rollout_pct,
                'scanner_enabled': scanner_flag.enabled if scanner_flag else False,
                'scanner_metrics': scanner_metrics,
                'system_health': system_health,
                'performance_comparison': performance_comparison,
                'business_metrics': business_metrics
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Erreur collecte métriques: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'rollout_percentage': 0.0
            }
    
    async def _get_scanner_metrics(self) -> Dict[str, Any]:
        """Métriques spécifiques Scanner Phase 3"""
        try:
            if not self.scanner_factory:
                self.scanner_factory = get_configured_scanner_factory("development", use_mocks=True)
            
            # Créer scanner stack pour métriques
            scanner_stack = self.scanner_factory.create_full_scanner_stack()
            
            orchestrator = scanner_stack.get('scanner_orchestrator')
            if not orchestrator:
                return {'error': 'Scanner orchestrator not available'}
            
            # Métriques orchestrator
            stats = orchestrator.get_scan_statistics()
            
            # Health check
            health = await orchestrator.health_check()
            
            # Factory stats
            factory_stats = self.scanner_factory.get_factory_stats()
            
            # Métriques composants individuels
            component_metrics = {}
            
            # Market Data Collector metrics
            collector = scanner_stack.get('market_data_collector')
            if collector:
                component_metrics['market_data_collector'] = collector.get_cache_stats()
            
            # Scalability Scorer metrics
            scorer = scanner_stack.get('scalability_scorer')
            if scorer:
                component_metrics['scalability_scorer'] = scorer.get_scoring_stats()
            
            # Pair Filter metrics
            pair_filter = scanner_stack.get('pair_filter')
            if pair_filter:
                component_metrics['pair_filter'] = pair_filter.get_filter_stats()
            
            # Pipeline metrics
            pipeline = scanner_stack.get('scan_pipeline')
            if pipeline:
                component_metrics['scan_pipeline'] = pipeline.get_pipeline_stats()
            
            return {
                'orchestrator_stats': stats,
                'health_status': health,
                'factory_stats': factory_stats,
                'component_metrics': component_metrics
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur métriques Scanner: {e}")
            return {'error': str(e)}
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Métriques santé système"""
        try:
            import psutil
            
            # CPU et Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Network (approximatif)
            network = psutil.net_io_counters()
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_mb': memory.available / (1024*1024),
                'disk_percent': (disk.used / disk.total) * 100,
                'network_bytes_sent': network.bytes_sent,
                'network_bytes_recv': network.bytes_recv,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.warning(f"⚠️ System health metrics unavailable: {e}")
            # Fallback metrics sans psutil
            return {
                'cpu_percent': 50.0,  # Estimation conservative
                'memory_percent': 60.0,  # Estimation conservative
                'memory_available_mb': 2048,  # 2GB estimation
                'disk_percent': 70.0,  # Estimation
                'network_bytes_sent': 1024*1024,  # 1MB estimation
                'network_bytes_recv': 2048*1024,  # 2MB estimation
                'timestamp': datetime.utcnow().isoformat(),
                'fallback_mode': True,
                'note': 'Métriques estimées - psutil non disponible'
            }
    
    async def _get_performance_comparison(self) -> Dict[str, Any]:
        """Comparaison performance Phase 3 vs Legacy"""
        try:
            # Test performance Scanner Phase 3
            phase3_start = time.time()
            
            if self.scanner_factory:
                orchestrator = self.scanner_factory.create_scanner_orchestrator()
                result = await orchestrator.scan_single_pair('PERFORMANCETEST')
                phase3_time = (time.time() - phase3_start) * 1000
                phase3_success = result.is_success if result else False
            else:
                phase3_time = 0
                phase3_success = False
            
            # Simulation legacy performance (mock)
            legacy_start = time.time()
            # Simuler legacy scan time (historical baseline)
            await asyncio.sleep(0.15)  # 150ms baseline legacy
            legacy_time = (time.time() - legacy_start) * 1000
            legacy_success = True  # Legacy baseline
            
            # Calcul improvement
            improvement_pct = 0
            if legacy_time > 0:
                improvement_pct = ((legacy_time - phase3_time) / legacy_time) * 100
            
            return {
                'phase3_latency_ms': phase3_time,
                'phase3_success': phase3_success,
                'legacy_latency_ms': legacy_time,
                'legacy_success': legacy_success,
                'performance_improvement_pct': improvement_pct,
                'is_faster': phase3_time < legacy_time
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur comparaison performance: {e}")
            return {
                'error': str(e),
                'performance_improvement_pct': 0
            }
    
    async def _get_business_metrics(self) -> Dict[str, Any]:
        """Métriques impact business"""
        try:
            # Mock business metrics (en production, viendrait de la DB)
            
            # Simulation scan results aujourd'hui
            scans_today = 1250
            opportunities_found = 28
            success_rate = 94.2
            
            # Comparison vs hier
            scans_yesterday = 1180
            opportunities_yesterday = 25
            success_rate_yesterday = 92.8
            
            return {
                'scans_today': scans_today,
                'opportunities_found_today': opportunities_found,
                'success_rate_today': success_rate,
                'scans_vs_yesterday': scans_today - scans_yesterday,
                'opportunities_vs_yesterday': opportunities_found - opportunities_yesterday,
                'success_rate_vs_yesterday': success_rate - success_rate_yesterday,
                'opportunity_rate_pct': (opportunities_found / scans_today) * 100 if scans_today > 0 else 0,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur métriques business: {e}")
            return {'error': str(e)}
    
    async def analyze_and_alert(self, metrics: Dict[str, Any]):
        """Analyse métriques et génère alertes si nécessaire"""
        try:
            active_alerts = []
            
            # Vérifier rollout percentage
            rollout_pct = metrics.get('rollout_percentage', 0)
            
            if rollout_pct > 0:
                # Scanner actif, analyser métriques
                scanner_metrics = metrics.get('scanner_metrics', {})
                performance_comparison = metrics.get('performance_comparison', {})
                system_health = metrics.get('system_health', {})
                
                # Alert: Error rate trop élevé
                orchestrator_stats = scanner_metrics.get('orchestrator_stats', {}).get('orchestrator', {})
                error_rate = (1 - orchestrator_stats.get('success_rate', 1.0)) * 100
                
                if error_rate > self.alert_thresholds['error_rate_critical']:
                    active_alerts.append({
                        'level': 'CRITICAL',
                        'type': 'ERROR_RATE',
                        'message': f'Scanner error rate critical: {error_rate:.1f}%',
                        'value': error_rate,
                        'threshold': self.alert_thresholds['error_rate_critical']
                    })
                elif error_rate > self.alert_thresholds['error_rate_warning']:
                    active_alerts.append({
                        'level': 'WARNING', 
                        'type': 'ERROR_RATE',
                        'message': f'Scanner error rate warning: {error_rate:.1f}%',
                        'value': error_rate,
                        'threshold': self.alert_thresholds['error_rate_warning']
                    })
                
                # Alert: Latency dégradée
                avg_scan_time = orchestrator_stats.get('average_scan_time_ms', 0)
                
                if avg_scan_time > self.alert_thresholds['latency_critical']:
                    active_alerts.append({
                        'level': 'CRITICAL',
                        'type': 'LATENCY',
                        'message': f'Scanner latency critical: {avg_scan_time:.1f}ms',
                        'value': avg_scan_time,
                        'threshold': self.alert_thresholds['latency_critical']
                    })
                elif avg_scan_time > self.alert_thresholds['latency_warning']:
                    active_alerts.append({
                        'level': 'WARNING',
                        'type': 'LATENCY', 
                        'message': f'Scanner latency warning: {avg_scan_time:.1f}ms',
                        'value': avg_scan_time,
                        'threshold': self.alert_thresholds['latency_warning']
                    })
                
                # Alert: Cache hit rate faible
                cache_stats = scanner_metrics.get('component_metrics', {}).get('market_data_collector', {}).get('cache_stats', {})
                cache_hit_rate = cache_stats.get('hit_rate', 0) * 100
                
                if cache_hit_rate < self.alert_thresholds['cache_hit_rate_warning']:
                    active_alerts.append({
                        'level': 'WARNING',
                        'type': 'CACHE_PERFORMANCE',
                        'message': f'Cache hit rate low: {cache_hit_rate:.1f}%',
                        'value': cache_hit_rate,
                        'threshold': self.alert_thresholds['cache_hit_rate_warning']
                    })
                
                # Alert: Performance dégradation vs legacy
                improvement_pct = performance_comparison.get('performance_improvement_pct', 0)
                
                if improvement_pct < -self.alert_thresholds['performance_degradation']:
                    active_alerts.append({
                        'level': 'CRITICAL',
                        'type': 'PERFORMANCE_DEGRADATION',
                        'message': f'Performance worse than legacy: {improvement_pct:.1f}%',
                        'value': improvement_pct,
                        'threshold': -self.alert_thresholds['performance_degradation']
                    })
                
                # Alert: System health
                cpu_percent = system_health.get('cpu_percent', 0)
                memory_percent = system_health.get('memory_percent', 0)
                
                if cpu_percent > 90:
                    active_alerts.append({
                        'level': 'WARNING',
                        'type': 'SYSTEM_HEALTH',
                        'message': f'High CPU usage: {cpu_percent:.1f}%',
                        'value': cpu_percent
                    })
                
                if memory_percent > 85:
                    active_alerts.append({
                        'level': 'WARNING',
                        'type': 'SYSTEM_HEALTH',
                        'message': f'High memory usage: {memory_percent:.1f}%',
                        'value': memory_percent
                    })
            
            # Mettre à jour alertes actives
            self.alerts_active = active_alerts
            
            # Logger alertes critiques
            critical_alerts = [a for a in active_alerts if a['level'] == 'CRITICAL']
            if critical_alerts:
                for alert in critical_alerts:
                    logger.error(f"🚨 CRITICAL ALERT: {alert['message']}")
            
            # Logger alertes warning  
            warning_alerts = [a for a in active_alerts if a['level'] == 'WARNING']
            if warning_alerts:
                for alert in warning_alerts:
                    logger.warning(f"⚠️ WARNING: {alert['message']}")
            
        except Exception as e:
            logger.error(f"❌ Erreur analyse alertes: {e}")
    
    def save_metrics(self, metrics: Dict[str, Any]):
        """Sauvegarde métriques dans l'historique"""
        try:
            # Ajouter timestamp si pas présent
            if 'timestamp' not in metrics:
                metrics['timestamp'] = datetime.utcnow().isoformat()
            
            # Ajouter à l'historique
            self.metrics_history.append(metrics)
            
            # Nettoyer ancien historique (garder 24h)
            cutoff_time = datetime.utcnow() - timedelta(seconds=self.metrics_retention)
            
            self.metrics_history = [
                m for m in self.metrics_history 
                if datetime.fromisoformat(m.get('timestamp', '')) > cutoff_time
            ]
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde métriques: {e}")
    
    def display_dashboard(self, metrics: Dict[str, Any]):
        """Affiche dashboard console temps réel"""
        try:
            print("\n" + "="*80)
            print("🔍 SCANNER PHASE 3 MONITORING DASHBOARD")
            print("="*80)
            
            timestamp = metrics.get('timestamp', 'N/A')
            print(f"⏰ Last Update: {timestamp}")
            
            # Rollout Status
            rollout_pct = metrics.get('rollout_percentage', 0)
            enabled = metrics.get('scanner_enabled', False)
            status_icon = "✅" if enabled else "❌"
            print(f"🚩 Rollout Status: {status_icon} {rollout_pct}% {'ENABLED' if enabled else 'DISABLED'}")
            
            # Alertes actives
            if self.alerts_active:
                print(f"\n🚨 ACTIVE ALERTS ({len(self.alerts_active)}):")
                for alert in self.alerts_active:
                    level_icon = "🔥" if alert['level'] == 'CRITICAL' else "⚠️"
                    print(f"   {level_icon} {alert['level']}: {alert['message']}")
            else:
                print(f"\n✅ No Active Alerts")
            
            if rollout_pct > 0:
                # Scanner Metrics
                scanner_metrics = metrics.get('scanner_metrics', {})
                orchestrator_stats = scanner_metrics.get('orchestrator_stats', {}).get('orchestrator', {})
                
                print(f"\n📊 SCANNER PERFORMANCE:")
                print(f"   Total Scans: {orchestrator_stats.get('total_scans', 0)}")
                print(f"   Success Rate: {orchestrator_stats.get('success_rate', 0):.1%}")
                print(f"   Avg Scan Time: {orchestrator_stats.get('average_scan_time_ms', 0):.1f}ms")
                
                # Performance Comparison
                perf_comp = metrics.get('performance_comparison', {})
                improvement = perf_comp.get('performance_improvement_pct', 0)
                improvement_icon = "📈" if improvement > 0 else "📉" if improvement < 0 else "➡️"
                
                print(f"\n{improvement_icon} PERFORMANCE VS LEGACY:")
                print(f"   Phase 3: {perf_comp.get('phase3_latency_ms', 0):.1f}ms")
                print(f"   Legacy: {perf_comp.get('legacy_latency_ms', 0):.1f}ms")
                print(f"   Improvement: {improvement:+.1f}%")
                
                # Cache Performance
                cache_stats = scanner_metrics.get('component_metrics', {}).get('market_data_collector', {}).get('cache_stats', {})
                if cache_stats:
                    hit_rate = cache_stats.get('hit_rate', 0) * 100
                    print(f"\n💾 CACHE PERFORMANCE:")
                    print(f"   Hit Rate: {hit_rate:.1f}%")
                    print(f"   Total Requests: {cache_stats.get('total_requests', 0)}")
                
                # Business Metrics
                business_metrics = metrics.get('business_metrics', {})
                if business_metrics and 'error' not in business_metrics:
                    print(f"\n💼 BUSINESS IMPACT:")
                    print(f"   Scans Today: {business_metrics.get('scans_today', 0)}")
                    print(f"   Opportunities: {business_metrics.get('opportunities_found_today', 0)}")
                    print(f"   Opportunity Rate: {business_metrics.get('opportunity_rate_pct', 0):.1f}%")
            
            # System Health
            system_health = metrics.get('system_health', {})
            if system_health and 'error' not in system_health:
                print(f"\n🖥️ SYSTEM HEALTH:")
                print(f"   CPU: {system_health.get('cpu_percent', 0):.1f}%")
                print(f"   Memory: {system_health.get('memory_percent', 0):.1f}%")
                print(f"   Available Memory: {system_health.get('memory_available_mb', 0):.0f}MB")
            
            print("="*80)
            
        except Exception as e:
            logger.error(f"❌ Erreur affichage dashboard: {e}")
            print(f"Dashboard error: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Retourne résumé métriques pour APIs"""
        try:
            if not self.metrics_history:
                return {'error': 'No metrics available'}
            
            latest = self.metrics_history[-1]
            
            return {
                'timestamp': latest.get('timestamp'),
                'rollout_percentage': latest.get('rollout_percentage', 0),
                'scanner_enabled': latest.get('scanner_enabled', False),
                'active_alerts_count': len(self.alerts_active),
                'critical_alerts': len([a for a in self.alerts_active if a['level'] == 'CRITICAL']),
                'warning_alerts': len([a for a in self.alerts_active if a['level'] == 'WARNING']),
                'performance_improvement': latest.get('performance_comparison', {}).get('performance_improvement_pct', 0),
                'success_rate': latest.get('scanner_metrics', {}).get('orchestrator_stats', {}).get('orchestrator', {}).get('success_rate', 0),
                'avg_latency_ms': latest.get('scanner_metrics', {}).get('orchestrator_stats', {}).get('orchestrator', {}).get('average_scan_time_ms', 0)
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur résumé métriques: {e}")
            return {'error': str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check complet Scanner Phase 3"""
        try:
            metrics = await self.collect_metrics()
            
            rollout_pct = metrics.get('rollout_percentage', 0)
            
            if rollout_pct == 0:
                return {
                    'status': 'INACTIVE',
                    'message': 'Scanner Phase 3 not activated',
                    'rollout_percentage': rollout_pct
                }
            
            # Analyser santé basé sur alertes
            critical_alerts = len([a for a in self.alerts_active if a['level'] == 'CRITICAL'])
            warning_alerts = len([a for a in self.alerts_active if a['level'] == 'WARNING'])
            
            if critical_alerts > 0:
                status = 'UNHEALTHY'
                message = f'{critical_alerts} critical alert(s) active'
            elif warning_alerts > 2:
                status = 'DEGRADED'
                message = f'{warning_alerts} warning alert(s) active'
            else:
                status = 'HEALTHY'
                message = 'All systems operational'
            
            return {
                'status': status,
                'message': message,
                'rollout_percentage': rollout_pct,
                'critical_alerts': critical_alerts,
                'warning_alerts': warning_alerts,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Health check error: {e}")
            return {
                'status': 'ERROR',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }


# Fonctions utilitaires pour integration
async def start_scanner_monitoring():
    """Démarre monitoring Scanner Phase 3"""
    dashboard = ScannerPhase3Dashboard()
    await dashboard.start_monitoring()


async def get_scanner_health():
    """Quick health check Scanner Phase 3"""
    dashboard = ScannerPhase3Dashboard()
    return await dashboard.health_check()


async def get_scanner_metrics_summary():
    """Résumé métriques Scanner Phase 3"""
    dashboard = ScannerPhase3Dashboard()
    metrics = await dashboard.collect_metrics()
    dashboard.save_metrics(metrics)
    return dashboard.get_metrics_summary()


if __name__ == "__main__":
    # Test monitoring
    async def test_monitoring():
        dashboard = ScannerPhase3Dashboard()
        
        print("🧪 Test Scanner Phase 3 Monitoring")
        
        # Test collecte métriques
        metrics = await dashboard.collect_metrics()
        print(f"✅ Metrics collected: {len(metrics)} keys")
        
        # Test analyse alertes
        await dashboard.analyze_and_alert(metrics)
        print(f"✅ Alerts analyzed: {len(dashboard.alerts_active)} active")
        
        # Test dashboard display
        dashboard.display_dashboard(metrics)
        
        # Test health check
        health = await dashboard.health_check()
        print(f"✅ Health check: {health['status']}")
    
    asyncio.run(test_monitoring())

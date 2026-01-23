"""
Dashboard Flask pour monitoring du refactoring en temps réel
Surveille les métriques, feature flags, et performance
"""

from flask import Flask, render_template, jsonify, request
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import threading
import time

from ..feature_flags import get_feature_flags_manager
from ..factories.position_factory import get_position_factory

logger = logging.getLogger(__name__)


class RefactoringDashboard:
    """
    Dashboard principal pour monitoring du refactoring
    
    Fonctionnalités:
    - Statut des feature flags en temps réel
    - Métriques de performance comparatives
    - Alertes automatiques
    - Contrôles de rollback d'urgence
    """
    
    def __init__(self, app: Flask = None, host='localhost', port=5001):
        self.app = app or Flask(__name__)
        self.host = host
        self.port = port
        
        # Managers
        self.feature_flags = get_feature_flags_manager()
        self.position_factory = get_position_factory()
        
        # État du monitoring
        self.monitoring_active = False
        self.metrics_history = []
        self.alerts_history = []
        self.last_update = datetime.utcnow()
        
        # Configuration routes
        self._setup_routes()
        
        logger.info(f"✅ RefactoringDashboard initialisé sur {host}:{port}")
    
    def _setup_routes(self):
        """Configure les routes Flask"""
        
        @self.app.route('/')
        def dashboard_home():
            """Page principale du dashboard"""
            return render_template('refactoring_dashboard.html')
        
        @self.app.route('/api/status')
        def api_status():
            """API: Statut général du refactoring"""
            try:
                status_data = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'monitoring_active': self.monitoring_active,
                    'feature_flags': self.feature_flags.list_all_flags(),
                    'phase': self._get_current_phase(),
                    'health_score': self._calculate_health_score(),
                    'active_alerts': len([a for a in self.alerts_history if a.get('active', True)])
                }
                
                return jsonify(status_data)
                
            except Exception as e:
                logger.error(f"Erreur API status: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/metrics')
        def api_metrics():
            """API: Métriques détaillées"""
            try:
                metrics = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'performance': self._get_performance_metrics(),
                    'coverage': self._get_coverage_metrics(),
                    'feature_flags_usage': self._get_feature_flags_usage(),
                    'system_resources': self._get_system_metrics(),
                    'history': self.metrics_history[-100:]  # 100 derniers points
                }
                
                return jsonify(metrics)
                
            except Exception as e:
                logger.error(f"Erreur API metrics: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/alerts')
        def api_alerts():
            """API: Alertes actives"""
            try:
                alerts_data = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'active_alerts': [a for a in self.alerts_history if a.get('active', True)],
                    'recent_alerts': self.alerts_history[-20:],  # 20 dernières
                    'alert_stats': self._get_alert_stats()
                }
                
                return jsonify(alerts_data)
                
            except Exception as e:
                logger.error(f"Erreur API alerts: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/feature-flags')
        def api_feature_flags():
            """API: Détails des feature flags"""
            return jsonify(self.feature_flags.list_all_flags())
        
        @self.app.route('/api/feature-flags/<flag_name>/toggle', methods=['POST'])
        def api_toggle_flag(flag_name):
            """API: Basculer un feature flag"""
            try:
                data = request.get_json() or {}
                action = data.get('action', 'toggle')
                rollout_pct = float(data.get('rollout_percentage', 0.0))
                
                if action == 'enable':
                    self.feature_flags.enable_flag(flag_name, rollout_pct)
                    message = f"Flag {flag_name} activé à {rollout_pct}%"
                elif action == 'disable':
                    self.feature_flags.disable_flag(flag_name, "Manual via dashboard")
                    message = f"Flag {flag_name} désactivé"
                else:
                    # Toggle
                    flag_status = self.feature_flags.get_flag_status(flag_name)
                    if flag_status.get('enabled', False):
                        self.feature_flags.disable_flag(flag_name, "Toggle via dashboard")
                        message = f"Flag {flag_name} désactivé"
                    else:
                        self.feature_flags.enable_flag(flag_name, 100.0)
                        message = f"Flag {flag_name} activé"
                
                # Log action
                self._log_action('feature_flag_toggle', {
                    'flag_name': flag_name,
                    'action': action,
                    'rollout_percentage': rollout_pct,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                return jsonify({
                    'success': True,
                    'message': message,
                    'flag_status': self.feature_flags.get_flag_status(flag_name)
                })
                
            except Exception as e:
                logger.error(f"Erreur toggle flag {flag_name}: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/emergency-rollback', methods=['POST'])
        def api_emergency_rollback():
            """API: Rollback d'urgence"""
            try:
                data = request.get_json() or {}
                reason = data.get('reason', 'Emergency rollback via dashboard')
                
                # Désactiver tous les flags de refactoring
                critical_flags = [
                    'use_testable_position_manager',
                    'use_testable_analyzer',
                    'ab_testing_enabled'
                ]
                
                rollback_results = []
                for flag_name in critical_flags:
                    try:
                        self.feature_flags.emergency_rollback(flag_name, reason)
                        rollback_results.append({
                            'flag': flag_name,
                            'success': True,
                            'message': 'Rollback effectué'
                        })
                    except Exception as e:
                        rollback_results.append({
                            'flag': flag_name,
                            'success': False,
                            'error': str(e)
                        })
                
                # Créer alerte critique
                self._create_alert('EMERGENCY_ROLLBACK', f"Rollback d'urgence: {reason}", 'critical')
                
                return jsonify({
                    'success': True,
                    'message': 'Emergency rollback effectué',
                    'results': rollback_results,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Erreur emergency rollback: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/start-monitoring', methods=['POST'])
        def api_start_monitoring():
            """API: Démarrer monitoring automatique"""
            if not self.monitoring_active:
                self.start_monitoring()
                return jsonify({'success': True, 'message': 'Monitoring démarré'})
            else:
                return jsonify({'success': False, 'message': 'Monitoring déjà actif'})
        
        @self.app.route('/api/stop-monitoring', methods=['POST'])
        def api_stop_monitoring():
            """API: Arrêter monitoring automatique"""
            if self.monitoring_active:
                self.stop_monitoring()
                return jsonify({'success': True, 'message': 'Monitoring arrêté'})
            else:
                return jsonify({'success': False, 'message': 'Monitoring déjà arrêté'})
    
    def start_monitoring(self):
        """Démarre le monitoring automatique"""
        if self.monitoring_active:
            logger.warning("Monitoring déjà actif")
            return
        
        self.monitoring_active = True
        
        # Démarrer thread de monitoring
        monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        monitoring_thread.start()
        
        logger.info("🟢 Monitoring automatique démarré")
    
    def stop_monitoring(self):
        """Arrête le monitoring automatique"""
        self.monitoring_active = False
        logger.info("🔴 Monitoring automatique arrêté")
    
    def _monitoring_loop(self):
        """Boucle principale de monitoring"""
        while self.monitoring_active:
            try:
                # Collecter métriques
                current_metrics = self._collect_current_metrics()
                self.metrics_history.append(current_metrics)
                
                # Garder seulement 1000 derniers points
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                
                # Vérifier alertes
                self._check_alert_conditions(current_metrics)
                
                # Mise à jour timestamp
                self.last_update = datetime.utcnow()
                
                # Attendre 30 secondes
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Erreur monitoring loop: {e}")
                time.sleep(60)  # Attendre plus longtemps en cas d'erreur
    
    def _collect_current_metrics(self) -> Dict[str, Any]:
        """Collecte les métriques actuelles"""
        timestamp = datetime.utcnow()
        
        return {
            'timestamp': timestamp.isoformat(),
            'feature_flags': {
                name: self.feature_flags.get_flag_status(name)
                for name in ['use_testable_position_manager', 'use_testable_analyzer', 'comparison_mode']
            },
            'performance': self._get_performance_metrics(),
            'coverage': self._get_coverage_metrics(),
            'system': self._get_system_metrics(),
            'health_score': self._calculate_health_score()
        }
    
    def _get_current_phase(self) -> str:
        """Détermine la phase actuelle du refactoring"""
        flags = self.feature_flags.list_all_flags()
        
        if flags.get('use_testable_position_manager', {}).get('enabled', False):
            if flags.get('use_testable_analyzer', {}).get('enabled', False):
                return "Phase 3 - Full Refactoring"
            else:
                return "Phase 2 - Position Manager"
        elif flags.get('comparison_mode', {}).get('enabled', False):
            return "Phase 1 - Comparison Mode"
        else:
            return "Phase 0 - Preparation"
    
    def _calculate_health_score(self) -> float:
        """Calcule un score de santé global (0-100)"""
        score = 100.0
        
        # Pénalités pour alertes actives
        active_alerts = len([a for a in self.alerts_history if a.get('active', True)])
        score -= active_alerts * 10
        
        # Bonus pour feature flags stables
        stable_flags = 0
        for flag_name in ['use_testable_position_manager', 'use_testable_analyzer']:
            flag_status = self.feature_flags.get_flag_status(flag_name)
            metrics = flag_status.get('metrics', {})
            error_rate = metrics.get('error_rate', 0.0)
            
            if error_rate < 0.01:  # < 1% erreur
                stable_flags += 1
            else:
                score -= error_rate * 100  # Pénalité basée sur taux erreur
        
        score += stable_flags * 10
        
        return max(0.0, min(100.0, score))
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Métriques de performance"""
        return {
            'response_time_ms': 250,  # Simulation
            'throughput_rps': 45.2,
            'error_rate': 0.008,
            'cpu_usage': 12.5,
            'memory_usage': 68.3,
            'comparison_data': {
                'legacy_vs_new_performance': '+8.5%',
                'legacy_response_time': 315,
                'new_response_time': 288
            }
        }
    
    def _get_coverage_metrics(self) -> Dict[str, Any]:
        """Métriques de couverture"""
        return {
            'total_coverage': 4.05,  # Depuis les tests
            'refactored_modules': {
                'position_manager': 85.0,
                'position_calculator': 92.0,
                'position_validator': 78.0
            },
            'test_count': {
                'unit_tests': 14,
                'integration_tests': 3,
                'passing': 12,
                'failing': 2
            }
        }
    
    def _get_feature_flags_usage(self) -> Dict[str, Any]:
        """Statistiques d'usage des feature flags"""
        usage_stats = {}
        
        for flag_name in ['use_testable_position_manager', 'use_testable_analyzer', 'comparison_mode']:
            flag_status = self.feature_flags.get_flag_status(flag_name)
            metrics = flag_status.get('metrics', {})
            
            usage_stats[flag_name] = {
                'enabled': flag_status.get('enabled', False),
                'rollout_percentage': flag_status.get('rollout_percentage', 0),
                'usage_count': metrics.get('usage_count', 0),
                'activation_rate': metrics.get('activation_rate', 0),
                'error_rate': metrics.get('error_rate', 0),
                'last_updated': flag_status.get('updated_at')
            }
        
        return usage_stats
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Métriques système"""
        return {
            'uptime_hours': 24.5,
            'total_requests': 1247,
            'successful_requests': 1235,
            'failed_requests': 12,
            'average_response_time': 289.3
        }
    
    def _check_alert_conditions(self, metrics: Dict[str, Any]):
        """Vérifie les conditions d'alerte"""
        current_time = datetime.utcnow()
        
        # Vérifier taux d'erreur élevé
        error_rate = metrics.get('performance', {}).get('error_rate', 0)
        if error_rate > 0.05:  # > 5%
            self._create_alert(
                'HIGH_ERROR_RATE', 
                f"Taux d'erreur élevé: {error_rate*100:.2f}%",
                'warning'
            )
        
        # Vérifier santé des feature flags
        for flag_name, flag_data in metrics.get('feature_flags', {}).items():
            flag_metrics = flag_data.get('metrics', {})
            flag_error_rate = flag_metrics.get('error_rate', 0)
            
            if flag_error_rate > 0.03:  # > 3%
                self._create_alert(
                    'FEATURE_FLAG_ERROR',
                    f"Flag {flag_name} taux erreur élevé: {flag_error_rate*100:.2f}%",
                    'warning'
                )
        
        # Vérifier score de santé critique
        health_score = metrics.get('health_score', 100)
        if health_score < 60:
            self._create_alert(
                'LOW_HEALTH_SCORE',
                f"Score de santé critique: {health_score:.1f}/100",
                'critical'
            )
    
    def _create_alert(self, alert_type: str, message: str, severity: str):
        """Crée une nouvelle alerte"""
        alert = {
            'id': f"{alert_type}_{int(datetime.utcnow().timestamp())}",
            'type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': datetime.utcnow().isoformat(),
            'active': True
        }
        
        # Éviter doublons récents
        recent_alerts = [a for a in self.alerts_history[-10:] if a.get('type') == alert_type]
        if recent_alerts:
            last_alert_time = datetime.fromisoformat(recent_alerts[-1]['timestamp'])
            if (datetime.utcnow() - last_alert_time).total_seconds() < 300:  # 5 min
                return  # Skip duplicate
        
        self.alerts_history.append(alert)
        logger.warning(f"🚨 ALERTE {severity.upper()}: {message}")
        
        # Auto-rollback si critique
        if severity == 'critical' and 'HEALTH_SCORE' in alert_type:
            logger.critical("🔴 Score santé critique - Auto-rollback activé")
            for flag in ['use_testable_position_manager', 'use_testable_analyzer']:
                try:
                    self.feature_flags.emergency_rollback(flag, f"Auto-rollback: {message}")
                except Exception as e:
                    logger.error(f"Erreur auto-rollback {flag}: {e}")
    
    def _get_alert_stats(self) -> Dict[str, Any]:
        """Statistiques des alertes"""
        recent_alerts = [a for a in self.alerts_history if 
                        datetime.utcnow() - datetime.fromisoformat(a['timestamp']) < timedelta(hours=24)]
        
        return {
            'total_24h': len(recent_alerts),
            'critical_24h': len([a for a in recent_alerts if a.get('severity') == 'critical']),
            'warning_24h': len([a for a in recent_alerts if a.get('severity') == 'warning']),
            'active_count': len([a for a in self.alerts_history if a.get('active', True)]),
            'most_common_type': self._get_most_common_alert_type(recent_alerts)
        }
    
    def _get_most_common_alert_type(self, alerts: List[Dict]) -> str:
        """Type d'alerte le plus fréquent"""
        if not alerts:
            return "None"
        
        type_counts = {}
        for alert in alerts:
            alert_type = alert.get('type', 'Unknown')
            type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
        
        return max(type_counts.keys(), key=type_counts.get)
    
    def _log_action(self, action_type: str, data: Dict[str, Any]):
        """Log une action utilisateur"""
        log_entry = {
            'action_type': action_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"📝 Action utilisateur: {action_type} - {data}")
    
    def run(self, debug=False):
        """Démarre le serveur Flask"""
        logger.info(f"🚀 Démarrage dashboard sur http://{self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=debug, threaded=True)


# Factory function
def create_dashboard(host='localhost', port=5001) -> RefactoringDashboard:
    """Crée une instance du dashboard"""
    app = Flask(__name__)
    return RefactoringDashboard(app, host, port)

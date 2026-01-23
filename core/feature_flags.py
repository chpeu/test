#!/usr/bin/env python3
"""
Feature Flags System - Trade Cursor v7.0
Système de feature flags pour refactorisation sécurisée
Permet basculement instantané et rollback d'urgence
"""

import logging
import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class FeatureFlagConfig:
    """Configuration d'un feature flag"""
    name: str
    enabled: bool
    description: str
    rollout_percentage: float = 0.0  # 0-100
    created_at: str = ""
    updated_at: str = ""
    environment: str = "development"  # development, staging, production
    dependencies: list = None
    rollback_on_error: bool = True
    max_error_rate: float = 0.05  # 5% max
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
        if self.dependencies is None:
            self.dependencies = []


class FeatureFlagsManager:
    """
    Gestionnaire central des feature flags
    
    Fonctionnalités:
    - Basculement sécurisé entre implémentations
    - Rollback automatique sur erreurs
    - Monitoring et métriques
    - Configuration persistante
    """
    
    def __init__(self, config_file: str = "feature_flags.json"):
        self.config_file = config_file
        self.flags: Dict[str, FeatureFlagConfig] = {}
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.rollback_history: list = []
        
        # Flags par défaut pour refactorisation
        self._init_default_flags()
        
        # Charger config existante
        self.load_config()
        
        logger.info("✅ FeatureFlagsManager initialisé")
    
    def _init_default_flags(self):
        """Initialiser flags par défaut pour refactorisation"""
        default_flags = {
            'use_testable_position_manager': FeatureFlagConfig(
                name='use_testable_position_manager',
                enabled=True,
                description='Utiliser TestablePositionManager au lieu de PositionManager legacy',
                rollout_percentage=75.0,
                environment='development'
            ),
            
            'use_testable_analyzer': FeatureFlagConfig(
                name='use_testable_analyzer',
                enabled=True,
                description='Utiliser TestableAnalyzer au lieu de TechnicalAnalyzer legacy',
                rollout_percentage=50.0,
                environment='development'
            ),
            
            'enable_coverage_tests': FeatureFlagConfig(
                name='enable_coverage_tests',
                enabled=True,
                description='Activer les tests de couverture avancés',
                rollout_percentage=100.0,
                environment='development',
                rollback_on_error=False
            ),
            
            'safe_rollback_mode': FeatureFlagConfig(
                name='safe_rollback_mode',
                enabled=True,
                description='Mode rollback automatique activé',
                rollout_percentage=100.0,
                environment='all',
                rollback_on_error=False
            ),
            
            'use_testable_scanner': FeatureFlagConfig(
                name='use_testable_scanner',
                enabled=True,
                description='Utiliser TestableScannerOrchestrator au lieu de ScalabilityScanner legacy',
                rollout_percentage=25.0,
                environment='development'
            ),
            
            'comparison_mode': FeatureFlagConfig(
                name='comparison_mode',
                enabled=True,
                description='Comparer résultats legacy vs nouveau',
                rollout_percentage=100.0,
                environment='development',
                rollback_on_error=False
            ),
            
            'ab_testing_enabled': FeatureFlagConfig(
                name='ab_testing_enabled',
                enabled=False,
                description='Activer A/B testing progressif',
                rollout_percentage=0.0,
                environment='staging',
                max_error_rate=0.02
            ),
            
            'monitoring_enabled': FeatureFlagConfig(
                name='monitoring_enabled',
                enabled=True,
                description='Monitoring des métriques et performances',
                rollout_percentage=100.0,
                environment='all',
                rollback_on_error=False
            ),
            
            'debug_logging': FeatureFlagConfig(
                name='debug_logging',
                enabled=True,
                description='Logging debug détaillé pour refactorisation',
                rollout_percentage=100.0,
                environment='development',
                rollback_on_error=False
            )
        }
        
        self.flags = default_flags
    
    def is_enabled(self, flag_name: str, user_id: str = None) -> bool:
        """
        Vérifier si flag activé pour utilisateur
        
        Args:
            flag_name: Nom du flag
            user_id: ID utilisateur pour rollout progressif
            
        Returns:
            bool: True si flag activé
        """
        try:
            flag = self.flags.get(flag_name)
            if not flag:
                logger.warning(f"Flag inconnu: {flag_name}")
                return False
            
            # Si flag désactivé globalement
            if not flag.enabled:
                return False
            
            # Si rollout 100%, toujours activé
            if flag.rollout_percentage >= 100.0:
                return True
            
            # Si pas d'user_id, utiliser rollout global
            if not user_id:
                return flag.rollout_percentage > 0.0
            
            # Rollout basé sur hash user_id (consistant)
            import hashlib
            hash_value = int(hashlib.md5(f"{flag_name}_{user_id}".encode()).hexdigest(), 16)
            percentage = (hash_value % 100) + 1
            
            is_enabled = percentage <= flag.rollout_percentage
            
            # Metrics
            self._track_flag_usage(flag_name, is_enabled, user_id)
            
            return is_enabled
            
        except Exception as e:
            logger.error(f"Flag check failed for {flag_name}: {e}")
            return False
    
    def enable_flag(self, flag_name: str, rollout_percentage: float = 100.0):
        """
        Activer flag avec rollout progressif
        
        Args:
            flag_name: Nom du flag
            rollout_percentage: Pourcentage rollout (0-100)
        """
        try:
            if not self.flags or flag_name not in self.flags:
                logger.error(f"Flag inconnu: {flag_name}")
                return
            
            old_state = self.flags[flag_name].enabled
            old_percentage = self.flags[flag_name].rollout_percentage
            
            self.flags[flag_name].enabled = True
            self.flags[flag_name].rollout_percentage = min(100.0, max(0.0, rollout_percentage))
            self.flags[flag_name].updated_at = datetime.utcnow().isoformat()
            
            self.save_config()
            
            logger.info(f"✅ Flag activé: {flag_name} ({rollout_percentage:.1f}%)")
            
            # Track change
            self._track_flag_change(flag_name, old_state, True, old_percentage, rollout_percentage)
            
        except Exception as e:
            logger.error(f"Enable flag failed: {e}")
    
    def disable_flag(self, flag_name: str, reason: str = "Manual"):
        """
        Désactiver flag avec logging
        
        Args:
            flag_name: Nom du flag
            reason: Raison désactivation
        """
        try:
            if not self.flags or flag_name not in self.flags:
                logger.error(f"Flag inconnu: {flag_name}")
                return
            
            old_state = self.flags[flag_name].enabled
            
            self.flags[flag_name].enabled = False
            self.flags[flag_name].rollout_percentage = 0.0
            self.flags[flag_name].updated_at = datetime.utcnow().isoformat()
            
            self.save_config()
            
            logger.warning(f"🔴 Flag désactivé: {flag_name} - Raison: {reason}")
            
            # Track change
            self._track_flag_change(flag_name, old_state, False, 0, 0, reason)
            
        except Exception as e:
            logger.error(f"Disable flag failed: {e}")
    
    def gradual_rollout(self, flag_name: str, target_percentage: float, step_size: float = 10.0):
        """
        Rollout progressif d'un flag
        
        Args:
            flag_name: Nom du flag
            target_percentage: Pourcentage cible
            step_size: Taille des étapes
        """
        try:
            if flag_name not in self.flags:
                logger.error(f"Flag inconnu: {flag_name}")
                return
            
            current = self.flags[flag_name].rollout_percentage
            
            if current >= target_percentage:
                logger.info(f"Rollout déjà atteint: {flag_name} ({current:.1f}%)")
                return
            
            # Calculer prochaine étape
            next_percentage = min(target_percentage, current + step_size)
            
            # Vérifier métriques avant augmentation
            if self._check_rollout_safety(flag_name):
                self.flags[flag_name].rollout_percentage = next_percentage
                self.flags[flag_name].updated_at = datetime.utcnow().isoformat()
                self.save_config()
                
                logger.info(f"📈 Rollout progressif: {flag_name} {current:.1f}% → {next_percentage:.1f}%")
                
                # Track progression
                self._track_rollout_progression(flag_name, current, next_percentage)
            else:
                logger.warning(f"⚠️ Rollout suspendu pour {flag_name} - Métriques défavorables")
                self._pause_rollout(flag_name)
            
        except Exception as e:
            logger.error(f"Gradual rollout failed: {e}")
    
    def emergency_rollback(self, flag_name: str, reason: str = "Emergency"):
        """
        Rollback d'urgence avec logging détaillé
        
        Args:
            flag_name: Nom du flag
            reason: Raison rollback
        """
        try:
            logger.critical(f"🚨 EMERGENCY ROLLBACK: {flag_name} - Raison: {reason}")
            
            # Désactiver immédiatement
            self.disable_flag(flag_name, f"EMERGENCY: {reason}")
            
            # Enregistrer dans historique
            rollback_entry = {
                'flag_name': flag_name,
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat(),
                'previous_state': self.flags[flag_name].enabled,
                'previous_percentage': self.flags[flag_name].rollout_percentage,
                'type': 'EMERGENCY'
            }
            
            self.rollback_history.append(rollback_entry)
            
            # Alerter équipe (simulation)
            self._alert_team(f"ROLLBACK EMERGENCY: {flag_name}", reason)
            
        except Exception as e:
            logger.error(f"Emergency rollback failed: {e}")
    
    def _check_rollout_safety(self, flag_name: str) -> bool:
        """Vérifier sécurité rollout via métriques"""
        try:
            metrics = self.metrics.get(flag_name, {})
            
            # Vérifier taux d'erreur
            error_rate = metrics.get('error_rate', 0.0)
            max_allowed = self.flags[flag_name].max_error_rate
            
            if error_rate > max_allowed:
                logger.warning(f"Error rate trop élevé: {error_rate:.3f} > {max_allowed:.3f}")
                return False
            
            # Vérifier performance
            performance_delta = metrics.get('performance_delta', 0.0)
            if performance_delta < -0.20:  # -20% performance max
                logger.warning(f"Performance dégradée: {performance_delta:.3f}")
                return False
            
            # Vérifier success rate
            success_rate = metrics.get('success_rate', 1.0)
            if success_rate < 0.95:  # 95% min
                logger.warning(f"Success rate trop bas: {success_rate:.3f}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Safety check failed: {e}")
            return False
    
    def update_metrics(self, flag_name: str, metrics_data: Dict[str, Any]):
        """Mettre à jour métriques pour flag"""
        try:
            if flag_name not in self.metrics:
                self.metrics[flag_name] = {}
            
            self.metrics[flag_name].update(metrics_data)
            self.metrics[flag_name]['last_updated'] = datetime.utcnow().isoformat()
            
            # Auto-rollback si métriques critiques
            if self.flags[flag_name].rollback_on_error:
                if not self._check_rollout_safety(flag_name):
                    self.emergency_rollback(flag_name, "Metrics threshold exceeded")
            
        except Exception as e:
            logger.error(f"Update metrics failed: {e}")
    
    def get_flag(self, flag_name: str) -> Optional[FeatureFlagConfig]:
        """Obtenir configuration d'un flag"""
        return self.flags.get(flag_name)
    
    def get_flag_status(self, flag_name: str) -> Dict[str, Any]:
        """Obtenir statut complet d'un flag"""
        try:
            if flag_name not in self.flags:
                return {'error': 'Flag not found'}
            
            flag = self.flags[flag_name]
            metrics = self.metrics.get(flag_name, {})
            
            return {
                'name': flag.name,
                'enabled': flag.enabled,
                'rollout_percentage': flag.rollout_percentage,
                'description': flag.description,
                'environment': flag.environment,
                'created_at': flag.created_at,
                'updated_at': flag.updated_at,
                'rollback_on_error': flag.rollback_on_error,
                'max_error_rate': flag.max_error_rate,
                'dependencies': flag.dependencies,
                'metrics': metrics,
                'last_metric_update': metrics.get('last_updated')
            }
            
        except Exception as e:
            logger.error(f"Get flag status failed: {e}")
            return {'error': str(e)}
    
    def list_all_flags(self) -> Dict[str, Dict[str, Any]]:
        """Lister tous les flags avec statuts"""
        return {name: self.get_flag_status(name) for name in self.flags.keys()}
    
    def save_config(self):
        """Sauvegarder configuration sur disque"""
        try:
            config_data = {
                'flags': {name: asdict(flag) for name, flag in self.flags.items()},
                'metrics': self.metrics,
                'rollback_history': self.rollback_history[-50:],  # Garder 50 derniers
                'last_saved': datetime.utcnow().isoformat()
            }
            
            config_path = os.path.join(os.path.dirname(__file__), self.config_file)
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.debug("✅ Feature flags config sauvée")
            
        except Exception as e:
            logger.error(f"Save config failed: {e}")
    
    def load_config(self):
        """Charger configuration depuis disque"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), self.config_file)
            
            if not os.path.exists(config_path):
                logger.info("Config file not found, using defaults")
                return
            
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Charger flags
            if 'flags' in config_data:
                for name, flag_dict in config_data['flags'].items():
                    self.flags[name] = FeatureFlagConfig(**flag_dict)
            
            # Charger métriques
            if 'metrics' in config_data:
                self.metrics = config_data['metrics']
            
            # Charger historique rollback
            if 'rollback_history' in config_data:
                self.rollback_history = config_data['rollback_history']
            
            logger.info(f"✅ Feature flags config chargée ({len(self.flags)} flags)")
            
        except Exception as e:
            logger.error(f"Load config failed: {e}")
            # Garder defaults en cas d'erreur
    
    def _track_flag_usage(self, flag_name: str, is_enabled: bool, user_id: str = None):
        """Tracker utilisation des flags pour métriques"""
        try:
            # Update usage metrics
            if hasattr(self, '_usage_metrics'):
                if flag_name not in self._usage_metrics:
                    self._usage_metrics[flag_name] = {'checks': 0, 'enabled_count': 0}
                
                self._usage_metrics[flag_name]['checks'] += 1
                if is_enabled:
                    self._usage_metrics[flag_name]['enabled_count'] += 1
                    
        except Exception as e:
            logger.error(f"Update metrics failed: {e}")
    
    def _track_flag_change(self, flag_name: str, old_state: bool, new_state: bool, 
                           old_percentage: float, new_percentage: float, reason: str = ""):
        """Tracker changements de flags"""
        change_entry = {
            'flag_name': flag_name,
            'old_state': old_state,
            'new_state': new_state,
            'old_percentage': old_percentage,
            'new_percentage': new_percentage,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if flag_name not in self.metrics:
            self.metrics[flag_name] = {}
        
        if 'changes' not in self.metrics[flag_name]:
            self.metrics[flag_name]['changes'] = []
        
        self.metrics[flag_name]['changes'].append(change_entry)
        
        # Garder seulement 20 derniers changements
        self.metrics[flag_name]['changes'] = self.metrics[flag_name]['changes'][-20:]
    
    def _track_rollout_progression(self, flag_name: str, old_pct: float, new_pct: float):
        """Tracker progression rollout"""
        if flag_name not in self.metrics:
            self.metrics[flag_name] = {}
        
        if 'rollout_history' not in self.metrics[flag_name]:
            self.metrics[flag_name]['rollout_history'] = []
        
        entry = {
            'from_percentage': old_pct,
            'to_percentage': new_pct,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.metrics[flag_name]['rollout_history'].append(entry)
    
    def _pause_rollout(self, flag_name: str):
        """Mettre rollout en pause"""
        logger.warning(f"⏸️ Rollout mis en pause: {flag_name}")
        
        if flag_name not in self.metrics:
            self.metrics[flag_name] = {}
        
        self.metrics[flag_name]['rollout_paused'] = True
        self.metrics[flag_name]['pause_timestamp'] = datetime.utcnow().isoformat()
    
    def _alert_team(self, title: str, message: str):
        """Alerter équipe (simulation)"""
        alert = f"🚨 ALERT: {title}\n{message}\nTimestamp: {datetime.utcnow()}"
        logger.critical(alert)
        
        # En production: envoyer Slack/email/etc.
        # Pour l'instant: log critique


# Instance globale pour facilité d'utilisation
_feature_flags_manager = None

def get_feature_flags_manager() -> FeatureFlagsManager:
    """Obtenir instance globale du gestionnaire"""
    global _feature_flags_manager
    if _feature_flags_manager is None:
        _feature_flags_manager = FeatureFlagsManager()
    return _feature_flags_manager


def is_flag_enabled(flag_name: str, user_id: str = None) -> bool:
    """Helper pour vérifier flag rapidement"""
    return get_feature_flags_manager().is_enabled(flag_name, user_id)


def enable_flag(flag_name: str, rollout_percentage: float = 100.0):
    """Helper pour activer flag"""
    get_feature_flags_manager().enable_flag(flag_name, rollout_percentage)


def disable_flag(flag_name: str, reason: str = "Manual"):
    """Helper pour désactiver flag"""
    get_feature_flags_manager().disable_flag(flag_name, reason)


def emergency_rollback(flag_name: str, reason: str = "Emergency"):
    """Helper pour rollback d'urgence"""
    get_feature_flags_manager().emergency_rollback(flag_name, reason)


# Décorateur pour méthodes protégées par feature flags
def feature_flag(flag_name: str, fallback_result=None):
    """
    Décorateur pour protéger méthodes par feature flags
    
    Usage:
        @feature_flag('use_testable_position_manager')
        def new_method(self):
            return "New implementation"
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if is_flag_enabled(flag_name):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Feature flag {flag_name} method failed: {e}")
                    # Auto-rollback si configuré
                    fm = get_feature_flags_manager()
                    if fm.flags.get(flag_name, {}).rollback_on_error:
                        emergency_rollback(flag_name, f"Method error: {e}")
                    return fallback_result
            else:
                return fallback_result
        return wrapper
    return decorator

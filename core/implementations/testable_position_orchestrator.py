"""
TestablePositionOrchestrator - Orchestrateur principal refactorisé
Coordonne tous les composants position avec gestion d'erreurs robuste
"""

import logging
import asyncio
import random
from typing import Dict, Any
from datetime import datetime

from ..interfaces.position_interfaces import (
    IPositionOrchestrator, IPositionCalculator, IPositionValidator,
    IPositionExecutor, IPositionRepository, PositionStatus
)
from ..feature_flags import get_feature_flags_manager

logger = logging.getLogger(__name__)


class TestablePositionOrchestrator(IPositionOrchestrator):
    """
    Orchestrateur testable pour gestion complète des positions
    
    Responsabilités:
    - Coordination des composants injectés
    - Gestion d'erreurs et rollback
    - Monitoring et métriques
    - Comparaison legacy vs nouveau (si activé)
    """
    
    def __init__(self,
                 calculator: IPositionCalculator,
                 validator: IPositionValidator,
                 executor: IPositionExecutor,
                 repository: IPositionRepository):
        
        self.calculator = calculator
        self.validator = validator
        self.executor = executor
        self.repository = repository
        self.feature_flags = get_feature_flags_manager()
        
        # Métriques internes
        self.processed_requests = 0
        self.successful_trades = 0
        self.failed_trades = 0
        
        logger.info("✅ TestablePositionOrchestrator initialisé")
    
    async def process_trade_request(self, setup: Dict[str, Any], capital: float) -> Dict[str, Any]:
        """
        Traite une demande de trade complète
        
        Workflow:
        1. Validation du setup
        2. Validation des conditions de marché
        3. Calcul de la position
        4. Validation des paramètres de risque
        5. Exécution
        6. Persistance
        
        Args:
            setup: Configuration du trade
            capital: Capital disponible
            
        Returns:
            Dict avec résultat complet du traitement
        """
        request_id = f"req_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{self.processed_requests}"
        self.processed_requests += 1
        
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"🚀 Traitement trade request: {request_id} ({setup.get('symbol', 'unknown')})")
            
            # 1. Validation du setup de base
            validation_result = self.validator.validate_setup(setup)
            
            if not validation_result.is_valid:
                logger.warning(f"❌ Setup invalide: {validation_result.errors}")
                return self._create_error_response(
                    request_id, "VALIDATION_ERROR", 
                    f"Setup invalide: {validation_result.errors}",
                    warnings=validation_result.warnings
                )
            
            # Log des warnings
            if validation_result.warnings:
                logger.info(f"⚠️ Warnings setup: {validation_result.warnings}")
            
            # 2. Validation conditions de marché
            symbol = setup.get('symbol')
            market_validation = self.validator.validate_market_conditions(symbol)
            
            if not market_validation.is_valid:
                logger.warning(f"❌ Conditions marché invalides: {market_validation.errors}")
                return self._create_error_response(
                    request_id, "MARKET_CONDITIONS_ERROR",
                    f"Conditions marché: {market_validation.errors}",
                    warnings=market_validation.warnings
                )
            
            # 3. Calcul de la position
            position_size = self.calculator.calculate_size(setup, capital)
            
            if not position_size.is_valid:
                logger.error(f"❌ Position size invalide: {position_size}")
                return self._create_error_response(
                    request_id, "POSITION_CALCULATION_ERROR",
                    "Impossible de calculer taille position valide"
                )
            
            logger.info(f"📊 Position calculée: {position_size.final_size} (risque: {position_size.risk_percentage:.2f}%)")
            
            # 4. Validation paramètres de risque
            risk_validation = self.validator.validate_risk_parameters(position_size, capital)
            
            if not risk_validation.is_valid:
                logger.error(f"❌ Paramètres risque invalides: {risk_validation.errors}")
                return self._create_error_response(
                    request_id, "RISK_VALIDATION_ERROR",
                    f"Paramètres risque: {risk_validation.errors}",
                    warnings=risk_validation.warnings
                )
            
            # 5. Calcul SL/TP
            stop_loss = self.calculator.calculate_stop_loss(setup, position_size.final_size)
            take_profit = self.calculator.calculate_take_profit(setup, position_size.final_size)
            
            # Enrichir setup avec SL/TP calculés
            execution_setup = setup.copy()
            execution_setup.update({
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'calculated_size': position_size.final_size
            })
            
            # 6. Mode comparaison si activé
            comparison_data = None
            if self.feature_flags.is_enabled('comparison_mode'):
                comparison_data = await self._run_comparison_mode(execution_setup, capital)
            
            # 7. Exécution
            execution_result = await self.executor.open_position(execution_setup, position_size)
            
            if not execution_result.get('success', False):
                logger.error(f"❌ Échec exécution: {execution_result.get('error')}")
                return self._create_error_response(
                    request_id, "EXECUTION_ERROR",
                    f"Exécution échouée: {execution_result.get('error')}"
                )
            
            # 8. Persistance
            position_data = self._create_position_data(
                request_id, execution_setup, position_size, execution_result
            )
            
            try:
                position_id = self.repository.save_position(position_data)
                logger.info(f"💾 Position sauvée: {position_id}")
            except Exception as e:
                logger.error(f"❌ Erreur sauvegarde: {e}")
                # Continuer - position ouverte mais non sauvée
                position_id = execution_result.get('position_id', 'unsaved')
            
            # 9. Mise à jour métriques
            self.successful_trades += 1
            
            # 10. Mise à jour feature flags metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_feature_flags_metrics(request_id, True, processing_time)
            
            # 11. Résultat succès
            result = {
                'success': True,
                'request_id': request_id,
                'position_id': position_id,
                'execution_details': execution_result,
                'position_size': position_size.__dict__,
                'calculated_levels': {
                    'stop_loss': stop_loss,
                    'take_profit': take_profit
                },
                'validation_warnings': validation_result.warnings + risk_validation.warnings,
                'processing_time_seconds': processing_time,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Ajouter données de comparaison si disponibles
            if comparison_data:
                result['comparison_data'] = comparison_data
            
            logger.info(f"✅ Trade request traité avec succès: {request_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"💥 Erreur critique trade request {request_id}: {e}")
            
            # Mise à jour métriques échec
            self.failed_trades += 1
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_feature_flags_metrics(request_id, False, processing_time)
            
            return self._create_error_response(
                request_id, "CRITICAL_ERROR", str(e)
            )
    
    async def close_all_positions(self) -> Dict[str, Any]:
        """Ferme toutes les positions ouvertes"""
        try:
            logger.info("🔴 Fermeture de toutes les positions...")
            
            # Récupérer positions ouvertes
            open_positions = self.repository.get_open_positions()
            
            if not open_positions:
                logger.info("ℹ️ Aucune position ouverte à fermer")
                return {
                    'success': True,
                    'closed_positions': 0,
                    'message': 'Aucune position ouverte'
                }
            
            results = []
            successful_closes = 0
            failed_closes = 0
            
            # Fermer chaque position
            for position in open_positions:
                position_id = position.get('position_id') or position.get('repository_id')
                
                try:
                    close_result = await self.executor.close_position(position_id)
                    
                    if close_result.get('success', False):
                        # Mise à jour statut en base
                        self.repository.update_position_status(position_id, PositionStatus.CLOSED)
                        successful_closes += 1
                        logger.info(f"✅ Position fermée: {position_id}")
                    else:
                        failed_closes += 1
                        logger.error(f"❌ Échec fermeture: {position_id}")
                    
                    results.append({
                        'position_id': position_id,
                        'success': close_result.get('success', False),
                        'details': close_result
                    })
                    
                except Exception as e:
                    failed_closes += 1
                    logger.error(f"❌ Erreur fermeture {position_id}: {e}")
                    results.append({
                        'position_id': position_id,
                        'success': False,
                        'error': str(e)
                    })
            
            logger.info(f"📊 Fermetures: {successful_closes} succès, {failed_closes} échecs")
            
            return {
                'success': True,
                'total_positions': len(open_positions),
                'successful_closes': successful_closes,
                'failed_closes': failed_closes,
                'results': results,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"💥 Erreur critique fermeture toutes positions: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def get_positions_summary(self) -> Dict[str, Any]:
        """Retourne résumé des positions et métriques"""
        try:
            # Récupérer positions ouvertes
            open_positions = self.repository.get_open_positions()
            
            # Calculer métriques
            total_open = len(open_positions)
            total_exposure = sum(
                float(pos.get('size', 0)) * float(pos.get('executed_price', 0))
                for pos in open_positions
            )
            
            # Positions par symbol
            symbols_summary = {}
            for pos in open_positions:
                symbol = pos.get('symbol', 'UNKNOWN')
                if symbol not in symbols_summary:
                    symbols_summary[symbol] = {'count': 0, 'total_size': 0}
                symbols_summary[symbol]['count'] += 1
                symbols_summary[symbol]['total_size'] += float(pos.get('size', 0))
            
            # Métriques de performance
            success_rate = 0
            if self.processed_requests > 0:
                success_rate = (self.successful_trades / self.processed_requests) * 100
            
            return {
                'open_positions': {
                    'count': total_open,
                    'total_exposure': total_exposure,
                    'by_symbol': symbols_summary
                },
                'performance_metrics': {
                    'processed_requests': self.processed_requests,
                    'successful_trades': self.successful_trades,
                    'failed_trades': self.failed_trades,
                    'success_rate_percent': success_rate
                },
                'feature_flags': {
                    'testable_position_manager': self.feature_flags.is_enabled('use_testable_position_manager'),
                    'comparison_mode': self.feature_flags.is_enabled('comparison_mode'),
                    'monitoring_enabled': self.feature_flags.is_enabled('monitoring_enabled')
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur récupération summary: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _run_comparison_mode(self, setup: Dict[str, Any], capital: float) -> Dict[str, Any]:
        """Exécute mode comparaison legacy vs nouveau"""
        try:
            logger.debug("🔄 Mode comparaison activé - simulation legacy")
            
            # Simulation de calculs legacy (à remplacer par vraie logique)
            legacy_size = capital * 0.02  # 2% simple
            legacy_sl = float(setup.get('current_price', 100)) * 0.98
            legacy_tp = float(setup.get('current_price', 100)) * 1.04
            
            return {
                'legacy_calculation': {
                    'size': legacy_size,
                    'stop_loss': legacy_sl,
                    'take_profit': legacy_tp,
                    'method': 'legacy_simple'
                },
                'comparison_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur mode comparaison: {e}")
            return {'comparison_error': str(e)}
    
    def _create_position_data(self, request_id: str, setup: Dict[str, Any], 
                            position_size, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """Crée données de position pour persistance"""
        return {
            'position_id': execution_result.get('position_id'),
            'request_id': request_id,
            'symbol': setup.get('symbol'),
            'side': setup.get('side'),
            'size': position_size.final_size,
            'calculated_size': position_size.__dict__,
            'requested_price': setup.get('current_price'),
            'executed_price': execution_result.get('executed_price'),
            'slippage': execution_result.get('slippage'),
            'stop_loss': setup.get('stop_loss'),
            'take_profit': setup.get('take_profit'),
            'status': PositionStatus.OPEN.value,
            'setup_data': setup,
            'execution_data': execution_result,
            'created_at': datetime.utcnow().isoformat(),
            'orchestrator_version': 'testable_v1'
        }
    
    def _create_error_response(self, request_id: str, error_type: str, 
                             message: str, warnings: list = None) -> Dict[str, Any]:
        """Crée réponse d'erreur standardisée"""
        return {
            'success': False,
            'request_id': request_id,
            'error_type': error_type,
            'error_message': message,
            'warnings': warnings or [],
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _update_feature_flags_metrics(self, request_id: str, success: bool, processing_time: float):
        """Met à jour métriques des feature flags"""
        try:
            metrics_data = {
                'success_rate': (self.successful_trades / max(self.processed_requests, 1)),
                'error_rate': (self.failed_trades / max(self.processed_requests, 1)),
                'avg_processing_time': processing_time,
                'last_request_id': request_id,
                'last_success': success
            }
            
            # Mise à jour metrics du testable position manager
            self.feature_flags.update_metrics('use_testable_position_manager', metrics_data)
            
        except Exception as e:
            logger.error(f"Erreur mise à jour metrics feature flags: {e}")

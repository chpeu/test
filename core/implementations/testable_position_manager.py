#!/usr/bin/env python3
"""
TestablePositionManager - Trade Cursor v7.0
Version testable du PositionManager avec injection de dépendances
ZÉRO RISQUE - Code existant inchangé, nouvelle implémentation à côté
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from core.interfaces.position_manager_interface import (
    IPositionManager, 
    PositionSetup, 
    PositionResult, 
    PositionManagerConfig
)

logger = logging.getLogger(__name__)


class TestablePositionManager(IPositionManager):
    """
    PositionManager testable avec injection de dépendances
    
    Même logique que l'original mais:
    - Dépendances injectées = testable avec mocks
    - Interface standardisée
    - Gestion d'erreurs améliorée
    - Logging détaillé pour debug
    """
    
    def __init__(self, config: PositionManagerConfig, dependencies: Optional[Dict[str, Any]] = None):
        self.config = config
        self.dependencies = dependencies or {}
        
        # État interne
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        self.position_history: List[Dict[str, Any]] = []
        
        # Dépendances injectées avec fallbacks
        self._init_dependencies()
        
        logger.info("✅ TestablePositionManager initialisé")
    
    def _init_dependencies(self):
        """Initialiser dépendances avec fallbacks sécurisés"""
        try:
            # TP/SL Calculator
            if 'tp_sl_calc' in self.dependencies:
                self.tp_sl_calc = self.dependencies['tp_sl_calc']
            else:
                self.tp_sl_calc = MockTPSLCalculator()
            
            # PnL Calculator
            if 'pnl_calc' in self.dependencies:
                self.pnl_calc = self.dependencies['pnl_calc']
            else:
                self.pnl_calc = MockPnLCalculator()
                
            # Recovery Manager
            if 'recovery_manager' in self.dependencies:
                self.recovery_manager = self.dependencies['recovery_manager']
            else:
                self.recovery_manager = MockRecoveryManager()
                
            # Trailing Stop Manager
            if 'trailing_stop' in self.dependencies:
                self.trailing_stop = self.dependencies['trailing_stop']
            else:
                self.trailing_stop = MockTrailingStopManager()
                
            # Early Invalidation Checker
            if 'early_invalidation' in self.dependencies:
                self.early_invalidation = self.dependencies['early_invalidation']
            else:
                self.early_invalidation = MockEarlyInvalidationChecker()
                
            # Analytics Logger
            if 'analytics_logger' in self.dependencies:
                self.analytics_logger = self.dependencies['analytics_logger']
            else:
                self.analytics_logger = MockAnalyticsLogger()
                
        except Exception as e:
            logger.error(f"Dependency initialization failed: {e}")
            self._init_fallback_dependencies()
    
    def _init_fallback_dependencies(self):
        """Fallbacks d'urgence si injection échoue"""
        logger.warning("🔧 Utilisation dependencies fallback")
        self.tp_sl_calc = MockTPSLCalculator()
        self.pnl_calc = MockPnLCalculator()
        self.recovery_manager = MockRecoveryManager()
        self.trailing_stop = MockTrailingStopManager()
        self.early_invalidation = MockEarlyInvalidationChecker()
        self.analytics_logger = MockAnalyticsLogger()
    
    def calculate_position_size(self, setup: PositionSetup, capital: float) -> float:
        """
        Calculer taille position avec recovery mode et validations
        
        Logique identique à l'original mais testable
        """
        try:
            logger.debug(f"Calculating position size: {setup.symbol}, capital: {capital}")
            
            # Validations de base
            if capital <= 0:
                logger.warning("Capital invalide")
                return 0.0
                
            if setup.entry_price <= 0 or setup.sl_price <= 0:
                logger.warning("Prix invalides")
                return 0.0
            
            spread = abs(setup.entry_price - setup.sl_price)
            if spread <= 0:
                logger.warning("Spread nul")
                return 0.0
            
            # Récupération paramètres
            base_risk_pct = min(setup.risk_per_trade, self.config.max_risk_per_trade)
            base_risk_pct = max(base_risk_pct, self.config.min_risk_per_trade)
            
            # Ajustement recovery mode
            recovery_state = self.get_recovery_state(setup.loss_streak)
            recovery_mult = recovery_state.get('position_size_mult', 1.0)
            
            # Calcul taille
            risk_amount = capital * (base_risk_pct / 100)
            adjusted_risk = risk_amount * recovery_mult
            position_size = adjusted_risk / spread
            
            # Validation max position
            max_position = capital * 0.1  # Max 10% du capital
            position_size = min(position_size, max_position)
            
            logger.info(f"Position size calculée: {position_size:.4f} (risk: {base_risk_pct}%, recovery: {recovery_mult})")
            
            return position_size
            
        except Exception as e:
            logger.error(f"Calculate position size failed: {e}")
            return 0.0
    
    def open_position(self, setup: PositionSetup) -> PositionResult:
        """
        Ouvrir position avec validations complètes
        """
        try:
            logger.info(f"🚀 Ouverture position: {setup.symbol} {setup.direction}")
            
            # Vérifications pre-trade
            if len(self.active_positions) >= self.config.max_positions:
                return PositionResult(
                    False, 0.0, 
                    f"Max positions atteint ({self.config.max_positions})",
                    error_code="MAX_POSITIONS"
                )
            
            # Calcul taille position
            # Note: capital serait normalement récupéré du broker
            mock_capital = 1000.0  # Pour tests
            position_size = self.calculate_position_size(setup, mock_capital)
            
            if position_size <= 0:
                return PositionResult(
                    False, 0.0, 
                    "Taille position invalide", 
                    error_code="INVALID_SIZE"
                )
            
            # Calcul TP/SL finaux
            tp_price, sl_price = self.tp_sl_calc.calculate_levels(
                setup.entry_price, 
                setup.tp_price, 
                setup.sl_price, 
                setup.direction
            )
            
            # Créer position
            position_id = str(uuid.uuid4())
            position_data = {
                'id': position_id,
                'symbol': setup.symbol,
                'direction': setup.direction,
                'entry_price': setup.entry_price,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'size': position_size,
                'atr': setup.atr,
                'score': setup.score,
                'opened_at': datetime.utcnow(),
                'status': 'ACTIVE',
                'pnl': 0.0,
                'max_pnl': 0.0,
                'min_pnl': 0.0
            }
            
            # Sauvegarder position
            self.active_positions[position_id] = position_data
            
            # Log analytics
            self.analytics_logger.log_position_opened(position_data)
            
            logger.info(f"✅ Position ouverte: {position_id} - Size: {position_size:.4f}")
            
            return PositionResult(
                True, 
                position_size, 
                f"Position ouverte: {position_id}",
                position_id=position_id
            )
            
        except Exception as e:
            logger.error(f"Open position failed: {e}")
            return PositionResult(
                False, 0.0, 
                f"Erreur ouverture: {e}", 
                error_code="OPEN_ERROR"
            )
    
    def close_position(self, position_id: str, reason: str = "Manual") -> bool:
        """
        Fermer position active
        """
        try:
            if position_id not in self.active_positions:
                logger.warning(f"Position introuvable: {position_id}")
                return False
            
            position = self.active_positions[position_id]
            position['status'] = 'CLOSED'
            position['closed_at'] = datetime.utcnow()
            position['close_reason'] = reason
            
            # Déplacer vers historique
            self.position_history.append(position)
            del self.active_positions[position_id]
            
            # Log analytics
            self.analytics_logger.log_position_closed(position, reason)
            
            logger.info(f"✅ Position fermée: {position_id} - Raison: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Close position failed: {e}")
            return False
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Retourner positions actives"""
        return list(self.active_positions.values())
    
    def get_recovery_state(self, loss_streak: int) -> Dict[str, Any]:
        """
        Obtenir état recovery mode via manager injecté
        """
        try:
            return self.recovery_manager.get_state(loss_streak)
        except Exception as e:
            logger.error(f"Recovery state failed: {e}")
            return {
                'active': False,
                'level': None,
                'position_size_mult': 1.0,
                'min_score_boost': 0.0
            }
    
    def update_position_status(self, position_id: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mettre à jour position avec données marché
        """
        try:
            if position_id not in self.active_positions:
                return {'error': 'Position not found'}
            
            position = self.active_positions[position_id]
            current_price = market_data.get('price', position['entry_price'])
            
            # Calculer PnL
            pnl_data = self.calculate_pnl(position_id, current_price)
            position.update(pnl_data)
            
            # Tracker min/max PnL
            if pnl_data.get('unrealized_pnl', 0) > position.get('max_pnl', 0):
                position['max_pnl'] = pnl_data['unrealized_pnl']
            if pnl_data.get('unrealized_pnl', 0) < position.get('min_pnl', 0):
                position['min_pnl'] = pnl_data['unrealized_pnl']
            
            # Vérifier trailing stop
            if self.config.trailing_stop_enabled:
                trailing_data = self.trailing_stop.update(position, current_price)
                position.update(trailing_data)
            
            # Vérifier early invalidation
            if self.config.early_invalidation_enabled:
                invalidation_check = self.early_invalidation.check(position, market_data)
                if invalidation_check.get('should_invalidate', False):
                    position['invalidation_warning'] = invalidation_check['reason']
            
            position['last_update'] = datetime.utcnow()
            
            return {
                'updated': True,
                'position': position,
                'pnl': pnl_data
            }
            
        except Exception as e:
            logger.error(f"Update position failed: {e}")
            return {'error': str(e)}
    
    def calculate_pnl(self, position_id: str, current_price: float) -> Dict[str, float]:
        """
        Calculer PnL position via calculator injecté
        """
        try:
            if position_id not in self.active_positions:
                return {'error': 'Position not found'}
            
            position = self.active_positions[position_id]
            
            return self.pnl_calc.calculate_unrealized_pnl(
                position['entry_price'],
                current_price,
                position['size'],
                position['direction']
            )
            
        except Exception as e:
            logger.error(f"Calculate PnL failed: {e}")
            return {'unrealized_pnl': 0.0, 'pnl_pct': 0.0, 'error': str(e)}
    
    def should_close_position(self, position_id: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Déterminer si position doit être fermée
        """
        try:
            if position_id not in self.active_positions:
                return {'should_close': False, 'error': 'Position not found'}
            
            position = self.active_positions[position_id]
            current_price = market_data.get('price', position['entry_price'])
            
            # Vérifier TP/SL
            if position['direction'] == 'LONG':
                if current_price >= position['tp_price']:
                    return {'should_close': True, 'reason': 'TP_HIT', 'urgency': 'HIGH'}
                if current_price <= position['sl_price']:
                    return {'should_close': True, 'reason': 'SL_HIT', 'urgency': 'HIGH'}
            else:  # SHORT
                if current_price <= position['tp_price']:
                    return {'should_close': True, 'reason': 'TP_HIT', 'urgency': 'HIGH'}
                if current_price >= position['sl_price']:
                    return {'should_close': True, 'reason': 'SL_HIT', 'urgency': 'HIGH'}
            
            # Vérifier trailing stop
            if position.get('trailing_sl'):
                if position['direction'] == 'LONG' and current_price <= position['trailing_sl']:
                    return {'should_close': True, 'reason': 'TRAILING_STOP', 'urgency': 'HIGH'}
                elif position['direction'] == 'SHORT' and current_price >= position['trailing_sl']:
                    return {'should_close': True, 'reason': 'TRAILING_STOP', 'urgency': 'HIGH'}
            
            # Vérifier early invalidation
            if position.get('invalidation_warning'):
                return {'should_close': True, 'reason': 'EARLY_INVALIDATION', 'urgency': 'MEDIUM'}
            
            return {'should_close': False, 'reason': 'Criteria not met'}
            
        except Exception as e:
            logger.error(f"Should close position failed: {e}")
            return {'should_close': False, 'error': str(e)}


# =============================================================================
# MOCKS POUR DÉPENDANCES - Permettent tests sans vrais modules
# =============================================================================

class MockTPSLCalculator:
    """Mock du calculateur TP/SL pour tests"""
    
    def calculate_levels(self, entry: float, tp: float, sl: float, direction: str):
        """Mock calcul TP/SL"""
        return tp, sl  # Retourne tel quel pour tests


class MockPnLCalculator:
    """Mock du calculateur PnL pour tests"""
    
    def calculate_unrealized_pnl(self, entry: float, current: float, size: float, direction: str):
        """Mock calcul PnL"""
        if direction == 'LONG':
            pnl = (current - entry) * size
        else:
            pnl = (entry - current) * size
        
        pnl_pct = (pnl / (entry * size)) * 100 if entry > 0 and size > 0 else 0
        
        return {
            'unrealized_pnl': pnl,
            'pnl_pct': pnl_pct,
            'entry_price': entry,
            'current_price': current
        }


class MockRecoveryManager:
    """Mock du gestionnaire recovery pour tests"""
    
    def get_state(self, loss_streak: int):
        """Mock état recovery"""
        if loss_streak >= 5:
            return {
                'active': True,
                'level': 3,
                'position_size_mult': 0.5,
                'min_score_boost': 2.5,
                'confluence_forced': True
            }
        elif loss_streak >= 3:
            return {
                'active': True,
                'level': 2,
                'position_size_mult': 0.7,
                'min_score_boost': 1.5,
                'confluence_forced': False
            }
        elif loss_streak >= 2:
            return {
                'active': True,
                'level': 1,
                'position_size_mult': 0.85,
                'min_score_boost': 0.5,
                'confluence_forced': False
            }
        else:
            return {
                'active': False,
                'level': None,
                'position_size_mult': 1.0,
                'min_score_boost': 0.0,
                'confluence_forced': False
            }


class MockTrailingStopManager:
    """Mock du gestionnaire trailing stop pour tests"""
    
    def update(self, position: Dict, current_price: float):
        """Mock update trailing stop"""
        # Logique simplifiée pour tests
        if 'trailing_sl' not in position:
            # Activer trailing si profit > 1.5x ATR
            profit = current_price - position['entry_price'] if position['direction'] == 'LONG' else position['entry_price'] - current_price
            if profit > position.get('atr', 1.0) * 1.5:
                position['trailing_sl'] = position['sl_price']
        
        return {'trailing_updated': True}


class MockEarlyInvalidationChecker:
    """Mock du checker early invalidation pour tests"""
    
    def check(self, position: Dict, market_data: Dict):
        """Mock check invalidation"""
        # Logique simplifiée pour tests
        current_price = market_data.get('price', position['entry_price'])
        entry = position['entry_price']
        
        # Invalider si mouvement adverse > 0.5%
        if position['direction'] == 'LONG':
            adverse_move = (entry - current_price) / entry
        else:
            adverse_move = (current_price - entry) / entry
        
        if adverse_move > 0.005:  # 0.5%
            return {
                'should_invalidate': True,
                'reason': f'Adverse move: {adverse_move:.3f}%'
            }
        
        return {'should_invalidate': False}


class MockAnalyticsLogger:
    """Mock du logger analytics pour tests"""
    
    def log_position_opened(self, position: Dict):
        """Mock log ouverture"""
        logger.debug(f"Analytics: Position opened {position['id']}")
    
    def log_position_closed(self, position: Dict, reason: str):
        """Mock log fermeture"""
        logger.debug(f"Analytics: Position closed {position['id']} - {reason}")

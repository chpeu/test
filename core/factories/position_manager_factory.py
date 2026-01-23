#!/usr/bin/env python3
"""
PositionManager Factory - Trade Cursor v7.0
Factory pattern pour basculement sécurisé entre implémentations
ZÉRO RISQUE - Permet rollback instantané vers code existant
"""

import logging
from typing import Dict, Any, Optional
from core.interfaces.position_manager_interface import IPositionManager, PositionManagerConfig

logger = logging.getLogger(__name__)


class PositionManagerFactory:
    """
    Factory pour créer PositionManager selon mode (legacy/testable)
    
    Permet basculement sécurisé avec rollback instantané:
    - Mode legacy: Code existant inchangé
    - Mode testable: Version avec injection dépendances
    - Feature flags pour contrôle total
    """
    
    _legacy_cache = None
    _testable_cache = {}
    
    @staticmethod
    def create(
        testing_mode: bool = False,
        config: Optional[PositionManagerConfig] = None,
        dependencies: Optional[Dict[str, Any]] = None,
        force_new: bool = False
    ) -> IPositionManager:
        """
        Créer PositionManager selon mode
        
        Args:
            testing_mode: True = version testable, False = legacy
            config: Configuration optionnelle
            dependencies: Dépendances injectées pour tests
            force_new: Force nouvelle instance (pas de cache)
            
        Returns:
            IPositionManager: Instance selon mode
        """
        try:
            if testing_mode:
                return PositionManagerFactory._create_testable(config, dependencies, force_new)
            else:
                return PositionManagerFactory._create_legacy(force_new)
                
        except Exception as e:
            logger.error(f"Factory creation failed: {e}")
            # Fallback vers legacy en cas d'erreur
            return PositionManagerFactory._create_legacy_fallback()
    
    @staticmethod
    def _create_legacy(force_new: bool = False) -> IPositionManager:
        """Créer instance legacy (code existant)"""
        
        if not force_new and PositionManagerFactory._legacy_cache:
            return PositionManagerFactory._legacy_cache
            
        try:
            # Essayer d'importer le vrai PositionManager
            from core.position_manager import PositionManager
            
            # Wrapper pour compatibilité interface
            legacy_wrapper = LegacyPositionManagerWrapper(PositionManager())
            
            if not force_new:
                PositionManagerFactory._legacy_cache = legacy_wrapper
                
            logger.info("✅ Legacy PositionManager créé")
            return legacy_wrapper
            
        except ImportError as e:
            logger.warning(f"Import legacy failed: {e}")
            return PositionManagerFactory._create_legacy_fallback()
    
    @staticmethod
    def _create_testable(
        config: Optional[PositionManagerConfig],
        dependencies: Optional[Dict[str, Any]],
        force_new: bool = False
    ) -> IPositionManager:
        """Créer instance testable avec dépendances injectées"""
        
        cache_key = f"{id(config)}_{id(dependencies)}"
        
        if not force_new and cache_key in PositionManagerFactory._testable_cache:
            return PositionManagerFactory._testable_cache[cache_key]
        
        try:
            from core.implementations.testable_position_manager import TestablePositionManager
            
            testable = TestablePositionManager(config or PositionManagerConfig(), dependencies)
            
            if not force_new:
                PositionManagerFactory._testable_cache[cache_key] = testable
                
            logger.info("✅ Testable PositionManager créé")
            return testable
            
        except ImportError as e:
            logger.error(f"Import testable failed: {e}")
            # Fallback vers legacy
            return PositionManagerFactory._create_legacy()
    
    @staticmethod
    def _create_legacy_fallback() -> IPositionManager:
        """Fallback d'urgence - Mock basic"""
        logger.warning("🔴 Utilisation fallback mock - Mode dégradé")
        return MockPositionManager()
    
    @staticmethod
    def clear_cache():
        """Vider cache pour tests"""
        PositionManagerFactory._legacy_cache = None
        PositionManagerFactory._testable_cache.clear()
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """Stats cache pour monitoring"""
        return {
            'legacy_cached': PositionManagerFactory._legacy_cache is not None,
            'testable_cached_count': len(PositionManagerFactory._testable_cache),
            'total_instances': (1 if PositionManagerFactory._legacy_cache else 0) + len(PositionManagerFactory._testable_cache)
        }


class LegacyPositionManagerWrapper(IPositionManager):
    """
    Wrapper pour legacy PositionManager
    Adapte interface sans modifier le code existant - ZÉRO RISQUE
    """
    
    def __init__(self, legacy_pm):
        self._legacy = legacy_pm
        logger.debug("Legacy wrapper créé")
    
    def calculate_position_size(self, setup, capital: float) -> float:
        """Adapter interface vers legacy"""
        try:
            # Convertir setup vers format legacy
            from core.interfaces.position_manager_interface import setup_to_dict
            legacy_setup = setup_to_dict(setup) if hasattr(setup, 'symbol') else setup
            
            # Appel legacy method
            return self._legacy.calculate_position_size(legacy_setup, capital)
            
        except Exception as e:
            logger.error(f"Legacy calculate_position_size failed: {e}")
            return 0.0
    
    def open_position(self, setup):
        """Adapter ouverture position"""
        try:
            from core.interfaces.position_manager_interface import setup_to_dict, PositionResult
            legacy_setup = setup_to_dict(setup) if hasattr(setup, 'symbol') else setup
            
            # Appel méthode legacy 
            result = self._legacy.open_position(
                legacy_setup['symbol'],
                legacy_setup['direction'], 
                legacy_setup
            )
            
            # Convertir résultat
            if isinstance(result, bool):
                return PositionResult(
                    success=result,
                    position_size=legacy_setup.get('position_size', 0),
                    message="Legacy position opened" if result else "Legacy position failed"
                )
            else:
                return result
                
        except Exception as e:
            logger.error(f"Legacy open_position failed: {e}")
            from core.interfaces.position_manager_interface import PositionResult
            return PositionResult(False, 0.0, f"Error: {e}")
    
    def close_position(self, position_id: str, reason: str = "Manual") -> bool:
        """Adapter fermeture position"""
        try:
            if hasattr(self._legacy, 'close_position'):
                return self._legacy.close_position(position_id, reason)
            else:
                # Fallback si méthode pas disponible
                logger.warning("Legacy close_position not available")
                return False
        except Exception as e:
            logger.error(f"Legacy close_position failed: {e}")
            return False
    
    def get_active_positions(self):
        """Adapter récupération positions actives"""
        try:
            if hasattr(self._legacy, 'get_active_positions'):
                return self._legacy.get_active_positions()
            elif hasattr(self._legacy, 'active_positions'):
                return self._legacy.active_positions or []
            else:
                return []
        except Exception as e:
            logger.error(f"Legacy get_active_positions failed: {e}")
            return []
    
    def get_recovery_state(self, loss_streak: int):
        """Adapter récupération état recovery"""
        try:
            if hasattr(self._legacy, 'recovery_mode') and self._legacy.recovery_mode:
                return self._legacy.recovery_mode.get_state(loss_streak)
            else:
                # État par défaut
                return {
                    'active': False,
                    'level': None,
                    'position_size_mult': 1.0,
                    'min_score_boost': 0.0
                }
        except Exception as e:
            logger.error(f"Legacy get_recovery_state failed: {e}")
            return {'active': False, 'position_size_mult': 1.0}
    
    def update_position_status(self, position_id: str, market_data):
        """Adapter mise à jour statut"""
        try:
            if hasattr(self._legacy, 'update_position_status'):
                return self._legacy.update_position_status(position_id, market_data)
            else:
                return {'updated': False, 'reason': 'Method not available in legacy'}
        except Exception as e:
            logger.error(f"Legacy update_position_status failed: {e}")
            return {'error': str(e)}
    
    def calculate_pnl(self, position_id: str, current_price: float):
        """Adapter calcul PnL"""
        try:
            if hasattr(self._legacy, 'calculate_pnl'):
                return self._legacy.calculate_pnl(position_id, current_price)
            else:
                return {'unrealized_pnl': 0.0, 'pnl_pct': 0.0}
        except Exception as e:
            logger.error(f"Legacy calculate_pnl failed: {e}")
            return {'error': str(e)}
    
    def should_close_position(self, position_id: str, market_data):
        """Adapter décision fermeture"""
        try:
            if hasattr(self._legacy, 'should_close_position'):
                return self._legacy.should_close_position(position_id, market_data)
            else:
                return {'should_close': False, 'reason': 'No decision logic in legacy'}
        except Exception as e:
            logger.error(f"Legacy should_close_position failed: {e}")
            return {'should_close': False, 'error': str(e)}


class MockPositionManager(IPositionManager):
    """Mock de base pour fallback d'urgence"""
    
    def __init__(self):
        self.positions = {}
        logger.warning("🔧 MockPositionManager actif - Mode dégradé")
    
    def calculate_position_size(self, setup, capital: float) -> float:
        """Mock calcul position"""
        try:
            risk_pct = setup.get('risk_per_trade', 2.0) if isinstance(setup, dict) else setup.risk_per_trade
            entry = setup.get('entry_price', 100) if isinstance(setup, dict) else setup.entry_price
            sl = setup.get('sl_price', 95) if isinstance(setup, dict) else setup.sl_price
            
            spread = abs(entry - sl)
            risk_amount = capital * (risk_pct / 100)
            return risk_amount / spread if spread > 0 else 0.0
            
        except Exception:
            return capital * 0.02  # 2% par défaut
    
    def open_position(self, setup):
        from core.interfaces.position_manager_interface import PositionResult
        position_id = f"mock_{len(self.positions)}"
        self.positions[position_id] = setup
        return PositionResult(True, 10.0, f"Mock position {position_id}")
    
    def close_position(self, position_id: str, reason: str = "Manual") -> bool:
        return self.positions.pop(position_id, None) is not None
    
    def get_active_positions(self):
        return list(self.positions.values())
    
    def get_recovery_state(self, loss_streak: int):
        return {'active': False, 'position_size_mult': 1.0}
    
    def update_position_status(self, position_id: str, market_data):
        return {'updated': True, 'mock': True}
    
    def calculate_pnl(self, position_id: str, current_price: float):
        return {'unrealized_pnl': 0.0, 'pnl_pct': 0.0, 'mock': True}
    
    def should_close_position(self, position_id: str, market_data):
        return {'should_close': False, 'mock': True}

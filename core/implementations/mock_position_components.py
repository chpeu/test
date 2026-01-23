"""
Mock Components pour tests unitaires
Implémentations simulées pour isolation complète des tests
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..interfaces.position_interfaces import (
    IPositionExecutor, IPositionRepository, PositionStatus
)

logger = logging.getLogger(__name__)


class MockPositionExecutor(IPositionExecutor):
    """
    Mock Executor pour tests sans API réelle
    
    Simule:
    - Ouverture/fermeture positions
    - Latence réseau
    - Erreurs d'exécution
    - Slippage
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.simulated_latency = config.get('simulated_latency_ms', 100)
        self.success_rate = config.get('success_rate', 0.95)
        self.slippage_rate = config.get('slippage_rate', 0.001)  # 0.1%
        
        # État interne pour simulation
        self.executed_positions = {}
        self.execution_count = 0
        
        logger.info("✅ MockPositionExecutor initialisé")
    
    async def open_position(self, setup: Dict[str, Any], position_size) -> Dict[str, Any]:
        """
        Simule ouverture de position
        
        Returns:
            Dict avec détails d'exécution simulée
        """
        try:
            self.execution_count += 1
            position_id = f"mock_pos_{uuid.uuid4().hex[:8]}"
            
            # Simuler latence
            await self._simulate_latency()
            
            # Simuler échec occasionnel
            if not self._simulate_success():
                return {
                    'success': False,
                    'position_id': None,
                    'error': 'Simulated execution failure',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Calculer prix d'exécution avec slippage
            requested_price = float(setup.get('current_price', 100))
            executed_price = self._apply_slippage(requested_price, setup.get('side', 'long'))
            
            # Créer position simulée
            position_data = {
                'position_id': position_id,
                'symbol': setup.get('symbol', 'BTCUSDT'),
                'side': setup.get('side', 'long'),
                'size': position_size.final_size,
                'requested_price': requested_price,
                'executed_price': executed_price,
                'slippage': abs(executed_price - requested_price),
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'OPEN',
                'stop_loss': setup.get('stop_loss'),
                'take_profit': setup.get('take_profit')
            }
            
            self.executed_positions[position_id] = position_data
            
            logger.info(f"✅ Mock position ouverte: {position_id} ({setup.get('symbol')}, {position_size.final_size})")
            
            return {
                'success': True,
                'position_id': position_id,
                'executed_price': executed_price,
                'slippage': abs(executed_price - requested_price),
                'commission': self._calculate_commission(position_size.final_size, executed_price),
                'timestamp': datetime.utcnow().isoformat(),
                'execution_latency_ms': self.simulated_latency
            }
            
        except Exception as e:
            logger.error(f"Mock execution error: {e}")
            return {
                'success': False,
                'position_id': None,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def close_position(self, position_id: str) -> Dict[str, Any]:
        """Simule fermeture de position"""
        try:
            await self._simulate_latency()
            
            if position_id not in self.executed_positions:
                return {
                    'success': False,
                    'error': f'Position not found: {position_id}',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            position = self.executed_positions[position_id]
            
            # Simuler échec occasionnel
            if not self._simulate_success():
                return {
                    'success': False,
                    'error': 'Simulated close failure',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Prix de fermeture simulé (prix d'ouverture +/- variation)
            open_price = position['executed_price']
            close_price = self._simulate_close_price(open_price, position['side'])
            
            # Calculer PnL
            pnl = self._calculate_pnl(position, close_price)
            
            # Mettre à jour position
            position['status'] = 'CLOSED'
            position['close_price'] = close_price
            position['pnl'] = pnl
            position['close_timestamp'] = datetime.utcnow().isoformat()
            
            logger.info(f"✅ Mock position fermée: {position_id} (PnL: {pnl:.2f})")
            
            return {
                'success': True,
                'position_id': position_id,
                'close_price': close_price,
                'pnl': pnl,
                'commission': self._calculate_commission(position['size'], close_price),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Mock close error: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def update_position(self, position_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Simule mise à jour de position"""
        try:
            await self._simulate_latency()
            
            if position_id not in self.executed_positions:
                return {
                    'success': False,
                    'error': f'Position not found: {position_id}',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Simuler échec occasionnel
            if not self._simulate_success():
                return {
                    'success': False,
                    'error': 'Simulated update failure',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Appliquer updates
            position = self.executed_positions[position_id]
            position.update(updates)
            position['last_updated'] = datetime.utcnow().isoformat()
            
            logger.info(f"✅ Mock position mise à jour: {position_id}")
            
            return {
                'success': True,
                'position_id': position_id,
                'updates_applied': list(updates.keys()),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Mock update error: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _simulate_latency(self):
        """Simule latence réseau"""
        import asyncio
        await asyncio.sleep(self.simulated_latency / 1000.0)
    
    def _simulate_success(self) -> bool:
        """Simule succès/échec basé sur success_rate"""
        import random
        return random.random() < self.success_rate
    
    def _apply_slippage(self, price: float, side: str) -> float:
        """Applique slippage simulé"""
        import random
        slippage = random.uniform(0, self.slippage_rate)
        
        if side.lower() == 'long':
            # Long: prix d'achat légèrement plus élevé
            return price * (1 + slippage)
        else:
            # Short: prix de vente légèrement plus bas
            return price * (1 - slippage)
    
    def _simulate_close_price(self, open_price: float, side: str) -> float:
        """Simule prix de fermeture"""
        import random
        
        # Variation aléatoire -2% à +2%
        variation = random.uniform(-0.02, 0.02)
        close_price = open_price * (1 + variation)
        
        # Appliquer slippage de fermeture
        return self._apply_slippage(close_price, 'short' if side.lower() == 'long' else 'long')
    
    def _calculate_pnl(self, position: Dict[str, Any], close_price: float) -> float:
        """Calcule PnL simulé"""
        open_price = position['executed_price']
        size = position['size']
        side = position['side'].lower()
        
        if side == 'long':
            pnl = (close_price - open_price) * size / open_price
        else:
            pnl = (open_price - close_price) * size / open_price
        
        return pnl
    
    def _calculate_commission(self, size: float, price: float) -> float:
        """Calcule commission simulée"""
        commission_rate = 0.001  # 0.1%
        return size * price * commission_rate


class MockPositionRepository(IPositionRepository):
    """
    Mock Repository pour tests sans base de données
    
    Simule:
    - Persistance en mémoire
    - Délais de DB
    - Erreurs de connexion
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.simulate_db_delay = config.get('simulate_db_delay_ms', 10)
        self.failure_rate = config.get('failure_rate', 0.01)  # 1% d'échec
        
        # Stockage en mémoire
        self.positions = {}
        self.save_count = 0
        
        logger.info("✅ MockPositionRepository initialisé")
    
    def save_position(self, position_data: Dict[str, Any]) -> str:
        """Simule sauvegarde en base"""
        try:
            self._simulate_db_delay()
            
            if self._simulate_failure():
                raise Exception("Simulated database save failure")
            
            position_id = position_data.get('position_id', f"repo_pos_{uuid.uuid4().hex[:8]}")
            
            # Ajouter métadonnées de persistance
            position_data['saved_at'] = datetime.utcnow().isoformat()
            position_data['repository_id'] = position_id
            
            self.positions[position_id] = position_data.copy()
            self.save_count += 1
            
            logger.debug(f"✅ Position sauvée (mock): {position_id}")
            
            return position_id
            
        except Exception as e:
            logger.error(f"Mock save error: {e}")
            raise
    
    def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Simule récupération depuis base"""
        try:
            self._simulate_db_delay()
            
            if self._simulate_failure():
                raise Exception("Simulated database read failure")
            
            position = self.positions.get(position_id)
            
            if position:
                # Ajouter métadonnées de lecture
                position['retrieved_at'] = datetime.utcnow().isoformat()
                logger.debug(f"✅ Position récupérée (mock): {position_id}")
            else:
                logger.debug(f"❌ Position non trouvée (mock): {position_id}")
            
            return position
            
        except Exception as e:
            logger.error(f"Mock get error: {e}")
            raise
    
    def update_position_status(self, position_id: str, status: PositionStatus) -> bool:
        """Simule mise à jour statut"""
        try:
            self._simulate_db_delay()
            
            if self._simulate_failure():
                raise Exception("Simulated database update failure")
            
            if position_id not in self.positions:
                return False
            
            self.positions[position_id]['status'] = status.value
            self.positions[position_id]['status_updated_at'] = datetime.utcnow().isoformat()
            
            logger.debug(f"✅ Statut mis à jour (mock): {position_id} -> {status.value}")
            
            return True
            
        except Exception as e:
            logger.error(f"Mock update status error: {e}")
            raise
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Simule récupération positions ouvertes"""
        try:
            self._simulate_db_delay()
            
            if self._simulate_failure():
                raise Exception("Simulated database query failure")
            
            open_positions = [
                pos for pos in self.positions.values()
                if pos.get('status') == 'OPEN'
            ]
            
            logger.debug(f"✅ {len(open_positions)} positions ouvertes récupérées (mock)")
            
            return open_positions
            
        except Exception as e:
            logger.error(f"Mock get open positions error: {e}")
            raise
    
    def _simulate_db_delay(self):
        """Simule délai base de données"""
        import time
        time.sleep(self.simulate_db_delay / 1000.0)
    
    def _simulate_failure(self) -> bool:
        """Simule échec de DB"""
        import random
        return random.random() < self.failure_rate
    
    # Méthodes utilitaires pour tests
    def clear_all_positions(self):
        """Vide le repository (utile pour tests)"""
        self.positions.clear()
        self.save_count = 0
        logger.info("🧹 Mock repository vidé")
    
    def get_stats(self) -> Dict[str, Any]:
        """Statistiques du repository mock"""
        return {
            'total_positions': len(self.positions),
            'open_positions': len([p for p in self.positions.values() if p.get('status') == 'OPEN']),
            'closed_positions': len([p for p in self.positions.values() if p.get('status') == 'CLOSED']),
            'save_count': self.save_count,
            'config': self.config
        }


class MockDataProvider:
    """
    Mock provider pour données de marché
    Utile pour tests d'intégration
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.generate_realistic_data = config.get('realistic_data', True)
        
        logger.info("✅ MockDataProvider initialisé")
    
    def get_current_price(self, symbol: str) -> float:
        """Prix courant simulé"""
        # Prix de base par symbol
        base_prices = {
            'BTCUSDT': 45000,
            'ETHUSDT': 3000,
            'BNBUSDT': 300,
            'ADAUSDT': 0.5,
            'XRPUSDT': 0.6
        }
        
        base_price = base_prices.get(symbol, 100)
        
        if self.generate_realistic_data:
            import random
            # Variation aléatoire -1% à +1%
            variation = random.uniform(-0.01, 0.01)
            return base_price * (1 + variation)
        else:
            return base_price
    
    def get_atr(self, symbol: str, period: int = 14) -> float:
        """ATR simulé"""
        price = self.get_current_price(symbol)
        
        if self.generate_realistic_data:
            import random
            # ATR entre 0.5% et 3% du prix
            atr_ratio = random.uniform(0.005, 0.03)
            return price * atr_ratio
        else:
            return price * 0.02  # 2% par défaut
    
    def get_volume_24h(self, symbol: str) -> float:
        """Volume 24h simulé"""
        if self.generate_realistic_data:
            import random
            return random.uniform(1000000, 10000000)
        else:
            return 5000000
    
    def generate_test_setup(self, symbol: str = 'BTCUSDT', side: str = 'long') -> Dict[str, Any]:
        """Génère setup de test réaliste"""
        import random
        
        current_price = self.get_current_price(symbol)
        atr = self.get_atr(symbol)
        volume = self.get_volume_24h(symbol)
        
        return {
            'symbol': symbol,
            'side': side,
            'current_price': current_price,
            'atr': atr,
            'volume': volume,
            'score_1m': random.uniform(3.0, 8.0) if self.generate_realistic_data else 6.0,
            'score_5m': random.uniform(3.0, 8.0) if self.generate_realistic_data else 5.5,
            'volatility_score': random.uniform(0.5, 2.0) if self.generate_realistic_data else 1.0,
            'risk_percentage': random.uniform(1.0, 3.0) if self.generate_realistic_data else 2.0,
            'timestamp': datetime.utcnow().isoformat()
        }

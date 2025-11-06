"""
🔥 PHASE 8: Filtre corrélation dynamique basé sur prix réels
Calcul de corrélation Pearson entre symboles pour éviter surexposition
"""
import logging
from typing import List, Dict, Optional
from collections import deque

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("⚠️ numpy non disponible - Corrélation dynamique désactivée")


class DynamicCorrelationFilter:
    """Filtre corrélation dynamique basé sur prix réels"""
    
    def __init__(self, period: int = 50, threshold: float = 0.7):
        self.period = period
        self.threshold = threshold
        self.price_history = {}  # {symbol: deque([prices])}
    
    def update_price(self, symbol: str, price: float):
        """Mettre à jour historique prix"""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.period)
        
        self.price_history[symbol].append(price)
    
    def calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """
        Calculer corrélation Pearson entre 2 symboles
        
        Returns:
            Corrélation entre -1.0 et 1.0
        """
        if not NUMPY_AVAILABLE:
            return 0.0
        
        if symbol1 not in self.price_history or symbol2 not in self.price_history:
            return 0.0
        
        prices1 = list(self.price_history[symbol1])
        prices2 = list(self.price_history[symbol2])
        
        # Besoin minimum de données
        if len(prices1) < 20 or len(prices2) < 20:
            return 0.0
        
        # Aligner longueurs
        min_len = min(len(prices1), len(prices2))
        prices1 = prices1[-min_len:]
        prices2 = prices2[-min_len:]
        
        # Calculer returns
        returns1 = np.diff(prices1) / prices1[:-1]
        returns2 = np.diff(prices2) / prices2[:-1]
        
        # Corrélation Pearson
        if len(returns1) > 0 and len(returns2) > 0:
            correlation = np.corrcoef(returns1, returns2)[0, 1]
            return float(correlation) if not np.isnan(correlation) else 0.0
        
        return 0.0
    
    def check_correlation(self, symbol: str, active_positions: List) -> Dict:
        """
        Vérifier corrélation avec positions actives
        
        Returns:
            Dict avec valid, penalty, correlation, correlated_with
        """
        if not active_positions:
            return {'valid': True, 'penalty': 0, 'correlation': 0}
        
        max_correlation = 0
        correlated_symbol = None
        
        for pos in active_positions:
            if pos.symbol and pos.symbol != symbol:
                corr = self.calculate_correlation(symbol, pos.symbol)
                
                if abs(corr) > abs(max_correlation):
                    max_correlation = corr
                    correlated_symbol = pos.symbol
        
        # Vérifier seuil
        if abs(max_correlation) > self.threshold:
            # Corrélation forte détectée
            penalty = -1.5 * (abs(max_correlation) - self.threshold) / (1 - self.threshold)
            penalty = max(-3.0, penalty)  # Max -3.0 points
            
            return {
                'valid': True,  # Mode SOFT : pénalité, pas rejet
                'penalty': penalty,
                'correlation': max_correlation,
                'correlated_with': correlated_symbol
            }
        
        return {
            'valid': True,
            'penalty': 0,
            'correlation': max_correlation,
            'correlated_with': None
        }


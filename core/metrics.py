"""
Métriques par condition pour optimisation
"""
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ConditionMetrics:
    """Tracker winrate par condition"""
    
    def __init__(self):
        self.condition_stats: Dict[str, Dict] = {}  # {condition: {'wins': 0, 'losses': 0, 'total': 0, 'winrate': 0.0}}
        self.combination_stats: Dict[tuple, Dict] = {}  # {('EMAs', 'MACD'): {...}}
    
    def record_trade(self, conditions: List[str], won: bool):
        """
        Enregistrer trade avec ses conditions
        
        Args:
            conditions: Liste des types de conditions (ex: ['EMAs', 'MACD', 'ADX_DI'])
            won: True si trade gagnant, False si perdant
        """
        if not conditions:
            return
        
        # Enregistrer chaque condition individuellement
        for condition in conditions:
            if condition not in self.condition_stats:
                self.condition_stats[condition] = {
                    'wins': 0,
                    'losses': 0,
                    'total': 0,
                    'winrate': 0.0
                }
            
            self.condition_stats[condition]['total'] += 1
            
            if won:
                self.condition_stats[condition]['wins'] += 1
            else:
                self.condition_stats[condition]['losses'] += 1
            
            # Calculer winrate
            total = self.condition_stats[condition]['total']
            wins = self.condition_stats[condition]['wins']
            self.condition_stats[condition]['winrate'] = (wins / total) * 100 if total > 0 else 0.0
        
        # Enregistrer combinaisons (paires de conditions)
        if len(conditions) >= 2:
            for i in range(len(conditions)):
                for j in range(i + 1, len(conditions)):
                    combo = tuple(sorted([conditions[i], conditions[j]]))
                    
                    if combo not in self.combination_stats:
                        self.combination_stats[combo] = {
                            'wins': 0,
                            'losses': 0,
                            'total': 0,
                            'winrate': 0.0
                        }
                    
                    self.combination_stats[combo]['total'] += 1
                    
                    if won:
                        self.combination_stats[combo]['wins'] += 1
                    else:
                        self.combination_stats[combo]['losses'] += 1
                    
                    total = self.combination_stats[combo]['total']
                    wins = self.combination_stats[combo]['wins']
                    self.combination_stats[combo]['winrate'] = (wins / total) * 100 if total > 0 else 0.0
    
    def get_best_conditions(self, min_samples: int = 10) -> List[Dict]:
        """
        Retourner meilleures conditions par winrate
        
        Args:
            min_samples: Nombre minimum d'échantillons pour inclure une condition
            
        Returns:
            Liste de dicts triée par winrate décroissant
        """
        results = []
        
        for condition, stats in self.condition_stats.items():
            if stats['total'] >= min_samples:
                results.append({
                    'condition': condition,
                    'winrate': round(stats['winrate'], 2),
                    'wins': stats['wins'],
                    'losses': stats['losses'],
                    'total': stats['total']
                })
        
        # Trier par winrate
        results.sort(key=lambda x: x['winrate'], reverse=True)
        return results
    
    def get_worst_conditions(self, min_samples: int = 10) -> List[Dict]:
        """
        Retourner pires conditions par winrate
        
        Args:
            min_samples: Nombre minimum d'échantillons
            
        Returns:
            Liste de dicts triée par winrate croissant
        """
        results = self.get_best_conditions(min_samples)
        results.reverse()  # Inverser tri
        return results
    
    def get_best_combinations(self, min_samples: int = 5) -> List[Dict]:
        """
        Retourner meilleures combinaisons de conditions
        
        Args:
            min_samples: Nombre minimum d'échantillons
            
        Returns:
            Liste de dicts avec combinaisons triées par winrate
        """
        results = []
        
        for combo, stats in self.combination_stats.items():
            if stats['total'] >= min_samples:
                results.append({
                    'combination': ' + '.join(combo),
                    'winrate': round(stats['winrate'], 2),
                    'wins': stats['wins'],
                    'losses': stats['losses'],
                    'total': stats['total']
                })
        
        results.sort(key=lambda x: x['winrate'], reverse=True)
        return results
    
    def get_stats_summary(self) -> Dict:
        """
        Retourner résumé des statistiques
        
        Returns:
            Dict avec best_conditions, worst_conditions, best_combinations
        """
        return {
            'best_conditions': self.get_best_conditions(min_samples=5)[:10],
            'worst_conditions': self.get_worst_conditions(min_samples=5)[:10],
            'best_combinations': self.get_best_combinations(min_samples=3)[:10],
            'all_conditions': self.condition_stats,
            'all_combinations': {f"{'+'.join(k)}": v for k, v in self.combination_stats.items()}
        }
    
    def reset(self):
        """Réinitialiser toutes les statistiques"""
        self.condition_stats = {}
        self.combination_stats = {}
        logger.info("📊 Métriques conditions réinitialisées")


# Instance globale
condition_metrics = ConditionMetrics()


# 🔥 Compatibilité : Fonction pour get_metrics_collector (si utilisé ailleurs)
class MetricsCollector:
    """Wrapper pour compatibilité avec code existant"""
    
    def __init__(self):
        self.condition_metrics = condition_metrics
        self.ws_connected = False  # 🔥 Compatibilité : Attribut utilisé dans price_provider.py
        self.ws_price_count = 0  # 🔥 Compatibilité : Compteur de prix WebSocket
        self.rest_price_count = 0  # 🔥 Compatibilité : Compteur de prix REST (si utilisé)
        self.ws_rest_fallback_count = 0  # 🔥 Compatibilité : Compteur de fallback REST
        self.positions_closed = 0  # 🔥 Compatibilité : Compteur de positions fermées
        self.trades_wins = 0  # 🔥 Compatibilité : Compteur de trades gagnants
        self.trades_losses = 0  # 🔥 Compatibilité : Compteur de trades perdants
    
    def record_trade(self, conditions: List[str], won: bool):
        """Alias pour condition_metrics.record_trade"""
        condition_metrics.record_trade(conditions, won)
    
    def get_stats(self):
        """Alias pour condition_metrics.get_stats_summary"""
        return condition_metrics.get_stats_summary()


# Instance globale pour compatibilité
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Retourner l'instance globale de MetricsCollector (compatibilité)"""
    return _metrics_collector

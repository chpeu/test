#!/usr/bin/env python3
"""
Système de métriques pour monitoring
- Latence des requêtes
- Success rate
- Erreurs
- Performance
"""
import time
from typing import Dict, List, Optional
from collections import defaultdict, deque
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collecteur de métriques pour monitoring"""
    
    def __init__(self, max_history: int = 1000):
        """
        Args:
            max_history: Nombre max de métriques à garder en mémoire
        """
        self.max_history = max_history
        
        # Métriques de latence
        self.latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        
        # Métriques de succès/échec
        self.success_count: Dict[str, int] = defaultdict(int)
        self.error_count: Dict[str, int] = defaultdict(int)
        self.total_count: Dict[str, int] = defaultdict(int)
        
        # Métriques d'erreurs
        self.errors: List[Dict] = []
        
        # Métriques de performance
        self.start_time = time.time()
        self.requests_total = 0
        self.requests_by_endpoint: Dict[str, int] = defaultdict(int)
        
        # Métriques WebSocket
        self.ws_connected = False
        self.ws_price_count = 0
        self.ws_rest_fallback_count = 0
        
        # Métriques trading
        self.setups_detected = 0
        self.positions_opened = 0
        self.positions_closed = 0
        self.trades_wins = 0
        self.trades_losses = 0
    
    def record_latency(self, operation: str, latency_ms: float):
        """Enregistrer une latence"""
        self.latencies[operation].append(latency_ms)
    
    def record_success(self, operation: str):
        """Enregistrer un succès"""
        self.success_count[operation] += 1
        self.total_count[operation] += 1
        self.requests_total += 1
    
    def record_error(self, operation: str, error: str):
        """Enregistrer une erreur"""
        self.error_count[operation] += 1
        self.total_count[operation] += 1
        self.requests_total += 1
        
        # Garder les 100 dernières erreurs
        self.errors.append({
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'error': str(error)
        })
        if len(self.errors) > 100:
            self.errors.pop(0)
    
    def record_request(self, endpoint: str):
        """Enregistrer une requête"""
        self.requests_by_endpoint[endpoint] += 1
    
    def get_latency_stats(self, operation: str) -> Optional[Dict]:
        """Obtenir les statistiques de latence pour une opération"""
        if operation not in self.latencies or not self.latencies[operation]:
            return None
        
        latencies = list(self.latencies[operation])
        return {
            'count': len(latencies),
            'min': min(latencies),
            'max': max(latencies),
            'avg': sum(latencies) / len(latencies),
            'p50': self._percentile(latencies, 50),
            'p95': self._percentile(latencies, 95),
            'p99': self._percentile(latencies, 99)
        }
    
    def get_success_rate(self, operation: str) -> Optional[float]:
        """Obtenir le taux de succès pour une opération"""
        if operation not in self.total_count or self.total_count[operation] == 0:
            return None
        
        total = self.total_count[operation]
        success = self.success_count[operation]
        return (success / total) * 100
    
    def get_all_metrics(self) -> Dict:
        """Obtenir toutes les métriques"""
        uptime_seconds = time.time() - self.start_time
        
        # Latence par opération
        latency_stats = {}
        for operation in self.latencies.keys():
            stats = self.get_latency_stats(operation)
            if stats:
                latency_stats[operation] = stats
        
        # Success rate par opération
        success_rates = {}
        for operation in self.total_count.keys():
            rate = self.get_success_rate(operation)
            if rate is not None:
                success_rates[operation] = rate
        
        # Top endpoints
        top_endpoints = sorted(
            self.requests_by_endpoint.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            'uptime_seconds': uptime_seconds,
            'requests_total': self.requests_total,
            'requests_by_endpoint': dict(top_endpoints),
            'latency_stats': latency_stats,
            'success_rates': success_rates,
            'error_count_total': sum(self.error_count.values()),
            'recent_errors': self.errors[-10:],  # 10 dernières erreurs
            'websocket': {
                'connected': self.ws_connected,
                'price_count': self.ws_price_count,
                'rest_fallback_count': self.ws_rest_fallback_count,
                'success_rate': (self.ws_price_count / (self.ws_price_count + self.ws_rest_fallback_count) * 100) 
                    if (self.ws_price_count + self.ws_rest_fallback_count) > 0 else 0
            },
            'trading': {
                'setups_detected': self.setups_detected,
                'positions_opened': self.positions_opened,
                'positions_closed': self.positions_closed,
                'trades_wins': self.trades_wins,
                'trades_losses': self.trades_losses,
                'winrate': (self.trades_wins / (self.trades_wins + self.trades_losses) * 100) 
                    if (self.trades_wins + self.trades_losses) > 0 else 0
            }
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculer un percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


# Instance globale
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Singleton pattern pour le collecteur de métriques"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector




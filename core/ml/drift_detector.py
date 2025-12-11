"""
Drift Detector - Phase 2D
=========================
Détecte les changements de comportement du marché (concept drift).
Alerte quand les performances se dégradent significativement.

Utilise l'algorithme ADWIN (Adaptive Windowing) pour détecter les drifts.

Usage:
    from core.ml.drift_detector import get_drift_detector
    
    detector = get_drift_detector()
    
    # Après chaque trade
    drift_info = detector.update(pnl=0.15, win=True)
    
    if drift_info['drift_detected']:
        # Déclencher réentraînement ou alerte
        trigger_retrain()

Auteur: Cascade AI
Date: 11/12/2025
"""

import json
import logging
import numpy as np
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Singleton instance
_detector_instance: Optional['MarketDriftDetector'] = None


@dataclass
class DriftEvent:
    """Événement de drift détecté."""
    timestamp: str
    drift_type: str  # 'pnl', 'winrate', 'combined'
    old_mean: float
    new_mean: float
    change_pct: float
    window_size: int
    severity: str  # 'low', 'medium', 'high'
    
    def to_dict(self) -> dict:
        return asdict(self)


class ADWINDetector:
    """
    Implémentation simplifiée de ADWIN (Adaptive Windowing).
    
    ADWIN maintient une fenêtre de données et détecte quand la moyenne
    de la fenêtre change significativement.
    """
    
    def __init__(self, delta: float = 0.002, min_window: int = 10):
        """
        Args:
            delta: Paramètre de confiance (plus petit = plus sensible)
            min_window: Taille minimale de fenêtre avant détection
        """
        self.delta = delta
        self.min_window = min_window
        self.window: deque = deque(maxlen=1000)
        self.total = 0.0
        self.variance = 0.0
        self.width = 0
    
    def update(self, value: float) -> bool:
        """
        Ajoute une valeur et vérifie s'il y a drift.
        
        Returns:
            True si drift détecté
        """
        self.window.append(value)
        self.width = len(self.window)
        
        if self.width < self.min_window:
            return False
        
        # Vérifier drift en comparant sous-fenêtres
        return self._check_drift()
    
    def _check_drift(self) -> bool:
        """Vérifie s'il y a un changement significatif dans la fenêtre."""
        n = len(self.window)
        if n < self.min_window * 2:
            return False
        
        # Diviser en deux sous-fenêtres
        mid = n // 2
        window_list = list(self.window)
        
        w1 = window_list[:mid]
        w2 = window_list[mid:]
        
        n1, n2 = len(w1), len(w2)
        if n1 == 0 or n2 == 0:
            return False
        
        mean1 = np.mean(w1)
        mean2 = np.mean(w2)
        
        # Calculer le seuil de détection
        m = 1.0 / ((1.0 / n1) + (1.0 / n2))
        epsilon = np.sqrt((1.0 / (2.0 * m)) * np.log(4.0 / self.delta))
        
        # Drift si la différence dépasse epsilon
        return abs(mean1 - mean2) > epsilon
    
    def get_mean(self) -> float:
        """Retourne la moyenne de la fenêtre."""
        if not self.window:
            return 0.0
        return np.mean(list(self.window))
    
    def get_stats(self) -> dict:
        """Retourne les statistiques de la fenêtre."""
        if not self.window:
            return {'mean': 0, 'std': 0, 'count': 0}
        
        window_list = list(self.window)
        return {
            'mean': np.mean(window_list),
            'std': np.std(window_list) if len(window_list) > 1 else 0,
            'count': len(window_list)
        }
    
    def reset(self) -> None:
        """Réinitialise la fenêtre."""
        self.window.clear()
        self.width = 0


class MarketDriftDetector:
    """
    Détecteur de drift pour le marché.
    
    Surveille:
    - PnL moyen: détecte si les trades deviennent moins rentables
    - WinRate: détecte si le taux de gain change
    - Volatilité: détecte si le comportement du marché change
    """
    
    def __init__(
        self,
        pnl_delta: float = 0.002,
        winrate_delta: float = 0.005,
        min_window: int = 20,
        alert_cooldown: int = 50,
        persistence_path: Optional[str] = None
    ):
        """
        Args:
            pnl_delta: Sensibilité pour PnL drift
            winrate_delta: Sensibilité pour WinRate drift
            min_window: Minimum de trades avant détection
            alert_cooldown: Trades entre alertes
            persistence_path: Chemin pour sauvegarder l'état
        """
        # Détecteurs ADWIN
        self.pnl_detector = ADWINDetector(delta=pnl_delta, min_window=min_window)
        self.winrate_detector = ADWINDetector(delta=winrate_delta, min_window=min_window)
        
        # Configuration
        self.alert_cooldown = alert_cooldown
        self.trades_since_alert = 0
        
        # Historique
        self.drift_history: List[DriftEvent] = []
        self.max_history = 100
        
        # État
        self.total_trades = 0
        self.enabled = True
        self.last_check = None
        
        # Persistence
        self.persistence_path = Path(persistence_path) if persistence_path else \
            Path("data/ml/drift_detector_state.json")
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Charger état précédent
        self._load_state()
        
        logger.info(f"✅ MarketDriftDetector initialisé (min_window: {min_window})")
    
    def update(self, pnl: float, win: bool) -> dict:
        """
        Met à jour les détecteurs après un trade.
        
        Args:
            pnl: PnL du trade (en %)
            win: True si trade gagnant
            
        Returns:
            Dict avec infos de drift
        """
        if not self.enabled:
            return {'drift_detected': False, 'enabled': False}
        
        self.total_trades += 1
        self.trades_since_alert += 1
        self.last_check = datetime.now().isoformat()
        
        # Mettre à jour les détecteurs
        pnl_drift = self.pnl_detector.update(pnl)
        winrate_drift = self.winrate_detector.update(1.0 if win else 0.0)
        
        # Vérifier cooldown
        if self.trades_since_alert < self.alert_cooldown:
            pnl_drift = False
            winrate_drift = False
        
        drift_detected = pnl_drift or winrate_drift
        
        result = {
            'drift_detected': drift_detected,
            'pnl_drift': pnl_drift,
            'winrate_drift': winrate_drift,
            'pnl_stats': self.pnl_detector.get_stats(),
            'winrate_stats': self.winrate_detector.get_stats(),
            'total_trades': self.total_trades,
            'last_check': self.last_check
        }
        
        # Enregistrer l'événement si drift détecté
        if drift_detected:
            self._record_drift_event(pnl_drift, winrate_drift)
            self.trades_since_alert = 0
            logger.warning(f"⚠️ DRIFT DÉTECTÉ! PnL: {pnl_drift}, WinRate: {winrate_drift}")
        
        # Sauvegarder périodiquement
        if self.total_trades % 50 == 0:
            self._save_state()
        
        return result
    
    def _record_drift_event(self, pnl_drift: bool, winrate_drift: bool) -> None:
        """Enregistre un événement de drift."""
        drift_type = 'combined' if (pnl_drift and winrate_drift) else \
                    ('pnl' if pnl_drift else 'winrate')
        
        pnl_stats = self.pnl_detector.get_stats()
        winrate_stats = self.winrate_detector.get_stats()
        
        # Calculer la sévérité
        if drift_type == 'combined':
            severity = 'high'
        elif pnl_stats['mean'] < -0.1 or winrate_stats['mean'] < 0.35:
            severity = 'high'
        elif pnl_stats['mean'] < 0 or winrate_stats['mean'] < 0.45:
            severity = 'medium'
        else:
            severity = 'low'
        
        event = DriftEvent(
            timestamp=datetime.now().isoformat(),
            drift_type=drift_type,
            old_mean=pnl_stats['mean'] if pnl_drift else winrate_stats['mean'],
            new_mean=0,  # Sera calculé après reset
            change_pct=0,
            window_size=pnl_stats['count'],
            severity=severity
        )
        
        self.drift_history.append(event)
        
        # Limiter l'historique
        if len(self.drift_history) > self.max_history:
            self.drift_history = self.drift_history[-self.max_history:]
    
    def get_status(self) -> dict:
        """Retourne le statut du détecteur."""
        return {
            'enabled': self.enabled,
            'total_trades': self.total_trades,
            'trades_since_alert': self.trades_since_alert,
            'pnl_stats': self.pnl_detector.get_stats(),
            'winrate_stats': self.winrate_detector.get_stats(),
            'recent_drifts': len([d for d in self.drift_history 
                                 if d.timestamp > (datetime.now().isoformat()[:10])]),
            'last_check': self.last_check
        }
    
    def get_history(self, limit: int = 10) -> List[dict]:
        """Retourne l'historique des drifts."""
        return [d.to_dict() for d in self.drift_history[-limit:]]
    
    def reset(self) -> None:
        """Réinitialise les détecteurs."""
        self.pnl_detector.reset()
        self.winrate_detector.reset()
        self.trades_since_alert = 0
        logger.info("🔄 Drift detectors reset")
    
    def _save_state(self) -> None:
        """Sauvegarde l'état."""
        try:
            state = {
                'total_trades': self.total_trades,
                'trades_since_alert': self.trades_since_alert,
                'drift_history': [d.to_dict() for d in self.drift_history],
                'saved_at': datetime.now().isoformat()
            }
            with open(self.persistence_path, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"⚠️ Failed to save drift state: {e}")
    
    def _load_state(self) -> None:
        """Charge l'état précédent."""
        if not self.persistence_path.exists():
            return
        
        try:
            with open(self.persistence_path, 'r') as f:
                state = json.load(f)
            
            self.total_trades = state.get('total_trades', 0)
            self.trades_since_alert = state.get('trades_since_alert', 0)
            
            for d in state.get('drift_history', []):
                self.drift_history.append(DriftEvent(**d))
            
            logger.info(f"📂 Drift state loaded: {self.total_trades} trades, "
                       f"{len(self.drift_history)} events")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load drift state: {e}")


def get_drift_detector() -> MarketDriftDetector:
    """Retourne l'instance singleton du détecteur."""
    global _detector_instance
    
    if _detector_instance is None:
        _detector_instance = MarketDriftDetector()
    
    return _detector_instance


def reset_drift_detector() -> None:
    """Réinitialise l'instance singleton."""
    global _detector_instance
    _detector_instance = None

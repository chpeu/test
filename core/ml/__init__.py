"""
Core ML Module - Phase 2D & 3
=============================
Composants ML pour l'adaptation automatique du trading.

Modules:
- threshold_optimizer: Seuils dynamiques par contexte (Thompson Sampling)
- drift_detector: Détection de changement de comportement marché
- regime_classifier: Classification ML du régime (Phase 3)
- sltp_predictor: Prédiction SL/TP optimaux (Phase 3)
- online_learner: Apprentissage incrémental (Phase 3)
"""

from .threshold_optimizer import ContextualThresholdOptimizer, get_threshold_optimizer
from .drift_detector import MarketDriftDetector, get_drift_detector

__all__ = [
    'ContextualThresholdOptimizer',
    'get_threshold_optimizer',
    'MarketDriftDetector',
    'get_drift_detector',
]

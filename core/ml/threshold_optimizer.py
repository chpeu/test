"""
Contextual Threshold Optimizer - Phase 2D
==========================================
Optimise dynamiquement le seuil de confiance GB par contexte (régime, session, heure).
Utilise Thompson Sampling pour balance exploration/exploitation.

Usage:
    from core.ml import get_threshold_optimizer
    
    optimizer = get_threshold_optimizer()
    
    # Avant un trade: obtenir le seuil optimal
    threshold = optimizer.get_threshold(regime='VOLATILE', session='EUROPE', hour=14)
    
    # Après un trade: mettre à jour
    optimizer.update(regime='VOLATILE', session='EUROPE', hour=14, win=True, pnl=0.15)

Auteur: Cascade AI
Date: 11/12/2025
"""

import json
import logging
import numpy as np
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Singleton instance
_optimizer_instance: Optional['ContextualThresholdOptimizer'] = None


@dataclass
class ContextStats:
    """Statistiques pour un contexte donné."""
    alpha: float = 1.0  # Succès (prior Beta)
    beta: float = 1.0   # Échecs (prior Beta)
    total_trades: int = 0
    total_wins: int = 0
    total_pnl: float = 0.0
    last_update: Optional[str] = None
    
    @property
    def winrate(self) -> float:
        if self.total_trades == 0:
            return 0.5
        return self.total_wins / self.total_trades
    
    @property
    def mean_threshold(self) -> float:
        """Moyenne de la distribution Beta."""
        return self.alpha / (self.alpha + self.beta)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ContextStats':
        return cls(**data)


class ContextualThresholdOptimizer:
    """
    Optimiseur de seuil contextuel utilisant Thompson Sampling.
    
    Le seuil de confiance GB s'adapte selon:
    - Le régime de marché (CALME, NORMAL, VOLATILE)
    - La session de trading (ASIA, EUROPE, US, etc.)
    - L'heure (groupée par tranches de 4h)
    
    Thompson Sampling permet de:
    - Explorer de nouveaux seuils quand on a peu de données
    - Exploiter les seuils performants quand on a beaucoup de données
    - S'adapter automatiquement aux changements de marché
    """
    
    def __init__(
        self,
        min_threshold: float = 0.45,
        max_threshold: float = 0.70,
        default_threshold: float = 0.55,
        exploration_bonus: float = 0.05,
        persistence_path: Optional[str] = None
    ):
        """
        Initialiser l'optimiseur.
        
        Args:
            min_threshold: Seuil minimum (mode agressif)
            max_threshold: Seuil maximum (mode conservateur)
            default_threshold: Seuil par défaut quand pas de données
            exploration_bonus: Bonus d'exploration pour nouveaux contextes
            persistence_path: Chemin pour sauvegarder/charger l'état
        """
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.default_threshold = default_threshold
        self.exploration_bonus = exploration_bonus
        
        # Stats par contexte
        self._context_stats: Dict[str, ContextStats] = defaultdict(ContextStats)
        
        # Persistence
        self.persistence_path = Path(persistence_path) if persistence_path else \
            Path("data/ml/threshold_optimizer_state.json")
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Charger l'état précédent si existe
        self._load_state()
        
        # Métriques globales
        self.total_updates = getattr(self, 'total_updates', 0)
        self.enabled = True
        
        logger.info(f"✅ ContextualThresholdOptimizer initialisé "
                   f"(range: {min_threshold:.2f}-{max_threshold:.2f}, "
                   f"contexts: {len(self._context_stats)})")
    
    def _get_context_key(self, regime: str, session: str, hour: int) -> str:
        """Génère la clé de contexte."""
        hour_group = hour // 4  # Grouper par tranches de 4h (0-5)
        return f"{regime}_{session}_{hour_group}"
    
    def get_threshold(
        self,
        regime: str,
        session: str,
        hour: int,
        use_sampling: bool = True
    ) -> float:
        """
        Obtenir le seuil optimal pour un contexte donné.
        
        Args:
            regime: Régime de marché (CALME, NORMAL, VOLATILE)
            session: Session de trading (ASIA, EUROPE, US, etc.)
            hour: Heure UTC (0-23)
            use_sampling: Si True, utilise Thompson Sampling; sinon, moyenne
            
        Returns:
            Seuil de confiance optimal pour ce contexte
        """
        if not self.enabled:
            return self.default_threshold
        
        context_key = self._get_context_key(regime, session, hour)
        stats = self._context_stats[context_key]
        
        # Si très peu de données, retourner le défaut avec exploration
        if stats.total_trades < 5:
            # Légère exploration autour du défaut
            if use_sampling:
                noise = np.random.uniform(-self.exploration_bonus, self.exploration_bonus)
                threshold = self.default_threshold + noise
            else:
                threshold = self.default_threshold
        else:
            if use_sampling:
                # Thompson Sampling: échantillonner depuis Beta(alpha, beta)
                sample = np.random.beta(stats.alpha, stats.beta)
            else:
                # Utiliser la moyenne de la distribution
                sample = stats.mean_threshold
            
            # Mapper sur [min, max]
            # sample proche de 1 = beaucoup de wins = seuil bas (agressif)
            # sample proche de 0 = beaucoup de losses = seuil haut (conservateur)
            threshold = self.max_threshold - sample * (self.max_threshold - self.min_threshold)
        
        # Clamp dans les bornes
        threshold = max(self.min_threshold, min(self.max_threshold, threshold))
        
        logger.debug(f"📊 Threshold pour {context_key}: {threshold:.3f} "
                    f"(trades: {stats.total_trades}, WR: {stats.winrate:.1%})")
        
        return threshold
    
    def update(
        self,
        regime: str,
        session: str,
        hour: int,
        win: bool,
        pnl: float = 0.0
    ) -> None:
        """
        Mettre à jour les stats après un trade.
        
        Args:
            regime: Régime de marché
            session: Session de trading
            hour: Heure UTC
            win: True si trade gagnant
            pnl: PnL du trade (optionnel, pour stats avancées)
        """
        context_key = self._get_context_key(regime, session, hour)
        stats = self._context_stats[context_key]
        
        # Mettre à jour les compteurs
        stats.total_trades += 1
        if win:
            stats.total_wins += 1
            stats.alpha += 1  # Succès
        else:
            stats.beta += 1   # Échec
        
        stats.total_pnl += pnl
        stats.last_update = datetime.now().isoformat()
        
        self.total_updates += 1
        
        logger.info(f"📈 Threshold update [{context_key}]: "
                   f"{'WIN' if win else 'LOSS'} | "
                   f"Trades: {stats.total_trades} | "
                   f"WR: {stats.winrate:.1%} | "
                   f"New threshold: {self.get_threshold(regime, session, hour, use_sampling=False):.3f}")
        
        # Sauvegarder périodiquement
        if self.total_updates % 1 == 0:
            self._save_state()
    
    def get_all_thresholds(self) -> Dict[str, dict]:
        """Retourne tous les seuils par contexte."""
        result = {}
        for context_key, stats in self._context_stats.items():
            # 🔥 FIX 15/12: Le hour_group est toujours le DERNIER element apres split
            # car session peut contenir des underscores (ex: EUROPE_OPEN)
            parts = context_key.split('_')
            if len(parts) >= 3:
                try:
                    hour_group = int(parts[-1])  # Dernier element = hour_group
                    regime = parts[0]
                    session = '_'.join(parts[1:-1])  # Tout entre regime et hour_group
                    result[context_key] = {
                        'regime': regime,
                        'session': session,
                        'hour_group': hour_group,
                        'threshold': self.get_threshold(regime, session, hour_group * 4, use_sampling=False),
                        'trades': stats.total_trades,
                        'wins': stats.total_wins,
                        'winrate': stats.winrate,
                        'pnl': stats.total_pnl
                    }
                except (ValueError, IndexError) as e:
                    logger.warning(f"Invalid context_key format: {context_key} - {e}")
                    continue
        return result
    
    def get_recommendations(self, min_trades: int = 10) -> List[dict]:
        """
        Génère des recommandations basées sur les données.
        
        Args:
            min_trades: Minimum de trades pour faire une recommandation
            
        Returns:
            Liste de recommandations
        """
        recommendations = []
        
        for context_key, stats in self._context_stats.items():
            if stats.total_trades < min_trades:
                continue
            
            # 🔥 FIX 15/12: Parser correctement le context_key
            parts = context_key.split('_')
            try:
                hour_group = int(parts[-1])  # Dernier element = hour_group
                regime = parts[0]
                session = '_'.join(parts[1:-1])  # Tout entre regime et hour_group
                current_threshold = self.get_threshold(
                    regime, session, hour_group * 4, use_sampling=False
                )
            except (ValueError, IndexError) as e:
                logger.warning(f"Invalid context_key in recommendations: {context_key} - {e}")
                continue
            
            # Recommander d'augmenter le seuil si WR < 40%
            if stats.winrate < 0.40:
                recommendations.append({
                    'context': context_key,
                    'action': 'increase_threshold',
                    'current': current_threshold,
                    'suggested': min(current_threshold + 0.05, self.max_threshold),
                    'reason': f'WinRate {stats.winrate:.1%} < 40%',
                    'trades': stats.total_trades
                })
            # Recommander de baisser le seuil si WR > 60%
            elif stats.winrate > 0.60 and stats.total_trades >= 20:
                recommendations.append({
                    'context': context_key,
                    'action': 'decrease_threshold',
                    'current': current_threshold,
                    'suggested': max(current_threshold - 0.03, self.min_threshold),
                    'reason': f'WinRate {stats.winrate:.1%} > 60%',
                    'trades': stats.total_trades
                })
        
        return sorted(recommendations, key=lambda x: x['trades'], reverse=True)
    
    def reset_context(self, regime: str, session: str, hour: int) -> None:
        """Réinitialise les stats pour un contexte spécifique."""
        context_key = self._get_context_key(regime, session, hour)
        if context_key in self._context_stats:
            del self._context_stats[context_key]
            logger.info(f"🗑️ Context {context_key} reset")
    
    def reset_all(self) -> None:
        """Réinitialise toutes les stats."""
        self._context_stats.clear()
        self.total_updates = 0
        logger.info("🗑️ All contexts reset")
        self._save_state()
    
    def _save_state(self) -> None:
        """Sauvegarde l'état dans un fichier JSON."""
        try:
            state = {
                'total_updates': self.total_updates,
                'contexts': {k: v.to_dict() for k, v in self._context_stats.items()},
                'saved_at': datetime.now().isoformat()
            }
            with open(self.persistence_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            logger.debug(f"💾 State saved to {self.persistence_path}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save state: {e}")
    
    def _load_state(self) -> None:
        """Charge l'état depuis un fichier JSON."""
        if not self.persistence_path.exists():
            logger.info("📂 No previous state found, starting fresh")
            return
        
        try:
            with open(self.persistence_path, 'r') as f:
                state = json.load(f)
            
            self.total_updates = state.get('total_updates', 0)
            
            for context_key, stats_dict in state.get('contexts', {}).items():
                self._context_stats[context_key] = ContextStats.from_dict(stats_dict)
            
            logger.info(f"📂 State loaded: {len(self._context_stats)} contexts, "
                       f"{self.total_updates} total updates")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load state: {e}")
    
    def get_status(self) -> dict:
        """Retourne le statut de l'optimiseur."""
        return {
            'enabled': self.enabled,
            'min_threshold': self.min_threshold,
            'max_threshold': self.max_threshold,
            'default_threshold': self.default_threshold,
            'total_contexts': len(self._context_stats),
            'total_updates': self.total_updates,
            'contexts_with_data': sum(1 for s in self._context_stats.values() if s.total_trades > 0)
        }


def get_threshold_optimizer() -> ContextualThresholdOptimizer:
    """
    Retourne l'instance singleton de l'optimiseur.
    
    Usage:
        optimizer = get_threshold_optimizer()
        threshold = optimizer.get_threshold('VOLATILE', 'EUROPE', 14)
    """
    global _optimizer_instance

    try:
        from utils.config_persistence import get_config_value

        min_threshold = float(get_config_value('threshold_min', 0.45))
        max_threshold = float(get_config_value('threshold_max', 0.70))
        default_threshold = float(get_config_value('gb_min_confidence', 0.55))
        exploration_bonus = float(get_config_value('threshold_exploration_bonus', 0.05))
        enabled = bool(get_config_value('threshold_optimizer_enabled', False))

        if min_threshold > max_threshold:
            min_threshold, max_threshold = max_threshold, min_threshold

    except Exception:
        min_threshold = 0.45
        max_threshold = 0.70
        default_threshold = 0.55
        exploration_bonus = 0.05
        enabled = True

    if _optimizer_instance is None:
        _optimizer_instance = ContextualThresholdOptimizer(
            min_threshold=min_threshold,
            max_threshold=max_threshold,
            default_threshold=default_threshold,
            exploration_bonus=exploration_bonus
        )
    else:
        _optimizer_instance.min_threshold = min_threshold
        _optimizer_instance.max_threshold = max_threshold
        _optimizer_instance.default_threshold = default_threshold
        _optimizer_instance.exploration_bonus = exploration_bonus

    _optimizer_instance.enabled = enabled

    return _optimizer_instance


def reset_threshold_optimizer() -> None:
    """Réinitialise l'instance singleton."""
    global _optimizer_instance
    _optimizer_instance = None

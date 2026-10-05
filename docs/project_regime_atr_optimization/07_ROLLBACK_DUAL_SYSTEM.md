# 🛡️ ROLLBACK DUAL SYSTEM - Specification
## Hard-Stop + Progressive Rollback

> **Version:** 1.0.0 | **Date:** 14/12/2025 | **Statut:** 📋 SPÉCIFIÉ
> 
> **Décision:** Implémenter LES DEUX approches (Hard-Stop ET Progressive)

---

## 🎯 OBJECTIF

Protéger le capital tout en permettant une optimisation continue:

1. **Hard-Stop**: Protection immédiate contre les pertes catastrophiques
2. **Progressive**: Ajustement graduel pour optimiser les performances

---

## 📐 ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                     ROLLBACK DUAL SYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              LAYER 1: HARD-STOP (Urgence)                │   │
│  │                                                          │   │
│  │  • Drawdown session > 5% → ROLLBACK IMMÉDIAT            │   │
│  │  • Losing streak ≥ 5 → ROLLBACK IMMÉDIAT                │   │
│  │  • Profit Factor < 0.5 (20 trades) → ROLLBACK IMMÉDIAT  │   │
│  │  • Win Rate < 25% (30 trades) → ROLLBACK IMMÉDIAT       │   │
│  │                                                          │   │
│  │  Action: Reset ALL parameters to BASELINE immediately   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           LAYER 2: PROGRESSIVE (Optimisation)            │   │
│  │                                                          │   │
│  │  • Fenêtres: Short (20) / Medium (50) / Long (100)      │   │
│  │  • Hystérésis: -15% pour dégrader, +10% pour améliorer  │   │
│  │  • Cooldown: 30 trades OU 24h entre ajustements         │   │
│  │  • Niveaux: -2, -1, 0, +1, +2                           │   │
│  │                                                          │   │
│  │  Action: Ajustement graduel des paramètres              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │             LAYER 3: REGIME-AWARE (Ciblé)                │   │
│  │                                                          │   │
│  │  • Évaluation séparée par régime                        │   │
│  │  • Rollback ciblé (ex: VOLATILE only)                   │   │
│  │  • Min 20 trades par régime pour évaluation             │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔴 LAYER 1: HARD-STOP

### Critères de déclenchement

| Critère | Seuil | Fenêtre | Justification |
|---------|-------|---------|---------------|
| **Drawdown session** | > 5% | Session en cours | Protection capital quotidien |
| **Losing streak** | ≥ 5 trades | Consécutifs | Évite spirale de pertes |
| **Profit Factor** | < 0.5 | 20 derniers trades | Ratio gains/pertes critique |
| **Win Rate** | < 25% | 30 derniers trades | Performance trop faible |

### Action déclenchée

```python
def trigger_hard_stop(reason: str) -> dict:
    """
    Rollback immédiat vers baseline.
    
    Actions:
    1. Reset TOUS les paramètres optimisés vers valeurs par défaut
    2. Reset threshold optimizer contexts
    3. Log l'événement
    4. Notifier via WebSocket
    5. Cooldown étendu avant nouvelle optimisation
    """
    return {
        'action': 'hard_rollback',
        'reason': reason,
        'params': get_baseline_params(),
        'cooldown_trades': 50,  # Plus long que progressif
        'cooldown_hours': 48
    }
```

### Paramètres baseline

```python
BASELINE_PARAMS = {
    # Threshold
    'gb_min_confidence': 0.55,
    
    # SL/TP par régime
    'calme': {'atr_mult_sl': 0.8, 'atr_mult_tp': 1.8},
    'normal': {'atr_mult_sl': 1.0, 'atr_mult_tp': 2.0},
    'volatile': {'atr_mult_sl': 1.2, 'atr_mult_tp': 2.5},
    
    # BE/Trailing
    'break_even_atr_mult': 0.5,
    'trailing_trigger_atr_mult': 1.0,
}
```

---

## 📊 LAYER 2: PROGRESSIVE ROLLBACK

### Fenêtres d'évaluation

| Fenêtre | Trades | Usage |
|---------|--------|-------|
| **Short** | 20 | Tendance récente |
| **Medium** | 50 | Tendance court terme |
| **Long** | 100 | Baseline de référence |

### Niveaux d'ajustement

```
Level -2: Very Conservative (après 2 dégradations)
Level -1: Conservative (après 1 dégradation)
Level  0: Baseline (défaut)
Level +1: Optimized (après amélioration, si était dégradé)
Level +2: Aggressive (après 2 améliorations, si était dégradé)
```

### Hystérésis

```python
# Pour DÉGRADER (passer à niveau inférieur)
# Performance doit être significativement pire
DEGRADE_THRESHOLD = -0.15  # -15% vs baseline

# Pour AMÉLIORER (revenir vers baseline)
# Performance doit être significativement meilleure
IMPROVE_THRESHOLD = +0.10  # +10% vs baseline
```

**Pourquoi l'asymétrie?**
- Dégrader = perdre de l'argent → seuil plus strict
- Améliorer = déjà dégradé, prudence

### Cooldown

```python
# Entre chaque ajustement
MIN_TRADES_BETWEEN_CHANGES = 30
MIN_HOURS_BETWEEN_CHANGES = 24

# Logique
def can_adjust() -> bool:
    trades_elapsed = current_trade_id - last_adjustment_trade_id
    hours_elapsed = (now - last_adjustment_time).total_seconds() / 3600
    
    return (
        trades_elapsed >= MIN_TRADES_BETWEEN_CHANGES
        and hours_elapsed >= MIN_HOURS_BETWEEN_CHANGES
    )
```

### Ajustements par niveau

```python
LEVEL_ADJUSTMENTS = {
    -2: {  # Very Conservative
        'threshold_delta': +0.10,      # 0.55 → 0.65
        'sl_mult_factor': 0.8,         # Tighter SL
        'tp_mult_factor': 0.7,         # Shorter TP
        'trailing_mult_factor': 0.8,   # Earlier trailing
    },
    -1: {  # Conservative
        'threshold_delta': +0.05,      # 0.55 → 0.60
        'sl_mult_factor': 0.9,
        'tp_mult_factor': 0.85,
        'trailing_mult_factor': 0.9,
    },
    0: {  # Baseline
        'threshold_delta': 0,
        'sl_mult_factor': 1.0,
        'tp_mult_factor': 1.0,
        'trailing_mult_factor': 1.0,
    },
    +1: {  # Optimized (only if was degraded)
        'threshold_delta': -0.03,
        'sl_mult_factor': 1.05,
        'tp_mult_factor': 1.1,
        'trailing_mult_factor': 1.05,
    },
    +2: {  # Aggressive (only if was degraded)
        'threshold_delta': -0.05,
        'sl_mult_factor': 1.1,
        'tp_mult_factor': 1.2,
        'trailing_mult_factor': 1.1,
    },
}
```

---

## 🎯 LAYER 3: REGIME-AWARE

### Évaluation séparée

```python
def evaluate_by_regime(self) -> dict[str, RollbackAction]:
    """
    Évalue chaque régime indépendamment.
    Permet rollback ciblé sans affecter les autres régimes.
    """
    actions = {}
    
    for regime in ['CALME', 'NORMAL', 'VOLATILE', 'CHOPPY']:
        regime_trades = self.get_trades_for_regime(regime)
        
        # Besoin de 20+ trades pour évaluer
        if len(regime_trades) < 20:
            actions[regime] = RollbackAction(
                action='hold',
                reason='insufficient_data',
                trade_count=len(regime_trades)
            )
            continue
        
        # Calculer métriques pour ce régime
        metrics = self.calculate_metrics(regime_trades)
        
        # Évaluer avec la même logique
        actions[regime] = self.evaluate_single(metrics)
    
    return actions
```

### Exemple de rollback ciblé

```
Situation:
- CALME: +5% vs baseline → HOLD
- NORMAL: -18% vs baseline → DEGRADE
- VOLATILE: +8% vs baseline → HOLD

Action:
- Rollback UNIQUEMENT les params NORMAL
- CALME et VOLATILE continuent normalement
```

---

## 📊 MÉTRIQUES D'ÉVALUATION

### Score composite

```python
def calculate_composite_score(metrics: dict) -> float:
    """
    Score pondéré pour évaluation.
    """
    weights = {
        'profit_factor': 0.30,
        'expectancy': 0.25,
        'max_drawdown': 0.20,  # Négatif = pire
        'trade_count': 0.15,
        'winrate': 0.10,
    }
    
    # Normaliser chaque métrique
    normalized = {
        'profit_factor': min(metrics['profit_factor'] / 2.0, 1.0),
        'expectancy': min(max(metrics['expectancy'] + 0.5, 0) / 1.0, 1.0),
        'max_drawdown': 1 - min(abs(metrics['max_drawdown']) / 10.0, 1.0),
        'trade_count': min(metrics['trade_count'] / 50, 1.0),
        'winrate': metrics['winrate'] / 100,
    }
    
    return sum(normalized[k] * weights[k] for k in weights)
```

### Formules

| Métrique | Formule |
|----------|---------|
| **Profit Factor** | Sum(Gains) / Sum(Losses) |
| **Expectancy** | (WR × Avg_Win) - ((1-WR) × Avg_Loss) |
| **Max Drawdown** | Max(Peak - Valley) / Peak |
| **Win Rate** | Wins / Total × 100 |

---

## 🔧 CONFIGURATION

### config.py

```python
ROLLBACK_CONFIG = {
    # === Hard-Stop ===
    'rollback_hard_stop_enabled': True,
    'rollback_hard_stop_drawdown_pct': 5.0,
    'rollback_hard_stop_losing_streak': 5,
    'rollback_hard_stop_profit_factor_min': 0.5,
    'rollback_hard_stop_profit_factor_window': 20,
    'rollback_hard_stop_winrate_min': 25,
    'rollback_hard_stop_winrate_window': 30,
    
    # === Progressive ===
    'rollback_progressive_enabled': True,
    'rollback_short_window': 20,
    'rollback_medium_window': 50,
    'rollback_long_window': 100,
    'rollback_degrade_threshold': -0.15,
    'rollback_improve_threshold': 0.10,
    'rollback_min_trades_between_changes': 30,
    'rollback_min_hours_between_changes': 24,
    
    # === Regime-Aware ===
    'rollback_regime_aware_enabled': True,
    'rollback_min_trades_per_regime': 20,
    
    # === Cooldown post Hard-Stop ===
    'rollback_hard_stop_cooldown_trades': 50,
    'rollback_hard_stop_cooldown_hours': 48,
}
```

### config_overrides.json

```json
{
  "rollback_hard_stop_enabled": true,
  "rollback_hard_stop_drawdown_pct": 5.0,
  "rollback_hard_stop_losing_streak": 5,
  "rollback_progressive_enabled": true,
  "rollback_degrade_threshold": -0.15,
  "rollback_improve_threshold": 0.10,
  "rollback_regime_aware_enabled": true
}
```

---

## 📁 IMPLÉMENTATION

### Fichier principal: `core/ml/rollback_manager.py`

```python
"""
Rollback Manager - Dual System (Hard-Stop + Progressive)
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class RollbackType(Enum):
    HARD_STOP = "hard_stop"
    PROGRESSIVE = "progressive"
    NONE = "none"


@dataclass
class RollbackAction:
    type: RollbackType
    regime: Optional[str]  # None = all regimes
    reason: str
    old_level: int
    new_level: int
    params_delta: Dict
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class RollbackManager:
    """
    Manages the dual rollback system.
    """
    
    def __init__(self, config: dict):
        self.config = config
        
        # State
        self.current_levels: Dict[str, int] = {
            'CALME': 0,
            'NORMAL': 0,
            'VOLATILE': 0,
            'CHOPPY': 0,
            'GLOBAL': 0,  # For non-regime-aware mode
        }
        
        self.last_adjustment_trade_id: Optional[int] = None
        self.last_adjustment_time: Optional[datetime] = None
        self.history: List[RollbackAction] = []
        
        # Metrics cache
        self._metrics_cache: Dict = {}
        self._cache_valid_until: Optional[datetime] = None
    
    # === HARD-STOP LAYER ===
    
    def check_hard_stop(self, metrics: dict) -> Optional[RollbackAction]:
        """
        Check if any hard-stop criteria is met.
        Returns RollbackAction if triggered, None otherwise.
        """
        if not self.config.get('rollback_hard_stop_enabled', True):
            return None
        
        # 1. Session drawdown
        session_dd = metrics.get('session_drawdown_pct', 0)
        if session_dd > self.config.get('rollback_hard_stop_drawdown_pct', 5.0):
            return self._create_hard_stop_action(
                f'Session drawdown {session_dd:.1f}% > {self.config["rollback_hard_stop_drawdown_pct"]}%'
            )
        
        # 2. Losing streak
        losing_streak = metrics.get('losing_streak', 0)
        if losing_streak >= self.config.get('rollback_hard_stop_losing_streak', 5):
            return self._create_hard_stop_action(
                f'Losing streak {losing_streak} >= {self.config["rollback_hard_stop_losing_streak"]}'
            )
        
        # 3. Profit factor
        pf = metrics.get('profit_factor_recent', 1.0)
        if pf < self.config.get('rollback_hard_stop_profit_factor_min', 0.5):
            return self._create_hard_stop_action(
                f'Profit factor {pf:.2f} < {self.config["rollback_hard_stop_profit_factor_min"]}'
            )
        
        # 4. Win rate
        wr = metrics.get('winrate_recent', 50)
        if wr < self.config.get('rollback_hard_stop_winrate_min', 25):
            return self._create_hard_stop_action(
                f'Win rate {wr:.1f}% < {self.config["rollback_hard_stop_winrate_min"]}%'
            )
        
        return None
    
    def _create_hard_stop_action(self, reason: str) -> RollbackAction:
        """Create a hard-stop rollback action."""
        # Reset all levels to 0
        old_levels = self.current_levels.copy()
        for key in self.current_levels:
            self.current_levels[key] = 0
        
        action = RollbackAction(
            type=RollbackType.HARD_STOP,
            regime=None,  # All regimes
            reason=reason,
            old_level=max(old_levels.values()),
            new_level=0,
            params_delta=self._get_baseline_params(),
        )
        
        self.history.append(action)
        self._set_cooldown(
            self.config.get('rollback_hard_stop_cooldown_trades', 50),
            self.config.get('rollback_hard_stop_cooldown_hours', 48)
        )
        
        logger.warning(f"🛑 HARD-STOP ROLLBACK: {reason}")
        return action
    
    # === PROGRESSIVE LAYER ===
    
    def evaluate_progressive(
        self, 
        metrics: dict, 
        current_trade_id: int
    ) -> Optional[RollbackAction]:
        """
        Evaluate if progressive rollback is needed.
        """
        if not self.config.get('rollback_progressive_enabled', True):
            return None
        
        # Check cooldown
        if not self._cooldown_elapsed(current_trade_id):
            return None
        
        # Calculate performance delta vs baseline
        short_perf = metrics.get('short_performance', 0)
        baseline_perf = metrics.get('long_performance', 0)
        
        if baseline_perf == 0:
            return None
        
        delta_pct = (short_perf - baseline_perf) / abs(baseline_perf) if baseline_perf else 0
        
        # Current level
        current_level = self.current_levels.get('GLOBAL', 0)
        
        # Degrade?
        degrade_threshold = self.config.get('rollback_degrade_threshold', -0.15)
        if delta_pct < degrade_threshold:
            new_level = max(current_level - 1, -2)
            if new_level != current_level:
                return self._create_progressive_action(
                    regime=None,
                    old_level=current_level,
                    new_level=new_level,
                    reason=f'Performance {delta_pct*100:.1f}% vs baseline',
                    current_trade_id=current_trade_id
                )
        
        # Improve? (only if degraded)
        improve_threshold = self.config.get('rollback_improve_threshold', 0.10)
        if delta_pct > improve_threshold and current_level < 0:
            new_level = current_level + 1
            return self._create_progressive_action(
                regime=None,
                old_level=current_level,
                new_level=new_level,
                reason=f'Performance +{delta_pct*100:.1f}% vs baseline',
                current_trade_id=current_trade_id
            )
        
        return None
    
    # === REGIME-AWARE LAYER ===
    
    def evaluate_by_regime(
        self, 
        metrics_by_regime: Dict[str, dict],
        current_trade_id: int
    ) -> Dict[str, Optional[RollbackAction]]:
        """
        Evaluate each regime separately.
        """
        if not self.config.get('rollback_regime_aware_enabled', True):
            return {}
        
        actions = {}
        min_trades = self.config.get('rollback_min_trades_per_regime', 20)
        
        for regime, metrics in metrics_by_regime.items():
            trade_count = metrics.get('trade_count', 0)
            
            if trade_count < min_trades:
                actions[regime] = None
                continue
            
            # Use same evaluation logic but per-regime
            short_perf = metrics.get('short_performance', 0)
            baseline_perf = metrics.get('long_performance', 0)
            
            if baseline_perf == 0:
                actions[regime] = None
                continue
            
            delta_pct = (short_perf - baseline_perf) / abs(baseline_perf)
            current_level = self.current_levels.get(regime, 0)
            
            # Degrade?
            if delta_pct < self.config.get('rollback_degrade_threshold', -0.15):
                new_level = max(current_level - 1, -2)
                if new_level != current_level:
                    actions[regime] = self._create_progressive_action(
                        regime=regime,
                        old_level=current_level,
                        new_level=new_level,
                        reason=f'{regime}: {delta_pct*100:.1f}% vs baseline',
                        current_trade_id=current_trade_id
                    )
                    continue
            
            # Improve?
            if delta_pct > self.config.get('rollback_improve_threshold', 0.10) and current_level < 0:
                new_level = current_level + 1
                actions[regime] = self._create_progressive_action(
                    regime=regime,
                    old_level=current_level,
                    new_level=new_level,
                    reason=f'{regime}: +{delta_pct*100:.1f}% vs baseline',
                    current_trade_id=current_trade_id
                )
                continue
            
            actions[regime] = None
        
        return actions
    
    # === HELPERS ===
    
    def _create_progressive_action(
        self,
        regime: Optional[str],
        old_level: int,
        new_level: int,
        reason: str,
        current_trade_id: int
    ) -> RollbackAction:
        """Create a progressive rollback action."""
        if regime:
            self.current_levels[regime] = new_level
        else:
            self.current_levels['GLOBAL'] = new_level
        
        action = RollbackAction(
            type=RollbackType.PROGRESSIVE,
            regime=regime,
            reason=reason,
            old_level=old_level,
            new_level=new_level,
            params_delta=self._get_params_for_level(new_level),
        )
        
        self.history.append(action)
        self._set_cooldown(
            self.config.get('rollback_min_trades_between_changes', 30),
            self.config.get('rollback_min_hours_between_changes', 24),
            current_trade_id
        )
        
        direction = "⬇️ DEGRADE" if new_level < old_level else "⬆️ IMPROVE"
        logger.info(f"{direction} ROLLBACK [{regime or 'GLOBAL'}]: {reason}")
        return action
    
    def _cooldown_elapsed(self, current_trade_id: int) -> bool:
        """Check if cooldown period has elapsed."""
        if self.last_adjustment_trade_id is None:
            return True
        
        trades_elapsed = current_trade_id - self.last_adjustment_trade_id
        min_trades = self.config.get('rollback_min_trades_between_changes', 30)
        
        if trades_elapsed < min_trades:
            return False
        
        if self.last_adjustment_time:
            hours_elapsed = (datetime.utcnow() - self.last_adjustment_time).total_seconds() / 3600
            min_hours = self.config.get('rollback_min_hours_between_changes', 24)
            if hours_elapsed < min_hours:
                return False
        
        return True
    
    def _set_cooldown(
        self, 
        trades: int, 
        hours: int, 
        current_trade_id: int = None
    ):
        """Set cooldown period."""
        self.last_adjustment_trade_id = current_trade_id
        self.last_adjustment_time = datetime.utcnow()
    
    def _get_baseline_params(self) -> dict:
        """Get baseline parameters."""
        return {
            'gb_min_confidence': 0.55,
            'threshold_delta': 0,
            'sl_mult_factor': 1.0,
            'tp_mult_factor': 1.0,
            'trailing_mult_factor': 1.0,
        }
    
    def _get_params_for_level(self, level: int) -> dict:
        """Get parameters adjustment for a given level."""
        adjustments = {
            -2: {'threshold_delta': +0.10, 'sl_mult_factor': 0.8, 'tp_mult_factor': 0.7},
            -1: {'threshold_delta': +0.05, 'sl_mult_factor': 0.9, 'tp_mult_factor': 0.85},
            0: {'threshold_delta': 0, 'sl_mult_factor': 1.0, 'tp_mult_factor': 1.0},
            +1: {'threshold_delta': -0.03, 'sl_mult_factor': 1.05, 'tp_mult_factor': 1.1},
            +2: {'threshold_delta': -0.05, 'sl_mult_factor': 1.1, 'tp_mult_factor': 1.2},
        }
        return adjustments.get(level, adjustments[0])
    
    def get_status(self) -> dict:
        """Get current rollback status for monitoring."""
        return {
            'current_levels': self.current_levels.copy(),
            'last_adjustment_trade_id': self.last_adjustment_trade_id,
            'last_adjustment_time': self.last_adjustment_time.isoformat() if self.last_adjustment_time else None,
            'history_count': len(self.history),
            'recent_history': [
                {
                    'type': h.type.value,
                    'regime': h.regime,
                    'reason': h.reason,
                    'old_level': h.old_level,
                    'new_level': h.new_level,
                    'timestamp': h.timestamp.isoformat(),
                }
                for h in self.history[-10:]  # Last 10
            ]
        }


# Singleton
_rollback_manager: Optional[RollbackManager] = None


def get_rollback_manager() -> RollbackManager:
    """Get or create the rollback manager singleton."""
    global _rollback_manager
    if _rollback_manager is None:
        from config import TRADING_CONFIG
        config = TRADING_CONFIG.get('rollback', {})
        _rollback_manager = RollbackManager(config)
    return _rollback_manager
```

---

## 🔌 INTÉGRATION

### Dans position_manager.py (après chaque trade)

```python
# After trade closed
from core.ml.rollback_manager import get_rollback_manager

def _on_trade_closed(self, trade_data: dict):
    # ... existing logic ...
    
    # Check rollback
    rollback_manager = get_rollback_manager()
    
    # Calculate current metrics
    metrics = self._calculate_rollback_metrics()
    
    # 1. Check hard-stop first
    hard_stop_action = rollback_manager.check_hard_stop(metrics)
    if hard_stop_action:
        self._apply_rollback(hard_stop_action)
        self._notify_rollback(hard_stop_action)
        return
    
    # 2. Check progressive
    progressive_action = rollback_manager.evaluate_progressive(
        metrics, 
        trade_data['id']
    )
    if progressive_action:
        self._apply_rollback(progressive_action)
        self._notify_rollback(progressive_action)
```

### WebSocket notification

```python
async def _notify_rollback(self, action: RollbackAction):
    """Notify frontend of rollback via WebSocket."""
    await ws_manager.broadcast({
        'type': 'ml_rollback_triggered',
        'data': {
            'rollback_type': action.type.value,
            'regime': action.regime,
            'reason': action.reason,
            'old_level': action.old_level,
            'new_level': action.new_level,
            'params_delta': action.params_delta,
            'timestamp': action.timestamp.isoformat(),
        }
    })
```

---

## ✅ CHECKLIST

- [ ] Créer `core/ml/rollback_manager.py`
- [ ] Ajouter ROLLBACK_CONFIG dans `config.py`
- [ ] Intégrer dans `position_manager.py`
- [ ] Ajouter WebSocket events dans `main.py`
- [ ] Créer endpoint `/api/ml/monitor/rollback-status`
- [ ] Créer `RollbackStatusCard.svelte`
- [ ] Tests unitaires
- [ ] Documentation utilisateur

---

**Ce document définit le système de rollback dual. Implémentation après validation de l'architecture.**

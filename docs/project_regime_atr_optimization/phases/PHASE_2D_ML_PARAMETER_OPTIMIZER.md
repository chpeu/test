# 🎛️ PHASE 2D: ML PARAMETER OPTIMIZER
## Optimisation ML des Paramètres par Régime

> **Prérequis:** 100+ trades avec What-If data
> **Durée:** 10h
> **Objectif:** Trouver les params optimaux (SL, TP, Score, etc.) pour chaque régime

---

## 🎯 OBJECTIF

**Problème actuel:**
Les params par régime sont définis MANUELLEMENT:
```python
VOLATILE = {
    "atr_mult_sl": 1.5,      # Pourquoi 1.5? 
    "atr_mult_tp": 2.5,      # Pourquoi pas 2.8?
    "min_score_required": 7.5,
}
```

**Solution:**
Le ML analyse l'historique et trouve les params OPTIMAUX:
```python
VOLATILE_OPTIMIZED = {
    "atr_mult_sl": 1.73,     # ML a trouvé que 1.73 maximise le PF
    "atr_mult_tp": 2.91,     # ML a trouvé que 2.91 est optimal
    "min_score_required": 7.2,
}
```

---

## 📊 LISTE EXHAUSTIVE DES PARAMÈTRES À OPTIMISER

### Tier 1: Priorité HAUTE (Impact direct sur PnL)

| Paramètre | Type | Plage d'optimisation | Impact attendu |
|-----------|------|---------------------|----------------|
| `atr_mult_sl` | float | [0.6, 2.5] | 🔴 Très fort |
| `atr_mult_tp` | float | [1.5, 5.0] | 🔴 Très fort |
| `min_score_required` | float | [5.0, 10.0] | 🔴 Très fort |
| `break_even_atr_mult` | float | [0.3, 1.5] | 🟠 Fort |
| `trailing_trigger_atr_mult` | float | [0.8, 2.5] | 🟠 Fort |
| `trailing_distance_atr_mult` | float | [0.2, 1.0] | 🟠 Fort |
| `partial_tp_percent` | float | [30, 80] | 🟠 Fort |

### Tier 2: Priorité MOYENNE (Filtrage et timing)

| Paramètre | Type | Plage d'optimisation | Impact attendu |
|-----------|------|---------------------|----------------|
| `snr_threshold` | float | [0.05, 0.30] | 🟡 Moyen |
| `breakout_threshold` | float | [0.10, 0.40] | 🟡 Moyen |
| `min_conditions` | int | [3, 8] | 🟡 Moyen |
| `di_gap_min` | float | [3.0, 10.0] | 🟡 Moyen |
| `di_gap_adx_threshold` | float | [15, 30] | 🟡 Moyen |
| `cooldown_seconds` | int | [30, 180] | 🟡 Moyen |
| `cooldown_same_symbol` | int | [60, 300] | 🟡 Moyen |
| `stagnation_timeout` | int | [180, 900] | 🟡 Moyen |
| `stagnation_min_pnl` | float | [0.01, 0.08] | 🟡 Moyen |
| `stagnation_max_loss` | float | [-0.20, -0.05] | 🟡 Moyen |

### Tier 3: Priorité BASSE (Ajustements fins)

| Paramètre | Type | Plage d'optimisation | Impact attendu |
|-----------|------|---------------------|----------------|
| `min_score_adx_high` | float | [5.0, 8.0] | 🟢 Faible |
| `min_score_adx_low` | float | [5.0, 8.0] | 🟢 Faible |
| `dynamic_tolerance_adx_high` | float | [25, 40] | 🟢 Faible |
| `dynamic_tolerance_adx_low` | float | [20, 35] | 🟢 Faible |
| `wick_ratio_max` | float | [2.0, 6.0] | 🟢 Faible |
| `rsi_final_long_max` | float | [65, 80] | 🟢 Faible |
| `rsi_final_short_min` | float | [20, 35] | 🟢 Faible |
| `momentum_lookback` | int | [2, 8] | 🟢 Faible |
| `whipsaw_threshold_pct` | float | [0.05, 0.25] | 🟢 Faible |

### Tier 4: Patterns (Activation/Désactivation)

| Pattern | Type | Optimiser si | Hypothèse |
|---------|------|--------------|-----------|
| `use_breakout` | bool | VOLATILE vs CALME | ON en VOLATILE, OFF en CALME |
| `use_snr` | bool | Toujours ON? | Vérifier par régime |
| `use_divergence` | bool | CHOPPY? | Peut-être OFF en CHOPPY |
| `use_engulfing` | bool | CHOPPY? | Faux signaux en CHOPPY |
| `use_doji` | bool | VOLATILE? | OFF en VOLATILE (indécision) |
| `use_marubozu` | bool | CALME? | Moins pertinent en CALME |
| `use_anti_whipsaw` | bool | CHOPPY | ON en CHOPPY uniquement |
| `use_retest_confirmation` | bool | CALME | ON pour confirmer signaux faibles |

---

## 🧮 APPROCHE: Feature Importance + Grid Search

### Étape 1: Calculer l'importance des features par régime

```python
from sklearn.ensemble import RandomForestRegressor
import pandas as pd
import numpy as np

class FeatureImportanceAnalyzer:
    """
    Calcule l'importance de chaque paramètre pour le PnL par régime.
    """
    
    def analyze(self, regime: str) -> Dict[str, float]:
        """
        Retourne l'importance de chaque param pour un régime.
        """
        # Récupérer tous les trades du régime avec leurs params
        trades_df = self._get_trades_with_params(regime)
        
        # Features = tous les params utilisés
        feature_cols = [
            'param_atr_mult_sl', 'param_atr_mult_tp',
            'param_min_score', 'param_snr_threshold',
            'param_breakout_threshold', 'param_cooldown',
            'param_stagnation_timeout', 'param_di_gap_min',
            # ... autres params loggés
        ]
        
        X = trades_df[feature_cols].fillna(0)
        y = trades_df['pnl_percent']
        
        # Random Forest pour importance
        rf = RandomForestRegressor(n_estimators=100, random_state=42)
        rf.fit(X, y)
        
        importance = dict(zip(feature_cols, rf.feature_importances_))
        
        # Trier par importance décroissante
        sorted_importance = dict(sorted(
            importance.items(), 
            key=lambda x: x[1], 
            reverse=True
        ))
        
        return sorted_importance
    
    def get_top_params_to_optimize(self, regime: str, top_n: int = 10):
        """
        Retourne les N params les plus impactants à optimiser.
        """
        importance = self.analyze(regime)
        return list(importance.keys())[:top_n]
```

### Étape 2: Grid Search sur les top params

```python
class RegimeGridSearchOptimizer:
    """
    Grid Search adaptatif par régime.
    """
    
    def optimize(self, regime: str, top_params: List[str]) -> Dict:
        """
        Optimise les top params pour un régime.
        """
        # Définir la grille pour chaque param
        param_grids = {
            'param_atr_mult_sl': np.arange(0.8, 2.2, 0.2),
            'param_atr_mult_tp': np.arange(1.5, 4.0, 0.3),
            'param_min_score': np.arange(6.0, 9.5, 0.5),
            'param_snr_threshold': np.arange(0.08, 0.25, 0.03),
            'param_breakout_threshold': np.arange(0.15, 0.35, 0.05),
            'param_cooldown': [30, 60, 90, 120, 180],
            'param_stagnation_timeout': [180, 300, 450, 600, 900],
            # ... etc
        }
        
        # Filtrer sur les top params seulement
        search_grid = {k: v for k, v in param_grids.items() if k in top_params}
        
        # Grid search (ou Bayesian si trop de combinaisons)
        best_params, best_pf = self._run_grid_search(regime, search_grid)
        
        return {
            'regime': regime,
            'optimized_params': best_params,
            'expected_pf': best_pf
        }
```

---

## ⚠️ PRÉREQUIS: Logging des Params Utilisés

### Problème Actuel
Pour optimiser les paramètres, on doit savoir QUELS PARAMS ont été utilisés pour chaque trade.

Actuellement loggé dans `trade_atr_metrics`:
```
✅ param_atr_mult_sl, param_atr_mult_tp
✅ param_trailing_trigger_mult, param_trailing_distance_mult
✅ param_be_atr_mult
✅ param_stagnation_timeout, param_stagnation_min_pnl
```

**À AJOUTER pour Phase 2D étendue:**
```sql
-- Nouveaux params à logger (Phase 1A étendue)
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_min_score_used FLOAT;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_snr_threshold_used FLOAT;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_breakout_threshold_used FLOAT;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_cooldown_used INT;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_di_gap_min_used FLOAT;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_min_conditions_used INT;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_partial_tp_pct_used FLOAT;

-- Patterns actifs au moment du trade
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS patterns_enabled_mask INT; -- Bitmask
-- Bit 0: use_breakout, Bit 1: use_snr, Bit 2: use_divergence, etc.
```

### Bitmask Patterns (économise des colonnes)

```python
PATTERN_BITS = {
    'use_breakout': 1 << 0,       # 1
    'use_snr': 1 << 1,            # 2
    'use_divergence': 1 << 2,     # 4
    'use_engulfing': 1 << 3,      # 8
    'use_hammer': 1 << 4,         # 16
    'use_doji': 1 << 5,           # 32
    'use_marubozu': 1 << 6,       # 64
    'use_anti_whipsaw': 1 << 7,   # 128
    'use_retest': 1 << 8,         # 256
    'use_momentum': 1 << 9,       # 512
}

def encode_patterns(config: Dict) -> int:
    """Encode les patterns actifs en un entier."""
    mask = 0
    for pattern, bit in PATTERN_BITS.items():
        if config.get(pattern, False):
            mask |= bit
    return mask

def decode_patterns(mask: int) -> Dict[str, bool]:
    """Décode le bitmask en dict de patterns."""
    return {
        pattern: bool(mask & bit)
        for pattern, bit in PATTERN_BITS.items()
    }
```

---

## 📊 DONNÉES UTILISÉES (ÉTENDUES)

### Input: What-If Existants + Params Loggés

```sql
SELECT 
    market_volatility_state as regime,
    session_market,
    
    -- Params SL/TP (existants)
    param_atr_mult_sl,
    param_atr_mult_tp,
    -- What-If: que se serait-il passé avec d'autres valeurs?
    pnl_if_wider_sl,      -- SL × 1.5
    pnl_if_tighter_sl,    -- SL × 0.75
    pnl_if_wider_trailing,
    pnl_if_tighter_trailing,
    -- Efficacité
    sl_efficiency,
    tp_efficiency,
    trailing_capture_pct,
    -- Résultat réel
    t.pnl_percent
FROM trade_atr_metrics tam
JOIN trades t ON t.id = tam.trade_id
WHERE market_volatility_state IS NOT NULL
```

### Métriques d'Optimisation

| Métrique | Formule | Objectif |
|----------|---------|----------|
| Profit Factor | Σ gains / Σ pertes | Maximiser |
| Sharpe Ratio | mean(pnl) / std(pnl) | Maximiser |
| Win Rate | wins / total | > 50% |
| Max Drawdown | max(peak - trough) | Minimiser |
| Avg Trade | mean(pnl) | Maximiser |

---

## 🧠 ALGORITHME D'OPTIMISATION

### Approche 1: Grid Search + What-If Interpolation

```python
class MLParameterOptimizer:
    """
    Optimise les params par régime via Grid Search intelligent.
    """
    
    PARAM_RANGES = {
        'atr_mult_sl': (0.6, 2.0, 0.1),      # min, max, step
        'atr_mult_tp': (1.5, 4.0, 0.1),
        'min_score_required': (6.0, 9.0, 0.5),
        'be_atr_mult': (0.5, 1.5, 0.1),
        'trailing_trigger_mult': (1.0, 2.5, 0.1),
        'trailing_distance_mult': (0.3, 0.8, 0.1),
    }
    
    def optimize_for_regime(self, regime: str, trades: List[Dict]) -> Dict:
        """
        Trouve les params optimaux pour un régime donné.
        
        Returns:
            Dict avec params optimaux et métriques
        """
        best_params = None
        best_score = -999
        
        # Grid search sur les combinaisons
        for sl in np.arange(*self.PARAM_RANGES['atr_mult_sl']):
            for tp in np.arange(*self.PARAM_RANGES['atr_mult_tp']):
                for score in np.arange(*self.PARAM_RANGES['min_score_required']):
                    
                    # Simuler les trades avec ces params
                    simulated_pnl = self.simulate_with_params(
                        trades, sl, tp, score
                    )
                    
                    # Calculer score composite
                    pf = self.calculate_profit_factor(simulated_pnl)
                    wr = self.calculate_win_rate(simulated_pnl)
                    
                    # Score = PF × sqrt(nb_trades) × WR_bonus
                    score = pf * np.sqrt(len(simulated_pnl)) * (1 + (wr - 0.5))
                    
                    if score > best_score:
                        best_score = score
                        best_params = {
                            'atr_mult_sl': sl,
                            'atr_mult_tp': tp,
                            'min_score_required': score,
                        }
        
        return {
            'regime': regime,
            'optimal_params': best_params,
            'expected_pf': best_pf,
            'expected_wr': best_wr,
            'confidence': min(len(trades) / 100, 1.0),
            'sample_size': len(trades)
        }
    
    def simulate_with_params(
        self, 
        trades: List[Dict], 
        sl_mult: float, 
        tp_mult: float,
        min_score: float
    ) -> List[float]:
        """
        Simule les PnL si on avait utilisé ces params.
        
        Utilise les colonnes What-If pour interpoler:
        - Si sl_mult > sl_utilisé: interpoler vers pnl_if_wider_sl
        - Si sl_mult < sl_utilisé: interpoler vers pnl_if_tighter_sl
        """
        simulated_pnls = []
        
        for trade in trades:
            # Filtrer par score minimum
            if trade['score'] < min_score:
                continue  # Ce trade n'aurait pas été pris
            
            base_pnl = trade['pnl_percent']
            used_sl = trade['param_atr_mult_sl']
            
            # Interpoler le PnL basé sur What-If
            if sl_mult > used_sl:
                # SL plus large
                wider_pnl = trade['pnl_if_wider_sl'] or base_pnl
                ratio = (sl_mult - used_sl) / (used_sl * 0.5)  # Assume wider = +50%
                interpolated_pnl = base_pnl + ratio * (wider_pnl - base_pnl)
            else:
                # SL plus serré
                tighter_pnl = trade['pnl_if_tighter_sl'] or base_pnl
                ratio = (used_sl - sl_mult) / (used_sl * 0.25)  # Assume tighter = -25%
                interpolated_pnl = base_pnl + ratio * (tighter_pnl - base_pnl)
            
            simulated_pnls.append(interpolated_pnl)
        
        return simulated_pnls
```

### Approche 2: Bayesian Optimization (Plus Avancé)

```python
from sklearn.gaussian_process import GaussianProcessRegressor
from scipy.optimize import minimize

class BayesianParameterOptimizer:
    """
    Utilise l'optimisation bayésienne pour trouver les params.
    Plus efficace que grid search pour espaces de params larges.
    """
    
    def optimize(self, regime: str, trades: List[Dict]) -> Dict:
        """
        Optimisation bayésienne des paramètres.
        """
        from skopt import gp_minimize
        from skopt.space import Real
        
        # Définir l'espace de recherche
        space = [
            Real(0.6, 2.0, name='atr_mult_sl'),
            Real(1.5, 4.0, name='atr_mult_tp'),
            Real(6.0, 9.0, name='min_score'),
            Real(0.5, 1.5, name='be_mult'),
        ]
        
        # Fonction objectif (à maximiser, donc négatif)
        def objective(params):
            sl, tp, score, be = params
            simulated = self.simulate_with_params(trades, sl, tp, score, be)
            pf = self.calculate_profit_factor(simulated)
            return -pf  # Négatif car gp_minimize minimise
        
        # Optimisation
        result = gp_minimize(
            objective,
            space,
            n_calls=100,
            random_state=42
        )
        
        return {
            'optimal_params': {
                'atr_mult_sl': result.x[0],
                'atr_mult_tp': result.x[1],
                'min_score_required': result.x[2],
                'be_atr_mult': result.x[3],
            },
            'expected_pf': -result.fun,
            'confidence': self.calculate_confidence(trades)
        }
```

---

## 📋 INTÉGRATION AVEC RÉGIMES

### Nouveau: `core/analysis/ml_param_optimizer.py`

```python
"""
ML Parameter Optimizer - Trouve les params optimaux par régime.
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OptimizedRegimeConfig:
    """Configuration optimisée pour un régime"""
    regime: str
    atr_mult_sl: float
    atr_mult_tp: float
    min_score_required: float
    be_atr_mult: float
    trailing_trigger_mult: float
    trailing_distance_mult: float
    confidence: float
    sample_size: int
    expected_pf: float
    expected_wr: float


class MLParamOptimizer:
    """
    Optimise les paramètres de trading par régime.
    """
    
    MIN_TRADES_PER_REGIME = 30
    MIN_CONFIDENCE = 0.70
    
    def __init__(self):
        self.optimized_configs: Dict[str, OptimizedRegimeConfig] = {}
        self.last_optimization = None
    
    def run_optimization(self) -> Dict[str, OptimizedRegimeConfig]:
        """
        Lance l'optimisation pour tous les régimes.
        
        Returns:
            Dict mapping régime → config optimisée
        """
        from core.postgresql_datalogger import get_pg_datalogger
        
        logger.info("🔄 Début optimisation ML des paramètres...")
        
        pg_logger = get_pg_datalogger()
        
        for regime in ['CALME', 'NORMAL', 'VOLATILE']:
            # Récupérer trades du régime
            trades = self._get_trades_for_regime(pg_logger, regime)
            
            if len(trades) < self.MIN_TRADES_PER_REGIME:
                logger.info(f"⏳ {regime}: {len(trades)}/{self.MIN_TRADES_PER_REGIME} trades - skip")
                continue
            
            # Optimiser
            optimized = self._optimize_for_regime(regime, trades)
            
            if optimized.confidence >= self.MIN_CONFIDENCE:
                self.optimized_configs[regime] = optimized
                logger.info(
                    f"✅ {regime}: sl={optimized.atr_mult_sl:.2f}, "
                    f"tp={optimized.atr_mult_tp:.2f}, "
                    f"PF={optimized.expected_pf:.2f} (conf={optimized.confidence:.0%})"
                )
            else:
                logger.info(f"⚠️ {regime}: confiance trop basse ({optimized.confidence:.0%})")
        
        self.last_optimization = datetime.now()
        return self.optimized_configs
    
    def get_optimized_config(self, regime: str) -> Optional[OptimizedRegimeConfig]:
        """Retourne la config optimisée pour un régime, si disponible."""
        return self.optimized_configs.get(regime)
    
    def apply_to_regime_selector(self):
        """
        Applique les params optimisés au MarketRegimeSelector.
        ATTENTION: Nécessite confirmation utilisateur.
        """
        from core.market_regime_selector import get_regime_selector
        
        rs = get_regime_selector()
        
        for regime, config in self.optimized_configs.items():
            if config.confidence < 0.80:
                continue  # Seuil plus strict pour auto-apply
            
            # Mettre à jour les params du régime
            if regime in rs.regime_configs:
                rs.regime_configs[regime].atr_mult_sl = config.atr_mult_sl
                rs.regime_configs[regime].atr_mult_tp = config.atr_mult_tp
                rs.regime_configs[regime].min_score_required = config.min_score_required
                rs.regime_configs[regime].break_even_atr_mult = config.be_atr_mult
                
                # Sauvegarder
                rs.save_regime_config(regime)
                
                logger.info(f"💾 {regime}: params optimisés appliqués et sauvegardés")


# Singleton
_optimizer: Optional[MLParamOptimizer] = None

def get_ml_param_optimizer() -> MLParamOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = MLParamOptimizer()
    return _optimizer
```

---

## 🔄 WORKFLOW COMPLET

```
1. ACCUMULATION (Phase 1)
   │ - 100+ trades avec What-If data
   │
   ▼
2. ANALYSE (Phase 2A-C)
   │ - Corrélations identifiées
   │ - Dashboard fonctionnel
   │
   ▼
3. ML PARAM OPTIMIZER (Phase 2D) ← NOUVEAU
   │ Pour chaque régime avec 30+ trades:
   │   - Grid/Bayesian search sur params
   │   - Utilise What-If pour simulation
   │   - Calcule Profit Factor attendu
   │   - Génère OptimizedRegimeConfig
   │
   ▼
4. VALIDATION
   │ - Comparer params actuels vs optimisés
   │ - Shadow mode: logger ce que donnerait les nouveaux params
   │
   ▼
5. APPLICATION (si confiance > 80%)
   │ - Met à jour RegimeConfig
   │ - Sauvegarde dans config/regimes/*.json
   │
   ▼
6. MONITORING
   │ - Suivre si le PF réel correspond au PF attendu
   │ - Rollback si dégradation
```

---

## 📊 MÉTRIQUES DE SUCCÈS

| Métrique | Avant Optimisation | Après Optimisation | Gain |
|----------|--------------------|--------------------|------|
| PF CALME | 1.2 | 1.5 | +25% |
| PF NORMAL | 1.4 | 1.7 | +21% |
| PF VOLATILE | 1.3 | 1.8 | +38% |
| PF Global | 1.35 | 1.65 | +22% |

---

## ⚠️ SÉCURITÉS

### 1. Validation Croisée
```python
# Ne pas optimiser sur les mêmes trades qu'on utilise pour valider
train_trades = trades[:int(len(trades)*0.7)]
test_trades = trades[int(len(trades)*0.7):]

optimized = optimize(train_trades)
validation_pf = evaluate(test_trades, optimized)

if validation_pf < expected_pf * 0.8:
    logger.warning("⚠️ Overfitting détecté!")
```

### 2. Rollback Automatique
```python
class RollbackManager:
    """Surveille et rollback si dégradation."""
    
    def check_performance(self):
        """Vérifie si les params optimisés performent."""
        recent_trades = get_trades_since(self.optimization_date)
        
        if len(recent_trades) < 20:
            return  # Pas assez de données
        
        current_pf = calculate_pf(recent_trades)
        
        if current_pf < self.expected_pf * 0.7:
            logger.warning(f"🔴 ROLLBACK: PF={current_pf} < {self.expected_pf*0.7}")
            self.rollback_to_previous()
```

### 3. Bounds de Sécurité
```python
# Ne jamais sortir de ces limites même si le ML suggère
SAFE_BOUNDS = {
    'atr_mult_sl': (0.5, 2.5),   # Jamais SL > 2.5× ATR
    'atr_mult_tp': (1.0, 5.0),   # Jamais TP > 5× ATR
    'min_score': (5.0, 10.0),    # Score toujours dans cette plage
}
```

---

## 📋 CHECKLIST PHASE 2D

```
[ ] Créer core/analysis/ml_param_optimizer.py
[ ] Implémenter Grid Search basic
[ ] Implémenter simulation What-If interpolation
[ ] Ajouter validation croisée
[ ] Créer API endpoint /api/optimizer/run
[ ] Créer API endpoint /api/optimizer/results
[ ] Ajouter bouton dans Dashboard
[ ] Implémenter RollbackManager
[ ] Tester avec 100+ trades réels
[ ] Documenter les résultats
```

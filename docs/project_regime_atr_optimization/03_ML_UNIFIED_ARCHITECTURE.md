# 🧠 ARCHITECTURE ML UNIFIÉE - ADAPTIVE TRADING INTELLIGENCE
## Version Finale - Phases 2D & 3

> **Version:** 2.0.0 | **Date:** 11/12/2025 | **Statut:** 📋 PLANIFIÉ

---

## 🎯 VISION GLOBALE

Système ML unifié qui:
1. **Détecte** le régime de marché via classifier ML (pas seuils fixes)
2. **Filtre** les trades avec GradientBoosting calibré (existant)
3. **Adapte** les seuils de confiance selon contexte (nouveau)
4. **Optimise** SL/TP dynamiquement par setup (nouveau)
5. **Apprend** en continu après chaque trade (nouveau)

---

## 📊 ARCHITECTURE SYSTÈME

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ADAPTIVE TRADING INTELLIGENCE (ATI)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    LAYER 1: EXISTANT (conservé)                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │    │
│  │  │ GradientBoost│  │  Calibration │  │   Feature    │               │    │
│  │  │  Classifier  │──│   Isotonic   │──│  Engineering │               │    │
│  │  │  (64-69%)    │  │              │  │   (81 feat)  │               │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    LAYER 2: PHASE 2D (Auto-Adaptation)               │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │    │
│  │  │  Contextual  │  │   Dynamic    │  │    Drift     │               │    │
│  │  │  Threshold   │──│   Config     │──│  Detection   │               │    │
│  │  │  Optimizer   │  │   Manager    │  │              │               │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    LAYER 3: PHASE 3 (ML Avancé)                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │    │
│  │  │   Regime     │  │  Dynamic     │  │   Online     │               │    │
│  │  │  Classifier  │──│   SL/TP      │──│   Learning   │               │    │
│  │  │  (LightGBM)  │  │  (CatBoost)  │  │   (River)    │               │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ✅ COMPOSANTS EXISTANTS (Layer 1)

| Composant | Fichier | Fonction | Status |
|-----------|---------|----------|--------|
| GradientBoosting | `optimization/predictor_optimized.py` | Filtre trades (64-69% accuracy) | ✅ ACTIF |
| Calibration | `optimization/models/train_enhanced.py` | `CalibratedClassifierCV` isotonic | ✅ ACTIF |
| Feature Engineering | `optimization/data/feature_engineering_advanced.py` | 46 → 81+ features | ✅ ACTIF |
| Optuna Tuning | `optimization/optuna_gradientboosting.py` | Hyperparams optimisés | ✅ ACTIF |
| Market Regime | `core/market_regime_selector.py` | Seuils ATR (à remplacer par ML) | ✅ ACTIF |
| Correlation Engine | `core/analysis/correlation_engine.py` | Analyse sessions/régimes | ✅ ACTIF |
| What-If Simulator | `core/analysis/what_if_simulator.py` | Simule scénarios SL/TP | ✅ ACTIF |

### Notes de fiabilité (profitabilité réelle)

- **Feature parity (live)**: `optimization/predictor_optimized.py` calcule les features dérivées manquantes (si inputs bruts présents) pour éviter le remplissage à zéro et réduire l'écart training vs runtime.
- **Analyse EV net par `ml_confidence`**: `scripts/analyze_ml_thresholds.py` permet d'évaluer WinRate + EV (`net_pnl_pct`) + PnL net (`net_pnl_usdt`) par seuil/buckets, avec split temporel train/test (objectif = rentabilité out-of-sample, pas seulement accuracy).

---

## PHASE 2D: AUTO-ADAPTATION (Layer 2)

### 2D.1 Contextual Threshold Optimizer

**Fichier:** `core/ml/threshold_optimizer.py`

**Concept:** Thompson Sampling pour ajuster `gb_min_confidence` par contexte

```python
class ContextualThresholdOptimizer:
    """
    Optimise le seuil de confiance GB par contexte (régime, session, heure).
    Utilise Thompson Sampling pour balance exploration/exploitation.
    """
    
    def __init__(self):
        # Prior Beta(1,1) pour chaque contexte
        self.alpha = defaultdict(lambda: 1.0)  # Succès
        self.beta = defaultdict(lambda: 1.0)   # Échecs
        self.min_threshold = 0.45
        self.max_threshold = 0.70
    
    def get_threshold(self, regime: str, session: str, hour: int) -> float:
        """Retourne le seuil optimal pour ce contexte."""
        context = (regime, session, hour // 4)  # Grouper heures par 4
        
        # Sample depuis Beta distribution
        sample = np.random.beta(self.alpha[context], self.beta[context])
        
        # Mapper sur [min, max]
        threshold = self.min_threshold + sample * (self.max_threshold - self.min_threshold)
        
        return threshold
    
    def update(self, regime: str, session: str, hour: int, win: bool):
        """Met à jour après un trade."""
        context = (regime, session, hour // 4)
        
        if win:
            self.alpha[context] += 1
        else:
            self.beta[context] += 1
```

### 2D.2 Dynamic Config Manager

**Fichier:** Modification de `core/market_regime_selector.py`

**Concept:** Utilise les corrélations pour ajuster les configs régime

```python
def update_from_correlations(self, correlation_data: dict):
    """
    Met à jour les configs régime basé sur les corrélations.
    
    Exemple: Si session ASIA a 35% winrate en CALME,
    augmenter min_score_required pour CALME pendant ASIA.
    """
    for session_data in correlation_data['by_session']:
        if session_data['winrate'] < 40:
            # Augmenter score requis pour ce contexte
            adjustment = (40 - session_data['winrate']) / 10
            self.session_score_adjustments[session_data['value']] = adjustment
```

### 2D.3 Drift Detection

**Fichier:** `core/ml/drift_detector.py`

**Concept:** Détecte si le marché change de comportement

```python
from river import drift

class MarketDriftDetector:
    """Détecte les changements de régime/performance."""
    
    def __init__(self):
        self.pnl_detector = drift.ADWIN()
        self.winrate_detector = drift.ADWIN()
        
    def update(self, pnl: float, win: bool) -> dict:
        self.pnl_detector.update(pnl)
        self.winrate_detector.update(1.0 if win else 0.0)
        
        return {
            'pnl_drift': self.pnl_detector.drift_detected,
            'winrate_drift': self.winrate_detector.drift_detected
        }
```

---

## 🆕 PHASE 3: ML AVANCÉ (Layer 3)

### 3.1 Regime Classifier (LightGBM)

**Fichier:** `core/ml/regime_classifier.py`

**Concept:** Classifier ML pour détecter le régime optimal (remplace seuils ATR)

```python
class RegimeClassifier:
    """
    Prédit le régime optimal basé sur features marché.
    Entraîné sur données What-If (quel régime aurait donné meilleur PnL).
    """
    
    def __init__(self):
        self.model = LGBMClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            device='gpu'  # RTX 3080
        )
        self.feature_names = [
            'atr_1m', 'atr_5m', 'atr_15m',
            'adx_1m', 'adx_5m',
            'di_plus_1m', 'di_minus_1m',
            'volume_ratio', 'spread_pct',
            'hour', 'day_of_week'
        ]
    
    def predict(self, features: dict) -> tuple:
        """Retourne (regime, confidence, probabilities)."""
        X = pd.DataFrame([features])[self.feature_names]
        
        proba = self.model.predict_proba(X)[0]
        regime_idx = np.argmax(proba)
        regime = ['CALME', 'NORMAL', 'VOLATILE'][regime_idx]
        
        return regime, proba[regime_idx], dict(zip(['CALME', 'NORMAL', 'VOLATILE'], proba))
```

### 3.2 Dynamic SL/TP Predictor (CatBoost)

**Fichier:** `core/ml/sltp_predictor.py`

**Concept:** Prédit les multiplicateurs ATR optimaux par setup

```python
class DynamicSLTPPredictor:
    """
    Prédit les multiplicateurs SL/TP optimaux pour chaque setup.
    Entraîné sur données What-If (MFE/MAE historiques).
    """
    
    def __init__(self):
        self.sl_model = CatBoostRegressor(
            iterations=500,
            depth=4,
            learning_rate=0.05,
            task_type='GPU'  # RTX 3080
        )
        self.tp_model = CatBoostRegressor(...)
        self.trailing_model = CatBoostRegressor(...)
    
    def predict(self, features: dict, regime: str) -> dict:
        """Retourne les multiplicateurs optimaux."""
        X = self._prepare_features(features, regime)
        
        return {
            'sl_multiplier': float(self.sl_model.predict(X)[0]),
            'tp_multiplier': float(self.tp_model.predict(X)[0]),
            'trailing_pct': float(self.trailing_model.predict(X)[0])
        }
```

### 3.3 Online Learning (River)

**Fichier:** `core/ml/online_learner.py`

**Concept:** Apprentissage incrémental après chaque trade

```python
from river import linear_model, preprocessing

class OnlineThresholdLearner:
    """
    Apprend en temps réel le seuil optimal.
    Pas besoin de réentraînement complet.
    """
    
    def __init__(self):
        self.model = preprocessing.StandardScaler() | linear_model.LogisticRegression()
        
    def partial_fit(self, features: dict, win: bool):
        """Update après chaque trade."""
        self.model.learn_one(features, win)
    
    def predict_proba(self, features: dict) -> float:
        """Probabilité de win pour ce setup."""
        return self.model.predict_proba_one(features).get(True, 0.5)
```

---

## 🖥️ INTERFACE UI FRONTEND

### MLDashboard - Vue d'ensemble

**Fichier:** `frontend/src/lib/components/ml/MLDashboard.svelte`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ML DASHBOARD                                                     [⚙️ Config]│
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐     │
│  │  🎯 TRADE FILTER   │  │  📊 REGIME         │  │  💰 SL/TP          │     │
│  │  ──────────────    │  │  ──────────────    │  │  ──────────────    │     │
│  │  GB Confidence:    │  │  Current: VOLATILE │  │  SL Mult: 1.35x    │     │
│  │  [████████──] 68%  │  │  Confidence: 87%   │  │  TP Mult: 2.40x    │     │
│  │                    │  │  Since: 14:32      │  │  Trail: 55%        │     │
│  │  Threshold: 0.55   │  │                    │  │                    │     │
│  │  [🔄 Auto] [Manual]│  │  [🤖 ML] [📏 Rules]│  │  [🤖 ML] [📏 Rules]│     │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  📈 PERFORMANCE PAR CONTEXTE (7 derniers jours)                      │   │
│  │  ────────────────────────────────────────────────────────────────    │   │
│  │                                                                       │   │
│  │  Session    │ Trades │ WinRate │ PnL     │ Threshold Optimal        │   │
│  │  ─────────────────────────────────────────────────────────────────   │   │
│  │  EUROPE     │   45   │  52%    │ +12.5$  │ 0.52 ✅                   │   │
│  │  US         │   78   │  48%    │ +8.2$   │ 0.55 ⚠️                   │   │
│  │  ASIA       │   23   │  35%    │ -4.1$   │ 0.62 🔺                   │   │
│  │  ─────────────────────────────────────────────────────────────────   │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  🔄 ONLINE LEARNING STATUS                                            │   │
│  │  ────────────────────────────────────────────────────────────────    │   │
│  │                                                                       │   │
│  │  Last Update: il y a 12 min (Trade #4521)                            │   │
│  │  Drift Detected: ❌ Non                                               │   │
│  │  Model Version: v2.3.1 (trained 3 days ago)                          │   │
│  │  Next Retrain: ~47 trades remaining                                  │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Configuration Panel

**Fichier:** `frontend/src/lib/components/ml/MLConfigPanel.svelte`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ⚙️ ML CONFIGURATION                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌── MODULES ACTIVATION ──────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  [✅] GradientBoosting Trade Filter                                     │ │
│  │       └─ Min Confidence: [0.55] (0.40 - 0.75)                          │ │
│  │                                                                         │ │
│  │  [✅] Contextual Threshold Optimizer (Phase 2D)                         │ │
│  │       └─ Mode: [Thompson Sampling ▼]                                   │ │
│  │       └─ Min Threshold: [0.45]  Max: [0.70]                            │ │
│  │                                                                         │ │
│  │  [❌] ML Regime Classifier (Phase 3)                                    │ │
│  │       └─ Status: En attente de données (besoin 500+ trades)            │ │
│  │                                                                         │ │
│  │  [❌] Dynamic SL/TP Predictor (Phase 3)                                 │ │
│  │       └─ Status: En attente de données (besoin 500+ trades)            │ │
│  │                                                                         │ │
│  │  [✅] Online Learning                                                   │ │
│  │       └─ Update: [Après chaque trade ▼]                                │ │
│  │       └─ Learning Rate: [0.01]                                         │ │
│  │                                                                         │ │
│  │  [✅] Drift Detection                                                   │ │
│  │       └─ Algorithm: [ADWIN ▼]                                          │ │
│  │       └─ Alert Threshold: [0.05]                                       │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌── RÉGIME DETECTION ────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  Mode: [● Seuils ATR (actuel) ○ ML Classifier (Phase 3)]              │ │
│  │                                                                         │ │
│  │  Seuils actuels:                                                       │ │
│  │  ├─ CALME:    ATR < [0.20]%                                            │ │
│  │  ├─ NORMAL:   ATR [0.20]% - [0.50]%                                    │ │
│  │  └─ VOLATILE: ATR > [0.50]%                                            │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌── SL/TP CONFIGURATION ─────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  Mode: [● Par Régime (actuel) ○ ML Dynamic (Phase 3)]                 │ │
│  │                                                                         │ │
│  │  Multiplicateurs par régime:                                           │ │
│  │  ┌─────────┬────────┬────────┬──────────┐                             │ │
│  │  │ Régime  │ SL     │ TP     │ Trailing │                             │ │
│  │  ├─────────┼────────┼────────┼──────────┤                             │ │
│  │  │ CALME   │ [0.8]x │ [1.8]x │ [50]%    │                             │ │
│  │  │ NORMAL  │ [1.0]x │ [2.0]x │ [55]%    │                             │ │
│  │  │ VOLATILE│ [1.2]x │ [2.5]x │ [60]%    │                             │ │
│  │  └─────────┴────────┴────────┴──────────┘                             │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  [💾 Sauvegarder]  [↩️ Reset Defaults]  [📊 Voir Stats]                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 STRUCTURE FICHIERS

```
core/
├── ml/                          # 🆕 NOUVEAU DOSSIER
│   ├── __init__.py
│   ├── threshold_optimizer.py   # Phase 2D - Thompson Sampling
│   ├── drift_detector.py        # Phase 2D - ADWIN
│   ├── regime_classifier.py     # Phase 3 - LightGBM
│   ├── sltp_predictor.py        # Phase 3 - CatBoost
│   └── online_learner.py        # Phase 3 - River
│
├── market_regime_selector.py    # Modifié: ajout update_from_correlations()
└── ...

frontend/src/lib/components/ml/
├── MLDashboard.svelte           # 🆕 Vue d'ensemble
├── MLConfigPanel.svelte         # 🆕 Configuration toggles
├── ThresholdOptimizer.svelte    # 🆕 Visualisation seuils
├── DriftIndicator.svelte        # 🆕 Alertes drift
└── ...

api/routes/
├── ml_config.py                 # 🆕 API pour config ML
└── ...
```

---

## 🔧 STACK TECHNIQUE

| Composant | Librairie | GPU (RTX 3080) |
|-----------|-----------|----------------|
| GradientBoosting | sklearn (existant) | ❌ CPU |
| Calibration | sklearn (existant) | ❌ CPU |
| Threshold Optimizer | Custom (Thompson Sampling) | ❌ CPU |
| Regime Classifier | LightGBM | ✅ GPU training |
| SL/TP Predictor | CatBoost | ✅ GPU training |
| Online Learning | River | ❌ CPU |
| Drift Detection | river.drift (ADWIN) | ❌ CPU |
| Experiment Tracking | MLflow (optionnel) | ❌ |

---

## 📅 TIMELINE IMPLÉMENTATION

### Semaine 1: Phase 2D (Rentabilité immédiate)

| Jour | Tâche | Fichier |
|------|-------|---------|
| J1 | Threshold Optimizer | `core/ml/threshold_optimizer.py` |
| J2 | Intégration main.py | Modification feedback loop |
| J3 | Drift Detection | `core/ml/drift_detector.py` |
| J4 | API + Config | `api/routes/ml_config.py` |
| J5 | Frontend MLConfigPanel | `MLConfigPanel.svelte` |

### Semaine 2: Phase 3.1 (Regime ML)

| Jour | Tâche | Fichier |
|------|-------|---------|
| J1-2 | Regime Classifier | `core/ml/regime_classifier.py` |
| J3 | Training pipeline | Scripts + GPU |
| J4-5 | Intégration + Tests | market_regime_selector.py |

### Semaine 3: Phase 3.2-3.3 (SL/TP + Online)

| Jour | Tâche | Fichier |
|------|-------|---------|
| J1-2 | SL/TP Predictor | `core/ml/sltp_predictor.py` |
| J3-4 | Online Learning | `core/ml/online_learner.py` |
| J5 | Frontend Dashboard | `MLDashboard.svelte` |

---

## 📊 MÉTRIQUES OBJECTIF

| Métrique | Actuel | Phase 2D | Phase 3 |
|----------|--------|----------|---------|
| Win Rate | 44% | 50% | 55% |
| Profit Factor | ~1.2 | 1.5 | 1.8 |
| Trades filtrés (mauvais) | 0% | 15% | 25% |
| Adaptation temps | Manuel | ~100 trades | Temps réel |

---

## ✅ CHECKLIST VALIDATION

- [ ] Architecture validée par utilisateur
- [ ] Documentation mise à jour
- [ ] UI Frontend designée
- [ ] Phase 2D implémentée
- [ ] Phase 3 implémentée
- [ ] Tests complets
- [ ] Déploiement live

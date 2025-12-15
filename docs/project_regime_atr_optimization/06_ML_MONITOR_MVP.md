# 🔬 ML MONITOR - MVP Specification
## Nouvel Onglet Observabilité "Glass Box"

> **Version:** 1.0.0 | **Date:** 14/12/2025 | **Statut:** 📋 SPÉCIFIÉ
> 
> **Objectif:** Transparence totale sur les décisions ML du bot

---

## 🎯 OBJECTIFS

| Objectif | Description | Priorité |
|----------|-------------|----------|
| **Observabilité** | Comprendre POURQUOI le bot prend ses décisions | 🔴 HIGH |
| **Transparence** | "Glass Box" vs "Black Box" | 🔴 HIGH |
| **Diagnostic** | Identifier rapidement les problèmes data/ML | 🔴 HIGH |
| **Confiance** | Valider que le système fonctionne comme prévu | 🟠 MEDIUM |

---

## 📐 ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                        ML MONITOR TAB                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ DATA HEALTH │  │  OPTIMIZER  │  │  ROLLBACK   │             │
│  │             │  │   STATUS    │  │   STATUS    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    DRIFT DETECTION                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 SECTION 1: DATA HEALTH

### Fonction
Afficher la qualité et la distribution des données utilisées par le ML.

### Métriques affichées

#### 1.1 Distribution des Régimes (7 jours)

```
Régime      │ Count │ %     │ WinRate │ PnL
────────────┼───────┼───────┼─────────┼────────
CALME       │  234  │  45%  │   52%   │ +45.2$
NORMAL      │  167  │  32%  │   48%   │ +12.1$
VOLATILE    │   78  │  15%  │   58%   │ +28.4$
CHOPPY      │   26  │   5%  │   42%   │  -3.2$
UNKNOWN     │   15  │   3%  │   35%   │  -8.1$ ⚠️
```

**Alertes:**
- ⚠️ UNKNOWN > 5% → Warning jaune
- 🔴 UNKNOWN > 10% → Alert rouge

#### 1.2 What-If Coverage

```
Période     │ Coverage │ Status
────────────┼──────────┼────────
Global      │    87%   │ ✅ OK
Last 24h    │    95%   │ ✅ Excellent
Last 7d     │    82%   │ ✅ OK
UNKNOWN     │     0%   │ ⚠️ Excluded
```

**Seuils:**
- ✅ ≥ 80%: OK
- ⚠️ 60-80%: Warning
- 🔴 < 60%: Critical

#### 1.3 Backfill Status

```
Metric              │ Value  │ Status
────────────────────┼────────┼────────
Eligible trades     │   45   │ -
Coherent (backfilled)│   32  │ 71% ✅
Excluded            │   13   │ 29%
```

**Exclusion Reasons Breakdown:**
- ATR mismatch: 8 trades
- Missing MFE/MAE: 3 trades
- Params out of range: 2 trades

### API Endpoint

```
GET /api/ml/monitor/data-health

Response:
{
  "regime_distribution": {
    "window_days": 7,
    "data": [
      {"regime": "CALME", "count": 234, "pct": 45.0, "winrate": 52.0, "pnl": 45.2},
      {"regime": "NORMAL", "count": 167, "pct": 32.0, "winrate": 48.0, "pnl": 12.1},
      {"regime": "VOLATILE", "count": 78, "pct": 15.0, "winrate": 58.0, "pnl": 28.4},
      {"regime": "CHOPPY", "count": 26, "pct": 5.0, "winrate": 42.0, "pnl": -3.2},
      {"regime": "UNKNOWN", "count": 15, "pct": 3.0, "winrate": 35.0, "pnl": -8.1}
    ],
    "unknown_warning": false,
    "unknown_critical": false
  },
  "whatif_coverage": {
    "global": {"coverage_pct": 87, "status": "ok"},
    "last_24h": {"coverage_pct": 95, "status": "excellent"},
    "last_7d": {"coverage_pct": 82, "status": "ok"},
    "by_regime": {
      "CALME": 92,
      "NORMAL": 88,
      "VOLATILE": 85,
      "UNKNOWN": 0
    }
  },
  "backfill_status": {
    "eligible_count": 45,
    "coherent_count": 32,
    "excluded_count": 13,
    "exclusion_reasons": {
      "atr_mismatch": 8,
      "missing_mfe_mae": 3,
      "params_out_of_range": 2
    }
  }
}
```

---

## 📊 SECTION 2: OPTIMIZER STATUS

### Fonction
Afficher l'état du Threshold Optimizer et ses décisions.

### Métriques affichées

#### 2.1 Optimizer State

```
Status:           ✅ ACTIVE
Mode:             Thompson Sampling
Current Context:  NORMAL / EUROPE
Current Threshold: 0.55

Last Update:      12 trades ago
Contexts Tracked: 15
```

#### 2.2 Thresholds by Context

```
Context         │ Trades │ WinRate │ PnL     │ Threshold │ Trend
────────────────┼────────┼─────────┼─────────┼───────────┼──────
CALME/EUROPE    │   45   │   58%   │ +12.5$  │   0.52    │ ↓
CALME/US        │   32   │   42%   │  +2.1$  │   0.62    │ ↑
NORMAL/EUROPE   │   78   │   48%   │  +8.2$  │   0.55    │ →
VOLATILE/EUROPE │   28   │   62%   │ +18.3$  │   0.48    │ ↓
```

**Trend Indicators:**
- ↓ Threshold decreasing (more aggressive)
- ↑ Threshold increasing (more conservative)
- → Stable

#### 2.3 Recent Adjustments

```
Time            │ Context         │ Old   │ New   │ Reason
────────────────┼─────────────────┼───────┼───────┼──────────────────
2h ago          │ CALME/US        │ 0.58  │ 0.62  │ WinRate < 40%
6h ago          │ VOLATILE/EUROPE │ 0.52  │ 0.48  │ WinRate > 60%
1d ago          │ NORMAL/ASIA     │ 0.55  │ 0.58  │ PnL negative
```

### API Endpoint

```
GET /api/ml/monitor/optimizer-status

Response:
{
  "enabled": true,
  "mode": "thompson_sampling",
  "current_context": {"regime": "NORMAL", "session": "EUROPE"},
  "current_threshold": 0.55,
  "trades_since_update": 12,
  "contexts_tracked": 15,
  "thresholds_by_context": [
    {
      "regime": "CALME",
      "session": "EUROPE", 
      "trades": 45,
      "winrate": 58.0,
      "pnl": 12.5,
      "threshold": 0.52,
      "trend": "decreasing"
    }
    // ...
  ],
  "recent_adjustments": [
    {
      "timestamp": "2025-12-14T12:00:00Z",
      "context": {"regime": "CALME", "session": "US"},
      "old_threshold": 0.58,
      "new_threshold": 0.62,
      "reason": "winrate_below_40"
    }
    // ...
  ]
}
```

---

## 📊 SECTION 3: ROLLBACK STATUS

### Fonction
Afficher l'état du système de rollback dual (Hard-Stop + Progressive).

### Métriques affichées

#### 3.1 Hard-Stop Monitors

```
Monitor              │ Current │ Threshold │ Status
─────────────────────┼─────────┼───────────┼────────
Session Drawdown     │   1.2%  │    < 5%   │ ✅ OK
Losing Streak        │    2    │    < 5    │ ✅ OK
Profit Factor (20)   │   1.45  │   > 0.5   │ ✅ OK
Win Rate (30)        │   47%   │   > 25%   │ ✅ OK
```

**Status Colors:**
- ✅ Green: Safe (> 50% margin)
- ⚠️ Yellow: Warning (< 50% margin)
- 🔴 Red: Critical (approaching threshold)

#### 3.2 Progressive Rollback State

```
Current Level:        0 (baseline)
Adjustment Range:     -2 to +2

Last Adjustment:      None
Cooldown Status:      ✅ Ready (45 trades since last)

Performance vs Baseline:
├─ Short (20):   +3.2%  ✅ Within tolerance
├─ Medium (50):  +1.8%  ✅ Within tolerance
└─ Long (100):   baseline

Degradation Threshold: -15%
Improvement Threshold: +10%
```

#### 3.3 Regime-Specific Status

```
Regime      │ Level │ vs Baseline │ Action
────────────┼───────┼─────────────┼─────────────
CALME       │   0   │    +5.2%    │ Hold
NORMAL      │  -1   │   -12.3%    │ Degraded
VOLATILE    │   0   │    +8.1%    │ Hold
```

#### 3.4 Rollback History

```
Time        │ Type        │ Regime   │ Level │ Reason
────────────┼─────────────┼──────────┼───────┼─────────────────
3d ago      │ Progressive │ NORMAL   │ 0→-1  │ -18% vs baseline
5d ago      │ Hard-Stop   │ ALL      │ →0    │ Losing streak 5
1w ago      │ Progressive │ VOLATILE │ -1→0  │ +12% improvement
```

### API Endpoint

```
GET /api/ml/monitor/rollback-status

Response:
{
  "hard_stop": {
    "enabled": true,
    "monitors": {
      "session_drawdown": {"current": 1.2, "threshold": 5.0, "status": "ok"},
      "losing_streak": {"current": 2, "threshold": 5, "status": "ok"},
      "profit_factor_20": {"current": 1.45, "threshold": 0.5, "status": "ok"},
      "winrate_30": {"current": 47, "threshold": 25, "status": "ok"}
    },
    "any_triggered": false
  },
  "progressive": {
    "enabled": true,
    "current_level": 0,
    "level_range": [-2, 2],
    "last_adjustment": null,
    "cooldown_status": "ready",
    "trades_since_last": 45,
    "performance_vs_baseline": {
      "short_20": 3.2,
      "medium_50": 1.8,
      "long_100": 0
    },
    "thresholds": {
      "degrade": -15,
      "improve": 10
    }
  },
  "by_regime": {
    "CALME": {"level": 0, "vs_baseline": 5.2, "action": "hold"},
    "NORMAL": {"level": -1, "vs_baseline": -12.3, "action": "degraded"},
    "VOLATILE": {"level": 0, "vs_baseline": 8.1, "action": "hold"}
  },
  "history": [
    {
      "timestamp": "2025-12-11T10:00:00Z",
      "type": "progressive",
      "regime": "NORMAL",
      "old_level": 0,
      "new_level": -1,
      "reason": "performance_below_threshold"
    }
    // ...
  ]
}
```

---

## 📊 SECTION 4: DRIFT DETECTION

### Fonction
Afficher les résultats de la détection de drift (changement de distribution).

### Métriques affichées

#### 4.1 Overall Status

```
Status: ✅ No drift detected
Last Check: 5 min ago
Next Check: in 10 min
Algorithm: ADWIN
```

#### 4.2 Monitored Distributions

```
Metric       │ Status  │ p-value │ Trend
─────────────┼─────────┼─────────┼────────────
PnL          │ Stable  │  0.72   │ →
WinRate      │ Stable  │  0.68   │ →
ATR          │ Watch   │  0.12   │ ↑ 👀
ADX          │ Stable  │  0.85   │ →
Volume       │ Stable  │  0.79   │ →
```

**Status Levels:**
- Stable (p > 0.20): No concern
- Watch (0.05 < p < 0.20): Monitor closely
- Drift (p < 0.05): Significant change detected

#### 4.3 Drift History

```
Time        │ Metric   │ p-value │ Action Taken
────────────┼──────────┼─────────┼────────────────────
2d ago      │ WinRate  │  0.03   │ Threshold adjusted
5d ago      │ ATR      │  0.04   │ Regime recalibrated
```

### API Endpoint

```
GET /api/ml/monitor/drift-status

Response:
{
  "overall_status": "stable",
  "last_check": "2025-12-14T14:50:00Z",
  "next_check": "2025-12-14T15:00:00Z",
  "algorithm": "adwin",
  "distributions": {
    "pnl": {"status": "stable", "p_value": 0.72, "trend": "neutral"},
    "winrate": {"status": "stable", "p_value": 0.68, "trend": "neutral"},
    "atr": {"status": "watch", "p_value": 0.12, "trend": "increasing"},
    "adx": {"status": "stable", "p_value": 0.85, "trend": "neutral"},
    "volume": {"status": "stable", "p_value": 0.79, "trend": "neutral"}
  },
  "history": [
    {
      "timestamp": "2025-12-12T10:00:00Z",
      "metric": "winrate",
      "p_value": 0.03,
      "action_taken": "threshold_adjusted"
    }
    // ...
  ]
}
```

---

## 🔧 CONFIGURATION

### Variables config.py

```python
ML_MONITOR_CONFIG = {
    # === General ===
    'ml_monitor_enabled': True,
    'ml_monitor_refresh_interval_seconds': 30,
    
    # === Data Health ===
    'ml_monitor_data_health_window_days': 7,
    'ml_monitor_unknown_regime_warning_pct': 5,
    'ml_monitor_unknown_regime_critical_pct': 10,
    'ml_monitor_whatif_coverage_warning_pct': 80,
    'ml_monitor_whatif_coverage_critical_pct': 60,
    
    # === Backfill ===
    'ml_monitor_backfill_coherence_enabled': True,
    'ml_monitor_backfill_atr_tolerance_pct': 50,
    'ml_monitor_backfill_require_mfe_mae': True,
    
    # === Display ===
    'ml_monitor_show_rollback_history': True,
    'ml_monitor_rollback_history_days': 30,
    'ml_monitor_show_drift_history': True,
    'ml_monitor_drift_history_days': 14,
}
```

### Variables config_overrides.json

```json
{
  "ml_monitor_enabled": true,
  "ml_monitor_refresh_interval_seconds": 30,
  "ml_monitor_unknown_regime_warning_pct": 5,
  "ml_monitor_whatif_coverage_warning_pct": 80,
  "ml_monitor_show_rollback_history": true,
  "ml_monitor_show_drift_history": true
}
```

---

## 📁 FICHIERS À CRÉER

### Backend

| Fichier | Description | Priorité |
|---------|-------------|----------|
| `api/routes/ml_monitor.py` | Endpoints API ML Monitor | 🔴 HIGH |
| `core/ml/data_quality_checker.py` | Vérification qualité données | 🔴 HIGH |
| `core/ml/rollback_manager.py` | Gestion rollback dual | 🔴 HIGH |

### Frontend

| Fichier | Description | Priorité |
|---------|-------------|----------|
| `MLMonitorPanel.svelte` | Container principal | 🔴 HIGH |
| `DataHealthCard.svelte` | Section Data Health | 🔴 HIGH |
| `OptimizerStatusCard.svelte` | Section Optimizer | 🔴 HIGH |
| `RollbackStatusCard.svelte` | Section Rollback | 🔴 HIGH |
| `DriftStatusCard.svelte` | Section Drift | 🟠 MEDIUM |

---

## 🔌 WEBSOCKET EVENTS

### Event: ml_monitor_update
Envoyé toutes les 30 secondes avec l'état complet.

```json
{
  "type": "ml_monitor_update",
  "data": {
    "data_health": { /* ... */ },
    "optimizer_status": { /* ... */ },
    "rollback_status": { /* ... */ },
    "drift_status": { /* ... */ }
  }
}
```

### Event: ml_alert
Envoyé immédiatement en cas d'alerte.

```json
{
  "type": "ml_alert",
  "severity": "warning" | "critical",
  "category": "data_health" | "rollback" | "drift",
  "message": "UNKNOWN regime > 5%",
  "details": { /* ... */ }
}
```

### Event: ml_rollback_triggered
Envoyé quand un rollback est déclenché.

```json
{
  "type": "ml_rollback_triggered",
  "rollback_type": "hard_stop" | "progressive",
  "regime": "NORMAL" | null,
  "reason": "losing_streak_5",
  "old_params": { /* ... */ },
  "new_params": { /* ... */ }
}
```

---

## ✅ CHECKLIST IMPLÉMENTATION

### Phase 1: Backend Core
- [ ] `core/ml/data_quality_checker.py`
- [ ] `core/ml/rollback_manager.py`
- [ ] Modifier `config.py` avec ML_MONITOR_CONFIG

### Phase 2: API
- [ ] `api/routes/ml_monitor.py`
- [ ] Intégration WebSocket dans `main.py`
- [ ] Tests API

### Phase 3: Frontend
- [ ] `MLMonitorPanel.svelte`
- [ ] `DataHealthCard.svelte`
- [ ] `OptimizerStatusCard.svelte`
- [ ] `RollbackStatusCard.svelte`
- [ ] `DriftStatusCard.svelte`
- [ ] Intégration dans `MLPanel.svelte`

### Phase 4: Polish
- [ ] Tests end-to-end
- [ ] Documentation utilisateur
- [ ] Optimisation performance

---

## 📝 NOTES

- Le ML Monitor ne modifie RIEN, il observe uniquement
- Les actions (rollback, ajustements) sont déclenchées par les modules existants
- Refresh automatique via WebSocket, pas de polling intensif
- Mobile-friendly: cartes repliables

---

**Ce document définit le MVP complet du ML Monitor. Implémentation prévue en 3 phases (Backend → API → Frontend).**

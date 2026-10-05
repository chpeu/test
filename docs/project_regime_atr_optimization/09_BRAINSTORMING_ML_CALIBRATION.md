# 🧠 BRAINSTORMING ML CALIBRATION - Intégration Stratégie Filtrage
## Maximiser Expectancy (PnL) et Robustesse

> **Version:** 1.0.0 | **Date:** 16/12/2025 | **Statut:** 📋 SPÉCIFIÉ
> 
> **Objectif:** Challenger et améliorer la stratégie de filtrage ML pour maximiser l'EV

---

## 🎯 CONTEXTE

Ce document capture les décisions du brainstorming sur l'optimisation du système ML:
- **Training** : Quels trades utilisés pour entraîner le modèle GB
- **Calibration** : Quels trades utilisés pour calibrer les buckets de confiance
- **Gating** : Quels trades passent le filtre ML
- **Metrics** : Quels trades comptabilisés dans les stats

---

## ✅ DÉJÀ IMPLÉMENTÉ (16/12/2025)

### 1. Filtrage exit_reason

**Fichier:** `ml/calibration.py`

```python
# Trades valides pour calibration/training (exits propres, non-biaisées)
VALID_EXIT_REASONS_CALIBRATION = {
    'TP', 'SL', 'TRAILING_STOP', 'ROI_TARGET',
    'STAGNATION', 'STAGNATION_POSITIVE', 'STAGNATION_MFE_PROTECT',
    'BE_TRIGGERED', 'TIME_LIMIT'
}

# Exit reasons à exclure (intervention manuelle ou erreurs système)
EXCLUDED_EXIT_REASONS = {
    'MANUAL', 'MANUAL_CLOSE', 'ERROR', 'LIQUIDATION', 
    'FORCE_CLOSE', 'UNKNOWN', 'SL_EXCHANGE'
}
```

**Impact:** `update_calibration()` rejette maintenant les trades avec exit non-propres.

### 2. CalibrationStats EV-based

**Fichier:** `ml/calibration.py`

Nouvelles propriétés ajoutées à `CalibrationStats`:
- `sum_pnl_pct` : Somme des PnL%
- `sum_pnl_pct_sq` : Somme des PnL² (pour variance)
- `var_pnl_pct` : Variance calculée
- `std_pnl_pct` : Écart-type
- `ev_estimate` : Expectancy = mean(pnl)
- `ev_lower_bound` : Borne inférieure conservatrice (EV - stderr)

### 3. Exploration Contrôlée (Threshold Optimizer)

**Fichier:** `core/ml/threshold_optimizer.py`

- Nouveau paramètre `exploration_rate` (défaut: 2%)
- Méthode `should_explore()` pour bypass exploration
- Tracking séparé des trades exploration dans `ContextStats`
- Stats exploration dans `get_status()`

**Config:** `threshold_exploration_rate` dans `config_overrides.json`

---

## ⚠️ DÉCISIONS IMPORTANTES (16/12/2025)

### Décision 1: exploration_rate = 0 en production

**Statut:** 🟡 DORMANT (code prêt, désactivé par défaut)

**Raison:**
- L'exploration = laisser passer des trades rejetés par le seuil ML
- En prod avec capital réel, ces trades ont statistiquement un WR plus bas
- Risque de pertes volontaires sans bénéfice immédiat

**Condition d'activation future:**
- [ ] Mode dry-run disponible → activer `exploration_rate = 0.02` en dry-run
- [ ] OU shadow mode implémenté → simuler sans exécuter
- [ ] OU sizing différencié → exploration = 10% du sizing normal
- [ ] Collecter 100+ trades exploration avant d'analyser

**Valeur actuelle:** `threshold_exploration_rate = 0.00`

---

### Décision 2: EV metrics = monitoring only (pas de gating)

**Statut:** 🟡 DORMANT (code prêt, non utilisé pour décision)

**Raison:**
- Avec 20-30 trades par bucket, l'EV est dominée par outliers
- Variance énorme → intervalle de confiance trop large
- WinRate plus stable pour décision avec peu de données

**Condition d'activation future:**
- [ ] 100+ trades par bucket de confiance
- [ ] Variance stabilisée (std < 0.3%)
- [ ] Tests en shadow mode montrant EV > WR pour décision

**Usage actuel:**
- `ev_estimate` et `ev_lower_bound` calculés et disponibles
- Affichables dans ML Monitor (informatif)
- NON utilisés pour gating (WinRate calibré reste la décision)

---

### Opportunités futures liées

Ces deux fonctionnalités dormantes seront pertinentes quand :

1. **Plus de données** : 200+ trades → stats fiables
2. **Mode dry-run/shadow** : tester sans risque capital
3. **A/B testing** : comparer stratégies sur sous-ensembles
4. **Retrain modèle** : après amélioration du modèle, l'exploration peut révéler des opportunités manquées

**Action requise :** Revenir sur ces décisions après 200 trades ou après implémentation d'un mode shadow.

---

## 📋 À IMPLÉMENTER (Phases futures)

### Phase 2H.1: Migration SQL Calibration EV

**Priorité:** 🟠 MEDIUM | **Effort:** 2h

Ajouter les colonnes EV dans la table `ml_calibration`:

```sql
ALTER TABLE ml_calibration ADD COLUMN IF NOT EXISTS sum_pnl_pct FLOAT DEFAULT 0;
ALTER TABLE ml_calibration ADD COLUMN IF NOT EXISTS sum_pnl_pct_sq FLOAT DEFAULT 0;
ALTER TABLE ml_calibration ADD COLUMN IF NOT EXISTS model_version VARCHAR(50);
ALTER TABLE ml_calibration ADD COLUMN IF NOT EXISTS last_model_reset_at TIMESTAMP;
```

**Fichiers à modifier:**
- `ml/calibration.py` : Requêtes UPDATE/SELECT pour les nouvelles colonnes
- `database/migrations/` : Script de migration

---

### Phase 2H.2: Model Version Tracking

**Priorité:** 🟠 MEDIUM | **Effort:** 3h

**Concept:** Tracker la version du modèle GB pour reset automatique de calibration après retrain.

```python
# Dans MLCalibrationManager
def check_model_version_change(self, current_version: str) -> bool:
    """Vérifie si le modèle a changé et reset si nécessaire."""
    stored_version = self._get_stored_model_version()
    if stored_version and stored_version != current_version:
        logger.warning(f"🔄 Model version changed: {stored_version} → {current_version}")
        self.reset_calibration(reason=f"model_version_change_{current_version}")
        return True
    return False
```

**Fichiers à modifier:**
- `ml/calibration.py` : Ajout `check_model_version_change()`, `_get_stored_model_version()`
- `optimization/predictor_optimized.py` : Appel au démarrage
- `config.py` : Variable `current_ml_model_version`

---

### Phase 2H.3: Simulated Seeding Post-Retrain

**Priorité:** 🟡 LOW | **Effort:** 5h

**Concept:** Après un retrain, re-scorer les N derniers trades avec le nouveau modèle pour initialiser la calibration.

```python
def seed_from_backtest(self, n_trades: int = 500) -> int:
    """
    Re-score les derniers trades avec le modèle actuel.
    Nécessite: features stockées en DB ou recalculables.
    """
    # 1. Récupérer les trades éligibles (exit_reason valide)
    # 2. Recalculer ml_confidence avec nouveau modèle
    # 3. Appeler update_calibration pour chaque trade
```

**Prérequis:**
- [ ] Feature store ou recalcul possible
- [ ] Historique des features dans `trade_atr_metrics`

**Fichiers à modifier:**
- `ml/calibration.py` : Méthode `seed_from_backtest()`
- `scripts/` : Script CLI `seed_calibration_post_retrain.py`

---

### Phase 2H.4: Gating EV-based (au lieu de WinRate)

**Priorité:** 🟠 MEDIUM | **Effort:** 4h

**Concept:** Utiliser `ev_lower_bound` au lieu de `actual_winrate` pour décider si un bucket est éligible.

```python
def should_take_trade_ev(self, direction: str, ml_confidence: float) -> Tuple[bool, float, str]:
    """Décision basée sur EV plutôt que WinRate."""
    stats = self._get_stats(direction, bucket)
    
    # Utiliser la borne inférieure de l'EV
    if stats.ev_lower_bound > 0:  # EV positive avec confiance
        return True, stats.ev_estimate, "ev_positive"
    elif stats.ev_lower_bound > -0.05:  # Incertain
        return True, stats.ev_estimate, "ev_uncertain_explore"
    else:
        return False, stats.ev_estimate, "ev_negative"
```

**Fichiers à modifier:**
- `ml/calibration.py` : Nouvelle méthode `should_take_trade_ev()`
- `config.py` : Toggle `ml_calib_use_ev_gating`
- `frontend/MLConfigPanel.svelte` : UI toggle

---

### Phase 2H.5: Seed Historical avec exit_reason Filter

**Priorité:** 🟢 HIGH | **Effort:** 1h

**Concept:** Modifier les méthodes de seeding existantes pour filtrer par exit_reason.

```python
def seed_from_historical_trades(self, days: int = 30) -> int:
    """Seed avec filtrage exit_reason."""
    query = """
        SELECT ... FROM trades
        WHERE timestamp_entry >= NOW() - INTERVAL '{days} days'
          AND ml_confidence IS NOT NULL
          AND ml_confidence >= 30
          AND timestamp_exit IS NOT NULL
          AND exit_reason IN ('TP', 'SL', 'TRAILING_STOP', ...)  -- NOUVEAU
    """
```

**Fichiers à modifier:**
- `ml/calibration.py` : `seed_from_historical_trades()`, `seed_from_last_n_trades()`

---

### Phase 2H.6: Trade Events Log (Data Quality) ✅ COMPLETE (16/12/2025)

**Priorité:** 🟢 HIGH | **Effort:** 5h | **Status:** IMPLEMENTED

**Concept:** Créer une table `trade_events` pour historiser tous les changements d'état d'un trade (Partial TP, Trailing Activation, SL Move, Stagnation Trigger).

**Justification:**
- L'analyse post-mortem est limitée car on n'a que l'état final et quelques snapshots.
- Impossible de reconstruire la courbe d'évolution du trade (quand le trailing a bougé ? quand le TP partiel a été pris ?).

**Table SQL:**
```sql
CREATE TABLE trade_events (
    id SERIAL PRIMARY KEY,
    trade_id UUID REFERENCES trades(id),
    event_type VARCHAR(50),  -- PARTIAL_TP, TRAILING_ACTIVATED, SL_MOVED, STAGNATION_DETECTED
    event_timestamp TIMESTAMP DEFAULT NOW(),
    price_at_event FLOAT,
    pnl_at_event FLOAT,
    details JSONB            -- { "sold_pct": 50, "new_sl": 0.123, "trigger": "MFE" }
);
```

**Fichiers à modifier:**
- `database/models.py` : Nouveau modèle
- `core/postgresql_datalogger.py` : Méthode `log_event(trade_id, type, details)`
- `core/position_manager.py` : Appels à `log_event()` aux moments clés

---

## 📊 MATRICE DE FILTRAGE FINALE

| exit_reason | Training GB | Calibration | Gating | Metrics |
|-------------|-------------|-------------|--------|---------|
| TP | ✅ | ✅ | ✅ | ✅ |
| SL | ✅ | ✅ | ✅ | ✅ |
| TRAILING_STOP | ✅ | ✅ | ✅ | ✅ |
| ROI_TARGET | ✅ | ✅ | ✅ | ✅ |
| BE_TRIGGERED | ✅ | ✅ | ✅ | ✅ |
| STAGNATION | ✅ | ✅ | ✅ | ✅ |
| STAGNATION_POSITIVE | ✅ | ✅ | ✅ | ✅ |
| STAGNATION_MFE_PROTECT | ✅ | ✅ | ✅ | ✅ |
| TIME_LIMIT | ✅ | ✅ | ✅ | ✅ |
| SL_EXCHANGE | ⚠️ | ❌ | ✅ | ✅ |
| MANUAL | ❌ | ❌ | ✅ | ⚠️ |
| ERROR | ❌ | ❌ | ✅ | ⚠️ |
| LIQUIDATION | ❌ | ❌ | ✅ | ⚠️ |

**Légende:**
- ✅ = Inclus
- ❌ = Exclu
- ⚠️ = Inclus mais flaggé/alerté

---

## 📐 ARCHITECTURE OBJECTIVE FUNCTION

```
┌─────────────────────────────────────────────────────────────────┐
│                    OBJECTIVE FUNCTION                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Niveau 1: EV/trade                                             │
│  ═══════════════════                                            │
│  E[PnL] = P(win) × avg_win - P(loss) × avg_loss - fees         │
│                                                                  │
│  Niveau 2: EV/temps (Sharpe-like)                               │
│  ═════════════════════════════════                              │
│  E[PnL/h] = E[PnL] / avg_trade_duration                         │
│  Sharpe = E[PnL] / std(PnL)                                     │
│                                                                  │
│  Niveau 3: Risk-adjusted                                        │
│  ═══════════════════════                                        │
│  EV_lower = E[PnL] - z × std(PnL) / sqrt(n)                    │
│  MaxDrawdown constraint                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⏱️ TIMELINE SUGGÉRÉE

| Phase | Description | Priorité | Effort | Dépendances |
|-------|-------------|----------|--------|-------------|
| 2H.5 | Seed avec exit_reason filter | 🟢 HIGH | 1h | - |
| 2H.1 | Migration SQL EV | 🟠 MEDIUM | 2h | - |
| 2H.2 | Model version tracking | 🟠 MEDIUM | 3h | 2H.1 |
| 2H.4 | Gating EV-based | 🟠 MEDIUM | 4h | 2H.1 |
| 2H.3 | Simulated seeding | 🟡 LOW | 5h | 2H.2, Feature store |

---

## 📁 FICHIERS MODIFIÉS (Résumé)

### Déjà modifiés (16/12/2025)
- `ml/calibration.py` : Constantes exit_reason, CalibrationStats EV, filtrage update_calibration
- `core/ml/threshold_optimizer.py` : exploration_rate, should_explore(), tracking exploration

### À modifier (Phases futures)
- `ml/calibration.py` : Méthodes seeding, gating EV, model version
- `config.py` : Nouvelles variables
- `database/migrations/` : Migration SQL
- `frontend/` : UI toggles

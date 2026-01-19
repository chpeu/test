# 📋 MASTER IMPLEMENTATION PLAN
## Market Regime V2 + ATR Optimization + ML Integration

> **Version:** 1.3.0 | **Date:** 14/12/2025 | **Statut:** ✅ Phases 0-2E opérationnelles + Stagnation Positive Exit
> 
> **⚠️ CONTRAINTE MAJEURE:** Aucune modification ne doit réduire le nombre de trades

---

## 🔗 MAPPING AVEC ATR_OPTIMIZATION_NEXT_STEPS.md

| ATR_OPTIMIZATION Phase | → MASTER_PLAN Phase | Status |
|------------------------|---------------------|--------|
| Phase 1.4: Context Clustering | Phase 2A (Corrélations) | ✅ Intégré |
| Phase 1.5: Dashboard Monitoring | Phase 2B (Dashboard) | ✅ Intégré |
| Phase 1.6: CorrelationEngine | Phase 2A (Corrélations) | ✅ Intégré |
| Phase 2.1: ContinuousATROptimizer | **Phase 2D (ML Param Optimizer)** | ✅ AJOUTÉ |
| Phase 2.2-2.4: Auto-Apply & Rollback | Phase 3C (Auto-Apply) | ✅ Intégré |

---

## 🧠 DEUX TYPES D'OPTIMISATION ML

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DISTINCTION CRITIQUE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TYPE A: ML DÉTECTION RÉGIME (Phase 3A)                                     │
│  ══════════════════════════════════════                                     │
│  Question: "Dans quel régime sommes-nous?"                                  │
│  Input:    ATR, ADX, Volume, Heure, BTC                                     │
│  Output:   CALME | NORMAL | VOLATILE                                        │
│  But:      Détecter le contexte de marché actuel                           │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TYPE B: ML OPTIMISATION PARAMÈTRES (Phase 2D) ← NOUVEAU                   │
│  ═════════════════════════════════════════════                              │
│  Question: "Quels params optimaux pour VOLATILE?"                          │
│  Input:    Historique trades VOLATILE + What-If                            │
│  Output:   atr_mult_sl=1.73, atr_mult_tp=2.91, min_score=7.2               │
│  But:      Trouver les meilleurs SL/TP/Score pour chaque régime            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## OBJECTIFS & MÉTRIQUES

| Métrique | Actuel | Phase 2F | Phase 2H | Phase 3 | Objectif Final |
|----------|--------|----------|----------|---------|----------------|
| Win Rate | 44.8% | 49% | 54% | 58% | 60%+ |
| Avg PnL/trade | +0.098% | +0.15% | +0.22% | +0.28% | +0.35% |
| Nombre Trades | 2,311 | **2,311** | **2,311** | **2,311** | **MAINTENIR** ⚠️ |
| Profit Factor | ~1.35 | 1.6 | 1.8 | 2.0 | 2.2 |
| Exit Efficiency | ~60% | ~65% | **~75%** | ~80% | 85%+ |
| Regret moyen | ~0.8% | ~0.6% | **~0.3%** | ~0.2% | <0.15% |

### CONTRAINTE ABSOLUE
| Règle | Impact |
|-------|--------|
| **Aucune réduction du nombre de trades** | Toutes les optimisations doivent améliorer la GESTION des trades, pas leur FILTRAGE |

---

## VUE D'ENSEMBLE DES PHASES

```
PHASE 0: Infrastructure (2h)        ← SQL + Config + Helpers
    │
    ▼
PHASE 1A: Logging Contextuel (3h)   ← Session/Heure dans chaque trade
    │                                  Bot: ✅ Running
    ▼
PHASE 1B: Régime V2 Quick Wins (4h) ← Médiane + Hystérésis + Lissage
    │                                  Bot: ✅ Running (toggles)
    ▼
PHASE 1C: What-If Régime (3h)       ← Quel régime aurait été optimal?
    │                                  Bot: ✅ Running
    ▼
PHASE 1D: Intégration Frontend (4h) ← UI Régime V2 + Toggles
    │                                  Bot: ✅ Running
    ▼
PHASE 1E: Auto-Calibration + BTC (6h) ← Seuils dynamiques + Indicateur BTC
    │                                    Bot: ✅ Running
    ▼
══════════════════════════════════════════════════════════════
    ⏸️ PAUSE: Accumulation 50+ trades (3-7 jours)
══════════════════════════════════════════════════════════════
    │
    ▼
PHASE 2A: Analyse Corrélations (4h) ← Session ↔ WinRate, Régime ↔ PnL
    │                                  (= ATR_OPT Phase 1.4 + 1.6)
    ▼
PHASE 2B: Dashboard Monitoring (6h) ← UI visualisation par session/régime
    │                                  (= ATR_OPT Phase 1.5)
    ▼
PHASE 2C: Optimizer Suggestions (SUPPRIMÉ) ← remplacé par 2D (auto-adaptation)
    │
    ▼
PHASE 2D: Auto-Adaptation ML (10h)  ← Threshold Optimizer + Drift Detector
    │                                  (= ATR_OPT Phase 2.1)
    ▼
PHASE 2E: Filtres ML Stricts (3h)   ← ATR MIN/MAX, Spread, Volume
    │                                  Bot: ✅ Running
    ▼
PHASE 2F: Quick Wins Gestion (4h)   ← 🆕 Stagnation Positive + Trailing MFE
    │                                  ⚠️ Sans réduction trades (MODE FIXE)
    ▼
PHASE 2G: ML Monitor + Rollback (8h) ← Observabilité + Sécurité
    │   Monitor, Rollback Dual, Data Quality, Backfill
    ▼
PHASE 2H: POST-EXIT ANALYSIS (12h)  ← 🆕 INTÉGRÉ 19/01/2026
    │   2H.1: Data Collection (✅ DONE)     - Tracking prix post-exit
    │   2H.2: Metrics & ML Targets (2h)    - Calcul optimal_sl/trailing/be
    │   2H.3: ML Model Training (4h)       - Multi-output regressor
    │   2H.4: Live Integration (3h)        - MLParamPredictor
    │   2H.5: Frontend Dashboard (3h)      - PostExitAnalysis.svelte
    ▼
PHASE 2I: ML Calibration EV (6h)     ← 🔄 SIMPLIFIÉ MODE FIXE
    │   2I.1: Migration SQL EV (2h)
    │   2I.2: Model version tracking (3h)
    │   2I.5: exit_reason filter (1h)
    │   ❌ 2I.3: Simulated seeding (SUPPRIMÉ - ROI incertain)
    │   ❌ 2I.4: Gating EV-based (SUPPRIMÉ - besoin 100+ trades/bucket)
    ▼
══════════════════════════════════════════════════════════════
    ⏸️ PAUSE: Accumulation 500+ trades (3-4 semaines)
    ⏸️ Prérequis Phase 2H.3: 500+ trades avec targets ML
══════════════════════════════════════════════════════════════
    │
    ▼
PHASE 3A: Mixture-of-Experts (8h)   ← ⏸️ REPORTER (besoin 50+ trades/régime)
    │   Un modèle ML par régime (CALME/NORMAL/VOLATILE/CHOPPY)
    ▼
PHASE 3B: Ensemble Learning (8h)    ← Multi-Model Voting + Stacking
    │                                    GB + XGBoost + LightGBM
    ▼
PHASE 3C: Feature Engineering (10h) ← 21 nouvelles features
    │                                    Lag, Rolling, BTC, Sentiment
    ▼
══════════════════════════════════════════════════════════════
    ⏸️ PHASES SUPPRIMÉES DU SCOPE MODE FIXE
══════════════════════════════════════════════════════════════
    │
    ❌ Phase 4: Séquences Temporelles (SUPPRIMÉ - prérequis 1000+ trades)
    ❌ Phase 5: Reinforcement Learning (SUPPRIMÉ - trop complexe)
    ❌ Phase 6: MLOps & Production (REPORTER - système pas encore stable)
```

---

## 🧠 ARCHITECTURE ML EN COUCHES

Cette approche combine votre GradientBoosting actuel (Moteur) avec le nouveau système de Régime (Contexte).

1.  **Niveau 1 : Régime ML (Contexte)**
    *   *Question :* "Est-ce que le marché est favorable ?"
    *   *Sortie :* `CALME` | `NORMAL` | `VOLATILE` | `CHOPPY`

2.  **Niveau 2 : Entry ML (Décision)**
    *   *Question :* "Dois-je entrer sur ce trade ?"
    *   *Entrée :* Indicateurs techniques + **Features Régime (Niveau 1)**
    *   *Sortie :* Score Confiance (ex: 72%)

3.  **Niveau 3 : Param Optimizer (Exécution)**
    *   *Question :* "Quels TP/SL pour ce contexte ?"
    *   *Entrée :* Régime (Niveau 1) + Historique
    *   *Sortie :* `atr_mult_tp=0.6`, `atr_mult_sl=0.8`

---

## 📁 FICHIERS À CRÉER/MODIFIER PAR PHASE

### PHASE 0: Infrastructure

| Action | Fichier | Description |
|--------|---------|-------------|
| CREATE | `database/migrations/add_regime_context_columns.sql` | 15+ nouvelles colonnes |
| CREATE | `utils/session_detector.py` | Helper détection session |
| MODIFY | `config.py` | Section `MARKET_REGIME_V2_CONFIG` |
| MODIFY | `config_overrides.json` | Toggles V2 |
| CREATE | `verification/run_regime_v2_migration.py` | Script migration |

### PHASE 1A: Logging Contextuel

| Action | Fichier | Description |
|--------|---------|-------------|
| MODIFY | `core/postgresql_datalogger.py` | +session_market, hour_utc dans logs |
| MODIFY | `core/market_regime_selector.py` | +métadonnées dans regime_history |
| MODIFY | `export_datalogger_to_excel.py` | Inclure nouvelles colonnes |
| CREATE | `verification/verify_phase1a_logging.py` | Vérification |

### PHASE 1B: Régime V2

| Action | Fichier | Description |
|--------|---------|-------------|
| MODIFY | `core/market_regime_selector.py` | Médiane, Hystérésis, Lissage, ATR5m |
| MODIFY | `frontend/.../VariablesPanel.svelte` | Toggles UI |
| CREATE | `verification/verify_phase1b_v2_methods.py` | Tests V2 |

### PHASE 1C: What-If Régime

| Action | Fichier | Description |
|--------|---------|-------------|
| MODIFY | `core/analysis/what_if_simulator.py` | +simulate_regime_scenarios() |
| MODIFY | `core/position_manager.py` | Appel what-if régime |
| CREATE | `verification/backfill_regime_whatif.py` | Backfill existants |

---

## 🗄️ SCHÉMA SQL COMPLET

### Nouvelles Colonnes `trade_atr_metrics`

```sql
-- Saisonnalité
session_market VARCHAR(20),        -- ASIA, EUROPE, US_OPEN, etc.
hour_utc INT,                      -- 0-23
day_of_week INT,                   -- 0=Lundi, 6=Dimanche
is_weekend BOOLEAN,

-- Régime V2 Metadata
regime_detection_method VARCHAR(30), -- RULE_BASED_V1/V2, ML
regime_atr_median FLOAT,
regime_atr_smoothed FLOAT,
regime_confidence FLOAT,
regime_stability_minutes INT,

-- ML Régime (Phase 3)
regime_ml_predicted VARCHAR(20),
regime_ml_confidence FLOAT,
regime_ml_vs_rule_match BOOLEAN,

-- What-If Régime
pnl_if_calme_params FLOAT,
pnl_if_normal_params FLOAT,
pnl_if_volatile_params FLOAT,
optimal_regime_retrospective VARCHAR(20),

-- Session Multiplier
session_atr_multiplier FLOAT
```

### Nouvelles Colonnes `market_regime_history`

```sql
detection_method VARCHAR(30),
atr_median FLOAT,
atr_smoothed FLOAT,
session_market VARCHAR(20),
hysteresis_applied BOOLEAN,
outliers_filtered_count INT,
ml_confidence FLOAT
```

### Nouvelles Colonnes `scan_logs`

```sql
session_market VARCHAR(20),
hour_utc INT,
regime_at_scan VARCHAR(20),
regime_confidence_at_scan FLOAT
```

---

## ⚙️ VARIABLES DE CONFIGURATION

### Section `MARKET_REGIME_V2_CONFIG`

```python
{
    # Master toggles
    "v2_enabled": False,
    "use_median": False,
    "use_hysteresis": False,
    "use_smoothing": False,
    "use_atr_5m": False,
    "use_seasonality": False,
    "use_ml_regime": False,          # Phase 3
    
    # Paramètres Médiane/Outliers
    "outlier_filter_enabled": True,
    "outlier_std_threshold": 2.5,
    "min_pairs_for_valid_regime": 5,
    
    # Paramètres Hystérésis
    "hysteresis_buffer_percent": 0.10,
    "threshold_calme_max": 0.20,
    "threshold_normal_max": 0.40,
    
    # Paramètres Lissage
    "smoothing_alpha": 0.3,
    
    # Paramètres ATR Combiné
    "atr_1m_weight": 0.40,
    "atr_5m_weight": 0.60,
    
    # Paramètres Stabilité
    "min_regime_duration_minutes": 30,
    "confirmation_required_checks": 2,
    
    # Sessions (voir détail Phase 0)
    "sessions": { ... }
}
```

---

## 📅 SESSIONS HORAIRES (UTC)

| Session | Heures UTC | Paris | Multiplier ATR | Score Adj |
|---------|------------|-------|----------------|-----------|
| ASIA | 00-07 | 01-08 | 0.80 | +0.5 |
| EUROPE_OPEN | 07-09 | 08-10 | 1.20 | 0.0 |
| EUROPE | 09-13 | 10-14 | 1.00 | 0.0 |
| US_PREMARKET | 13-14 | 14-15 | 1.10 | +0.3 |
| US_OPEN | 14-16 | 15-17 | **1.50** | -0.5 |
| US_SESSION | 16-20 | 17-21 | 1.20 | 0.0 |
| US_CLOSE | 20-21 | 21-22 | 1.30 | -0.3 |
| NIGHT | 21-24 | 22-01 | 0.70 | +1.0 |

---

## ✅ CHECKLISTS PAR PHASE

### Phase 0 Checklist
- [x] Migration SQL créée
- [x] Migration exécutée sans erreur
- [x] `session_detector.py` créé et testé
- [x] Config variables ajoutées
- [x] Export Excel mis à jour

### Phase 1A Checklist
- [x] Logger trade_atr_metrics enrichi
- [x] Logger scan_logs enrichi
- [x] Logger regime_history enrichi
- [x] Vérification: 1 trade loggé avec session_market

### Phase 1B Checklist
- [x] `calculate_atr_metric()` (médiane) implémenté
- [x] `should_change_regime()` (hystérésis) implémenté
- [x] `apply_smoothing()` (EMA) implémenté
- [x] `calculate_combined_atr()` (1m+5m) implémenté
- [x] Scanner: calcul `atr_percent_5m`
- [x] Runtime: `check_regime(atr_values, atr_5m_values, adx_values)`
- [x] Frontend toggles ajoutés
- [x] Vérification: régime stable (min duration + hystérésis)

### Phase 1C Checklist
- [x] `simulate_regime_scenarios()` implémenté
- [x] Intégration dans `close_position()`
- [x] Backfill trades existants
- [x] Vue SQL `v_optimal_regime_analysis`

---

## 🔗 DÉPENDANCES TECHNIQUES

```
utils/session_detector.py
    └── Utilisé par:
        ├── postgresql_datalogger.py (logging)
        ├── market_regime_selector.py (seuils ajustés)
        └── analyzer.py (context scan)

config.MARKET_REGIME_V2_CONFIG
    └── Utilisé par:
        ├── market_regime_selector.py (tous les calculs)
        ├── utils/effective_config.py (override JSON)
        └── frontend (toggles)

core/market_regime_selector.py
    └── Modifications:
        ├── calculate_atr_metric() ← NOUVEAU
        ├── should_change_regime() ← NOUVEAU
        ├── apply_smoothing() ← NOUVEAU
        ├── calculate_combined_atr() ← NOUVEAU
        ├── determine_regime() ← MODIFIÉ (calibration + BTC + saisonnalité optionnelle)
        ├── check_regime() ← MODIFIÉ (V2 activé via toggles)
        └── _log_regime_change_to_db() ← MODIFIÉ
```

---

## 📝 NOTES IMPORTANTES

### Principe de Non-Régression
- **Tous les toggles désactivés par défaut**
- V1 reste le comportement par défaut
- Activation progressive feature par feature
- Rollback possible à tout moment

### Données Requises par Phase
- Phase 1: 0 trades (infrastructure)
- Phase 2: 50+ trades loggés
- Phase 3: 200+ trades loggés

### Compatibilité
- Migration SQL: `IF NOT EXISTS` partout
- Anciennes données: colonnes NULL acceptées
- Export Excel: colonnes optionnelles masquées si vides

---

## 📄 DOCUMENTS DÉTAILLÉS

Les détails d'implémentation sont dans:
- `phases/PHASE_0_INFRASTRUCTURE.md` ← SQL + Config détaillés
- `phases/PHASE_1_IMPLEMENTATION.md` ← Code Python Logging + Régime V2
- `phases/PHASE_2_3_ANALYSIS_ML.md` ← Analyse + Dashboard + ML Regime
- `phases/PHASE_2D_ML_PARAMETER_OPTIMIZER.md` ← ML optimisation params par régime
- `10_POST_EXIT_INTEGRATION.md` ← 🆕 Phase 2H - Guide complet Post-Exit (5 sous-phases)
- `11_PROJECT_OVERVIEW_PERFORMANCE.md` ← 🆕 Analyse impact performance de chaque composant
- `architecture/INTERACTIONS_REGIME_PARAMS.md` ← Comment les params circulent dans le pipeline

**Documents de référence existants:**
- `reference/ATR_OPTIMIZATION_NEXT_STEPS.md` ← Roadmap originale ATR (intégrée ici)
- `architecture/PLAN_MARKET_REGIME.md` ← Architecture conceptuelle

---

## 📊 RÉSUMÉ COUVERTURE COMPLÈTE

| Dimension | Couvert | Document |
|-----------|---------|----------|
| Détection Régime (V1→V2→ML) | ✅ | PHASE_1, PHASE_2_3 |
| Saisonnalité (Sessions) | ✅ | PHASE_0, PHASE_1 |
| What-If Régime | ✅ | PHASE_1C |
| What-If ATR (existant) | ✅ | ATR_OPTIMIZATION |
| **Régime → Scanner (filtrage)** | ✅ | INTERACTIONS |
| **Régime → Position Manager (SL/TP)** | ✅ | INTERACTIONS |
| **Régime → SL MEXC** | ✅ | INTERACTIONS |
| **Régime → GB Features** | ✅ | INTERACTIONS |
| **ML Optimisation Params** | ✅ | PHASE_2D |
| **Post-Exit Analysis** | ✅ | PHASE_2H (10_POST_EXIT) |
| **ML Params Dynamiques** | 🔄 | PHASE_2H.3-2H.4 |
| Auto-Apply & Rollback | ✅ | PHASE_3C |
| Dashboard | ✅ | PHASE_2B |

---

## 🎯 PHASE 2H: POST-EXIT ANALYSIS - DÉTAILS

### Objectif global
Optimiser les paramètres de sortie (SL, Trailing, BE) en analysant les mouvements de prix APRÈS chaque trade.

### Architecture
```
Trade fermé → Tracking 5min → Métriques → Targets ML → Modèle → Prédictions live
```

### Sous-phases

#### 2H.1: Data Collection ✅ TERMINÉE (19/01/2026)
**Durée:** Déjà implémenté | **Prérequis:** Aucun

**Fichiers créés:**
- `database/migrations/add_post_exit_analysis_tables.sql`
- `core/post_exit/tracker.py`
- `core/post_exit/manager.py`
- `core/callbacks/post_exit_loop.py`

**Fichiers modifiés:**
- `core/position_manager.py` (hook ligne 4643-4676)
- `main.py` (startup/shutdown + API endpoints)

**Tables SQL:**
- `trade_post_exit_analysis` (métriques agrégées)
- `trade_post_exit_samples` (données brutes 1Hz)

**Livrable:** ✅ Collecte automatique active

---

#### 2H.2: Metrics & ML Targets ⬜ À FAIRE
**Durée:** 2h | **Prérequis:** 100+ trades avec données post-exit

**Tâches:**
1. Script `scripts/analyze_post_exit.py`
2. Calcul `ml_optimal_sl_pct`, `ml_optimal_trailing_trigger`, `ml_optimal_be_trigger`
3. Endpoint `/api/analytics/post-exit/summary`

**Formules:**
```python
# SL optimal (trade gagnant)
ml_optimal_sl_pct = max(used_sl, abs(post_exit_mae) * 1.1 + 0.02)

# Trailing trigger optimal
if post_exit_mfe > 0.5:
    ml_optimal_trailing_trigger = realized_pnl * 0.8
else:
    ml_optimal_trailing_trigger = realized_pnl * 0.5

# BE trigger optimal
ml_optimal_be_trigger = realized_pnl * 0.4
```

**Livrable:** Targets ML calculés pour chaque trade

---

#### 2H.3: ML Model Training ⬜ À FAIRE
**Durée:** 4h | **Prérequis:** 500+ trades avec targets ML

**Tâches:**
1. `optimization/post_exit_dataset.py` (dataset builder)
2. Feature engineering (ATR, régime, session, ADX, RSI, etc.)
3. Multi-output regressor (GradientBoosting)
4. Validation temporelle (train/test split)
5. Sauvegarder `exit_optimizer.pkl`

**Features (8):**
- `atr_entry`, `market_regime`, `session`, `adx`, `rsi_1m`, `spread_bps`, `hour_utc`, `direction`

**Targets (3):**
- `ml_optimal_sl_pct`, `ml_optimal_trailing_trigger`, `ml_optimal_be_trigger`

**Métriques cibles:**
- MAE < 0.05% sur chaque param
- R² > 0.3 sur chaque param

**Livrable:** Modèle ML entraîné et validé

---

#### 2H.4: Live Integration ⬜ À FAIRE
**Durée:** 3h | **Prérequis:** Phase 2H.3 terminée

**Tâches:**
1. `core/ml_param_predictor.py` (MLParamPredictor class)
2. Intégration dans `PositionManager.open_position()`
3. Config `ml_dynamic_params_enabled`
4. Fallback si confidence < seuil
5. Logging params prédits vs utilisés

**Bornes de sécurité:**
```python
sl_pct: (0.08, 0.50)
trailing_trigger: (0.10, 0.50)
be_trigger: (0.10, 0.40)
```

**Livrable:** Params dynamiques ML en production

---

#### 2H.5: Frontend Dashboard ⬜ À FAIRE
**Durée:** 3h | **Prérequis:** Phase 2H.4 en production

**Tâches:**
1. `PostExitDashboard.svelte`
2. Graphiques exit_efficiency par jour
3. Distribution grades (A+, A, B, C, D, F)
4. Comparaison params prédits vs utilisés
5. Métriques ML accuracy

**Livrable:** Interface monitoring complète

---

### Impact attendu Phase 2H
| Métrique | Avant | Après Phase 2H | Amélioration |
|----------|-------|----------------|--------------|
| Exit Efficiency | 60% | 75% | +25% |
| Regret moyen | 0.8% | 0.3% | -62% |
| Winrate | 54% | 58% | +7% |
| Profit Factor | 1.6 | 1.8 | +12% |

---

**Ce document est la référence principale. Les phases sont exécutées séquentiellement avec validation à chaque étape.**

# 📊 PROJECT TRACKER - REGIME FIXE OPTIMIZATION
## Document de Suivi Central

> **Dernière mise à jour:** 19/01/2026 06:45
> **Status global:** ✅ PHASES 0-2E OPÉRATIONNELLES | ✅ POST-EXIT ANALYSIS Phase 1 PRÊT
> **Phase actuelle:** ▶️ RUNNING | **Mode:** FIXE uniquement (pas ATR)
> 
> **⚠️ CONTRAINTE MAJEURE:** Aucune modification ne doit réduire le nombre de trades
> 
> **🔄 CHANGEMENT 19/01/2026:** Projet recentré sur mode FIXE (pas ATR)

---

## 🎯 OBJECTIF DU PROJET (MODE FIXE)

Créer un système d'optimisation intelligent qui:
1. **Détecte** le régime de marché (CALME/NORMAL/VOLATILE/CHOPPY) de manière fiable
2. **Adapte** automatiquement **9 paramètres FIXE** selon le régime
3. **Optimise** ces paramètres via ML + Post-Exit Analysis
4. **Applique** les optimisations automatiquement avec rollback de sécurité

### Variables FIXE optimisables (9 total)

| Variable | Priorité ML | Description |
|----------|-------------|-------------|
| `sl_percent` | ⭐⭐⭐⭐⭐ | Stop Loss initial |
| `trailing_trigger_pnl` | ⭐⭐⭐⭐⭐ | PnL% pour activer trailing |
| `break_even_trigger` | ⭐⭐⭐⭐ | PnL% pour déplacer SL à entry |
| `trailing_min_distance` | ⭐⭐⭐⭐ | Distance initiale trailing |
| `tp_percent` | ⭐⭐⭐⭐ | Take Profit final |
| `partial_tp_percent` | ⭐⭐⭐⭐ | % position vendue au TP partiel |
| `trailing_max_distance` | ⭐⭐⭐ | Distance max trailing |
| `trailing_pnl_cap` | ⭐⭐⭐ | PnL% pour atteindre max_distance |
| `trailing_enabled` | ⭐⭐ | Activer/désactiver trailing |

### ❌ Variables NON utilisées (ATR-only, supprimées du scope)
- `stagnation_exit_*` (tout le bloc)
- `stagnation_positive_*` (tout le bloc)
- `trailing_mfe_*` (tout le bloc)
- `atr_mult_*` (multiplicateurs ATR)

---

## 🆕 POST-EXIT ANALYSIS SYSTEM (19/01/2026) - ✅ PRÊT À DÉPLOYER

> **Documentation:** `docs/POST_EXIT_ANALYSIS_ML_SYSTEM.md`
> **Status:** ✅ Phase 1 IMPLÉMENTÉE ET TESTÉE | ⬜ Phases 2-5 EN ATTENTE
> **Activation:** Automatique au redémarrage du backend

### Objectif
Collecter les données de prix APRÈS clôture de chaque trade pour:
1. Évaluer l'optimalité des sorties (`exit_efficiency_pct`)
2. Générer des **targets ML** pour les 9 variables FIXE
3. Alimenter le ML Param Optimizer avec des données précises

### Intégration avec le projet Regime FIXE

| Composant | Utilisation Post-Exit |
|-----------|----------------------|
| **ML Param Optimizer** | Fournit `ml_optimal_sl_pct`, `ml_optimal_trailing_trigger`, `ml_optimal_be_trigger` |
| **ML Monitor** | Métriques `exit_efficiency_pct`, `regret_pct` |
| **Mixture-of-Experts** | Targets segmentés par `entry_market_regime` |

### ⚠️ Supprimé (ATR-only)
- ~~Phase 2F (Trailing MFE)~~ → Ne s'applique pas en mode FIXE

### Fichiers implémentés

| Fichier | Description |
|---------|-------------|
| `database/migrations/add_post_exit_analysis_tables.sql` | Tables SQL + vues |
| `core/post_exit/tracker.py` | `PostExitTracker` dataclass |
| `core/post_exit/manager.py` | `PostExitManager` singleton |
| `core/callbacks/post_exit_loop.py` | Boucle prix dédiée |
| `core/position_manager.py:4643-4676` | Hook start_tracking |
| `main.py:3833-3868` | API endpoints |

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/post-exit/status` | Statut système (enabled, active_count) |
| `GET /api/post-exit/recent` | Métriques récentes |

### Prochaines étapes
1. **Phase 2**: Calculer métriques + targets ML
2. **Phase 3**: Entraîner modèle multi-output
3. **Phase 4**: Intégration live
4. **Phase 5**: Frontend dashboard

### 📚 Documentation complète
| Document | Description |
|----------|-------------|
| `10_POST_EXIT_INTEGRATION.md` | Guide d'implémentation détaillé (toutes les phases) |
| `11_PROJECT_OVERVIEW_PERFORMANCE.md` | Analyse d'impact performance de chaque composant |

---

## ✅ ÉTAT RUNTIME (19/01/2026)

- **Régime V2**
  - `market_regime_v2_enabled` utilise:
    - ATR 5m (`atr_percent_5m`) remonté par le scanner
    - `calculate_combined_atr()` + `apply_smoothing()`
    - hystérésis `should_change_regime()`
- **Phase 1E (Auto-Calibration + BTC)**
  - Déclenchement périodique depuis `check_regime()` (cache 6h + cooldown tentative)
  - Calibration via `core.postgresql_datalogger` (pas de module `database.postgres_pool`)
- **Phase 2D (Auto-Adaptation ML)**
  - `threshold_optimizer` + `drift_detector` rechargent la config runtime via `config_overrides.json`
  - Persistence:
    - `data/ml/threshold_optimizer_state.json` (save à chaque update)
    - `data/ml/drift_detector_state.json` (créé après volume suffisant)

### Scripts de vérification

- `python verification\verify_runtime_loop.py --loops 1 --interval 1`
- `python verification\verify_phase1b_v2_methods.py`
- `python verification\verify_phase2d_integration.py`

## ✅ FEATURE IMPLÉMENTÉE: Stagnation Positive Exit (14/12/2025)

> **Spec:** `05_STAGNATION_POSITIVE_EXIT.md`
> **Impact estimé:** +16.4% PnL sur trades STAGNATION

### Paramètres implémentés
| Paramètre | Défaut | Recommandé | Description |
|-----------|--------|------------|-------------|
| `stagnation_positive_exit_enabled` | `true` | `true` | Active sortie anticipée en profit |
| `stagnation_positive_threshold` | `0.03%` | `0.03%` | Seuil profit pour sortir |
| `stagnation_positive_timeout_seconds` | `60s` | `90s` | Timeout réduit si en profit |
| `stagnation_use_mfe_tracking` | `true` | `true` | Protéger le MFE atteint |
| `stagnation_mfe_pullback_pct` | `0.08%` | `0.05%` | Sortir si pullback depuis MFE |

### Checklist implémentation ✅
- [x] Backend: `position_manager.py` + `config.py` + `main.py` (WebSocket handlers)
- [x] Frontend: `VariablesPanel.svelte` (UI + export Excel)
- [x] SQL: Migration `add_stagnation_positive_exit.sql` (8 colonnes)
- [x] Logging: `postgresql_datalogger.py` (config + tracking)
- [x] Nouveaux exit_reason: `STAGNATION_POSITIVE`, `STAGNATION_MFE_PROTECT`

### 🔧 Fix SL_EXCHANGE (14/12/2025)
**Problème:** 4/8 derniers trades marqués SL_EXCHANGE incorrectement
- Le bot détectait SL_EXCHANGE simplement si `len(mexc_positions) == 0`
- Le prix de sortie n'était pas le vrai prix de fill MEXC

**Correction:** `main.py` lignes 2590-2645
- Vérifie si le prix a vraiment atteint le SL MEXC calculé
- Récupère le vrai prix de fill depuis l'historique MEXC
- Ne marque pas SL_EXCHANGE si c'est une race condition

### 🔧 Désactivation ATR MAX (14/12/2025)
**Problème:** ~1,495 scans bloqués/semaine pour ATR trop haut, mais les données montrent:
- ATR 1m > 0.50% = **+168.96% PnL** (le PLUS rentable)
- ATR 5m 0.70-1.00% = **57% WinRate** (le MEILLEUR)
- Le filtre ATR MAX bloquait des trades RENTABLES

**Correction:** `core/analyzer/filters.py` lignes 213-266
- Si `market_regime_enabled = True` → ATR MAX désactivé (plus de limite haute)
- Si `market_regime_enabled = False` → ATR MAX conservé (fallback sécurité)
- ATR MIN toujours actif (filtre les marchés trop calmes)

### 🔧 Optimisation BE Trigger + ATR MIN (14/12/2025)
**Problème identifié:** Analyse 24h montre:
- LOW (ATR<0.20%): 23% WR sans BE, **100% WR avec BE** mais seulement 15% des trades atteignent BE
- MEDIUM (0.20-0.50%): 33% WR, BE trigger insuffisant
- 50% des scans rejetés par `atr_filter` (ATR MIN trop strict)

**Corrections apportées:**

#### 1. Position Manager - Adaptation locale BE (`core/position_manager.py`)
| Régime Local | Ancien BE mult | Nouveau BE mult | Impact |
|--------------|----------------|-----------------|--------|
| LOW (<0.20%) | 1.0 | **0.7** | BE 30% plus tôt |
| MEDIUM (0.20-0.50%) | 0.6 | **0.5** | BE 17% plus tôt |
| HIGH (>0.50%) | 1.2 | **1.0** | BE 17% plus tôt |

#### 2. Configs Régime (`config/regimes/*.json`)
| Régime | Param | Ancien | Nouveau |
|--------|-------|--------|---------|
| CALME | `break_even_atr_mult` | 0.8 | **0.6** |
| CALME | `trailing_trigger_atr_mult` | 1.0 | **0.8** |
| CALME | `optimal_atr_min` | 0.10 | **0.08** |
| NORMAL | `break_even_atr_mult` | 1.2 | **1.0** |
| NORMAL | `trailing_trigger_atr_mult` | 1.5 | **1.2** |
| NORMAL | `optimal_atr_min` | 0.15 | **0.10** |
| VOLATILE | `trailing_trigger_atr_mult` | 2.0 | **1.5** |
| VOLATILE | `optimal_atr_min` | 0.25 | **0.20** |

#### 3. Config globale (`config.py`)
- `optimal_atr_min_1m`: 0.12% → **0.08%** (permet marchés calmes)

**Impact attendu:**
- +30% de trades avec BE trigger en régime LOW
- +opportunités en marchés calmes (ATR < 0.12%)
- Dashboard Market Regime affiche les nouvelles valeurs automatiquement

---

## 📁 STRUCTURE DU DOSSIER

```
docs/project_regime_atr_optimization/
│
├── 00_PROJECT_TRACKER.md          ← CE FICHIER (suivi central)
│
├── 01_SYNTHESE_COMPLETE.md        ← Vue complète du projet
├── 02_MASTER_PLAN.md              ← Roadmap des phases
├── 05_STAGNATION_POSITIVE_EXIT.md ← Spec sortie stagnation positive
├── 06_ML_MONITOR_MVP.md           ← 🆕 Spec nouvel onglet "ML Monitor"
├── 07_ROLLBACK_DUAL_SYSTEM.md     ← 🆕 Spec rollback Hard-Stop + Progressive
├── 08_DATA_BACKFILL_STRATEGY.md   ← 🆕 Stratégie backfill cohérent
├── 09_BRAINSTORMING_ML_CALIBRATION.md ← 🆕 Brainstorming EV-based + exploration
│
├── phases/
│   ├── PHASE_0_INFRASTRUCTURE.md  ← SQL + Config + Helpers
│   ├── PHASE_1_IMPLEMENTATION.md  ← Logging + Régime V2
│   ├── PHASE_2_3_ANALYSIS_ML.md   ← Analyse + ML Regime
│   └── PHASE_2D_ML_PARAM_OPTIMIZER.md ← ML optimisation params
│
├── architecture/
│   ├── INTERACTIONS_REGIME_PARAMS.md  ← Flux params pipeline
│   └── PLAN_MARKET_REGIME.md          ← Architecture conceptuelle
│
└── reference/
    ├── ATR_OPTIMIZATION_NEXT_STEPS.md ← Roadmap ATR originale
    └── BRAINSTORM_ATR_OPTIMIZATION.md ← Brainstorm initial
```

---

## 📅 TIMELINE & STATUS

### ✅ Phase 1.3a: Local Regime Adaptation (SPRINT 3) - COMPLÉTÉE
> **Concept:** Adaptation des paramètres TP/SL/BE/Trailing PAR TRADE basée sur l'ATR% local

| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Calcul régime LOCAL (LOW/MEDIUM/HIGH) | ✅ DONE | 10/12 | ATR% < 0.2/0.2-0.5/>0.5 |
| Adaptation TP/SL multiplicateurs | ✅ DONE | 10/12 | MEDIUM agressif (×0.6) |
| Adaptation BE/Trailing | ✅ DONE | 10/12 | BE×0.5, Trail×0.6 en MEDIUM |
| Adaptation Stagnation timeout | ✅ DONE | 10/12 | ×0.7 en MEDIUM |
| Stockage `effective_config` par trade | ✅ DONE | 10/12 | Dans Position dataclass |
| Logging dans `trade_atr_metrics` | ✅ DONE | 10/12 | Colonnes param_* remplies |
| Script vérification | ✅ DONE | 10/12 | `verify_adaptive_behavior.py` |
| **PHASE 1.3a COMPLETE** | ✅ | 10/12 | - |

#### Régimes LOCAL vs GLOBAL
| Régime LOCAL | ATR% | Ajustements | Winrate Observé |
|--------------|------|-------------|-----------------|
| **LOW** | < 0.2% | Base (aucun) | 52% ✅ |
| **MEDIUM** | 0.2-0.5% | TP×0.6, BE×0.5, Trail×0.6, Stag×0.7 | 15% → En test |
| **HIGH** | > 0.5% | SL×1.2, Trail×1.5, Stag×1.5 | 100% (1 trade) |

#### Fichiers Modifiés
- `core/position_manager.py` : Calcul régime + adaptation params
- `core/position/trailing_stop.py` : Support `custom_distance_pct`
- `utils/effective_config.py` : `set_local_trade_adjustments()`
- `verification/verify_adaptive_behavior.py` : Script de test

---

### Phase 0: Infrastructure ✅
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Migration SQL (35 colonnes) | ✅ DONE | 10/12/2025 | add_regime_context_columns.sql |
| session_detector.py | ✅ DONE | 10/12/2025 | 8 sessions définies |
| Config MARKET_REGIME_V2_CONFIG | ✅ DONE | 10/12/2025 | Ajouté dans config.py |
| config_overrides.json toggles | ✅ DONE | 10/12/2025 | 11 nouveaux toggles |
| Script migration | ✅ DONE | 10/12/2025 | run_regime_v2_migration.py |
| **PHASE 0 COMPLETE** | ✅ | 10/12/2025 | Infrastructure prête |

### Phase 1A: Logging Contextuel ✅
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Logger session/hour dans trade_atr_metrics | ✅ DONE | 10/12/2025 | 8 colonnes ajoutées |
| Logger session/régime dans scan_logs | ✅ DONE | 10/12/2025 | 4 colonnes ajoutées |
| Logger colonnes V2 dans market_regime_history | ✅ DONE | 10/12/2025 | 7 colonnes ajoutées |
| Script vérification | ✅ DONE | 10/12/2025 | verify_phase1a_logging.py |
| **PHASE 1A COMPLETE** | ✅ | 10/12/2025 | Prêt pour test réel |

### Phase 1B: Régime V2 Quick Wins ✅
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| calculate_atr_metric() (médiane) | ✅ DONE | 10/12/2025 | + filtrage outliers |
| apply_smoothing() (EMA) | ✅ DONE | 10/12/2025 | Alpha configurable |
| should_change_regime() (hystérésis) | ✅ DONE | 10/12/2025 | Buffer 10% |
| calculate_combined_atr() (1m+5m) | ✅ DONE | 10/12/2025 | Poids configurables |
| Script vérification | ✅ DONE | 10/12/2025 | verify_phase1b_v2_methods.py |
| **PHASE 1B COMPLETE** | ✅ | 10/12/2025 | Toggles OFF par défaut |

### Phase 1C: What-If Régime ✅
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| simulate_regime_scenarios() (4 régimes) | ✅ DONE | 10/12/2025 | CALME/NORMAL/VOLATILE |
| update_regime_whatif() | ✅ DONE | 10/12/2025 | Mise à jour DB |
| Backfill trades existants | ✅ DONE | 10/12/2025 | 56/75 trades |
| **PHASE 1C COMPLETE** | ✅ | 10/12/2025 | CALME optimal pour 75% |

### Phase 1D: Intégration Composants ✅
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Nouvel onglet Frontend "Régime V2" | ✅ DONE | 11/12/2025 | VariablesPanel.svelte |
| Toggles V2 (7 switches) | ✅ DONE | 11/12/2025 | Tous OFF par défaut |
| Sliders (buffer, alpha, durée) | ✅ DONE | 11/12/2025 | Conditionnels |
| Insights performance session | ✅ DONE | 11/12/2025 | Données historiques |
| **PHASE 1D COMPLETE** | ✅ | 11/12/2025 | Frontend prêt |

### Phase 1E: Auto-Calibration Seuils + BTC Indicator ✅
> **Objectif:** Améliorer la détection de régime avec seuils dynamiques et confirmation BTC
> **Décision:** Brainstorm Option D (11/12/2025)

| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Document PHASE_1D_AUTO_CALIBRATION_BTC.md | ✅ DONE | 11/12/2025 | Plan intégration |
| `core/btc_indicator.py` (BTCIndicator) | ✅ DONE | 11/12/2025 | MEXC API, cache 5min |
| `calibrate_thresholds()` (percentiles 7j) | ✅ DONE | 11/12/2025 | P33=CALME, P66=VOLATILE |
| `get_btc_status()` + `should_force_volatile_from_btc()` | ✅ DONE | 11/12/2025 | BTC volatile → force VOLATILE |
| Intégration dans `determine_regime()` | ✅ DONE | 11/12/2025 | Seuils calibrés + BTC check |
| Toggles config.py (8 nouveaux) | ✅ DONE | 11/12/2025 | Tous OFF par défaut |
| **PHASE 1E COMPLETE** | ✅ | 11/12/2025 | Prêt pour activation |

#### Nouveaux Toggles Phase 1E
| Toggle | Défaut | Description |
|--------|--------|-------------|
| `market_regime_auto_calibration_enabled` | OFF | Active calibration percentiles |
| `market_regime_calibration_lookback_days` | 7 | Fenêtre historique |
| `market_regime_calibration_percentile_calme` | 33 | P33 = seuil CALME |
| `market_regime_calibration_percentile_volatile` | 66 | P66 = seuil VOLATILE |
| `market_regime_btc_indicator_enabled` | OFF | Active indicateur BTC |
| `market_regime_btc_volatile_threshold_1h` | 2.0% | Seuil BTC volatile 1h |
| `market_regime_btc_force_volatile_enabled` | ON | Force VOLATILE si BTC volatile |

#### Fichiers Créés/Modifiés
- `core/btc_indicator.py` : NOUVEAU - BTCIndicator classe
- `core/market_regime_selector.py` : +4 méthodes Phase 1E
- `config.py` : +8 toggles Phase 1E
- `docs/project_regime_atr_optimization/phases/PHASE_1D_AUTO_CALIBRATION_BTC.md` : Documentation

### ⏸️ Pause Accumulation (50+ trades)
| Métrique | Objectif | Actuel | Status |
|----------|----------|--------|--------|
| Trades avec session_market | 50+ | 75 | ✅ |
| Trades avec What-If régime | 50+ | 56 | ✅ |
| Nouveaux trades post-Phase 1D | 50+ | 0 | ⏳ EN COURS |

**Paramètres runtime (13/12/2025):**
- `market_regime_v2_enabled`: ON
- `market_regime_use_median`: ON
- `market_regime_use_hysteresis`: ON
- `market_regime_use_smoothing`: ON
- `market_regime_use_atr_5m`: ON
- `market_regime_auto_calibration_enabled`: ON
- `market_regime_btc_indicator_enabled`: ON
- `threshold_optimizer_enabled`: ON
- `drift_detection_enabled`: ON

**Historique (snapshot 11/12/2025 - accumulation V1):**
- `market_regime_v2_enabled`: OFF (comportement V1)
- `market_regime_outlier_filter`: ON (seul toggle actif)
- Tous autres toggles: OFF

**Insights actuels:**
- 75% des trades auraient mieux performé avec params CALME
- EUROPE_OPEN: +0.31% avg (meilleure session)
- US_OPEN: -0.17% avg (à éviter)

### Phase 2A: Analyse Corrélations ✅
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| correlation_engine.py | ✅ DONE | 11/12/2025 | Analyse sessions/régimes/heures |
| API endpoint | ✅ DONE | 11/12/2025 | /api/ml/analytics/correlations |
| **PHASE 2A COMPLETE** | ✅ | 11/12/2025 | - |

### Phase 2B: Dashboard Corrélations ✅
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| CorrelationAnalytics.svelte | ✅ DONE | 11/12/2025 | Tableaux sessions/régimes |
| MLPanel intégration | ✅ DONE | 11/12/2025 | Onglet "Corrélations" |
| **PHASE 2B COMPLETE** | ✅ | 11/12/2025 | - |

### Phase 2C: Suggestions (SUPPRIMÉ)
> ⚠️ Supprimé - Remplacé par Phase 2D Auto-Adaptation
> L'objectif est l'adaptation AUTOMATIQUE, pas manuelle

### Phase 2D: Auto-Adaptation ML ✅
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| `core/ml/threshold_optimizer.py` | ✅ DONE | 11/12/2025 | Thompson Sampling |
| `core/ml/drift_detector.py` | ✅ DONE | 11/12/2025 | ADWIN detection |
| Intégration main.py (seuil dynamique) | ✅ DONE | 11/12/2025 | Via get_threshold_optimizer() |
| Intégration position_manager.py (feedback) | ✅ DONE | 11/12/2025 | Update après trade |
| `api/routes/ml_config.py` | ✅ DONE | 11/12/2025 | 6 endpoints API |
| Config toggles config.py | ✅ DONE | 11/12/2025 | threshold_optimizer_enabled, etc. |
| `MLConfigPanel.svelte` | ✅ DONE | 11/12/2025 | UI toggles + stats |
| **PHASE 2D COMPLETE** | ✅ | 11/12/2025 | - |

### Phase 2E: Filtres ML Stricts ✅
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Filtre LIVE uniquement | ✅ DONE | 11/12/2025 | `is_live_trade = true` |
| Filtre ATR mode uniquement | ✅ DONE | 11/12/2025 | `tp_sl_mode = 'ATR'` |
| Exclure MANUAL + STAGNATION | ✅ DONE | 11/12/2025 | `exit_reason NOT IN (...)` |
| Retirer filtre configs différentes | ✅ DONE | 11/12/2025 | Plus de données (548 trades) |
| API ml_trades_count mise à jour | ✅ DONE | 11/12/2025 | Nouveaux compteurs |
| Frontend MLCONTENT_GB_Variables | ✅ DONE | 11/12/2025 | 5 cartes stats |
| **PHASE 2E COMPLETE** | ✅ | 11/12/2025 | 548 trades ML utilisables |

### ⏸️ Pause Accumulation (200+ trades)
| Métrique | Objectif | Actuel | Status |
|----------|----------|--------|--------|
| Trades VOLATILE | 50+ | 6 | ⬜ |
| Trades NORMAL | 50+ | 82 | ✅ |
| Trades CALME | 30+ | 138 | ✅ |
| Trades CHOPPY | 30+ | 10 | ⬜ |

> **Note:** Ignorer trades avec `entry_market_regime = NULL` ou `UNKNOWN` (ancien code avant régime V2)

---

### 🆕 Phase 2F: Quick Wins - Gestion Sortie (RÉVISÉ - 14/12/2025)
> **Objectif:** Améliorer la rentabilité SANS réduire le nombre de trades
> **Principe:** Optimiser la GESTION des trades, pas leur FILTRAGE

| Tâche | Status | Priorité | Impact estimé | Trades |
|-------|--------|----------|---------------|--------|
| **✅ Stagnation Positive Exit** | ✅ DONE | 🔴 HAUTE | **+57% PnL** | ✅ Idem |
| **~~RSI Extreme Quick Exit~~** | ❌ TESTÉ | - | **-2.07% PnL** (dégrade) | ✅ Idem |
| **Trailing MFE Protection (sur SL)** | ⬜ TODO | 🔴 HAUTE | **+64% PnL** | ✅ Idem |
| **Drift detection sur features** | ⬜ TODO | 🟠 MOYENNE | Anticiper dégradation | ✅ Idem |
| ~~Gating US_OPEN~~ | ❌ EXCLU | - | - | ❌ Réduit trades |
| ~~Orderflow skip~~ | ❌ EXCLU | - | - | ❌ Réduit trades |

### 🆕 Phase 2G: ML Monitor + Rollback Dual (NOUVEAU - 14/12/2025)
> **Objectif:** Observabilité complète du système ML ("Glass Box")
> **Documentation:** `06_ML_MONITOR_MVP.md`, `07_ROLLBACK_DUAL_SYSTEM.md`, `08_DATA_BACKFILL_STRATEGY.md`

| Tâche | Status | Priorité | Description |
|-------|--------|----------|-------------|
| **Data Quality Checker** | ⬜ TODO | 🔴 HAUTE | Vérification cohérence backfill |
| **Rollback Manager** | ⬜ TODO | 🔴 HAUTE | Hard-Stop + Progressive dual system |
| **ML Monitor Backend** | ⬜ TODO | 🔴 HAUTE | API endpoints pour observabilité |
| **ML Monitor Frontend** | ⬜ TODO | 🔴 HAUTE | Nouvel onglet "ML Monitor" |
| **Smart Backfill Script** | ⬜ TODO | 🟠 MOYENNE | Backfill cohérent only |

---

### 🆕 Phase 2H: POST-EXIT ANALYSIS (INTÉGRÉ - 19/01/2026)
> **Objectif:** Optimiser params de sortie via analyse prix post-exit
> **Documentation:** `10_POST_EXIT_INTEGRATION.md`, `11_PROJECT_OVERVIEW_PERFORMANCE.md`

| Sous-Phase | Status | Durée | Prérequis | Description |
|------------|--------|-------|-----------|-------------|
| **2H.1: Data Collection** | ✅ DONE | - | Aucun | Tracking prix 5min post-exit |
| **2H.2: Metrics & Targets** | ⬜ TODO | 2h | 100+ trades | Calcul ml_optimal_* |
| **2H.3: ML Model Training** | ⬜ TODO | 4h | 500+ trades | Multi-output regressor |
| **2H.4: Live Integration** | ⬜ TODO | 3h | Phase 2H.3 | MLParamPredictor |
| **2H.5: Frontend Dashboard** | ⬜ TODO | 3h | Phase 2H.4 | PostExitAnalysis.svelte |

#### 2H.1: Data Collection ✅ TERMINÉE (19/01/2026)
**Fichiers créés:**
- `database/migrations/add_post_exit_analysis_tables.sql`
- `core/post_exit/tracker.py` (PostExitTracker dataclass)
- `core/post_exit/manager.py` (PostExitManager singleton)
- `core/callbacks/post_exit_loop.py` (Boucle prix 1Hz)

**Fichiers modifiés:**
- `core/position_manager.py:4643-4676` (Hook start_tracking)
- `main.py:585-592` (Startup post_exit_loop)
- `main.py:657-663` (Shutdown post_exit_loop)
- `main.py:3833-3868` (API endpoints)

**Tables SQL:**
- `trade_post_exit_analysis` (métriques agrégées)
- `trade_post_exit_samples` (données brutes 1Hz)

**API Endpoints:**
- `GET /api/post-exit/status` (statut système)
- `GET /api/post-exit/recent` (métriques récentes)

**Status:** ✅ Collecte automatique active depuis redémarrage

#### Impact attendu Phase 2H complète
| Métrique | Avant | Après 2H | Amélioration |
|----------|-------|----------|--------------|
| Exit Efficiency | 60% | 75% | +25% |
| Regret moyen | 0.8% | 0.3% | -62% |
| Winrate | 54% | 58% | +7% |
| Profit Factor | 1.6 | 1.8 | +12% |

#### Décisions Phase 2G (14/12/2025)

**1. Stratégie Backfill:**
- Backfill régime SEULEMENT si données cohérentes
- Critères: ATR dans plage régime, params SL/TP compatibles, MFE/MAE présents
- Trades incohérents: marqués `backfill_excluded=TRUE` (pas dans dataset ML)

**2. Rollback Dual System:**
- **Hard-Stop:** Drawdown >5%, Losing streak ≥5, PF <0.5, WR <25% → Rollback immédiat
- **Progressive:** Fenêtres 20/50/100 trades, hystérésis -15%/+10%, cooldown 30 trades
- **Regime-Aware:** Évaluation et rollback ciblé par régime

**3. ML Monitor MVP:**
- Nouvel onglet "ML Monitor" (sans toucher dashboard actuel)
- Sections: Data Health, Optimizer Status, Rollback Status, Drift Detection
- Refresh WebSocket 30s, alertes temps réel

#### 2F.1 Trailing MFE Protection (NOUVELLE PRIORITÉ)
```
Problème: 221 trades SL avaient MFE >= 0.05% avant de toucher SL
           PnL actuel: -29.48% → PnL potentiel: +34.37%

Solution:
- Activer Break-Even dès MFE >= 0.05%
- Ou Trailing plus agressif après MFE > seuil

Impact: +63.85% PnL récupérable
Trades: AUCUNE réduction (même trades, meilleure gestion)
```

#### 2F.2 Drift Detection Features (extension ADWIN) - CONSERVÉ
```
Actuellement: ADWIN sur PnL/WinRate (détecte APRÈS pertes)
Amélioration: ADWIN sur ATR/ADX/volume_ratio (détecte AVANT)

Logique:
- Si distribution ATR change → ajuster params (pas bloquer)
- Si ADX baisse → réduire TP/augmenter trailing (pas bloquer)

Impact: Adaptation dynamique des params
Trades: AUCUNE réduction
```

#### ❌ 2F.3 Gating/Filtrage - EXCLU
```
⚠️ EXCLU car réduit le nombre de trades:
- Gating US_OPEN: -243 trades
- Orderflow skip: -X trades
- Min score +2: -X trades

Alternative: Utiliser ces signaux pour AJUSTER les params
(TP plus court, SL plus serré, trailing plus agressif)
au lieu de BLOQUER les trades.
```

---

---

### 🆕 Phase 2I: ML Calibration EV (SIMPLIFIÉ - 6h au lieu de 15h)
> **Objectif:** Calibration basée sur Expected Value
> **Documentation:** `09_BRAINSTORMING_ML_CALIBRATION.md`, `13_PHASE_ANALYSIS_FIXE_MODE.md`

| Sous-Phase | Status | Durée | Description |
|------------|--------|-------|-------------|
| 2I.1: Migration SQL EV | ⬜ TODO | 2h | Colonnes EV dans trades |
| 2I.2: Model version tracking | ⬜ TODO | 3h | Versioning modèles |
| 2I.5: exit_reason filter | ⬜ TODO | 1h | Filtrage raisons exit |
| ❌ 2I.3: Simulated seeding | ❌ SUPPRIMÉ | - | ROI incertain, complexe |
| ❌ 2I.4: Gating EV-based | ❌ SUPPRIMÉ | - | Besoin 100+ trades/bucket |

**Économie:** -9h (-60% de la phase)

---

### ⏸️ Phase 3A: Mixture-of-Experts par Régime (REPORTER)
> **Objectif:** Un modèle ML par régime, activé seulement si assez de données
> **Status:** ⏸️ REPORTER - Pas assez de trades VOLATILE (6) et CHOPPY (10)

| Tâche | Status | Prérequis |
|-------|--------|-----------|
| Architecture gating (seuil trades par régime) | ⏸️ REPORTER | - |
| Model CALME (si 50+ trades) | ⏸️ REPORTER | 50 trades CALME (✅ 138 OK) |
| Model NORMAL (si 50+ trades) | ⏸️ REPORTER | 50 trades NORMAL (✅ 82 OK) |
| Model VOLATILE (si 50+ trades) | ⏸️ REPORTER | 50 trades VOLATILE (❌ 6 insuffisant) |
| Model CHOPPY (si 50+ trades) | ⏸️ REPORTER | 50 trades CHOPPY (❌ 10 insuffisant) |
| Fallback rule-based si pas assez de données | ⏸️ REPORTER | - |

**Réactivation:** Après accumulation 500+ trades (dont 50+ VOLATILE et 50+ CHOPPY)

#### Architecture
```
┌─────────────────────────────────────────────────────────┐
│                      GATING LOGIC                        │
│  if trades_count[regime] >= MIN_THRESHOLD (50):         │
│      → use ML model for this regime                     │
│  else:                                                  │
│      → use rule-based (current logic)                   │
└─────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ Model CALME   │  │ Model NORMAL  │  │ Model VOLATILE│
│ (138 trades ✅)│  │ (82 trades ✅) │  │ (6 trades ❌) │
└───────────────┘  └───────────────┘  └───────────────┘
```

**Avantages:**
- Chaque modèle apprend les patterns spécifiques à son contexte
- Pas de contamination entre régimes
- Activation progressive (dès qu'un régime a 50+ trades)

---

### Phase 3B: Ensemble Learning (RENOMMÉ - ancienne Phase 3)
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| LightGBM Trainer | ✅ DONE | 11/12/2025 | `optimization/models/lightgbm_trainer.py` |
| Fix model_logger.py | ✅ DONE | 11/12/2025 | RealDictCursor pour PostgreSQL |
| Fix postgresql_datalogger.py | ✅ DONE | 11/12/2025 | Param cursor_factory rétrocompatible |
| Multi-Model Voting | ⬜ TODO | - | GB + XGBoost + LightGBM |
| Stacking Meta-Model | ⬜ TODO | - | Combine prédictions |
| Confidence Calibration | ⬜ TODO | - | Platt Scaling / Isotonic |
| **PHASE 3B COMPLETE** | ⏸️ PAUSÉ | - | En attente accumulation trades |

### Phase 3C: Feature Engineering Avancé (21 features) - RENOMMÉ (ancienne Phase 4)
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Lag Features (1-3 trades) | ⬜ TODO | - | 6 features: pnl + win/loss |
| Rolling Windows (5+10) | ⬜ TODO | - | 6 features: winrate, avg, std |
| BTC Features (MEXC) | ⬜ TODO | - | 4 features: price, trend, ma20 |
| Funding Rate (Binance) | ⬜ TODO | - | 1 feature: public API |
| Sentiment (F&G + L/S) | ⬜ TODO | - | 2 features: alternative.me + Bybit |
| Order Flow cumulatifs | ⬜ TODO | - | 2 features: delta_10, trend_5 |
| **PHASE 3C COMPLETE** | ⬜ | - | 21 nouvelles features |

### ❌ Phase 4: Séquences Temporelles (SUPPRIMÉ DU SCOPE)
> **Raison:** Prérequis 1000+ trades non atteints, complexité élevée, ROI incertain
> **Documentation:** `13_PHASE_ANALYSIS_FIXE_MODE.md`

| Tâche | Status | Notes |
|-------|--------|-------|
| GRU Séquences 10-20 scans | ❌ SUPPRIMÉ | Prérequis: 1000+ trades |
| Transformer Attention | ❌ SUPPRIMÉ | Deep Learning complexe |

**Réévaluation:** Après 1000+ trades et stabilisation Phases 2H-3C

---

### ❌ Phase 5: Reinforcement Learning (SUPPRIMÉ DU SCOPE)
> **Raison:** Trop complexe, ROI très incertain, besoin GPU + expertise RL
> **Documentation:** `13_PHASE_ANALYSIS_FIXE_MODE.md`

| Tâche | Status | Notes |
|-------|--------|-------|
| Environment Simulation | ❌ SUPPRIMÉ | Besoin simulateur fiable |
| Agent PPO | ❌ SUPPRIMÉ | Expertise RL requise |
| Reward Shaping | ❌ SUPPRIMÉ | Complexité élevée |

**Décision:** SUPPRIMÉ DÉFINITIVEMENT du scope Mode FIXE

---

### ⏸️ Phase 6: MLOps & Production (REPORTER)
> **Raison:** Système pas encore stable, prématuré
> **Documentation:** `13_PHASE_ANALYSIS_FIXE_MODE.md`

| Tâche | Status | Notes |
|-------|--------|-------|
| Auto-Retrain hebdomadaire | ⏸️ REPORTER | Après Phase 2H complète |
| A/B Testing modèles | ⏸️ REPORTER | Besoin infrastructure |
| Model Registry (MLflow) | ⏸️ REPORTER | Après 6+ mois production |
| Monitoring & Alertes | ⏸️ REPORTER | Après stabilisation |

**Réactivation:** Après Phase 3C + 6 mois production stable

---

## 📊 MÉTRIQUES DE SUIVI

### Performance Actuelle (14/12/2025)
| Métrique | Valeur | 7 derniers jours | Objectif |
|----------|--------|------------------|----------|
| Win Rate | 44.8% | 47.2% | 52%+ |
| PnL Total | +226% | -14% ⚠️ | Positif |
| Avg PnL/trade | +0.098% | -0.026% ⚠️ | +0.15% |
| Trades | 2,311 | 540 | **Maintenir** |

### Contrainte Majeure
| Règle | Description |
|-------|-------------|
| **⚠️ AUCUNE réduction du nombre de trades** | Les optimisations doivent améliorer la GESTION, pas le FILTRAGE |

### Données Accumulées
| Table | Trades | Avec Session | Avec What-If | Avec Params |
|-------|--------|--------------|--------------|-------------|
| trade_atr_metrics | ? | 0% | 0% | 0% |
| market_regime_history | ? | 0% | - | - |
| scan_logs | ? | 0% | - | - |

---

## 🔧 FICHIERS MODIFIÉS/CRÉÉS

### Phase 1.3a (Sprint 3) - COMPLÉTÉE ✅
- [x] `core/position_manager.py` - Calcul régime LOCAL + adaptation params
- [x] `core/position/trailing_stop.py` - Support `custom_distance_pct`
- [x] `utils/effective_config.py` - `set_local_trade_adjustments()`
- [x] `main.py` - Fix toggle flags CB + reset à désactivation
- [x] `verification/verify_adaptive_behavior.py` - Script test régime LOCAL
- [x] `verification/verify_toggle_flags.py` - Script test toggles

### Phase 0 ✅
- [x] `database/migrations/add_regime_context_columns.sql` - 35 colonnes + 4 vues
- [x] `utils/session_detector.py` - 8 sessions (ASIA, EUROPE_OPEN, etc.)
- [x] `config.py` (section MARKET_REGIME_V2_CONFIG) - Toggles OFF par défaut
- [x] `config_overrides.json` - 11 nouveaux toggles V2
- [x] `verification/run_regime_v2_migration.py` - Script de migration

### Phase 1A ✅
- [x] `core/postgresql_datalogger.py` - log_trade_atr_metrics + _batch_insert_scans enrichis
- [x] `core/market_regime_selector.py` - _log_regime_change_to_db enrichi
- [x] `verification/verify_phase1a_logging.py` - Script vérification

### Phase 1B ✅
- [x] `core/market_regime_selector.py` - 4 méthodes V2 (calculate_atr_metric, apply_smoothing, should_change_regime, calculate_combined_atr)
- [x] `verification/verify_phase1b_v2_methods.py` - Script vérification

### Phase 1C ✅
- [x] `core/analysis/what_if_simulator.py` - simulate_regime_scenarios() + update_regime_whatif()
- [x] `verification/backfill_regime_whatif.py` - Script backfill

### Phase 1D ✅
- [x] `frontend/src/lib/components/VariablesPanel.svelte` - Nouvel onglet "Régime V2" avec 7 toggles

### Phase 2
- [ ] `core/analysis/correlation_engine.py`
- [ ] `core/analysis/regime_optimizer.py`
- [ ] `core/analysis/ml_param_optimizer.py`
- [ ] `frontend/.../RegimeAnalyticsDashboard.svelte`
- [ ] `api/regime_analytics.py`

### Phase 3 (Ensemble Learning) - EN COURS
- [x] `optimization/models/lightgbm_trainer.py` - LightGBM avec split temporel + calibration
- [x] `optimization/models/model_logger.py` - Fix RealDictCursor pour PostgreSQL
- [x] `core/postgresql_datalogger.py` - Param cursor_factory (rétrocompatible)
- [x] `verification/verify_lightgbm.py` - Script de test
- [ ] Multi-Model Voting (GB + XGBoost + LightGBM)
- [ ] Stacking Meta-Model
- [ ] Confidence Calibration

### Phase 4 (Feature Engineering)
- [ ] `optimization/data/feature_engineering_v2.py` - 21 nouvelles features
- [ ] `core/data/btc_data_fetcher.py` - BTC depuis MEXC
- [ ] `core/data/market_sentiment.py` - F&G + Funding + L/S Ratio
- [ ] Modifier `optimization/data/feature_loader.py`

---

## 📝 NOTES DE DÉVELOPPEMENT

### 19/12/2025 - ML Profitability: feature parity GB + analyse EV (Option B)
 
 - ✅ Fix feature parity (live): `optimization/predictor_optimized.py` calcule les features dérivées manquantes si les inputs bruts sont présents (évite remplissage à zéro).
 - ✅ Script EV/thresholds: `scripts/analyze_ml_thresholds.py` calcule WinRate + EV (avg `net_pnl_pct`) + PnL net (`net_pnl_usdt`) par seuil et buckets de `ml_confidence`, avec split temporel train/test.
 - ⚠️ Contrainte trades: si on utilise ces résultats pour ajuster `gb_min_confidence`, privilégier un seuil sous contrainte de conservation (ex: >=90% trades) ou usage en monitoring/sizing.
 - ⚠️ ThresholdOptimizer: la distribution de `ml_confidence` peut changer après le fix → surveiller `data/ml/threshold_optimizer_state.json` et reset si nécessaire.

### 11/12/2025 21:15 - Phase 3 démarrée puis PAUSÉE
 **Accumulation trades en cours - Phase 3 en attente**

 **Travail effectué:**
- ✅ Créé `optimization/models/lightgbm_trainer.py` - LightGBM aligné avec XGBoost V2.1
  - Split temporel, filtrage qualité, calibration probabilités
  - Intégration Optuna, logging PostgreSQL
- ✅ Installé package `lightgbm` (4.6.0)
- ✅ Corrigé `optimization/models/model_logger.py` - ajout RealDictCursor
- ✅ Corrigé `core/postgresql_datalogger.py` - param cursor_factory (rétrocompatible)
- ✅ Créé `verification/verify_lightgbm.py` - script de test
- ✅ Vérifié que LightGBM fonctionne correctement

**⚠️ AUCUNE PERTURBATION DU BOT:**
- Tous les fichiers créés/modifiés sont rétrocompatibles
- Le bot continue de fonctionner normalement pendant l'accumulation

**Pour reprendre Phase 3:**
1. Lire ce tracker
2. Prochaine étape: `Voting Classifier (GB + XGBoost + LightGBM)`
3. Fichier existant à utiliser comme base: `optimization/models/train_enhanced.py` (contient déjà un ensemble XGB+LGBM)
4. Objectif: combiner 3 modèles avec Voting soft + Stacking

---

### 11/12/2025 19:30 - Filtres ML Stricts (Phase 2E)
**Nouveaux critères de filtrage pour l'entraînement ML**

- ✅ Uniquement trades LIVE (`is_live_trade = true`)
- ✅ Uniquement mode TP/SL ATR (`tp_sl_mode = 'ATR'`)
- ✅ Exclure exits MANUAL et STAGNATION
- ✅ Retrait du filtre "configs différentes" (trop restrictif)
- ✅ Résultat: **548 trades ML utilisables** (vs 137 avant)

**Fichiers modifiés:**
- `optimization/data/feature_loader.py` - build_config_filter_conditions()
- `api/routes/ml_dashboard.py` - Nouveaux compteurs
- `frontend/.../MLCONTENT_GB_Variables.svelte` - 5 cartes stats

**Breakdown trades:**
| Étape | Trades |
|-------|--------|
| Total | 4,513 |
| - Dry-run exclus | -2,280 |
| - Non-ATR exclus | -1,141 |
| - MANUAL/STAGNATION | -544 |
| **= ML utilisables** | **548** |

### 10/12/2025 19:00 - Phase 1.3a COMPLÉTÉE (Sprint 3)
**Régime LOCAL par trade implémenté et vérifié**

- ✅ Calcul régime LOCAL (LOW/MEDIUM/HIGH) basé sur ATR% du trade
- ✅ Adaptation paramètres TP/SL/BE/Trailing selon régime
- ✅ Stockage `effective_config` dans Position pour chaque trade
- ✅ Logging complet dans `trade_atr_metrics` (colonnes param_*)
- ✅ Script vérification `verify_adaptive_behavior.py`
- ✅ Correction bug toggle flags (CB désactivé mais actif)
- ✅ Analyse performance: LOW 52% WR, MEDIUM 15% WR → ajustement agressif

**Paramètres MEDIUM ajustés (19:00):**
- TP: ×0.8 → ×0.6 (plus court)
- SL: ×1.0 → ×0.8 (plus serré)
- BE: ×0.8 → ×0.5 (très tôt)
- Trailing: ×0.9 → ×0.6 (trigger tôt)
- Stagnation: ×1.0 → ×0.7 (timeout court)

### 10/12/2025 00:24 - Planification
- Création de la documentation complète
- 10 documents créés
- Structure phases définitive
- 34 paramètres identifiés pour optimisation par régime

---

## 🚨 PROBLÈMES RENCONTRÉS

| Date | Problème | Solution | Status |
|------|----------|----------|--------|
| 14/12/2025 | SL_EXCHANGE détecté incorrectement (4/8 trades) | Vérifier si prix atteint SL MEXC + récupérer vrai prix fill | ✅ CORRIGÉ |

---

## 💡 IDÉES FUTURES

- [ ] Ajouter BTC correlation dans features régime
- [ ] Dashboard temps réel WebSocket
- [ ] Alertes Telegram sur changement régime
- [ ] A/B testing automatique des configs
- [ ] Backtesting What-If sur historique complet

---

## 🔧 DETTE TECHNIQUE

### Coverage Tests (Actuel: 30.95%)
| Fichier | Coverage | Priorité | Notes |
|---------|----------|----------|-------|
| `core/analyzer.py` | 3.6% | 🔴 HAUTE | Cœur du système, logique critique |
| `core/scanner_loop.py` | 6% | 🔴 HAUTE | Boucle principale |
| `core/position_manager.py` | 12% | 🟠 MOYENNE | Amélioré récemment |
| `core/postgresql_datalogger.py` | 4% | 🟠 MOYENNE | Logging critique |
| `api/live_trading_endpoints.py` | 10% | 🟡 BASSE | Endpoints API |

**Objectif:** Atteindre 50% coverage sur les fichiers `core/` critiques.

**Approche pour nouveau code:**
- Test-First ou Test-Strict pour chaque nouvelle fonctionnalité
- Chaque fichier `utils/session_detector.py` → `tests/test_session_detector.py`

---

## 📋 POUR REPRENDRE LE TRAVAIL

1. **Lire ce fichier** pour connaître l'état actuel
2. **Vérifier la phase en cours** dans les tableaux ci-dessus
3. **Consulter le document de phase** correspondant pour les détails
4. **Mettre à jour ce tracker** après chaque avancée

---

**⚠️ IMPORTANT:** Mettre à jour ce document après chaque session de travail!

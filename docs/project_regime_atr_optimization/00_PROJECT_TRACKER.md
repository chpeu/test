# 📊 PROJECT TRACKER - REGIME & ATR OPTIMIZATION
## Document de Suivi Central

> **Dernière mise à jour:** 11/12/2025 21:15
> **Status global:** ✅ PHASES 1-2E COMPLÈTES | Phase 3 démarrée (LightGBM prêt)
> **Phase actuelle:** ⏸️ PAUSE ACCUMULATION - Phase 3 en attente

---

## 🎯 OBJECTIF DU PROJET

Créer un système d'optimisation intelligent qui:
1. **Détecte** le régime de marché (CALME/NORMAL/VOLATILE/CHOPPY) de manière fiable
2. **Adapte** automatiquement 34+ paramètres de trading selon le régime
3. **Optimise** ces paramètres via ML basé sur les données historiques
4. **Applique** les optimisations automatiquement avec rollback de sécurité

---

## 📁 STRUCTURE DU DOSSIER

```
docs/project_regime_atr_optimization/
│
├── 00_PROJECT_TRACKER.md          ← CE FICHIER (suivi central)
│
├── 01_SYNTHESE_COMPLETE.md        ← Vue complète du projet
├── 02_MASTER_PLAN.md              ← Roadmap des phases
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

### ⏸️ Pause Accumulation (50+ trades)
| Métrique | Objectif | Actuel | Status |
|----------|----------|--------|--------|
| Trades avec session_market | 50+ | 75 | ✅ |
| Trades avec What-If régime | 50+ | 56 | ✅ |
| Nouveaux trades post-Phase 1D | 50+ | 0 | ⏳ EN COURS |

**Paramètres Accumulation (11/12/2025):**
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
| Trades VOLATILE | 50+ | 0 | ⬜ |
| Trades NORMAL | 50+ | 0 | ⬜ |
| Trades CALME | 30+ | 0 | ⬜ |

### Phase 3: Ensemble Learning (EN COURS - PAUSÉ)
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| LightGBM Trainer | ✅ DONE | 11/12/2025 | `optimization/models/lightgbm_trainer.py` |
| Fix model_logger.py | ✅ DONE | 11/12/2025 | RealDictCursor pour PostgreSQL |
| Fix postgresql_datalogger.py | ✅ DONE | 11/12/2025 | Param cursor_factory rétrocompatible |
| Multi-Model Voting | ⬜ TODO | - | GB + XGBoost + LightGBM |
| Stacking Meta-Model | ⬜ TODO | - | Combine prédictions |
| Confidence Calibration | ⬜ TODO | - | Platt Scaling / Isotonic |
| **PHASE 3 COMPLETE** | ⏸️ PAUSÉ | - | En attente accumulation trades |

### Phase 4: Feature Engineering Avancé (21 features) - PLANIFIÉ
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Lag Features (1-3 trades) | ⬜ TODO | - | 6 features: pnl + win/loss |
| Rolling Windows (5+10) | ⬜ TODO | - | 6 features: winrate, avg, std |
| BTC Features (MEXC) | ⬜ TODO | - | 4 features: price, trend, ma20 |
| Funding Rate (Binance) | ⬜ TODO | - | 1 feature: public API |
| Sentiment (F&G + L/S) | ⬜ TODO | - | 2 features: alternative.me + Bybit |
| Order Flow cumulatifs | ⬜ TODO | - | 2 features: delta_10, trend_5 |
| **PHASE 4 COMPLETE** | ⬜ | - | 21 nouvelles features |

### Phase 5: Séquences Temporelles (GRU/LSTM)
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| GRU Séquences 10-20 scans | ⬜ TODO | - | River ou PyTorch |
| Transformer Attention | ⬜ TODO | - | Multi-timeframe |
| **PHASE 5 COMPLETE** | ⬜ | - | Prérequis: 1000+ trades |

### Phase 6: Reinforcement Learning (PPO)
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Environment Simulation | ⬜ TODO | - | Gym-like trading env |
| Agent PPO | ⬜ TODO | - | Entrée + gestion position |
| Reward Shaping | ⬜ TODO | - | Optimiser Sharpe, pas PnL |
| **PHASE 6 COMPLETE** | ⬜ | - | Prérequis: GPU + 1000+ trades |

### Phase 7: MLOps & Production
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Auto-Retrain hebdomadaire | ⬜ TODO | - | Si drift détecté |
| A/B Testing modèles | ⬜ TODO | - | Comparaison parallèle |
| Model Registry (MLflow) | ⬜ TODO | - | Versioning modèles |
| Monitoring & Alertes | ⬜ TODO | - | Si performance dégradée |
| **PHASE 7 COMPLETE** | ⬜ | - | - |

---

## 📊 MÉTRIQUES DE SUIVI

### Performance Actuelle
| Métrique | Valeur | Tendance | Objectif Final |
|----------|--------|----------|----------------|
| Win Rate | ~48% | - | 60% |
| Profit Factor | ~1.35 | - | 2.0 |
| Max Drawdown | ~4.5% | - | 2.0% |
| Flip-Flop/jour | ~8 | - | 0.5 |
| Précision Régime | ~50% | - | 85% |

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
| - | - | - | - |

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

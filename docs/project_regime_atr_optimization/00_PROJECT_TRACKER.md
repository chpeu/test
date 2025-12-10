# 📊 PROJECT TRACKER - REGIME & ATR OPTIMIZATION
## Document de Suivi Central

> **Dernière mise à jour:** 10/12/2025 19:15
> **Status global:** 🚀 PHASE 1.3a COMPLÉTÉE (Local Regime Adaptation)
> **Phase actuelle:** Phase 1.3a terminée, accumulation données en cours

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

### Phase 0: Infrastructure
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Migration SQL (35 colonnes) | ⬜ TODO | - | - |
| session_detector.py | ⬜ TODO | - | - |
| Config MARKET_REGIME_V2_CONFIG | ⬜ TODO | - | - |
| config_overrides.json toggles | ⬜ TODO | - | - |
| Script migration | ⬜ TODO | - | - |
| **PHASE 0 COMPLETE** | ⬜ | - | - |

### Phase 1A: Logging Contextuel
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Logger session/hour dans trade_atr_metrics | ⬜ TODO | - | - |
| Logger params utilisés (8 colonnes) | ⬜ TODO | - | - |
| Bitmask patterns | ⬜ TODO | - | - |
| Vérification 1 trade loggé | ⬜ TODO | - | - |
| **PHASE 1A COMPLETE** | ⬜ | - | - |

### Phase 1B: Régime V2 Quick Wins
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| calculate_atr_metric() (médiane) | ⬜ TODO | - | - |
| should_change_regime() (hystérésis) | ⬜ TODO | - | - |
| apply_smoothing() (EMA) | ⬜ TODO | - | - |
| calculate_combined_atr() (1m+5m) | ⬜ TODO | - | - |
| get_session_adjusted_thresholds() | ⬜ TODO | - | - |
| check_regime_v2() | ⬜ TODO | - | - |
| Frontend toggles | ⬜ TODO | - | - |
| **PHASE 1B COMPLETE** | ⬜ | - | - |

### Phase 1C: What-If Régime
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| simulate_regime_scenarios() (4 régimes) | ⬜ TODO | - | - |
| Intégration position_manager | ⬜ TODO | - | - |
| Backfill trades existants | ⬜ TODO | - | - |
| **PHASE 1C COMPLETE** | ⬜ | - | - |

### Phase 1D: Intégration Composants
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| analyzer.py → get_active_config() | ⬜ TODO | - | - |
| position_manager → calculate_sl_tp_from_regime() | ⬜ TODO | - | - |
| SL MEXC lié au régime | ⬜ TODO | - | - |
| GB features régime | ⬜ TODO | - | - |
| **PHASE 1D COMPLETE** | ⬜ | - | - |

### ⏸️ Pause Accumulation (50+ trades)
| Métrique | Objectif | Actuel | Status |
|----------|----------|--------|--------|
| Trades avec session_market | 50+ | 0 | ⬜ |
| Trades avec What-If régime | 50+ | 0 | ⬜ |

### Phase 2A: Analyse Corrélations
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| correlation_engine.py | ⬜ TODO | - | - |
| Script analyse | ⬜ TODO | - | - |
| **PHASE 2A COMPLETE** | ⬜ | - | - |

### Phase 2B: Dashboard
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| RegimeAnalyticsDashboard.svelte | ⬜ TODO | - | - |
| API endpoints | ⬜ TODO | - | - |
| **PHASE 2B COMPLETE** | ⬜ | - | - |

### Phase 2C: Optimizer Suggestions
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| regime_optimizer.py | ⬜ TODO | - | - |
| API suggestions | ⬜ TODO | - | - |
| **PHASE 2C COMPLETE** | ⬜ | - | - |

### Phase 2D: ML Param Optimizer
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Feature importance | ⬜ TODO | - | - |
| Grid search | ⬜ TODO | - | - |
| Cross-validation | ⬜ TODO | - | - |
| 4 configs générées | ⬜ TODO | - | - |
| **PHASE 2D COMPLETE** | ⬜ | - | - |

### ⏸️ Pause Accumulation (200+ trades)
| Métrique | Objectif | Actuel | Status |
|----------|----------|--------|--------|
| Trades VOLATILE | 50+ | 0 | ⬜ |
| Trades NORMAL | 50+ | 0 | ⬜ |
| Trades CALME | 30+ | 0 | ⬜ |

### Phase 3A: ML Regime Detector
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| regime_classifier.py | TODO | - | - |
| Training | TODO | - | - |
| Accuracy > 70% | TODO | - | - |
| **PHASE 3A COMPLETE** | TODO | - | - |

### Phase 3B: GB Feature Integration
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Feature Engineering: ml_features | TODO | - | - |
| Retraining pipeline | TODO | - | - |
| **PHASE 3B COMPLETE** | TODO | - | - |

### Phase 3B+: Context-Aware Entry Model (NOUVEAU)
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Ajout `market_regime_index` features | TODO | - | - |
| Support features catégorielles Trainer | TODO | - | - |
| Calibration contextuelle par régime | TODO | - | - |
| Réentraînement modèle unique enrichi | TODO | - | - |
| **PHASE 3B+ COMPLETE** | TODO | - | - |

### Phase 3C: Auto-Apply & Rollback
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| auto_apply_engine.py | TODO | - | - |
| rollback_manager.py | TODO | - | - |
| Tests validation | TODO | - | - |
| **PHASE 3C COMPLETE** | TODO | - | - |
| **PHASE 3C COMPLETE** | ⬜ | - | - |

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

### Phase 0
- [ ] `database/migrations/add_regime_v2_columns.sql`
- [ ] `utils/session_detector.py`
- [ ] `config.py` (section MARKET_REGIME_V2_CONFIG)
- [ ] `config_overrides.json`
- [ ] `verification/run_migration.py`

### Phase 1
- [ ] `core/postgresql_datalogger.py`
- [ ] `core/market_regime_selector.py`
- [ ] `core/analysis/what_if_simulator.py`
- [ ] `core/position_manager.py`
- [ ] `core/analyzer.py`
- [ ] `frontend/.../VariablesPanel.svelte`

### Phase 2
- [ ] `core/analysis/correlation_engine.py`
- [ ] `core/analysis/regime_optimizer.py`
- [ ] `core/analysis/ml_param_optimizer.py`
- [ ] `frontend/.../RegimeAnalyticsDashboard.svelte`
- [ ] `api/regime_analytics.py`

### Phase 3
- [ ] `core/ml/regime_classifier.py`
- [ ] `ml/feature_loader.py`
- [ ] `core/analysis/auto_apply_engine.py`
- [ ] `core/analysis/rollback_manager.py`

---

## 📝 NOTES DE DÉVELOPPEMENT

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

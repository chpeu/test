# 📊 PROJECT TRACKER - REGIME & ATR OPTIMIZATION
## Document de Suivi Central

> **Dernière mise à jour:** 10/12/2025 00:24
> **Status global:** 📝 PLANIFICATION FINALISÉE
> **Phase actuelle:** Phase 0 (Prêt à démarrer)

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
| regime_classifier.py | ⬜ TODO | - | - |
| Training | ⬜ TODO | - | - |
| Accuracy > 70% | ⬜ TODO | - | - |
| **PHASE 3A COMPLETE** | ⬜ | - | - |

### Phase 3B: GB Integration
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| Features régime ajoutées | ⬜ TODO | - | - |
| Réentraînement GB | ⬜ TODO | - | - |
| **PHASE 3B COMPLETE** | ⬜ | - | - |

### Phase 3C: Auto-Apply & Rollback
| Tâche | Status | Date | Notes |
|-------|--------|------|-------|
| auto_apply_engine.py | ⬜ TODO | - | - |
| rollback_manager.py | ⬜ TODO | - | - |
| Tests validation | ⬜ TODO | - | - |
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

### 10/12/2025 - Planification
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

## 📋 POUR REPRENDRE LE TRAVAIL

1. **Lire ce fichier** pour connaître l'état actuel
2. **Vérifier la phase en cours** dans les tableaux ci-dessus
3. **Consulter le document de phase** correspondant pour les détails
4. **Mettre à jour ce tracker** après chaque avancée

---

**⚠️ IMPORTANT:** Mettre à jour ce document après chaque session de travail!

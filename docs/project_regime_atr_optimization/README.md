# 🎯 PROJECT: REGIME & ATR OPTIMIZATION

> **Objectif:** Système intelligent d'optimisation des paramètres de trading par régime de marché

---

## 📁 STRUCTURE DU DOSSIER

```
project_regime_atr_optimization/
│
├── README.md                      ← CE FICHIER
├── 00_PROJECT_TRACKER.md          ← 📊 SUIVI CENTRAL (à mettre à jour)
│
├── 01_SYNTHESE_COMPLETE.md        ← Vue complète du projet
├── 02_MASTER_PLAN.md              ← Roadmap des phases
├── 03_ML_UNIFIED_ARCHITECTURE.md  ← Architecture ML unifiée (Phase 2D+3)
├── 04_UI_FRONTEND_SPECS.md        ← Spécifications UI frontend
├── 05_STAGNATION_POSITIVE_EXIT.md ← Spec sortie stagnation positive
├── 06_ML_MONITOR_MVP.md           ← 🆕 Spec nouvel onglet "ML Monitor"
├── 07_ROLLBACK_DUAL_SYSTEM.md     ← 🆕 Spec rollback Hard-Stop + Progressive
├── 08_DATA_BACKFILL_STRATEGY.md   ← 🆕 Stratégie backfill cohérent
│
├── phases/                        ← Détails d'implémentation par phase
│   ├── PHASE_0_INFRASTRUCTURE.md
│   ├── PHASE_1_IMPLEMENTATION.md
│   ├── PHASE_2_3_ANALYSIS_ML.md
│   └── PHASE_2D_ML_PARAMETER_OPTIMIZER.md
│
├── architecture/                  ← Architecture technique
│   ├── INTERACTIONS_REGIME_PARAMS.md
│   └── PLAN_MARKET_REGIME_OPTIMIZATION.md
│
└── reference/                     ← Documents de référence originaux
    ├── ATR_OPTIMIZATION_NEXT_STEPS.md
    └── BRAINSTORM_ATR_OPTIMIZATION.md
```

---

## 🚀 QUICK START

### Pour reprendre le travail:
1. **Ouvrir** `00_PROJECT_TRACKER.md` - Voir l'état actuel
2. **Identifier** la phase en cours
3. **Consulter** le document de phase correspondant dans `phases/`
4. **Mettre à jour** le tracker après chaque avancée

### Pour comprendre le projet:
1. **Lire** `01_SYNTHESE_COMPLETE.md` - Vue d'ensemble
2. **Consulter** `02_MASTER_PLAN.md` - Timeline et objectifs

### Pour implémenter:
1. **Suivre** les documents dans `phases/` dans l'ordre
2. **Vérifier** `architecture/` pour les interactions entre composants

---

## 📊 PHASES DU PROJET

| Phase | Description | Status | Durée |
|-------|-------------|--------|-------|
| **0** | Infrastructure (SQL, Config, Helpers) | ✅ DONE | 2h |
| **1A** | Logging Contextuel | ✅ DONE | 3h |
| **1B** | Régime V2 Quick Wins | ✅ DONE | 4h |
| **1C** | What-If Régime | ✅ DONE | 3h |
| **1D** | Intégration Composants (Frontend) | ✅ DONE | 4h |
| **1E** | Auto-Calibration + BTC Indicator | ✅ DONE | ~6h |
| ⏸️ | *Accumulation 50+ trades* | ✅ DONE | ~1 sem |
| **2A** | Analyse Corrélations | ✅ DONE | 4h |
| **2B** | Dashboard Monitoring | ✅ DONE | 6h |
| **2C** | Optimizer Suggestions | 🗑️ SUPPRIMÉ | - |
| **2D** | ML Auto-Adaptation (Threshold + Drift) | ✅ DONE | 10h |
| **2E** | Filtres ML Stricts (dataset training) | ✅ DONE | ~2h |
| **2F** | Quick Wins Gestion Sortie | ✅ PARTIEL | ~4h |
| **2G** | ML Monitor + Rollback Dual | 📋 SPÉCIFIÉ | ~8h |
| ⏸️ | *Accumulation 200+ trades* | ⏳ EN COURS | ~2 sem |
| **3A** | ML Regime Detector | ⬜ TODO | 8h |
| **3B** | GB Feature Integration | ⬜ TODO | 4h |
| **3C** | Auto-Apply & Rollback | ⬜ TODO | 8h |

**Total estimé:** ~80h sur 6-8 semaines

---

## 🎯 OBJECTIFS MÉTRIQUES

| Métrique | Actuel | Objectif |
|----------|--------|----------|
| Win Rate | ~48% | 60% |
| Profit Factor | ~1.35 | 2.0 |
| Max Drawdown | ~4.5% | 2.0% |
| Précision Régime | ~50% | 85% |
| Params optimisables | 10 | 34 |

---

## ⚠️ PRINCIPE CARDINAL

```
🔄 BOT TOUJOURS RUNNING - Accumulation continue de données
```

- Tous les toggles OFF par défaut
- Activation progressive feature par feature
- Rollback possible à tout moment
- Pas de reboot pour tester

---

## 📝 MISE À JOUR

Après chaque session de travail:
1. Mettre à jour `00_PROJECT_TRACKER.md`
2. Cocher les tâches complétées
3. Noter les problèmes rencontrés
4. Ajouter les métriques actuelles

---

## ✅ VÉRIFICATION RAPIDE (runtime)

Scripts:

1. `python verification\verify_runtime_loop.py --loops 1 --interval 1`
2. `python verification\verify_phase1b_v2_methods.py`
3. `python verification\verify_phase2d_integration.py`

---

## 🧪 ANALYSE ML (EV net / seuil `gb_min_confidence`)

 Objectif: analyser la **rentabilité réelle (EV net)** par `ml_confidence` et identifier un seuil robuste (split temporel train/test).

 Commandes:

 1. `python scripts\analyze_ml_thresholds.py --days 180 --test-ratio 0.30 --step 5`
 2. (option) `python scripts\analyze_ml_thresholds.py --days 365 --test-ratio 0.30 --step 5 --no-training-filter`

 Sorties principales:
 - **Meilleurs seuils** (optimisés sur TRAIN, reportés sur TEST)
 - **Table TEST** par seuil (EV%, PF, PnL net)
 - **Buckets 5%** (EV net par tranche de `ml_confidence`)

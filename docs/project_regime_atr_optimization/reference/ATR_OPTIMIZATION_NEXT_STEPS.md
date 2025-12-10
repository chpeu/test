# ATR Optimization - Prochaines Étapes

> **Document créé:** 09/12/2025
> **Dernière mise à jour:** 10/12/2025 19:15
> **Status actuel:** Phase 1.3a complétée, paramètres MEDIUM ajustés agressivement

---

## 📊 État Actuel du Système

### Composants Implémentés ✅

| Composant | Description | Status |
|-----------|-------------|--------|
| `trailing_distance_atr_mult` | Nouveau paramètre distance trailing | ✅ Opérationnel |
| Table `trade_atr_metrics` | 55 colonnes de métriques | ✅ Créée |
| Logger enrichi | Capture automatique à chaque trade | ✅ Actif |
| Context Tagging | Volatility/Trend state + ADX | ✅ 100% rempli |
| WhatIfSimulator | Calcul scénarios alternatifs | ✅ Fonctionnel |
| Backfill script | Remplissage trades existants | ✅ Disponible |
| Local Adaptation | Ajustement dynamique par trade (Sprint 3) | ✅ Validé |

### Phase 1.3a: Local Trade Adaptation (Sprint 3) ✅
**Objectif:** Appliquer dynamiquement des paramètres ATR adaptés au régime de volatilité local à l'ouverture du trade, sans modifier les sliders globaux.

**Réalisations:**
- **Adaptation Locale:** `PositionManager` calcule le régime (LOW/MEDIUM/HIGH) à l'ouverture.
- **Paramètres Adaptatifs:**

| Régime | ATR% | TP | SL | BE | Trail Trigger | Trail Dist | Stag Timeout |
|--------|------|-----|-----|-----|---------------|------------|--------------|
| **LOW** | < 0.2% | ×1.0 | ×1.0 | ×1.0 | ×1.0 | ×1.0 | ×1.0 |
| **MEDIUM** | 0.2-0.5% | **×0.6** | **×0.8** | **×0.5** | **×0.6** | **×0.7** | **×0.7** |
| **HIGH** | > 0.5% | ×1.0 | ×1.2 | ×1.2 | ×1.2 | ×1.5 | ×1.5 |

- **Performance Observée (10/12/2025):**
  - LOW: 52% WR, +0.10% avg PnL ✅
  - MEDIUM: 15% WR → ajustement agressif appliqué
  - HIGH: 100% WR (1 trade)
- **Transparence:** Les valeurs effectives sont exposées via `effective_config` et visibles dans le frontend ("Variables en cours").
- **Vérification:** Script `verification/verify_adaptive_behavior.py` valide la logique.

### Colonnes Remplies (45+ trades analysés au 10/12/2025)

```
✅ 100% rempli:
   - Core params (7): atr_mult_sl/tp, trailing_trigger/distance, be_mult, stagnation
   - Context: market_volatility_state, market_trend_state, entry_adx
   - Events: be_triggered, trailing_activated, stagnation_detected
   - PnL: max_pnl_reached, min_pnl_reached
   - Niveaux calculés: calculated_sl_price, calculated_tp_price, calculated_sl_pct, calculated_tp_pct
   - Prix extrêmes: max_price_reached, min_price_reached
   - Timing: time_to_max_pnl_seconds, time_to_min_pnl_seconds
   - Stagnation (si applicable): stagnation_detected_at, stagnation_duration_seconds, stagnation_pnl_at_exit

⚠️ 50-100% rempli (via What-If):
   - pnl_if_no_be, pnl_if_no_trailing, pnl_if_fixed_tp
   - pnl_if_wider_sl, pnl_if_tighter_sl
   - sl_efficiency, tp_efficiency, trailing_capture_pct

❌ Non implémenté (non prioritaire):
   - entry_atr_percentile (requiert calcul percentile vs historique)
```

---

## 📅 Roadmap des Prochaines Phases

### Phase 1.4: Context Clustering (4h)
**Objectif:** Regrouper les trades par régime de marché

```
Clusters attendus:
├── LOW_VOLATILITY + RANGING
├── LOW_VOLATILITY + TRENDING_WEAK
├── LOW_VOLATILITY + TRENDING_STRONG
├── MEDIUM_VOLATILITY + RANGING
├── MEDIUM_VOLATILITY + TRENDING
├── HIGH_VOLATILITY + RANGING
└── HIGH_VOLATILITY + TRENDING
```

**Prérequis:** Minimum 50 trades dans trade_atr_metrics (actuellement 8)

**Livrables:**
- `core/analysis/context_clusterer.py` - Moteur de clustering
- Vue SQL `v_trades_by_cluster` - Agrégation par régime
- Script d'analyse `verification/analyze_clusters.py`

---

### Phase 1.5: Dashboard Monitoring (6h)
**Objectif:** Interface pour visualiser les métriques ATR

**Composants:**
```
frontend/src/lib/components/
├── ATRMonitoringDashboard.svelte  (nouveau)
│   ├── Métriques globales (winrate, PF par cluster)
│   ├── Distribution What-If (histogramme pnl_if_*)
│   ├── Heatmap efficacité (sl_efficiency, tp_efficiency)
│   └── Timeline des trades avec context tagging
```

**Prérequis:** Phase 1.4 complétée

---

### Phase 1.6: CorrelationEngine (4h)
**Objectif:** Identifier corrélations params ↔ performance

**Analyses:**
- Corrélation `atr_mult_sl` vs Winrate
- Corrélation `trailing_distance_mult` vs `trailing_capture_pct`
- Impact du `be_atr_mult` sur les trades gagnants vs perdants

**Livrables:**
- `core/analysis/correlation_engine.py`
- Rapport automatique des corrélations significatives

---

### Phase 2.1: ContinuousATROptimizer (12h)
**Objectif:** Suggérer des paramètres optimaux par cluster

**Algorithme:**
1. Pour chaque cluster avec ≥20 trades
2. Calculer le "Best Param Set" basé sur What-If
3. Comparer avec les params actuels
4. Générer suggestions avec niveau de confiance

**Prérequis:** 
- Phase 1.4 complétée
- Minimum 100 trades avec ≥20 par cluster principal

---

### Phase 2.2-2.4: Auto-Apply & Rollback (14h)
**Objectif:** Appliquer automatiquement les optimisations

**Composants:**
- `ConfidenceScorer` - Évalue la fiabilité des suggestions
- `RollbackManager` - Détecte dégradation et rollback
- `AutoApplyEngine` - Applique les params si confiance > seuil

**Seuils de sécurité:**
```python
CONFIDENCE_THRESHOLD = 0.85  # Appliquer si confiance ≥ 85%
ROLLBACK_TRIGGER = -2.0      # Rollback si PF baisse de 2+ points
MIN_TRADES_FOR_DECISION = 30 # Minimum trades pour décider
```

---

## 🎯 Critères de Passage de Phase

| Phase | Critère de Succès |
|-------|-------------------|
| 1.4 → 1.5 | ≥3 clusters avec ≥20 trades chacun |
| 1.5 → 1.6 | Dashboard affiche données temps réel |
| 1.6 → 2.1 | Corrélations significatives identifiées (p < 0.05) |
| 2.1 → 2.2 | Suggestions générées pour ≥2 clusters |
| 2.2 → 2.4 | Confiance moyenne ≥ 70% sur suggestions |

---

## 📈 Métriques de Succès Attendues

| Métrique | Baseline | Objectif Phase 1 | Objectif Phase 2 |
|----------|----------|------------------|------------------|
| Profit Factor | 1.35 | 1.60 (+18%) | 1.85 (+37%) |
| Sharpe Ratio | 1.10 | 1.35 (+23%) | 1.55 (+41%) |
| Max Drawdown | 4.5% | 3.0% (-33%) | 2.0% (-55%) |
| Winrate | 52% | 55% (+6%) | 58% (+12%) |
| Adaptation Time | Manuel | <4h | <30min (auto) |

---

## 🔧 Scripts de Vérification Disponibles

```bash
# Vérification système complet
python verification/verify_atr_full_system.py

# Analyse remplissage colonnes
python verification/check_atr_metrics.py

# Backfill What-If pour nouveaux trades
python verification/backfill_whatif.py

# (À créer) Analyse des clusters
python verification/analyze_clusters.py
```

---

## ⏰ Timeline Estimée

```
Semaine 1 (actuelle):
├── ✅ Phase 0: Prérequis (4h) - TERMINÉ
├── ✅ Phase 1.1-1.3: Data + Logger + What-If (14h) - TERMINÉ
└── ⏸️  Accumulation données (3-5 jours)

Semaine 2 (si 50+ trades):
├── 1.4 Context Clustering (4h)
├── 1.5 Dashboard Monitoring (6h)
└── 1.6 CorrelationEngine (4h)

Semaine 3 (si patterns clairs):
├── 2.1 ContinuousATROptimizer (12h)
├── 2.2 ConfidenceScorer (4h)
└── 2.3 RollbackManager (4h)

Semaine 4:
├── 2.4 AutoApplyEngine (6h)
└── 3.x UI avancée (optionnel)
```

---

## 📝 Notes Importantes

### Anti-Overfitting
- Ne jamais optimiser sur <50 trades
- Toujours valider par cluster de marché
- Le What-If est déterministe mais le contexte change

### Colonnes Non-Critiques
Les colonnes à 0% (timestamps détaillés, prix extrêmes) sont **nice-to-have**.
L'optimisation peut fonctionner avec les colonnes actuellement remplies.

### Backfill Automatique
Le WhatIfSimulator est appelé automatiquement à la fermeture de chaque trade.
Le backfill manuel n'est nécessaire que pour les anciens trades.

---

**Document de référence pour les phases futures du système ATR Optimization.**

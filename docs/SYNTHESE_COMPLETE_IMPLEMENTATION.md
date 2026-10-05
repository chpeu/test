# 📋 SYNTHÈSE COMPLÈTE - IMPLÉMENTATION MARKET REGIME V2 + ATR OPTIMIZATION
## Document Consolidé Final

> **Version:** 2.0 | **Date:** 10/12/2025 | **Statut:** 📝 Planification Finalisée
> 
> **Principe Cardinal:** 🔄 **BOT TOUJOURS RUNNING** - Accumulation continue de données

---

## 🎯 LES 4 RÉGIMES (+ UNKNOWN)

| Régime | ADX | ATR% | Score Min | SL | TP | Stratégie |
|--------|-----|------|-----------|----|----|-----------|
| **CALME** | >20 | <0.20% | 8.5 | 0.8×ATR | 1.8×ATR | Signaux rares, très stricts |
| **NORMAL** | >20 | 0.20-0.40% | 8.0 | 1.2×ATR | 2.2×ATR | Équilibré |
| **VOLATILE** | >20 | >0.40% | 7.5 | 1.5×ATR | 2.5×ATR | Momentum, SL large |
| **CHOPPY** | <20 | Any | 10.0 | 0.7×ATR | 1.5×ATR | Pas de trend, quasi pas de trade |
| UNKNOWN | - | - | - | - | - | État initial seulement |

---

## 🏗️ ARCHITECTURE GLOBALE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SYSTÈME COMPLET                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    NIVEAU 1: CONTEXTE                               │    │
│  │                                                                     │    │
│  │  Session Detector ────► Market Regime Selector                      │    │
│  │  (heure UTC)             ├── V1: Rule-based (actuel)               │    │
│  │                          ├── V2: Médiane + Hystérésis + Lissage    │    │
│  │                          └── V3: ML Classifier                      │    │
│  │                                                                     │    │
│  │  Output: CALME | NORMAL | VOLATILE | CHOPPY                        │    │
│  │          + Session (ASIA, US_OPEN, etc.)                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    NIVEAU 2: PARAMÈTRES                             │    │
│  │                                                                     │    │
│  │  Chaque régime fournit sa config:                                   │    │
│  │  ├── SL/TP multipliers                                             │    │
│  │  ├── min_score_required                                            │    │
│  │  ├── optimal_atr_min/max                                           │    │
│  │  ├── stagnation params                                             │    │
│  │  ├── trailing/BE params                                            │    │
│  │  ├── seuils techniques (SNR, breakout, etc.)                       │    │
│  │  └── patterns activés (use_breakout, use_doji, etc.)              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    NIVEAU 3: PIPELINE TRADE                         │    │
│  │                                                                     │    │
│  │  Scanner ─► Analyzer ─► GB Classifier ─► ML Calibration            │    │
│  │     │          │              │               │                     │    │
│  │     │          │              │               │                     │    │
│  │   Filtre     Score          Features        Filtre                  │    │
│  │   ATR        min            Régime          WR band                 │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    NIVEAU 4: EXÉCUTION                              │    │
│  │                                                                     │    │
│  │  Position Manager ─► SL/TP calc ─► MEXC Order ─► Gestion           │    │
│  │        │                                            │               │    │
│  │        │                                     BE/Trailing/Stag      │    │
│  │        │                                                            │    │
│  │        ▼                                                            │    │
│  │  Close + Log ─► What-If ATR ─► What-If Régime ─► DB                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    NIVEAU 5: OPTIMISATION ML                        │    │
│  │                                                                     │    │
│  │  A) ML Regime Detector: "Dans quel régime?"                        │    │
│  │  B) ML Param Optimizer: "Quels params pour ce régime?"             │    │
│  │                                                                     │    │
│  │  Feature Importance ─► Grid Search ─► Cross-Validation ─► Apply    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 PHASES D'IMPLÉMENTATION DÉTAILLÉES

### 🟢 PHASE 0: INFRASTRUCTURE (2h)
**Bot:** ✅ Running | **Risque:** Aucun

| Action | Fichier | Description |
|--------|---------|-------------|
| CREATE | `database/migrations/add_regime_v2_columns.sql` | ~35 nouvelles colonnes |
| CREATE | `utils/session_detector.py` | Détection session (ASIA, US_OPEN, etc.) |
| MODIFY | `config.py` | Section `MARKET_REGIME_V2_CONFIG` |
| MODIFY | `config_overrides.json` | Toggles (tous OFF par défaut) |
| CREATE | `verification/run_migration.py` | Script de migration |

**Colonnes SQL à créer:**
```sql
-- trade_atr_metrics (15 nouvelles)
session_market, hour_utc, day_of_week, is_weekend,
regime_detection_method, regime_atr_median, regime_atr_smoothed,
regime_confidence, regime_stability_minutes,
pnl_if_calme_params, pnl_if_normal_params, pnl_if_volatile_params, pnl_if_choppy_params,
optimal_regime_retrospective, session_atr_multiplier

-- Params utilisés (8 nouvelles - pour ML Optimizer)
param_min_score_used, param_snr_threshold_used, param_breakout_threshold_used,
param_cooldown_used, param_di_gap_min_used, param_min_conditions_used,
param_partial_tp_pct_used, patterns_enabled_mask

-- market_regime_history (7 nouvelles)
detection_method, atr_median, atr_smoothed, session_market,
hysteresis_applied, outliers_filtered_count, ml_confidence

-- scan_logs (4 nouvelles)
session_market, hour_utc, regime_at_scan, regime_confidence_at_scan
```

---

### 🟢 PHASE 1A: LOGGING CONTEXTUEL (3h)
**Bot:** ✅ Running | **Risque:** Aucun | **Données:** Commence accumulation

| Action | Fichier | Description |
|--------|---------|-------------|
| MODIFY | `core/postgresql_datalogger.py` | Log session + régime + params utilisés |
| MODIFY | `core/market_regime_selector.py` | Log métadonnées V2 |
| CREATE | `verification/verify_logging.py` | Vérifier remplissage colonnes |

**Code clé - Logger params utilisés:**
```python
def log_trade_atr_metrics(self, trade_id, trade_data):
    # ... existant ...
    
    # NOUVEAU: Logger TOUS les params utilisés
    from utils.session_detector import get_current_session
    from utils.effective_config import get_all_effective_values
    
    session = get_current_session()
    config = get_all_effective_values()
    
    # Encoder les patterns actifs en bitmask
    patterns_mask = encode_patterns_mask(config)
    
    # Ajouter dans la query INSERT
    params_to_log = {
        'session_market': session['name'],
        'hour_utc': session['hour_utc'],
        'param_min_score_used': config.get('min_score_required'),
        'param_snr_threshold_used': config.get('snr_threshold'),
        'param_cooldown_used': config.get('cooldown_seconds'),
        'patterns_enabled_mask': patterns_mask,
        # ... etc
    }
```

---

### 🟢 PHASE 1B: RÉGIME V2 QUICK WINS (4h)
**Bot:** ✅ Running | **Risque:** Faible (toggles) | **Données:** Continue accumulation

| Action | Fichier | Description |
|--------|---------|-------------|
| MODIFY | `core/market_regime_selector.py` | Ajouter 6 nouvelles méthodes |
| MODIFY | `frontend/.../VariablesPanel.svelte` | Ajouter toggles V2 |
| CREATE | `verification/verify_regime_v2.py` | Tests régime V2 |

**Nouvelles méthodes:**
```python
# 1. Médiane au lieu de moyenne (anti-outliers)
def calculate_atr_metric(self, atr_values) -> float

# 2. Hystérésis (anti-flip-flop)
def should_change_regime(self, current, proposed, atr) -> bool

# 3. Lissage EMA (stabilité temporelle)
def apply_smoothing(self, new_value) -> float

# 4. Combinaison ATR 1m + 5m
def calculate_combined_atr(self, atr_1m, atr_5m) -> float

# 5. Seuils ajustés par session
def get_session_adjusted_thresholds(self) -> Dict

# 6. Check complet V2
async def check_regime_v2(self, atr_1m, atr_5m, adx, force) -> Tuple
```

**Frontend toggles à ajouter:**
```svelte
<!-- Section Régime V2 -->
<Toggle bind:checked={$config.market_regime_v2_enabled} label="Régime V2 Activé" />
<Toggle bind:checked={$config.market_regime_use_median} label="Utiliser Médiane" />
<Toggle bind:checked={$config.market_regime_use_hysteresis} label="Hystérésis" />
<Toggle bind:checked={$config.market_regime_use_smoothing} label="Lissage EMA" />
<Toggle bind:checked={$config.market_regime_use_atr_5m} label="Combiner ATR 5m" />
<Toggle bind:checked={$config.market_regime_use_seasonality} label="Saisonnalité" />
```

---

### 🟢 PHASE 1C: WHAT-IF RÉGIME (3h)
**Bot:** ✅ Running | **Données:** Continue accumulation

| Action | Fichier | Description |
|--------|---------|-------------|
| MODIFY | `core/analysis/what_if_simulator.py` | Ajouter simulate_regime_scenarios() |
| MODIFY | `core/position_manager.py` | Appeler what-if régime à la close |
| CREATE | `verification/backfill_regime_whatif.py` | Backfill trades existants |

**Simulation pour les 4 régimes:**
```python
def simulate_regime_scenarios(self, trade_data) -> Dict:
    results = {}
    
    for regime in ['CALME', 'NORMAL', 'VOLATILE', 'CHOPPY']:
        config = DEFAULT_REGIME_CONFIGS[regime]
        simulated_pnl = self._simulate_with_config(trade_data, config)
        results[f'pnl_if_{regime.lower()}_params'] = simulated_pnl
    
    # Déterminer le meilleur régime rétrospectif
    best = max(results.items(), key=lambda x: x[1])
    results['optimal_regime_retrospective'] = best[0].replace('pnl_if_', '').replace('_params', '').upper()
    
    return results
```

---

### 🟡 PHASE 1D: INTÉGRATION RÉGIME → COMPOSANTS (4h)
**Bot:** ✅ Running | **Risque:** Moyen | **Test requis**

| Action | Fichier | Description |
|--------|---------|-------------|
| MODIFY | `core/analyzer.py` | Utiliser get_active_config() pour filtrage |
| MODIFY | `core/position_manager.py` | Fonctions calculate_sl_tp_from_regime() |
| MODIFY | `trading/live_order_manager_futures.py` | SL MEXC lié au régime |
| MODIFY | `ml/feature_loader.py` | Ajouter features régime pour GB |

**Code clé - Injection des params:**
```python
# analyzer.py
def should_analyze_pair(self, pair, atr_pct):
    from core.market_regime_selector import get_regime_selector
    rs = get_regime_selector()
    config = rs.get_active_config()
    
    return config['optimal_atr_min'] <= atr_pct <= config['optimal_atr_max']

# position_manager.py
def calculate_sl_tp_from_regime(self, entry, direction, atr_pct):
    rs = get_regime_selector()
    config = rs.get_active_config()
    
    sl = entry * (1 - atr_pct * config['atr_mult_sl'] / 100)
    tp = entry * (1 + atr_pct * config['atr_mult_tp'] / 100)
    
    return sl, tp
```

---

### ⏸️ PAUSE: ACCUMULATION 50+ TRADES (3-7 jours)
**Bot:** ✅ Running 24/7 | **Action:** Monitoring des données

---

### 🟡 PHASE 2A: ANALYSE CORRÉLATIONS (4h)
**Prérequis:** 50+ trades | **Bot:** ✅ Running

| Action | Fichier | Description |
|--------|---------|-------------|
| CREATE | `core/analysis/correlation_engine.py` | Moteur d'analyse |
| CREATE | `verification/analyze_performance.py` | Script d'analyse |

**Analyses générées:**
```
┌────────────────────────────────────────┐
│ RAPPORT PERFORMANCE PAR CONTEXTE       │
├────────────────────────────────────────┤
│                                        │
│ PAR SESSION:                           │
│ US_OPEN:     32 trades, WR=62%, PF=1.8 │
│ EUROPE:      28 trades, WR=54%, PF=1.4 │
│ ASIA:        15 trades, WR=48%, PF=1.1 │
│                                        │
│ PAR RÉGIME:                            │
│ VOLATILE:    40 trades, WR=58%, PF=1.6 │
│ NORMAL:      25 trades, WR=55%, PF=1.5 │
│ CALME:       10 trades, WR=50%, PF=1.2 │
│ CHOPPY:       0 trades                 │
│                                        │
│ PRÉCISION RÉGIME:                      │
│ 68% des trades utilisaient le régime  │
│ qui aurait été optimal                 │
│                                        │
│ RECOMMANDATIONS:                       │
│ 🔴 Éviter ASIA (WR<50%)               │
│ 🟢 Favoriser US_OPEN (WR=62%)          │
└────────────────────────────────────────┘
```

---

### 🟡 PHASE 2B: DASHBOARD MONITORING (6h)
**Bot:** ✅ Running

| Action | Fichier | Description |
|--------|---------|-------------|
| CREATE | `frontend/.../RegimeAnalyticsDashboard.svelte` | Dashboard complet |
| CREATE | `api/regime_analytics.py` | Endpoints analytics |
| MODIFY | `frontend/.../+page.svelte` | Intégrer dashboard |

**Composant Dashboard:**
```svelte
<RegimeAnalyticsDashboard>
  <!-- Cartes status actuel -->
  <StatusCards>
    <Card title="Session Actuelle" value={currentSession} />
    <Card title="Régime Actuel" value={currentRegime} icon={regimeIcon} />
    <Card title="Précision Régime" value={accuracy + '%'} />
    <Card title="Stabilité" value={stabilityMinutes + ' min'} />
  </StatusCards>
  
  <!-- Tableau performance par session -->
  <SessionPerformanceTable data={sessionStats} />
  
  <!-- Tableau performance par régime -->
  <RegimePerformanceTable data={regimeStats} />
  
  <!-- Graphique heure par heure -->
  <HourlyPerformanceChart data={hourlyStats} />
  
  <!-- Matrice régime utilisé vs optimal -->
  <RegimeAccuracyMatrix data={regimeMatrix} />
</RegimeAnalyticsDashboard>
```

---

### 🟡 PHASE 2C: OPTIMIZER SUGGESTIONS (4h)
**Prérequis:** 50+ trades

| Action | Fichier | Description |
|--------|---------|-------------|
| CREATE | `core/analysis/regime_optimizer.py` | Suggérer params optimaux |
| CREATE | `api/optimizer_endpoints.py` | API suggestions |
| MODIFY | Dashboard | Afficher suggestions |

---

### 🔴 PHASE 2D: ML PARAMETER OPTIMIZER (10h)
**Prérequis:** 100+ trades par régime principal

| Action | Fichier | Description |
|--------|---------|-------------|
| CREATE | `core/analysis/ml_param_optimizer.py` | Optimisation ML |
| CREATE | `core/analysis/feature_importance.py` | Importance des params |

**Paramètres optimisables (34 total):**

| Tier | Catégorie | Params | Priorité |
|------|-----------|--------|----------|
| 1 | SL/TP/Position | 7 | 🔴 Haute |
| 2 | Filtrage/Timing | 10 | 🟡 Moyenne |
| 3 | Ajustements | 9 | 🟢 Basse |
| 4 | Patterns ON/OFF | 8 | 🟡 Moyenne |

**Output attendu:**
```json
{
  "CALME": {
    "atr_mult_sl": 0.92,
    "atr_mult_tp": 1.75,
    "min_score_required": 8.8,
    "snr_threshold": 0.11,
    "use_breakout": false,
    "use_retest": true
  },
  "NORMAL": { ... },
  "VOLATILE": { ... },
  "CHOPPY": { ... }
}
```

---

### ⏸️ PAUSE: ACCUMULATION 200+ TRADES (2-3 semaines)
**Bot:** ✅ Running 24/7

---

### 🔴 PHASE 3A: ML REGIME DETECTOR (8h)
**Prérequis:** 200+ trades

| Action | Fichier | Description |
|--------|---------|-------------|
| CREATE | `core/ml/regime_classifier.py` | Classifier ML |
| MODIFY | `core/market_regime_selector.py` | Intégrer ML classifier |

**Features ML:**
```python
REGIME_FEATURES = [
    'atr_1m', 'atr_5m', 'atr_15m',
    'adx_1m', 'adx_5m',
    'volume_ratio',
    'hour_utc', 'day_of_week',
    'btc_correlation',
    'regime_stability_minutes'
]
```

---

### 🔴 PHASE 3B: GB FEATURE INTEGRATION (4h)

| Action | Fichier | Description |
|--------|---------|-------------|
| MODIFY | `ml/feature_loader.py` | Ajouter features régime |
| MODIFY | `ml/train_model.py` | Réentraîner avec nouvelles features |

**Nouvelles features GB:**
```python
'regime_encoded',           # 0=CALME, 1=NORMAL, 2=VOLATILE, 3=CHOPPY
'session_encoded',          # 0-7 pour les sessions
'regime_stability_minutes',
'session_atr_multiplier',
'regime_ml_confidence'
```

---

### 🔴 PHASE 3C: AUTO-APPLY & ROLLBACK (8h)

| Action | Fichier | Description |
|--------|---------|-------------|
| CREATE | `core/analysis/auto_apply_engine.py` | Application auto |
| CREATE | `core/analysis/rollback_manager.py` | Surveillance & rollback |

**Sécurités:**
```python
CONFIDENCE_THRESHOLD = 0.85    # Appliquer si confiance ≥ 85%
MIN_TRADES_FOR_DECISION = 30   # Minimum trades
ROLLBACK_TRIGGER = -2.0        # Rollback si PF baisse de 2+ points
VALIDATION_PERIOD_TRADES = 20  # Trades avant validation définitive
```

---

## 🖥️ FRONTEND: TOUS LES COMPOSANTS

### Modifications VariablesPanel.svelte

```svelte
<!-- SECTION 1: Régime V2 Toggles -->
<Section title="🌡️ Market Regime V2">
  <Toggle key="market_regime_v2_enabled" />
  <Toggle key="market_regime_use_median" />
  <Toggle key="market_regime_use_hysteresis" />
  <Toggle key="market_regime_use_smoothing" />
  <Toggle key="market_regime_use_atr_5m" />
  <Toggle key="market_regime_use_seasonality" />
  <Toggle key="market_regime_use_ml" />  <!-- Phase 3 -->
</Section>

<!-- SECTION 2: Paramètres Régime V2 -->
<Section title="⚙️ Paramètres V2">
  <Slider key="market_regime_hysteresis_buffer" min="0.05" max="0.20" />
  <Slider key="market_regime_smoothing_alpha" min="0.1" max="0.5" />
  <Slider key="market_regime_atr_1m_weight" min="0.2" max="0.8" />
  <Slider key="market_regime_min_duration_min" min="10" max="60" />
</Section>

<!-- SECTION 3: Status Actuel (lecture seule) -->
<Section title="📊 Status Actuel">
  <Display label="Session" value={currentSession} />
  <Display label="Régime" value={currentRegime} />
  <Display label="Stabilité" value={stabilityMinutes + ' min'} />
  <Display label="Méthode" value={detectionMethod} />
</Section>
```

### Nouveau: RegimeAnalyticsDashboard.svelte

```svelte
<!-- Dashboard complet avec graphiques -->
<script>
  import { onMount } from 'svelte';
  import { Card, Table, Chart } from '$lib/components/ui';
  
  let sessionStats = [];
  let regimeStats = [];
  let hourlyStats = [];
  let currentSession = '';
  let currentRegime = '';
  let accuracy = 0;
  
  onMount(async () => {
    await fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 60000);
    return () => clearInterval(interval);
  });
  
  async function fetchAnalytics() {
    const res = await fetch('/api/regime/analytics');
    const data = await res.json();
    sessionStats = data.session_performance;
    regimeStats = data.regime_performance;
    hourlyStats = data.hourly_performance;
    currentSession = data.current_session;
    currentRegime = data.current_regime;
    accuracy = data.regime_accuracy;
  }
</script>
```

### Nouveau: RegimeOptimizerPanel.svelte

```svelte
<!-- Panel pour lancer l'optimisation et voir les suggestions -->
<script>
  let suggestions = [];
  let isOptimizing = false;
  
  async function runOptimization() {
    isOptimizing = true;
    const res = await fetch('/api/optimizer/run', { method: 'POST' });
    suggestions = await res.json();
    isOptimizing = false;
  }
  
  async function applySuggestion(regime) {
    await fetch(`/api/optimizer/apply/${regime}`, { method: 'POST' });
    // Refresh
  }
</script>

<Card title="🎛️ ML Parameter Optimizer">
  <Button on:click={runOptimization} disabled={isOptimizing}>
    {isOptimizing ? 'Optimisation en cours...' : 'Lancer Optimisation'}
  </Button>
  
  {#each suggestions as s}
    <SuggestionCard 
      regime={s.regime}
      currentParams={s.current_params}
      suggestedParams={s.suggested_params}
      expectedPF={s.expected_pf}
      confidence={s.confidence}
      onApply={() => applySuggestion(s.regime)}
    />
  {/each}
</Card>
```

---

## 📋 MAPPING DOCUMENTS

| Document | Contenu |
|----------|---------|
| `MASTER_IMPLEMENTATION_PLAN.md` | Roadmap phases |
| `PHASE_0_INFRASTRUCTURE.md` | SQL + Config détaillés |
| `PHASE_1_IMPLEMENTATION.md` | Logging + Régime V2 |
| `PHASE_2_3_ANALYSIS_ML.md` | Analyse + Dashboard + ML Regime |
| `PHASE_2D_ML_PARAMETER_OPTIMIZER.md` | ML optimisation params |
| `INTERACTIONS_REGIME_PARAMS.md` | Flux params dans le pipeline |
| `SYNTHESE_COMPLETE_IMPLEMENTATION.md` | **CE DOCUMENT** |

---

## ✅ CHECKLIST EXHAUSTIVE

### Phase 0
- [ ] Migration SQL créée (35+ colonnes)
- [ ] session_detector.py créé et testé
- [ ] Config variables ajoutées
- [ ] Script migration exécuté
- [ ] Bot restart, vérifie qu'il tourne

### Phase 1A
- [ ] Logger enrichi (session, hour, params utilisés)
- [ ] Bitmask patterns implémenté
- [ ] Vérif: 1 trade avec toutes colonnes remplies

### Phase 1B
- [ ] 6 nouvelles méthodes dans market_regime_selector
- [ ] Toggles frontend ajoutés
- [ ] Test: régime stable 2h avec hystérésis

### Phase 1C
- [ ] What-If régime pour 4 régimes
- [ ] optimal_regime_retrospective calculé
- [ ] Backfill trades existants

### Phase 1D
- [ ] analyzer.py utilise get_active_config()
- [ ] position_manager.py: calculate_sl_tp_from_regime()
- [ ] SL MEXC lié au régime
- [ ] GB features régime ajoutées

### Phase 2A
- [ ] Script analyse corrélations
- [ ] Rapport généré
- [ ] Recommandations identifiées

### Phase 2B
- [ ] Dashboard Svelte créé
- [ ] API endpoints créés
- [ ] Intégré dans layout

### Phase 2C
- [ ] Optimizer suggestions rule-based
- [ ] API endpoint

### Phase 2D
- [ ] Feature importance par régime
- [ ] Grid search implémenté
- [ ] Cross-validation
- [ ] 4 fichiers config générés

### Phase 3A
- [ ] ML Regime classifier entraîné
- [ ] Accuracy > 70%
- [ ] Intégré avec toggle

### Phase 3B
- [ ] Features régime dans GB
- [ ] Modèle réentraîné

### Phase 3C
- [ ] Auto-apply avec seuil confiance
- [ ] Rollback manager
- [ ] Logs surveillance

---

## 🎯 MÉTRIQUES DE SUCCÈS

| Métrique | Actuel | Phase 1 | Phase 2 | Phase 3 |
|----------|--------|---------|---------|---------|
| Win Rate | ~48% | 52% | 56% | 60% |
| Profit Factor | ~1.35 | 1.55 | 1.85 | 2.0 |
| Max Drawdown | ~4.5% | 3.5% | 2.5% | 2.0% |
| Flip-Flop/jour | ~8 | ~3 | ~1 | ~0.5 |
| Précision Régime | ~50% | 65% | 75% | 85% |
| Params par régime | 10 | 10 | 20 | 34 |

---

## ⏰ TIMELINE ESTIMÉE

```
SEMAINE 1 (Cette semaine):
├── Phase 0: Infrastructure (2h)
├── Phase 1A: Logging (3h)
└── Bot running 24/7, accumulation données

SEMAINE 2:
├── Phase 1B: Régime V2 (4h)
├── Phase 1C: What-If Régime (3h)
├── Phase 1D: Intégration composants (4h)
└── Bot running, 50+ trades attendus

SEMAINE 3:
├── Phase 2A: Analyse corrélations (4h)
├── Phase 2B: Dashboard (6h)
└── Phase 2C: Optimizer suggestions (4h)

SEMAINE 4:
├── Phase 2D: ML Param Optimizer (10h)
└── Bot running, 100+ trades attendus

SEMAINE 5-6:
├── Phase 3A: ML Regime Detector (8h)
├── Phase 3B: GB Integration (4h)
└── Phase 3C: Auto-Apply (8h)

TOTAL: ~70h sur 6 semaines
```

---

**Ce document est LA référence complète. Rien n'est oublié.**

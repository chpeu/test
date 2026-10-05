# Architecture d'Optimisation TP/SL ATR

> **Objectif:** Monitorer, analyser et auto-adapter tous les paramètres ATR pour maximiser la performance.
> **Vision:** Phase 2 = Auto-adaptation dynamique sans limites fixes, le système s'adapte à la performance.
> **Focus:** Uniquement les paramètres de SORTIE/CLOTURE de trade (pas les entrées).

---

## 🔍 PHASE 0: Audit des Paramètres Actuels

### 0.1 Pourquoi l'approche "What-If" est le Gold Standard

Contrairement aux entrées (probabilistes), l'optimisation des **sorties** sur le passé est **déterministe**.

Une fois entré dans un trade à `t=0`, le futur des prix est connu dans la base de données.
On peut calculer **mathématiquement et avec 100% de certitude** :
- *"Si mon SL avait été à 1.5 ATR au lieu de 1.2, aurais-je été liquidé ?"*
- *"Si mon TP avait été à 4 ATR, le prix l'aurait-il touché avant le SL ?"*

**L'architecture Monitoring + What-If est donc la plus robuste** car elle ne se base pas sur des suppositions, mais sur la recalculation exacte de ce qui se serait passé avec d'autres réglages.

### 0.2 Classification des Paramètres Actuels

#### ✅ INDISPENSABLES (Keep & Optimize - Priorité #1)

| Paramètre | Impact | Commentaire |
|-----------|--------|-------------|
| `atr_mult_sl` | **CRITIQUE** | Plus d'impact sur Winrate. Trop serré = bruit vous sort. Trop large = R:R effondré |
| `atr_mult_tp` | **CRITIQUE** | Définit l'espérance de gain |
| `trailing_trigger_atr_mult` | **IMPORTANT** | Quand activer le trailing pour sécuriser les gains |

#### ⚠️ À SURVEILLER / AFFINER (Refine)

| Paramètre | Critique | Action |
|-----------|----------|--------|
| `break_even_atr_mult` | Souvent le **"tueur de performance"**. Mis trop tôt pour se rassurer ("trade gratuit"), mais le prix revient souvent tester l'entrée avant de repartir. | L'optimiseur doit surveiller agressivement le **"Opportunity Cost"** du BE |
| `stagnation_timeout` | Paramètre temporel, pas ATR pur | Garder en sécurité ultime, potentiellement redondant si Trailing efficace |
| `stagnation_min_pnl` | Idem | Idem |

#### ❌ DOUBLONS / INUTILES (Simplify)

| Paramètre | Problème | Action Recommandée |
|-----------|----------|-------------------|
| `break_even_use_atr` | Toggle inutile en Mode ATR | **SUPPRIMER** - On force l'ATR |
| `trailing_use_atr_trigger` | Toggle inutile en Mode ATR | **SUPPRIMER** - On force l'ATR |

> **Décision:** En Mode ATR pur, ces booléens ajoutent de la complexité au code et à l'optimiseur sans valeur ajoutée.

#### 🧩 PARAMÈTRE MANQUANT (Missing Link)

| Paramètre | Besoin | Impact |
|-----------|--------|--------|
| `trailing_distance_atr_mult` | **CRITIQUE** | Actuellement on a le *Trigger* (quand ça commence), mais pas la *Distance* du stop suiveur |

**Problème actuel:**
- `trailing_trigger_atr_mult` = 1.5 → Le trailing s'active à +1.5 ATR de profit
- Mais quelle est la distance du stop suiveur ensuite ? 0.5 ATR (serré) ou 1.5 ATR (large) ?

**Best Practice:**
```
Trigger LOIN (ex: 1.5 ATR) → Laisser le trade partir
Distance SERRÉE (ex: 0.5 ATR) → Capturer le mouvement une fois parti
```

> **Action:** Séparer `Trigger` et `Distance` dans le code ET l'optimisation.

### 0.3 Context Tagging (Anti-Overfitting)

**Danger:** Si le marché est calme lundi et volatile mardi, l'optimiseur ne doit pas appliquer les réglages de lundi pour mardi.

**Solution:** Chaque trade doit être tagué avec son contexte marché :

```sql
-- Ajouter au trade_atr_metrics
market_volatility_state VARCHAR(10),  -- 'LOW', 'MEDIUM', 'HIGH'
market_trend_state VARCHAR(20),       -- 'RANGING', 'TRENDING_WEAK', 'TRENDING_STRONG'
entry_adx FLOAT,                      -- ADX au moment de l'entrée
entry_atr_percentile FLOAT,           -- Percentile ATR vs historique (0-100)
```

**L'optimiseur fonctionne alors par "Cluster" :**
1. *"Je suis actuellement en régime VOLATILE + RANGING"*
2. *"Cherche les 100 derniers trades qui avaient ce MÊME contexte"*
3. *"Quels étaient les meilleurs paramètres TP/SL pour CE contexte ?"*

### 0.4 Liste Finale des Paramètres à Optimiser

| # | Paramètre | Type | Plage | Priorité |
|---|-----------|------|-------|----------|
| 1 | `atr_mult_sl` | Float | 0.5 - 3.0 | 🔴 CRITIQUE |
| 2 | `atr_mult_tp` | Float | 1.0 - 6.0 | 🔴 CRITIQUE |
| 3 | `trailing_trigger_atr_mult` | Float | 0.5 - 3.0 | 🔴 CRITIQUE |
| 4 | `trailing_distance_atr_mult` | Float | 0.3 - 2.0 | 🔴 CRITIQUE (NOUVEAU) |
| 5 | `be_atr_mult` | Float | 0.2 - 2.5 | 🟡 IMPORTANT |
| 6 | `stagnation_timeout` | Int | 60 - 900 | 🟢 SÉCURITÉ |
| 7 | `stagnation_min_pnl` | Float | 0.01 - 0.20 | 🟢 SÉCURITÉ |

**Paramètres SUPPRIMÉS de l'optimisation:**
- `break_even_use_atr` → Toujours TRUE en mode ATR
- `trailing_use_atr_trigger` → Toujours TRUE en mode ATR
- `stagnation_max_loss` → Redondant avec SL

---

## 📊 PHASE 1: Monitoring Exhaustif

### 1.1 Nouvelles Colonnes SQL Requises

```sql
-- Table: trade_atr_metrics (nouvelle table dédiée)
CREATE TABLE trade_atr_metrics (
    id SERIAL PRIMARY KEY,
    trade_id UUID REFERENCES trades(id),
    
    -- Contexte ATR à l'entrée
    entry_atr_1m FLOAT,
    entry_atr_5m FLOAT,
    entry_atr_pct_1m FLOAT,
    entry_atr_pct_5m FLOAT,
    
    -- Paramètres utilisés pour CE trade (7 paramètres finaux)
    param_atr_mult_sl FLOAT,
    param_atr_mult_tp FLOAT,
    param_trailing_trigger_mult FLOAT,
    param_trailing_distance_mult FLOAT,  -- 🆕 NOUVEAU: Distance du trailing
    param_be_atr_mult FLOAT,             -- NULL si BE désactivé
    param_stagnation_timeout INT,        -- NULL si stagnation désactivée
    param_stagnation_min_pnl FLOAT,
    
    -- Context Tagging (Anti-Overfitting)
    market_volatility_state VARCHAR(10),  -- 'LOW', 'MEDIUM', 'HIGH'
    market_trend_state VARCHAR(20),       -- 'RANGING', 'TRENDING_WEAK', 'TRENDING_STRONG'
    entry_adx FLOAT,
    entry_atr_percentile FLOAT,           -- Percentile ATR vs historique (0-100)
    
    -- Niveaux calculés (en prix)
    calculated_sl_price FLOAT,
    calculated_tp_price FLOAT,
    calculated_be_trigger_pnl_pct FLOAT,  -- PnL% pour déclencher BE
    calculated_trailing_trigger_pnl_pct FLOAT,
    
    -- Événements survenus
    be_triggered BOOLEAN DEFAULT FALSE,
    be_triggered_at TIMESTAMPTZ,
    be_triggered_pnl_pct FLOAT,  -- PnL% au moment du trigger
    
    trailing_activated BOOLEAN DEFAULT FALSE,
    trailing_activated_at TIMESTAMPTZ,
    trailing_activated_pnl_pct FLOAT,
    trailing_final_distance_pct FLOAT,  -- Distance finale du trailing
    
    stagnation_detected BOOLEAN DEFAULT FALSE,
    stagnation_detected_at TIMESTAMPTZ,
    stagnation_duration_seconds INT,
    
    -- Résultats "What-If" (calculés post-trade)
    pnl_if_no_be FLOAT,           -- PnL si BE n'avait pas été activé
    pnl_if_no_trailing FLOAT,     -- PnL si trailing n'avait pas été activé
    pnl_if_fixed_tp FLOAT,        -- PnL avec TP fixe (sans trailing)
    pnl_if_wider_sl FLOAT,        -- PnL avec SL × 1.5
    pnl_if_tighter_sl FLOAT,      -- PnL avec SL × 0.75
    
    -- Maximum atteint pendant le trade
    max_pnl_reached FLOAT,
    min_pnl_reached FLOAT,
    max_price_reached FLOAT,
    min_price_reached FLOAT,
    time_to_max_pnl_seconds INT,
    time_to_min_pnl_seconds INT,
    
    -- Efficacité des paramètres
    sl_efficiency FLOAT,  -- % du SL utilisé (0-100%)
    tp_efficiency FLOAT,  -- % du TP atteint avant sortie
    be_efficiency FLOAT,  -- Si BE: trade aurait-il été perdant sans?
    trailing_capture_pct FLOAT,  -- % du mouvement capturé par trailing
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour analyses rapides
CREATE INDEX idx_atr_metrics_trade ON trade_atr_metrics(trade_id);
CREATE INDEX idx_atr_metrics_be ON trade_atr_metrics(be_triggered) WHERE be_triggered = TRUE;
CREATE INDEX idx_atr_metrics_trailing ON trade_atr_metrics(trailing_activated) WHERE trailing_activated = TRUE;
```

### 1.2 Métriques Dérivées à Calculer

| Métrique | Formule | Utilité |
|----------|---------|---------|
| **BE Hit Rate** | `COUNT(be_triggered) / COUNT(*)` | Fréquence d'activation du BE |
| **BE Save Rate** | `COUNT(be_triggered AND win) / COUNT(be_triggered)` | % de BE qui ont sauvé le trade |
| **BE Opportunity Cost** | `AVG(pnl_if_no_be - actual_pnl) WHERE be_triggered` | Gain perdu à cause du BE |
| **Trailing Capture Efficiency** | `AVG(trailing_capture_pct)` | Efficacité du trailing |
| **SL Optimality Score** | `AVG(CASE WHEN sl_hit THEN max_pnl_reached ELSE 0 END)` | Le SL coupe-t-il des trades rentables? |
| **Stagnation Accuracy** | `COUNT(stagnation_exit AND would_have_lost) / COUNT(stagnation_exit)` | La stagnation évite-t-elle des pertes? |

### 1.3 Dashboard Monitoring Temps Réel

```
┌────────────────────────────────────────────────────────────────────┐
│ 📊 ATR PERFORMANCE MONITOR                          [Live] 🟢      │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │ 🎯 BE ANALYSIS  │  │ 📈 TRAILING     │  │ ⏰ STAGNATION   │    │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤    │
│  │ Hit Rate: 42%   │  │ Activation: 28% │  │ Exits: 12%      │    │
│  │ Save Rate: 78%  │  │ Capture: 67%    │  │ Saved: 85%      │    │
│  │ Opp. Cost: -2.1%│  │ Avg Gain: +0.18%│  │ Avg Save: +0.09%│    │
│  │ ▲ Optimal: 0.8x │  │ ▲ Optimal: 1.2x │  │ ▲ Optimal: 420s │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ 🎚️ PARAMETER IMPACT HEATMAP (Last 200 trades)               │  │
│  ├─────────────────────────────────────────────────────────────┤  │
│  │                                                             │  │
│  │  ATR Mult SL    [0.8]──[1.0]──[1.2]──[1.4]──[1.6]          │  │
│  │  Impact PnL:     -3%    +1%   ▓▓+5%▓▓  +2%    -1%          │  │
│  │                                 ↑ OPTIMAL                   │  │
│  │                                                             │  │
│  │  BE ATR Mult    [0.5]──[0.7]──[1.0]──[1.2]──[1.5]          │  │
│  │  Impact PnL:     +2%  ▓▓+4%▓▓  +1%    -2%    -5%          │  │
│  │                        ↑ OPTIMAL                            │  │
│  │                                                             │  │
│  │  Trailing Mult  [1.0]──[1.2]──[1.5]──[1.8]──[2.0]          │  │
│  │  Impact PnL:     -4%    +1%  ▓▓+6%▓▓  +3%    -1%          │  │
│  │                                 ↑ OPTIMAL                   │  │
│  │                                                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ ⚠️ ALERTS & RECOMMENDATIONS                                 │  │
│  ├─────────────────────────────────────────────────────────────┤  │
│  │ 🔴 BE Mult 1.0 → Opportunity cost élevé (-2.1%)             │  │
│  │    Recommandation: Réduire à 0.7x (+4% PnL attendu)         │  │
│  │                                                             │  │
│  │ 🟡 Stagnation Timeout 540s → 15% des exits prématurés       │  │
│  │    Recommandation: Augmenter à 600s ou réduire min_pnl      │  │
│  │                                                             │  │
│  │ 🟢 ATR Mult SL 1.2 → Optimal confirmé (78% efficacité)      │  │
│  └─────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🔬 PHASE 1.5: Analyse d'Impact Précise

### 1.5.1 Système de Backtesting Paramétrique

Pour chaque trade fermé, calculer rétroactivement ce qui se serait passé avec d'autres paramètres:

```python
class ATRParameterAnalyzer:
    """
    Analyse l'impact de chaque paramètre sur la performance.
    Utilise les données de prix historiques pour simuler des scénarios alternatifs.
    """
    
    def analyze_trade(self, trade_id: str) -> Dict:
        """
        Pour un trade donné, calcule le PnL avec différentes configurations.
        """
        trade = self.get_trade(trade_id)
        price_history = self.get_price_history(trade.symbol, trade.entry_time, trade.exit_time)
        
        # Configuration réelle utilisée
        actual_config = trade.atr_config
        actual_pnl = trade.net_pnl_pct
        
        # Scénarios alternatifs
        scenarios = {
            'sl_mult': [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0],
            'tp_mult': [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
            'be_mult': [0.5, 0.7, 0.8, 1.0, 1.2, 1.5, None],  # None = disabled
            'trailing_mult': [0.8, 1.0, 1.2, 1.5, 1.8, 2.0, None],
            'stagnation_timeout': [180, 300, 420, 540, 600, None],
        }
        
        results = {}
        for param, values in scenarios.items():
            results[param] = {}
            for value in values:
                # Simuler le trade avec ce paramètre modifié
                alt_config = actual_config.copy()
                if value is None:
                    alt_config[f'{param}_enabled'] = False
                else:
                    alt_config[param] = value
                
                simulated_pnl = self.simulate_trade(trade, price_history, alt_config)
                results[param][value] = {
                    'pnl': simulated_pnl,
                    'delta_vs_actual': simulated_pnl - actual_pnl,
                    'events': self.get_simulated_events(trade, price_history, alt_config)
                }
        
        return {
            'trade_id': trade_id,
            'actual_pnl': actual_pnl,
            'actual_config': actual_config,
            'scenarios': results,
            'optimal_config': self.find_optimal(results),
            'improvement_potential': self.calculate_improvement_potential(results)
        }
```

### 1.5.2 Matrice de Corrélation Paramètres/Performance

```
CORRELATION MATRIX: Parameters vs Performance Metrics
═══════════════════════════════════════════════════════════════════

                    │ Winrate │ Avg PnL │ Max DD │ Sharpe │ Profit Factor
────────────────────┼─────────┼─────────┼────────┼────────┼───────────────
ATR Mult SL         │  +0.42  │  +0.38  │ -0.55  │ +0.45  │    +0.41
ATR Mult TP         │  -0.15  │  +0.52  │ +0.22  │ +0.35  │    +0.48
BE ATR Mult         │  +0.28  │  -0.18  │ -0.45  │ +0.12  │    +0.08
Trailing Trigger    │  -0.08  │  +0.45  │ +0.15  │ +0.38  │    +0.42
Stagnation Timeout  │  +0.05  │  +0.12  │ -0.08  │ +0.10  │    +0.06

INSIGHTS:
• ATR Mult SL: Forte corrélation positive avec toutes les métriques sauf Max DD
  → Un SL bien calibré est CRUCIAL
  
• BE ATR Mult: Corrélation négative avec Avg PnL
  → Le BE protège mais limite les gains
  → Trade-off sécurité vs performance
  
• Trailing: Forte corrélation avec Avg PnL et Profit Factor
  → Le trailing capture efficacement les mouvements
  
• Stagnation: Impact faible sur toutes les métriques
  → Paramètre de protection, pas d'optimisation
```

### 1.5.3 Segmentation par Conditions de Marché

```
PARAMETER PERFORMANCE BY MARKET CONDITION
═════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│ REGIME: VOLATILE (ATR > 0.5%)                                   │
├─────────────────────────────────────────────────────────────────┤
│ Optimal ATR Mult SL: 1.5 (vs 1.2 baseline) → +12% Sharpe       │
│ Optimal BE Mult: 0.5 (BE rapide pour sécuriser)                │
│ Optimal Trailing: 1.8 (laisser courir les gains)               │
│ Stagnation: DISABLED (mouvements rapides)                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ REGIME: CALME (ATR < 0.2%)                                      │
├─────────────────────────────────────────────────────────────────┤
│ Optimal ATR Mult SL: 0.9 (SL serré car faible volatilité)      │
│ Optimal BE Mult: 1.2 (attendre confirmation)                   │
│ Optimal Trailing: 1.0 (capturer les petits mouvements)         │
│ Stagnation: 300s (sortir vite si ça ne bouge pas)              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ REGIME: TRENDING (ADX > 30)                                     │
├─────────────────────────────────────────────────────────────────┤
│ Optimal ATR Mult SL: 1.2 (standard)                            │
│ Optimal BE Mult: DISABLED (laisser les trends respirer)        │
│ Optimal Trailing: 2.0 (maximiser la capture du trend)          │
│ Stagnation: 600s (les trends peuvent avoir des pauses)         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ REGIME: CHOPPY (ADX < 20, direction changes > 3/5min)           │
├─────────────────────────────────────────────────────────────────┤
│ Optimal ATR Mult SL: 0.8 (sortir vite)                         │
│ Optimal BE Mult: 0.3 (BE ultra-rapide)                         │
│ Optimal Trailing: DISABLED (pas de trend à suivre)             │
│ Stagnation: 120s (sortir rapidement)                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🤖 PHASE 2: Auto-Adaptation Dynamique

### 2.1 Architecture du Système Adaptatif

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ATR AUTO-OPTIMIZER                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   MARKET    │───▶│  ANALYZER   │───▶│  OPTIMIZER  │             │
│  │   STATE     │    │   ENGINE    │    │   ENGINE    │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│        │                  │                  │                      │
│        ▼                  ▼                  ▼                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │ • ATR 1m/5m │    │ • Trade     │    │ • Parameter │             │
│  │ • ADX       │    │   Metrics   │    │   Gradient  │             │
│  │ • Volume    │    │ • What-If   │    │ • Confidence│             │
│  │ • Spread    │    │   Analysis  │    │   Score     │             │
│  │ • Trend     │    │ • Correla-  │    │ • Suggested │             │
│  │   Strength  │    │   tions     │    │   Values    │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│                                                                     │
│                           │                                         │
│                           ▼                                         │
│                    ┌─────────────┐                                  │
│                    │  DECISION   │                                  │
│                    │   ENGINE    │                                  │
│                    └─────────────┘                                  │
│                           │                                         │
│           ┌───────────────┼───────────────┐                        │
│           ▼               ▼               ▼                        │
│    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│    │   AUTO      │ │  SUGGEST    │ │   ALERT     │                 │
│    │   APPLY     │ │  (Manual)   │ │   ONLY      │                 │
│    └─────────────┘ └─────────────┘ └─────────────┘                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Algorithme d'Optimisation Continue

```python
class ContinuousATROptimizer:
    """
    Optimisation continue des paramètres ATR basée sur la performance récente.
    
    Principes:
    1. Pas de limites fixes - le système cherche l'optimal
    2. Adaptation graduelle pour éviter l'overfitting
    3. Confidence scoring pour valider les changements
    4. Rollback automatique si dégradation
    """
    
    def __init__(self):
        self.learning_rate = 0.1  # Vitesse d'adaptation
        self.min_trades_for_decision = 30  # Minimum de trades pour décider
        self.confidence_threshold = 0.75  # Seuil de confiance pour auto-apply
        self.rollback_threshold = -0.05  # Seuil de dégradation pour rollback
        
    def optimize_cycle(self) -> Dict:
        """
        Cycle d'optimisation appelé après chaque trade ou périodiquement.
        """
        # 1. Collecter les données récentes
        recent_trades = self.get_recent_trades(n=100)
        market_state = self.get_current_market_state()
        
        # 2. Analyser chaque paramètre
        parameter_analysis = {}
        for param in self.OPTIMIZABLE_PARAMS:
            analysis = self.analyze_parameter_impact(param, recent_trades)
            parameter_analysis[param] = analysis
        
        # 3. Calculer les suggestions d'optimisation
        suggestions = {}
        for param, analysis in parameter_analysis.items():
            suggestion = self.calculate_optimal_value(
                param=param,
                current_value=self.current_config[param],
                analysis=analysis,
                market_state=market_state
            )
            suggestions[param] = suggestion
        
        # 4. Scoring de confiance
        confidence_scores = self.calculate_confidence(suggestions, recent_trades)
        
        # 5. Décision d'application
        decisions = {}
        for param, suggestion in suggestions.items():
            confidence = confidence_scores[param]
            
            if confidence >= self.confidence_threshold:
                # Auto-apply avec adaptation graduelle
                new_value = self.gradual_adapt(
                    current=self.current_config[param],
                    target=suggestion['optimal_value'],
                    learning_rate=self.learning_rate * confidence
                )
                decisions[param] = {
                    'action': 'AUTO_APPLY',
                    'new_value': new_value,
                    'confidence': confidence,
                    'expected_impact': suggestion['expected_pnl_delta']
                }
            elif confidence >= 0.5:
                decisions[param] = {
                    'action': 'SUGGEST',
                    'suggested_value': suggestion['optimal_value'],
                    'confidence': confidence,
                    'reason': suggestion['reason']
                }
            else:
                decisions[param] = {
                    'action': 'HOLD',
                    'reason': 'Insufficient confidence',
                    'confidence': confidence
                }
        
        return {
            'timestamp': datetime.now(),
            'market_state': market_state,
            'analysis': parameter_analysis,
            'suggestions': suggestions,
            'decisions': decisions,
            'applied_changes': [d for d in decisions.values() if d['action'] == 'AUTO_APPLY']
        }
    
    def calculate_optimal_value(self, param: str, current_value: float, 
                                analysis: Dict, market_state: Dict) -> Dict:
        """
        Calcule la valeur optimale pour un paramètre donné.
        
        Utilise:
        - Performance historique à différentes valeurs
        - Conditions de marché actuelles
        - Gradient de performance
        """
        # Performance à différentes valeurs testées
        value_performance = analysis['value_performance_map']
        
        # Trouver le gradient de performance
        gradient = self.calculate_gradient(value_performance, current_value)
        
        # Ajuster selon les conditions de marché
        market_adjustment = self.get_market_adjustment(param, market_state)
        
        # Calculer la valeur optimale
        optimal_value = current_value + gradient * market_adjustment
        
        # Appliquer des bounds de sécurité (larges mais présents)
        bounds = self.PARAM_SAFETY_BOUNDS[param]
        optimal_value = max(bounds['min'], min(bounds['max'], optimal_value))
        
        # Calculer l'impact attendu
        expected_impact = self.estimate_pnl_impact(
            param, current_value, optimal_value, analysis
        )
        
        return {
            'current_value': current_value,
            'optimal_value': optimal_value,
            'gradient': gradient,
            'market_adjustment': market_adjustment,
            'expected_pnl_delta': expected_impact,
            'reason': self.generate_reason(param, current_value, optimal_value, analysis)
        }
    
    PARAM_SAFETY_BOUNDS = {
        'atr_mult_sl': {'min': 0.5, 'max': 3.0},
        'atr_mult_tp': {'min': 1.0, 'max': 6.0},
        'be_atr_mult': {'min': 0.2, 'max': 2.5},
        'trailing_trigger_mult': {'min': 0.5, 'max': 3.0},
        'stagnation_timeout': {'min': 60, 'max': 900},
    }
```

### 2.3 Système de Rollback Automatique

```python
class AdaptiveRollbackSystem:
    """
    Surveille la performance après les changements et rollback si nécessaire.
    """
    
    def __init__(self):
        self.change_history = []  # Historique des changements
        self.performance_baseline = {}  # Baseline avant changement
        self.rollback_threshold = -0.03  # -3% de dégradation = rollback
        
    def record_change(self, param: str, old_value: float, new_value: float):
        """Enregistre un changement de paramètre."""
        self.change_history.append({
            'timestamp': datetime.now(),
            'param': param,
            'old_value': old_value,
            'new_value': new_value,
            'baseline_metrics': self.capture_current_metrics()
        })
    
    def check_for_rollback(self) -> List[Dict]:
        """
        Vérifie si des changements récents ont dégradé la performance.
        """
        rollbacks_needed = []
        
        for change in self.change_history:
            if self.is_change_mature(change):  # Au moins 20 trades depuis
                current_metrics = self.capture_current_metrics()
                baseline = change['baseline_metrics']
                
                # Calculer la dégradation
                degradation = self.calculate_degradation(baseline, current_metrics)
                
                if degradation < self.rollback_threshold:
                    rollbacks_needed.append({
                        'param': change['param'],
                        'rollback_to': change['old_value'],
                        'current_value': change['new_value'],
                        'degradation': degradation,
                        'reason': f"Performance degraded by {degradation*100:.1f}%"
                    })
        
        return rollbacks_needed
    
    def calculate_degradation(self, baseline: Dict, current: Dict) -> float:
        """
        Calcule le score de dégradation composite.
        """
        weights = {
            'sharpe_ratio': 0.3,
            'profit_factor': 0.25,
            'avg_pnl': 0.25,
            'winrate': 0.2
        }
        
        degradation = 0
        for metric, weight in weights.items():
            if baseline[metric] != 0:
                delta = (current[metric] - baseline[metric]) / abs(baseline[metric])
                degradation += delta * weight
        
        return degradation
```

### 2.4 Multi-Objective Optimization

```python
class MultiObjectiveATROptimizer:
    """
    Optimisation multi-objectifs pour trouver le meilleur compromis.
    
    Objectifs:
    1. Maximiser le Profit Factor
    2. Maximiser le Sharpe Ratio
    3. Minimiser le Maximum Drawdown
    4. Maximiser le Winrate (secondaire)
    """
    
    def optimize(self, trades: List[Trade], constraints: Dict) -> List[Dict]:
        """
        Retourne le front de Pareto des configurations optimales.
        """
        # Définir l'espace de recherche
        search_space = {
            'atr_mult_sl': (0.6, 2.0),
            'atr_mult_tp': (1.5, 5.0),
            'be_atr_mult': (0.3, 2.0),
            'trailing_trigger': (0.5, 2.5),
            'stagnation_timeout': (120, 600),
        }
        
        # Générer des configurations candidates
        candidates = self.generate_candidates(search_space, n=1000)
        
        # Évaluer chaque configuration sur les trades historiques
        evaluations = []
        for config in candidates:
            metrics = self.evaluate_config(config, trades)
            evaluations.append({
                'config': config,
                'metrics': metrics,
                'dominated': False
            })
        
        # Trouver le front de Pareto (non-dominés)
        pareto_front = self.find_pareto_front(evaluations)
        
        # Classer par score composite
        for solution in pareto_front:
            solution['composite_score'] = self.composite_score(solution['metrics'])
        
        return sorted(pareto_front, key=lambda x: x['composite_score'], reverse=True)
    
    def composite_score(self, metrics: Dict) -> float:
        """Score composite pour ranking final."""
        return (
            metrics['profit_factor'] * 0.30 +
            metrics['sharpe_ratio'] * 0.30 +
            (1 - metrics['max_drawdown']) * 0.20 +  # Inverser car on minimise
            metrics['winrate'] * 0.20
        )
```

---

## 📈 PHASE 3: Dashboard & Reporting

### 3.1 Vue Synthétique Exécutive

```
┌────────────────────────────────────────────────────────────────────────┐
│ 🎯 ATR OPTIMIZER STATUS                                    [ACTIVE]   │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  CURRENT PERFORMANCE (vs Manual Baseline)                              │
│  ═══════════════════════════════════════                              │
│                                                                        │
│  Sharpe Ratio:    1.45  [████████████░░░░░░] +28% vs baseline         │
│  Profit Factor:   1.82  [███████████████░░░] +15% vs baseline         │
│  Max Drawdown:    2.1%  [██░░░░░░░░░░░░░░░░] -45% vs baseline         │
│  Winrate:         58%   [████████████░░░░░░] +8% vs baseline          │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ PARAMETER OPTIMIZATION STATUS                                    │ │
│  ├──────────────────────────────────────────────────────────────────┤ │
│  │                                                                  │ │
│  │  ATR Mult SL      1.35  [AUTO] ✅ Confidence: 89%               │ │
│  │  ATR Mult TP      2.80  [AUTO] ✅ Confidence: 82%               │ │
│  │  BE ATR Mult      0.70  [AUTO] ✅ Confidence: 91%               │ │
│  │  Trailing Mult    1.40  [SUGGEST] ⚠️ Confidence: 65%            │ │
│  │  Stagnation       420s  [HOLD] ℹ️ Confidence: 45%               │ │
│  │                                                                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  RECENT ADAPTATIONS (Last 24h)                                        │
│  ═════════════════════════════                                        │
│  • 14:32 - BE Mult: 1.0 → 0.85 (Auto) → +2.1% PnL improvement        │
│  • 09:15 - ATR SL: 1.2 → 1.35 (Auto) → Pending evaluation            │
│  • Yesterday - Trailing: 1.5 → 1.4 (Suggested, Applied manually)      │
│                                                                        │
│  ⚠️ ALERTS                                                            │
│  ═════════                                                            │
│  • Stagnation timeout may need increase (3 premature exits today)     │
│  • Consider disabling BE in trending markets (ADX > 35)               │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Rapport Hebdomadaire Automatique

```
═══════════════════════════════════════════════════════════════════════
                    ATR OPTIMIZATION WEEKLY REPORT
                        Week 49 (Dec 2-8, 2025)
═══════════════════════════════════════════════════════════════════════

EXECUTIVE SUMMARY
─────────────────
Total Trades: 847
Auto-Adaptations: 23
Suggested Changes: 8 (5 applied manually)
Rollbacks: 1 (BE Mult reverted from 0.6 to 0.7)

PERFORMANCE COMPARISON
──────────────────────
                    This Week    Last Week    Delta
Profit Factor:         1.78         1.52      +17.1%
Sharpe Ratio:          1.42         1.18      +20.3%
Avg PnL/Trade:       +0.14%       +0.09%     +55.6%
Winrate:              57.2%        54.8%      +4.4%
Max Drawdown:          2.3%         3.8%     -39.5%

PARAMETER EVOLUTION
───────────────────
                 Start of Week  End of Week  Changes  Impact
ATR Mult SL:          1.20          1.35      +3      +8.2% PF
ATR Mult TP:          3.00          2.80      -2      +5.1% PF
BE ATR Mult:          1.00          0.70      -4      +12.4% PF
Trailing Mult:        1.50          1.40      -2      +3.8% PF
Stagnation:           540s          420s      -2      +1.2% PF

KEY INSIGHTS
────────────
1. BE Mult reduction was the biggest performance driver this week
   → 0.70 captures 89% of potential gains vs 67% at 1.00
   
2. Tighter Trailing (1.4 vs 1.5) improved capture efficiency
   → But may underperform in trending markets (monitor next week)
   
3. ATR Mult SL increase to 1.35 reduced premature SL hits by 23%
   → Trade-off: slightly higher losses when SL is hit

RECOMMENDATIONS FOR NEXT WEEK
─────────────────────────────
• [HIGH] Consider market-regime-specific BE Mult
  - Current 0.70 optimal for ranging, but 0.50 better for volatile
  
• [MEDIUM] Test Trailing Mult 1.2 for choppy markets
  - Current 1.4 may be leaving money on the table
  
• [LOW] Stagnation timeout could be removed in trending regimes
  - 15% of exits during trends were premature

═══════════════════════════════════════════════════════════════════════
```

---

## 🔧 Implémentation Technique

### Architecture des Composants

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURE GLOBALE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    DATA LAYER                                 │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  • PostgreSQL: trade_atr_metrics, optimization_history       │  │
│  │  • Redis: Real-time metrics cache                            │  │
│  │  • Time-series: Price data for backtesting                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   ANALYSIS LAYER                              │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  • ATRParameterAnalyzer: Impact analysis per trade           │  │
│  │  • WhatIfSimulator: Alternative scenario calculation         │  │
│  │  • CorrelationEngine: Parameter/performance correlations     │  │
│  │  • MarketContextAnalyzer: Regime-specific insights           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  OPTIMIZATION LAYER                           │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  • ContinuousATROptimizer: Gradient-based optimization       │  │
│  │  • MultiObjectiveOptimizer: Pareto-optimal configs           │  │
│  │  • ConfidenceScorer: Decision confidence calculation         │  │
│  │  • RollbackManager: Automatic degradation detection          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   EXECUTION LAYER                             │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  • AutoApplyEngine: Automatic parameter updates              │  │
│  │  • SuggestionEmitter: Dashboard suggestions                  │  │
│  │  • AlertManager: Degradation/opportunity alerts              │  │
│  │  • ReportGenerator: Weekly/daily reports                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   FRONTEND LAYER                              │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  • ATROptimizerDashboard.svelte: Main monitoring UI          │  │
│  │  • ParameterHeatmap.svelte: Visual impact analysis           │  │
│  │  • OptimizationHistory.svelte: Change timeline               │  │
│  │  • WhatIfExplorer.svelte: Interactive scenario testing       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Roadmap d'Implémentation (Mise à jour post-audit)

#### 🔧 PRÉ-REQUIS (Phase 0) - Avant toute implémentation

| # | Action | Effort | Description |
|---|--------|--------|-------------|
| 0.1 | Ajouter `trailing_distance_atr_mult` | 2h | Nouveau paramètre dans config + position_manager + frontend |
| 0.2 | Supprimer toggles inutiles | 1h | Retirer `break_even_use_atr` et `trailing_use_atr_trigger` du code |
| 0.3 | Valider context tagging existe | 1h | Vérifier que `entry_adx`, `entry_atr_pct` sont loggés dans trades |

#### 📊 PHASE 1: Data Collection & Monitoring

| # | Composant | Effort | Priorité | Dépendances |
|---|-----------|--------|----------|-------------|
| 1.1 | Table SQL `trade_atr_metrics` | 2h | 🔴 HIGH | Phase 0 complète |
| 1.2 | Logger enrichi (capture 7 params + context) | 4h | 🔴 HIGH | 1.1 |
| 1.3 | WhatIfSimulator (calcul scénarios) | 8h | 🔴 HIGH | 1.2 |
| 1.4 | Context Clustering (regroupement par régime) | 4h | 🔴 HIGH | 1.2 |
| 1.5 | Dashboard Monitoring basique | 6h | 🟡 MEDIUM | 1.3 |
| 1.6 | CorrelationEngine | 4h | 🟡 MEDIUM | 1.3 |

#### 🤖 PHASE 2: Auto-Optimization

| # | Composant | Effort | Priorité | Dépendances |
|---|-----------|--------|----------|-------------|
| 2.1 | ContinuousATROptimizer (par cluster) | 12h | 🟡 MEDIUM | 1.4 |
| 2.2 | ConfidenceScorer | 4h | 🟡 MEDIUM | 2.1 |
| 2.3 | RollbackManager | 4h | 🟡 MEDIUM | 2.1 |
| 2.4 | AutoApplyEngine | 6h | 🟢 LOW | 2.2, 2.3 |

#### 📈 PHASE 3: Reporting & UI

| # | Composant | Effort | Priorité | Dépendances |
|---|-----------|--------|----------|-------------|
| 3.1 | Dashboard complet (heatmaps, history) | 8h | 🟢 LOW | 2.1 |
| 3.2 | ReportGenerator (weekly/daily) | 4h | 🟢 LOW | 2.1 |
| 3.3 | WhatIfExplorer UI (interactive) | 6h | 🟢 LOW | 1.3 |

#### 📅 Timeline Estimée

```
Phase 0: 4h  (Pré-requis code)
Phase 1: 28h (Data + Monitoring)
Phase 2: 26h (Auto-Optimization)
Phase 3: 18h (UI + Reports)
─────────────────────────────────
TOTAL:   76h (~10 jours dev)
```

#### 🎯 Checkpoints de Validation

| Checkpoint | Critère de succès |
|------------|-------------------|
| Fin Phase 0 | `trailing_distance_atr_mult` visible dans config + frontend |
| Fin Phase 1.3 | WhatIfSimulator calcule PnL alternatif pour 100 trades en <10s |
| Fin Phase 1.4 | Clusters identifiés: au moins 3 clusters avec >50 trades chacun |
| Fin Phase 2.1 | Optimiseur suggère des valeurs différentes par cluster |
| Fin Phase 2.4 | Premier auto-apply réussi avec rollback si dégradation |

---

## 🎯 Métriques de Succès

| Métrique | Baseline Actuel | Objectif Phase 1 | Objectif Phase 2 |
|----------|-----------------|------------------|------------------|
| Profit Factor | 1.35 | 1.60 (+18%) | 1.85 (+37%) |
| Sharpe Ratio | 1.10 | 1.35 (+23%) | 1.55 (+41%) |
| Max Drawdown | 4.5% | 3.0% (-33%) | 2.0% (-55%) |
| Winrate | 52% | 55% (+6%) | 58% (+12%) |
| Adaptation Time | Manuel | <4h | <30min (auto) |

---

**Ce document servira de référence pour l'implémentation future du système d'optimisation ATR.**

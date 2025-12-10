# 🧠 Brainstorming: Architecture ML Adaptative

> **Date:** 07/12/2025  
> **Status:** En discussion - Pas d'implémentation pour le moment  
> **Objectif:** Bot qui s'adapte au marché et optimise ses paramètres en continu

---

## 📍 Situation Actuelle

### Ce qui fonctionne
| Composant | Description | Status |
|-----------|-------------|--------|
| **GradientBoosting** | Modèle ML pour filtrer les trades par confiance | ✅ Actif |
| **Calibration Auto** | Ajustement automatique du seuil de confiance | ✅ Actif |
| **Règles Fixes** | Filtres ATR, Score, Volume, RSI, etc. | ✅ Actif |

### Ce qui a été codé mais N'EST PAS ACTIF
| Composant | Fichier | Raison |
|-----------|---------|--------|
| Shadow Trading L2 | `trading/live_order_manager_futures.py` | Non intégré au flux principal |
| Multi-Config Grid Search | `optimization/multi_config_backtest.py` | Script standalone, jamais lancé |
| CatBoost Trainer | `optimization/models/catboost_trainer.py` | Non connecté au système |

### Problème Identifié (07/12/2025)
- **Symptôme:** 0 trades pendant 8h (session du 06/12 soir)
- **Cause:** Paramètres trop restrictifs pour les conditions de marché (ATR min 0.55% alors que le marché était à 0.14%)
- **Solution temporaire:** Ajustement manuel des seuils après analyse SQL
- **Besoin:** Un système qui fait cette adaptation AUTOMATIQUEMENT

---

## 🎯 Objectif Cible

Un bot qui:
1. **Détecte** le régime de marché actuel (calme, normal, volatile)
2. **Adapte** ses paramètres de trading en conséquence
3. **Apprend** continuellement de ses trades pour s'améliorer
4. **Se remet en question** plutôt que de stagner sur une config fixe

---

## 🏗️ Options d'Architecture Discutées

### Option A: Optimisation Périodique des Seuils (Simple)
**Concept:** Un script qui tourne chaque nuit et ajuste les seuils.

```
┌─────────────────────────────────────────┐
│         DAILY OPTIMIZER (Nuit)          │
│                                         │
│  1. Récupère trades des 7 derniers jours│
│  2. Grid Search sur combinaisons seuils │
│  3. Trouve meilleure config             │
│  4. Met à jour config_overrides.json    │
└─────────────────────────────────────────┘
```

**Avantages:**
- Simple à implémenter
- Pas de risque en production
- Résultats interprétables

**Inconvénients:**
- Réactif, pas proactif (ajuste APRÈS les problèmes)
- Ne gère pas les changements intra-journaliers

---

### Option B: Sélecteur de Régime (Recommandé)
**Concept:** Un "Chef d'Orchestre" qui détecte le type de marché et charge la config appropriée.

```
┌──────────────────────────────────────────────────────────────┐
│              ARCHITECTURE NIVEAU 3                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  🎯 SÉLECTEUR DE RÉGIME (Nouveau - Toutes les 1-4h)    │ │
│  │                                                         │ │
│  │  Input: ATR moyen marché, Volatilité BTC, Volume global│ │
│  │                                                         │ │
│  │  Output: "CALME" | "NORMAL" | "VOLATILE"               │ │
│  │          → Charge config correspondante                 │ │
│  │          → Charge modèle ML spécialisé                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  📡 SCANNER (Existant)                                  │ │
│  │  Utilise seuils de la config active                    │ │
│  │  (ATR, Score, Volume adaptés au régime)                │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  🤖 JUGE ML (GradientBoosting ou Ensemble)             │ │
│  │  Modèle spécialisé par régime                          │ │
│  │  model_calme.pkl | model_normal.pkl | model_volatile   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Avantages:**
- Proactif: s'adapte AVANT que le problème n'arrive
- Modèles ML spécialisés = meilleure précision
- Configs optimisées pour chaque type de marché

**Inconvénients:**
- Plus complexe à mettre en place
- Nécessite de définir les régimes et leurs configs

---

### Option C: ML End-to-End (Ambitieux)
**Concept:** Le ML prend toutes les décisions, plus de règles fixes.

```
┌─────────────────────────────────────────┐
│         NEURAL NETWORK / TRANSFORMER    │
│                                         │
│  Input: Prix, Volume, Orderbook, etc.   │
│  Output: BUY / SELL / HOLD + Sizing     │
│                                         │
│  Pas de "Score", pas de seuils manuels  │
└─────────────────────────────────────────┘
```

**Avantages:**
- Peut découvrir des patterns invisibles aux règles
- Potentiel de performance supérieur

**Inconvénients:**
- Boîte noire totale
- Très difficile à débugger
- Risque d'overfit massif
- Nécessite énormément de données

---

## 🔬 Analyse des Modèles ML

### Comparatif des Options

| Modèle | Forces | Faiblesses | Adapté? |
|--------|--------|------------|---------|
| **XGBoost (Actuel)** | Robuste, éprouvé | Pas de temporel | ⭐⭐⭐ |
| **GradientBoosting (Actuel)** | Simple, rapide | Moins performant | ⭐⭐⭐ |
| **CatBoost** | Catégorielles, robust | Plus lent | ⭐⭐⭐⭐ |
| **LightGBM** | Ultra rapide | Moins stable | ⭐⭐⭐ |
| **Ensemble (XGB+Cat+LGBM)** | Robustesse maximale | Complexité | ⭐⭐⭐⭐⭐ |
| **TabPFN-v2** | Zero-shot, SOTA 2025 | Limité 10k samples | ⭐⭐⭐ |
| **Temporal Fusion Transformer** | Séquences temporelles | Très complexe | ⭐⭐⭐⭐ |

### Recommandation: Ensemble Hybride par Régime

```python
class HybridEnsemblePredictor:
    """
    Un modèle par régime de marché
    Chaque modèle = Ensemble de XGBoost + CatBoost + LightGBM
    """
    
    def __init__(self):
        self.models = {
            'calme': EnsembleModel(trained_on='low_volatility_trades'),
            'normal': EnsembleModel(trained_on='medium_volatility_trades'),
            'volatile': EnsembleModel(trained_on='high_volatility_trades'),
        }
    
    def predict(self, features, regime):
        return self.models[regime].predict(features)
```

---

## 📊 Données Découvertes (Session 07/12/2025)

### Insight #1: ATR Inversé
**Découverte:** Les trades avec ATR FAIBLE ont un MEILLEUR winrate!

| ATR Range | Winrate | PnL |
|-----------|---------|-----|
| < 0.15% | **60.0%** ✅ | +1.39% |
| 0.15-0.25% | 43.9% | +1.41% |
| 0.25-0.35% | 32.3% | -0.97% |
| 0.35-0.50% | **12.5%** ❌ | -2.08% |

→ **Implication:** Le bot doit ÉVITER les fortes volatilités, pas les chercher!

### Insight #2: Combinaison Optimale Trouvée
| Filtre | Trades | Winrate | PnL |
|--------|--------|---------|-----|
| ATR<0.26 + Score>=9 + Vol>=0.8 | 31 | **61.3%** | +3.26% |
| + ATR5m < 0.60 | 28 | 60.7% | +3.58% |
| + ADX >= 20 | 21 | **66.7%** | +2.78% |

### Insight #3: RSI par Direction
- **LONG RSI 50-60:** 62.5% winrate ✅
- **LONG RSI >= 70:** 33.3% winrate ❌
- **SHORT RSI < 40:** 42.4% winrate (meilleur pour shorts)

---

## 🛤️ Roadmap Proposée

### Phase 1: Fondations (1-2 semaines)
1. **Définir les régimes de marché**
   - Critères: ATR moyen, Volatilité BTC, Volume global
   - 3 régimes: CALME, NORMAL, VOLATILE

2. **Créer les configs par régime**
   - `config_regime_calme.json` (ATR<0.25, Score>=9, Vol>=0.8)
   - `config_regime_normal.json` (à déterminer via Grid Search)
   - `config_regime_volatile.json` (à déterminer)

3. **Créer le Sélecteur de Régime**
   - Module `core/market_regime_selector.py`
   - Calcul ATR moyen toutes les heures
   - Chargement dynamique de la config

### Phase 2: ML Spécialisé (2-3 semaines)
1. **Segmenter les données historiques par régime**
   - Requêtes SQL pour isoler trades par type de marché

2. **Entraîner un modèle par régime**
   - Utiliser l'infrastructure CatBoost existante
   - 3 modèles spécialisés

3. **Intégrer au Sélecteur**
   - Chargement dynamique du bon modèle

### Phase 3: Optimisation Continue (Ongoing)
1. **Daily Optimizer**
   - Script qui réoptimise les configs chaque nuit
   - Basé sur les 7 derniers jours de trades

2. **A/B Testing**
   - Comparer performance Ensemble vs GradientBoosting actuel

3. **Monitoring**
   - Dashboard pour suivre quel régime est actif
   - Alertes si le régime change

---

## ❓ Questions Ouvertes

1. **Fréquence de détection du régime?**
   - Toutes les heures? 4 heures? À chaque scan?

2. **Critères exacts pour définir les régimes?**
   - ATR seul suffit-il?
   - Faut-il inclure la tendance BTC?

3. **Comment gérer les transitions?**
   - Cooldown entre changements de régime?
   - Fermer les positions ouvertes au changement?

4. **Quel horizon pour l'entraînement ML?**
   - 7 jours? 30 jours? Fenêtre glissante?

5. **GradientBoosting actuel vs Ensemble?**
   - Migrer complètement ou A/B test d'abord?

---

## 📝 Notes de Session

### 07/12/2025 - Matin
- Découverte que les paramètres (ATR min 0.55%, Score 10) étaient trop restrictifs
- Analyse SQL a révélé que ATR FAIBLE = meilleur winrate
- Nouvelle config appliquée: ATR max 0.26%, Score 9, Vol 0.8
- Discussion sur architecture ML adaptative (Niveau 3)
- Décision: Rester en brainstorming, pas d'implémentation immédiate

---

## 🔧 FONCTIONNALITÉS DÉTAILLÉES

Chaque fonctionnalité est indépendante et peut être implémentée séparément.

---

### FONCTIONNALITÉ 1: Sélecteur de Régime de Marché ⭐ PRIORITÉ 1

**Objectif:** Adapter automatiquement les paramètres selon la volatilité du marché

**Problème résolu:** Éviter le cas du 06/12 (0 trades car config trop restrictive pour marché calme)

#### Données d'entrée (Runtime)
```
• ATR moyen 1m des 10 top paires (calculé toutes les heures)
• Volume moyen relatif
• (Optionnel) Tendance BTC
```

#### Logique de décision
```python
def detect_regime(avg_atr_1m):
    if avg_atr_1m < 0.20:
        return "CALME"
    elif avg_atr_1m < 0.50:
        return "NORMAL"
    else:
        return "VOLATILE"
```

#### Configs par régime (à créer)
| Régime | ATR max 1m | Score min | Vol min | ATR max 5m |
|--------|------------|-----------|---------|------------|
| CALME | 0.26 | 9 | 0.8 | 0.60 |
| NORMAL | 0.50 | 7.5 | 1.0 | 1.0 |
| VOLATILE | 1.0 | 6 | 1.2 | 1.5 |

#### Fichiers à créer/modifier
| Fichier | Action |
|---------|--------|
| `core/market_regime_selector.py` | **CRÉER** - Logique de détection |
| `config/regime_calme.json` | **CRÉER** - Config optimisée calme |
| `config/regime_normal.json` | **CRÉER** - Config optimisée normal |
| `config/regime_volatile.json` | **CRÉER** - Config optimisée volatile |
| `main.py` | **MODIFIER** - Appeler le sélecteur toutes les heures |
| `utils/config_persistence.py` | **MODIFIER** - Fonction pour charger config par régime |

#### Implémentation suggérée
```python
# core/market_regime_selector.py

class MarketRegimeSelector:
    def __init__(self, exchange, config_manager):
        self.exchange = exchange
        self.config_manager = config_manager
        self.current_regime = None
        self.last_check = None
        
    async def check_and_update_regime(self):
        """Appelé toutes les heures depuis main.py"""
        avg_atr = await self._calculate_market_atr()
        new_regime = self._detect_regime(avg_atr)
        
        if new_regime != self.current_regime:
            logger.info(f"🔄 Changement de régime: {self.current_regime} → {new_regime}")
            self._load_regime_config(new_regime)
            self.current_regime = new_regime
            
    def _detect_regime(self, avg_atr):
        if avg_atr < 0.20:
            return "CALME"
        elif avg_atr < 0.50:
            return "NORMAL"
        return "VOLATILE"
        
    def _load_regime_config(self, regime):
        config_file = f"config/regime_{regime.lower()}.json"
        # Charger et appliquer à config_overrides
```

#### Tests de validation
```sql
-- Après implémentation, vérifier que le régime détecté correspond à l'ATR
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    ROUND(AVG(atr_pct_1m)::numeric, 3) as avg_atr,
    CASE 
        WHEN AVG(atr_pct_1m) < 0.20 THEN 'CALME'
        WHEN AVG(atr_pct_1m) < 0.50 THEN 'NORMAL'
        ELSE 'VOLATILE'
    END as expected_regime
FROM scan_logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY 1
ORDER BY 1 DESC;
```

#### Dépendances
- Aucune (peut être implémenté en premier)

#### Estimation
- **Complexité:** Moyenne
- **Temps:** 2-3 heures
- **Risque:** Faible

---

### FONCTIONNALITÉ 2: Circuit Breaker (Auto-Pause) ⭐ PRIORITÉ 2

**Objectif:** Protéger le capital pendant les mauvaises séries

**Problème résolu:** Éviter de creuser quand "rien ne marche"

#### Règles de déclenchement
| Condition | Action | Durée |
|-----------|--------|-------|
| 3 losses consécutifs | Score min +1 | Jusqu'à 1 win |
| 5 losses consécutifs | PAUSE trading | 30 min |
| Drawdown > 2% journée | PAUSE trading | 2h |
| Drawdown > 5% journée | STOP journée | Jusqu'au lendemain |

#### Données d'entrée (Runtime)
```
• Historique trades de la session (depuis minuit)
• PnL cumulé journalier
• Série W/L en cours
```

#### Fichiers à créer/modifier
| Fichier | Action |
|---------|--------|
| `core/circuit_breaker.py` | **CRÉER** - Logique de protection |
| `core/callbacks/scanner_loop.py` | **MODIFIER** - Vérifier circuit breaker avant trade |
| `main.py` | **MODIFIER** - Initialiser et mettre à jour le circuit breaker |

#### Implémentation suggérée
```python
# core/circuit_breaker.py

class CircuitBreaker:
    def __init__(self, config):
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.paused_until = None
        self.score_boost = 0  # Ajouté au score minimum
        
    def on_trade_closed(self, trade_result):
        """Appelé après chaque trade fermé"""
        self.daily_pnl += trade_result.pnl_pct
        
        if trade_result.win:
            self.consecutive_losses = 0
            self.score_boost = max(0, self.score_boost - 1)
        else:
            self.consecutive_losses += 1
            self._check_triggers()
            
    def _check_triggers(self):
        if self.consecutive_losses >= 5:
            self.paused_until = datetime.now() + timedelta(minutes=30)
            logger.warning("⚠️ Circuit Breaker: PAUSE 30min (5 losses)")
        elif self.consecutive_losses >= 3:
            self.score_boost = 1
            logger.info("⚠️ Circuit Breaker: Score min +1 (3 losses)")
            
        if self.daily_pnl <= -2.0:
            self.paused_until = datetime.now() + timedelta(hours=2)
            logger.warning("⚠️ Circuit Breaker: PAUSE 2h (Drawdown 2%)")
            
    def can_trade(self) -> bool:
        if self.paused_until and datetime.now() < self.paused_until:
            return False
        return True
        
    def get_adjusted_min_score(self, base_min_score: float) -> float:
        return base_min_score + self.score_boost
```

#### Dépendances
- Aucune (peut être implémenté indépendamment)

#### Estimation
- **Complexité:** Faible
- **Temps:** 1-2 heures
- **Risque:** Très faible

---

### FONCTIONNALITÉ 3: Filtre Horaire Intelligent ⭐ PRIORITÉ 3

**Objectif:** Éviter de trader aux heures historiquement perdantes

**Constat du 07/12:** Heures 7h, 10h, 17h = 0% winrate

#### Logique
```
• Analyse hebdomadaire des trades par heure (0-23)
• Si winrate < 35% sur 10+ trades → Heure blacklistée
• Ou: Score minimum majoré pour heures à risque
```

#### Mode de fonctionnement
| Mode | Comportement |
|------|--------------|
| **BLACKLIST** | Aucun trade pendant ces heures |
| **PRUDENT** | Score min +2 pendant ces heures |

#### Fichiers à créer/modifier
| Fichier | Action |
|---------|--------|
| `core/hourly_filter.py` | **CRÉER** - Analyse et filtre horaire |
| `scripts/update_hourly_stats.py` | **CRÉER** - Script nocturne de mise à jour |
| `core/callbacks/scanner_loop.py` | **MODIFIER** - Vérifier filtre horaire |

#### Données stockées
```json
// data/hourly_stats.json (mis à jour chaque nuit)
{
    "last_updated": "2025-12-07T03:00:00",
    "hours": {
        "0": {"trades": 45, "winrate": 42.2, "status": "OK"},
        "7": {"trades": 12, "winrate": 8.3, "status": "BLACKLIST"},
        "10": {"trades": 18, "winrate": 5.5, "status": "BLACKLIST"},
        "17": {"trades": 15, "winrate": 13.3, "status": "PRUDENT"}
    }
}
```

#### Script de mise à jour (nocturne)
```sql
-- Script qui tourne chaque nuit pour calculer stats horaires
SELECT 
    EXTRACT(HOUR FROM timestamp_entry) as hour,
    COUNT(*) as trades,
    ROUND(100.0 * SUM(CASE WHEN win THEN 1 ELSE 0 END) / COUNT(*), 1) as winrate
FROM trades
WHERE timestamp_entry > NOW() - INTERVAL '7 days'
GROUP BY 1
HAVING COUNT(*) >= 5
ORDER BY 1;
```

#### Dépendances
- Aucune

#### Estimation
- **Complexité:** Faible
- **Temps:** 1-2 heures
- **Risque:** Faible

---

### FONCTIONNALITÉ 4: Score Pair Dynamique ⭐ PRIORITÉ 4

**Objectif:** Favoriser les paires qui performent historiquement bien

#### Logique
```
• Analyse hebdomadaire des trades par paire
• Calcul d'un bonus/malus basé sur winrate + PnL
• Score final = score_base + pair_bonus
```

#### Calcul du bonus
```python
def calculate_pair_bonus(winrate, pnl_avg, trades_count):
    if trades_count < 10:
        return 0  # Pas assez de données
    
    # Bonus basé sur winrate (vs moyenne 40%)
    wr_bonus = (winrate - 40) / 10  # +1 pour chaque 10% au-dessus de 40%
    
    # Bonus basé sur PnL moyen (vs moyenne 0.05%)
    pnl_bonus = (pnl_avg - 0.05) / 0.1  # +1 pour chaque 0.1% au-dessus de 0.05%
    
    # Combiné et borné
    return max(-2, min(2, (wr_bonus + pnl_bonus) / 2))
```

#### Données stockées
```json
// data/pair_scores.json
{
    "last_updated": "2025-12-07T03:00:00",
    "pairs": {
        "ZEC/USDT:USDT": {"trades": 45, "winrate": 52.3, "pnl_avg": 0.12, "bonus": 1.5},
        "SHIB/USDT:USDT": {"trades": 32, "winrate": 28.1, "pnl_avg": -0.08, "bonus": -1.0},
        "SUI/USDT:USDT": {"trades": 38, "winrate": 44.7, "pnl_avg": 0.06, "bonus": 0.5}
    }
}
```

#### Fichiers à créer/modifier
| Fichier | Action |
|---------|--------|
| `core/pair_scorer.py` | **CRÉER** - Gestion des scores par paire |
| `scripts/update_pair_scores.py` | **CRÉER** - Script nocturne |
| `core/callbacks/scanner_loop.py` | **MODIFIER** - Appliquer bonus au score |

#### Dépendances
- Aucune

#### Estimation
- **Complexité:** Faible
- **Temps:** 1-2 heures
- **Risque:** Faible

---

### FONCTIONNALITÉ 5: Momentum BTC ⭐ PRIORITÉ 5

**Objectif:** Adapter la stratégie selon le comportement de BTC

#### Logique
```
• Si BTC pump > 2% en 1h → Mode "LONG only" ou "Follow trend"
• Si BTC dump > 2% en 1h → Mode "SHORT only" ou "Pause"
• Si BTC flat → Mode normal
```

#### Données d'entrée (Runtime)
```
• Prix BTC actuel
• Prix BTC il y a 1h, 4h, 24h
• ATR BTC
```

#### Modes de réaction
| Mouvement BTC | Action suggérée |
|---------------|-----------------|
| +3% en 1h | LONG only, Score min -1 |
| +1-3% en 1h | Favoriser LONG (bonus +1) |
| -1% à +1% | Normal |
| -1 à -3% en 1h | Favoriser SHORT (bonus +1) |
| -3% en 1h | SHORT only ou PAUSE |

#### Fichiers à créer/modifier
| Fichier | Action |
|---------|--------|
| `core/btc_momentum.py` | **CRÉER** - Calcul momentum BTC |
| `core/market_regime_selector.py` | **MODIFIER** - Intégrer momentum dans décision |

#### Implémentation suggérée
```python
# core/btc_momentum.py

class BTCMomentum:
    def __init__(self, exchange):
        self.exchange = exchange
        self.price_history = []  # [(timestamp, price), ...]
        
    async def get_btc_momentum(self) -> dict:
        current_price = await self._get_btc_price()
        
        delta_1h = self._calculate_delta(hours=1)
        delta_4h = self._calculate_delta(hours=4)
        
        return {
            "delta_1h": delta_1h,
            "delta_4h": delta_4h,
            "mode": self._determine_mode(delta_1h),
            "direction_filter": self._get_direction_filter(delta_1h)
        }
        
    def _determine_mode(self, delta_1h):
        if delta_1h > 3.0:
            return "PUMP"
        elif delta_1h < -3.0:
            return "DUMP"
        elif abs(delta_1h) > 1.0:
            return "TRENDING"
        return "FLAT"
        
    def _get_direction_filter(self, delta_1h):
        if delta_1h > 3.0:
            return "LONG_ONLY"
        elif delta_1h < -3.0:
            return "SHORT_ONLY"  # ou "PAUSE"
        return None  # Pas de filtre
```

#### Dépendances
- **Sélecteur de Régime** (pour intégration)

#### Estimation
- **Complexité:** Moyenne
- **Temps:** 2-3 heures
- **Risque:** Moyen (peut filtrer de bons trades)

---

### FONCTIONNALITÉ 6: Voting Ensemble ML ⭐ PRIORITÉ 6

**Objectif:** Améliorer la fiabilité des prédictions ML

#### Architecture actuelle
```
Setup → GradientBoosting → Confiance → Trade/Reject
```

#### Architecture proposée
```
Setup → GradientBoosting ──┐
      → CatBoost ──────────┼→ Vote → Trade/Reject
      → LightGBM ──────────┘
```

#### Règles de vote
| Votes positifs | Action |
|----------------|--------|
| 3/3 | Trade avec confiance HAUTE |
| 2/3 | Trade avec confiance NORMALE |
| 1/3 | Reject |
| 0/3 | Reject |

#### Fichiers à créer/modifier
| Fichier | Action |
|---------|--------|
| `optimization/models/ensemble_predictor.py` | **CRÉER** - Orchestrateur des modèles |
| `optimization/models/lightgbm_trainer.py` | **CRÉER** - Trainer LightGBM |
| `api/routes/ml.py` | **MODIFIER** - Endpoint pour ensemble |

#### Implémentation suggérée
```python
# optimization/models/ensemble_predictor.py

class EnsemblePredictor:
    def __init__(self):
        self.models = {
            'gradient_boosting': load_model('best_classifier_latest.pkl'),
            'catboost': load_model('catboost_model.pkl'),
            'lightgbm': load_model('lightgbm_model.pkl'),
        }
        self.weights = {'gradient_boosting': 0.4, 'catboost': 0.35, 'lightgbm': 0.25}
        
    def predict(self, features) -> dict:
        votes = {}
        confidences = {}
        
        for name, model in self.models.items():
            proba = model.predict_proba(features)[0][1]
            confidences[name] = proba
            votes[name] = proba > 0.5
            
        positive_votes = sum(votes.values())
        weighted_confidence = sum(
            confidences[name] * self.weights[name] 
            for name in self.models
        )
        
        return {
            'votes': positive_votes,
            'decision': positive_votes >= 2,
            'confidence': weighted_confidence,
            'details': confidences
        }
```

#### Dépendances
- CatBoost installé (`pip install catboost`)
- LightGBM installé (`pip install lightgbm`)
- Modèles entraînés

#### Estimation
- **Complexité:** Moyenne
- **Temps:** 3-4 heures (incluant entraînement des modèles)
- **Risque:** Faible

---

### FONCTIONNALITÉ 7: Drift Detector ⭐ PRIORITÉ 7

**Objectif:** Détecter quand le modèle ML devient obsolète

#### Logique
```
• Compare winrate prédit vs winrate réel (glissant 7 jours)
• Si écart > 10% → Alerte
• Si écart > 20% → Suggestion de ré-entraînement
```

#### Métriques surveillées
| Métrique | Seuil alerte | Seuil critique |
|----------|--------------|----------------|
| Écart winrate | 10% | 20% |
| Écart confiance moyenne | 15% | 25% |
| Distribution features | Kolmogorov-Smirnov > 0.1 | > 0.2 |

#### Fichiers à créer/modifier
| Fichier | Action |
|---------|--------|
| `monitoring/drift_detector.py` | **CRÉER** - Logique de détection |
| `scripts/check_drift.py` | **CRÉER** - Script quotidien |
| `utils/telegram_notifications.py` | **MODIFIER** - Ajouter alertes drift |

#### Implémentation suggérée
```python
# monitoring/drift_detector.py

class DriftDetector:
    def __init__(self, db_connection):
        self.db = db_connection
        
    def check_prediction_drift(self, days=7) -> dict:
        # Récupère trades récents avec prédictions
        trades = self._get_recent_trades(days)
        
        # Calcule winrate prédit (moyenne des confidences)
        predicted_wr = trades['ml_confidence'].mean() * 100
        
        # Calcule winrate réel
        actual_wr = trades['win'].mean() * 100
        
        drift = abs(predicted_wr - actual_wr)
        
        return {
            'predicted_winrate': predicted_wr,
            'actual_winrate': actual_wr,
            'drift': drift,
            'status': 'OK' if drift < 10 else ('ALERT' if drift < 20 else 'CRITICAL')
        }
        
    def check_feature_drift(self, days=7) -> dict:
        # Compare distribution features récentes vs training
        # Utilise test Kolmogorov-Smirnov
        pass
```

#### Dépendances
- Colonne `ml_confidence` dans table trades (déjà présente)
- scipy pour tests statistiques

#### Estimation
- **Complexité:** Haute
- **Temps:** 3-4 heures
- **Risque:** Faible (monitoring seulement)

---

### FONCTIONNALITÉ 8: Optimiseur Nocturne ⭐ (Inclus dans Priorité 1)

**Objectif:** Mettre à jour automatiquement les configs par régime

#### Logique
```
Chaque nuit à 3h:
1. Analyse trades des 7 derniers jours
2. Pour chaque régime (CALME, NORMAL, VOLATILE):
   - Filtre trades de ce régime
   - Grid search sur combinaisons de seuils
   - Trouve config optimale
3. Sauvegarde les 3 configs
4. (Optionnel) Ré-entraîne modèles ML
```

#### Script nocturne
```python
# scripts/nightly_optimizer.py

async def run_nightly_optimization():
    logger.info("🌙 Début optimisation nocturne")
    
    for regime in ['CALME', 'NORMAL', 'VOLATILE']:
        trades = get_trades_by_regime(regime, days=7)
        
        if len(trades) < 20:
            logger.info(f"Pas assez de trades pour {regime}")
            continue
            
        best_config = grid_search_optimal_config(trades)
        save_regime_config(regime, best_config)
        
        logger.info(f"✅ Config {regime} mise à jour: {best_config}")
    
    # Optionnel: ré-entraînement ML
    if should_retrain():
        await retrain_ml_models()
```

#### Planification
- Windows: Task Scheduler
- Linux: Cron `0 3 * * * python scripts/nightly_optimizer.py`

---

## 📋 PLAN D'IMPLÉMENTATION PROGRESSIF

### Sprint 1 (Cette semaine)
- [ ] **Fonctionnalité 1:** Sélecteur de Régime
- [ ] **Fonctionnalité 2:** Circuit Breaker

### Sprint 2 (Semaine prochaine)
- [ ] **Fonctionnalité 3:** Filtre Horaire
- [ ] **Fonctionnalité 4:** Score Pair Dynamique

### Sprint 3
- [ ] **Fonctionnalité 5:** Momentum BTC
- [ ] **Fonctionnalité 8:** Optimiseur Nocturne

### Sprint 4
- [ ] **Fonctionnalité 6:** Voting Ensemble ML
- [ ] **Fonctionnalité 7:** Drift Detector

---

## 📝 Notes de Session

### 07/12/2025 - Matin
- Découverte que les paramètres (ATR min 0.55%, Score 10) étaient trop restrictifs
- Analyse SQL a révélé que ATR FAIBLE = meilleur winrate
- Nouvelle config appliquée: ATR max 0.26%, Score 9, Vol 0.8
- Discussion sur architecture ML adaptative (Niveau 3)
- Choix: Architecture 100% Live (pas de simulation)
- Définition de 8 fonctionnalités complémentaires
- Plan d'implémentation progressif établi

---

*Document vivant - À mettre à jour après chaque session de brainstorming*

# Sprint 1 - Market Regime Selector & Trading Circuit Breaker

## Vue d'ensemble

Sprint 1 ajoute deux mécanismes de protection et d'adaptation au bot de trading :

1. **Market Regime Selector** - Adapte automatiquement les paramètres selon le régime de marché
2. **Trading Circuit Breaker** - Protège le capital en cas de séries de pertes

---

## 1. Market Regime Selector

### Principe de fonctionnement

Le régime de marché est déterminé par l'analyse de **l'ATR moyen** (Average True Range) et **l'ADX** (Average Directional Index) des 10 meilleures paires.

```
┌──────────────────────────────────────────────────────────────┐
│                    DÉTECTION DU RÉGIME                       │
├──────────────────────────────────────────────────────────────┤
│  ADX < 20 ?                                                  │
│     → OUI: Régime CHOPPY (marché sans direction)             │
│     → NON: Continuer avec ATR                                │
│                                                              │
│  ATR moyen:                                                  │
│     0.00% - 0.20%  →  CALME     (faible volatilité)         │
│     0.20% - 0.40%  →  NORMAL    (volatilité standard)       │
│     0.40% +        →  VOLATILE  (haute volatilité)          │
└──────────────────────────────────────────────────────────────┘
```

### Configurations par régime

| Régime    | min_score | SL mult | TP mult | Interprétation |
|-----------|-----------|---------|---------|----------------|
| CALME     | 6.0       | 1.0x    | 2.5x    | Marché lent, opportunités rares mais fiables |
| NORMAL    | 7.0       | 1.2x    | 3.0x    | Conditions optimales pour le trading |
| VOLATILE  | 8.0       | 1.5x    | 4.0x    | Risque élevé, setups de haute qualité requis |
| CHOPPY    | 9.0       | 0.8x    | 2.0x    | Marché indécis, exigences maximales |

### Flux d'exécution

```
┌─────────────────────────────────────────────────────────────┐
│                    SCANNER LOOP (main.py)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Récupérer top_pairs                                     │
│                                                             │
│  2. ┌──────────────────────────────────────────────────┐    │
│     │  VÉRIFICATION RÉGIME                              │    │
│     │  - Extraire ATR et ADX des top 10 paires         │    │
│     │  - Appeler check_regime(atr_values, adx_values)  │    │
│     │  - Si changement: émettre 'regime_changed' (WS)  │    │
│     │  - Charger nouvelle config régime                │    │
│     └──────────────────────────────────────────────────┘    │
│                                                             │
│  3. Scanner les paires pour setups...                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Fichiers

| Fichier | Description |
|---------|-------------|
| `core/market_regime_selector.py` | Classe `MarketRegimeSelector` |
| `config/regimes/calme.json` | Config régime CALME |
| `config/regimes/normal.json` | Config régime NORMAL |
| `config/regimes/volatile.json` | Config régime VOLATILE |
| `config/regimes/choppy.json` | Config régime CHOPPY |

---

## 2. Trading Circuit Breaker

### Principe de fonctionnement

Le Circuit Breaker protège le capital en :
1. **Comptant les pertes consécutives** - Pause après N pertes
2. **Surveillant le drawdown journalier** - Pause/Stop selon seuils
3. **Augmentant les exigences** - Score boost après pertes

### États du Circuit Breaker

```
┌────────────────────────────────────────────────────────────────┐
│                   ÉTATS DU CIRCUIT BREAKER                     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ACTIVE ─────────────────────────────────────────────────────  │
│     │                                                          │
│     │ N pertes consécutives OU drawdown > seuil_pause          │
│     ▼                                                          │
│  PAUSED ─────────────────────────────────────────────────────  │
│     │                                                          │
│     │ Timeout expiré OU reset manuel                           │
│     ▼                                                          │
│  ACTIVE (retour)                                               │
│                                                                │
│  OU                                                            │
│                                                                │
│  ACTIVE ─────────────────────────────────────────────────────  │
│     │                                                          │
│     │ Drawdown > seuil_stop (critique)                         │
│     ▼                                                          │
│  STOPPED ─────────────────────────────────────────────────────  │
│     │                                                          │
│     │ Reset manuel UNIQUEMENT                                  │
│     ▼                                                          │
│  ACTIVE                                                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Seuils par défaut

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| `max_consecutive_losses` | 5 | Nombre de pertes avant pause |
| `daily_drawdown_pause_pct` | -2.0% | Drawdown pour pause temporaire |
| `daily_drawdown_stop_pct` | -5.0% | Drawdown pour arrêt complet |
| `pause_duration_minutes` | 30 | Durée pause automatique |
| `score_boost_per_loss` | 0.5 | Boost score par perte consécutive |

### Score Boost

Après des pertes consécutives, le score minimum requis augmente :

```
Pertes consécutives: 0  → score_boost = 0.0
Pertes consécutives: 1  → score_boost = 0.5
Pertes consécutives: 2  → score_boost = 1.0
Pertes consécutives: 3  → score_boost = 1.5 (+ PAUSE)
```

**Exemple** : Si `min_score_required = 7.0` et 2 pertes consécutives :
- Score minimum ajusté = 7.0 + 1.0 = **8.0**
- Setup avec score 7.5 sera **rejeté** jusqu'à un win

### Flux d'exécution

```
┌─────────────────────────────────────────────────────────────────┐
│                     SCANNER LOOP (main.py)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. ┌────────────────────────────────────────────────────────┐  │
│     │  VÉRIFICATION CAN_TRADE()                               │  │
│     │  - Si False: SKIP scanner, log warning, return         │  │
│     │  - Émettre 'circuit_breaker_trading_update' (WS)       │  │
│     └────────────────────────────────────────────────────────┘  │
│                                                                 │
│  2. Scanner paires, trouver setup valide...                     │
│                                                                 │
│  3. ┌────────────────────────────────────────────────────────┐  │
│     │  VÉRIFICATION SCORE_BOOST                               │  │
│     │  - Récupérer score_boost depuis CB                     │  │
│     │  - Si score_boost > 0:                                 │  │
│     │      adjusted_min = min_score + score_boost            │  │
│     │      Si setup_score < adjusted_min: SKIP setup         │  │
│     └────────────────────────────────────────────────────────┘  │
│                                                                 │
│  4. Ouvrir position...                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 POSITION MANAGER (close_position)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Calculer PnL net...                                         │
│                                                                 │
│  2. ┌────────────────────────────────────────────────────────┐  │
│     │  ENREGISTRER TRADE DANS CB                              │  │
│     │  trading_cb.record_trade(symbol, pnl_pct, pnl_usdt)    │  │
│     │                                                         │  │
│     │  - Si WIN: reset consecutive_losses                    │  │
│     │  - Si LOSS: increment consecutive_losses               │  │
│     │  - Évaluer conditions pause/stop                       │  │
│     └────────────────────────────────────────────────────────┘  │
│                                                                 │
│  3. Return result                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Fichiers

| Fichier | Description |
|---------|-------------|
| `core/trading_circuit_breaker.py` | Classe `TradingCircuitBreaker` |
| `api/regime_endpoints.py` | Endpoints API (status, reset, config) |

---

## 3. API Endpoints

### Market Regime

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/regime/status` | État actuel du régime |
| POST | `/api/regime/force-check` | Forcer vérification |
| GET | `/api/regime/history` | Historique des changements |
| GET | `/api/regime/thresholds` | Seuils par régime |
| POST | `/api/regime/thresholds` | Modifier seuils |

### Trading Circuit Breaker

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/circuit-breaker/trading/status` | État actuel CB |
| POST | `/api/circuit-breaker/trading/reset` | Reset manuel |
| GET | `/api/circuit-breaker/trading/events` | Historique événements |
| POST | `/api/circuit-breaker/trading/config` | Modifier config |

---

## 4. Frontend - Dashboard

Les widgets sont intégrés dans l'onglet Dashboard :

```
┌─────────────────────────────────────────────────────────────────┐
│                         DASHBOARD                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │   🤖 Bot Controls    │  │   📊 Session Stats   │            │
│  └──────────────────────┘  └──────────────────────┘            │
│                                                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │ 🌡️ MARKET REGIME     │  │ 🛑 CIRCUIT BREAKER  │  ← SPRINT 1│
│  │                      │  │                      │            │
│  │  Régime: CALME 🟢    │  │  État: ACTIF ✅      │            │
│  │  ATR: 0.15% | ADX:24 │  │  Losses: 2/5        │            │
│  │                      │  │  PnL jour: +1.2%    │            │
│  │  [🔄 Vérifier]       │  │  Score+: +1.0       │            │
│  │                      │  │  [🔄 Reset]         │            │
│  └──────────────────────┘  └──────────────────────┘            │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  🎯 Mode TP/SL: [ATR ▼]                                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │   Position Card      │  │   Scanner Panel      │            │
│  └──────────────────────┘  └──────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### Composants Svelte

| Fichier | Description |
|---------|-------------|
| `MarketRegimeWidget.svelte` | Widget régime avec couleurs dynamiques |
| `TradingCircuitBreaker.svelte` | Widget CB avec countdown |

---

## 5. WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `regime_changed` | Server → Client | Nouveau régime détecté |
| `circuit_breaker_trading_update` | Server → Client | État CB mis à jour |
| `circuit_breaker_trading_pause` | Server → Client | CB en pause |
| `circuit_breaker_trading_resume` | Server → Client | CB reprise |

---

## 6. Tests

Exécuter les tests :

```bash
python scripts/test_sprint1_integration.py
```

Tests couverts :
- ✅ Market Regime Selector (détection régimes)
- ✅ Trading Circuit Breaker (pause, stop, reset)
- ✅ API Endpoints (toutes les routes)
- ✅ Config Files (validation JSON)
- ✅ main.py Integration
- ✅ position_manager.py Integration

---

## 7. Logs à surveiller

### Market Regime
```
🌡️ Régime changé: VOLATILE | ATR: 0.520% | ADX: 32
```

### Circuit Breaker
```
🛑 Scanner ignoré : Circuit Breaker PAUSED | Raison: 5 pertes consécutives | Reprise dans: 1200s
🛑 Trading Circuit Breaker activé après trade BTCUSDT | État: PAUSED | Raison: 5 pertes consécutives
⚠️ BTCUSDT - Setup rejeté par Circuit Breaker score boost: Score 7.5 < 8.5 (min: 7.0 + boost: 1.5)
```

---

## Résumé

Sprint 1 ajoute une **double protection** :

1. **Adaptation au marché** - Le bot ajuste ses paramètres selon les conditions (CALME → agressif, VOLATILE → conservateur)

2. **Protection du capital** - En cas de série noire, le bot :
   - Augmente ses exigences (score boost)
   - Se met en pause temporaire (pertes consécutives)
   - S'arrête complètement (drawdown critique)

Ces mécanismes fonctionnent **automatiquement** sans intervention manuelle, mais peuvent être contrôlés via le Dashboard ou l'API.

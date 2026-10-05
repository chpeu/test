# Post-Exit Analysis & ML Dynamic Parameters System

> **Version:** 2.0 | **Date:** 2026-01-19 | **Status:** ✅ Phase 1 IMPLÉMENTÉE
> 
> **Relation projet:** Intégré au `project_regime_atr_optimization` (Phase 2H+)

---

## 📋 Vue d'ensemble

Système de suivi des prix après clôture pour:
1. **Analyser l'optimalité des sorties** (exit efficiency)
2. **Alimenter un ML** qui prédit les paramètres optimaux par trade
3. **Adapter dynamiquement** les variables du mode FIXE selon le contexte
4. **🆕 Alimenter le Regime ATR Optimizer** avec des targets précis par régime

---

## 🔗 Relation avec `project_regime_atr_optimization`

### Architecture commune

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    REGIME ATR OPTIMIZATION PROJECT                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ NIVEAU 1: RÉGIME (Contexte)                                      │       │
│  │ "Dans quel régime sommes-nous?" → CALME|NORMAL|VOLATILE         │       │
│  └───────────────────────────────┬─────────────────────────────────┘       │
│                                  │                                          │
│  ┌───────────────────────────────▼─────────────────────────────────┐       │
│  │ NIVEAU 2: ENTRY ML (Décision)                                    │       │
│  │ "Dois-je entrer?" → Score confiance 72%                         │       │
│  └───────────────────────────────┬─────────────────────────────────┘       │
│                                  │                                          │
│  ┌───────────────────────────────▼─────────────────────────────────┐       │
│  │ NIVEAU 3: PARAM OPTIMIZER (Exécution)          ← POST-EXIT      │       │
│  │ "Quels TP/SL/BE/Trailing?" → sl=0.15%, trailing_trigger=0.2%   │       │
│  │                                                                  │       │
│  │  📊 POST-EXIT ANALYSIS fournit les TARGETS pour ce niveau       │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Intégration avec les phases du projet Regime ATR

| Phase Regime ATR | Utilisation Post-Exit | Description |
|------------------|----------------------|-------------|
| **Phase 2D** (ML Param Optimizer) | ✅ Targets ML | Fournit `ml_optimal_sl_pct`, `ml_optimal_trailing_trigger` |
| **Phase 2F** (Trailing MFE Protection) | ✅ Validation | Données post-exit valident l'efficacité du trailing MFE |
| **Phase 2G** (ML Monitor) | ✅ Métriques | `exit_efficiency_pct`, `regret_pct` dans dashboard |
| **Phase 3A** (Mixture-of-Experts) | ✅ Training par régime | Targets post-exit segmentés par `entry_market_regime` |

### Flux de données

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   TRADE      │────►│  POST-EXIT   │────►│  TARGETS ML  │
│   FERMÉ      │     │  TRACKING    │     │  CALCULÉS    │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
     ┌────────────────────────────────────────────┼────────────────┐
     │                                            ▼                │
     │  ┌──────────────────┐    ┌──────────────────┐              │
     │  │ ML PARAM         │◄───│ FEATURE JOIN:    │              │
     │  │ OPTIMIZER        │    │ - entry_atr      │              │
     │  │ (Phase 2D)       │    │ - market_regime  │              │
     │  └────────┬─────────┘    │ - session_market │              │
     │           │              │ - adx, rsi, etc  │              │
     │           ▼              └──────────────────┘              │
     │  ┌──────────────────┐                                      │
     │  │ PRÉDICTION:      │                                      │
     │  │ sl_pct=0.12%     │  → APPLIQUÉ AU PROCHAIN TRADE       │
     │  │ trailing=0.18%   │                                      │
     │  └──────────────────┘                                      │
     │                                                             │
     │              REGIME ATR OPTIMIZATION PROJECT                │
     └─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Variables du Mode FIXE (scope ML)

### Variables actives en mode FIXE uniquement

| Variable | Valeur actuelle | Description | Priorité ML |
|----------|-----------------|-------------|-------------|
| **`sl_percent`** | 0.15% | Stop Loss initial | ⭐⭐⭐⭐⭐ |
| **`tp_percent`** | 5.0% | Take Profit final | ⭐⭐⭐⭐ |
| **`break_even_trigger`** | 0.2% | PnL% pour déplacer SL à entry | ⭐⭐⭐⭐ |
| **`trailing_enabled`** | true | Activer trailing stop | ⭐⭐ (bool) |
| **`trailing_trigger_pnl`** | 0.2% | PnL% pour activer trailing | ⭐⭐⭐⭐⭐ |
| **`trailing_min_distance`** | 0.15% | Distance initiale trailing | ⭐⭐⭐⭐ |
| **`trailing_max_distance`** | 0.4% | Distance max trailing | ⭐⭐⭐ |
| **`trailing_pnl_cap`** | 1.45% | PnL% pour atteindre max_distance | ⭐⭐⭐ |
| **`partial_tp_percent`** | 40% | % position vendue au TP partiel | ⭐⭐⭐⭐ |

### Variables NON utilisées en mode FIXE (ATR only)

Ces variables sont ignorées quand `tp_sl_mode = "FIXE"`:
- `stagnation_exit_*` (tout le bloc)
- `stagnation_positive_*` (tout le bloc)
- `stagnation_mfe_*` (tout le bloc)
- `trailing_mfe_*` (tout le bloc)

---

## 🧠 Architecture ML-First

### Objectif

Prédire les paramètres optimaux de sortie **au moment de l'entrée** en fonction du contexte de marché.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ML PIPELINE                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐         │
│  │ Post-Exit Data │───►│ Target Labels  │───►│ ML Training    │         │
│  │ (historical)   │    │ (optimal params│    │ (supervised)   │         │
│  └────────────────┘    └────────────────┘    └────────────────┘         │
│                                                      │                   │
│                                                      ▼                   │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐         │
│  │ Entry Features │───►│ ML Predictor   │───►│ Dynamic Params │         │
│  │ (live trade)   │    │ (inference)    │    │ (per trade)    │         │
│  └────────────────┘    └────────────────┘    └────────────────┘         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Target Variables (ce que le ML prédit)

| Target | Source | Formule |
|--------|--------|---------|
| `optimal_sl_pct` | Post-exit MAE | `max(realized_sl, post_exit_mae × 1.1)` si trade gagnant |
| `optimal_trailing_trigger` | Post-exit timing | `realized_pnl_at_optimal × 0.6` |
| `optimal_be_trigger` | MFE/MAE ratio | `entry_mfe × 0.5` si trade a touché BE |
| `should_use_partial_tp` | Exit efficiency | `1` si partial aurait amélioré result |

### Features d'entrée (contexte au moment du trade)

| Feature | Source | Importance estimée |
|---------|--------|-------------------|
| `atr_1m` | Scanner | ⭐⭐⭐⭐⭐ |
| `atr_5m` | Scanner | ⭐⭐⭐⭐⭐ |
| `adx` | Scanner | ⭐⭐⭐⭐ |
| `rsi_1m` | Scanner | ⭐⭐⭐ |
| `spread_bps` | Entry | ⭐⭐⭐⭐ |
| `volume_ratio` | Scanner | ⭐⭐⭐ |
| `session` (Asia/London/NY) | Time | ⭐⭐⭐⭐ |
| `hour_utc` | Time | ⭐⭐⭐ |
| `market_regime` | Regime detector | ⭐⭐⭐⭐ |
| `btc_trend_24h` | BTC indicator | ⭐⭐⭐ |
| `symbol_hist_winrate` | DB | ⭐⭐⭐ |
| `direction` (LONG/SHORT) | Trade | ⭐⭐ |

---

## 📊 Données Post-Exit à collecter

### Configuration haute précision

```python
POST_EXIT_CONFIG = {
    # Durée et échantillonnage
    "tracking_duration_seconds": 300,      # 5 minutes
    "sample_interval_ms": 1000,            # 1 sample/seconde
    "max_samples_per_trade": 300,          # 300 points max
    
    # Durée adaptative
    "adaptive_duration": True,
    "min_duration_seconds": 60,            # Min 1 minute
    "max_duration_seconds": 600,           # Max 10 minutes
    "duration_multiplier": 2.0,            # durée = min(max, trade_duration × 2)
    
    # Gestion ressources
    "max_concurrent_trackers": 15,
    "memory_limit_mb": 50,
    
    # Persistence
    "store_raw_samples": True,             # Garder tous les points
    "batch_db_write": True,                # Écriture unique à la fin
}
```

### Métriques calculées par trade

| Métrique | Formule | Usage ML |
|----------|---------|----------|
| `post_exit_mfe_pct` | Max favorable après exit | Target pour TP optimal |
| `post_exit_mae_pct` | Max adverse après exit | Target pour SL optimal |
| `post_exit_final_pct` | Mouvement net final | Contexte |
| `time_to_mfe_sec` | Temps pour atteindre MFE | Target pour trailing trigger |
| `exit_efficiency_pct` | `realized / (realized + mfe) × 100` | Label de qualité |
| `would_have_hit_original_tp` | Prix a atteint TP original? | Validation partial TP |
| `regret_pct` | PnL% manqué | Coût d'opportunité |

---

## 🗄️ Schéma Base de Données

### Table `trade_post_exit_analysis`

```sql
CREATE TABLE trade_post_exit_analysis (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    
    -- Contexte de sortie
    exit_price DECIMAL(20, 10) NOT NULL,
    exit_timestamp TIMESTAMPTZ NOT NULL,
    exit_reason VARCHAR(50),
    direction VARCHAR(10) NOT NULL,
    realized_pnl_pct DECIMAL(10, 4),
    realized_pnl_usdt DECIMAL(20, 8),
    
    -- Params utilisés (pour analyse)
    used_sl_pct DECIMAL(10, 4),
    used_tp_pct DECIMAL(10, 4),
    used_be_trigger DECIMAL(10, 4),
    used_trailing_trigger DECIMAL(10, 4),
    
    -- Config tracking
    tracking_duration_sec INTEGER NOT NULL,
    sample_count INTEGER NOT NULL,
    
    -- Métriques post-exit
    post_exit_mfe_pct DECIMAL(10, 4),
    post_exit_mfe_price DECIMAL(20, 10),
    post_exit_mfe_timestamp TIMESTAMPTZ,
    time_to_mfe_sec INTEGER,
    
    post_exit_mae_pct DECIMAL(10, 4),
    post_exit_mae_price DECIMAL(20, 10),
    post_exit_mae_timestamp TIMESTAMPTZ,
    
    post_exit_final_pct DECIMAL(10, 4),
    post_exit_final_price DECIMAL(20, 10),
    
    -- Métriques dérivées
    exit_efficiency_pct DECIMAL(10, 4),
    regret_pct DECIMAL(10, 4),
    regret_usdt DECIMAL(20, 8),
    exit_timing_grade CHAR(2),
    
    -- Flags analyse
    would_have_hit_original_tp BOOLEAN DEFAULT FALSE,
    would_have_hit_original_sl BOOLEAN DEFAULT FALSE,
    price_returned_to_entry BOOLEAN DEFAULT FALSE,
    
    -- ML Targets calculés
    ml_optimal_sl_pct DECIMAL(10, 4),
    ml_optimal_trailing_trigger DECIMAL(10, 4),
    ml_optimal_be_trigger DECIMAL(10, 4),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(trade_id)
);

CREATE INDEX idx_post_exit_trade_id ON trade_post_exit_analysis(trade_id);
CREATE INDEX idx_post_exit_efficiency ON trade_post_exit_analysis(exit_efficiency_pct);
CREATE INDEX idx_post_exit_created ON trade_post_exit_analysis(created_at);
```

### Table `trade_post_exit_samples` (données brutes)

```sql
CREATE TABLE trade_post_exit_samples (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    sample_index INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    price DECIMAL(20, 10) NOT NULL,
    pnl_vs_exit_pct DECIMAL(10, 4),
    cumulative_mfe_pct DECIMAL(10, 4),
    cumulative_mae_pct DECIMAL(10, 4),
    
    UNIQUE(trade_id, sample_index)
);

CREATE INDEX idx_samples_trade_id ON trade_post_exit_samples(trade_id);
```

---

## 📈 Phases d'implémentation

### ✅ Phase 1: Data Collection (2-3h) - COMPLÉTÉE 19/01/2026
**Objectif**: Collecter les données post-exit pour chaque trade

- [x] Créer migration SQL pour les 2 tables
- [x] Implémenter `PostExitTracker` dataclass
- [x] Implémenter `PostExitManager` singleton
- [x] Hook dans `PositionManager.close_position()`
- [x] Boucle dédiée `post_exit_loop.py` pour récupérer prix
- [x] Batch write en DB à la fin du tracking
- [x] API endpoints `/api/post-exit/status` et `/api/post-exit/recent`

**Fichiers créés:**
| Fichier | Description |
|---------|-------------|
| `database/migrations/add_post_exit_analysis_tables.sql` | Tables + vues SQL |
| `core/post_exit/__init__.py` | Module exports |
| `core/post_exit/tracker.py` | `PostExitTracker` dataclass |
| `core/post_exit/manager.py` | `PostExitManager` singleton |
| `core/callbacks/post_exit_loop.py` | Boucle prix dédiée |

**Fichiers modifiés:**
| Fichier | Modification |
|---------|--------------|
| `core/position_manager.py:4643-4676` | Hook start_tracking_sync() |
| `core/callbacks/position_check_loop.py:169-176` | Hook prix aux trackers |
| `main.py:585-592` | Startup boucle post-exit |
| `main.py:657-663` | Shutdown boucle post-exit |
| `main.py:3833-3868` | API endpoints post-exit |
| `main.py:8173-8178, 8286-8302` | Excel export post-exit |

**Livrable**: ✅ Données post-exit collectées automatiquement pour chaque nouveau trade

### ⬜ Phase 2: Metrics & Analysis (2h)
**Objectif**: Calculer et stocker les métriques + targets ML

- [ ] Calculer `exit_efficiency`, `regret`, grades
- [ ] Calculer `ml_optimal_*` targets
- [ ] Endpoint API `/api/analytics/post-exit/summary`
- [ ] Script d'analyse `scripts/analyze_post_exit.py`
- [ ] Intégration avec `project_regime_atr_optimization/Phase 2G` (ML Monitor)

**Livrable**: Métriques et targets ML disponibles pour chaque trade

### ⬜ Phase 3: ML Model Training (3-4h)
**Objectif**: Entraîner un modèle pour prédire les params optimaux

- [ ] Feature engineering (extraire features au moment entry)
- [ ] Dataset builder (join trades + post_exit + features)
- [ ] Multi-output regressor (sl_pct, trailing_trigger, be_trigger)
- [ ] Validation (train/test split temporel)
- [ ] Sauvegarder modèle `exit_optimizer.pkl`
- [ ] Intégration avec `project_regime_atr_optimization/Phase 2D` (ML Param Optimizer)

**Prérequis**: 500+ trades avec données post-exit complètes

**Livrable**: Modèle ML entraîné pour prédire params optimaux

### ⬜ Phase 4: Live Integration (2-3h)
**Objectif**: Utiliser les prédictions ML en live

- [ ] Config `ml_dynamic_params_enabled`
- [ ] `MLParamPredictor` class avec inference
- [ ] Intégration dans `PositionManager.open_position()`
- [ ] Fallback si confidence < seuil
- [ ] Logging des params prédits vs utilisés
- [ ] Intégration avec `project_regime_atr_optimization/Phase 3A` (Mixture-of-Experts)

**Livrable**: Trades live avec params dynamiques ML

### ⬜ Phase 5: Frontend & Monitoring (2-3h)
**Objectif**: Visualiser et monitorer le système

- [ ] Dashboard PostExitAnalysis.svelte
- [ ] Mini-chart post-exit dans TradeHistory
- [ ] Métriques ML (accuracy, predicted vs actual)
- [ ] Alertes si drift détecté
- [ ] Intégration avec `project_regime_atr_optimization/Phase 2G` (ML Monitor)

---

## 🛠️ Détails d'implémentation Phase 1

### PostExitTracker (dataclass)

```python
@dataclass
class PostExitTracker:
    """Tracker pour un trade individuel"""
    trade_id: int
    symbol: str
    direction: str  # 'LONG' ou 'SHORT'
    exit_price: float
    exit_timestamp: datetime
    exit_reason: str
    realized_pnl_pct: float
    realized_pnl_usdt: float
    
    # Params utilisés (pour analyse)
    original_sl: float
    original_tp: float
    entry_price: float
    trade_duration_sec: float
    used_params: Dict[str, Any]
    
    # Tracking config
    tracking_duration_sec: int = 300
    sample_interval_ms: int = 1000
    
    # Données collectées
    samples: List[PostExitSample] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    # Métriques calculées
    post_exit_mfe_pct: float = 0.0
    post_exit_mae_pct: float = 0.0
    post_exit_mfe_price: float = 0.0
    post_exit_mae_price: float = 0.0
    
    def add_sample(self, price: float) -> bool:
        """Ajoute un sample et met à jour MFE/MAE"""
        
    def compute_metrics(self) -> Dict[str, Any]:
        """Calcule toutes les métriques finales"""
        
    def compute_ml_targets(self) -> Dict[str, float]:
        """Calcule les targets ML optimaux"""
```

### PostExitManager (singleton)

```python
class PostExitManager:
    """Gestionnaire global des trackers post-exit"""
    
    DEFAULT_CONFIG = {
        'enabled': True,
        'tracking_duration_sec': 300,
        'sample_interval_ms': 1000,
        'max_concurrent': 15,
        'store_raw_samples': True,
    }
    
    active_trackers: Dict[str, PostExitTracker]
    completed_metrics: List[Dict]
    
    async def start_tracking(self, trade_id, symbol, ...) -> bool:
        """Démarre le tracking pour un trade fermé"""
        
    async def on_price_update(self, symbol: str, price: float):
        """Reçoit une mise à jour de prix"""
        
    async def _complete_tracker(self, symbol: str):
        """Finalise un tracker et sauvegarde en DB"""
        
    async def _save_to_database(self, tracker: PostExitTracker):
        """Sauvegarde métriques + samples dans PostgreSQL"""
```

### Boucle dédiée post_exit_loop

```python
async def post_exit_loop():
    """
    Boucle indépendante pour récupérer les prix des symboles
    en cours de tracking post-exit.
    
    - Intervalle: 1 seconde
    - Récupère prix via price_provider
    - Envoie au PostExitManager
    """
    while _is_running:
        active_symbols = post_exit_mgr.get_active_symbols()
        for symbol in active_symbols:
            price = await _price_provider.get_price(symbol)
            post_exit_mgr.on_price_update_sync(symbol, price)
        await asyncio.sleep(1.0)
```

### Hook dans PositionManager

```python
# Dans close_position(), juste avant self.active_position = None

try:
    from core.post_exit import get_post_exit_manager
    post_exit_manager = get_post_exit_manager()
    
    post_exit_manager.start_tracking_sync(
        trade_id=db_trade_id,
        symbol=position.symbol,
        direction=position.direction,
        exit_price=exit_price,
        exit_reason=reason,
        realized_pnl_pct=net_pnl_pct,
        realized_pnl_usdt=net_pnl_usdt,
        original_sl=position.initial_sl or position.sl,
        original_tp=position.tp,
        entry_price=position.entry,
        trade_duration_sec=float(duration),
        used_params=used_params
    )
except Exception as post_exit_err:
    logger.debug(f"PostExit tracking ignoré: {post_exit_err}")
```

---

## 🔧 Configuration finale

```python
# config.py - Nouvelles variables
ML_DYNAMIC_PARAMS = {
    # Master switch
    "enabled": False,                      # Activer params dynamiques ML
    
    # Confidence thresholds
    "min_confidence": 0.65,                # Confiance min pour utiliser prédiction
    "fallback_to_config": True,            # Si confidence faible, utiliser config
    
    # Variables prédites
    "predict_sl_pct": True,
    "predict_trailing_trigger": True,
    "predict_be_trigger": True,
    "predict_partial_tp": False,           # Phase 2
    
    # Bounds de sécurité (override jamais au-delà)
    "sl_pct_min": 0.10,
    "sl_pct_max": 0.50,
    "trailing_trigger_min": 0.10,
    "trailing_trigger_max": 0.50,
    "be_trigger_min": 0.10,
    "be_trigger_max": 0.40,
    
    # Retraining
    "retrain_interval_trades": 200,        # Ré-entraîner tous les 200 trades
    "retrain_min_samples": 500,            # Minimum trades pour training
}
```

---

## 📊 Estimation ressources

| Métrique | Valeur | Notes |
|----------|--------|-------|
| RAM par tracker | ~50 KB | 300 samples × ~150 bytes |
| RAM max (15 trackers) | ~750 KB | Négligeable |
| CPU overhead | +0.5% | WebSocket filtering + calculs |
| DB storage/trade | ~5 KB | Analyse + samples |
| ML inference latency | <10ms | GradientBoosting léger |

---

## 🔗 Dépendances

### Backend
- `core/position_manager.py` - Hook à la clôture
- `trading/websocket_manager.py` - Prix en temps réel
- `core/postgresql_datalogger.py` - Sauvegarde DB
- `optimization/` - ML training infrastructure

### Frontend
- `TradeHistory.svelte` - Intégration mini-chart
- Nouveau: `PostExitDashboard.svelte`

---

## 📝 Notes de conception

### Pourquoi ML multi-output vs modèles séparés?

**Choix: Multi-output** (un modèle prédit tous les params)
- ✅ Plus stable (moins de variance)
- ✅ Capture corrélations entre params
- ✅ Plus simple à maintenir
- ❌ Moins flexible par variable

### Pourquoi fallback si confidence faible?

Le ML peut être incertain sur certains contextes (nouvelles paires, conditions rares).
Utiliser la config fixe comme fallback garantit un comportement prévisible.

### Pourquoi bounds de sécurité?

Même si le ML prédit un SL de 2%, on ne veut jamais dépasser `sl_pct_max=0.50%`.
Cela protège contre les prédictions aberrantes.

---

## 📊 Vues SQL créées

### v_post_exit_summary
Résumé des métriques post-exit par trade avec join sur `trades`.

### v_post_exit_by_hour
Agrégation des métriques post-exit par heure UTC pour analyse temporelle.

---

## 🔍 API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/post-exit/status` | GET | Statut du système (enabled, active_count, etc.) |
| `/api/post-exit/recent` | GET | Métriques récentes (limit=10 par défaut) |

---

## 📈 Export Excel

Les tables `trade_post_exit_analysis` et `trade_post_exit_samples` sont automatiquement incluses dans l'export Excel (`/api/datalogger/export/excel`) avec:
- Tri par `exit_timestamp DESC` pour analysis
- Tri par `timestamp DESC` pour samples
- Toutes les colonnes post-exit visibles

---

*Document créé: 2026-01-19*
*Version: 2.0*
*Status: ✅ Phase 1 IMPLÉMENTÉE | ⬜ Phases 2-5 EN ATTENTE*

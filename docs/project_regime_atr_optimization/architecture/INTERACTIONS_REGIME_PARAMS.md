# 🔗 INTERACTIONS RÉGIME ↔ PARAMÈTRES
## Comment le Régime contrôle chaque composant

> **Document complémentaire au MASTER_IMPLEMENTATION_PLAN**
> **Objectif:** Détailler EXACTEMENT comment les paramètres du régime sont injectés dans chaque composant

---

## 1. 📊 PARAMÈTRES PAR RÉGIME (Source de Vérité)

Chaque régime définit ces paramètres dans `RegimeConfig`:

```python
# core/market_regime_selector.py - DEFAULT_REGIME_CONFIGS

CALME = {
    # Filtrage Scanner
    "optimal_atr_min": 0.05,      # Min ATR% accepté
    "optimal_atr_max": 0.20,      # Max ATR% accepté
    "optimal_atr_min_5m": 0.10,
    "optimal_atr_max_5m": 0.35,
    "min_score_required": 8.5,    # Score min pour trade
    "volume_multiplier": 1.0,
    
    # SL/TP Position
    "atr_mult_sl": 0.8,           # SL = ATR × 0.8
    "atr_mult_tp": 1.8,           # TP = ATR × 1.8
    "sl_exchange_percent": 0.25,  # SL MEXC fixe
    
    # Gestion Position
    "break_even_atr_mult": 0.8,
    "trailing_trigger_atr_mult": 1.0,
    "max_position_time": 180,     # secondes
    
    # Stagnation
    "stagnation_timeout": 360,
    "stagnation_min_pnl": 0.05,
    "stagnation_max_loss": -0.08
}

NORMAL = {
    "optimal_atr_min": 0.15,
    "optimal_atr_max": 0.40,
    "min_score_required": 8.0,
    "atr_mult_sl": 1.2,
    "atr_mult_tp": 2.2,
    # ...
}

VOLATILE = {
    "optimal_atr_min": 0.30,
    "optimal_atr_max": 1.5,
    "min_score_required": 7.5,    # Plus permissif
    "atr_mult_sl": 1.5,           # SL plus large
    "atr_mult_tp": 2.5,           # TP plus ambitieux
    # ...
}
```

---

## 2. 🔌 POINT D'INJECTION: `get_active_config()`

**Fonction clé** qui retourne les params du régime actuel:

```python
# core/market_regime_selector.py

def get_active_config(self) -> Dict[str, Any]:
    """
    Retourne la configuration active pour le régime actuel.
    C'est LE point d'entrée pour tous les composants.
    """
    if not self.current_config:
        return {}
    
    return {
        # Scanner
        "min_score_required": self.current_config.min_score_required,
        "optimal_atr_min_1m": self.current_config.optimal_atr_min,
        "optimal_atr_max_1m": self.current_config.optimal_atr_max,
        "optimal_atr_min_5m": self.current_config.optimal_atr_min_5m,
        "optimal_atr_max_5m": self.current_config.optimal_atr_max_5m,
        "volume_multiplier": self.current_config.volume_multiplier,
        
        # Position SL/TP
        "atr_mult_sl": self.current_config.atr_mult_sl,
        "atr_mult_tp": self.current_config.atr_mult_tp,
        "sl_exchange_percent": self.current_config.sl_exchange_percent,
        
        # Position Management
        "break_even_atr_mult": self.current_config.break_even_atr_mult,
        "trailing_trigger_atr_mult": self.current_config.trailing_trigger_atr_mult,
        "position_timeout": self.current_config.max_position_time,
        
        # Stagnation
        "stagnation_exit_timeout_seconds": self.current_config.stagnation_timeout,
        "stagnation_exit_min_pnl_to_stay": self.current_config.stagnation_min_pnl,
        "stagnation_exit_max_loss_to_exit": self.current_config.stagnation_max_loss
    }
```

---

## 3. 📡 CONSOMMATEURS DES PARAMÈTRES

### 3.1 Scanner/Analyzer → Filtrage ATR

**Fichier:** `core/analyzer.py`

```python
def should_analyze_pair(self, pair: str, atr_pct: float) -> bool:
    """
    Vérifie si une paire est dans la plage ATR acceptable.
    DOIT utiliser les params du régime actuel.
    """
    # NOUVEAU: Récupérer config du régime
    from core.market_regime_selector import get_regime_selector
    rs = get_regime_selector()
    config = rs.get_active_config()
    
    # Utiliser les bornes du régime (pas de config_overrides)
    atr_min = config.get('optimal_atr_min_1m', 0.15)
    atr_max = config.get('optimal_atr_max_1m', 0.40)
    
    is_valid = atr_min <= atr_pct <= atr_max
    
    if not is_valid:
        logger.debug(
            f"❌ {pair} ATR={atr_pct:.3f}% hors plage régime "
            f"[{atr_min:.2f}-{atr_max:.2f}%]"
        )
    
    return is_valid


def get_min_score_for_regime(self) -> float:
    """
    Retourne le score minimum requis selon le régime.
    """
    from core.market_regime_selector import get_regime_selector
    rs = get_regime_selector()
    config = rs.get_active_config()
    
    # Ajustement session si activé
    session_adj = 0.0
    try:
        from utils.session_detector import get_current_session
        session = get_current_session()
        session_adj = session.get('score_adjustment', 0.0)
    except:
        pass
    
    base_score = config.get('min_score_required', 7.0)
    final_score = base_score + session_adj
    
    logger.debug(f"📊 Score min: {base_score} + session_adj {session_adj} = {final_score}")
    
    return final_score
```

### 3.2 Position Manager → Calcul SL/TP

**Fichier:** `core/position_manager.py`

```python
def calculate_sl_tp_from_regime(
    self, 
    entry_price: float, 
    direction: str, 
    atr_pct: float
) -> Tuple[float, float, Dict]:
    """
    Calcule SL/TP en utilisant les multipliers du régime actuel.
    
    Returns:
        Tuple (sl_price, tp_price, metadata)
    """
    from core.market_regime_selector import get_regime_selector
    
    rs = get_regime_selector()
    config = rs.get_active_config()
    
    # Récupérer multipliers du régime
    atr_mult_sl = config.get('atr_mult_sl', 1.2)
    atr_mult_tp = config.get('atr_mult_tp', 2.2)
    
    # Calculer distances
    sl_distance_pct = atr_pct * atr_mult_sl / 100
    tp_distance_pct = atr_pct * atr_mult_tp / 100
    
    if direction == 'LONG':
        sl_price = entry_price * (1 - sl_distance_pct)
        tp_price = entry_price * (1 + tp_distance_pct)
    else:  # SHORT
        sl_price = entry_price * (1 + sl_distance_pct)
        tp_price = entry_price * (1 - tp_distance_pct)
    
    metadata = {
        'regime': rs.current_regime.value,
        'atr_mult_sl_used': atr_mult_sl,
        'atr_mult_tp_used': atr_mult_tp,
        'sl_distance_pct': sl_distance_pct * 100,
        'tp_distance_pct': tp_distance_pct * 100,
    }
    
    logger.info(
        f"📐 SL/TP Régime {rs.current_regime.value}: "
        f"SL={atr_mult_sl}×ATR={sl_distance_pct*100:.3f}% | "
        f"TP={atr_mult_tp}×ATR={tp_distance_pct*100:.3f}%"
    )
    
    return sl_price, tp_price, metadata


def get_break_even_trigger(self, atr_pct: float) -> float:
    """
    Retourne le trigger Break-Even selon le régime.
    """
    from core.market_regime_selector import get_regime_selector
    
    rs = get_regime_selector()
    config = rs.get_active_config()
    
    be_mult = config.get('break_even_atr_mult', 1.0)
    trigger_pnl_pct = atr_pct * be_mult
    
    return trigger_pnl_pct


def get_trailing_params(self, atr_pct: float) -> Dict[str, float]:
    """
    Retourne les params du trailing selon le régime.
    """
    from core.market_regime_selector import get_regime_selector
    
    rs = get_regime_selector()
    config = rs.get_active_config()
    
    trigger_mult = config.get('trailing_trigger_atr_mult', 1.5)
    distance_mult = config.get('trailing_distance_atr_mult', 0.5)  # Du ATR Optimization
    
    return {
        'trigger_pnl_pct': atr_pct * trigger_mult,
        'distance_pct': atr_pct * distance_mult,
    }


def get_stagnation_params(self) -> Dict[str, Any]:
    """
    Retourne les params de stagnation selon le régime.
    """
    from core.market_regime_selector import get_regime_selector
    
    rs = get_regime_selector()
    config = rs.get_active_config()
    
    return {
        'timeout_seconds': config.get('stagnation_exit_timeout_seconds', 300),
        'min_pnl_to_stay': config.get('stagnation_exit_min_pnl_to_stay', 0.03),
        'max_loss_to_exit': config.get('stagnation_exit_max_loss_to_exit', -0.10),
    }
```

### 3.3 SL MEXC Dynamique → Lié au Régime

**Fichier:** `trading/live_order_manager_futures.py`

```python
def calculate_sl_mexc_from_regime(
    self, 
    entry_price: float, 
    direction: str,
    atr_pct: float
) -> Tuple[float, float]:
    """
    Calcule le SL MEXC basé sur le SL du régime × marge de sécurité.
    
    Returns:
        Tuple (sl_mexc_price, sl_mexc_pct)
    """
    from core.market_regime_selector import get_regime_selector
    
    rs = get_regime_selector()
    config = rs.get_active_config()
    
    # SL du régime
    atr_mult_sl = config.get('atr_mult_sl', 1.2)
    sl_atr_pct = atr_pct * atr_mult_sl
    
    # Marge de sécurité MEXC (10% plus large)
    SL_MEXC_MARGIN = 1.1
    sl_mexc_pct = sl_atr_pct * SL_MEXC_MARGIN
    
    # Calculer prix
    if direction == 'LONG':
        sl_mexc_price = entry_price * (1 - sl_mexc_pct / 100)
    else:
        sl_mexc_price = entry_price * (1 + sl_mexc_pct / 100)
    
    logger.info(
        f"🛡️ SL MEXC Dynamique: Régime={rs.current_regime.value} | "
        f"SL_ATR={sl_atr_pct:.3f}% × {SL_MEXC_MARGIN} = SL_MEXC={sl_mexc_pct:.3f}%"
    )
    
    return sl_mexc_price, sl_mexc_pct
```

### 3.4 GB Classifier → Régime comme Feature

**Fichier:** `ml/feature_loader.py`

```python
def add_regime_features(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ajoute les features de régime pour le GB Classifier.
    """
    from core.market_regime_selector import get_regime_selector
    from utils.session_detector import get_current_session
    
    rs = get_regime_selector()
    session = get_current_session()
    
    # Encodage régime
    regime_encoding = {
        'CALME': 0, 'NORMAL': 1, 'VOLATILE': 2, 'CHOPPY': 3, 'UNKNOWN': 1
    }
    
    # Encodage session
    session_encoding = {
        'ASIA': 0, 'EUROPE_OPEN': 1, 'EUROPE': 2, 'US_PREMARKET': 3,
        'US_OPEN': 4, 'US_SESSION': 5, 'US_CLOSE': 6, 'NIGHT': 7
    }
    
    features['regime_encoded'] = regime_encoding.get(
        rs.current_regime.value if rs.current_regime else 'UNKNOWN', 1
    )
    features['session_encoded'] = session_encoding.get(session['name'], 2)
    features['session_atr_multiplier'] = session.get('atr_multiplier', 1.0)
    
    # Stabilité du régime (plus stable = plus fiable)
    if rs.regime_since:
        from datetime import datetime
        stability = (datetime.now() - rs.regime_since).total_seconds() / 60
        features['regime_stability_minutes'] = min(stability, 240)  # Cap à 4h
    else:
        features['regime_stability_minutes'] = 60
    
    return features
```

---

## 4. ⚠️ CAS SPÉCIAL: Changement de Régime Mid-Trade

### Problème
Que se passe-t-il si le régime change pendant qu'une position est ouverte?

### Solution Recommandée: NE PAS modifier les positions ouvertes

```python
# core/position_manager.py

def should_update_sl_tp_on_regime_change(self) -> bool:
    """
    Politique: Les positions existantes gardent leurs params d'origine.
    Seules les NOUVELLES positions utilisent le nouveau régime.
    
    Raison: Éviter de modifier le risque d'une position déjà engagée.
    """
    return False  # Ne jamais modifier mid-trade


# Alternative pour le futur (Phase 3):
def handle_regime_change_for_open_positions(self, new_regime: str):
    """
    Option avancée: Ajuster UNIQUEMENT le trailing/stagnation.
    Les SL/TP d'entrée restent fixes.
    """
    if not self.active_position:
        return
    
    # On peut ajuster les params de SORTIE mais pas d'entrée
    new_config = get_regime_selector().get_active_config()
    
    # Ajuster stagnation
    self.active_position['stagnation_timeout'] = new_config.get(
        'stagnation_exit_timeout_seconds', 300
    )
    
    logger.info(
        f"♻️ Position existante: stagnation ajustée pour régime {new_regime}"
    )
```

---

## 5. 📊 FLUX COMPLET: Trade de A à Z

```
1. SCAN DÉMARRE
   │
   ▼
2. REGIME SELECTOR vérifie/met à jour le régime
   │ → current_regime = VOLATILE
   │ → get_active_config() prêt
   │
   ▼
3. SCANNER parcourt les paires
   │ Pour chaque paire:
   │   └─ analyzer.should_analyze_pair(atr_pct)
   │      └─ Utilise optimal_atr_min/max du régime VOLATILE [0.30-1.5%]
   │
   ▼
4. ANALYZER trouve un setup
   │ └─ Score calculé = 8.2
   │ └─ get_min_score_for_regime() = 7.5 (VOLATILE + session_adj)
   │ └─ 8.2 >= 7.5 → ACCEPTÉ
   │
   ▼
5. GB CLASSIFIER score l'opportunité
   │ └─ Features incluent: regime_encoded=2, session_encoded=4
   │ └─ Confidence = 68%
   │
   ▼
6. ML CALIBRATION vérifie
   │ └─ Band 65-70% → WR réel = 55%
   │ └─ 55% >= 45% threshold → TRADE ACCEPTÉ
   │
   ▼
7. POSITION MANAGER ouvre le trade
   │ └─ calculate_sl_tp_from_regime(entry, direction, atr_pct)
   │    └─ atr_mult_sl = 1.5 (VOLATILE)
   │    └─ atr_mult_tp = 2.5 (VOLATILE)
   │    └─ SL = entry × (1 - atr_pct × 1.5)
   │    └─ TP = entry × (1 + atr_pct × 2.5)
   │
   ▼
8. LIVE ORDER MANAGER soumet à MEXC
   │ └─ calculate_sl_mexc_from_regime()
   │    └─ SL_MEXC = SL_ATR × 1.1 (marge sécurité)
   │
   ▼
9. GESTION POSITION (pendant le trade)
   │ └─ get_break_even_trigger() → from régime VOLATILE
   │ └─ get_trailing_params() → from régime VOLATILE
   │ └─ get_stagnation_params() → from régime VOLATILE
   │
   ▼
10. CLOSE + LOG
    │ └─ log_trade_atr_metrics() avec:
    │    └─ session_market = US_OPEN
    │    └─ regime_used = VOLATILE
    │    └─ atr_mult_sl_used = 1.5
    │    └─ atr_mult_tp_used = 2.5
    │
    ▼
11. WHAT-IF RÉGIME calcule
    └─ pnl_if_calme = -0.3%
    └─ pnl_if_normal = +0.1%
    └─ pnl_if_volatile = +0.5% (utilisé)
    └─ optimal_regime_retrospective = VOLATILE ✅
```

---

## 6. 📋 CHECKLIST INTÉGRATION

### Scanner/Analyzer
- [ ] `should_analyze_pair()` utilise `get_active_config().optimal_atr_min/max`
- [ ] `get_min_score_for_regime()` utilise `get_active_config().min_score_required`
- [ ] Session adjustment appliqué sur min_score

### Position Manager
- [ ] `calculate_sl_tp_from_regime()` utilise `get_active_config().atr_mult_sl/tp`
- [ ] `get_break_even_trigger()` utilise `get_active_config().break_even_atr_mult`
- [ ] `get_trailing_params()` utilise `get_active_config().trailing_*`
- [ ] `get_stagnation_params()` utilise `get_active_config().stagnation_*`
- [ ] Metadata de trade inclut `regime_used`, `atr_mult_*_used`

### Live Order Manager
- [ ] `calculate_sl_mexc_from_regime()` utilise SL régime × 1.1

### GB Classifier
- [ ] `regime_encoded` ajouté aux features
- [ ] `session_encoded` ajouté aux features
- [ ] `regime_stability_minutes` ajouté aux features

### Logger
- [ ] trade_atr_metrics log `regime_used`, `session_market`, `atr_mult_*_used`
- [ ] what_if calcule `pnl_if_calme/normal/volatile`

---

## 7. 🔧 MODIFICATIONS REQUISES (Pas encore dans les docs)

| Fichier | Modification | Priorité |
|---------|--------------|----------|
| `core/analyzer.py` | Utiliser `get_active_config()` pour filtrage ATR | 🔴 Phase 1B |
| `core/position_manager.py` | Créer `calculate_sl_tp_from_regime()` | 🔴 Phase 1B |
| `core/position_manager.py` | Créer `get_break_even_trigger()` | 🔴 Phase 1B |
| `core/position_manager.py` | Créer `get_trailing_params()` | 🔴 Phase 1B |
| `core/position_manager.py` | Créer `get_stagnation_params()` | 🔴 Phase 1B |
| `trading/live_order_manager_futures.py` | Utiliser `calculate_sl_mexc_from_regime()` | 🟡 Phase 1B |
| `ml/feature_loader.py` | Ajouter `add_regime_features()` | 🟡 Phase 3B |

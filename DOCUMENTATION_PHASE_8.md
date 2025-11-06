# 📚 DOCUMENTATION PHASE 8 - AMÉLIORATIONS MAJEURES

**Date**: 2025-01-06  
**Version**: v7.0  
**Commit**: `c18767d` (implémentation) + `0abf9b4` (corrections) + `416d30f` (fix imports)

---

## 📋 RÉSUMÉ

La Phase 8 implémente **6 améliorations majeures** pour optimiser la gestion des risques, améliorer la qualité des setups, et renforcer la persistance des données.

### Améliorations implémentées

1. **Recovery Mode Progressif** - Réaction proportionnelle aux pertes
2. **Seuils Adaptatifs ATR** - Invalidation selon volatilité
3. **Max Drawdown Tracking** - Calcul précis du drawdown maximum
4. **Export CSV/JSON** - Export des trades pour analyse externe
5. **Corrélation Dynamique** - Filtre basé sur corrélation réelle des prix
6. **Persistance SQLite** - Historique illimité avec requêtes rapides

---

## 1️⃣ RECOVERY MODE PROGRESSIF

### Description

Remplace le Recovery Mode simple (1 niveau) par un système progressif avec plusieurs niveaux selon la magnitude du loss streak. Réaction proportionnelle aux pertes.

### Fichiers modifiés

- **`config.py`** : Configuration des niveaux progressifs
- **`core/position_manager.py`** : Méthode `get_recovery_level()` et intégration dans `calculate_adaptive_position_size()`
- **`core/analyzer.py`** : Intégration dans `analyze_pair()` pour boost score et confluence

### Détails des modifications

#### 1.1 Configuration (`config.py`)

**Avant** :
```python
"recovery_mode": {
    "enabled": True,
    "trigger_loss_streak": 3,
    "min_score_boost": 1.5,
    "position_size_reduction": 0.7,
    "confluence_forced": False,
    "duration_trades": 5,
}
```

**Après** :
```python
"recovery_mode": {
    "enabled": True,
    "mode": "PROGRESSIVE",  # "SIMPLE" ou "PROGRESSIVE"
    # Mode SIMPLE (fallback)
    "trigger_loss_streak": 3,
    "min_score_boost": 1.5,
    "position_size_reduction": 0.7,
    "confluence_forced": False,
    "duration_trades": 5,
    # Mode PROGRESSIVE : Niveaux selon loss streak
    "levels": [
        {
            "trigger_loss_streak": 2,
            "min_score_boost": 0.5,
            "position_size_reduction": 0.85,  # -15%
            "confluence_forced": False,
            "duration_trades": 3
        },
        {
            "trigger_loss_streak": 3,
            "min_score_boost": 1.5,
            "position_size_reduction": 0.7,  # -30%
            "confluence_forced": False,
            "duration_trades": 5
        },
        {
            "trigger_loss_streak": 5,
            "min_score_boost": 2.5,
            "position_size_reduction": 0.5,  # -50%
            "confluence_forced": True,
            "duration_trades": 7
        }
    ]
}
```

#### 1.2 Méthode `get_recovery_level()` (`core/position_manager.py`)

**Nouvelle méthode ajoutée** :
```python
def get_recovery_level(self, loss_streak: int) -> Optional[Dict]:
    """
    🔥 PHASE 6: Obtenir niveau recovery selon loss streak (mode PROGRESSIVE)
    
    Args:
        loss_streak: Nombre de pertes consécutives
        
    Returns:
        Dict avec niveau recovery ou None
    """
    from config import TRADING_CONFIG
    
    recovery_config = TRADING_CONFIG.get('recovery_mode', {})
    
    if not recovery_config.get('enabled', False):
        return None
    
    mode = recovery_config.get('mode', 'SIMPLE')
    
    if mode == 'SIMPLE':
        # Mode simple existant (fallback)
        trigger = recovery_config.get('trigger_loss_streak', 3)
        if loss_streak >= trigger:
            return {
                'level': 1,
                'min_score_boost': recovery_config.get('min_score_boost', 1.5),
                'position_size_reduction': recovery_config.get('position_size_reduction', 0.7),
                'confluence_forced': recovery_config.get('confluence_forced', False),
                'duration_trades': recovery_config.get('duration_trades', 5)
            }
        return None
    
    # Mode PROGRESSIVE
    levels = recovery_config.get('levels', [])
    
    # Trouver niveau le plus élevé applicable
    applicable_level = None
    for i, level in enumerate(levels):
        if loss_streak >= level['trigger_loss_streak']:
            applicable_level = {**level, 'level': i + 1}
    
    return applicable_level
```

**Logique** :
- Si `mode == 'SIMPLE'` : Comportement identique à l'ancien système
- Si `mode == 'PROGRESSIVE'` : Trouve le niveau le plus élevé applicable selon `loss_streak`
- Exemple : `loss_streak = 5` → Niveau 3 (boost +2.5, réduction -50%, confluence forcée)

#### 1.3 Intégration dans `calculate_adaptive_position_size()` (`core/position_manager.py`)

**Avant** :
```python
# 🔥 PHASE 6: Recovery Mode - Activation et réduction de taille
recovery_config = TRADING_CONFIG.get('recovery_mode', {})
if recovery_config.get('enabled', False):
    if loss_streak >= recovery_config.get('trigger_loss_streak', 3):
        if not self.config.recovery_mode_active:
            self.config.recovery_mode_active = True
            self.config.recovery_mode_remaining_trades = recovery_config.get('duration_trades', 5)
            logger.warning(f"🔄 RECOVERY MODE ACTIVÉ après {loss_streak} losses ...")
    
    if self.config.recovery_mode_active:
        recovery_mult = recovery_config.get('position_size_reduction', 0.7)
        streak_mult = streak_mult * recovery_mult
```

**Après** :
```python
# 🔥 PHASE 6: Recovery Mode Progressif - Activation et réduction de taille
recovery_level = self.get_recovery_level(loss_streak)
if recovery_level:
    level_num = recovery_level.get('level', 1)
    reduction = recovery_level.get('position_size_reduction', 0.7)
    
    # Activer Recovery Mode si pas déjà actif
    if not self.config.recovery_mode_active:
        self.config.recovery_mode_active = True
        self.config.recovery_mode_remaining_trades = recovery_level.get('duration_trades', 5)
        logger.warning(
            f"🔄 RECOVERY MODE Niveau {level_num} ACTIVÉ après {loss_streak} losses "
            f"(durée: {self.config.recovery_mode_remaining_trades} trades, "
            f"boost: +{recovery_level.get('min_score_boost', 0):.1f}, "
            f"réduction: {((1-reduction)*100):.0f}%)"
        )
    
    # Appliquer réduction de taille
    streak_mult = streak_mult * reduction
    logger.debug(f"🔄 Recovery Mode Niveau {level_num}: Taille réduite (mult: {reduction:.2f}, final streak: {streak_mult:.2f})")
```

**Changements** :
- Utilise `get_recovery_level()` au lieu de config directe
- Affiche le niveau dans les logs
- Réduction de taille selon le niveau progressif

#### 1.4 Intégration dans `analyze_pair()` (`core/analyzer.py`)

**Avant** :
```python
if recovery_mode_active:
    recovery_boost = recovery_config.get('min_score_boost', 1.5)
    adjusted_min_score = min_score_required + recovery_boost
    
    if recovery_config.get('confluence_forced', False):
        use_confluence = True
        # Vérifier confluence...
```

**Après** :
```python
if recovery_mode_active:
    # Utiliser get_recovery_level() pour obtenir le niveau progressif
    loss_streak = position_manager.config.loss_streak if hasattr(position_manager, 'config') else 0
    recovery_level = position_manager.get_recovery_level(loss_streak) if hasattr(position_manager, 'get_recovery_level') else None
    
    if recovery_level:
        recovery_boost = recovery_level.get('min_score_boost', recovery_config.get('min_score_boost', 1.5))
        level_num = recovery_level.get('level', 1)
    else:
        # Fallback sur config simple
        recovery_boost = recovery_config.get('min_score_boost', 1.5)
        level_num = 1
    
    adjusted_min_score = min_score_required + recovery_boost
    
    # Forcer confluence si configuré dans le niveau
    confluence_forced = recovery_level.get('confluence_forced', False) if recovery_level else recovery_config.get('confluence_forced', False)
    
    if confluence_forced:
        use_confluence = True
        # Vérifier confluence...
        logger.warning(f"⚠️ {symbol} - Setup rejeté (Recovery Mode Niveau {level_num}): Confluence requise")
```

**Changements** :
- Récupère le niveau progressif via `get_recovery_level()`
- Utilise `min_score_boost` et `confluence_forced` du niveau
- Logs incluent le numéro de niveau

### Comportement

| Loss Streak | Niveau | Boost Score | Réduction Taille | Confluence | Durée |
|-------------|--------|------------|------------------|------------|-------|
| 2 | 1 | +0.5 | -15% | Non | 3 trades |
| 3 | 2 | +1.5 | -30% | Non | 5 trades |
| 5+ | 3 | +2.5 | -50% | **Oui** | 7 trades |

### Gain attendu

- **Winrate** : +1-2% (réaction proportionnelle)
- **Réduction risque** : Progressive selon magnitude des pertes
- **Flexibilité** : Mode SIMPLE disponible en fallback

---

## 2️⃣ SEUILS ADAPTATIFS ATR

### Description

Adapter les seuils d'invalidation précoce selon la volatilité (ATR) de la paire. Moins strict en faible volatilité, plus strict en haute volatilité.

### Fichiers modifiés

- **`config.py`** : Configuration des seuils adaptatifs
- **`core/position_manager.py`** : Méthode `get_adaptive_early_threshold()` et modification de `_check_early_invalidation()`

### Détails des modifications

#### 2.1 Configuration (`config.py`)

**Nouvelle section ajoutée** :
```python
# 🔥 PHASE 8: Seuils adaptatifs ATR pour invalidation
"adaptive_thresholds": {
    "enabled": True,
    "early_invalidation": {
        "low_vol_multiplier": 0.7,   # ATR < 0.3%
        "high_vol_multiplier": 1.3,  # ATR > 0.8%
    },
    "stagnation": {
        "low_vol_threshold": 0.015,  # ATR < 0.3%
        "high_vol_threshold": 0.04,  # ATR > 0.8%
    }
}
```

#### 2.2 Méthode `get_adaptive_early_threshold()` (`core/position_manager.py`)

**Nouvelle méthode ajoutée** :
```python
def get_adaptive_early_threshold(self, elapsed: float) -> float:
    """
    🔥 PHASE 8: Calculer seuil Early Invalidation adaptatif selon ATR
    
    Args:
        elapsed: Temps écoulé en secondes
    
    Returns:
        Seuil PnL adaptatif (négatif)
    """
    from config import TRADING_CONFIG
    
    # Seuil de base selon temps écoulé (utiliser config actuelle)
    early_config = TRADING_CONFIG.get('early_invalidation', {})
    
    if elapsed <= 15:
        base_threshold = early_config.get('threshold_15s', -0.12)  # -0.12% pour 10-15s
    else:
        base_threshold = early_config.get('threshold_30s', -0.08)  # -0.08% pour 15-30s
    
    # Vérifier si seuils adaptatifs activés
    adaptive_config = TRADING_CONFIG.get('adaptive_thresholds', {})
    if not adaptive_config.get('enabled', True):
        return base_threshold
    
    # Calculer ATR en pourcentage (à la volée car atr_percent n'existe pas)
    position = self.active_position
    if position and position.atr and position.entry:
        atr_percent = (position.atr / position.entry) * 100
    else:
        atr_percent = 0.5  # Valeur par défaut
    
    # Ajuster selon ATR
    early_inv_config = adaptive_config.get('early_invalidation', {})
    
    if atr_percent < 0.3:  # Faible volatilité
        # Moins strict (ATR faible = mouvements plus petits)
        multiplier = early_inv_config.get('low_vol_multiplier', 0.7)
    elif atr_percent > 0.8:  # Haute volatilité
        # Plus strict (ATR élevé = mouvements plus grands)
        multiplier = early_inv_config.get('high_vol_multiplier', 1.3)
    else:  # Volatilité normale
        multiplier = 1.0
    
    adaptive_threshold = base_threshold * multiplier
    
    # Bornes de sécurité
    adaptive_threshold = max(-0.15, min(-0.05, adaptive_threshold))
    
    logger.debug(
        f"🎯 Seuil Early adaptatif: {adaptive_threshold:.3f}% "
        f"(base: {base_threshold:.2f}%, ATR: {atr_percent:.2f}%, mult: {multiplier:.2f})"
    )
    
    return adaptive_threshold
```

**Logique** :
1. Récupère le seuil de base selon `elapsed` (15s ou 30s)
2. Calcule `atr_percent` à la volée : `(atr / entry) * 100`
3. Applique multiplicateur selon volatilité :
   - ATR < 0.3% → `multiplier = 0.7` (moins strict)
   - ATR > 0.8% → `multiplier = 1.3` (plus strict)
   - Sinon → `multiplier = 1.0` (normal)
4. Applique bornes de sécurité : `[-0.15%, -0.05%]`

#### 2.3 Modification de `_check_early_invalidation()` (`core/position_manager.py`)

**Avant** :
```python
if elapsed <= 15:
    invalidation_threshold = early_config.get('threshold_15s', -0.12)
elif elapsed <= 30:
    invalidation_threshold = early_config.get('threshold_30s', -0.08)
else:
    return None

if pnl < invalidation_threshold:
    logger.warning(f"⚠️ Invalidation précoce ... (seuil {invalidation_threshold}%)")
    return 'EARLY_INVALIDATION'
```

**Après** :
```python
# ⚡ Seuil adaptatif selon ATR
invalidation_threshold = self.get_adaptive_early_threshold(elapsed)

# Vérifier mouvement attendu
if pnl <= invalidation_threshold:
    atr_percent = (self.active_position.atr / self.active_position.entry * 100) if (self.active_position.atr and self.active_position.entry) else 0.0
    logger.warning(
        f"⚠️ Invalidation précoce {self.active_position.direction} "
        f"{self.active_position.symbol}: "
        f"P&L {pnl:.2f}% après {elapsed:.0f}s "
        f"(seuil adaptatif: {invalidation_threshold:.2f}%, "
        f"ATR: {atr_percent:.2f}%)"
    )
    return 'EARLY_INVALIDATION'
```

**Changements** :
- Utilise `get_adaptive_early_threshold()` au lieu de seuil fixe
- Logs incluent ATR et seuil adaptatif

### Exemples de calcul

| ATR % | Base (15s) | Multiplicateur | Seuil Adaptatif |
|-------|------------|----------------|-----------------|
| 0.2% | -0.12% | 0.7 | **-0.084%** (moins strict) |
| 0.5% | -0.12% | 1.0 | **-0.12%** (normal) |
| 1.0% | -0.12% | 1.3 | **-0.156%** → **-0.15%** (borné) |

### Gain attendu

- **Winrate** : +1-2% (réduction invalidations prématurées)
- **Réduction invalidations** : -10-15% en faible volatilité
- **Protection** : +15-20% en haute volatilité

---

## 3️⃣ MAX DRAWDOWN TRACKING

### Description

Calculer et afficher le drawdown maximum historique (peak to trough) dans le dashboard avec calcul précis.

### Fichiers modifiés

- **`main.py`** : Fonction `calculate_max_drawdown()` et intégration dans `get_dashboard_summary()`

### Détails des modifications

#### 3.1 Fonction `calculate_max_drawdown()` (`main.py`)

**Nouvelle fonction ajoutée** :
```python
def calculate_max_drawdown(trade_history: List[Dict]) -> Dict:
    """
    🔥 PHASE 8: Calculer drawdown maximum historique (peak to trough)
    
    Returns:
        Dict avec max_dd, max_dd_date, current_dd
    """
    if not trade_history:
        return {'max_dd': 0, 'max_dd_date': None, 'current_dd': 0, 'current_peak': 0}
    
    # Calculer equity curve
    equity_curve = []
    cumulative = 0
    dates = []
    
    for trade in trade_history:
        cumulative += trade.get('gross_pnl_pct', 0)
        equity_curve.append(cumulative)
        dates.append(trade.get('timestamp', ''))
    
    # Trouver drawdown maximum
    peak = equity_curve[0] if equity_curve else 0
    peak_idx = 0
    max_dd = 0
    max_dd_idx = 0
    
    for i, equity in enumerate(equity_curve):
        if equity > peak:
            peak = equity
            peak_idx = i
        
        dd = ((equity - peak) / peak * 100) if peak > 0 else 0
        
        if dd < max_dd:
            max_dd = dd
            max_dd_idx = i
    
    # Drawdown actuel
    current_peak = max(equity_curve) if equity_curve else 0
    current_equity = equity_curve[-1] if equity_curve else 0
    current_dd = ((current_equity - current_peak) / current_peak * 100) if current_peak > 0 else 0
    
    return {
        'max_dd': round(max_dd, 2),
        'max_dd_date': dates[max_dd_idx] if max_dd_idx < len(dates) else None,
        'max_dd_from_peak': dates[peak_idx] if peak_idx < len(dates) else None,
        'current_dd': round(current_dd, 2),
        'current_peak': round(current_peak, 2)
    }
```

**Logique** :
1. Calcule la courbe d'équité cumulative (basée sur `gross_pnl_pct`)
2. Trouve le pic maximum et le drawdown maximum (peak-to-trough)
3. Calcule le drawdown actuel (depuis le dernier pic)
4. Retourne les dates et valeurs

#### 3.2 Intégration dans `get_dashboard_summary()` (`main.py`)

**Avant** :
```python
# Drawdown
equity_curve = []
running_equity = 0.0
peak = 0.0
max_drawdown = 0.0

for trade in trades:
    running_equity += trade.get('net_pnl_usdt', 0)
    equity_curve.append(running_equity)
    if running_equity > peak:
        peak = running_equity
    drawdown = peak - running_equity
    if drawdown > max_drawdown:
        max_drawdown = drawdown

return JSONResponse({
    ...
    'drawdown': round(max_drawdown, 4),
    ...
})
```

**Après** :
```python
# 🔥 PHASE 8: Max Drawdown Tracking (calcul précis)
max_dd_info = calculate_max_drawdown(trades)

# Equity curve pour graphique (basée sur PnL USDT)
equity_curve = []
running_equity = 0.0
for trade in trades:
    running_equity += trade.get('net_pnl_usdt', 0)
    equity_curve.append(running_equity)

return JSONResponse({
    ...
    'drawdown': round(max_dd_info.get('current_dd', 0), 2),  # Drawdown actuel (%)
    'drawdown_max': max_dd_info.get('max_dd', 0),  # Drawdown max historique (%)
    'drawdown_max_date': max_dd_info.get('max_dd_date'),  # Date du max drawdown
    'current_peak': max_dd_info.get('current_peak', 0),  # Pic actuel (%)
    ...
})
```

**Changements** :
- Utilise `calculate_max_drawdown()` pour calcul précis
- Retourne drawdown actuel, max historique, dates, et pic actuel
- Equity curve séparée pour graphique (basée sur USDT)

### Données retournées

| Champ | Description | Format |
|-------|-------------|--------|
| `drawdown` | Drawdown actuel (%) | Float (2 décimales) |
| `drawdown_max` | Drawdown max historique (%) | Float (2 décimales) |
| `drawdown_max_date` | Date du max drawdown | String (timestamp) |
| `current_peak` | Pic actuel (%) | Float (2 décimales) |

### Gain attendu

- **Visibilité risque** : Meilleure compréhension du drawdown
- **Monitoring** : Tracking précis de la performance
- **Décisions** : Données pour ajuster stratégie

---

## 4️⃣ EXPORT CSV/JSON

### Description

Endpoint pour exporter l'historique des trades en CSV ou JSON pour analyse externe (Excel, Python, etc.).

### Fichiers modifiés

- **`main.py`** : Endpoint `/api/export/trades` avec support CSV et JSON

### Détails des modifications

#### 4.1 Imports ajoutés (`main.py`)

```python
import csv
import io
from typing import Optional
from fastapi.responses import StreamingResponse
```

#### 4.2 Endpoint `/api/export/trades` (`main.py`)

**Nouvel endpoint ajouté** :
```python
@app.get("/api/export/trades")
async def export_trades_csv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    format: str = "csv"
):
    """
    🔥 PHASE 8: Exporter trades en CSV ou JSON
    
    Args:
        start_date: Date début (YYYY-MM-DD)
        end_date: Date fin (YYYY-MM-DD)
        format: csv ou json (défaut: csv)
    """
    trades = app_state['trade_history']
    
    # Filtrer par date si fourni
    if start_date and end_date:
        filtered_trades = [
            t for t in trades
            if start_date <= t.get('date', '') <= end_date
        ]
    else:
        filtered_trades = trades
    
    if format == "json":
        return JSONResponse(filtered_trades)
    
    # Format CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'timestamp', 'date', 'time', 'symbol', 'direction',
        'entry', 'exit', 'gross_pnl_pct', 'gross_pnl_usdt',
        'net_pnl_pct', 'net_pnl_usdt', 'fees', 'slippage',
        'total_costs', 'reason', 'duration'
    ])
    
    writer.writeheader()
    for trade in filtered_trades:
        writer.writerow({
            'timestamp': trade.get('timestamp', ''),
            'date': trade.get('date', ''),
            'time': trade.get('time', ''),
            'symbol': trade.get('symbol', ''),
            'direction': trade.get('direction', ''),
            'entry': trade.get('entry', 0),
            'exit': trade.get('exit', 0),
            'gross_pnl_pct': trade.get('gross_pnl_pct', 0),
            'gross_pnl_usdt': trade.get('gross_pnl_usdt', 0),
            'net_pnl_pct': trade.get('net_pnl_pct', 0),
            'net_pnl_usdt': trade.get('net_pnl_usdt', 0),
            'fees': trade.get('fees', 0),
            'slippage': trade.get('slippage', 0),
            'total_costs': trade.get('total_costs', 0),
            'reason': trade.get('reason', ''),
            'duration': trade.get('duration', 0)
        })
    
    output.seek(0)
    
    filename = f"trades_{start_date}_{end_date}.csv" if (start_date and end_date) else "trades_all.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
```

**Fonctionnalités** :
- **Filtres par date** : `start_date` et `end_date` (format YYYY-MM-DD)
- **Format CSV** : Export avec en-têtes et toutes les colonnes importantes
- **Format JSON** : Export JSON brut pour analyse programmatique
- **Streaming** : Utilise `StreamingResponse` pour fichiers volumineux
- **Nom de fichier** : Dynamique selon dates ou "trades_all.csv"

### Utilisation

**Export CSV tous les trades** :
```
GET /api/export/trades
```

**Export CSV période spécifique** :
```
GET /api/export/trades?start_date=2025-01-01&end_date=2025-01-31
```

**Export JSON** :
```
GET /api/export/trades?format=json
```

**Export JSON période** :
```
GET /api/export/trades?start_date=2025-01-01&end_date=2025-01-31&format=json
```

### Colonnes CSV

| Colonne | Description |
|---------|-------------|
| `timestamp` | Timestamp complet |
| `date` | Date (YYYY-MM-DD) |
| `time` | Heure (HH:MM:SS) |
| `symbol` | Symbole de la paire |
| `direction` | LONG ou SHORT |
| `entry` | Prix d'entrée |
| `exit` | Prix de sortie |
| `gross_pnl_pct` | PnL brut (%) |
| `gross_pnl_usdt` | PnL brut (USDT) |
| `net_pnl_pct` | PnL net (%) |
| `net_pnl_usdt` | PnL net (USDT) |
| `fees` | Frais |
| `slippage` | Slippage |
| `total_costs` | Coûts totaux |
| `reason` | Raison de fermeture |
| `duration` | Durée (secondes) |

### Gain attendu

- **Analyse externe** : Export facile pour Excel, Python, etc.
- **Backup** : Sauvegarde des données
- **Reporting** : Génération de rapports personnalisés

---

## 5️⃣ CORRÉLATION DYNAMIQUE

### Description

Remplacer le filtre de corrélation statique (groupes) par un calcul dynamique basé sur la corrélation réelle des prix (corrélation Pearson).

### Fichiers créés/modifiés

- **`core/correlation_dynamic.py`** : Nouveau fichier avec classe `DynamicCorrelationFilter`
- **`config.py`** : Configuration de la corrélation dynamique
- **`core/analyzer.py`** : Intégration dans `__init__()` et `analyze_pair()`

### Détails des modifications

#### 5.1 Configuration (`config.py`)

**Nouvelle section ajoutée** :
```python
# 🔥 PHASE 8: Corrélation dynamique (basée sur prix réels)
"dynamic_correlation": {
    "enabled": False,  # Désactivé par défaut (besoin historique)
    "period": 50,      # 50 bougies pour calcul
    "threshold": 0.7,  # Corrélation > 0.7 = pénalité
    "max_penalty": -3.0  # Pénalité max
}
```

#### 5.2 Classe `DynamicCorrelationFilter` (`core/correlation_dynamic.py`)

**Nouveau fichier créé** :
```python
"""
🔥 PHASE 8: Filtre corrélation dynamique basé sur prix réels
Calcul de corrélation Pearson entre symboles pour éviter surexposition
"""
import logging
from typing import List, Dict, Optional
from collections import deque

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("⚠️ numpy non disponible - Corrélation dynamique désactivée")


class DynamicCorrelationFilter:
    """Filtre corrélation dynamique basé sur prix réels"""
    
    def __init__(self, period: int = 50, threshold: float = 0.7):
        self.period = period
        self.threshold = threshold
        self.price_history = {}  # {symbol: deque([prices])}
    
    def update_price(self, symbol: str, price: float):
        """Mettre à jour historique prix"""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.period)
        
        self.price_history[symbol].append(price)
    
    def calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """
        Calculer corrélation Pearson entre 2 symboles
        
        Returns:
            Corrélation entre -1.0 et 1.0
        """
        if not NUMPY_AVAILABLE:
            return 0.0
        
        if symbol1 not in self.price_history or symbol2 not in self.price_history:
            return 0.0
        
        prices1 = list(self.price_history[symbol1])
        prices2 = list(self.price_history[symbol2])
        
        # Besoin minimum de données
        if len(prices1) < 20 or len(prices2) < 20:
            return 0.0
        
        # Aligner longueurs
        min_len = min(len(prices1), len(prices2))
        prices1 = prices1[-min_len:]
        prices2 = prices2[-min_len:]
        
        # Calculer returns
        returns1 = np.diff(prices1) / prices1[:-1]
        returns2 = np.diff(prices2) / prices2[:-1]
        
        # Corrélation Pearson
        if len(returns1) > 0 and len(returns2) > 0:
            correlation = np.corrcoef(returns1, returns2)[0, 1]
            return float(correlation) if not np.isnan(correlation) else 0.0
        
        return 0.0
    
    def check_correlation(self, symbol: str, active_positions: List) -> Dict:
        """
        Vérifier corrélation avec positions actives
        
        Returns:
            Dict avec valid, penalty, correlation, correlated_with
        """
        if not active_positions:
            return {'valid': True, 'penalty': 0, 'correlation': 0}
        
        max_correlation = 0
        correlated_symbol = None
        
        for pos in active_positions:
            if pos.symbol and pos.symbol != symbol:
                corr = self.calculate_correlation(symbol, pos.symbol)
                
                if abs(corr) > abs(max_correlation):
                    max_correlation = corr
                    correlated_symbol = pos.symbol
        
        # Vérifier seuil
        if abs(max_correlation) > self.threshold:
            # Corrélation forte détectée
            penalty = -1.5 * (abs(max_correlation) - self.threshold) / (1 - self.threshold)
            penalty = max(-3.0, penalty)  # Max -3.0 points
            
            return {
                'valid': True,  # Mode SOFT : pénalité, pas rejet
                'penalty': penalty,
                'correlation': max_correlation,
                'correlated_with': correlated_symbol
            }
        
        return {
            'valid': True,
            'penalty': 0,
            'correlation': max_correlation,
            'correlated_with': None
        }
```

**Fonctionnalités** :
- **Historique prix** : Maintient un historique de 50 prix par symbole (deque)
- **Corrélation Pearson** : Calcule la corrélation entre returns des prix
- **Fallback** : Si numpy non disponible, retourne 0.0 (pas d'erreur)
- **Mode SOFT** : Applique pénalité au score, ne rejette pas systématiquement
- **Pénalité progressive** : Plus la corrélation est forte, plus la pénalité est élevée

#### 5.3 Intégration dans `__init__()` (`core/analyzer.py`)

**Ajout dans `__init__()`** :
```python
# 🔥 PHASE 8: Corrélation dynamique
from core.correlation_dynamic import DynamicCorrelationFilter
dynamic_corr_config = TRADING_CONFIG.get('dynamic_correlation', {})
if dynamic_corr_config.get('enabled', False):
    self.correlation_filter = DynamicCorrelationFilter(
        period=dynamic_corr_config.get('period', 50),
        threshold=dynamic_corr_config.get('threshold', 0.7)
    )
else:
    self.correlation_filter = None
```

#### 5.4 Intégration dans `analyze_pair()` (`core/analyzer.py`)

**Ajout après vérification corrélation statique** :
```python
# 🔥 PHASE 8: Vérifier corrélation dynamique (basée sur prix réels)
dynamic_corr_config = TRADING_CONFIG.get('dynamic_correlation', {})
if dynamic_corr_config.get('enabled', False) and self.correlation_filter and active_positions:
    # Mettre à jour prix actuel pour corrélation
    current_price = best_setup.get('price', 0)
    if current_price > 0:
        self.correlation_filter.update_price(symbol, current_price)
    
    # Vérifier corrélation dynamique
    corr_check = self.correlation_filter.check_correlation(symbol, active_positions)
    
    if corr_check['penalty'] < 0:
        penalty = corr_check['penalty']
        max_penalty = dynamic_corr_config.get('max_penalty', -3.0)
        penalty = max(max_penalty, penalty)  # Limiter pénalité max
        
        if 'totalScore' in best_setup:
            best_setup['totalScore'] += penalty
            logger.warning(
                f"⚠️ {symbol} corrélé dynamiquement avec {corr_check['correlated_with']} "
                f"(corrélation: {corr_check['correlation']:.2f}) - "
                f"Pénalité: {penalty:.2f}, Score: {best_setup['totalScore']:.1f}"
            )
```

**Logique** :
1. Met à jour l'historique prix avec le prix actuel
2. Calcule la corrélation avec toutes les positions actives
3. Si corrélation > seuil : applique pénalité au score
4. Limite la pénalité à `max_penalty` (défaut: -3.0)

### Exemples de pénalité

| Corrélation | Seuil | Pénalité | Score (ex: 10.0) |
|-------------|-------|----------|------------------|
| 0.5 | 0.7 | 0 | 10.0 (pas de pénalité) |
| 0.8 | 0.7 | -0.5 | 9.5 |
| 0.9 | 0.7 | -1.0 | 9.0 |
| 0.95 | 0.7 | -1.5 | 8.5 |
| 1.0 | 0.7 | -2.0 | 8.0 |

### Points d'attention

- **Dépendance numpy** : Nécessite `numpy` installé (fallback si absent)
- **Période de chauffe** : Besoin de 20+ prix pour calculer corrélation
- **Performance** : Calcul pour chaque symbole vs chaque position active
- **Mode SOFT** : Pénalité au lieu de rejet (plus souple que filtre statique)

### Gain attendu

- **Winrate** : +1-2% (corrélation réelle au lieu d'approximation)
- **Précision** : Corrélation basée sur données réelles, pas groupes statiques
- **Adaptatif** : S'adapte aux conditions de marché

---

## 6️⃣ PERSISTANCE SQLITE

### Description

Remplacer/augmenter la persistance JSON par une base de données SQLite pour historique illimité et requêtes rapides.

### Fichiers créés/modifiés

- **`core/database.py`** : Nouveau fichier avec classe `TradeDatabase`
- **`main.py`** : Intégration de SQLite dans `save_trade_history()` et `load_trade_history()`
- **`.gitignore`** : Ignorer fichiers DB par instance

### Détails des modifications

#### 6.1 Classe `TradeDatabase` (`core/database.py`)

**Nouveau fichier créé** :
```python
"""
🔥 PHASE 8: Gestion base de données SQLite pour historique trades
Persistance illimitée avec requêtes rapides
"""
import sqlite3
import logging
import json
import os
import sys
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TradeDatabase:
    """Gestion base de données SQLite pour historique trades"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialiser base de données
        
        Args:
            db_path: Chemin vers fichier DB (si None, utilise instance-specific)
        """
        if db_path is None:
            # 🔥 FIX: Fichier DB par instance pour éviter conflits multi-instances
            port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
            db_path = f"trades_instance_{port}.db"
        
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialiser base de données et tables"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Retourner dict
        
        cursor = self.conn.cursor()
        
        # Table trades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry REAL NOT NULL,
                exit REAL NOT NULL,
                gross_pnl_pct REAL NOT NULL,
                gross_pnl_usdt REAL NOT NULL,
                net_pnl_pct REAL NOT NULL,
                net_pnl_usdt REAL NOT NULL,
                fees REAL DEFAULT 0,
                slippage REAL DEFAULT 0,
                total_costs REAL DEFAULT 0,
                reason TEXT,
                duration INTEGER,
                condition_types TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index pour performances
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON trades(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON trades(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON trades(timestamp)')
        
        self.conn.commit()
        logger.info(f"✅ Base de données initialisée: {self.db_path}")
    
    def insert_trade(self, trade: Dict) -> int:
        """Insérer un trade"""
        # ... (voir code complet)
    
    def get_all_trades(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict]:
        """Récupérer tous les trades"""
        # ... (voir code complet)
    
    def get_trades_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Récupérer trades par plage de dates"""
        # ... (voir code complet)
    
    def get_trades_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Récupérer trades par symbole"""
        # ... (voir code complet)
    
    def get_statistics(self) -> Dict:
        """Calculer statistiques globales"""
        # ... (voir code complet)
    
    def close(self):
        """Fermer connexion"""
        if self.conn:
            self.conn.close()
```

**Fonctionnalités** :
- **Fichier par instance** : `trades_instance_{port}.db` pour éviter conflits
- **Table trades** : Toutes les colonnes nécessaires
- **Index** : Sur `symbol`, `date`, `timestamp` pour performances
- **JSON fields** : `condition_types` et `metadata` stockés en JSON
- **Méthodes** : Insert, get all, get by date range, get by symbol, statistics

#### 6.2 Intégration dans `main.py`

**Ajout imports** :
```python
from core.database import TradeDatabase  # 🔥 PHASE 8: SQLite
```

**Variable globale** :
```python
# 🔥 PHASE 8: Instance globale TradeDatabase
trade_db = None

def init_trade_database():
    """Initialiser base de données SQLite"""
    global trade_db
    if TradeDatabase and not trade_db:
        try:
            trade_db = TradeDatabase()
            logger.info("✅ Base de données SQLite initialisée")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation DB: {e}")
            trade_db = None
```

**Modification `save_trade_history()`** :
```python
def save_trade_history():
    """Sauvegarder l'historique des trades dans un fichier JSON et SQLite"""
    global TRADE_HISTORY_FILE, trade_db
    
    # ... (sauvegarde JSON existante) ...
    
    # 🔥 PHASE 8: Sauvegarder aussi en SQLite (si activé)
    if trade_db and app_state['trade_history']:
        try:
            # Sauvegarder uniquement le dernier trade (éviter doublons)
            last_trade = app_state['trade_history'][0] if app_state['trade_history'] else None
            if last_trade:
                # Vérifier si déjà en DB (par timestamp)
                existing = trade_db.get_trades_by_date_range(
                    last_trade.get('date', ''),
                    last_trade.get('date', '')
                )
                # Si pas déjà présent, insérer
                if not any(t.get('timestamp') == last_trade.get('timestamp') for t in existing):
                    trade_db.insert_trade(last_trade)
                    logger.debug(f"✅ Trade sauvegardé en DB: {last_trade.get('symbol')}")
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde DB: {e}")
```

**Modification `load_trade_history()`** :
```python
def load_trade_history():
    """Charger l'historique des trades depuis un fichier JSON et/ou SQLite"""
    global TRADE_HISTORY_FILE, trade_db
    
    # 🔥 PHASE 8: Charger depuis SQLite si disponible (priorité)
    if trade_db:
        try:
            db_trades = trade_db.get_all_trades()
            if db_trades:
                app_state['trade_history'] = db_trades
                logger.info(f"✅ Historique chargé depuis DB: {len(db_trades)} trades")
                # Sauvegarder aussi en JSON (backup)
                save_trade_history()
                return
        except Exception as e:
            logger.error(f"❌ Erreur chargement DB: {e}")
    
    # Fallback: Charger depuis JSON
    # ... (chargement JSON existant) ...
    
    # 🔥 PHASE 8: Migrer JSON → SQLite si DB disponible
    if trade_db and app_state['trade_history']:
        try:
            for trade in app_state['trade_history']:
                # Vérifier si déjà en DB
                existing = trade_db.get_trades_by_date_range(
                    trade.get('date', ''),
                    trade.get('date', '')
                )
                if not any(t.get('timestamp') == trade.get('timestamp') for t in existing):
                    trade_db.insert_trade(trade)
            logger.info(f"✅ Migration JSON → SQLite: {len(app_state['trade_history'])} trades")
        except Exception as e:
            logger.error(f"❌ Erreur migration DB: {e}")
```

**Initialisation au démarrage** :
```python
if __name__ == '__main__':
    import uvicorn
    
    # 🔥 PHASE 8: Initialiser base de données SQLite
    init_trade_database()
    
    # 🔥 PHASE 4: Charger l'historique au démarrage
    load_trade_history()
```

#### 6.3 Mise à jour `.gitignore`

**Ajout** :
```
# Trade history files (multi-instance)
trade_history_instance_*.json
trade_history_instance_*.json.tmp
trades_instance_*.db
```

### Flux de données

1. **Au démarrage** :
   - Initialise DB SQLite (`trades_instance_{port}.db`)
   - Charge depuis DB si disponible (priorité)
   - Sinon charge depuis JSON
   - Migre JSON → SQLite si nécessaire

2. **Après chaque trade** :
   - Sauvegarde en JSON (backup)
   - Sauvegarde en SQLite (si pas déjà présent)

3. **Multi-instances** :
   - Chaque instance a son propre fichier DB
   - Pas de conflit entre instances

### Avantages SQLite

- **Historique illimité** : Pas de limite de 1000 trades
- **Requêtes rapides** : Index sur symbol, date, timestamp
- **Filtres avancés** : Par date range, symbole, etc.
- **Statistiques** : Calculs SQL optimisés
- **Backup JSON** : Double sauvegarde (JSON + SQLite)

### Points d'attention

- **Multi-instances** : Fichier DB par instance (pas de partage)
- **Migration** : Automatique JSON → SQLite au démarrage
- **Doublons** : Vérification par timestamp avant insertion
- **Performance** : Index créés pour optimiser requêtes

### Gain attendu

- **Historique illimité** : Pas de perte de données
- **Requêtes rapides** : Filtres par date/symbole optimisés
- **Statistiques** : Calculs SQL efficaces
- **Backup** : Double sauvegarde (JSON + SQLite)

---

## 📊 RÉSUMÉ DES FICHIERS MODIFIÉS

### Fichiers créés

1. **`core/correlation_dynamic.py`** - Classe `DynamicCorrelationFilter`
2. **`core/database.py`** - Classe `TradeDatabase`
3. **`ANALYSE_AMELIORATIONS_PROPOSEES_V2.md`** - Document d'analyse
4. **`DOCUMENTATION_PHASE_8.md`** - Ce document

### Fichiers modifiés

1. **`config.py`**
   - Recovery Mode Progressif (niveaux)
   - Seuils Adaptatifs ATR
   - Corrélation Dynamique

2. **`core/position_manager.py`**
   - `get_recovery_level()` - Nouvelle méthode
   - `get_adaptive_early_threshold()` - Nouvelle méthode
   - `calculate_adaptive_position_size()` - Intégration Recovery Mode Progressif
   - `_check_early_invalidation()` - Intégration seuils adaptatifs

3. **`core/analyzer.py`**
   - `__init__()` - Initialisation `correlation_filter`
   - `analyze_pair()` - Intégration Recovery Mode Progressif et Corrélation Dynamique

4. **`main.py`**
   - Imports : `List`, `Dict`, `csv`, `io`, `StreamingResponse`, `TradeDatabase`
   - `calculate_max_drawdown()` - Nouvelle fonction
   - `init_trade_database()` - Nouvelle fonction
   - `save_trade_history()` - Intégration SQLite
   - `load_trade_history()` - Intégration SQLite et migration
   - `get_dashboard_summary()` - Intégration Max Drawdown
   - `/api/export/trades` - Nouvel endpoint

5. **`.gitignore`**
   - Ignorer fichiers DB par instance

---

## 🔧 CONFIGURATION

### Activation/Désactivation

Toutes les fonctionnalités sont configurables dans `config.py` :

```python
# Recovery Mode Progressif
"recovery_mode": {
    "enabled": True,
    "mode": "PROGRESSIVE",  # ou "SIMPLE"
    ...
}

# Seuils Adaptatifs ATR
"adaptive_thresholds": {
    "enabled": True,
    ...
}

# Corrélation Dynamique
"dynamic_correlation": {
    "enabled": False,  # Désactivé par défaut (besoin numpy)
    ...
}
```

### Dépendances

- **numpy** : Requis pour Corrélation Dynamique (fallback si absent)
- **sqlite3** : Natif Python (pas d'installation nécessaire)

---

## ⚠️ POINTS D'ATTENTION

### Multi-instances

- **Fichiers par instance** : DB et JSON séparés par port
- **Pas de partage** : Chaque instance a son propre historique
- **Pas de conflit** : Isolation complète entre instances

### Performance

- **Corrélation Dynamique** : Calculs pour chaque symbole vs chaque position (peut être coûteux)
- **SQLite** : Index créés pour optimiser requêtes
- **Migration** : Automatique au démarrage (peut prendre du temps si beaucoup de trades)

### Compatibilité

- **Mode SIMPLE** : Disponible en fallback pour Recovery Mode
- **Fallback numpy** : Corrélation Dynamique désactivée si numpy absent
- **Backup JSON** : Toujours sauvegardé même avec SQLite

---

## 📈 GAINS ATTENDUS

| Amélioration | Winrate | Autres Gains |
|--------------|---------|--------------|
| Recovery Mode Progressif | +1-2% | Réaction proportionnelle |
| Seuils Adaptatifs ATR | +1-2% | -10-15% invalidations prématurées |
| Max Drawdown Tracking | - | Meilleure visibilité risque |
| Export CSV/JSON | - | Analyse externe facile |
| Corrélation Dynamique | +1-2% | Corrélation réelle |
| Persistance SQLite | - | Historique illimité |

**Total estimé** : Winrate +3-6%, Réduction risque -10-15%

---

## ✅ TESTS RECOMMANDÉS

1. **Recovery Mode Progressif** :
   - Vérifier activation niveau 1 (2 losses)
   - Vérifier activation niveau 2 (3 losses)
   - Vérifier activation niveau 3 (5 losses)
   - Vérifier réduction taille et boost score

2. **Seuils Adaptatifs ATR** :
   - Tester avec ATR faible (< 0.3%)
   - Tester avec ATR normal (0.3-0.8%)
   - Tester avec ATR élevé (> 0.8%)
   - Vérifier logs avec seuil adaptatif

3. **Max Drawdown Tracking** :
   - Vérifier calcul drawdown max
   - Vérifier drawdown actuel
   - Vérifier dates retournées

4. **Export CSV/JSON** :
   - Tester export CSV
   - Tester export JSON
   - Tester filtres par date

5. **Corrélation Dynamique** :
   - Vérifier calcul corrélation (si numpy disponible)
   - Vérifier pénalité appliquée
   - Vérifier fallback si numpy absent

6. **Persistance SQLite** :
   - Vérifier création DB par instance
   - Vérifier migration JSON → SQLite
   - Vérifier sauvegarde après chaque trade
   - Vérifier pas de doublons

---

## 📝 NOTES FINALES

- **Toutes les fonctionnalités sont optionnelles** : Peuvent être activées/désactivées via config
- **Compatibilité arrière** : Mode SIMPLE disponible pour Recovery Mode
- **Fallback** : Corrélation Dynamique désactivée si numpy absent (pas d'erreur)
- **Multi-instances** : Isolation complète (fichiers par instance)
- **Backup** : Double sauvegarde (JSON + SQLite)

---

**Dernière mise à jour** : 2025-01-06  
**Version** : v7.0  
**Commits** : `c18767d`, `0abf9b4`, `416d30f`


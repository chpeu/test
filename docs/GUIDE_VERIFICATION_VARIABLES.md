# Guide de Vérification des Variables Backend

Ce guide explique toutes les méthodes disponibles pour vérifier les variables enregistrées dans le backend et prises en compte par le bot.

## 📋 Table des Matières

1. [Méthodes de Vérification](#méthodes-de-vérification)
2. [Endpoints API REST](#endpoints-api-rest)
3. [WebSocket](#websocket)
4. [Fichier de Configuration](#fichier-de-configuration)
5. [Logs Backend](#logs-backend)
6. [Script Python](#script-python)

---

## 🔍 Méthodes de Vérification

### 1. **Endpoint API REST `/api/config`** (Variables principales)

**URL**: `GET http://localhost:5000/api/config`

**Description**: Retourne les variables principales utilisées par le frontend (sous-ensemble de TRADING_CONFIG).

**Exemple de réponse**:
```json
{
  "volume_multiplier": 0.95,
  "min_score_required": 7.5,
  "use_confluence": false,
  "tp_sl_mode": "FIXE",
  "tp_percent": 0.6,
  "sl_percent": 0.25,
  "snr_threshold": 0.25,
  "breakout_threshold": 0.35,
  "wick_ratio_max": 2.8,
  "di_gap_min": 4.0,
  "di_gap_adx_threshold": 25,
  "optimal_atr_min_1m": 0.12,
  "optimal_atr_max_1m": 0.75,
  "optimal_atr_min_5m": 0.22,
  "optimal_atr_max_5m": 1.4,
  "trend_timeframe": "15m",
  "account_size": 1000.0,
  "risk_per_trade": 2.0
}
```

**Avantages**:
- ✅ Rapide et simple
- ✅ Retourne les variables les plus utilisées

**Inconvénients**:
- ❌ Ne retourne pas toutes les variables
- ❌ Ne montre pas les variables avancées (recovery_mode, correlation_filter, etc.)

---

### 2. **Endpoint API REST `/api/config/complete`** ⭐ RECOMMANDÉ

**URL**: `GET http://localhost:5000/api/config/complete`

**Description**: Retourne **TOUTES** les variables de configuration (TRADING_CONFIG complet + autres configs).

**Exemple de réponse**:
```json
{
  "trading_config": {
    "fee_per_trade": 0.0004,
    "use_slippage_calculation": true,
    "position_timeout": 300,
    "check_interval": 0.1,
    "scan_interval": 45,
    "scalability_interval": 90,
    "volume_multiplier": 0.95,
    "tp_sl_mode": "FIXE",
    "tp_percent": 0.6,
    "sl_percent": 0.25,
    "atr_mult_tp": 1.5,
    "atr_mult_sl": 1.0,
    "atr_min": 0.15,
    "atr_max": 1.5,
    "trend_timeframe": "15m",
    "min_score_required": 7.5,
    "use_breakout": true,
    "use_snr": true,
    "use_wick": true,
    "use_divergence": true,
    "use_engulfing": true,
    "use_hammer": true,
    "use_shooting_star": true,
    "use_doji": true,
    "use_marubozu": true,
    "use_morning_star": true,
    "use_evening_star": true,
    "snr_threshold": 0.25,
    "breakout_threshold": 0.35,
    "wick_ratio_max": 2.8,
    "di_gap_min": 4.0,
    "di_gap_adx_threshold": 25,
    "optimal_atr_min_1m": 0.12,
    "optimal_atr_max_1m": 0.75,
    "optimal_atr_min_5m": 0.22,
    "optimal_atr_max_5m": 1.4,
    "volume_multiplier": 0.95,
    "top_pairs_limit": 20,
    "balance_score_min": 0.7,
    "use_confluence": false,
    "account_size": 1000.0,
    "risk_per_trade": 2.0,
    "early_invalidation": {
      "enabled": true,
      "delay": 10,
      "threshold_15s": -0.12,
      "threshold_30s": -0.08
    },
    "trailing_stop": {
      "enabled": true,
      "trigger_pnl": 0.25,
      "atr_multiplier": 0.4,
      "min_distance": 0.08,
      "max_distance": 0.25
    },
    "adaptive_thresholds": {
      "enabled": true,
      "early_invalidation": {
        "low_vol_multiplier": 0.7,
        "high_vol_multiplier": 1.3
      },
      "stagnation": {
        "low_vol_threshold": 0.015,
        "high_vol_threshold": 0.04
      }
    },
    "dynamic_correlation": {
      "enabled": false,
      "period": 50,
      "threshold": 0.7,
      "max_penalty": -3.0
    },
    "position_sizing": {
      "base_risk": 0.02,
      "min_risk": 0.005,
      "max_risk": 0.03,
      "quality_multipliers": {
        "excellent": 1.4,
        "good": 1.2,
        "acceptable": 1.0,
        "weak": 0.8
      },
      "streak_multipliers": {
        "win_streak_3+": 1.1,
        "loss_streak_2+": 0.85
      }
    },
    "correlation_filter": {
      "enabled": true,
      "mode": "SOFT",
      "max_positions_per_group": 2,
      "penalty_score": -1.5,
      "groups": {
        "BTC_GROUP": ["BTC", "ETH", "BNB", "SOL"],
        "MEME_GROUP": ["DOGE", "SHIB", "PEPE", "FLOKI", "BONK"],
        "LAYER1_GROUP": ["ADA", "DOT", "AVAX", "NEAR", "ATOM", "ALGO"],
        "DEFI_GROUP": ["UNI", "AAVE", "SUSHI", "LINK", "MKR", "CRV"],
        "L2_GROUP": ["MATIC", "ARB", "OP", "STRK", "IMX"],
        "EXCHANGE_GROUP": ["BNB", "FTT", "HT", "OKB"],
        "STABLECOIN_GROUP": ["USDC", "USDT", "DAI", "BUSD"]
      }
    },
    "recovery_mode": {
      "enabled": true,
      "mode": "PROGRESSIVE",
      "trigger_loss_streak": 3,
      "min_score_boost": 1.5,
      "position_size_reduction": 0.7,
      "confluence_forced": false,
      "duration_trades": 5,
      "levels": [
        {
          "trigger_loss_streak": 2,
          "min_score_boost": 0.5,
          "position_size_reduction": 0.85,
          "confluence_forced": false,
          "duration_trades": 3
        },
        {
          "trigger_loss_streak": 3,
          "min_score_boost": 1.5,
          "position_size_reduction": 0.7,
          "confluence_forced": false,
          "duration_trades": 5
        },
        {
          "trigger_loss_streak": 5,
          "min_score_boost": 2.5,
          "position_size_reduction": 0.5,
          "confluence_forced": true,
          "duration_trades": 7
        }
      ]
    },
    "partial_tp_percent": 50,
    "escalier_level1_pnl": 0.20,
    "escalier_level1_size": 25,
    "escalier_level2_pnl": 0.35,
    "escalier_level2_size": 25,
    "escalier_level3_pnl": 0.50,
    "escalier_level3_size": 25,
    "escalier_level4_pnl": 0.80,
    "escalier_level4_size": 25,
    "trailing_enabled": true,
    "trailing_trigger_pnl": 0.25,
    "trailing_atr_multiplier": 0.4,
    "trailing_min_distance": 0.08,
    "trailing_max_distance": 0.25,
    "tp_escalier": {
      "enabled": true,
      "levels": [
        {"pnl": 0.20, "size_pct": 0.25, "move_sl": "entry"},
        {"pnl": 0.35, "size_pct": 0.25, "move_sl": "breakeven"},
        {"pnl": 0.50, "size_pct": 0.25, "move_sl": "trailing"},
        {"pnl": 0.80, "size_pct": 0.25, "move_sl": "trailing"}
      ]
    }
  },
  "risk_config": {
    "base_risk": 0.02,
    "quality_multiplier_perfect": 1.5,
    "quality_multiplier_good": 1.2,
    "quality_multiplier_ok": 0.8,
    "quality_multiplier_weak": 0.5,
    "vol_multiplier_high": 0.7,
    "vol_multiplier_low": 1.3,
    "max_risk": 0.05,
    "min_risk": 0.005
  },
  "condition_weights": {
    "EMAs": 2.5,
    "ADX_DI": 2.5,
    "MACD": 2.0,
    "RSI": 1.5,
    "Volume": 1.5,
    "Bollinger": 0.8,
    "Pattern": 0.8,
    "Divergence": 1.0
  },
  "trend_bonus_config": {
    "use_direct_score": true,
    "bonus_divisor": 5
  },
  "retry_config": {
    "max_attempts": 5,
    "wait_multiplier": 1,
    "wait_min": 1,
    "wait_max": 10
  },
  "circuit_breaker_config": {
    "fail_max": 5,
    "reset_timeout": 60
  },
  "websocket_config": {
    "url": "wss://contract.mexc.com/edge",
    "ping_interval": 30,
    "reconnect_delay": 5,
    "timeout": 10,
    "watchdog_timeout": 30
  },
  "timestamp": 1700000000.0
}
```

**Avantages**:
- ✅ Retourne **TOUTES** les variables
- ✅ Inclut les configurations avancées (recovery_mode, correlation_filter, etc.)
- ✅ Inclut RISK_CONFIG, CONDITION_WEIGHTS, etc.

**Inconvénients**:
- ❌ Réponse volumineuse (peut être lente sur connexion lente)

---

### 3. **Endpoint API REST `/api/state`** (État complet)

**URL**: `GET http://localhost:5000/api/state`

**Description**: Retourne l'état complet de l'application (config + position + stats + trades).

**Exemple de réponse**:
```json
{
  "success": true,
  "session_id": "live_1700000000",
  "config": {
    "volume_multiplier": 0.95,
    "min_score_required": 7.5,
    "use_confluence": false,
    "tp_sl_mode": "FIXE",
    "tp_percent": 0.6,
    "sl_percent": 0.25,
    "snr_threshold": 0.25,
    "breakout_threshold": 0.35,
    "wick_ratio_max": 2.8,
    "di_gap_min": 4.0,
    "di_gap_adx_threshold": 25,
    "optimal_atr_min_1m": 0.12,
    "optimal_atr_max_1m": 0.75,
    "optimal_atr_min_5m": 0.22,
    "optimal_atr_max_5m": 1.4,
    "trend_timeframe": "15m",
    "account_size": 1000.0,
    "risk_per_trade": 2.0,
    "telegram_enabled": false
  },
  "scanner": {
    "is_scanning": true,
    "top_pairs": [...]
  },
  "position": {
    "active": true,
    "data": {...}
  },
  "stats": {
    "total_trades": 10,
    "wins": 7,
    "losses": 3,
    "winrate": 70.0
  },
  "trades": [...],
  "timestamp": 1700000000.0
}
```

**Avantages**:
- ✅ Retourne config + état actuel (position, stats, trades)
- ✅ Utile pour avoir une vue d'ensemble

**Inconvénients**:
- ❌ Ne retourne pas toutes les variables (sous-ensemble)

---

### 4. **WebSocket Request `state`**

**Description**: Via WebSocket, envoyer une requête de type `request` avec `request_type: 'state'`.

**Exemple de message**:
```json
{
  "type": "request",
  "request_type": "state",
  "id": "req_123"
}
```

**Réponse**:
```json
{
  "type": "request_response",
  "id": "req_123",
  "request_type": "state",
  "data": {
    "success": true,
    "session_id": "live_1700000000",
    "config": {...},
    "scanner": {...},
    "position": {...},
    "stats": {...},
    "trades": [...],
    "timestamp": 1700000000.0
  }
}
```

**Avantages**:
- ✅ Temps réel (pas de polling)
- ✅ Même format que `/api/state`

**Inconvénients**:
- ❌ Nécessite une connexion WebSocket active
- ❌ Ne retourne pas toutes les variables

---

### 5. **Fichier de Configuration `config.py`**

**Chemin**: `trade_cursor_py/config.py`

**Description**: Fichier source contenant toutes les variables par défaut.

**Avantages**:
- ✅ Source de vérité (valeurs par défaut)
- ✅ Facile à lire et modifier

**Inconvénients**:
- ❌ Ne montre pas les valeurs modifiées en runtime
- ❌ Nécessite d'accéder au serveur

---

### 6. **Logs Backend**

**Description**: Les logs du backend affichent les changements de configuration.

**Exemple de log**:
```
✅ Configuration mise à jour: {'volume_multiplier': 0.95, 'tp_percent': 0.6}
[19:23:45] INFO: Config mise à jour {'volume_multiplier': 0.95, 'tp_percent': 0.6}
```

**Avantages**:
- ✅ Historique des changements
- ✅ Utile pour déboguer

**Inconvénients**:
- ❌ Nécessite de surveiller les logs
- ❌ Ne montre pas l'état actuel complet

---

### 7. **Script Python (Vérification Programmatique)**

**Description**: Créer un script Python pour vérifier les variables.

**Exemple de script** (`verify_config.py`):
```python
#!/usr/bin/env python3
"""
Script pour vérifier les variables de configuration du bot
"""
import requests
import json

# URL du backend
BACKEND_URL = "http://localhost:5000"

def verify_config():
    """Vérifier la configuration complète"""
    try:
        # Récupérer config complète
        response = requests.get(f"{BACKEND_URL}/api/config/complete")
        if response.status_code == 200:
            config = response.json()
            
            print("=" * 70)
            print("📊 VARIABLES DE CONFIGURATION")
            print("=" * 70)
            
            # Afficher TRADING_CONFIG
            print("\n🔧 TRADING_CONFIG:")
            trading_config = config.get('trading_config', {})
            for key, value in sorted(trading_config.items()):
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"    {sub_key}: {sub_value}")
                else:
                    print(f"  {key}: {value}")
            
            # Afficher RISK_CONFIG
            print("\n⚠️ RISK_CONFIG:")
            risk_config = config.get('risk_config', {})
            for key, value in sorted(risk_config.items()):
                print(f"  {key}: {value}")
            
            # Afficher CONDITION_WEIGHTS
            print("\n⚖️ CONDITION_WEIGHTS:")
            condition_weights = config.get('condition_weights', {})
            for key, value in sorted(condition_weights.items()):
                print(f"  {key}: {value}")
            
            print("\n" + "=" * 70)
            print("✅ Vérification terminée")
            print("=" * 70)
            
        else:
            print(f"❌ Erreur: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    verify_config()
```

**Utilisation**:
```bash
python verify_config.py
```

**Avantages**:
- ✅ Automatisable
- ✅ Peut être intégré dans des tests
- ✅ Format personnalisable

**Inconvénients**:
- ❌ Nécessite d'écrire du code
- ❌ Nécessite `requests` installé

---

## 📝 Résumé des Méthodes

| Méthode | Variables Complètes | Temps Réel | Facilité | Recommandation |
|---------|---------------------|------------|----------|----------------|
| `/api/config` | ❌ | ❌ | ⭐⭐⭐⭐⭐ | Variables principales uniquement |
| `/api/config/complete` | ✅ | ❌ | ⭐⭐⭐⭐ | ⭐ **RECOMMANDÉ** pour vérification complète |
| `/api/state` | ❌ | ❌ | ⭐⭐⭐⭐ | Vue d'ensemble (config + état) |
| WebSocket `state` | ❌ | ✅ | ⭐⭐⭐ | Temps réel (config + état) |
| `config.py` | ✅ | ❌ | ⭐⭐⭐ | Valeurs par défaut uniquement |
| Logs Backend | ❌ | ✅ | ⭐⭐ | Historique des changements |
| Script Python | ✅ | ❌ | ⭐⭐ | Automatisation |

---

## 🎯 Recommandations

1. **Pour vérifier toutes les variables** : Utiliser `/api/config/complete`
2. **Pour vérifier rapidement les variables principales** : Utiliser `/api/config`
3. **Pour vérifier l'état complet (config + position + stats)** : Utiliser `/api/state` ou WebSocket `state`
4. **Pour automatiser la vérification** : Créer un script Python
5. **Pour déboguer les changements** : Surveiller les logs backend

---

## 🔧 Exemples d'Utilisation

### cURL
```bash
# Variables principales
curl http://localhost:5000/api/config

# Toutes les variables
curl http://localhost:5000/api/config/complete

# État complet
curl http://localhost:5000/api/state
```

### Python
```python
import requests

# Variables principales
response = requests.get("http://localhost:5000/api/config")
config = response.json()

# Toutes les variables
response = requests.get("http://localhost:5000/api/config/complete")
complete_config = response.json()

# État complet
response = requests.get("http://localhost:5000/api/state")
state = response.json()
```

### JavaScript (Frontend)
```javascript
// Variables principales
const config = await fetch('/api/config').then(r => r.json());

// Toutes les variables
const completeConfig = await fetch('/api/config/complete').then(r => r.json());

// État complet
const state = await fetch('/api/state').then(r => r.json());
```

---

## 📌 Notes Importantes

1. **Les variables modifiées en runtime** sont stockées dans `TRADING_CONFIG` (dictionnaire Python en mémoire).
2. **Persistance**: les changements appliqués via l'UI / WebSocket peuvent être persistés dans `config_overrides.json` (voir `utils/config_persistence.py`). Au démarrage, ces overrides sont rechargés et appliqués sur `TRADING_CONFIG`.
3. **Les variables sont validées** lors de la modification (clamp, validation de type, etc.).
4. **Les variables sont synchronisées** avec le frontend via WebSocket (`config_updated` event).

---

## 🐛 Dépannage

### Problème : Les variables ne sont pas prises en compte

1. Vérifier que le backend est démarré
2. Vérifier que les variables sont bien dans `TRADING_CONFIG` via `/api/config/complete`
3. Vérifier les logs backend pour voir si les variables sont bien chargées
4. Vérifier que `init_instances()` est appelé après modification

### Problème : Les variables ne persistent pas

1. Vérifier que `config_overrides.json` existe à la racine du projet et contient les clés attendues
2. Vérifier dans les logs backend: `Config overrides chargés` puis `overrides appliqués sur TRADING_CONFIG`
3. Vérifier que la clé a un préfixe autorisé (ex: `market_regime_`, `ml_`, `gb_`) si elle n'existe pas encore en dur dans `TRADING_CONFIG`
4. Les valeurs par défaut restent dans `config.py`

---

## 🧪 Scripts de Vérification (régime V2)

### Script: `verification/verify_regime_v2_params.py`

Ce script simule une séquence d'ATR et vérifie que:
- le lissage (EMA) est appliqué si activé
- l'hystérésis bloque les flip-flops autour des seuils
- `market_regime_min_duration_minutes` bloque les changements dans les deux sens

---

 **Dernière mise à jour** : 2025-12-12

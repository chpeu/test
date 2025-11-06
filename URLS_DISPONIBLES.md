# 📍 URLs DISPONIBLES - Trade Cursor v7.0

**Mise à jour**: 2025-11-06  
**Version**: Architecture V2 Intégrée

---

## 🔧 Multi-Instances

Le bot supporte **plusieurs instances** sur différents ports.

### Démarrage

```bash
# Instance 1 (port par défaut: 5000)
python main.py

# Instance 2 (port personnalisé: 5001)
python main.py 5001

# Instance 3 (port personnalisé: 5002)
python main.py 5002
```

⚠️ **Important**: Chaque instance a son propre port et fichier historique unique.

---

## 🌐 URLs PAR INSTANCE

Remplacer `{PORT}` par le port de votre instance (5000, 5001, 5002, etc.)

### 1️⃣ Interface Utilisateur

#### 🏠 Interface Principale
```
http://localhost:{PORT}/
```
- Interface HTML complète
- Contrôles scanner (Start/Stop)
- Liste positions actives
- Historique trades
- Top pairs

#### 📊 Dashboard Graphiques (🔥 Nouveau V2)
```
http://localhost:{PORT}/dashboard/charts
```
- Equity Curve
- Win/Loss Ratio
- Distribution PnL
- Trades par symbole
- Performance horaire
- Raisons fermeture
- **Temps réel** via WebSocket

---

### 2️⃣ API REST (🔥 V2)

Base URL: `http://localhost:{PORT}/api`

#### 💚 Health Check
```bash
GET http://localhost:{PORT}/api/health
```
**Réponse**:
```json
{
  "status": "ok",
  "timestamp": 1730929200.123,
  "service": "Trading Bot API"
}
```

#### 📈 Stats Globales
```bash
GET http://localhost:{PORT}/api/stats
```
**Réponse**:
```json
{
  "success": true,
  "stats": {
    "total_trades": 42,
    "wins": 28,
    "losses": 14,
    "winrate": 66.67,
    "profit_factor": 1.85,
    "max_drawdown": 5.2,
    "capital": 1050.25
  }
}
```

**Avec filtres**:
```bash
GET http://localhost:{PORT}/api/stats?symbol=BTC/USDT:USDT&start_date=2025-11-01
```

#### 📋 Trades (avec filtres)
```bash
GET http://localhost:{PORT}/api/trades?limit=10
```
**Paramètres optionnels**:
- `limit` (1-1000) - Max résultats
- `offset` - Pagination
- `symbol` - Filtrer par symbole
- `direction` - LONG ou SHORT
- `exit_reason` - TP, SL, TS, etc.
- `trading_mode` - LIVE, PAPER, BACKTEST
- `start_date` - Date début (YYYY-MM-DD)
- `end_date` - Date fin (YYYY-MM-DD)

**Exemples**:
```bash
# 10 derniers trades
GET http://localhost:{PORT}/api/trades?limit=10

# Trades BTC LONG uniquement
GET http://localhost:{PORT}/api/trades?symbol=BTC/USDT:USDT&direction=LONG

# Trades fermés en TP
GET http://localhost:{PORT}/api/trades?exit_reason=TP

# Trades d'aujourd'hui
GET http://localhost:{PORT}/api/trades?start_date=2025-11-06
```

#### ❌ Setups Rejetés
```bash
GET http://localhost:{PORT}/api/setups/rejected?limit=50
```
**Paramètres**:
- `limit`, `offset`, `symbol`, `direction`
- `start_date`, `end_date`

**Réponse**:
```json
{
  "success": true,
  "count": 15,
  "setups": [
    {
      "symbol": "ETH/USDT:USDT",
      "direction": "LONG",
      "rejection_reason": "Spread trop élevé",
      "rejection_category": "spread",
      "timestamp": 1730929200.456,
      "spread_bps": 35,
      "price": 2450.50
    }
  ]
}
```

#### ✅ Setups Validés
```bash
GET http://localhost:{PORT}/api/setups/validated?limit=50
```
**Paramètres**: identiques à setups rejetés

#### 📥 Export Données
```bash
# Export CSV
GET http://localhost:{PORT}/api/export?format=csv&data_type=trades

# Export JSON
GET http://localhost:{PORT}/api/export?format=json&data_type=setups_rejected
```
**Paramètres**:
- `format` - csv ou json
- `data_type` - trades, setups_rejected, setups_validated
- `symbol` - Filtrer par symbole
- `start_date`, `end_date` - Période

**Réponse CSV**: Téléchargement fichier `trades_1730929200.csv`

#### 🔄 Backtest (POST)
```bash
POST http://localhost:{PORT}/api/backtest
Content-Type: application/json

{
  "symbols": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
  "start_date": "2025-01-01",
  "end_date": "2025-02-01",
  "initial_capital": 1000.0,
  "config": {
    "tp_pct_fixed": 0.5,
    "sl_pct_fixed": 0.3
  }
}
```
**Réponse**:
```json
{
  "success": true,
  "results": {
    "total_trades": 125,
    "winrate": 62.4,
    "profit_factor": 1.68,
    "sharpe_ratio": 1.42,
    "max_drawdown": 8.5,
    "final_capital": 1123.45
  }
}
```

#### 🤖 ML Optimize (POST)
```bash
POST http://localhost:{PORT}/api/optimize
Content-Type: application/json

{
  "symbols": ["BTC/USDT:USDT"],
  "start_date": "2025-01-01",
  "end_date": "2025-02-01",
  "n_trials": 100,
  "initial_capital": 1000.0
}
```
**Réponse**:
```json
{
  "success": true,
  "results": {
    "best_params": {
      "tp_pct_fixed": 0.65,
      "sl_pct_fixed": 0.28,
      "tp_atr_mult": 1.8,
      "tp_sl_mode": "ATR"
    },
    "best_value": 1.523,
    "n_trials": 100
  }
}
```

---

### 3️⃣ WebSocket (Temps Réel)

#### Socket.IO
```
ws://localhost:{PORT}/socket.io/
```

**Events disponibles**:
- `connect` - Connexion établie
- `status` - État scanner
- `top_pairs_update` - Mise à jour top pairs
- `position_opened` - Position ouverte
- `position_closed` - Position fermée
- `tp_escalier_level` - TP Escalier niveau atteint
- `stats_update` - Stats mises à jour

**Exemple JavaScript**:
```javascript
const socket = io('http://localhost:{PORT}');

socket.on('connect', () => {
    console.log('Connected');
});

socket.on('position_closed', (data) => {
    console.log('Position fermée:', data);
});
```

---

## 📋 EXEMPLES CURL

### Get Stats
```bash
curl http://localhost:5000/api/stats
```

### Get Last 10 Trades
```bash
curl "http://localhost:5000/api/trades?limit=10"
```

### Export Trades CSV
```bash
curl "http://localhost:5000/api/export?format=csv&data_type=trades" -o trades.csv
```

### Backtest (POST)
```bash
curl -X POST http://localhost:5000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTC/USDT:USDT"],
    "start_date": "2025-01-01",
    "end_date": "2025-02-01",
    "initial_capital": 1000
  }'
```

---

## 🔒 Rate Limiting

**Limite**: 100 requêtes / minute par IP

Si dépassé:
```json
{
  "detail": "Too many requests. Please try again later."
}
```
**Status Code**: 429

---

## 📊 EXEMPLES D'INTÉGRATION

### Python
```python
import requests

# Get stats
response = requests.get('http://localhost:5000/api/stats')
stats = response.json()
print(f"Winrate: {stats['stats']['winrate']}%")

# Get trades
response = requests.get('http://localhost:5000/api/trades', params={'limit': 10})
trades = response.json()
print(f"{trades['count']} trades récupérés")
```

### JavaScript
```javascript
// Get stats
fetch('http://localhost:5000/api/stats')
  .then(res => res.json())
  .then(data => {
    console.log('Winrate:', data.stats.winrate + '%');
  });

// Get trades
fetch('http://localhost:5000/api/trades?limit=10')
  .then(res => res.json())
  .then(data => {
    console.log(data.count + ' trades');
  });
```

---

## 🌐 ACCÈS EXTERNE (Réseau Local)

Pour accéder depuis un autre appareil sur votre réseau:

1. Trouver votre IP locale:
```bash
ipconfig  # Windows
ifconfig  # Linux/Mac
```

2. Remplacer `localhost` par votre IP:
```
http://192.168.1.XXX:{PORT}/
http://192.168.1.XXX:{PORT}/dashboard/charts
http://192.168.1.XXX:{PORT}/api/stats
```

⚠️ **Sécurité**: Par défaut, le serveur écoute sur `0.0.0.0` (toutes interfaces).

---

## 📱 ACCÈS MOBILE

### Depuis votre téléphone (même WiFi)

1. Trouver IP de votre PC: `192.168.1.XXX`
2. Ouvrir navigateur mobile
3. Aller sur: `http://192.168.1.XXX:{PORT}/dashboard/charts`

**Dashboard optimisé** pour mobile ! 📱

---

## 🔧 DÉPANNAGE

### Port déjà utilisé
```
OSError: [WinError 10048] Une seule utilisation de chaque adresse
```
**Solution**: Utiliser un port différent
```bash
python main.py 5001
```

### API ne répond pas
```bash
# Vérifier que le serveur est démarré
curl http://localhost:{PORT}/api/health
```

### Dashboard vide
1. Vérifier que l'API fonctionne: `/api/health`
2. Ouvrir console navigateur (F12) pour erreurs JavaScript
3. Vérifier WebSocket connecté (🟢 Connecté)

---

## 📚 DOCUMENTATION COMPLÈTE

- Architecture V2: `README_ARCHITECTURE_V2.md`
- Intégration: `INTEGRATION_V2_COMPLETE.md`
- Guide API: Ce document

---

## ✅ RÉSUMÉ RAPIDE

| URL | Type | Description |
|-----|------|-------------|
| `/` | GET | Interface principale |
| `/dashboard/charts` | GET | Dashboard graphiques |
| `/api/health` | GET | Health check |
| `/api/stats` | GET | Stats globales |
| `/api/trades` | GET | Liste trades |
| `/api/setups/rejected` | GET | Setups rejetés |
| `/api/setups/validated` | GET | Setups validés |
| `/api/export` | GET | Export CSV/JSON |
| `/api/backtest` | POST | Lancer backtest |
| `/api/optimize` | POST | ML optimization |

**WebSocket**: `ws://localhost:{PORT}/socket.io/`

---

**🎉 Toutes les URLs sont prêtes à l'emploi !**

**Bon trading ! 🚀📈**


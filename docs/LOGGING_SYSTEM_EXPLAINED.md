# 📝 Système de Logging : Explication complète

## 🎯 Question : Pourquoi tous les logs ne sont pas dans PostgreSQL ?

**Réponse courte** : Parce qu'il y a **2 systèmes différents** qui servent des objectifs distincts.

---

## 📊 Les deux systèmes de logging

### 1. **Logs d'application** (Console / Frontend) 🖥️

#### C'est quoi ?
Messages textuels pour le debugging et le monitoring en temps réel.

#### Exemples
```
[22:15:30] INFO - 🔍 Scan 1m: 125 paires analysées en 2.3s
[22:15:32] WARNING - ⚠️ Invalidation précoce LONG LTC: P&L -0.15%
[22:15:35] INFO - ✅ Setup LONG BTC détecté: score 9.3/7.0
[22:15:37] ERROR - ❌ Erreur WebSocket MEXC: Connection timeout
```

#### Où vont-ils ?
- ✅ **Console** (terminal)
- ✅ **Frontend** (via WebSocket en temps réel)
- ❌ **PostgreSQL** → **NON, CE N'EST PAS LEUR DESTINATION**

#### Code source
`utils/logger.py` + `logging.Logger` standard Python

#### Objectif
- Debugging en direct
- Monitoring du bot
- Alertes en temps réel

---

### 2. **Données de trading** (PostgreSQL) 🗄️

#### C'est quoi ?
Données **structurées** pour l'analyse ML et l'optimisation.

#### Exemples de tables
```sql
-- scan_logs : Tous les scans effectués
timestamp | symbol | price | rsi_1m | score | is_opportunity
----------|--------|-------|--------|-------|---------------
22:15:30  | BTC    | 50000 | 45.2   | 9.3   | true
22:15:32  | ETH    | 3000  | 32.1   | 6.8   | false

-- opportunities : Opportunités détectées
id | symbol | direction | entry | tp | sl | score | status
---|--------|-----------|-------|----|----|-------|-------
1  | BTC    | LONG      | 50000 | 50250 | 49875 | 9.3 | PENDING

-- trades : Trades exécutés
id | symbol | direction | entry | exit | pnl_pct | reason | duration_s
---|--------|-----------|-------|------|---------|--------|------------
1  | LTC    | LONG      | 82.11 | 81.99| -0.15   | EARLY_INV | 12
```

#### Où vont-elles ?
- ✅ **PostgreSQL** (table `scan_logs`, `opportunities`, `trades`)
- ❌ **Console** → Non (sauf si erreur)
- ❌ **Frontend** → Oui, mais via API REST, pas WebSocket logs

#### Code source
`core/postgresql_datalogger.py` → `PostgreSQLDataLogger`

#### Objectif
- Training ML (XGBoost)
- Analyse des performances
- Backtesting
- Optimisation des paramètres

---

## 🔍 Pourquoi cette séparation ?

### Raisons techniques

#### Performance
```
Logs console : 1000-5000 messages/minute
Données PostgreSQL : 10-50 inserts/minute (batch)

Si on enregistrait TOUS les logs console dans PostgreSQL :
→ 5000 INSERT/minute = 83 INSERT/seconde
→ Surcharge énorme de la base de données
→ Ralentissement du bot
```

#### Volumétrie
```
Logs console (24h) : ~100 000 messages = ~10 MB texte
Données PostgreSQL (24h) : ~1000 scans = ~500 KB structuré

Si on stockait tout :
→ 100 000 rows/jour dans PostgreSQL
→ 3 millions rows/mois
→ Base de données ingérable
```

#### Utilité
```
Log console : "🔍 Scan 1m: 125 paires analysées en 2.3s"
→ Utile pour debugging EN TEMPS RÉEL
→ Aucune valeur pour l'analyse ML

Donnée PostgreSQL : {symbol: "BTC", rsi: 45.2, score: 9.3}
→ Données structurées pour ML
→ Permet de prédire les trades gagnants
```

---

## 📋 Tableau comparatif

| Critère | Logs Console | Données PostgreSQL |
|---------|--------------|-------------------|
| **Format** | Texte libre | JSON structuré |
| **Volume** | 100k msg/jour | 1k scans/jour |
| **Destination** | Console + Frontend | PostgreSQL |
| **Objectif** | Debugging | Analyse ML |
| **Durée de vie** | Session (perdu au redémarrage) | Permanent |
| **Recherchable** | Non (scroll manuel) | Oui (SQL) |
| **Utilisé pour ML** | ❌ Non | ✅ Oui |

---

## 🎓 Que contient PostgreSQL exactement ?

### Table `scan_logs`

**Chaque scan (toutes les 45s) enregistre** :
```python
{
    'timestamp': '2025-11-21 22:15:30',
    'session_id': 'uuid-session',
    'symbol': 'BTCUSDT',
    'scan_duration_ms': 234,
    'price': 50000.0,
    'spread_pct': 0.02,
    'book_depth': 500000.0,
    'balance_score': 1.15,
    'bid_vol': 250000,
    'ask_vol': 220000,
    'orderbook_imbalance_ratio': 1.14,
    'volatility_1m': 0.45,
    'rsi_1m': 45.2,
    'macd_1m': 12.5,
    'adx_1m': 28.3,
    'volume_spike_1m': 1.8,
    'score_total': 9.3,
    'nb_conditions_met': 7,
    'is_opportunity': True,
    'rejection_reason': None
}
```

**Fréquence** : Toutes les 45 secondes (paramètre `scan_interval`)

**Nombre par jour** : ~1920 scans (si 24h d'activité)

---

### Table `opportunities`

**Chaque opportunité détectée enregistre** :
```python
{
    'symbol': 'BTCUSDT',
    'direction': 'LONG',
    'timeframe': '1m',
    'entry': 50000.0,
    'tp': 50250.0,
    'sl': 49875.0,
    'score': 9.3,
    'nb_conditions': 7,
    'conditions': ['EMAs', 'RSI', 'Volume', 'ADX', 'MACD', 'Breakout', 'Trend'],
    'indicators': {...},  # Tous les indicateurs
    'status': 'PENDING',  # PENDING, OPENED, REJECTED, EXPIRED
    'created_at': '2025-11-21 22:15:30'
}
```

**Fréquence** : Variable (dépend du marché, 5-20 par jour)

---

### Table `trades`

**Chaque trade exécuté enregistre** :
```python
{
    'symbol': 'LTCUSDT',
    'direction': 'LONG',
    'entry': 82.110,
    'exit': 81.987,
    'pnl_pct': -0.15,
    'pnl_usdt': -1.50,
    'reason': 'EARLY_INVALIDATION',
    'duration_seconds': 12,
    'entry_time': '2025-11-21 22:15:30',
    'exit_time': '2025-11-21 22:15:42',
    'win': False,
    'entry_conditions': [...],
    'entry_indicators': {...},
    'exit_indicators': {...}
}
```

**Fréquence** : Variable (dépend du trading, 3-15 par jour)

---

## ❓ Alors, comment voir TOUS les logs ?

### Option 1 : Logs console (temps réel) ✅ ACTUEL

**Avantages** :
- ✅ Temps réel
- ✅ Tous les messages de debugging
- ✅ Colorés et émojis
- ✅ Pas de surcharge

**Inconvénients** :
- ❌ Perdus au redémarrage
- ❌ Pas searchable (scroll manuel)
- ❌ Pas d'analyse possible

**Comment y accéder** :
- Console (terminal où tourne `python main.py`)
- Frontend : Onglet **Logs** en temps réel

---

### Option 2 : Fichiers de logs (nouveau, à implémenter) 💡

Si tu veux **TOUS les logs console persistés**, on peut ajouter un **FileHandler** :

```python
# utils/logger.py

def setup_logger(name, level, ws_manager=None, log_to_file=True):
    logger = logging.getLogger(name)
    
    # Console handler (existant)
    console_handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(console_handler)
    
    # 🆕 File handler (NOUVEAU)
    if log_to_file:
        file_handler = logging.FileHandler('logs/app.log', mode='a')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
```

**Avantages** :
- ✅ Tous les logs console persistés
- ✅ Searchable (grep, find)
- ✅ Pas de surcharge PostgreSQL
- ✅ Facile à implémenter

**Inconvénients** :
- ⚠️ Fichiers peuvent devenir volumineux
- ⚠️ Rotation nécessaire (logrotate)

---

### Option 3 : Logs PostgreSQL (lourd, pas recommandé) ⚠️

Si tu veux **vraiment** tous les logs dans PostgreSQL :

#### Nouvelle table `application_logs`
```sql
CREATE TABLE application_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    level VARCHAR(20),
    message TEXT,
    module VARCHAR(100),
    function VARCHAR(100),
    line_number INT
);
```

#### Handler personnalisé
```python
class PostgreSQLLogHandler(logging.Handler):
    def emit(self, record):
        # INSERT INTO application_logs
        pass
```

**Avantages** :
- ✅ Tous les logs dans PostgreSQL
- ✅ Searchable via SQL
- ✅ Centralisation

**Inconvénients** :
- ❌ 100k+ INSERT/jour
- ❌ Surcharge énorme de la base
- ❌ Ralentissement du bot
- ❌ Pas nécessaire pour l'objectif

---

## 🎯 Recommandation finale

### Configuration actuelle (optimale) ✅

```
Logs console → Console + Frontend (temps réel)
Données trading → PostgreSQL (analyse ML)
```

**C'est optimal pour** :
- Performance
- Scalabilité
- Objectif (trading + ML)

---

### Si tu veux persister les logs console

**Solution recommandée** : **Option 2 (FileHandler)**

#### Implémentation (5 min)

1. Créer dossier `logs/`
```bash
mkdir logs
```

2. Modifier `utils/logger.py` :
```python
def setup_logger(name, level, ws_manager=None, log_to_file=True):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if DEBUG_ENABLED else level)
    
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if DEBUG_ENABLED else level)
    formatter = ColoredFormatter(
        '[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 🆕 File handler
    if log_to_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5  # Garder 5 fichiers max
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # WebSocket handler
    if ws_manager:
        ws_handler = WebSocketLogHandler()
        ws_handler.set_ws_manager(ws_manager)
        ws_handler.setLevel(logging.DEBUG if DEBUG_ENABLED else level)
        logger.addHandler(ws_handler)
    
    return logger
```

3. Résultat :
```
logs/
  app.log       (fichier actuel)
  app.log.1     (rotation)
  app.log.2
  ...
```

4. Rechercher dans les logs :
```bash
# Chercher "EARLY_INVALIDATION"
grep "EARLY_INVALIDATION" logs/app.log

# Chercher les erreurs
grep "ERROR" logs/app.log

# Dernières 100 lignes
tail -n 100 logs/app.log
```

---

## 📊 Résumé visuel

```
┌─────────────────────────────────────────────────────────┐
│                    ARCHITECTURE ACTUELLE                │
└─────────────────────────────────────────────────────────┘

Scanner détecte un setup
         │
         ├─→ Log console: "✅ Setup LONG BTC détecté"
         │   └─→ Console (terminal) ✅
         │   └─→ Frontend WebSocket ✅
         │   └─→ PostgreSQL ❌ (pas enregistré)
         │
         └─→ Données structurées: {symbol: BTC, score: 9.3, ...}
             └─→ PostgreSQL.scan_logs ✅
             └─→ Console ❌ (sauf debug)


┌─────────────────────────────────────────────────────────┐
│              AVEC FILE HANDLER (RECOMMANDÉ)             │
└─────────────────────────────────────────────────────────┘

Scanner détecte un setup
         │
         ├─→ Log console: "✅ Setup LONG BTC détecté"
         │   └─→ Console (terminal) ✅
         │   └─→ Frontend WebSocket ✅
         │   └─→ logs/app.log ✅ (NOUVEAU)
         │   └─→ PostgreSQL ❌
         │
         └─→ Données structurées: {symbol: BTC, score: 9.3, ...}
             └─→ PostgreSQL.scan_logs ✅
```

---

## ✅ Conclusion

**Les logs console ne DOIVENT PAS être dans PostgreSQL** pour des raisons de performance et de conception.

**Si tu veux les persister** :
- ✅ **Recommandé** : FileHandler (`logs/app.log`)
- ❌ **Pas recommandé** : PostgreSQL (100k+ INSERT/jour)

**PostgreSQL est réservé aux données de trading** :
- `scan_logs` : Données de scan (1920/jour)
- `opportunities` : Opportunités détectées (5-20/jour)
- `trades` : Trades exécutés (3-15/jour)

Tu veux que j'implémente le FileHandler pour persister tous les logs ? 🚀

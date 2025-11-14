# ✅ Guide de Vérification Complète - PostgreSQL Datalogger

**Date :** 2025-11-12

---

## 📋 Checklist de Vérification

### ✅ Étape 1 : Vérifier le Schéma SQL

#### 1.1 Vérifier que la migration a été appliquée

```sql
-- Se connecter à PostgreSQL
psql -U postgres -d trade_cursor_ml

-- Compter les colonnes de trades
SELECT COUNT(*) as total_columns
FROM information_schema.columns
WHERE table_name = 'trades';
-- ✅ Attendu: ~115 colonnes

-- Vérifier les colonnes early_invalidation
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'trades' 
AND column_name LIKE 'early_invalidation%'
ORDER BY column_name;
-- ✅ Attendu: 6 colonnes (triggered, triggered_at, threshold, elapsed, atr_pct, pnl_pct)

-- Vérifier config_snapshot
SELECT column_name, data_type
FROM information_schema.columns 
WHERE table_name = 'trades' 
AND column_name = 'config_snapshot';
-- ✅ Attendu: config_snapshot JSONB

-- Vérifier market_context JSONB
SELECT column_name, data_type
FROM information_schema.columns 
WHERE table_name = 'market_context' 
AND column_name IN ('global_metrics', 'session_stats');
-- ✅ Attendu: 2 colonnes JSONB
```

#### 1.2 Vérifier les index

```sql
-- Vérifier les index sur trades
SELECT indexname 
FROM pg_indexes 
WHERE tablename = 'trades' 
ORDER BY indexname;
-- ✅ Vérifier que les index temporels et early_invalidation existent
```

---

### ✅ Étape 2 : Vérifier le Code Python

#### 2.1 Vérifier que le code est à jour

```bash
# Vérifier que les fichiers ont été modifiés récemment
cd "C:\Users\sebta\Documents\clone github\test\test"

# Vérifier postgresql_datalogger.py
git log -1 --format="%h %s" core/postgresql_datalogger.py

# Vérifier position_manager.py
git log -1 --format="%h %s" core/position_manager.py
```

#### 2.2 Vérifier les imports et syntaxe

```bash
# Vérifier la syntaxe Python (sans erreur)
python -m py_compile core/postgresql_datalogger.py
python -m py_compile core/position_manager.py
python -m py_compile core/callbacks/scanner_loop.py
```

---

### ✅ Étape 3 : Vérifier la Configuration

#### 3.1 Vérifier les variables d'environnement

```bash
# Vérifier que .env existe et contient les bonnes variables
cd "C:\Users\sebta\Documents\clone github\test\test"

# Afficher les variables PostgreSQL (sans afficher le mot de passe)
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('POSTGRES_ENABLED:', os.getenv('POSTGRES_ENABLED')); print('POSTGRES_HOST:', os.getenv('POSTGRES_HOST')); print('POSTGRES_DB:', os.getenv('POSTGRES_DB')); print('POSTGRES_USER:', os.getenv('POSTGRES_USER'))"
```

**✅ Vérifier :**
- `POSTGRES_ENABLED=true`
- `POSTGRES_HOST=localhost` (ou votre host)
- `POSTGRES_DB=trade_cursor_ml`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD` est défini

---

### ✅ Étape 4 : Vérifier la Connexion PostgreSQL

#### 4.1 Test de connexion simple

```bash
# Tester la connexion
psql -U postgres -d trade_cursor_ml -c "SELECT version();"
```

#### 4.2 Test avec Python

```python
# Créer un fichier test_connection.py
import os
from dotenv import load_dotenv
load_dotenv()

try:
    import psycopg2
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    print("✅ Connexion PostgreSQL réussie!")
    conn.close()
except Exception as e:
    print(f"❌ Erreur connexion: {e}")
```

---

### ✅ Étape 5 : Vérifier le Datalogger au Démarrage

#### 5.1 Démarrer l'application

```bash
cd "C:\Users\sebta\Documents\clone github\test\test"
python main.py
```

#### 5.2 Vérifier les logs

**✅ Rechercher dans les logs :**
```
✅ PostgreSQL DataLogger initialisé: trade_cursor_ml@localhost:5432
✅ PostgreSQL DataLogger initialisé
✅ Tâche périodique contexte marché démarrée
```

**❌ Si vous voyez :**
```
❌ psycopg2 non disponible - PostgreSQL DataLogger désactivé
```
→ Installer : `pip install psycopg2-binary==2.9.9`

```
❌ Erreur connexion PostgreSQL: fe_sendauth: no password supplied
```
→ Vérifier `POSTGRES_PASSWORD` dans `.env`

---

### ✅ Étape 6 : Vérifier les Scans

#### 6.1 Attendre quelques scans (45 secondes par scan)

#### 6.2 Vérifier dans PostgreSQL

```sql
-- Vérifier que les scans sont loggés
SELECT 
    id, 
    timestamp, 
    symbol, 
    scan_duration_ms,
    is_opportunity,
    score_total
FROM scan_logs 
ORDER BY timestamp DESC 
LIMIT 10;
-- ✅ Attendu: Des scans loggés

-- Compter les scans
SELECT COUNT(*) as total_scans FROM scan_logs;
-- ✅ Attendu: > 0 après quelques minutes

-- Vérifier que les indicateurs sont remplis
SELECT 
    symbol,
    rsi_1m,
    macd_hist_1m,
    adx_1m,
    ema9_1m,
    bb_upper_1m,
    volume_ratio_1m
FROM scan_logs 
WHERE rsi_1m IS NOT NULL
LIMIT 5;
-- ✅ Attendu: Des indicateurs non NULL
```

---

### ✅ Étape 7 : Vérifier les Opportunités

```sql
-- Vérifier les opportunités
SELECT 
    id,
    timestamp,
    symbol,
    status,
    direction,
    setup_score,
    entry_suggested,
    tp_suggested,
    sl_suggested
FROM opportunities 
ORDER BY timestamp DESC 
LIMIT 10;
-- ✅ Attendu: Des opportunités si des setups sont détectés

-- Vérifier le lien avec scan_logs
SELECT 
    o.id,
    o.symbol,
    o.direction,
    o.setup_score,
    sl.score_total,
    sl.is_opportunity
FROM opportunities o
JOIN scan_logs sl ON o.scan_log_id = sl.id
ORDER BY o.timestamp DESC
LIMIT 10;
-- ✅ Attendu: Des résultats avec scan_log_id valide
```

---

### ✅ Étape 8 : Vérifier les Trades

**⚠️ Nécessite qu'une position soit ouverte puis fermée**

```sql
-- Vérifier les trades
SELECT 
    id,
    timestamp_entry,
    timestamp_exit,
    symbol,
    direction,
    entry_price,
    exit_price,
    net_pnl_usdt,
    win
FROM trades 
ORDER BY timestamp_entry DESC 
LIMIT 10;
-- ✅ Attendu: Des trades si des positions ont été fermées

-- Vérifier les indicateurs d'entrée
SELECT 
    symbol,
    direction,
    entry_rsi_1m,
    entry_rsi_5m,
    entry_macd_hist_1m,
    entry_adx_1m,
    entry_ema9_1m,
    entry_bb_upper_1m,
    entry_score,
    entry_condition_count
FROM trades 
WHERE entry_rsi_1m IS NOT NULL
ORDER BY timestamp_entry DESC
LIMIT 5;
-- ✅ Attendu: Des indicateurs d'entrée remplis

-- Vérifier config_snapshot
SELECT 
    symbol,
    config_snapshot->>'tp_sl_mode' as tp_sl_mode,
    config_snapshot->>'risk_per_trade' as risk_per_trade,
    config_snapshot->>'min_score_required' as min_score_required,
    config_snapshot->'RISK_CONFIG'->>'base_risk' as risk_config_base_risk,
    config_snapshot->'CONDITION_WEIGHTS'->>'EMAs' as condition_weights_emas
FROM trades 
WHERE config_snapshot IS NOT NULL
ORDER BY timestamp_entry DESC
LIMIT 5;
-- ✅ Attendu: config_snapshot contient toutes les variables

-- Vérifier early_invalidation
SELECT 
    symbol,
    exit_reason,
    early_invalidation_triggered,
    early_invalidation_threshold,
    early_invalidation_elapsed,
    early_invalidation_atr_pct,
    early_invalidation_pnl_pct
FROM trades 
WHERE early_invalidation_triggered = TRUE
ORDER BY timestamp_entry DESC
LIMIT 5;
-- ✅ Attendu: Des données si des invalidations précoces ont eu lieu
```

---

### ✅ Étape 9 : Vérifier l'Intégrité des Données

```sql
-- Vérifier qu'il n'y a pas de trades sans entry_price
SELECT COUNT(*) as trades_sans_entry_price
FROM trades 
WHERE entry_price IS NULL;
-- ✅ Attendu: 0

-- Vérifier que les timestamps sont cohérents
SELECT 
    id,
    symbol,
    timestamp_entry,
    timestamp_exit,
    duration_seconds,
    EXTRACT(EPOCH FROM (timestamp_exit - timestamp_entry)) as calculated_duration
FROM trades 
WHERE timestamp_exit IS NOT NULL
AND ABS(EXTRACT(EPOCH FROM (timestamp_exit - timestamp_entry)) - duration_seconds) > 1
LIMIT 10;
-- ✅ Attendu: 0 lignes (ou très peu avec tolérance de 1 seconde)

-- Vérifier que win est calculé correctement
SELECT 
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE win = TRUE) as wins,
    COUNT(*) FILTER (WHERE win = FALSE) as losses,
    COUNT(*) FILTER (WHERE win IS NULL) as win_null
FROM trades
WHERE timestamp_exit IS NOT NULL;
-- ✅ Attendu: win_null = 0 (tous les trades fermés ont win défini)
```

---

### ✅ Étape 10 : Vérifier les Performances

```sql
-- Vérifier que les index sont utilisés
EXPLAIN ANALYZE
SELECT * FROM trades 
WHERE timestamp_entry > NOW() - INTERVAL '1 day'
ORDER BY timestamp_entry DESC;
-- ✅ Vérifier "Index Scan" dans le plan d'exécution

-- Vérifier les requêtes sur scan_logs
EXPLAIN ANALYZE
SELECT * FROM scan_logs 
WHERE symbol = 'BTCUSDT'
AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
-- ✅ Vérifier "Index Scan" dans le plan d'exécution
```

---

## 🧪 Script de Vérification Automatique

Utilisez le script Python de vérification :

```bash
cd "C:\Users\sebta\Documents\clone github\test\test"
python database/verify_schema_complete.py
```

**✅ Résultat attendu :**
- Toutes les tables sont listées
- Toutes les colonnes de `trades` sont présentes
- Aucune colonne manquante

---

## 📊 Requêtes de Statistiques

```sql
-- Statistiques générales
SELECT 
    (SELECT COUNT(*) FROM scan_logs) as total_scans,
    (SELECT COUNT(*) FROM opportunities) as total_opportunities,
    (SELECT COUNT(*) FROM trades) as total_trades,
    (SELECT COUNT(*) FROM trades WHERE win = true) as winning_trades,
    (SELECT COUNT(*) FROM trades WHERE win = false) as losing_trades;

-- Taux de succès
SELECT 
    COUNT(*) as total_trades,
    SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN win THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate_pct,
    ROUND(AVG(net_pnl_usdt), 4) as avg_pnl_usdt
FROM trades
WHERE timestamp_exit IS NOT NULL;
```

---

## ✅ Checklist Finale

- [ ] Schéma SQL appliqué (migration exécutée)
- [ ] ~115 colonnes dans `trades`
- [ ] Colonnes `early_invalidation` présentes (6 colonnes)
- [ ] Colonne `config_snapshot` présente (JSONB)
- [ ] Colonnes `market_context` JSONB présentes
- [ ] Code Python à jour (derniers commits)
- [ ] Variables d'environnement configurées
- [ ] Connexion PostgreSQL fonctionne
- [ ] Datalogger initialisé au démarrage (logs OK)
- [ ] Scans sont loggés (après quelques minutes)
- [ ] Indicateurs sont remplis (non NULL)
- [ ] Opportunités sont loggées (si détectées)
- [ ] Trades sont loggés avec toutes les colonnes (si positions fermées)
- [ ] `config_snapshot` contient toutes les variables
- [ ] Aucune erreur dans les logs

---

## 🎯 Si Tout est OK

✅ **Le datalogger est fonctionnel et prêt pour l'optimisation ML !**

Vous pouvez maintenant :
1. Laisser l'application tourner pour collecter des données
2. Analyser les données avec des requêtes SQL
3. Préparer l'intégration ML (Phase suivante)

---

## 🐛 Si Problème

Consultez `database/GUIDE_TEST_DATALOGGER.md` pour le dépannage détaillé.


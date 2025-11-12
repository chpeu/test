# 🧪 Guide de Test - PostgreSQL Datalogger

**Date :** 2025-11-12

---

## 📋 Prérequis

1. ✅ PostgreSQL installé et démarré
2. ✅ Base de données `trade_cursor_ml` créée
3. ✅ Schéma SQL appliqué (`schema_postgresql_complete.sql`)
4. ✅ Migration appliquée (`migration_add_all_variables.sql`)
5. ✅ Variables d'environnement configurées (`.env`)

---

## 🔍 Étape 1 : Vérifier le Schéma

### 1.1 Vérification Automatique

```bash
# Depuis le répertoire du projet
python database/verify_schema_complete.py
```

**Résultat attendu :**
- ✅ Toutes les tables sont listées
- ✅ Toutes les colonnes de `trades` sont présentes
- ✅ Aucune colonne manquante

### 1.2 Vérification Manuelle avec psql

```bash
# Se connecter à PostgreSQL
psql -U postgres -d trade_cursor_ml

# Vérifier les tables
\dt

# Vérifier les colonnes de trades
\d trades

# Compter les colonnes
SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'trades';
-- Attendu: ~100+ colonnes

# Vérifier les colonnes spécifiques
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'trades' 
AND column_name LIKE 'entry_%' 
ORDER BY column_name;
```

---

## 🧪 Étape 2 : Tester le Datalogger

### 2.1 Vérifier la Connexion

```bash
# Démarrer l'application
python main.py
```

**Vérifier dans les logs :**
```
✅ PostgreSQL DataLogger initialisé: trade_cursor_ml@localhost:5432
✅ PostgreSQL DataLogger initialisé
```

**Si erreur :**
- Vérifier `POSTGRES_ENABLED=true` dans `.env`
- Vérifier `POSTGRES_PASSWORD` dans `.env`
- Vérifier que PostgreSQL est démarré

### 2.2 Vérifier les Scans

**Attendre quelques scans (45 secondes par scan)**

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

-- Compter les scans
SELECT COUNT(*) FROM scan_logs;

-- Vérifier les indicateurs sont loggés
SELECT 
    symbol,
    rsi_1m,
    macd_hist_1m,
    adx_1m,
    ema9_1m,
    bb_upper_1m
FROM scan_logs 
WHERE rsi_1m IS NOT NULL
LIMIT 5;
```

**Résultat attendu :**
- ✅ Des scans sont loggés toutes les 45 secondes
- ✅ Les indicateurs sont remplis (non NULL)
- ✅ `scan_duration_ms` est > 0

### 2.3 Vérifier les Opportunités

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

-- Compter les opportunités
SELECT COUNT(*) FROM opportunities;

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
```

**Résultat attendu :**
- ✅ Des opportunités sont loggées si des setups sont détectés
- ✅ Le lien avec `scan_logs` fonctionne

### 2.4 Vérifier les Trades

**Ouvrir une position manuellement ou attendre qu'une position s'ouvre automatiquement**

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

-- Vérifier les métriques temporelles
SELECT 
    symbol,
    entry_hour_of_day,
    entry_day_of_week,
    exit_hour_of_day,
    exit_day_of_week,
    duration_seconds
FROM trades 
WHERE timestamp_exit IS NOT NULL
ORDER BY timestamp_entry DESC
LIMIT 5;

-- Vérifier config_snapshot
SELECT 
    symbol,
    config_snapshot->>'tp_sl_mode' as tp_sl_mode,
    config_snapshot->>'risk_per_trade' as risk_per_trade,
    config_snapshot->>'min_score_required' as min_score_required
FROM trades 
WHERE config_snapshot IS NOT NULL
ORDER BY timestamp_entry DESC
LIMIT 5;
```

**Résultat attendu :**
- ✅ Les trades sont loggés avec toutes les colonnes
- ✅ Les indicateurs d'entrée sont remplis
- ✅ Les métriques temporelles sont calculées
- ✅ `config_snapshot` contient toutes les variables de configuration

### 2.5 Vérifier les Métriques de Performance

```sql
-- Vérifier max_favorable_excursion et max_adverse_excursion
SELECT 
    symbol,
    direction,
    net_pnl_usdt,
    max_favorable_excursion,
    max_adverse_excursion,
    max_favorable_excursion_usdt,
    max_adverse_excursion_usdt,
    max_drawdown_pct,
    max_drawdown_usdt,
    entry_to_max_profit_price_change_pct,
    entry_to_max_loss_price_change_pct
FROM trades 
WHERE timestamp_exit IS NOT NULL
AND max_favorable_excursion IS NOT NULL
ORDER BY timestamp_entry DESC
LIMIT 5;

-- Vérifier risk_reward_ratio
SELECT 
    symbol,
    direction,
    entry_price,
    tp_price,
    sl_price,
    risk_reward_ratio,
    net_pnl_usdt
FROM trades 
WHERE risk_reward_ratio IS NOT NULL
ORDER BY timestamp_entry DESC
LIMIT 5;
```

**Résultat attendu :**
- ✅ Les métriques de performance sont calculées
- ✅ `risk_reward_ratio` est calculé correctement

---

## 🔍 Étape 3 : Tests de Validation

### 3.1 Test d'Intégrité des Données

```sql
-- Vérifier qu'il n'y a pas de trades sans entry_price
SELECT COUNT(*) FROM trades WHERE entry_price IS NULL;
-- Attendu: 0

-- Vérifier qu'il n'y a pas de trades sans symbol
SELECT COUNT(*) FROM trades WHERE symbol IS NULL;
-- Attendu: 0

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
-- Attendu: 0 lignes (ou très peu avec tolérance de 1 seconde)
```

### 3.2 Test de Performance

```sql
-- Vérifier les index sont utilisés
EXPLAIN ANALYZE
SELECT * FROM trades 
WHERE timestamp_entry > NOW() - INTERVAL '1 day'
ORDER BY timestamp_entry DESC;

-- Vérifier les requêtes sur scan_logs
EXPLAIN ANALYZE
SELECT * FROM scan_logs 
WHERE symbol = 'BTCUSDT'
AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
```

**Résultat attendu :**
- ✅ Les index sont utilisés (Index Scan)
- ✅ Les requêtes sont rapides (< 100ms)

### 3.3 Test de Batch Inserts

```sql
-- Vérifier que les batch inserts fonctionnent
-- (Les scans devraient être insérés par batch de 50)

-- Compter les scans par minute
SELECT 
    DATE_TRUNC('minute', timestamp) as minute,
    COUNT(*) as scan_count
FROM scan_logs
WHERE timestamp > NOW() - INTERVAL '10 minutes'
GROUP BY minute
ORDER BY minute DESC;

-- Vérifier qu'il n'y a pas de doublons
SELECT 
    session_id,
    symbol,
    timestamp,
    COUNT(*) as count
FROM scan_logs
GROUP BY session_id, symbol, timestamp
HAVING COUNT(*) > 1;
-- Attendu: 0 lignes
```

---

## 🐛 Dépannage

### Problème : Aucun scan n'est loggé

**Vérifications :**
1. ✅ `POSTGRES_ENABLED=true` dans `.env`
2. ✅ PostgreSQL est démarré
3. ✅ Les logs montrent "✅ PostgreSQL DataLogger initialisé"
4. ✅ Le scanner loop est actif (logs toutes les 45 secondes)

**Solution :**
```bash
# Vérifier les logs de l'application
# Chercher les erreurs PostgreSQL dans les logs
```

### Problème : Colonnes manquantes

**Vérifications :**
1. ✅ Le schéma SQL est appliqué
2. ✅ La migration est appliquée

**Solution :**
```bash
# Appliquer la migration
psql -U postgres -d trade_cursor_ml -f database/migration_add_all_variables.sql

# Vérifier avec le script
python database/verify_schema_complete.py
```

### Problème : Indicateurs NULL

**Vérifications :**
1. ✅ Les scans sont loggés
2. ✅ Les indicateurs sont calculés dans le code

**Solution :**
- Vérifier que `indicators_1m` et `indicators_5m` sont bien passés au datalogger
- Vérifier les logs pour les erreurs de logging

### Problème : Erreur de connexion

**Vérifications :**
1. ✅ PostgreSQL est démarré
2. ✅ `POSTGRES_PASSWORD` est correct dans `.env`
3. ✅ `POSTGRES_HOST` et `POSTGRES_PORT` sont corrects

**Solution :**
```bash
# Tester la connexion manuellement
psql -U postgres -d trade_cursor_ml -h localhost -p 5432

# Vérifier les variables d'environnement
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('POSTGRES_PASSWORD'))"
```

---

## ✅ Checklist de Validation

- [ ] Schéma SQL appliqué
- [ ] Migration appliquée
- [ ] Script de vérification passe sans erreur
- [ ] Connexion PostgreSQL fonctionne
- [ ] Scans sont loggés toutes les 45 secondes
- [ ] Opportunités sont loggées si détectées
- [ ] Trades sont loggés avec toutes les colonnes
- [ ] Indicateurs d'entrée sont remplis
- [ ] Métriques temporelles sont calculées
- [ ] Config snapshot est rempli
- [ ] Métriques de performance sont calculées
- [ ] Aucune erreur dans les logs

---

## 📊 Requêtes Utiles pour Monitoring

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

-- Performance par symbole
SELECT 
    symbol,
    COUNT(*) as trades,
    SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN win THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate_pct,
    ROUND(SUM(net_pnl_usdt), 4) as total_pnl_usdt,
    ROUND(AVG(net_pnl_usdt), 4) as avg_pnl_usdt
FROM trades
WHERE timestamp_exit IS NOT NULL
GROUP BY symbol
ORDER BY total_pnl_usdt DESC;
```

---

## 🎯 Conclusion

Si tous les tests passent, le datalogger est fonctionnel et prêt pour l'optimisation ML ! 🚀


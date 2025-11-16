# 🔧 CHECKLIST OPTIMISATION - Base/DataLogger/SQL

**Date**: 2025-11-16  
**Objectif**: Liste d'actions pour optimiser avant/après ML

---

## ✅ DÉJÀ OPTIMISÉ

### Pool de connexions ✅
```python
ThreadedConnectionPool(min_conn=1, max_conn=5)
```
- ✅ Réutilisation connexions (pas de reconnexion à chaque query)
- ✅ Taille adaptée pour scalping (5 connexions max suffisant)
- ✅ Gestion thread-safe

### Batch inserts ✅
```python
batch_size = 10  # Réduit de 50 pour flush plus fréquent
batch_flush_interval = 2.0  # Réduit de 5.0 pour flush plus fréquent
```
- ✅ Buffers pour scans/opportunities
- ✅ execute_values() pour insertions groupées
- ✅ Flush automatique + manuel

### Index database ✅
```sql
-- Scan logs (partitionné)
CREATE INDEX scan_logs_*_timestamp_symbol_idx  -- Composite optimal
CREATE INDEX scan_logs_*_is_opportunity_idx    -- Pour filtres
CREATE INDEX scan_logs_*_session_id_idx        -- Pour JOIN

-- Trades
CREATE INDEX idx_trade_timestamp_entry         -- Pour requêtes temporelles
CREATE INDEX idx_trade_symbol                  -- Pour filtres symbol
CREATE INDEX idx_trade_win                     -- Pour ML (label)
CREATE INDEX idx_trade_direction               -- Pour stratégies L/S
CREATE INDEX idx_trade_session                 -- Pour analytics session
```
- ✅ Index bien placés sur colonnes de filtrage ML
- ✅ Pas d'index sur colonnes calculées (évite overhead)

### Cache PostgreSQL ✅
```
Index cache hit rate: 99.8%
Table cache hit rate: 100.0%
```
- ✅ Performance optimale
- ✅ shared_buffers probablement bien configuré

---

## 🟡 OPTIMISATIONS RECOMMANDÉES

### 1. Supprimer index dupliqués (priorité: BASSE)

**Problème**: Index timestamp seul couvert par timestamp+symbol composite

```sql
-- À exécuter
DROP INDEX IF EXISTS scan_logs_2025_11_timestamp_idx;
DROP INDEX IF EXISTS scan_logs_2025_12_timestamp_idx;
DROP INDEX IF EXISTS scan_logs_2026_01_timestamp_idx;
```

**Gain**: ~0.6MB + légère réduction overhead INSERT

**Risque**: Aucun (index composite couvre timestamp seul)

---

### 2. Installer pg_stat_statements (priorité: MOYENNE)

**Objectif**: Monitoring queries lentes

```sql
-- Dans PostgreSQL
CREATE EXTENSION pg_stat_statements;

-- Dans postgresql.conf
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
pg_stat_statements.max = 10000
```

**Gain**: 
- Identification queries lentes
- Optimisation index futures basée sur usage réel
- Dashboard performance

**Risque**: Overhead très faible (<1%)

---

### 3. Créer vues ML pré-calculées (priorité: MOYENNE)

#### Vue features complètes
```sql
CREATE OR REPLACE VIEW ml_trades_complete AS
SELECT 
    -- Identifiants
    id, symbol, direction, timestamp_entry, timestamp_exit,
    
    -- Features entry (indicateurs techniques)
    entry_rsi_1m, entry_rsi_5m, entry_rsi_prev_1m, entry_rsi_prev_5m,
    entry_macd_hist_1m, entry_macd_hist_5m,
    entry_adx_1m, entry_adx_5m,
    entry_di_gap_1m, entry_di_gap_5m,
    entry_ema_diff_pct_1m, entry_ema_diff_pct_5m,
    entry_atr_pct_1m, entry_atr_pct_5m,
    entry_bb_width_1m, entry_bb_width_5m,
    entry_volume_ratio_1m, entry_volume_ratio_5m,
    
    -- Features entry (contexte)
    entry_score, entry_spread_pct, entry_balance_score,
    entry_condition_count,
    entry_hour_of_day, entry_day_of_week,
    
    -- Features setup
    tp_sl_mode, risk_reward_ratio,
    size_usdt,
    
    -- Résultats
    duration_seconds, net_pnl_usdt, net_pnl_pct,
    exit_reason,
    
    -- Label ML
    win as label
    
FROM trades
WHERE timestamp_exit IS NOT NULL  -- Trades fermés seulement
  AND net_pnl_usdt IS NOT NULL;   -- Résultat calculé
```

#### Vue analyse temporelle
```sql
CREATE OR REPLACE VIEW ml_trades_temporal AS
SELECT 
    entry_hour_of_day,
    entry_day_of_week,
    direction,
    COUNT(*) as trade_count,
    AVG(net_pnl_usdt) as avg_pnl,
    SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN NOT win THEN 1 ELSE 0 END) as losses,
    ROUND(100.0 * SUM(CASE WHEN win THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate
FROM trades
WHERE timestamp_exit IS NOT NULL
GROUP BY entry_hour_of_day, entry_day_of_week, direction
ORDER BY entry_day_of_week, entry_hour_of_day;
```

#### Vue feature importance (post-ML)
```sql
CREATE TABLE IF NOT EXISTS ml_feature_importance (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(20),
    feature_name VARCHAR(100) NOT NULL,
    importance_score FLOAT NOT NULL,
    importance_rank INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(model_name, model_version, feature_name)
);

CREATE INDEX idx_fi_model ON ml_feature_importance(model_name, model_version);
CREATE INDEX idx_fi_score ON ml_feature_importance(importance_score DESC);
```

**Gain**: 
- Requêtes ML simplifiées
- Performance SELECT (vue pré-optimisée)
- Analyse temporelle rapide

---

### 4. Fonction PostgreSQL pour feature engineering (priorité: BASSE)

```sql
-- Exemple: Calculer features dérivées
CREATE OR REPLACE FUNCTION calculate_derived_features(trade_id UUID)
RETURNS TABLE (
    rsi_divergence_1m FLOAT,
    macd_momentum_1m FLOAT,
    bb_squeeze_1m FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        -- RSI divergence (diff entre 1m et 5m)
        ABS(t.entry_rsi_1m - t.entry_rsi_5m) as rsi_divergence_1m,
        
        -- MACD momentum (variation histogramme)
        t.entry_macd_hist_1m - t.entry_macd_hist_prev_1m as macd_momentum_1m,
        
        -- BB squeeze (largeur relative)
        t.entry_bb_width_1m / NULLIF(t.entry_atr_pct_1m, 0) as bb_squeeze_1m
        
    FROM trades t
    WHERE t.id = trade_id;
END;
$$ LANGUAGE plpgsql;
```

**Gain**: 
- Features calculées côté DB (plus rapide que Python)
- Cohérence calculs

**Risque**: Complexité maintenance

---

### 5. Partitionnement table `trades` (priorité: BASSE - FUTUR)

**Quand**: Après 10 000+ trades

```sql
-- Partitionner par trimestre
CREATE TABLE trades_2025_q1 PARTITION OF trades
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE trades_2025_q2 PARTITION OF trades
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

-- etc.
```

**Gain**: 
- Performance queries temporelles
- Maintenance facilitée (VACUUM par partition)
- Archivage ancien data

**Risque**: Complexité gestion

---

### 6. Monitoring & alerting (priorité: MOYENNE)

#### Créer vue monitoring
```sql
CREATE OR REPLACE VIEW datalogger_health AS
SELECT 
    'scans' as table_name,
    COUNT(*) as total_rows,
    COUNT(*) FILTER (WHERE timestamp > NOW() - INTERVAL '1 hour') as last_hour,
    COUNT(*) FILTER (WHERE timestamp > NOW() - INTERVAL '24 hours') as last_24h,
    MAX(timestamp) as last_insert
FROM scan_logs
UNION ALL
SELECT 
    'opportunities',
    COUNT(*),
    COUNT(*) FILTER (WHERE timestamp > NOW() - INTERVAL '1 hour'),
    COUNT(*) FILTER (WHERE timestamp > NOW() - INTERVAL '24 hours'),
    MAX(timestamp)
FROM opportunities
UNION ALL
SELECT 
    'trades',
    COUNT(*),
    COUNT(*) FILTER (WHERE timestamp_entry > NOW() - INTERVAL '1 hour'),
    COUNT(*) FILTER (WHERE timestamp_entry > NOW() - INTERVAL '24 hours'),
    MAX(timestamp_entry)
FROM trades;
```

#### Script monitoring Python
```python
# database/monitor_health.py
import psycopg2
from datetime import datetime, timedelta

def check_datalogger_health():
    """Vérifier santé datalogger"""
    conn = psycopg2.connect(...)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM datalogger_health")
    results = cursor.fetchall()
    
    for table, total, last_hour, last_24h, last_insert in results:
        # Alerte si pas d'insert depuis 2h
        if last_insert < datetime.now() - timedelta(hours=2):
            print(f"⚠️ ALERTE: {table} - Pas d'insert depuis {last_insert}")
        
        # Alerte si très peu d'inserts (scanner arrêté?)
        if table == 'scans' and last_hour < 10:
            print(f"⚠️ ALERTE: Seulement {last_hour} scans dernière heure")
    
    cursor.close()
    conn.close()

# Cron: toutes les 30 minutes
```

---

## 🔴 OPTIMISATIONS CRITIQUES (si problèmes futurs)

### Si INSERT lent (>100ms) après 100K+ rows

#### 1. Augmenter batch_size
```python
# core/postgresql_datalogger.py
batch_size = 50  # Au lieu de 10
batch_flush_interval = 5.0  # Au lieu de 2.0
```

#### 2. Désactiver index temporairement
```sql
-- Avant bulk insert
DROP INDEX idx_scan_timestamp;
-- ... INSERT ...
-- Après bulk insert
CREATE INDEX idx_scan_timestamp ON scan_logs(timestamp);
```

#### 3. COPY au lieu d'INSERT
```python
# Pour très gros volumes
from io import StringIO

def bulk_insert_csv(data):
    conn = pool.getconn()
    cursor = conn.cursor()
    
    csv_buffer = StringIO()
    for row in data:
        csv_buffer.write(','.join(str(x) for x in row) + '\n')
    
    csv_buffer.seek(0)
    cursor.copy_from(csv_buffer, 'scan_logs', sep=',', columns=('timestamp', 'symbol', ...))
    
    conn.commit()
    pool.putconn(conn)
```

---

### Si SELECT lent (>1s) pour ML queries

#### 1. Créer index spécifiques ML
```sql
-- Index pour filtres ML communs
CREATE INDEX idx_trades_ml_training ON trades(timestamp_entry)
    WHERE timestamp_exit IS NOT NULL AND net_pnl_usdt IS NOT NULL;

-- Index covering pour queries fréquentes
CREATE INDEX idx_trades_features ON trades(
    symbol, direction, entry_rsi_1m, entry_adx_1m, win
) WHERE timestamp_exit IS NOT NULL;
```

#### 2. Table matérialisée pour features
```sql
CREATE MATERIALIZED VIEW ml_trades_features_mat AS
SELECT * FROM ml_trades_complete;

CREATE UNIQUE INDEX ON ml_trades_features_mat(id);

-- Refresh périodique (cron)
REFRESH MATERIALIZED VIEW CONCURRENTLY ml_trades_features_mat;
```

---

### Si storage DB trop grand (>10GB)

#### 1. Archivage ancien data
```python
# database/archive_old_data.py
def archive_scans_older_than(days=90):
    """Archiver scans > 90 jours"""
    conn = psycopg2.connect(...)
    cursor = conn.cursor()
    
    # Export vers CSV
    cursor.execute(f"""
        COPY (
            SELECT * FROM scan_logs 
            WHERE timestamp < NOW() - INTERVAL '{days} days'
        ) TO '/backup/scan_logs_archive_{datetime.now().date()}.csv' 
        WITH CSV HEADER
    """)
    
    # Supprimer de la base
    cursor.execute(f"""
        DELETE FROM scan_logs 
        WHERE timestamp < NOW() - INTERVAL '{days} days'
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
```

#### 2. Compression colonnes JSONB
```sql
-- Activer compression TOAST
ALTER TABLE trades ALTER COLUMN config_snapshot SET STORAGE EXTENDED;
```

---

## 📊 MÉTRIQUES À SURVEILLER

### Performance queries
```sql
-- Top 10 queries lentes (requiert pg_stat_statements)
SELECT 
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### Taille tables
```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Index usage
```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan ASC;  -- Index jamais utilisés en premier
```

---

## ✅ CONCLUSION

### Actions immédiates (avant ML)
1. ⚠️ **Optionnel**: Supprimer index dupliqués
2. ✅ **Recommandé**: Installer pg_stat_statements
3. ✅ **Recommandé**: Créer vues ML

### Actions futures (après 100+ trades)
1. Analyser requêtes lentes avec pg_stat_statements
2. Optimiser index selon usage réel
3. Considérer table matérialisée si queries ML lentes

### Actions long terme (après 10K+ trades)
1. Partitionnement table trades
2. Archivage ancien data
3. Monitoring automatisé + alerting

---

**Statut actuel**: ✅ **OPTIMAL POUR DÉMARRAGE ML**

Aucune action bloquante. Base prête pour accumulation données + implémentation ML.

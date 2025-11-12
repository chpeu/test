# 📊 Guide : Comment Voir les Logs PostgreSQL

## 🔧 Prérequis

### 1. Vérifier que PostgreSQL est activé

Dans votre fichier `.env`, assurez-vous que :
```env
POSTGRES_ENABLED=true
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trade_cursor_ml
POSTGRES_USER=postgres
POSTGRES_PASSWORD=votre_mot_de_passe
```

### 2. Vérifier que le schéma est créé

Exécutez le script SQL pour créer les tables :
```bash
psql -U postgres -d trade_cursor_ml -f database/schema_postgresql_complete.sql
```

---

## 🔍 Méthodes pour Voir les Logs

### Méthode 1 : psql (Ligne de commande)

#### Se connecter à PostgreSQL
```bash
psql -U postgres -d trade_cursor_ml
```

#### Requêtes utiles

**1. Voir les dernières sessions de trading :**
```sql
SELECT 
    id,
    start_time,
    end_time,
    config_snapshot
FROM trading_sessions
ORDER BY start_time DESC
LIMIT 10;
```

**2. Voir les derniers scans :**
```sql
SELECT 
    id,
    timestamp,
    symbol,
    scan_duration_ms,
    price,
    score_total,
    is_opportunity,
    opportunity_direction,
    reject_reason
FROM scan_logs
ORDER BY timestamp DESC
LIMIT 50;
```

**3. Voir les opportunités détectées :**
```sql
SELECT 
    o.id,
    o.timestamp,
    o.symbol,
    o.direction,
    o.setup_score,
    o.entry_price,
    o.tp_price,
    o.sl_price,
    o.status,
    s.score_total as scan_score
FROM opportunities o
LEFT JOIN scan_logs s ON o.scan_log_id = s.id
ORDER BY o.timestamp DESC
LIMIT 20;
```

**4. Voir les trades exécutés :**
```sql
SELECT 
    id,
    timestamp,
    symbol,
    direction,
    entry_price,
    exit_price,
    size_usdt,
    gross_pnl_usdt,
    gross_pnl_pct,
    net_pnl_usdt,
    net_pnl_pct,
    reason,
    duration_seconds
FROM trades
ORDER BY timestamp DESC
LIMIT 20;
```

**5. Voir les erreurs de scan :**
```sql
SELECT 
    id,
    timestamp,
    symbol,
    error_type,
    error_message,
    resolved
FROM scan_errors
ORDER BY timestamp DESC
LIMIT 20;
```

**6. Statistiques par session :**
```sql
SELECT 
    ts.id as session_id,
    ts.start_time,
    COUNT(DISTINCT sl.id) as total_scans,
    COUNT(DISTINCT o.id) as total_opportunities,
    COUNT(DISTINCT t.id) as total_trades,
    SUM(t.net_pnl_usdt) as total_pnl,
    AVG(t.net_pnl_pct) as avg_pnl_pct
FROM trading_sessions ts
LEFT JOIN scan_logs sl ON sl.session_id = ts.id
LEFT JOIN opportunities o ON o.session_id = ts.id
LEFT JOIN trades t ON t.session_id = ts.id
GROUP BY ts.id, ts.start_time
ORDER BY ts.start_time DESC;
```

**7. Performance des scans :**
```sql
SELECT 
    symbol,
    COUNT(*) as scan_count,
    AVG(scan_duration_ms) as avg_duration_ms,
    MIN(scan_duration_ms) as min_duration_ms,
    MAX(scan_duration_ms) as max_duration_ms,
    COUNT(CASE WHEN is_opportunity THEN 1 END) as opportunities_count
FROM scan_logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY scan_count DESC;
```

**8. Taux de conversion (scans → opportunités → trades) :**
```sql
WITH stats AS (
    SELECT 
        COUNT(DISTINCT sl.id) as total_scans,
        COUNT(DISTINCT o.id) as total_opportunities,
        COUNT(DISTINCT t.id) as total_trades
    FROM scan_logs sl
    LEFT JOIN opportunities o ON o.scan_log_id = sl.id
    LEFT JOIN trades t ON t.opportunity_id = o.id
    WHERE sl.timestamp > NOW() - INTERVAL '24 hours'
)
SELECT 
    total_scans,
    total_opportunities,
    total_trades,
    ROUND(100.0 * total_opportunities / NULLIF(total_scans, 0), 2) as scan_to_opp_rate,
    ROUND(100.0 * total_trades / NULLIF(total_opportunities, 0), 2) as opp_to_trade_rate
FROM stats;
```

**9. Raisons de rejet les plus fréquentes :**
```sql
SELECT 
    reject_reason,
    reject_reason_category,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
FROM scan_logs
WHERE reject_reason IS NOT NULL
    AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY reject_reason, reject_reason_category
ORDER BY count DESC
LIMIT 10;
```

**10. Contexte marché récent :**
```sql
SELECT 
    timestamp,
    hour_of_day,
    day_of_week,
    btc_price,
    eth_price,
    market_trend,
    market_volatility,
    session_stats
FROM market_context
ORDER BY timestamp DESC
LIMIT 20;
```

---

### Méthode 2 : pgAdmin (Interface Graphique)

1. **Installer pgAdmin** : https://www.pgadmin.org/download/
2. **Se connecter** :
   - Host: `localhost`
   - Port: `5432`
   - Database: `trade_cursor_ml`
   - Username: `postgres`
   - Password: (votre mot de passe)

3. **Naviguer** :
   - Databases → `trade_cursor_ml` → Schemas → `public` → Tables
   - Clic droit sur une table → "View/Edit Data" → "All Rows"

---

### Méthode 3 : Python Script

Créez un script Python pour interroger les logs :

```python
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

# Connexion
conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='trade_cursor_ml',
    user='postgres',
    password='votre_mot_de_passe'
)

cursor = conn.cursor(cursor_factory=RealDictCursor)

# Derniers scans
cursor.execute("""
    SELECT * FROM scan_logs
    ORDER BY timestamp DESC
    LIMIT 10
""")
scans = cursor.fetchall()

for scan in scans:
    print(f"{scan['timestamp']} | {scan['symbol']} | Score: {scan['score_total']} | Opportunity: {scan['is_opportunity']}")

# Derniers trades
cursor.execute("""
    SELECT * FROM trades
    ORDER BY timestamp DESC
    LIMIT 10
""")
trades = cursor.fetchall()

for trade in trades:
    print(f"{trade['timestamp']} | {trade['symbol']} | PnL: {trade['net_pnl_usdt']:.2f} USDT ({trade['net_pnl_pct']:.2f}%)")

cursor.close()
conn.close()
```

---

### Méthode 4 : API Endpoint (à créer)

Vous pouvez créer un endpoint FastAPI pour exposer les logs :

```python
@app.get("/api/logs/scans")
async def get_scan_logs(limit: int = 50):
    """Récupérer les derniers scans"""
    # Implémenter avec psycopg2
    pass

@app.get("/api/logs/trades")
async def get_trade_logs(limit: int = 50):
    """Récupérer les derniers trades"""
    pass
```

---

## 📈 Requêtes Avancées

### Analyse des performances ML

**Scores moyens par pattern :**
```sql
SELECT 
    pattern_1m,
    pattern_5m,
    AVG(score_total) as avg_score,
    COUNT(*) as count,
    COUNT(CASE WHEN is_opportunity THEN 1 END) as opportunities
FROM scan_logs
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY pattern_1m, pattern_5m
ORDER BY avg_score DESC;
```

**Corrélation indicateurs → opportunités :**
```sql
SELECT 
    CASE 
        WHEN rsi_1m < 30 THEN 'Oversold'
        WHEN rsi_1m > 70 THEN 'Overbought'
        ELSE 'Neutral'
    END as rsi_zone,
    COUNT(*) as total_scans,
    COUNT(CASE WHEN is_opportunity THEN 1 END) as opportunities,
    ROUND(100.0 * COUNT(CASE WHEN is_opportunity THEN 1 END) / COUNT(*), 2) as opp_rate
FROM scan_logs
WHERE rsi_1m IS NOT NULL
    AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY rsi_zone
ORDER BY opp_rate DESC;
```

**Performance par direction :**
```sql
SELECT 
    direction,
    COUNT(*) as trade_count,
    SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN net_pnl_usdt <= 0 THEN 1 ELSE 0 END) as losses,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
    AVG(net_pnl_usdt) as avg_pnl,
    SUM(net_pnl_usdt) as total_pnl
FROM trades
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY direction;
```

---

## 🔔 Vérification que les logs sont actifs

**Vérifier que le datalogger est actif :**
```sql
-- Dernière insertion
SELECT 
    'scan_logs' as table_name,
    MAX(timestamp) as last_insert
FROM scan_logs
UNION ALL
SELECT 
    'trades',
    MAX(timestamp)
FROM trades
UNION ALL
SELECT 
    'opportunities',
    MAX(timestamp)
FROM opportunities;
```

Si les timestamps sont récents (< 5 minutes), le datalogger fonctionne correctement.

---

## 📝 Notes

- Les logs sont partitionnés par mois pour `scan_logs` (voir schéma)
- Utilisez des index sur `timestamp` pour de meilleures performances
- Les données JSONB peuvent être interrogées avec `->` et `->>`
- Pour de gros volumes, utilisez `EXPLAIN ANALYZE` pour optimiser les requêtes


# 📊 PostgreSQL Schema - Trade Cursor ML Database

## Vue d'ensemble

Ce schéma PostgreSQL est conçu pour logger tous les scans, opportunités et trades du bot Trade Cursor, avec un focus sur le Machine Learning et l'optimisation des paramètres.

## 🎯 Objectifs

1. **ML & Feature Engineering** : Capturer toutes les features nécessaires pour entraîner des modèles prédictifs
2. **Optimisation de Paramètres** : Tracker l'impact des changements de configuration
3. **Analyse de Performance** : Analyser les patterns gagnants/perdants
4. **Scalabilité** : Partitionnement pour gérer de gros volumes de données

## 📋 Tables Principales

### 1. `trading_sessions`
**Objectif** : Grouper les scans/trades par session de trading

**Colonnes clés** :
- `start_time` / `end_time` : Durée de la session
- `config_snapshot` : Configuration au démarrage (JSONB)
- Stats agrégées : scans, opportunités, trades, PnL

**Utilisation** : Analyser la performance par session, corréler avec changements de config

### 2. `config_snapshots`
**Objectif** : Historique complet des changements de configuration

**Colonnes clés** :
- `config_data` : Config complète (JSONB)
- `changed_keys` : Clés modifiées (array)
- `changed_by` : 'system', 'user', 'auto'

**Utilisation** : Analyser l'impact des changements de paramètres sur les performances

### 3. `scan_logs` (PARTITIONNÉE)
**Objectif** : Log de CHAQUE scan avec tous les indicateurs

**Partitionnement** : Par mois pour performance (ex: `scan_logs_2025_01`)

**Colonnes principales** :
- **Indicateurs 1m/5m** : EMA, RSI, MACD, ADX, ATR, Bollinger, Volume
- **Filtres de qualité** : SNR, Breakout, Wick Ratio, ATR Optimal
- **Patterns** : Patterns de bougies détectés
- **Scores** : Scores pondérés 1m, 5m, total
- **Décision ML** : `is_opportunity`, `opportunity_direction`, `reject_reason`

**Volume estimé** : ~38,400 scans/jour (20 paires × 45s intervalle)

### 4. `opportunities`
**Objectif** : Opportunités détectées (subset de scan_logs)

**Colonnes clés** :
- `scan_log_id` : Lien vers scan_logs
- `status` : PENDING, EXECUTED, IGNORED, EXPIRED, REJECTED
- `setup_score` : Score du setup
- `conditions_matched` : Array des conditions validées

**Utilisation** : Analyser pourquoi certaines opportunités ne sont pas exécutées

### 5. `trades`
**Objectif** : Trades exécutés avec résultats complets

**Colonnes principales** :
- **Entry** : Prix, taille, TP/SL, snapshot indicateurs
- **Exit** : Prix, raison, durée
- **Résultats** : PnL brut/net, slippage, fees
- **Events** : Break-even, TP partiel, TP escalier, trailing stop
- **Métriques** : MFE/MAE (Max Favorable/Adverse Excursion)

**Utilisation** : Base principale pour ML prédictif (labels : `win`, `net_pnl_pct`)

### 6. `market_context`
**Objectif** : Contexte marché général (snapshot périodique)

**Colonnes** : Heure, jour, prix BTC/ETH, métriques globales, stats session

**Utilisation** : Analyser l'impact du contexte marché sur les performances

### 7. `scan_errors`
**Objectif** : Logs d'erreurs pour détecter patterns de problèmes

**Utilisation** : Monitoring et debugging

### 8. `model_predictions` (Futur)
**Objectif** : Prédictions ML avec résultats réels

**Utilisation** : Améliorer les modèles en comparant prédictions vs réalité

### 9. `features_engineered` (Optionnel)
**Objectif** : Features pré-calculées pour ML avancé

**Features** : Divergences, cross signals, ratios composites, scores composites

## 🔍 Vues Utiles

### `scans_with_opportunities`
Scans qui ont généré des opportunités avec détails

### `opportunities_executed`
Opportunités exécutées avec résultats des trades

### `daily_stats`
Stats quotidiennes agrégées (trades, winrate, PnL, etc.)

### `session_stats`
Stats par session avec comparaison prévu vs réel

### `ml_features`
Vue optimisée pour ML avec toutes les features + labels

## 🛠️ Fonctions Utiles

### `cleanup_old_data()`
Nettoie automatiquement les données > 6 mois (garde les opportunités)

### `get_global_stats()`
Retourne stats globales : total scans, opportunités, trades, winrate, PnL

### `create_monthly_partition()`
Crée automatiquement une partition mensuelle pour `scan_logs`

### `update_updated_at_column()`
Trigger pour mettre à jour automatiquement `updated_at` sur `trades`

## 📊 Index de Performance

### Index Principaux
- **Timestamp** : Pour requêtes temporelles
- **Symbol** : Pour requêtes par paire
- **Opportunity/Direction** : Pour filtrage ML
- **Win** : Pour analyse de performance
- **Session** : Pour analyse par session

### Index Composés
- `(timestamp DESC, symbol)` : Requêtes fréquentes
- `(is_opportunity, opportunity_direction, score_total)` : ML queries

## 🚀 Installation

### 1. Installer PostgreSQL
```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# Windows
# Télécharger depuis https://www.postgresql.org/download/windows/
```

### 2. Créer la base de données
```sql
CREATE DATABASE trade_cursor_ml;
\c trade_cursor_ml
```

### 3. Exécuter le schéma
```bash
psql -U postgres -d trade_cursor_ml -f database/schema_postgresql_complete.sql
```

### 4. Créer un utilisateur (optionnel)
```sql
CREATE USER trade_cursor_app WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trade_cursor_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trade_cursor_app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO trade_cursor_app;
```

## 📈 Maintenance

### Créer une partition mensuelle
```sql
SELECT create_monthly_partition('scan_logs', '2025-02-01');
```

### Nettoyer les vieilles données
```sql
SELECT cleanup_old_data();
```

### Vérifier les stats
```sql
SELECT * FROM get_global_stats();
```

## 🔄 Migration depuis SQLite

Un script de migration sera nécessaire pour transférer les données existantes depuis `analytics.db` (SQLite) vers PostgreSQL.

**Tables à migrer** :
- `trades` → `trades`
- `setups_validated` → `opportunities` (avec mapping)
- Stats → `trading_sessions`

## 📝 Notes Importantes

### Performance
- **Partitionnement** : Créer les partitions mensuelles à l'avance
- **Index** : Les index sont créés automatiquement sur chaque partition
- **Compression** : Activer la compression pour partitions > 1 mois

### Volume de Données
- **Scans/jour** : ~38,400 (20 paires × 45s)
- **Opportunités/jour** : ~100-500 (estimé)
- **Trades/jour** : ~10-50 (estimé)
- **Stockage estimé** : ~500MB/mois pour scans, ~50MB/mois pour trades

### ML Features
Toutes les features nécessaires sont capturées dans `scan_logs` :
- Indicateurs techniques (1m et 5m)
- Filtres de qualité (SNR, Breakout, Wicks, ATR)
- Patterns de bougies
- Scores pondérés
- Contexte marché

### Requêtes ML Exemple
```sql
-- Features + Labels pour entraînement
SELECT * FROM ml_features 
WHERE timestamp > NOW() - INTERVAL '30 days'
ORDER BY timestamp DESC;

-- Analyse des patterns gagnants
SELECT 
    conditions_matched,
    COUNT(*) as count,
    AVG(net_pnl_pct) as avg_pnl,
    COUNT(*) FILTER (WHERE win = TRUE)::FLOAT / COUNT(*) as win_rate
FROM trades t
JOIN opportunities o ON t.opportunity_id = o.id
WHERE t.timestamp_exit IS NOT NULL
GROUP BY conditions_matched
ORDER BY win_rate DESC, avg_pnl DESC;
```

## 🔐 Sécurité

- Utiliser un utilisateur dédié avec permissions limitées
- Activer SSL pour connexions distantes
- Sauvegarder régulièrement (pg_dump)
- Chiffrer les données sensibles si nécessaire

## 📚 Ressources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Partitioning Guide](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [JSONB Performance](https://www.postgresql.org/docs/current/datatype-json.html)

---

**Version** : 1.0  
**Date** : 2025-01-11  
**Compatible avec** : Trade Cursor v7.0+



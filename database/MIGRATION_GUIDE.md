# 🔄 Guide de Migration - PostgreSQL Schema

## Vue d'ensemble

Ce guide vous aide à supprimer l'ancien schéma PostgreSQL et à appliquer le nouveau schéma complet.

## ⚠️ Précautions

1. **Sauvegarde** : Si vous avez des données importantes, faites une sauvegarde avant :
   ```bash
   pg_dump -U postgres -d trade_cursor_ml > backup_old_schema.sql
   ```

2. **Vérification** : Le script de nettoyage vérifie qu'il n'y a pas de données avant de supprimer (mais supprime quand même les structures)

## 📋 Procédure

### Option 1 : Nettoyage Complet (Recommandé)

```bash
# 1. Se connecter à PostgreSQL
psql -U postgres -d trade_cursor_ml

# 2. Exécuter le script de nettoyage
\i database/drop_old_schema.sql

# 3. Vérifier que tout est supprimé
\dt  # Devrait être vide

# 4. Quitter
\q

# 5. Appliquer le nouveau schéma
psql -U postgres -d trade_cursor_ml -f database/schema_postgresql_complete.sql
```

### Option 2 : Nettoyage Manuel (Si vous préférez)

```sql
-- Se connecter à PostgreSQL
psql -U postgres -d trade_cursor_ml

-- Supprimer dans l'ordre
DROP VIEW IF EXISTS daily_stats CASCADE;
DROP VIEW IF EXISTS opportunities_executed CASCADE;
DROP VIEW IF EXISTS scans_with_opportunities CASCADE;
DROP VIEW IF EXISTS session_stats CASCADE;
DROP VIEW IF EXISTS ml_features CASCADE;

DROP TRIGGER IF EXISTS update_trades_updated_at ON trades CASCADE;

DROP FUNCTION IF EXISTS cleanup_old_data() CASCADE;
DROP FUNCTION IF EXISTS get_global_stats() CASCADE;
DROP FUNCTION IF EXISTS create_monthly_partition(TEXT, DATE) CASCADE;
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

DROP TABLE IF EXISTS model_predictions CASCADE;
DROP TABLE IF EXISTS features_engineered CASCADE;
DROP TABLE IF EXISTS scan_errors CASCADE;
DROP TABLE IF EXISTS trades CASCADE;
DROP TABLE IF EXISTS opportunities CASCADE;
DROP TABLE IF EXISTS market_context CASCADE;
DROP TABLE IF EXISTS config_snapshots CASCADE;
DROP TABLE IF EXISTS scan_logs CASCADE;  -- Supprime aussi les partitions
DROP TABLE IF EXISTS trading_sessions CASCADE;

-- Vérifier
\dt
```

### Option 3 : Script PowerShell (Windows)

```powershell
# Sauvegarde (optionnel)
pg_dump -U postgres -d trade_cursor_ml > backup_old_schema.sql

# Nettoyage
psql -U postgres -d trade_cursor_ml -f database\drop_old_schema.sql

# Nouveau schéma
psql -U postgres -d trade_cursor_ml -f database\schema_postgresql_complete.sql
```

## 🔍 Vérification

Après le nettoyage, vérifiez que tout est supprimé :

```sql
-- Lister les tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE';

-- Lister les vues
SELECT viewname 
FROM pg_views 
WHERE schemaname = 'public';

-- Lister les fonctions
SELECT proname 
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public';
```

Tout devrait être vide (sauf peut-être des tables système).

## ✅ Application du Nouveau Schéma

Une fois le nettoyage terminé :

```bash
psql -U postgres -d trade_cursor_ml -f database/schema_postgresql_complete.sql
```

Vérifiez que les nouvelles tables sont créées :

```sql
\dt
```

Vous devriez voir :
- `trading_sessions`
- `config_snapshots`
- `scan_logs` (table partitionnée)
- `opportunities`
- `trades`
- `market_context`
- `scan_errors`
- `model_predictions`
- `features_engineered`

## 🐛 Résolution de Problèmes

### Erreur : "cannot drop table because other objects depend on it"

Le script utilise `CASCADE` pour gérer automatiquement les dépendances. Si vous avez encore des erreurs :

```sql
-- Voir les dépendances
SELECT 
    dependent_ns.nspname as dependent_schema,
    dependent_view.relname as dependent_view,
    source_ns.nspname as source_schema,
    source_table.relname as source_table
FROM pg_depend 
JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid 
JOIN pg_class as dependent_view ON pg_rewrite.ev_class = dependent_view.oid 
JOIN pg_class as source_table ON pg_depend.refobjid = source_table.oid 
JOIN pg_namespace dependent_ns ON dependent_view.relnamespace = dependent_ns.oid 
JOIN pg_namespace source_ns ON source_table.relnamespace = source_ns.oid 
WHERE source_table.relname = 'nom_de_la_table';
```

### Erreur : "permission denied"

Assurez-vous d'être connecté en tant qu'utilisateur avec les droits appropriés :

```sql
-- Vérifier les permissions
SELECT current_user;

-- Si nécessaire, utiliser postgres (superuser)
\c trade_cursor_ml postgres
```

### Tables partitionnées non supprimées

Si les partitions de `scan_logs` ne sont pas supprimées :

```sql
-- Lister les partitions
SELECT tablename 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename LIKE 'scan_logs_%';

-- Supprimer manuellement si nécessaire
DROP TABLE IF EXISTS scan_logs_2025_01 CASCADE;
DROP TABLE IF EXISTS scan_logs_2025_02 CASCADE;
-- etc.

-- Puis supprimer la table principale
DROP TABLE IF EXISTS scan_logs CASCADE;
```

## 📝 Notes

- Le script de nettoyage est **idempotent** : vous pouvez l'exécuter plusieurs fois sans problème
- Les extensions (comme `uuid-ossp`) ne sont **pas supprimées** car nécessaires pour le nouveau schéma
- Si vous avez des **données importantes**, faites une sauvegarde avant !

## 🚀 Après la Migration

Une fois le nouveau schéma appliqué :

1. **Vérifier les tables** : `\dt`
2. **Vérifier les vues** : `\dv`
3. **Vérifier les fonctions** : `\df`
4. **Tester une requête** :
   ```sql
   SELECT * FROM get_global_stats();
   ```

---

**Version** : 1.0  
**Date** : 2025-01-11


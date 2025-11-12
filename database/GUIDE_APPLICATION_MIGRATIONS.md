# 🔧 Guide d'Application des Migrations SQL

**Date :** 2025-11-12

---

## 📋 Ordre d'Application des Migrations

Si vous avez une base de données existante, appliquez les migrations dans cet ordre :

### 1. Migration de base (si nécessaire)
```bash
# Si la base n'existe pas, créer le schéma complet
psql -U postgres -d trade_cursor_ml -f database/schema_postgresql_complete.sql
```

### 2. Migration complète (RECOMMANDÉ)
```bash
# Appliquer TOUTES les modifications en une seule fois
psql -U postgres -d trade_cursor_ml -f database/migration_complete_all_changes.sql
```

**OU** appliquer les migrations individuelles dans l'ordre :

### 2a. Migration market_context (JSONB)
```bash
psql -U postgres -d trade_cursor_ml -f database/migration_add_market_context_jsonb.sql
```

### 2b. Migration toutes les variables
```bash
psql -U postgres -d trade_cursor_ml -f database/migration_add_all_variables.sql
```

### 2c. Migration early_invalidation
```bash
psql -U postgres -d trade_cursor_ml -f database/migration_add_early_invalidation.sql
```

---

## ✅ Vérification Post-Migration

### Vérifier le nombre de colonnes
```sql
SELECT COUNT(*) as total_columns
FROM information_schema.columns
WHERE table_name = 'trades';
-- Attendu: ~115 colonnes
```

### Vérifier les colonnes spécifiques
```sql
-- Vérifier early_invalidation
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'trades' 
AND column_name LIKE 'early_invalidation%'
ORDER BY column_name;
-- Attendu: 6 colonnes

-- Vérifier config_snapshot
SELECT column_name, data_type
FROM information_schema.columns 
WHERE table_name = 'trades' 
AND column_name = 'config_snapshot';
-- Attendu: config_snapshot JSONB

-- Vérifier market_context JSONB
SELECT column_name, data_type
FROM information_schema.columns 
WHERE table_name = 'market_context' 
AND column_name IN ('global_metrics', 'session_stats');
-- Attendu: 2 colonnes JSONB
```

### Vérifier les index
```sql
SELECT indexname 
FROM pg_indexes 
WHERE tablename = 'trades' 
AND indexname LIKE '%early_invalidation%' OR indexname LIKE '%entry_hour%' OR indexname LIKE '%exit_hour%';
```

---

## 🔍 Script de Vérification Automatique

```bash
# Utiliser le script Python de vérification
python database/verify_schema_complete.py
```

---

## ⚠️ Notes Importantes

1. **Idempotence** : Toutes les migrations utilisent `IF NOT EXISTS`, elles peuvent être exécutées plusieurs fois sans erreur
2. **Ordre** : L'ordre d'application n'est pas critique (grâce à `IF NOT EXISTS`)
3. **Performance** : Les migrations peuvent prendre quelques secondes si la table `trades` contient déjà des données

---

## 📊 Résumé des Changements

### Table `trades`
- **+58 colonnes** d'indicateurs d'entrée additionnels
- **+12 colonnes** d'indicateurs de sortie
- **+4 colonnes** de métriques temporelles
- **+4 colonnes** de métriques de performance
- **+6 colonnes** d'early_invalidation
- **+1 colonne** config_snapshot (JSONB)

**Total : +85 colonnes ajoutées**

### Table `market_context`
- **+2 colonnes** JSONB (global_metrics, session_stats)

---

## 🚀 Après Migration

1. ✅ Vérifier avec `verify_schema_complete.py`
2. ✅ Redémarrer l'application
3. ✅ Vérifier les logs pour confirmer que le datalogger fonctionne
4. ✅ Vérifier qu'un trade est loggé avec toutes les colonnes


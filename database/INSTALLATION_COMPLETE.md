# 🚀 Installation Complète PostgreSQL - Trade Cursor

## 📋 Procédure Complète depuis Zéro

### ÉTAPE 1 : Se connecter à PostgreSQL

```bash
psql -U postgres
```

Si vous êtes déjà connecté, passez à l'étape 2.

### ÉTAPE 2 : Créer la Base de Données

```sql
-- Créer la base de données
CREATE DATABASE trade_cursor_ml;

-- Se connecter à la nouvelle base
\c trade_cursor_ml
```

### ÉTAPE 3 : Vérifier la Connexion

```sql
-- Vérifier que vous êtes bien connecté
SELECT current_database();
```

Vous devriez voir : `trade_cursor_ml`

### ÉTAPE 4 : Quitter psql Temporairement

```sql
\q
```

### ÉTAPE 5 : Exécuter le Schéma Complet

**Depuis PowerShell ou CMD, placez-vous dans le répertoire du projet :**

```bash
cd "C:\Users\sebta\Documents\clone github\test\test"
```

**Puis exécutez le schéma :**

```bash
psql -U postgres -d trade_cursor_ml -f database\schema_postgresql_complete.sql
```

**OU avec chemin absolu :**

```bash
psql -U postgres -d trade_cursor_ml -f "C:\Users\sebta\Documents\clone github\test\test\database\schema_postgresql_complete.sql"
```

### ÉTAPE 6 : Vérifier l'Installation

```bash
psql -U postgres -d trade_cursor_ml
```

Puis dans psql :

```sql
-- Lister les tables
\dt

-- Lister les vues
\dv

-- Lister les fonctions
\df

-- Tester une fonction
SELECT * FROM get_global_stats();
```

## ✅ Résultat Attendu

### Tables créées :
- `trading_sessions`
- `config_snapshots`
- `scan_logs` (table partitionnée)
- `opportunities`
- `trades`
- `market_context`
- `scan_errors`
- `model_predictions`
- `features_engineered`

### Vues créées :
- `scans_with_opportunities`
- `opportunities_executed`
- `daily_stats`
- `session_stats`
- `ml_features`

### Fonctions créées :
- `extract_hour_immutable()`
- `extract_date_immutable()`
- `cleanup_old_data()`
- `get_global_stats()`
- `create_monthly_partition()`
- `update_updated_at_column()`

## 🐛 Résolution de Problèmes

### Erreur : "database already exists"

```sql
-- Supprimer la base existante
DROP DATABASE IF EXISTS trade_cursor_ml;

-- Recréer
CREATE DATABASE trade_cursor_ml;
```

### Erreur : "permission denied"

```sql
-- Se connecter en tant que postgres (superuser)
\c postgres postgres

-- Puis créer la base
CREATE DATABASE trade_cursor_ml;
```

### Erreur : "No such file or directory"

**Vérifier le chemin :**
```bash
# Windows PowerShell
cd "C:\Users\sebta\Documents\clone github\test\test"
dir database\*.sql
```

**Utiliser le chemin absolu :**
```bash
psql -U postgres -d trade_cursor_ml -f "C:\Users\sebta\Documents\clone github\test\test\database\schema_postgresql_complete.sql"
```

### Erreur : "functions in index expression must be marked IMMUTABLE"

Le schéma est déjà corrigé avec les fonctions IMMUTABLE. Si vous avez encore cette erreur, exécutez d'abord :

```bash
psql -U postgres -d trade_cursor_ml -f "C:\Users\sebta\Documents\clone github\test\test\database\fix_immutable_error.sql"
```

Puis réexécutez le schéma complet.

## 📝 Script PowerShell Complet (Copier-Coller)

```powershell
# Script d'installation automatique
$dbName = "trade_cursor_ml"
$schemaPath = "C:\Users\sebta\Documents\clone github\test\test\database\schema_postgresql_complete.sql"

# Se connecter et créer la base
psql -U postgres -c "DROP DATABASE IF EXISTS $dbName;"
psql -U postgres -c "CREATE DATABASE $dbName;"

# Exécuter le schéma
psql -U postgres -d $dbName -f $schemaPath

# Vérifier
psql -U postgres -d $dbName -c "\dt"
```

---

**Version** : 1.0  
**Date** : 2025-01-11



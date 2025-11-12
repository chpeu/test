# 🚀 Guide d'Exécution du Schéma PostgreSQL

## 📍 Emplacement des Fichiers

Les fichiers SQL sont dans : `C:\Users\sebta\Documents\clone github\test\test\database\`

## 🔧 Méthode 1 : Chemin Absolu (Recommandé)

```bash
# Depuis n'importe quel répertoire
psql -U postgres -d trade_cursor_ml -f "C:\Users\sebta\Documents\clone github\test\test\database\fix_immutable_error.sql"
psql -U postgres -d trade_cursor_ml -f "C:\Users\sebta\Documents\clone github\test\test\database\schema_postgresql_complete.sql"
```

## 🔧 Méthode 2 : Se Placer dans le Bon Répertoire

```bash
# Se placer dans le répertoire du projet
cd "C:\Users\sebta\Documents\clone github\test\test"

# Puis exécuter avec chemin relatif
psql -U postgres -d trade_cursor_ml -f database\fix_immutable_error.sql
psql -U postgres -d trade_cursor_ml -f database\schema_postgresql_complete.sql
```

## 🔧 Méthode 3 : PowerShell (Windows)

```powershell
# Se placer dans le répertoire
cd "C:\Users\sebta\Documents\clone github\test\test"

# Exécuter les scripts
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -d trade_cursor_ml -f database\fix_immutable_error.sql
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -d trade_cursor_ml -f database\schema_postgresql_complete.sql
```

**Note** : Ajustez le chemin vers `psql.exe` selon votre installation PostgreSQL.

## 🔧 Méthode 4 : Depuis psql

```bash
# Se connecter à PostgreSQL
psql -U postgres -d trade_cursor_ml

# Puis dans psql :
\i "C:/Users/sebta/Documents/clone github/test/test/database/fix_immutable_error.sql"
\i "C:/Users/sebta/Documents/clone github/test/test/database/schema_postgresql_complete.sql"
```

**Note** : Dans psql, utilisez des `/` au lieu de `\` pour les chemins Windows.

## 📋 Ordre d'Exécution

1. **Optionnel** : Exécuter `fix_immutable_error.sql` pour créer les fonctions IMMUTABLE
2. **Obligatoire** : Exécuter `schema_postgresql_complete.sql` pour créer le schéma complet

## ✅ Vérification

Après l'exécution, vérifiez que les tables sont créées :

```sql
\dt
```

Vous devriez voir :
- `trading_sessions`
- `config_snapshots`
- `scan_logs`
- `opportunities`
- `trades`
- `market_context`
- `scan_errors`
- `model_predictions`
- `features_engineered`

## 🐛 Résolution de Problèmes

### Erreur : "No such file or directory"

**Solution** : Utilisez le chemin absolu ou placez-vous dans le bon répertoire.

### Erreur : "permission denied"

**Solution** : Assurez-vous d'avoir les droits sur la base de données :
```sql
GRANT ALL PRIVILEGES ON DATABASE trade_cursor_ml TO postgres;
```

### Erreur : "database does not exist"

**Solution** : Créez la base de données d'abord :
```sql
CREATE DATABASE trade_cursor_ml;
```

---

**Version** : 1.0  
**Date** : 2025-01-11



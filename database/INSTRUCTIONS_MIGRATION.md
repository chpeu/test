# 📋 Instructions pour Appliquer la Migration SQL

**Date :** 2025-11-12

---

## 🚨 IMPORTANT : Répertoire de Travail

Vous devez être dans le répertoire du projet pour exécuter la migration !

---

## ✅ Méthode 1 : PowerShell (Recommandé)

### Étape 1 : Ouvrir PowerShell
- Appuyez sur `Windows + X`
- Sélectionnez "Windows PowerShell" ou "Terminal"

### Étape 2 : Se déplacer dans le répertoire du projet
```powershell
cd "C:\Users\sebta\Documents\clone github\test\test"
```

### Étape 3 : Vérifier que vous êtes au bon endroit
```powershell
# Vérifier que le fichier existe
Test-Path "database\migration_complete_all_changes.sql"
# Doit retourner: True
```

### Étape 4 : Appliquer la migration
```powershell
psql -U postgres -d trade_cursor_ml -f database\migration_complete_all_changes.sql
```

**Vous serez demandé le mot de passe PostgreSQL** (celui configuré dans votre `.env`)

---

## ✅ Méthode 2 : Script Batch (Double-clic)

1. Naviguez vers : `C:\Users\sebta\Documents\clone github\test\test\database\`
2. Double-cliquez sur `APPLIQUER_MIGRATION.bat`
3. Entrez le mot de passe PostgreSQL quand demandé

---

## ✅ Méthode 3 : Script PowerShell (Double-clic)

1. Naviguez vers : `C:\Users\sebta\Documents\clone github\test\test\database\`
2. Clic droit sur `APPLIQUER_MIGRATION.ps1`
3. Sélectionnez "Exécuter avec PowerShell"
4. Entrez le mot de passe PostgreSQL quand demandé

**Note :** Si vous avez une erreur d'exécution de script, exécutez d'abord :
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## ✅ Méthode 4 : Chemin Absolu

Si vous êtes dans n'importe quel répertoire, utilisez le chemin complet :

```powershell
psql -U postgres -d trade_cursor_ml -f "C:\Users\sebta\Documents\clone github\test\test\database\migration_complete_all_changes.sql"
```

---

## 🔍 Vérification Post-Migration

Après avoir appliqué la migration, vérifiez :

```sql
-- Se connecter à PostgreSQL
psql -U postgres -d trade_cursor_ml

-- Compter les colonnes
SELECT COUNT(*) as total_columns
FROM information_schema.columns
WHERE table_name = 'trades';
-- Attendu: ~115 colonnes

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
```

---

## ⚠️ Dépannage

### Erreur : "No such file or directory"
**Cause :** Vous n'êtes pas dans le bon répertoire

**Solution :**
```powershell
# Vérifier votre répertoire actuel
pwd

# Se déplacer dans le répertoire du projet
cd "C:\Users\sebta\Documents\clone github\test\test"

# Vérifier que le fichier existe
ls database\migration_complete_all_changes.sql
```

### Erreur : "fe_sendauth: no password supplied"
**Cause :** Le mot de passe n'est pas fourni

**Solution :**
- Utilisez `-W` pour forcer la demande de mot de passe :
```powershell
psql -U postgres -d trade_cursor_ml -W -f database\migration_complete_all_changes.sql
```

### Erreur : "database does not exist"
**Cause :** La base de données n'existe pas

**Solution :**
```sql
-- Créer la base de données
CREATE DATABASE trade_cursor_ml;

-- Puis appliquer le schéma complet
psql -U postgres -d trade_cursor_ml -f database\schema_postgresql_complete.sql
```

---

## 📝 Commandes Utiles

```powershell
# Voir votre répertoire actuel
pwd

# Lister les fichiers dans database/
ls database\

# Vérifier que PostgreSQL est accessible
psql -U postgres -c "SELECT version();"
```

---

## ✅ Checklist

- [ ] Je suis dans le répertoire `C:\Users\sebta\Documents\clone github\test\test`
- [ ] Le fichier `database\migration_complete_all_changes.sql` existe
- [ ] PostgreSQL est démarré
- [ ] La base de données `trade_cursor_ml` existe
- [ ] Je connais le mot de passe PostgreSQL
- [ ] La migration s'est exécutée sans erreur
- [ ] J'ai vérifié que les colonnes sont présentes


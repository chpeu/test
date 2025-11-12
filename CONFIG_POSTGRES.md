# 🔧 Configuration PostgreSQL - Guide Rapide

## ❌ Erreur Actuelle
```
connection to server at "localhost" (::1), port 5432 failed: fe_sendauth: no password supplied
```

## ✅ Solution

### 1. Vérifier que PostgreSQL est installé et démarré

**Windows :**
```powershell
# Vérifier si PostgreSQL est en cours d'exécution
Get-Service -Name postgresql*

# Si pas démarré, démarrer :
Start-Service postgresql-x64-XX  # Remplacez XX par votre version
```

### 2. Configurer le mot de passe dans `.env`

Ouvrez votre fichier `.env` et ajoutez/modifiez :

```env
POSTGRES_ENABLED=true
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trade_cursor_ml
POSTGRES_USER=postgres
POSTGRES_PASSWORD=votre_mot_de_passe_ici  # ⚠️ IMPORTANT : Remplacez par votre mot de passe
POSTGRES_USE_SSL=false
```

### 3. Si vous ne connaissez pas le mot de passe PostgreSQL

**Option A : Réinitialiser le mot de passe (Windows)**

1. Ouvrez `pgAdmin` ou connectez-vous en ligne de commande
2. Ou modifiez le fichier `pg_hba.conf` pour autoriser les connexions sans mot de passe temporairement

**Option B : Créer un nouvel utilisateur**

```sql
-- Se connecter en tant que superutilisateur
psql -U postgres

-- Créer un nouvel utilisateur
CREATE USER trade_cursor WITH PASSWORD 'votre_nouveau_mot_de_passe';

-- Créer la base de données
CREATE DATABASE trade_cursor_ml OWNER trade_cursor;

-- Donner les permissions
GRANT ALL PRIVILEGES ON DATABASE trade_cursor_ml TO trade_cursor;
```

Puis dans `.env` :
```env
POSTGRES_USER=trade_cursor
POSTGRES_PASSWORD=votre_nouveau_mot_de_passe
```

### 4. Tester la connexion

```bash
psql -U postgres -d trade_cursor_ml -h localhost
# Ou avec le nouvel utilisateur :
psql -U trade_cursor -d trade_cursor_ml -h localhost
```

### 5. Créer le schéma

Une fois connecté, exécutez :
```bash
psql -U postgres -d trade_cursor_ml -f database/schema_postgresql_complete.sql
```

### 6. Redémarrer le serveur

```bash
python main.py
```

Vous devriez voir :
```
✅ PostgreSQL DataLogger initialisé: trade_cursor_ml@localhost:5432
```

---

## 🔍 Vérification

Après redémarrage, testez :
```sql
SELECT MAX(timestamp) as last_scan FROM scan_logs;
```

Si vous voyez un résultat (même NULL), la connexion fonctionne !


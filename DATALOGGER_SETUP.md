# Configuration du DataLogger PostgreSQL

## Problème : Tables Vides

Si vous constatez que les tables PostgreSQL (scan_logs, opportunities, etc.) sont vides malgré que le bot fonctionne, c'est probablement parce que **le datalogger est désactivé par défaut**.

## Solution : Activer le DataLogger

### Étape 1 : Créer le fichier .env

Copiez le fichier exemple :

```bash
cp .env.example .env
```

### Étape 2 : Configurer PostgreSQL

Éditez le fichier `.env` et ajustez les valeurs :

```env
# IMPORTANT: Activer le datalogger
POSTGRES_ENABLED=true

# Connexion PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trade_cursor_ml
POSTGRES_USER=postgres
POSTGRES_PASSWORD=VOTRE_MOT_DE_PASSE
```

### Étape 3 : Redémarrer le bot

Arrêtez et redémarrez le bot pour que les changements prennent effet :

```bash
# Arrêter le bot (Ctrl+C)
# Puis relancer
python main.py
```

### Étape 4 : Vérifier que ça fonctionne

Utilisez le script de diagnostic pour vérifier que les scans sont bien enregistrés :

```bash
python check_datalogger_tables.py --password VOTRE_MOT_DE_PASSE
```

Vous devriez voir :
- ✅ scan_logs avec des lignes
- ✅ Derniers scans affichés

## Exporter vers Excel

Une fois que le datalogger enregistre les données, vous pouvez exporter vers Excel :

```bash
# Export complet
python export_datalogger_to_excel.py --password VOTRE_MOT_DE_PASSE

# Résumé des données disponibles
python export_datalogger_to_excel.py --password VOTRE_MOT_DE_PASSE --summary
```

Ou via l'API :

```bash
curl -O http://localhost:5000/api/export/datalogger
```

## Vérification Rapide

```bash
# 1. Vérifier que POSTGRES_ENABLED=true dans .env
cat .env | grep POSTGRES_ENABLED

# 2. Vérifier les tables
python check_datalogger_tables.py --password VOTRE_MOT_DE_PASSE

# 3. Regarder les logs du bot
# Vous devriez voir : "✅ 10 scan(s) flushés avec succès"
```

## Pourquoi le datalogger est-il désactivé par défaut ?

Le datalogger PostgreSQL est optionnel car :
- Il nécessite une installation PostgreSQL
- Il consomme des ressources disque
- Certains utilisateurs veulent juste trader sans analyse ML

Pour l'analyse ML et l'optimisation des paramètres, il est **fortement recommandé** de l'activer.

## Dépannage

### Le bot dit "flushés avec succès" mais les tables sont vides

- ✅ Vérifiez que `POSTGRES_ENABLED=true` dans `.env`
- ✅ Redémarrez le bot après modification de `.env`
- ✅ Vérifiez les logs pour des erreurs de connexion PostgreSQL

### Erreur de connexion PostgreSQL

- ✅ PostgreSQL est-il démarré ?
- ✅ Le mot de passe est-il correct dans `.env` ?
- ✅ La base de données `trade_cursor_ml` existe-t-elle ?

```bash
# Créer la base si elle n'existe pas
psql -U postgres -c "CREATE DATABASE trade_cursor_ml;"

# Créer le schéma
psql -U postgres -d trade_cursor_ml -f database/schema_postgresql_complete.sql
```

### Tables créées mais vides

Attendez quelques minutes que le bot scanne les marchés. Les scans sont flushés par batch toutes les quelques secondes.

Vérifiez aussi que les partitions existent pour le mois en cours :

```sql
-- Scanner logs en novembre 2025
SELECT * FROM scan_logs_2025_11 LIMIT 10;
```

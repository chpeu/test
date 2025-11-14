# Export DataLogger PostgreSQL vers Excel

Ce document explique comment exporter toutes les tables du DataLogger PostgreSQL vers un fichier Excel multi-feuilles.

## Tables Exportées

Le script exporte **toutes** les tables du DataLogger PostgreSQL, incluant :

1. **trading_sessions** - Sessions de trading avec statistiques
2. **config_snapshots** - Historique des changements de configuration
3. **scan_logs** - Log de tous les scans (opportunités détectées ou non)
4. **opportunities** - Opportunités de trading détectées
5. **trades** - Historique complet des trades exécutés
6. **market_context** - Contexte de marché au moment des trades
7. **scan_errors** - Erreurs survenues lors des scans
8. **model_predictions** - Prédictions du modèle ML
9. **features_engineered** - Features calculées pour le ML

## Utilisation

### Option 1 : Via l'API (Recommandé)

L'API expose un endpoint pour télécharger l'export Excel :

```bash
# Export complet (toutes les tables)
curl -O http://localhost:5000/api/export/datalogger

# Export avec limite de lignes par table
curl -O "http://localhost:5000/api/export/datalogger?limit=1000"

# Export de tables spécifiques
curl -O "http://localhost:5000/api/export/datalogger?tables=config_snapshots,features_engineered"

# Résumé des données disponibles (JSON)
curl "http://localhost:5000/api/export/datalogger?summary_only=true"
```

### Option 2 : Script en ligne de commande

Le script peut être exécuté directement depuis la ligne de commande :

```bash
# Export complet
python3 export_datalogger_to_excel.py

# Export avec paramètres spécifiques
python3 export_datalogger_to_excel.py \
    --host localhost \
    --port 5432 \
    --database trade_cursor_ml \
    --user postgres \
    --output mon_export.xlsx

# Export avec limite de lignes
python3 export_datalogger_to_excel.py --limit 10000

# Export de tables spécifiques
python3 export_datalogger_to_excel.py --tables trading_sessions config_snapshots trades

# Afficher un résumé sans exporter
python3 export_datalogger_to_excel.py --summary
```

### Option 3 : Utilisation programmatique (Python)

```python
from export_datalogger_to_excel import DataLoggerExporter

# Créer l'exporteur
exporter = DataLoggerExporter()

# Connecter
if exporter.connect():
    # Export complet
    output_file = exporter.export_to_excel()
    print(f"Fichier créé: {output_file}")

    # Ou résumé
    summary = exporter.export_summary()
    for table, info in summary.items():
        print(f"{table}: {info['count']} lignes")

    # Déconnecter
    exporter.disconnect()
```

## Configuration PostgreSQL

Le script utilise les variables d'environnement suivantes (ou valeurs par défaut) :

- `POSTGRES_HOST` (défaut: localhost)
- `POSTGRES_PORT` (défaut: 5432)
- `POSTGRES_DB` (défaut: trade_cursor_ml)
- `POSTGRES_USER` (défaut: postgres)
- `POSTGRES_PASSWORD` (défaut: vide)

Vous pouvez aussi passer ces paramètres en arguments au script.

## Dépendances

Le script nécessite les bibliothèques Python suivantes :

```bash
pip install pandas openpyxl psycopg2-binary
```

## Format du Fichier Excel

Le fichier Excel généré contient :

- **Une feuille par table** (jusqu'à 9 feuilles)
- **Noms de feuilles tronqués à 31 caractères** (limitation Excel)
- **Toutes les colonnes de chaque table** avec leurs valeurs
- **En-têtes de colonnes** sur la première ligne
- **Formatage automatique** des types de données

## Exemples de Cas d'Usage

### Analyse ML

```bash
# Exporter uniquement les tables ML
python3 export_datalogger_to_excel.py \
    --tables features_engineered model_predictions trades \
    --limit 50000 \
    --output ml_analysis.xlsx
```

### Audit de Configuration

```bash
# Exporter uniquement config et sessions
python3 export_datalogger_to_excel.py \
    --tables config_snapshots trading_sessions \
    --output config_audit.xlsx
```

### Export Complet pour Backup

```bash
# Tout exporter sans limite
python3 export_datalogger_to_excel.py \
    --output backup_$(date +%Y%m%d).xlsx
```

## Résolution de Problèmes

### Erreur de connexion PostgreSQL

Vérifiez :
- Que PostgreSQL est démarré
- Que les identifiants sont corrects
- Que le firewall autorise la connexion

### Table vide ou inexistante

Si une table n'existe pas ou est vide, elle sera simplement ignorée avec un avertissement dans les logs.

### Fichier Excel trop volumineux

Si l'export est trop volumineux :
- Utilisez `--limit` pour limiter le nombre de lignes
- Exportez des tables spécifiques avec `--tables`
- Exportez en plusieurs fois par plage de dates

## Notes

- Les tables partitionnées (comme `scan_logs`) sont exportées dans leur ensemble
- Les données JSONB sont converties en texte dans Excel
- Les tableaux PostgreSQL sont convertis en texte séparé par des virgules
- Le script gère automatiquement les types de données PostgreSQL vers Excel

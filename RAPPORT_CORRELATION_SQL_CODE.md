# 📊 Rapport de Corrélation PostgreSQL ↔ Code Python

**Date** : 2025-11-15
**Base de données** : `trade_cursor_ml`
**Projet** : Trade Cursor v7.0

---

## 🎯 Résumé Exécutif

| Métrique | Valeur |
|----------|--------|
| **Total de tables** | 13 |
| **Tables utilisées** | 9 (69.2%) |
| **Tables non utilisées** | 4 (30.8%) |
| **Vues SQL** | 5 |
| **Fichiers Python utilisant PostgreSQL** | 4 |

---

## 📋 Tables PostgreSQL

### ✅ Tables Utilisées (9)

#### 1. **scan_logs** (Table Principale - Partitionnée)
- **Rôle** : Logs de TOUS les scans (opportunités ou non)
- **Utilisée dans** : 9 fichiers
- **Fichiers principaux** :
  - `core/postgresql_datalogger.py` : INSERT de tous les scans
  - `core/position_manager.py` : Lecture pour analyse
  - `main.py` : Export Excel
- **Partitions** : 3 mois (2025-11, 2025-12, 2026-01)

#### 2. **opportunities**
- **Rôle** : Opportunités détectées (subset de scan_logs)
- **Utilisée dans** : 7 fichiers
- **Fichiers principaux** :
  - `core/postgresql_datalogger.py` : Ligne 684 - INSERT opportunités
  - `main.py` : Export et affichage

#### 3. **trades** (Table Principale)
- **Rôle** : Trades exécutés avec résultats complets pour ML
- **Utilisée dans** : 19 fichiers (!!)
- **Fichiers principaux** :
  - `core/postgresql_datalogger.py` : Ligne 806 - INSERT trades
  - `core/analytics_database.py` : Ligne 624 - Analyse et requêtes
  - `core/database.py` : Ligne 84 - Opérations CRUD
  - `session_manager.py` : Statistiques de session

#### 4. **trading_sessions**
- **Rôle** : Sessions de trading pour analyse par période
- **Utilisée dans** : 6 fichiers
- **Fichiers principaux** :
  - `core/postgresql_datalogger.py` : Lignes 316, 324 - Gestion sessions
  - `check_datalogger_tables.py` : Ligne 163 - Vérification

#### 5. **config_snapshots**
- **Rôle** : Historique des changements de configuration
- **Utilisée dans** : 4 fichiers
- **Fichiers principaux** :
  - `main.py` : Ligne 4693
  - `export_datalogger_to_excel.py` : Export

#### 6. **market_context**
- **Rôle** : Contexte marché général (snapshots périodiques)
- **Utilisée dans** : 5 fichiers
- **Fichiers principaux** :
  - `database/verify_all.py` : Ligne 143 - Vérifications

#### 7. **scan_errors**
- **Rôle** : Logs d'erreurs de scan
- **Utilisée dans** : 4 fichiers

#### 8. **model_predictions**
- **Rôle** : Prédictions ML (pour usage futur)
- **Utilisée dans** : 3 fichiers

#### 9. **features_engineered**
- **Rôle** : Features pré-calculées pour ML avancé
- **Utilisée dans** : 3 fichiers

---

### ⚠️ Tables Non Utilisées (4)

| Table | Raison |
|-------|--------|
| **IF** | Erreur de parsing - probablement "CREATE TABLE IF NOT EXISTS" |
| **scan_logs_2025_11** | Partition automatique de `scan_logs` |
| **scan_logs_2025_12** | Partition automatique de `scan_logs` |
| **scan_logs_2026_01** | Partition automatique de `scan_logs` |

**Note** : Les partitions sont automatiquement gérées par PostgreSQL et ne sont pas référencées directement dans le code.

---

## 👁️ Vues SQL (5)

| Vue | Rôle |
|-----|------|
| **daily_stats** | Statistiques quotidiennes des trades |
| **ml_features** | Features extraites pour ML |
| **opportunities_executed** | Opportunités avec résultats de trade |
| **scans_with_opportunities** | Scans marqués comme opportunités |
| **session_stats** | Statistiques par session de trading |

---

## 🐍 Fichiers Python Utilisant PostgreSQL

### 1. **core/postgresql_datalogger.py** (Principal)
- **Rôle** : DataLogger principal pour PostgreSQL
- **Tables utilisées** :
  - `scan_logs` (INSERT ligne 444)
  - `opportunities` (INSERT ligne 684)
  - `trades` (INSERT ligne 806)
  - `trading_sessions` (INSERT ligne 324)

### 2. **core/analytics_database.py**
- **Rôle** : Analyses et requêtes avancées
- **Tables utilisées** :
  - `trades` (ligne 624, 693)

### 3. **core/database.py**
- **Rôle** : Base de données SQLite (legacy)
- **Tables utilisées** :
  - `trades` (ligne 84, 118)

### 4. **core/simple_pg_logger.py**
- **Rôle** : Logger PostgreSQL simplifié
- **Tables utilisées** :
  - `scan_logs` (ligne 58)

---

## 📊 Statistiques d'Utilisation

### Tables par Fréquence d'Utilisation

| Rang | Table | Fichiers | Utilisation |
|------|-------|----------|-------------|
| 1 | **trades** | 19 | 🔥🔥🔥 Très élevée |
| 2 | **scan_logs** | 9 | 🔥🔥 Élevée |
| 3 | **opportunities** | 7 | 🔥 Moyenne |
| 4 | **trading_sessions** | 6 | ✅ Régulière |
| 5 | **market_context** | 5 | ✅ Régulière |
| 6 | **config_snapshots** | 4 | ✅ Normale |
| 6 | **scan_errors** | 4 | ✅ Normale |
| 8 | **model_predictions** | 3 | ⚡ Faible |
| 8 | **features_engineered** | 3 | ⚡ Faible |

---

## 🔍 Analyse de Corrélation

### ✅ Points Forts

1. **Excellente couverture** : 69.2% des tables sont utilisées
2. **Tables principales bien intégrées** :
   - `scan_logs` : 9 fichiers
   - `opportunities` : 7 fichiers
   - `trades` : 19 fichiers (!)
   - `trading_sessions` : 6 fichiers

3. **Cohérence architecturale** :
   - Le datalogger principal (`postgresql_datalogger.py`) gère toutes les insertions
   - Les autres fichiers font des lectures/analyses
   - Séparation claire entre écriture et lecture

### ⚠️ Points d'Attention

1. **Tables ML peu utilisées** :
   - `model_predictions` : 3 fichiers seulement
   - `features_engineered` : 3 fichiers seulement
   - **Raison** : Fonctionnalités ML futures non encore implémentées

2. **Table "IF"** :
   - Probablement une erreur de parsing du regex
   - À vérifier dans le schéma SQL

---

## 🎯 Recommandations

### Immédiat

1. ✅ **Corriger le parsing** : Vérifier l'origine de la table "IF"
2. ✅ **Documentation** : Ajouter commentaires sur tables ML peu utilisées

### Futur

1. 🚀 **Implémenter ML** : Utiliser `model_predictions` et `features_engineered`
2. 🚀 **Utiliser les vues** : Les 5 vues SQL ne sont pas encore exploitées dans le code

---

## 📈 Workflow de Données

```
1. SCAN
   ↓
   scan_logs (INSERT via postgresql_datalogger.py:444)

2. OPPORTUNITÉ DÉTECTÉE
   ↓
   opportunities (INSERT via postgresql_datalogger.py:684)

3. TRADE EXÉCUTÉ
   ↓
   trades (INSERT via postgresql_datalogger.py:806)

4. FIN DE SESSION
   ↓
   trading_sessions (UPDATE)
```

---

## 🔗 Fichiers de Référence

- **Schéma SQL** : `database/schema_postgresql_complete.sql`
- **DataLogger** : `core/postgresql_datalogger.py`
- **Vérification** : `check_datalogger_tables.py`
- **Export Excel** : `export_datalogger_to_excel.py`
- **Ce rapport** : Généré par `analyze_sql_code_correlation.py`

---

**Conclusion** : La corrélation entre les tables PostgreSQL et le code Python est **excellente**. Les tables principales sont bien utilisées, et la séparation des responsabilités est claire. Les tables ML peu utilisées reflètent simplement que ces fonctionnalités sont prévues pour le futur.

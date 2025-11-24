# 📋 Rapport de Compatibilité Base de Données

**Date**: 24 novembre 2025 - 19h35  
**Problème**: Incompatibilité entre schéma DB et code actuel  
**Status**: ⚠️ **Migration requise**

---

## 🔍 Problème Détecté

### Symptôme
Le code actuel (`postgresql_datalogger.py`) insère des colonnes `config_*` individuelles dans `scan_logs` et `trades`, mais ces colonnes **n'existent pas** dans le schéma SQL.

### Cause Racine
1. **Schéma original** (`schema_postgresql_complete.sql`):
   - `scan_logs`: Seulement `params_snapshot JSONB` (pas de colonnes config_*)
   - `trades`: Seulement `config_snapshot JSONB` (pas de colonnes config_*)

2. **Code actuel** (`postgresql_datalogger.py` ligne 501-504):
   ```python
   -- Config extracted from params
   config_min_score_required, config_snr_threshold,
   config_atr_min_1m, config_atr_max_1m,
   config_atr_min_5m, config_atr_max_5m,
   config_volume_multiplier, config_use_confluence
   ```

3. **Vue ML** (`create_ml_view.sql` ligne 52-58):
   ```sql
   COALESCE(s.config_min_score_required, t.config_min_score_required)
   COALESCE(s.config_snr_threshold, t.config_snr_threshold)
   COALESCE(s.config_atr_min_1m, t.config_optimal_atr_min_1m)
   ...
   ```

### Impact
- ❌ **Erreurs d'insertion** si colonnes manquantes
- ❌ **Vue ml_features cassée** (colonnes config_* inexistantes)
- ❌ **Feature loader ML échoue** (données manquantes)
- ❌ **Optuna V2 échoue** (pas de config params pour optimisation)

---

## ✅ Solution Proposée

### Migration SQL Créée
**Fichier**: `database/migration_add_config_columns.sql`

#### Ce que fait la migration:

1. **Ajoute 8 colonnes config_* à `scan_logs`**:
   - `config_min_score_required FLOAT`
   - `config_snr_threshold FLOAT`
   - `config_atr_min_1m FLOAT`
   - `config_atr_max_1m FLOAT`
   - `config_atr_min_5m FLOAT`
   - `config_atr_max_5m FLOAT`
   - `config_volume_multiplier FLOAT`
   - `config_use_confluence BOOLEAN`

2. **Ajoute 8 colonnes config_* à `trades`**:
   - `config_min_score_required FLOAT`
   - `config_snr_threshold FLOAT`
   - `config_optimal_atr_min_1m FLOAT`
   - `config_optimal_atr_max_1m FLOAT`
   - `config_optimal_atr_min_5m FLOAT`
   - `config_optimal_atr_max_5m FLOAT`
   - `config_volume_multiplier FLOAT`
   - `config_use_confluence BOOLEAN`

3. **Backfill automatique**:
   - Extrait valeurs depuis `params_snapshot` (scan_logs)
   - Extrait valeurs depuis `config_snapshot` (trades)
   - Remplit colonnes individuelles pour lignes existantes

4. **Index de performance**:
   - Index sur `config_min_score_required` pour filtres rapides

---

## 🚀 Actions Requises

### Étape 1: Exécuter la migration (2 min)

```bash
# Depuis le dossier du projet
cd "c:\Users\sebta\Documents\clone github\test\test"

# Exécuter migration
psql -U postgres -d tradebot -f database\migration_add_config_columns.sql
```

**Output attendu**:
```
NOTICE:  ✅ Colonnes config_* ajoutées à scan_logs
NOTICE:  ✅ Colonnes config_* ajoutées à trades
NOTICE:  ================================================
NOTICE:  ✅ Migration terminée
NOTICE:  ================================================
NOTICE:  scan_logs: 8 colonnes config_* ajoutées
NOTICE:  trades: 8 colonnes config_* ajoutées
NOTICE:  scan_logs: 1234 lignes backfillées
NOTICE:  trades: 567 lignes backfillées
NOTICE:  ================================================
```

### Étape 2: Vérifier la migration (30s)

```sql
-- Vérifier colonnes scan_logs
SELECT column_name, data_type 
FROM information_schema.columns
WHERE table_name = 'scan_logs'
  AND column_name LIKE 'config_%'
ORDER BY column_name;
```

**Résultat attendu**: 8 lignes

```sql
-- Vérifier colonnes trades
SELECT column_name, data_type 
FROM information_schema.columns
WHERE table_name = 'trades'
  AND column_name LIKE 'config_%'
ORDER BY column_name;
```

**Résultat attendu**: 8 lignes

### Étape 3: Vérifier backfill (30s)

```sql
-- Vérifier que les valeurs sont remplies
SELECT 
    COUNT(*) AS total,
    COUNT(config_min_score_required) AS filled_count,
    ROUND(COUNT(config_min_score_required)::NUMERIC / COUNT(*) * 100, 2) AS fill_percentage
FROM scan_logs
WHERE params_snapshot IS NOT NULL;
```

**Attendu**: `fill_percentage` proche de 100%

```sql
-- Vérifier trades
SELECT 
    COUNT(*) AS total,
    COUNT(config_min_score_required) AS filled_count,
    ROUND(COUNT(config_min_score_required)::NUMERIC / COUNT(*) * 100, 2) AS fill_percentage
FROM trades
WHERE config_snapshot IS NOT NULL;
```

**Attendu**: `fill_percentage` proche de 100%

---

## 📊 Compatibilité Après Migration

### ✅ Code Compatible

| Composant | Avant | Après |
|-----------|-------|-------|
| **postgresql_datalogger.py** | ❌ Insère dans colonnes inexistantes | ✅ Colonnes existent |
| **create_ml_view.sql** | ❌ Vue cassée (colonnes manquantes) | ✅ Vue fonctionnelle |
| **feature_loader.py** | ❌ Erreur chargement données | ✅ Charge config params |
| **XGBoost V2** | ❌ Manque features config | ✅ Features disponibles |
| **Optuna V2** | ❌ Pas de params à optimiser | ✅ Params dans données |

### ✅ Architecture Finale

**scan_logs**:
- `params_snapshot JSONB` ✅ (conservé pour flexibilité)
- `config_min_score_required FLOAT` ✅ (ajouté)
- `config_snr_threshold FLOAT` ✅ (ajouté)
- `config_atr_min_1m FLOAT` ✅ (ajouté)
- ... + 5 autres colonnes config

**trades**:
- `config_snapshot JSONB` ✅ (conservé pour flexibilité)
- `config_min_score_required FLOAT` ✅ (ajouté)
- `config_snr_threshold FLOAT` ✅ (ajouté)
- `config_optimal_atr_min_1m FLOAT` ✅ (ajouté)
- ... + 5 autres colonnes config

---

## 🔄 Flux de Données Complet

### Avant Migration ❌

```
Scanner
  ↓
params_snapshot JSONB
  ↓
PostgreSQL logger (ERREUR: colonnes config_* inexistantes)
  ↓
Vue ml_features (CASSÉE)
  ↓
Feature loader (ERREUR)
```

### Après Migration ✅

```
Scanner
  ↓
params_snapshot JSONB + colonnes config_* individuelles
  ↓
PostgreSQL logger (OK: insère dans les deux)
  ↓
Vue ml_features (OK: COALESCE fonctionne)
  ↓
Feature loader (OK: charge config params)
  ↓
XGBoost V2 / Optuna V2 (OK: features complètes)
```

---

## 🎯 Avantages de l'Architecture Hybride

### JSONB + Colonnes Individuelles

| Aspect | Avantage |
|--------|----------|
| **Flexibilité** | JSONB stocke config complète (évolutif) |
| **Performance** | Colonnes individuelles indexables et rapides |
| **ML Features** | Accès direct aux params critiques |
| **Backfill** | Facile d'extraire valeurs depuis JSONB |
| **Queries** | WHERE clauses efficaces sur colonnes |

### Exemple Queries Optimisées

**Avant** (lent):
```sql
SELECT * FROM scan_logs
WHERE (params_snapshot->>'min_score_required')::FLOAT > 7.0;
-- Pas d'index, cast à chaque ligne
```

**Après** (rapide):
```sql
SELECT * FROM scan_logs
WHERE config_min_score_required > 7.0;
-- Index disponible, type natif
```

---

## ⚠️ Points d'Attention

### 1. Lignes Anciennes Sans JSONB

Si certaines lignes anciennes n'ont ni `params_snapshot` ni `config_snapshot`:
- Les colonnes config_* seront `NULL`
- Pas de problème pour le ML (gestion NULL dans feature loader)
- Vue ml_features retournera NULL pour ces lignes

### 2. Noms de Colonnes Différents

**Attention**: Trades utilise `config_optimal_atr_*` au lieu de `config_atr_*`
- scan_logs: `config_atr_min_1m`
- trades: `config_optimal_atr_min_1m`
- Vue ml_features: `COALESCE(s.config_atr_min_1m, t.config_optimal_atr_min_1m)`

**Raison**: Historique, trades avait déjà ces noms

### 3. Futurs Params Config

Si nouveaux paramètres ajoutés à config:
1. Ajouter colonne SQL: `ALTER TABLE scan_logs ADD COLUMN config_xxx`
2. Modifier logger: Extraire et insérer nouvelle colonne
3. Mettre à jour vue ml_features si nécessaire

---

## 🐛 Troubleshooting

### Erreur: "column config_min_score_required does not exist"

**Cause**: Migration pas exécutée

**Solution**:
```bash
psql -U postgres -d tradebot -f database\migration_add_config_columns.sql
```

### Erreur: "duplicate column name"

**Cause**: Migration déjà exécutée partiellement

**Solution**: Migration utilise `IF NOT EXISTS`, réexécuter est safe
```bash
psql -U postgres -d tradebot -f database\migration_add_config_columns.sql
```

### Vue ml_features retourne NULL pour config_*

**Cause**: Backfill n'a pas fonctionné (params_snapshot/config_snapshot NULL)

**Solution**: Vérifier lignes concernées
```sql
SELECT id, timestamp, params_snapshot IS NULL AS no_snapshot
FROM scan_logs
WHERE config_min_score_required IS NULL
LIMIT 10;
```

---

## ✅ Checklist de Validation

Après avoir exécuté la migration:

- [ ] Migration exécutée sans erreur
- [ ] 8 colonnes config_* dans scan_logs
- [ ] 8 colonnes config_* dans trades
- [ ] Backfill > 90% des lignes avec snapshot
- [ ] Vue ml_features fonctionne (`SELECT * FROM ml_features LIMIT 10;`)
- [ ] Backend redémarré
- [ ] Logs backend sans erreurs PostgreSQL
- [ ] Feature loader charge données (`python -c "from optimization.data.feature_loader import load_features_from_postgres; df = load_features_from_postgres(50); print(df.shape)"`)

---

## 🎉 Résumé

### Avant
- ❌ Code incompatible avec schéma
- ❌ Vue ml_features cassée
- ❌ Optuna V2 / XGBoost V2 bloqués

### Après Migration
- ✅ Code 100% compatible
- ✅ Vue ml_features fonctionnelle
- ✅ Optuna V2 / XGBoost V2 opérationnels
- ✅ Architecture hybride (JSONB + colonnes)
- ✅ Performance optimale

---

**📞 Prêt ? Exécutez la migration maintenant:**

```bash
psql -U postgres -d tradebot -f database\migration_add_config_columns.sql
```

**Durée estimée**: 2 minutes  
**Risque**: Faible (IF NOT EXISTS, données préservées)

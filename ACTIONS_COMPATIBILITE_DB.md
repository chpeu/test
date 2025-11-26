# ⚡ Actions Rapides - Compatibilité Base de Données

**Date**: 24 novembre 2025 - 19h40  
**Problème**: Colonnes `config_*` manquantes dans scan_logs et trades  
**Solution**: Migration SQL prête à exécuter  

---

## 🎯 ACTIONS IMMÉDIATES (5 minutes)

### 1️⃣ Vérifier l'incompatibilité (30 secondes)

```bash
python verify_db_compatibility.py
```

**Si échec**: Continuez à l'étape 2  
**Si succès**: Colonnes déjà présentes, rien à faire ! ✅

---

### 2️⃣ Exécuter la migration (2 minutes)

```bash
psql -U postgres -d tradebot -f database\migration_add_config_columns.sql
```

**Résultat attendu**:
```
NOTICE:  ✅ Colonnes config_* ajoutées à scan_logs
NOTICE:  ✅ Colonnes config_* ajoutées à trades
NOTICE:  scan_logs: 8 colonnes config_* ajoutées
NOTICE:  trades: 8 colonnes config_* ajoutées
NOTICE:  scan_logs: XXXX lignes backfillées
NOTICE:  trades: XXXX lignes backfillées
```

---

### 3️⃣ Valider la migration (30 secondes)

```bash
python verify_db_compatibility.py
```

**Résultat attendu**:
```
Score: 5/5 vérifications réussies
🎉 SUCCÈS ! Base de données 100% compatible
```

---

## 📊 Ce qui est corrigé

| Avant | Après |
|-------|-------|
| ❌ Code insère dans colonnes inexistantes | ✅ Colonnes existent |
| ❌ Vue ml_features cassée | ✅ Vue fonctionnelle |
| ❌ XGBoost V2 échoue | ✅ XGBoost V2 opérationnel |
| ❌ Optuna V2 échoue | ✅ Optuna V2 opérationnel |
| ❌ Feature loader erreur | ✅ Feature loader OK |

---

## 🔍 Détails Technique (si besoin)

### Colonnes ajoutées à `scan_logs`:
- `config_min_score_required FLOAT`
- `config_snr_threshold FLOAT`
- `config_atr_min_1m FLOAT`
- `config_atr_max_1m FLOAT`
- `config_atr_min_5m FLOAT`
- `config_atr_max_5m FLOAT`
- `config_volume_multiplier FLOAT`
- `config_use_confluence BOOLEAN`

### Colonnes ajoutées à `trades`:
- `config_min_score_required FLOAT`
- `config_snr_threshold FLOAT`
- `config_optimal_atr_min_1m FLOAT` *(nom différent)*
- `config_optimal_atr_max_1m FLOAT` *(nom différent)*
- `config_optimal_atr_min_5m FLOAT` *(nom différent)*
- `config_optimal_atr_max_5m FLOAT` *(nom différent)*
- `config_volume_multiplier FLOAT`
- `config_use_confluence BOOLEAN`

### Backfill automatique:
- Extraction depuis `params_snapshot` JSONB (scan_logs)
- Extraction depuis `config_snapshot` JSONB (trades)
- Remplissage automatique des lignes existantes

---

## ⏱️ Temps Total

```
Étape 1: Vérification    [██░░░░░░░░] 30s
Étape 2: Migration       [██████████] 2m
Étape 3: Validation      [██░░░░░░░░] 30s
                         ────────────────
                         TOTAL: 3 minutes
```

---

## 📚 Documentation Complète

| Fichier | Usage |
|---------|-------|
| **ACTIONS_COMPATIBILITE_DB.md** | Ce guide (démarrage rapide) |
| **RAPPORT_COMPATIBILITE_DB.md** | Analyse complète du problème |
| **migration_add_config_columns.sql** | Script SQL de migration |
| **verify_db_compatibility.py** | Script de vérification |

---

## 🆘 En cas de problème

### Erreur: "psql: command not found"
```bash
# Utiliser chemin complet
"C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -d tradebot -f database\migration_add_config_columns.sql
```

### Erreur: "permission denied"
```bash
# Se connecter en tant que superuser postgres
psql -U postgres -d tradebot -f database\migration_add_config_columns.sql
```

### Migration échoue partiellement
- La migration utilise `IF NOT EXISTS`
- Réexécuter est **safe** et ne casse rien
- Relancez simplement la commande

---

## ✅ Checklist Finale

Après les 3 étapes:

- [ ] Migration exécutée sans erreur
- [ ] `verify_db_compatibility.py` → 5/5 checks
- [ ] Vue ml_features fonctionne
- [ ] Backend redémarré (optionnel)
- [ ] Logs backend propres (optionnel)

**Si toutes les cases cochées**: ✅ **Problème résolu !**

---

**🚀 Prêt ? Commencez par l'Étape 1 ci-dessus !**

**Temps**: 3 minutes  
**Risque**: Aucun (IF NOT EXISTS, données préservées)  
**Impact**: Débloquer XGBoost V2 et Optuna V2

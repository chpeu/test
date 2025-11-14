# 🔧 Correction : Table trades manquante

## Problème

La table `trades` n'a pas été créée lors de l'exécution du schéma.

## Solution

Exécutez le script pour créer la table manquante :

### Depuis PowerShell/CMD

```bash
cd "C:\Users\sebta\Documents\clone github\test\test"
psql -U postgres -d trade_cursor_ml -f database\create_missing_trades_table.sql
```

### Depuis psql

```bash
psql -U postgres -d trade_cursor_ml
```

Puis :
```sql
\i "C:/Users/sebta/Documents/clone github/test/test/database/create_missing_trades_table.sql"
```

### Avec chemin absolu

```bash
psql -U postgres -d trade_cursor_ml -f "C:\Users\sebta\Documents\clone github\test\test\database\create_missing_trades_table.sql"
```

## Vérification

Après l'exécution :

```sql
-- Vérifier que la table existe
\dt trades

-- Vérifier la structure
\d trades

-- Tester la fonction
SELECT * FROM get_global_stats();
```

## Résultat attendu

La table `trades` devrait apparaître dans `\dt` et la fonction `get_global_stats()` devrait fonctionner.

---

**Note** : Le script crée aussi tous les index et le trigger nécessaires pour la table `trades`.



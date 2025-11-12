# 🔍 Commandes Rapides pour Lister l'Ancien Schéma

## Méthode 1 : Script Complet (Recommandé)

```bash
psql -U postgres -d trade_cursor_ml -f database/list_existing_schema.sql
```

Cela affichera tous les objets (tables, vues, fonctions, triggers, etc.) avec leurs détails.

## Méthode 2 : Commandes psql Directes

### Se connecter à PostgreSQL
```bash
psql -U postgres -d trade_cursor_ml
```

### Lister les tables
```sql
\dt
```

Ou avec plus de détails :
```sql
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
ORDER BY table_name;
```

### Lister les vues
```sql
\dv
```

Ou :
```sql
SELECT viewname 
FROM pg_views 
WHERE schemaname = 'public'
ORDER BY viewname;
```

### Lister les fonctions
```sql
\df
```

Ou :
```sql
SELECT proname as function_name
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public'
ORDER BY proname;
```

### Lister les triggers
```sql
SELECT 
    trigger_name,
    event_object_table as table_name
FROM information_schema.triggers
WHERE trigger_schema = 'public'
ORDER BY event_object_table, trigger_name;
```

### Lister les partitions (si table partitionnée)
```sql
SELECT tablename 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename LIKE 'scan_logs_%'
ORDER BY tablename;
```

### Lister les extensions
```sql
\dx
```

Ou :
```sql
SELECT extname, extversion 
FROM pg_extension;
```

## Méthode 3 : Export dans un Fichier

```bash
# Exporter la liste complète
psql -U postgres -d trade_cursor_ml -f database/list_existing_schema.sql > schema_inventory.txt

# Ou juste les tables
psql -U postgres -d trade_cursor_ml -c "\dt" > tables_list.txt
```

## Méthode 4 : Requête SQL Complète (Tout en Une)

```sql
-- Tout lister en une requête
SELECT 
    'TABLE' as object_type,
    table_name as object_name,
    NULL as parent_object
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'

UNION ALL

SELECT 
    'VIEW' as object_type,
    viewname as object_name,
    NULL as parent_object
FROM pg_views
WHERE schemaname = 'public'

UNION ALL

SELECT 
    'FUNCTION' as object_type,
    proname as object_name,
    NULL as parent_object
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public'

UNION ALL

SELECT 
    'TRIGGER' as object_type,
    trigger_name as object_name,
    event_object_table as parent_object
FROM information_schema.triggers
WHERE trigger_schema = 'public'

ORDER BY object_type, object_name;
```

## Exemples de Sortie

### Tables
```
              List of relations
 Schema |      Name       | Type  |  Owner   
--------+-----------------+-------+----------
 public | opportunities  | table | postgres
 public | scan_logs      | table | postgres
 public | trades         | table | postgres
```

### Vues
```
              List of relations
 Schema |        Name         | Type |  Owner   
--------+---------------------+------+----------
 public | daily_stats         | view | postgres
 public | opportunities_executed | view | postgres
```

## 💡 Astuce : Voir la Structure d'une Table

```sql
\d nom_de_la_table
```

Exemple :
```sql
\d scan_logs
```

Cela affichera :
- Colonnes avec types
- Index
- Contraintes
- Triggers
- Foreign keys

## 🎯 Après Avoir Trouvé les Noms

Une fois que vous avez la liste, vous pouvez :

1. **Vérifier manuellement** si les noms correspondent à ceux dans `drop_old_schema.sql`
2. **Adapter le script** si nécessaire
3. **Exécuter le nettoyage** avec `drop_old_schema.sql`

---

**Note** : Le script `drop_old_schema.sql` détecte automatiquement tous les objets, donc normalement vous n'avez pas besoin de modifier quoi que ce soit. Mais cette liste peut être utile pour vérifier avant/après.



# Journal des trades : remise en route le 18/11/2026

## Le problème, en une phrase

Le robot écrivait ses trades dans le vide : le fichier de réglages disait
`POSTGRES_ENABLED=false`, il n'y avait aucune base PostgreSQL sur la machine, et
le schéma SQL du dépôt est plus vieux que le code.

Ce que ça donnait à l'écran : carte rouge « Erreur connexion DB » sur l'onglet
Machine Learning, Historique vide, Corrélations vides, et le bilan demandé à
l'IA locale qui répondait « 0 trade fermé » même après des heures de marche.

## Ce qui a été fait, dans l'ordre

1. **Base installée** dans un conteneur Docker, joignable seulement depuis la
   machine (jamais depuis le réseau de la maison) :

   ```bash
   docker run -d --name tradebot-pg --restart unless-stopped \
     -e POSTGRES_PASSWORD="$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)" \
     -e POSTGRES_DB=trade_cursor_ml \
     -p 127.0.0.1:5432:5432 \
     -v tradebot-pg-data:/var/lib/postgresql/data \
     postgres:16-alpine
   ```

   Le mot de passe est lu dans `.env` au moment de la commande : il n'est écrit
   ni dans ce fichier, ni dans une note, ni dans le journal.

2. **Interrupteur activé** dans `.env` : `POSTGRES_ENABLED=true`.

3. **Structure créée** avec les fichiers déjà présents dans le dépôt :

   ```bash
   docker exec -i tradebot-pg psql -U postgres -d trade_cursor_ml \
     < database/schema_postgresql_complete.sql
   ```

   Puis les correctifs manquants, dans cet ordre :
   `add_post_exit_tracker_persistence.sql`, `add_ml_calibration_table.sql`,
   `migration_add_scalability_params.sql`,
   `migrations/add_market_regime_to_opportunities.sql`,
   `migrations/add_model_version_to_ml_calibration.sql`,
   `migrations/add_regime_circuit_breaker_columns.sql`,
   `migrations/add_orderflow_columns.sql`,
   `migrations/add_ml_confidence_threshold.sql`,
   `migrations/add_live_trading_columns.sql`,
   `migrations/add_ml_threshold_columns.sql`,
   `migrations/003_create_trade_events.sql`,
   `migrations/add_trade_atr_metrics.sql`.

4. **Colonnes que le code écrit et que le schéma ne connaissait pas** : 28 dans
   `scan_logs`, 6 dans `market_regime_history`, 1 dans `market_context`. Ajoutées
   avec `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. Deux types avaient été
   devinés nombre alors que la valeur est un mot (`session_market` vaut
   `EUROPE_OPEN`, `regime_at_scan` vaut `VOLATILE`) : corrigés en texte.

5. **Cloisons de rangement** : `scan_logs` est une table partitionnée par mois,
   et le schéma ne couvrait que novembre 2025 → janvier 2026. Créées pour
   février → décembre 2026 avec la fonction fournie :

   ```sql
   SELECT create_monthly_partition('scan_logs', date '2026-11-01');
   ```

## Résultat mesuré

| Avant | Après |
|---|---|
| 12 lignes d'erreur au démarrage | 0 |
| 0 ligne dans `scan_logs` | 151 après quelques minutes de marche |
| Historique et Corrélations vides | sessions et analyses qui se remplissent |

## Le garde-fou laissé pour la suite

`database/verifier_ecarts_base.py` compare les colonnes que le code écrit avec
celles que la base accepte :

```bash
.venv/bin/python database/verifier_ecarts_base.py              # regard seul
.venv/bin/python database/verifier_ecarts_base.py --appliquer  # ajoute ce qui manque
```

Avertissement assumé : il lit le code sans l'exécuter, donc sur les requêtes
construites à la volée il peut proposer un nom qui n'est pas une colonne. Vérifier
table par table avant `--appliquer`.

Une dernière colonne manquait côté lecture : `optimal_regime_retrospective`
(reclamée par la carte « Analyse des Corrélations »). Ajoutée, plus `regime_local`.
Depuis, plus aucune carte rouge.

Avertissement sur les sondes automatiques : une seconde version qui comparait
les requêtes lues à la table `trades` a proposé 36 « colonnes » qui étaient en
fait des alias de calcul (`wins`, `avg_pnl`) ou des mots du programme. Elle a
été retirée le jour même. La sonde gardée (`verifier_ecarts_base.py`) ne porte
que sur ce que le robot **écrit**, là où elle est fiable.

## Choix écrit dans le code ce jour

`RESET_HISTORY_AT_STARTUP` (`.env`, défaut `false`) : au démarrage, le robot ne
vide plus le journal des trades, les stats et les journaux. Avant, chaque
redémarrage effaçait tout — impossible de juger une semaine de marche. Les
sessions sont déjà séparées par `session_id`, donc l'ancien n'affiche pas par
dessus le nouveau.

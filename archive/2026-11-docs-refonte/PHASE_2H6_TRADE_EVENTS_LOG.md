# Phase 2H.6: Trade Events Log

**Date d'implementation:** 16/12/2025  
**Status:** COMPLETE

## Objectif

Creer une table `trade_events` pour historiser tous les changements d'etat d'un trade, permettant une analyse post-mortem detaillee.

## Probleme resolu

- L'analyse post-mortem etait limitee car on n'avait que l'etat final
- Impossible de reconstruire la courbe d'evolution du trade
- Questions sans reponse: "Quand le trailing a-t-il bouge?", "Pourquoi on n'a pas sorti au pic?"

## Solution implementee

### 1. Table PostgreSQL `trade_events`

```sql
CREATE TABLE trade_events (
    id SERIAL PRIMARY KEY,
    trade_id UUID REFERENCES trades(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    event_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    price_at_event FLOAT,
    pnl_pct_at_event FLOAT,
    pnl_usdt_at_event FLOAT,
    details JSONB
);
```

### 2. Types d'evenements supportes

| Event Type | Description | Details JSON |
|------------|-------------|--------------|
| `ENTRY` | Ouverture de position | - |
| `BE_TRIGGERED` | Break-even active | new_sl, trigger |
| `TRAILING_ACTIVATED` | Trailing stop active | trigger_pct |
| `TRAILING_SL_MOVED` | SL trailing deplace | old_sl, new_sl |
| `TRAILING_MFE_TRIGGERED` | MFE SL->BE | new_sl, mfe_pct, trigger_threshold |
| `MAX_PNL_REACHED` | Nouveau max PnL | previous_max |
| `MIN_PNL_REACHED` | Nouveau min PnL | previous_min |
| `PARTIAL_TP` | TP partiel execute | sold_pct, sold_usdt, remaining_usdt |
| `TP_ESCALIER_LEVEL` | Niveau TP escalier | level, profit |
| `STAGNATION_DETECTED` | Stagnation detectee | elapsed, pnl |
| `STAGNATION_MFE_PROTECT` | Protection MFE stagnation | mfe_pct |
| `SL_EXCHANGE_SET` | SL MEXC configure | sl_price, margin_pct |
| `EXIT` | Fermeture de position | reason, duration, gross_pnl, fees |

### 3. Exemple de "film" d'un trade

```
07:38:09 - ENTRY @ 0.10825
07:39:19 - BE_TRIGGERED (PnL +0.11%) - {new_sl: 0.10825, trigger: PARTIAL_TP}
07:39:22 - TRAILING_ACTIVATED - {trigger_pct: 0.15}
07:44:49 - MAX_PNL_REACHED (+0.97%)
07:45:10 - PARTIAL_TP (50% @ +0.80%) - {sold_pct: 50, sold_usdt: 12.5}
07:49:37 - EXIT - {reason: TS, duration: 688s, pnl: +0.01%}
```

## Fichiers modifies

### Backend
- `core/postgresql_datalogger.py` - Ajout methode `log_trade_event()`
- `core/position_manager.py` - Ajout methode `_log_trade_event()` et appels aux moments cles
- `database/migrations/003_create_trade_events.sql` - Migration SQL
- `database/migrations/004_add_partial_tp_columns.sql` - Colonnes partial_tp manquantes

### Frontend
- `frontend/src/lib/components/VariablesPanel.svelte` - Mise a jour popup export Excel

### Verification
- `verification/verify_trade_events.py` - Script de verification

## Integration avec l'export Excel

La table `trade_events` est automatiquement incluse dans l'export Excel du datalogger.
Le popup d'export mentionne maintenant cette table.

## Requetes utiles

### Voir le film d'un trade
```sql
SELECT 
    te.event_type,
    te.event_timestamp,
    te.price_at_event,
    te.pnl_pct_at_event,
    te.details
FROM trade_events te
WHERE te.trade_id = 'UUID_DU_TRADE'
ORDER BY te.event_timestamp;
```

### Compter les evenements par type
```sql
SELECT event_type, COUNT(*) 
FROM trade_events 
GROUP BY event_type 
ORDER BY COUNT(*) DESC;
```

### Trades avec trailing active mais sortis en SL
```sql
SELECT DISTINCT t.id, t.symbol, t.pnl_pct
FROM trades t
JOIN trade_events te ON te.trade_id = t.id
WHERE te.event_type = 'TRAILING_ACTIVATED'
AND t.exit_reason = 'SL';
```

## Verification

Executer le script de verification:
```bash
python verification/verify_trade_events.py
```

Output attendu:
```
Table trade_events exists: OK
Columns: OK
Events recorded: N (apres trades)
```

## Notes

- Les evenements sont logges de maniere non-bloquante (thread daemon)
- Les erreurs sont ignorees silencieusement pour ne pas impacter le trading
- Les evenements ne sont enregistres que si `trade_id` est disponible

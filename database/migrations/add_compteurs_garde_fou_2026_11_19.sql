-- Compteurs du garde-fou : ils doivent survivre au redémarrage.
-- 19/11/2026 : `TradingCircuitBreaker` comptait les prises du jour, les pertes
-- consécutives, le PnL du jour et l'état (pause/arrêt) en mémoire seulement. Un
-- redémarrage — plantage, coupure réseau, mise à jour — remettait tout à zéro :
-- le robot repartait avec 40 prises autorisées alors qu'il venait d'en prendre 40
-- et de perdre sa série. Les plafonds de dégâts étaient donc effaçables par un
-- simple redémarrage, ce qui les rend inutile.
--
-- Table ajoutée sans toucher à `circuit_breaker_events` (l'historique, qui
-- existait déjà) : ici on garde UNIQUEMENT l'état courant, une ligne par jour.
-- `pause_jusqua` est en `timestamp` simple, comme les horaires manipulés par le
-- garde-fou (heure locale de l'horloge système) — mélanger les références de
-- temps est précisément le bug corrigé le même jour par ailleurs.

BEGIN;

CREATE TABLE IF NOT EXISTS circuit_breaker_etat (
    jour               date        PRIMARY KEY,
    trades_pris        integer     NOT NULL DEFAULT 0,
    gains              integer     NOT NULL DEFAULT 0,
    pertes             integer     NOT NULL DEFAULT 0,
    pertes_consecutives integer    NOT NULL DEFAULT 0,
    pnl_jour_pct       numeric(10,4) NOT NULL DEFAULT 0,
    pnl_jour_usdt      numeric(14,2) NOT NULL DEFAULT 0,
    etat               text        NOT NULL DEFAULT 'ACTIVE',
    pause_jusqua       timestamp,
    motif_pause        text,
    maj_at             timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_circuit_breaker_etat_jour
    ON circuit_breaker_etat (jour DESC);

COMMIT;

-- Contrôles (lecture seule) :
--   select jour, trades_pris, pertes_consecutives, pnl_jour_pct, etat
--     from circuit_breaker_etat order by jour desc limit 3;

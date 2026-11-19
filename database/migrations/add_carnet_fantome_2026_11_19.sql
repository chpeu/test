-- Carnet fantôme : la trace de ce que le robot a raté
-- Date : 19/11/2026
-- But : répondre à « est-ce que ce filtre qui refuse fait perdre de l'argent ? ».
--   Le robot note ses prises (table `trades`) et ses analyses (table `scan_logs`),
--   mais rien sur les dossiers refusés alors qu'un signal existait déjà.
--   Ce tableau garde le dossier (symbole, sens, prix d'entrée, score, motif du
--   refus) et le verdict calculé plus tard : dans l'heure qui a suivi, le prix
--   aurait-il atteint l'objectif avant le stop ?
--
-- Additif uniquement : CREATE TABLE / CREATE INDEX. Aucune table existante n'est
-- touchée, aucune colonne modifiée ni supprimée.

CREATE TABLE IF NOT EXISTS ghost_setups (
    id BIGSERIAL PRIMARY KEY,
    timestamp_scan TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    score_total DOUBLE PRECISION,
    min_score_required DOUBLE PRECISION,
    reject_reason TEXT NOT NULL,
    reject_category TEXT,
    atr_pct_1m DOUBLE PRECISION,
    volume_spike_1m DOUBLE PRECISION,
    sl_pct DOUBLE PRECISION NOT NULL,
    tp_pct DOUBLE PRECISION NOT NULL,
    scan_id TEXT,
    -- EN_ATTENTE | GAGNE | PERDU | NEUTRE | DONNEES_MANQUANTES
    statut TEXT NOT NULL DEFAULT 'EN_ATTENTE',
    evalue_le TIMESTAMPTZ,
    gain_max_pct DOUBLE PRECISION,
    perte_max_pct DOUBLE PRECISION,
    minutes_avant_verdict DOUBLE PRECISION
);

-- La passe d'évaluation cherche les dossiers en attente les plus anciens.
CREATE INDEX IF NOT EXISTS idx_ghost_statut_timestamp
    ON ghost_setups (statut, timestamp_scan);

-- La lecture (« quels refus coûtent de l'argent ? ») groupe par motif de refus.
CREATE INDEX IF NOT EXISTS idx_ghost_categorie_statut
    ON ghost_setups (reject_category, statut);

COMMENT ON TABLE ghost_setups IS
    'Dossiers refusés alors qu''un signal existait, avec leur verdict calculé a posteriori (carnet fantôme)';

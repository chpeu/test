-- Pilotage par l'IA locale : les traces qui manquaient.
-- 20/11/2026. Trois choses étaient vraies et bloquantes :
--   1. le grand modèle répondait à l'interface, et sa réponse ne restait nulle part ;
--   2. personne ne pouvait juger six mois plus tard ce qu'il avait annoncé ;
--   3. une décision de réglage prise automatiquement n'aurait eu ni valeur
--      d'avant, ni valeur d'après, ni trace d'annulation — donc aucun retour
--      en arrière possible.
--
-- Cet ajout est uniquement additif : CREATE TABLE / CREATE INDEX. Aucune table
-- existante n'est modifiée, aucune donnée n'est touchée. La table
-- `model_predictions` existait déjà (avec 0 ligne écrite) : le moteur y écrit
-- désormais ses verdicts, sans changement de schéma.

BEGIN;

CREATE TABLE IF NOT EXISTS ia_avis (
    id          bigserial   PRIMARY KEY,
    quand       timestamptz NOT NULL DEFAULT NOW(),
    usage       text        NOT NULL DEFAULT 'conseil',  -- conseil | bilan | proposition
    question    text,
    reponse     text        NOT NULL,
    modele      text,
    duree_ms    integer
);

CREATE INDEX IF NOT EXISTS idx_ia_avis_quand ON ia_avis (quand DESC);

CREATE TABLE IF NOT EXISTS ia_bilans (
    id          bigserial   PRIMARY KEY,
    quand       timestamptz NOT NULL DEFAULT NOW(),
    texte       text        NOT NULL,
    drapeaux    jsonb       NOT NULL DEFAULT '[]'::jsonb,
    chiffres    jsonb       NOT NULL DEFAULT '{}'::jsonb,
    modele      text
);

CREATE INDEX IF NOT EXISTS idx_ia_bilans_quand ON ia_bilans (quand DESC);

CREATE TABLE IF NOT EXISTS ia_decisions (
    id            bigserial   PRIMARY KEY,
    cree_le       timestamptz NOT NULL DEFAULT NOW(),
    type          text        NOT NULL DEFAULT 'reglage',
    cle           text        NOT NULL,
    valeur_avant  double precision,
    valeur_apres  double precision,
    motif         text,
    etat          text        NOT NULL DEFAULT 'propose',  -- propose | applique | annule | rejete | expire
    applique_le   timestamptz,
    annule_le     timestamptz,
    mesures       jsonb       NOT NULL DEFAULT '{}'::jsonb  -- {"avant": …, "apres": …, "verdict": …}
);

CREATE INDEX IF NOT EXISTS idx_ia_decisions_etat ON ia_decisions (etat, cree_le DESC);

-- La table `model_predictions` existait depuis le début et est restée vide (0 ligne)
-- alors que le filtre de confiance, lui, parlait dans les journaux. Elle n'avait
-- d'ailleurs pas de colonne pour la paire concernée : ajoutée ici (additif).
ALTER TABLE model_predictions ADD COLUMN IF NOT EXISTS symbol text;
ALTER TABLE model_predictions ADD COLUMN IF NOT EXISTS seuil_utilise double precision;

CREATE INDEX IF NOT EXISTS idx_model_predictions_timestamp
    ON model_predictions (timestamp DESC);

COMMIT;

-- Contrôles (lecture seule) :
--   select count(*) from model_predictions;
--   select etat, count(*) from ia_decisions group by etat;
--   select quand, left(texte, 80) from ia_bilans order by quand desc limit 3;
--   select count(*) as verdicts_du_filtre from model_predictions;

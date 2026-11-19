"""Le carnet fantôme doit noter les refus et juger ce qu'ils ont donné.

Pourquoi ce fichier existe : sur 8 000 analyses, le robot en refuse la plupart, et
le journal ne garde que les prises acceptées. La question « ce filtre fait-il
perdre de l'argent ? » était donc sans réponse. Le carnet note les dossiers
refusés alors qu'un signal existait, puis une passe régulière écrit le verdict
d'après les bougies qui ont suivi.
"""

from contextlib import contextmanager

import pytest

from core.carnet_fantome import (
    GAGNE,
    NEUTRE,
    PERDU,
    categoriser,
    evaluer_fantomes,
    enregistrer_refus,
    verdict,
)


def bougie(haut, bas):
    """[timestamp, ouverture, haut, bas, clôture, volume] — seule importe la mèche."""
    return [0, 100.0, haut, bas, 100.0, 1.0]


# ── ranger les motifs ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "motif,famille",
    [
        ("Volume insuffisant: 0.27x < 0.72x requis", "volume_filter"),
        ("ATR sous-optimal: 0.263% (trop bas, min: 0.35%)", "atr_filter"),
        ("Score insuffisant: Long=1 → Score: 1.5/7.0", "score_insufficient"),
        ("SNR trop faible: 0.008 < 0.15", "snr_filter"),
        ("Raison mystérieuse", "autre"),
    ],
)
def test_chaque_refus_trouve_sa_famille(motif, famille):
    assert categoriser(motif) == famille


# ── le verdict, cœur du dispositif ───────────────────────────────────────────


def test_long_qui_atteint_objectif_d_abord_est_gagne():
    resultat = verdict(
        [bougie(100.20, 99.95), bougie(100.45, 100.10), bougie(100.65, 100.30)],
        entree=100.0,
        sens="LONG",
        sl_pct=0.22,
        tp_pct=0.60,
    )
    assert resultat["statut"] == GAGNE
    assert resultat["minutes_avant_verdict"] == 3.0
    assert resultat["gain_max_pct"] == pytest.approx(0.65)


def test_long_touche_le_stop_d_abord_est_perdu():
    resultat = verdict(
        [bougie(100.10, 99.75), bougie(100.65, 100.20)],
        entree=100.0,
        sens="LONG",
        sl_pct=0.22,
        tp_pct=0.60,
    )
    assert resultat["statut"] == PERDU
    assert resultat["minutes_avant_verdict"] == 1.0


def test_meme_bougie_des_deux_cotes_compte_comme_perte():
    """On ne sait pas dans quel ordre le prix est passé dans la bougie : prudence."""
    resultat = verdict(
        [bougie(100.70, 99.70)],
        entree=100.0,
        sens="LONG",
        sl_pct=0.22,
        tp_pct=0.60,
    )
    assert resultat["statut"] == PERDU


def test_short_juge_a_l_envers():
    resultat = verdict(
        [bougie(100.05, 99.85), bougie(99.55, 99.40)],
        entree=100.0,
        sens="SHORT",
        sl_pct=0.22,
        tp_pct=0.60,
    )
    assert resultat["statut"] == GAGNE
    assert resultat["gain_max_pct"] == pytest.approx(0.60)


def test_rien_ne_se_passe_sur_la_fenetre_est_neutre():
    resultat = verdict(
        [bougie(100.10, 99.95) for _ in range(10)],
        entree=100.0,
        sens="LONG",
        sl_pct=0.22,
        tp_pct=0.60,
    )
    assert resultat["statut"] == NEUTRE


# ── écriture et évaluation sur un faux journal ───────────────────────────────


class FauxCurseur:
    def __init__(self, journal):
        self.journal = journal

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, requete, params=None):
        self.journal.requetes.append((requete.strip().split()[0].upper(), params))
        return None

    def fetchall(self):
        return self.journal.lignes_en_attente


class FauxJournal:
    """Fait semblant d'être la connexion du journal et se souvient des écritures."""

    def __init__(self, lignes_en_attente=()):
        self.lignes_en_attente = list(lignes_en_attente)
        self.requetes = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self):
        return FauxCurseur(self)

    def commit(self):
        self.requetes.append(("COMMIT", None))


@pytest.fixture
def faux_journal(monkeypatch, lignes=()):
    import core.postgresql_datalogger as datalogger

    journal = FauxJournal(lignes)

    @contextmanager
    def connexion_menteuse():
        yield journal

    monkeypatch.setattr(datalogger, "connexion_journal", connexion_menteuse)
    return journal


def test_enregistrer_refus_classe_et_ecrit(faux_journal):
    ecrit = enregistrer_refus(
        symbole="XPL/USDT:USDT",
        sens="LONG",
        prix=0.0464,
        motif="Volume insuffisant: 0.27x < 0.72x requis",
        sl_pct=0.22,
        tp_pct=0.80,
        score=6.2,
        score_requis=9.0,
    )
    assert ecrit is True
    ordre, params = faux_journal.requetes[0]
    assert ordre == "INSERT"
    assert "volume_filter" in params


@pytest.mark.asyncio
async def test_la_passe_ecrit_le_verdict_d_un_dossier(faux_journal):
    faux_journal.lignes_en_attente = [(7, "XPL/USDT:USDT", "LONG", 100.0, 0.22, 0.60)]

    async def fausses_bougies(symbole, timeframe, limit):
        return [
            bougie(100.10, 99.95),
            bougie(100.15, 100.00),
            bougie(100.20, 100.05),
            bougie(100.25, 100.10),
            bougie(100.30, 100.15),
            bougie(100.70, 100.20),
        ]

    evalues, sans_donnees = await evaluer_fantomes(fausses_bougies, limite=5)
    assert (evalues, sans_donnees) == (1, 0)

    mise_a_jour = [r for r in faux_journal.requetes if r[0] == "UPDATE"]
    assert mise_a_jour, "la passe n'a pas écrit de verdict"
    assert GAGNE in mise_a_jour[0][1]
    assert 7 in mise_a_jour[0][1]


@pytest.mark.asyncio
async def test_sans_bougies_le_dossier_n_est_pas_invente(faux_journal):
    faux_journal.lignes_en_attente = [(9, "NUL/USDT:USDT", "LONG", 100.0, 0.22, 0.60)]

    async def pas_de_bougies(symbole, timeframe, limit):
        return []

    evalues, sans_donnees = await evaluer_fantomes(pas_de_bougies, limite=5)
    assert (evalues, sans_donnees) == (0, 1)


# ── le branchement ne doit pas se débrancher tout seul ───────────────────────


def test_l_analyse_note_bien_les_refus_apres_un_signal_1m():
    """`core.analyzer` est un paquet qui charge `core/analyzer.py` par chemin :
    c'est le fichier qu'il faut lire, pas le paquet (sinon le contrôle ne voit
    rien et le branchement peut disparaître sans que personne s'en aperçoive)."""
    from pathlib import Path

    chemin = Path(__file__).resolve().parent.parent / "core" / "analyzer.py"
    source = chemin.read_text(encoding="utf-8")
    assert "enregistrer_refus" in source and "carnet_fantome" in source, (
        "le carnet fantôme n'est plus branché sur le refus de la re-vérification "
        "5 minutes : les dossiers ratés redeviennent invisibles"
    )


def test_le_fichier_de_migration_est_additif():
    from pathlib import Path

    chemin = (
        Path(__file__).resolve().parent.parent
        / "database"
        / "migrations"
        / "add_carnet_fantome_2026_11_19.sql"
    )
    texte = chemin.read_text(encoding="utf-8").upper()
    for interdit in ("DROP ", "DELETE ", "TRUNCATE", "ALTER COLUMN"):
        assert interdit not in texte, f"le fichier de carnet fantôme contient {interdit}"
    assert "CREATE TABLE IF NOT EXISTS GHOST_SETUPS" in texte

"""La cage du pilotage IA : ce qu'il a le droit de toucher, et rien d'autre.

Ce fichier est la ceinture de sécurité. Ce qui y est vérifié :

  - l'IA ne peut proposer que six réglages, chacun avec ses bornes ;
  - la taille des prises, les plafonds de dégâts, les frais et le passage en
    réel sont **hors de portée** — un réglage bien justifié n'y change rien ;
  - une seule modification à la fois, et elle doit être mesurée avant qu'une
    autre soit proposée ;
  - une mesure plus mauvaise que l'avant fait revenir le réglage tout seul ;
  - le verdict du filtre de confiance est écrit en base (la table
    `model_predictions` est restée vide des semaines : 0 ligne).
"""

import json
from contextlib import contextmanager

import pytest

from config import TRADING_CONFIG
from core import pilotage_ia


# ── un faux journal pour voir ce qui est écrit, sans toucher la base réelle ──


class FauxCurseur:
    def __init__(self, magasin):
        self.magasin = magasin
        self.ligne = None
        self.lignes = []

    def execute(self, requete, params=None):
        self.magasin["ecritures"].append((" ".join(requete.split()), params))
        for motif, resultat in self.magasin.get("resultats", []):
            if motif in requete:
                if isinstance(resultat, list):
                    self.lignes = resultat
                else:
                    self.ligne = resultat
                break

    def fetchone(self):
        return self.ligne

    def fetchall(self):
        return self.lignes

    def close(self):
        pass


class FauxJournal:
    def __init__(self, magasin):
        self.magasin = magasin

    def cursor(self):
        return FauxCurseur(self.magasin)

    def commit(self):
        self.magasin["commits"] = self.magasin.get("commits", 0) + 1


@pytest.fixture
def journal(monkeypatch):
    magasin = {"ecritures": [], "commits": 0, "resultats": []}

    @contextmanager
    def connexion():
        yield FauxJournal(magasin)

    monkeypatch.setattr(pilotage_ia, "_present", lambda: True)
    monkeypatch.setattr(pilotage_ia, "_connexion", connexion)
    monkeypatch.setattr(pilotage_ia, "_ecrire_override", lambda changements: magasin.setdefault(
        "overrides", {}
    ).update(changements))
    return magasin


# ── la cage ──────────────────────────────────────────────────────────────────


def test_la_cage_est_courte_et_bornee():
    assert len(pilotage_ia.REGISTRE_CAGE) == 6
    for cle, regle in pilotage_ia.REGISTRE_CAGE.items():
        assert regle["min"] < regle["max"], cle
        assert regle.get("nom"), cle


def test_l_argent_n_est_pas_dans_la_cage():
    """Taille des prises, plafonds de dégâts, frais, réel : jamais proposables."""
    interdits = (
        "size", "usdt", "sl_pct", "tp_pct", "trading_mode", "dry_run",
        "api_key", "frais", "levier", "leverage", "max_loss", "max_size",
    )
    for cle in pilotage_ia.REGISTRE_CAGE:
        for mot in interdits:
            assert mot not in cle.lower(), f"{cle} touche à l'argent ou au risque maximal"


def test_un_reglage_hors_cage_est_refuse():
    ok, motif = pilotage_ia.appliquer("fixed_tp_pct", 0.01)
    assert ok is False
    assert "hors de la cage" in motif


def test_une_valeur_hors_bornes_est_refusee():
    ok, motif = pilotage_ia.appliquer("trailing_pnl_cap", 99.0)
    assert ok is False
    assert "hors bornes" in motif


def test_appliquer_ecrit_dans_le_fichier_qui_commande(journal):
    ok, motif = pilotage_ia.appliquer("trailing_pnl_cap", 0.65)
    assert ok is True and motif == ""
    assert journal["overrides"]["trailing_pnl_cap"] == 0.65
    assert TRADING_CONFIG["trailing_pnl_cap"] == 0.65


# ── les propositions de l'IA sont vérifiées, pas crues ───────────────────────


def une_reponse(tableau):
    return {"ok": True, "texte": json.dumps(tableau, ensure_ascii=False), "modele": "x", "motif": None}


class FauxConseiller:
    def __init__(self, reponse):
        self.reponse = reponse
        self.appels = 0

    def demander_avis(self, question, contexte="", timeout=45.0):
        self.appels += 1
        return self.reponse


@pytest.fixture
def conseiller(monkeypatch):
    def installer(reponse):
        faux = FauxConseiller(reponse)
        import ml.conseiller_ia as conseiller_ia

        monkeypatch.setattr(conseiller_ia, "demander_avis", faux.demander_avis)
        return faux

    return installer


def test_une_proposition_hors_cage_ne_passe_pas(journal, conseiller, monkeypatch):
    conseiller(une_reponse([{"cle": "atr_mult_sl", "valeur": 0.9, "motif": "stop trop serré"}]))
    retenues = pilotage_ia.propositions(bloc={"trades": 5})
    assert retenues == []
    assert not any("INSERT INTO ia_decisions" in e[0] for e in journal["ecritures"])


def test_une_proposition_hors_bornes_ne_passe_pas(journal, conseiller):
    conseiller(une_reponse([{"cle": "trailing_pnl_cap", "valeur": 12.0, "motif": "laisser courir"}]))
    assert pilotage_ia.propositions(bloc={"trades": 5}) == []
    assert not any("INSERT INTO ia_decisions" in e[0] for e in journal["ecritures"])


def test_une_proposition_valide_est_ecrite_en_attente(journal, conseiller):
    conseiller(une_reponse([{"cle": "trailing_pnl_cap", "valeur": 0.60, "motif": "4 prises ont rendu 0,3 %"}]))
    retenues = pilotage_ia.propositions(bloc={"trades": 5})
    assert len(retenues) == 1
    ecrite = [e for e in journal["ecritures"] if "INSERT INTO ia_decisions" in e[0]][-1]
    assert "propose" in ecrite[0]
    assert ecrite[1][0] == "trailing_pnl_cap"
    assert ecrite[1][2] == 0.60


def test_le_modele_qui_ecrit_autour_du_json_quand_meme_est_lu():
    assert pilotage_ia._lire_json("voici ma réponse : [{\"cle\": \"x\"}] voilà") == [{"cle": "x"}]
    assert pilotage_ia._lire_json("rien à proposer") == []


def test_une_seule_proposition_par_tour(journal, conseiller):
    conseiller(une_reponse([
        {"cle": "trailing_pnl_cap", "valeur": 0.60, "motif": "a"},
        {"cle": "gb_min_confidence", "valeur": 0.5, "motif": "b"},
    ]))
    assert len(pilotage_ia.propositions(bloc={"trades": 5})) == 1


def test_niveau_1_ne_propose_rien(journal, conseiller, monkeypatch):
    monkeypatch.setitem(TRADING_CONFIG, "pilote_ia_niveau", 1)
    faux = conseiller(une_reponse([{"cle": "trailing_pnl_cap", "valeur": 0.60, "motif": "a"}]))
    assert pilotage_ia.propositions(bloc={"trades": 5}) == []
    assert faux.appels == 0  # on ne demande même pas son avis au modèle


def test_une_modification_en_cours_de_mesure_bloque_les_nouvelles_propositions(journal, conseiller, monkeypatch):
    journal["resultats"] = [(
        "FROM ia_decisions",
        [(4, "reglage", "trailing_pnl_cap", 0.8, 0.6, "motif", "applique",
          "2026-11-20T10:00:00", "2026-11-20T09:00:00", {})],
    )]
    conseiller(une_reponse([{"cle": "trailing_pnl_cap", "valeur": 0.60, "motif": "a"}]))
    assert pilotage_ia.propositions(bloc={"trades": 5}) == []


# ── mesurer, puis revenir en arrière tout seul ───────────────────────────────


def test_une_mesure_pire_fait_revenir_le_reglage(journal, monkeypatch):
    journal["resultats"] = [
        ("FROM ia_decisions", [(4, "reglage", "trailing_pnl_cap", 0.8, 0.6, "motif", "applique",
                                "2026-11-20T10:00:00", "2026-11-20T09:00:00", {})]),
        ("avg(pnl_pct)", (0.10,)),   # après
    ]
    monkeypatch.setattr(pilotage_ia, "_gain_moyen_avant", lambda *a, **k: 0.40)
    annules = []
    monkeypatch.setattr(pilotage_ia, "annuler_decision",
                        lambda identifiant, motif="": annules.append((identifiant, motif)) or (True, ""))

    resultats = pilotage_ia.mesurer_modifications()

    assert resultats[0]["verdict"] == "pire"
    assert annules and annules[0][0] == 4
    assert "retour automatique" in annules[0][1]


def test_une_mesure_meilleure_ne_touchepas(journal, monkeypatch):
    journal["resultats"] = [
        ("FROM ia_decisions", [(7, "reglage", "gb_min_confidence", 0.4, 0.45, "motif", "applique",
                                "2026-11-20T10:00:00", "2026-11-20T09:00:00", {})]),
        ("avg(pnl_pct)", (0.30,)),
    ]
    monkeypatch.setattr(pilotage_ia, "_gain_moyen_avant", lambda *a, **k: 0.10)
    annules = []
    monkeypatch.setattr(pilotage_ia, "annuler_decision",
                        lambda identifiant, motif="": annules.append(identifiant) or (True, ""))

    resultats = pilotage_ia.mesurer_modifications()
    assert resultats[0]["verdict"] == "mieux"
    assert annules == []


def test_approuver_applique_la_valeur_proposee(journal, monkeypatch):
    monkeypatch.setattr(pilotage_ia, "_lire_decision", lambda identifiant: {
        "cle": "trailing_pnl_cap", "valeur_avant": 0.8, "valeur_apres": 0.6,
        "etat": "propose", "mesures": {}, "apres": 0.6,
    })
    ok, motif = pilotage_ia.approuver(3)
    assert ok is True, motif
    assert journal["overrides"]["trailing_pnl_cap"] == 0.6


def test_annuler_remet_la_valeur_d_avant(journal, monkeypatch):
    monkeypatch.setattr(pilotage_ia, "_lire_decision", lambda identifiant: {
        "cle": "trailing_min_distance", "valeur_avant": 0.12, "valeur_apres": 0.30,
        "etat": "applique", "mesures": {}, "apres": 0.30,
    })
    ok, motif = pilotage_ia.annuler_decision(9)
    assert ok is True, motif
    assert journal["overrides"]["trailing_min_distance"] == 0.12


# ── les alertes viennent des nombres, pas du modèle ──────────────────────────


def test_les_alertes_sont_calculees_sur_les_chiffres():
    signes = pilotage_ia.drapeaux({
        "trades": 12,
        "gain_moyen_par_prise": -0.08,
        "garde_fou": {"pertes_de_suite": 4},
        "occasions_ratees": {"GAGNE": 5, "PERDU": 1},
        "tranches": [{"sens": "LONG", "tranche": "40-45", "trades": 40, "pnl_moyen": -0.11}],
    })
    assert "4 pertes l'une après l'autre" in signes
    assert "les prises de la période perdent de l'argent" in signes
    assert "des occasions écartées auraient rapporté" in signes
    assert any("40-45" in s for s in signes)


def test_aucune_prise_est_signale():
    assert "aucune prise sur la période" in pilotage_ia.drapeaux({"trades": 0})


# ── la trace du filtre de confiance ──────────────────────────────────────────


def test_le_verdict_du_filtre_est_ecrit_en_base(journal):
    pilotage_ia.ecrire_prediction_filtre(
        symbole="ZEC/USDT:USDT", approuve=False, confiance=0.393, seuil=0.40, signes={"rsi": 61}
    )
    ecrite = [e for e in journal["ecritures"] if "INSERT INTO model_predictions" in e[0]]
    assert ecrite, "le verdict du filtre repartirait dans les seuls journaux"
    params = ecrite[-1][1]
    assert params[1] == "ZEC/USDT:USDT"
    assert params[2] is False
    assert params[3] == pytest.approx(0.393)


# ── branchement et migration ─────────────────────────────────────────────────


def test_l_orchestrateur_connait_la_boucle_de_pilotage():
    from core.scheduler import Scheduler

    assert hasattr(Scheduler, "set_pilotage_callback")
    assert hasattr(Scheduler, "_pilotage_loop")


def test_les_routes_de_pilotage_sont_declarees():
    from api.routes.ia import router

    chemins = {route.path for route in router.routes}
    for chemin in (
        "/api/ia/pilotage",
        "/api/ia/pilotage/niveau",
        "/api/ia/pilotage/bilan",
        "/api/ia/pilotage/approuver",
        "/api/ia/pilotage/rejeter",
        "/api/ia/pilotage/annuler",
    ):
        assert chemin in chemins, f"{chemin} manquante"


def test_la_migration_ajoute_sans_rien_casser():
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parent.parent
        / "database"
        / "migrations"
        / "add_pilotage_ia_2026_11_20.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS ia_decisions" in sql
    assert "ALTER TABLE model_predictions ADD COLUMN IF NOT EXISTS symbol" in sql
    for defense in ("DROP TABLE", "DROP COLUMN", "TRUNCATE", "DELETE FROM"):
        assert defense not in sql.upper()


def test_les_reglages_de_pilotage_sont_regles():
    assert TRADING_CONFIG["pilote_ia_actif"] is True
    assert TRADING_CONFIG["pilote_ia_niveau"] == 2  # propositions, humain approuve
    assert TRADING_CONFIG["pilote_ia_minutes"] == 60

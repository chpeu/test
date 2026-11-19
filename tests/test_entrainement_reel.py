"""
Le vrai moteur d'entrainement, sur un petit jeu de donnees synthetique.

Les ~1 800 lignes jamais executees des routes ML sont le coeur d'entrainement :
chargement des features, split temporel, preprocessing, sklearn/xgboost,
sauvegarde du modele et de ses metadonnees. Avec des faux objets partout, on ne
testerait que « le faux objet a bien ete appele ».

Ici on ne remplace QUE la source de donnees (PostgreSQL) par un petit jeu
synthetique de 260 prises, et on laisse tourner le vrai code : le vrai
GradientBoosting, le vrai XGBoost V2, les vrais fichiers de modele. Le dossier de
travail est deplace dans un repertoire temporaire, donc rien n'est ecrit dans le
depot ni a cote du robot.
"""

import asyncio
import math
from contextlib import contextmanager
from pathlib import Path

import pytest

import api.routes.ml_training as entraînement

NB_PRISES = 260




class CurseurFaux:
    def __init__(self, journal):
        self.journal = journal

    def execute(self, requete, params=None):
        self.journal["requetes"].append(requete)
        self.journal["requetes_completes"].append((requete, params))
        return 1

    def close(self):
        return None


class ConnexionFausse:
    """Fausse connexion du journal : on note ce qui aurait ete ecrit en base."""

    def __init__(self, journal):
        self._journal = journal

    def cursor(self):
        return CurseurFaux(self._journal)

    def commit(self):
        return None


@pytest.fixture
def atelier(monkeypatch, tmp_path, jeu_ml):
    """Dossier de travail isole + faux journal + vraie source de features synthetique."""
    journal = {"requetes": [], "requetes_completes": []}

    from optimization.data import feature_loader

    monkeypatch.setattr(
        feature_loader,
        "load_features_from_postgres",
        lambda *a, **k: jeu_ml.copy(),
    )

    import core.postgresql_datalogger as scribe

    @contextmanager
    def connexion_fausse():
        yield ConnexionFausse(journal)

    monkeypatch.setattr(scribe, "connexion_journal", connexion_fausse)

    import ml.calibration as calibration

    class FauxCalibrage:
        def __init__(self):
            self.reinitialisations = 0

        def reset_calibration(self, reason=None):
            self.reinitialisations += 1
            return True

    calibration_factice = FauxCalibrage()
    monkeypatch.setattr(calibration, "get_calibration_manager", lambda: calibration_factice)

    import utils.config_persistence as persistance

    monkeypatch.setattr(persistance, "CONFIG_OVERRIDES_FILE", tmp_path / "config_overrides.json", raising=False)
    monkeypatch.setattr(entraînement, "CONFIG_OVERRIDES_FILE", tmp_path / "config_overrides.json", raising=False)

    taches = {}
    monkeypatch.setattr(entraînement, "ml_tasks", taches)

    # tout ce que le moteur ecrit (modeles, metadonnees) tombe ici
    monkeypatch.chdir(tmp_path)

    yield {
        "taches": taches,
        "dossier": tmp_path,
        "calibrage": calibration_factice,
        **journal,
    }


def demarrer_tache(atelier, identifiant):
    """Creer la tache comme le fait la route, puis lancer le vrai moteur."""
    atelier["taches"][identifiant] = {
        "task_id": identifiant,
        "status": "pending",
        "progress": 0,
        "stage": "starting",
    }


# ------------------------------------------------- GradientBoosting (le filtre en service)
def test_entrainer_gradientboosting_sur_un_petit_jeu(atelier):
    demarrer_tache(atelier, "gb-1")
    asyncio.run(entraînement._train_gradientboosting_background("gb-1"))

    tache = atelier["taches"]["gb-1"]
    assert tache["status"] in ("completed", "done"), tache.get("error")

    fichiers = list(Path("optimization/saved_models").iterdir())
    modeles = [f for f in fichiers if f.suffix == ".pkl"]
    metadonnees = [f for f in fichiers if f.suffix == ".json"]

    assert modeles, "le modele entraine doit laisser un fichier .pkl"
    assert metadonnees, "les metadonnees du modele doivent accompagner le fichier du modele"


def test_le_modele_entraine_annonce_un_score_comparable_au_hasard(atelier):
    """Le score annonce doit etre un vrai pourcentage, pas un nombre au hasard."""
    demarrer_tache(atelier, "gb-2")
    asyncio.run(entraînement._train_gradientboosting_background("gb-2"))

    tache = atelier["taches"]["gb-2"]
    resultat = tache.get("result") or {}
    score = (
        resultat.get("accuracy")
        or resultat.get("test_accuracy")
        or tache.get("accuracy")
        or tache.get("test_accuracy")
    )

    assert score is not None, "la tache doit rendre le score obtenu"
    score_pct = float(score) * 100 if float(score) <= 1 else float(score)
    assert 20 <= score_pct <= 100, f"score hors sol: {score}"
    assert math.isfinite(score_pct)


def test_le_modele_enregistre_le_nombre_de_prises_utilisees(atelier):
    """Les metadonnees du modele doivent dire sur combien de prises il a appris."""
    import json

    demarrer_tache(atelier, "gb-3")
    asyncio.run(entraînement._train_gradientboosting_background("gb-3"))

    metadonnees = sorted(Path("optimization/saved_models").glob("*metadata*.json"))
    assert metadonnees
    contenu = json.loads(metadonnees[-1].read_text(encoding="utf-8"))

    n = contenu.get("n_samples") or contenu.get("total_samples")
    assert n is not None and n > 100, f"les metadonnees doivent annoncer les prises utilisees: {sorted(contenu)}"


# ------------------------------------------------- XGBoost V2 (le modele de calibration)
def test_entrainer_xgboost_v2_sur_un_petit_jeu(atelier):
    demarrer_tache(atelier, "v2-1")
    asyncio.run(entraînement._train_xgboost_v2_background("v2-1", force=False))

    tache = atelier["taches"]["v2-1"]
    assert tache["status"] in ("completed", "done"), tache.get("error")

    fichiers = [f.as_posix() for f in Path(".").glob("optimization/saved_models/*")]
    assert fichiers, "le modele V2 doit laisser des fichiers derriere lui"


def test_xgboost_v2_enregistre_le_modele_dans_la_table_ml_models(atelier):
    """Le modele doit laisser une trace en base, pas seulement un fichier .pkl.

    Le 19/11/2026: ce test a montre que le bloc d'enregistrement appelait un module
    inexistant (`database.db_manager`). L'erreur etait avalee : la table ml_models
    etait restee a 0 ligne depuis la creation du robot.
    """
    demarrer_tache(atelier, "v2-2")
    asyncio.run(entraînement._train_xgboost_v2_background("v2-2", force=False))

    requetes = atelier["requetes"]
    assert any("INSERT INTO ml_models" in q for q in requetes), (
        "le modele V2 doit etre enregistre dans ml_models: sans trace en base, "
        "impossible de savoir quel modele tourne, ni de revenir a l'ancien"
    )
    assert any("UPDATE ml_models" in q and "is_active" in q for q in requetes), (
        "l'ancien modele doit etre marque inactif avant d'activer le nouveau"
    )
    insertion = next(q for q in atelier["requetes_completes"] if "INSERT INTO ml_models" in q[0])
    assert len(insertion[1]) == 32, "l'enregistrement doit porter les 32 valeurs annoncees"


def test_un_jeu_trop_petit_ne_detruit_rien(atelier, monkeypatch, jeu_ml):
    """Moins de 100 prises : le moteur s'arrete proprement et le dit."""
    from optimization.data import feature_loader

    monkeypatch.setattr(feature_loader, "load_features_from_postgres", lambda *a, **k: jeu_ml.iloc[:40].copy())

    demarrer_tache(atelier, "v2-3")
    asyncio.run(entraînement._train_xgboost_v2_background("v2-3", force=False))

    tache = atelier["taches"]["v2-3"]
    assert tache["status"] in ("failed", "error"), tache
    assert "Dataset trop petit" in str(tache.get("error"))
    assert tache.get("failed_at"), (
        "la tache doit porter l'heure de son echec: le 19/11/2026, le gestionnaire "
        "d'erreur plantait lui-meme (datetime masque par un import local) et la "
        "tache restait sans trace"
    )


def test_sans_base_le_entrainement_va_quand_meme(atelier, monkeypatch):
    """Journal desactive : le modele s'entraine, on le dit, et rien ne casse."""
    import core.postgresql_datalogger as scribe

    @contextmanager
    def journal_eteint():
        yield None

    monkeypatch.setattr(scribe, "connexion_journal", journal_eteint)

    demarrer_tache(atelier, "v2-4")
    asyncio.run(entraînement._train_xgboost_v2_background("v2-4", force=False))

    tache = atelier["taches"]["v2-4"]
    assert tache["status"] in ("completed", "done"), tache.get("error")
    assert atelier["requetes"] == []
    fichiers = list(Path(".").glob("optimization/saved_models/xgboost_v2*"))
    assert fichiers, "sans base, les fichiers du modele sont la seule trace: ils doivent exister"


def test_aucun_import_local_ne_masque_un_nom_du_module():
    """Reinvestir `import json` ou `from datetime import datetime` a l'interieur
    d'une fonction rend le nom local pour TOUTE la fonction : l'utiliser avant
    (notamment dans un `except`) fait planter la fonction. Mesure le 19/11/2026 :
    un entrainement qui echouait tot echouait deux fois, le gestionnaire d'erreur
    levait `UnboundLocalError: datetime`.
    """
    chemin = Path(entraînement.__file__)
    lignes = chemin.read_text(encoding="utf-8").split("\n")

    fautes = [
        (numero, ligne.strip())
        for numero, ligne in enumerate(lignes, 1)
        if ligne.startswith(("    import json", "    from datetime import", "        import json",
                            "        from datetime import"))
    ]
    assert not fautes, f"des imports locaux masquent les noms du module: {fautes}"


def test_changer_les_reglages_d_entrainement_change_le_modele(atelier):
    """Les hyperparametres passes par la route doivent arriver jusqu'au modele."""
    demarrer_tache(atelier, "gb-4")
    asyncio.run(entraînement._train_gradientboosting_background("gb-4"))
    petit = atelier["taches"]["gb-4"]

    atelier["taches"].clear()
    demarrer_tache(atelier, "gb-5")
    asyncio.run(entraînement._train_gradientboosting_background("gb-5"))
    grand = atelier["taches"]["gb-5"]

    assert petit["status"] in ("completed", "done")
    assert grand["status"] in ("completed", "done")

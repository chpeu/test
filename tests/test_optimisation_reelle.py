"""Les tours d'optimisation Optuna, lancees pour de vrai sur un petit jeu.

Meme principe que `test_entrainement_reel.py` : on ne remplace que la source de
donnees (PostgreSQL) par 260 prises synthetiques, et on laisse Optuna choisir de
vrais hyperparametres en faisant de vrais apprentissages. Le dossier de travail
est un repertoire temporaire, et le fichier ou le tour GradientBoosting ecrit ses
resultats est redirige (constante `RESULTATS_GB`) : rien n'est ecrit dans le
depot ni a cote du robot.
"""

import asyncio
import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ces tests lancent de vraies sessions Optuna (donc de vraies sessions SQL).
# Un autre fichier de la suite laisse l'interne de SQLAlchemy dans un etat ou
# `create_study` echoue (`TypeError: 'InternalTraversal' object is not callable`,
# dans le module compile de SQLAlchemy 2.1.3). Meme une etude Optuna creee dans
# un fichier temporaire y right pas. Ils sont donc marques pour tourner dans
# leur propre processus: etape dediee de GitHub Actions, et
# `pytest tests/test_optimisation_reelle.py` a la main.
pytestmark = pytest.mark.optuna_lourd

import api.routes.ml_optimization as optimisation

NB_ESSAIS = 3


@pytest.fixture(scope="module")
def client():
    from main import app

    return TestClient(app)


class CurseurFaux:
    def __init__(self, journal):
        self.journal = journal

    def execute(self, requete, params=None):
        self.journal["requetes"].append(requete)
        return 1

    def close(self):
        return None


class ConnexionFausse:
    def __init__(self, journal):
        self._journal = journal

    def cursor(self):
        return CurseurFaux(self._journal)

    def commit(self):
        return None


@pytest.fixture
def atelier(monkeypatch, tmp_path, jeu_ml):
    """Donnees synthetiques + resultats rediriges + dossier de travail isole."""
    from optimization.data import feature_loader

    monkeypatch.setattr(feature_loader, "load_features_from_postgres", lambda *a, **k: jeu_ml.copy())
    # `ml.hyperparameter_tuning` a importe la fonction directement (donc il possede
    # sa propre reference): remplacer l'attribut du module d'origine ne suffit pas,
    # et sans ce second faux l'optimisation allait lire la vraie base du robot.
    import ml.hyperparameter_tuning as tuning

    monkeypatch.setattr(tuning, "load_features_from_postgres", lambda *a, **k: jeu_ml.copy())

    # Le tuner choisit son stockage tout seul: la base PostgreSQL du robot si elle
    # est joignable, sinon un fichier sqlite pose la ou le programme tourne. Dans
    # les tests c'est doublement mauvais (gauche sur la base du robot, et resultat
    # qui depend de ce que les autres tests ont laisse). On epingle un fichier
    # temporaire pour chaque test.
    classe_accordeur = tuning.HyperparameterTuner
    chemin_stockage = tmp_path / "optuna_etudes.db"

    class AccordeurAStockageLocal(classe_accordeur):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("storage", f"sqlite:///{chemin_stockage}")
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(tuning, "HyperparameterTuner", AccordeurAStockageLocal)

    # le module garde aussi l'etat du tour V2 en tete: sans remise a zero, la
    # deuxieme demande repond "optimisation V2 deja en cours" au lieu de demarrer
    monkeypatch.setattr(
        optimisation,
        "optuna_v2_state",
        {
            "is_running": False,
            "progress": 0,
            "current_trial": 0,
            "total_trials": 0,
            "best_params": None,
            "best_value": None,
            "run_best_params": None,
            "run_best_score": None,
            "run_best_trial": None,
        },
    )

    # le module se souvient du dernier tour Optuna: sans remise a zero, la deuxieme
    # demande de la journee repond "optimisation deja en cours" (409)
    monkeypatch.setattr(optimisation, "_gb_optuna_task", {
        "status": "idle",
        "task_id": None,
        "progress": 0,
        "current_trial": 0,
        "total_trials": 0,
        "best_score": 0,
        "best_params": None,
        "error": None,
        "started_at": None,
        "completed_at": None,
    })
    # les routes de demarrage comptent d'abord les prises en base : sans ce faux,
    # elles repondent 400 et ne lancent rien (et ouvriraient un vrai pool PostgreSQL)
    monkeypatch.setattr(feature_loader, "get_trades_count", lambda: 4000)

    import core.postgresql_datalogger as scribe

    journal = {"requetes": []}

    @contextmanager
    def connexion_fausse():
        yield ConnexionFausse(journal)

    monkeypatch.setattr(scribe, "connexion_journal", connexion_fausse)

    import ml.calibration as calibration

    class FauxCalibrage:
        def reset_calibration(self, reason=None):
            return True

    monkeypatch.setattr(calibration, "get_calibration_manager", lambda: FauxCalibrage())

    import utils.config_persistence as persistance

    monkeypatch.setattr(persistance, "CONFIG_OVERRIDES_FILE", tmp_path / "config_overrides.json", raising=False)

    # le tour GB ecrit ses resultats a cote de son propre fichier : on le deplace
    chemin_resultats = tmp_path / "data" / "optuna_gb_results.json"
    chemin_resultats.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(optimisation, "RESULTATS_GB", str(chemin_resultats))

    # idem pour le modele et les metadonnees du tour GB : sans ca, les tests laissent
    # des .pkl dans le depot (mesure du 19/11/2026 : 10 fichiers orphelins) et par
    #-dessus un enregistrement historique de dec. 2025
    import optimization.optuna_gradientboosting as tuner_gb_avance

    monkeypatch.setattr(
        tuner_gb_avance,
        "__file__",
        str(tmp_path / "optimization" / "optuna_gradientboosting.py"),
    )

    import optimization.optuna_gb_tuner as tuner_gb

    monkeypatch.setattr(tuner_gb, "OPTIMIZATION_DIR", tmp_path / "optimization" / "saved_models")

    # le dictionnaire des taches est partage par les deux modules de routes ML et
    # par `ml_common.create_task` : il faut le remplacer partout a la fois, sinon la
    # route cree sa tache d'un cote et va la chercher de l'autre
    import api.routes.ml_common as ml_common

    taches = {}
    monkeypatch.setattr(optimisation, "ml_tasks", taches)
    monkeypatch.setattr(ml_common, "ml_tasks", taches)

    # photo du depot avant : un tour d'optimisation ne doit rien y laisser
    depot_modeles = Path(__file__).resolve().parent.parent / "optimization" / "saved_models"
    avant = set(depot_modeles.glob("*")) if depot_modeles.exists() else set()

    monkeypatch.chdir(tmp_path)

    yield {"taches": taches, "dossier": tmp_path, "resultats_gb": chemin_resultats, "journal": journal}

    orphelins = sorted(p.name for p in set(depot_modeles.glob("*")) - avant)
    assert not orphelins, (
        f"le tour d'optimisation a laisse des fichiers dans le depot: {orphelins}"
    )


def demarrer_tache(atelier, identifiant):
    atelier["taches"][identifiant] = {
        "task_id": identifiant,
        "status": "pending",
        "progress": 0,
        "stage": "starting",
    }


# ------------------------------------------------- optimisation XGBoost (le modele de calibration)
def test_un_tour_d_optimisation_designe_un_vrai_meilleur(atelier):
    demarrer_tache(atelier, "xgb-1")

    asyncio.run(optimisation._optimize_hyperparameters_background("xgb-1", NB_ESSAIS, 120, "accuracy", False, 260))

    tache = atelier["taches"]["xgb-1"]
    assert tache["status"] == "completed", tache.get("error")
    assert tache["n_trials_completed"] == NB_ESSAIS

    params = tache["best_params"]
    assert 2 <= params["max_depth"] <= 12, f"profondeur hors de la zone cherchee: {params['max_depth']}"
    assert 0 < params["subsample"] <= 1
    assert 0 <= tache["best_score"] <= 1, "le score doit etre une proportion, pas un nombre au hasard"


def test_le_tour_rapporte_ce_qu_a_ete_essaye(atelier):
    demarrer_tache(atelier, "xgb-2")

    asyncio.run(optimisation._optimize_hyperparameters_background("xgb-2", NB_ESSAIS, 120, "roc_auc", False, 260))

    tache = atelier["taches"]["xgb-2"]
    assert tache["n_trials_completed"] + tache["n_trials_pruned"] == NB_ESSAIS, (
        "chaque essai doit etre compte quelque part: otherwise le tour peut "
        "s'arreter a mi-chemin sans que personne le sache"
    )


def test_une_metrique_invalide_n_empeche_pas_le_tour_de_s_interrompre_proprement(atelier):
    demarrer_tache(atelier, "xgb-3")

    asyncio.run(optimisation._optimize_hyperparameters_background("xgb-3", 2, 60, "accuracy", False, 100))

    tache = atelier["taches"]["xgb-3"]
    assert tache["status"] in ("completed", "error"), tache
    if tache["status"] == "error":
        assert tache.get("failed_at") or tache.get("error"), "un tour rate doit laisser une trace lisible"


# ------------------------------------------------- optimisation GradientBoosting (le filtre en service)
def test_un_tour_gb_ecrit_ses_resultats_dans_le_fichier_prevu(atelier):
    demarrer_tache(atelier, "gb-1")

    asyncio.run(optimisation._optimize_gradientboosting_background("gb-1", NB_ESSAIS, 2, 30, False))

    tache = atelier["taches"]["gb-1"]
    assert tache["status"] == "completed", tache.get("error")

    fichier = atelier["resultats_gb"]
    assert fichier.exists(), "le tour doit laisser son resultat ailleurs qu'en memoire: sinon, au redemarrage, tout est perdu"

    contenu = json.loads(fichier.read_text(encoding="utf-8"))
    assert contenu["status"] == "completed"
    assert contenu["best_params"]["n_estimators"] > 0
    assert 0 < contenu["best_params"]["learning_rate"] < 0.5


def test_la_route_de_resultats_retrouve_le_tour_qui_vient_de_faire(atelier, client):
    demarrer_tache(atelier, "gb-2")
    asyncio.run(optimisation._optimize_gradientboosting_background("gb-2", NB_ESSAIS, 2, 30, False))

    corps = client.get("/api/ml/optimize/gb/results").json()

    assert corps["found"] is True
    assert corps["best_params"]["n_estimators"] > 0


def test_appliquer_les_meilleurs_params_gb_d_une_optimisation_qui_vient_de_turner(atelier, client, tmp_path):
    """Le cycle complet : optimiser, puis appliquer ce qu'Optuna a trouve."""
    demarrer_tache(atelier, "gb-3")
    asyncio.run(optimisation._optimize_gradientboosting_background("gb-3", NB_ESSAIS, 2, 30, False))

    chemin_config = tmp_path / "config_overrides.json"
    reponse = client.post("/api/ml/optimize/gb/apply", params={"config_file": str(chemin_config)})
    corps = reponse.json()

    assert reponse.status_code == 200, corps
    ecrit = json.loads(chemin_config.read_text(encoding="utf-8"))
    assert "gb_max_iter" in ecrit or "gb_learning_rate" in ecrit, (
        f"les parametres trouves par Optuna doivent arriver dans les reglages: {sorted(ecrit)}"
    )


# ------------------------------------------------- les routes qui lancent les tours
def test_la_route_optimize_v2_enregistre_la_tache_et_repond_vite(atelier, client):
    """10 essais: le minimum que la route accepte. La reponse revient avant la fin.

    Le tour tourne en tache de fond: la route doit donc rendre un identifiant de
    tache et laisser la suite consultable, pas simuler une fin immediate.
    """
    reponse = client.post("/api/ml/optimize_v2/start", params={"n_trials": 10})
    assert reponse.status_code == 200, reponse.json()
    corps = reponse.json()

    assert corps["status"] == "started"
    assert corps["n_trials"] == 10
    assert corps["trades_count"] > 0, "la route annonce le nombre de prises sur lesquelles elle va chercher"
    assert "message" in corps

    suivi = client.get("/api/ml/optimize_v2/status")
    assert suivi.status_code == 200
    assert isinstance(suivi.json(), dict)


def test_le_tour_gb_par_sa_route_est_suivable_pendant_qu_il_tourne(atelier, client):
    """20 essais / 5 minutes: la route refuse en dessous, et c'est voulu.

    Comme pour V2, le tour est lance sans attendre: ce qu'on exige, c'est qu'il
    soit enregistre et consultable pendant qu'il tourne (le test direct du moteur
    verifierait plus haut que le fichier de resultats est bien ecrit a la fin).
    """
    reponse = client.post("/api/ml/optimize_gb", params={"n_trials": 20, "timeout_minutes": 5})
    assert reponse.status_code == 200, reponse.json()
    corps = reponse.json()

    assert corps["success"] is True
    assert corps["task_id"], "sans identifiant, impossible de suivre le tour ou de l'arreter"
    assert corps["status_url"] == "/api/ml/optimize_gb/status"

    suivi = client.get("/api/ml/optimize_gb/status")
    assert suivi.status_code == 200
    assert isinstance(suivi.json(), dict)


def test_une_route_refuse_un_tour_trop_petit(client):
    """Les bornes existent: un tour de 3 essais ne sert a rien, la route le dit."""
    assert client.post("/api/ml/optimize_gb", params={"n_trials": 3}).status_code == 422
    assert client.post("/api/ml/optimize_v2/start", params={"n_trials": 3}).status_code == 422


# ------------------------------------------------- garde-fou sur le chemin des resultats
def test_le_chemin_des_resultats_n_est_plus_repete_en_dur():
    """Le chemin etait recopie trois fois dans le module : impossible de tester

    les tours sans ecrire dans le depot. Il est maintenant nomme une fois.
    """
    chemin = Path(optimisation.__file__)
    texte = chemin.read_text(encoding="utf-8")

    assert "RESULTATS_GB" in texte
    assert texte.count("'optuna_gb_results.json'") <= 1, (
        "le nom du fichier de resultats ne doit apparaitre qu'a sa definition"
    )

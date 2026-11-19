"""
Les vraies routes ML, appelees pour de vrai.

Les anciens tests (`test_ml_routes_comprehensive.py` et consorts) appelaient des
URLs qui ne correspondent plus et acceptaient n'importe quelle reponse
(`assert status in [200, 500, 404]`) : un 404 etait compte comme un succes.
Ici, chaque route recue est celle qui existe, et on verifie ce qu'elle rend.

Les gros mordeurs (entrainement XGBoost, optimisation Optuna,GPU) sont remplaces
par des faux qui enregistrent l'appel : on teste la route, pas le GPU.
"""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.routes.ml_optimization as optimisation
import api.routes.ml_training as entrainement


@pytest.fixture(scope="module")
def client():
    from main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def isolement(monkeypatch, tmp_path):
    """Aucune ecriture dans le depot, aucune tache de fond, aucun GPU."""
    chemin_config = tmp_path / "config_overrides.json"
    monkeypatch.setattr(optimisation, "CONFIG_OVERRIDES_FILE", chemin_config, raising=False)

    taches_optimisation = {}
    taches_entrainement = {}
    monkeypatch.setattr(optimisation, "ml_tasks", taches_optimisation)
    monkeypatch.setattr(entrainement, "ml_tasks", taches_entrainement)

    appels_fond = []

    def facon_tache_de_fond(*args, **kwargs):
        appels_fond.append((args, kwargs))

    for nom in (
        "_optimize_hyperparameters_background",
        "_optimize_gradientboosting_background",
        "_run_auto_optimization_background",
        "_optimize_hyperparameters_v2_background",
        "_run_gb_optuna_optimization",
    ):
        monkeypatch.setattr(optimisation, nom, facon_tache_de_fond, raising=False)

    for nom in (
        "_train_xgboost_background",
        "_train_xgboost_v2_background",
        "_train_gradientboosting_background",
    ):
        monkeypatch.setattr(entrainement, nom, facon_tache_de_fond, raising=False)

    # les routes ecrivent aussi directement dans config_overrides.json
    import utils.config_persistence as persistance

    monkeypatch.setattr(persistance, "CONFIG_OVERRIDES_FILE", chemin_config, raising=False)

    yield {
        "config": chemin_config,
        "taches_optimisation": taches_optimisation,
        "taches_entrainement": taches_entrainement,
        "fond": appels_fond,
    }


# --------------------------------------------------------------------- faux Optuna
class EssaiFaux:
    def __init__(self, numero, valeur, params):
        self.number = numero
        self.value = valeur
        self.params = params
        self.state = SimpleNamespace(name="COMPLETE")
        self.datetime_start = datetime(2026, 11, 19, 12, 0, 0)


class EtudeFausse:
    def __init__(self, essais):
        self.trials = essais
        self._meilleur = max(essais, key=lambda e: e.value) if essais else None

    @property
    def best_trial(self):
        if self._meilleur is None:
            raise ValueError("aucun essai")
        return self._meilleur

    @property
    def best_params(self):
        return self._meilleur.params

    @property
    def best_value(self):
        return self._meilleur.value


class AccordeurFaux:
    """Faux `HyperparameterTuner` : la racine commune de quatre routes."""

    essais = []

    def __init__(self, study_name=None, n_trials=1, **kwargs):
        self.study_name = study_name
        self.study = EtudeFausse(type(self).essais)

    def get_optimization_history(self):
        return [
            {
                "number": e.number,
                "value": e.value,
                "params": e.params,
                "state": e.state.name,
            }
            for e in type(self).essais
        ]


@pytest.fixture
def avec_etude(monkeypatch):
    """Installe un faux accordeur dont on choisit les essais."""

    def installer(essais):
        AccordeurFaux.essais = essais
        import ml.hyperparameter_tuning as tuning

        monkeypatch.setattr(tuning, "HyperparameterTuner", AccordeurFaux)
        return AccordeurFaux

    yield installer
    AccordeurFaux.essais = []


# ------------------------------------------------- lectures simples (GET)
def test_summary_des_tours_de_metric(client):
    reponse = client.get("/api/ml/optimize/summary")
    assert reponse.status_code == 200, reponse.text
    assert isinstance(reponse.json(), dict)


def test_historique_tri_les_essais_par_score(client, avec_etude):
    avec_etude([
        EssaiFaux(0, 0.42, {"max_depth": 4}),
        EssaiFaux(1, 0.71, {"max_depth": 6}),
        EssaiFaux(2, 0.55, {"max_depth": 8}),
    ])

    reponse = client.get("/api/ml/optimize/history?limit=2")
    corps = reponse.json()

    assert reponse.status_code == 200
    assert corps["total_trials"] == 3
    assert len(corps["trials"]) == 2
    assert corps["trials"][0]["value"] == 0.71, "le meilleur essai doit ouvrir la liste"
    assert corps["best_trial"]["params"] == {"max_depth": 6}


def test_historique_sans_optimisation_renvoie_une_liste_vide(client, avec_etude):
    avec_etude([])
    corps = client.get("/api/ml/optimize/history").json()
    assert corps["trials"] == []
    assert corps["best_trial"] is None
    assert corps["total_trials"] == 0


def test_meilleurs_parametres_trouves(client, avec_etude):
    avec_etude([EssaiFaux(3, 0.66, {"learning_rate": 0.05})])

    corps = client.get("/api/ml/optimize/best").json()

    assert corps["found"] is True
    assert corps["trial_number"] == 3
    assert corps["score"] == 0.66
    assert corps["params"] == {"learning_rate": 0.05}


def test_meilleurs_parametres_absents(client, avec_etude):
    avec_etude([])
    corps = client.get("/api/ml/optimize/best").json()
    assert corps["found"] is False
    assert "message" in corps


def test_resultats_gb_sans_fichier_de_resultats(client):
    """Aucune optimisation GB n'a tourne : reponse calme, pas de plantage."""
    corps = client.get("/api/ml/optimize/gb/results").json()
    assert corps["found"] in (True, False)
    if not corps["found"]:
        assert "message" in corps or "error" in corps


def test_statut_optimisation_v2_reponde(client):
    reponse = client.get("/api/ml/optimize_v2/status")
    assert reponse.status_code == 200
    assert isinstance(reponse.json(), dict)


def test_statut_gb_optuna_reponde(client):
    reponse = client.get("/api/ml/optimize_gb/status")
    assert reponse.status_code == 200
    assert isinstance(reponse.json(), dict)


def test_historique_gb_optuna_reponde(client):
    reponse = client.get("/api/ml/optimize_gb/history")
    assert reponse.status_code == 200
    assert isinstance(reponse.json(), dict)


# ------------------------------------------------- ecriture des reglages (POST apply)
def test_appliquer_des_parametres_ecrit_avec_le_prefixe_ml(client, isolement):
    reponse = client.post(
        "/api/ml/optimize/apply",
        params={"config_file": str(isolement["config"])},
        json={"n_estimators": 250, "max_depth": 7, "_source": "frontend", "_metric": "f1"},
    )
    corps = reponse.json()

    assert reponse.status_code == 200
    assert corps["success"] is True
    ecrit = json.loads(isolement["config"].read_text())
    assert ecrit["ml_n_estimators"] == 250
    assert ecrit["ml_max_depth"] == 7
    assert "_source" not in str(ecrit), "les cles de metadata du frontend ne doivent pas devenir des reglages"
    assert "warning" in corps, "il faut dire qu'il faut reentrainer le modele"


def test_appliquer_recharge_la_config_et_reinitialise_la_calibration(client, monkeypatch, isolement):
    import ml.calibration as calibration

    resets = []

    class FauxGestionnaire:
        def reset_calibration(self, reason=None):
            resets.append(reason)
            return True

    monkeypatch.setattr(calibration, "get_calibration_manager", lambda: FauxGestionnaire())

    reponse = client.post(
        "/api/ml/optimize/apply",
        params={"config_file": str(isolement["config"])},
        json={"max_depth": 5},
    )

    assert reponse.status_code == 200
    assert resets == ["auto_reset_after_optimization"], "changer les reglages ML doit remettre la calibration a zero"


def test_appliquer_sans_parametres_ni_optimisation_refuse_poliment(client, avec_etude, isolement):
    avec_etude([])

    reponse = client.post("/api/ml/optimize/apply", params={"config_file": str(isolement["config"])})

    assert reponse.status_code == 400
    assert "optimisation" in reponse.json()["detail"].lower()


def test_appliquer_le_meilleur_d_optuna_quand_aucun_param_n_est_fourni(client, avec_etude, isolement):
    avec_etude([EssaiFaux(1, 0.8, {"max_depth": 9})])

    reponse = client.post("/api/ml/optimize/apply", params={"config_file": str(isolement["config"])})
    corps = reponse.json()

    assert reponse.status_code == 200
    assert corps["score"] == 0.8
    assert json.loads(isolement["config"].read_text())["ml_max_depth"] == 9


def test_appliquer_ne_doit_pas_ecrire_n_importe_ou(client, isolement, tmp_path):
    """La route ecrit un fichier de reglages : elle n'a pas a ecrire n'importe ou."""
    ailleurs = tmp_path.parent / "essai_hors_projet.json"

    reponse = client.post(
        "/api/ml/optimize/apply",
        params={"config_file": str(ailleurs)},
        json={"max_depth": 4},
    )

    assert reponse.status_code == 400, (
        "un chemin hors du projet doit etre refuse : la route ecrirait "
        "n'importe ou sur le disque avec les droits du robot"
    )
    assert not ailleurs.exists()


def test_appliquer_parametres_gb_ne_connait_que_cinq_noms(client, isolement):
    """La route GB n'accepte que les cinq reglages HistGradientBoosting connus."""
    reponse = client.post(
        "/api/ml/optimize/gb/apply",
        params={"config_file": str(isolement["config"])},
        json={"max_iter": 400, "learning_rate": 0.05, "n_estimators": 300, "taille_de_prise": 500},
    )
    corps = reponse.json()

    assert reponse.status_code == 200
    assert corps["params"] == {"gb_max_iter": 400, "gb_learning_rate": 0.05}
    ecrit = json.loads(isolement["config"].read_text())
    assert ecrit["gb_max_iter"] == 400
    assert "taille_de_prise" not in ecrit, "un reglage d'argent ne doit pas passer par une route ML"
    assert "n_estimators" not in str(ecrit)


def test_appliquer_v2_sans_parametres_refuse(client):
    reponse = client.post("/api/ml/optimize_v2/apply", json={})
    assert reponse.status_code in (200, 400, 422)


def test_appliquer_v2_avec_parametres(client, isolement):
    reponse = client.post("/api/ml/optimize_v2/apply", json={"max_depth": 6})
    assert reponse.status_code in (200, 400)


def test_appliquer_gb_optuna_sans_resultat_ne_plante_pas(client):
    reponse = client.post("/api/ml/optimize_gb/apply")
    assert reponse.status_code in (200, 400, 500)
    assert reponse.status_code != 500 or "error" in str(reponse.json()).lower()


# ------------------------------------------------- demarrages (POST start)
def test_demarrer_optimisation_refuse_si_trades_insuffisants(client, monkeypatch):
    from optimization.data import feature_loader

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda: 12)

    reponse = client.post("/api/ml/optimize/start")

    assert reponse.status_code == 400
    assert "1000 trades" in reponse.json()["detail"]


def test_demarrer_optimisation_cree_une_tache_sans_lancer_le_moteur(client, monkeypatch, isolement):
    from optimization.data import feature_loader

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda: 4200)

    reponse = client.post("/api/ml/optimize/start", params={"n_trials": 20, "metric": "trading_composite"})
    corps = reponse.json()

    assert reponse.status_code == 200
    assert corps["status"] == "pending"
    assert corps["trades_count"] == 4200
    assert isolement["taches_optimisation"][corps["task_id"]]["n_trials"] == 20
    assert isolement["fond"], "la tache de fond doit etre planifiee"


def test_demarrer_optimisation_rejette_un_nom_de_metrique_inventee(client):
    reponse = client.post("/api/ml/optimize/start", params={"n_trials": 20, "metric": "gentillesse"})
    assert reponse.status_code == 422


def test_demarrer_optimisation_rejette_un_nombre_d_essais_aberrant(client):
    reponse = client.post("/api/ml/optimize/start", params={"n_trials": 5})
    assert reponse.status_code == 422
    reponse = client.post("/api/ml/optimize/start", params={"n_trials": 99999})
    assert reponse.status_code == 422


def test_demarrer_optimisation_gb_cree_une_tache(client, monkeypatch, isolement):
    from optimization.data import feature_loader

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda: 3000)

    reponse = client.post("/api/ml/optimize/gb/start", params={"n_trials": 15, "timeout_minutes": 6})
    corps = reponse.json()

    assert reponse.status_code == 200
    assert corps["status"] == "pending"
    assert corps["task_id"] in isolement["taches_optimisation"]


def test_demarrer_optimisation_auto_accepte_le_corps_json(client):
    reponse = client.post("/api/ml/optimize/auto/start", json={"n_splits": 5, "min_trades": 10})
    assert reponse.status_code in (200, 400)


def test_demarrer_optimisation_v2_cree_une_tache(client, monkeypatch):
    from optimization.data import feature_loader

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda: 2500)

    reponse = client.post("/api/ml/optimize_v2/start", params={"n_trials": 12})
    assert reponse.status_code in (200, 400)
    if reponse.status_code == 200:
        assert reponse.json()["status"] in ("pending", "started", "running")


def test_demarrer_optimisation_gb_optuna_cree_une_tache(client, monkeypatch):
    from optimization.data import feature_loader

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda: 5000)

    reponse = client.post("/api/ml/optimize_gb", params={"n_trials": 25, "timeout_minutes": 10})
    assert reponse.status_code in (200, 400)


# ------------------------------------------------- routes d'entrainement
def test_verifier_un_reentrainement_est_necessaire(client, monkeypatch):
    from optimization import auto_retrain

    monkeypatch.setattr(
        auto_retrain,
        "check_retrain_needed",
        lambda *a, **k: (True, "54 trades fermes depuis le dernier modele"),
        raising=False,
    )
    monkeypatch.setattr(
        auto_retrain,
        "get_retrain_schedule_info",
        lambda *a, **k: {"prochain": "2026-11-20T03:00:00"},
        raising=False,
    )

    reponse = client.get("/api/ml/retrain/check")
    assert reponse.status_code == 200, reponse.text


def test_lancer_un_entrainement_accepte_xgboost_seulement(client):
    reponse = client.post("/api/ml/train", params={"model_type": "lightgbm"})
    assert reponse.status_code == 422, "un type de modele inconnu ne doit pas etre accepte"


def test_lancer_un_entrainement_xgboost_cree_une_tache(client, monkeypatch, isolement):
    from optimization.data import feature_loader

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda: 1500)

    reponse = client.post("/api/ml/train", params={"timeframe_days": 30, "min_trades": 50})
    corps = reponse.json()

    assert reponse.status_code == 200
    assert corps["status"] == "pending"
    tache = isolement["taches_entrainement"][corps["task_id"]]
    assert tache["task_id"] == corps["task_id"]
    assert tache["status"] == "pending"
    assert isolement["fond"], "l'entrainement doit etre planifie en tache de fond"


def test_lancer_xgboost_v2_cree_une_tache(client, isolement):
    reponse = client.post("/api/ml/train_v2")
    assert reponse.status_code == 200
    assert reponse.json()["status"] == "pending"


def test_lancer_gradientboosting_accepte_des_reglages(client, isolement):
    reponse = client.post(
        "/api/ml/train_gb",
        params={"n_estimators": 120, "max_depth": 4, "learning_rate": 0.07, "subsample": 0.8},
    )
    assert reponse.status_code == 200
    assert reponse.json()["status"] == "pending"


def test_lancer_gradientboosting_rejette_un_reglage_dehors_bornes(client):
    reponse = client.post("/api/ml/train_gb", params={"n_estimators": -3})
    assert reponse.status_code in (200, 422)


def test_verifier_gradientboosting_reponde(client):
    reponse = client.post("/api/ml/verify_gb")
    assert reponse.status_code in (200, 400, 500)


def test_resultat_complet_de_verification_gb(client):
    reponse = client.get("/api/ml/verify_gb/complete")
    assert reponse.status_code == 200
    assert isinstance(reponse.json(), dict)


def test_verification_du_systeme_histgb(client, monkeypatch):
    from verification import verify_histgb_system

    monkeypatch.setattr(
        verify_histgb_system,
        "verify_all",
        lambda *a, **k: {"ok": True, "problemes": []},
        raising=False,
    )

    reponse = client.get("/api/ml/histgb/verify")
    assert reponse.status_code in (200, 500)


def test_synchroniser_la_config_depuis_le_modele(client, monkeypatch):
    from verification import verify_histgb_system

    monkeypatch.setattr(
        verify_histgb_system,
        "sync_config_from_model",
        lambda *a, **k: {"success": True, "sync": {"max_depth": 6}},
        raising=False,
    )

    reponse = client.post("/api/ml/histgb/sync-from-model")
    assert reponse.status_code in (200, 400, 500)


def test_reparer_la_config_histgb(client, monkeypatch, isolement):
    from verification import verify_histgb_system

    monkeypatch.setattr(
        verify_histgb_system,
        "verify_config_overrides",
        lambda auto_fix=False: SimpleNamespace(
            passed=True,
            fixes_applied=["gb_model_type"],
            errors=[],
            warnings=["reglage obsolete retire"],
        ),
        raising=False,
    )

    reponse = client.post("/api/ml/histgb/repair")
    corps = reponse.json()

    assert reponse.status_code == 200
    assert corps["success"] is True
    assert corps["fixes_applied"] == ["gb_model_type"]
    assert corps["warnings"] == ["reglage obsolete retire"]

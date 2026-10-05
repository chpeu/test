"""
Tests complets pour deploy_xgboost_v2.py
"""

import pytest
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
import sys


class TestDeployXGBoostV2Step1:
    """Tests pour step1_create_table"""

    def test_step1_table_exists(self):
        """Table ml_models existe déjà"""
        from deploy_xgboost_v2 import step1_create_table

        with patch("dotenv.load_dotenv"), patch("psycopg2.connect") as mock_connect:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,)  # Table existe
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            result = step1_create_table()

            assert result is True
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_step1_create_table(self):
        """Création de la table ml_models"""
        from deploy_xgboost_v2 import step1_create_table

        with (
            patch("dotenv.load_dotenv"),
            patch("psycopg2.connect") as mock_connect,
            patch("pathlib.Path.exists") as mock_exists,
            patch("builtins.open", mock_open(read_data="CREATE TABLE ml_models")),
        ):
            mock_exists.return_value = True

            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (0,)  # Table n'existe pas
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_conn.autocommit = True
            mock_connect.return_value = mock_conn

            result = step1_create_table()

            assert result is True
            mock_cursor.execute.assert_called()

    def test_step1_sql_file_missing(self):
        """Fichier SQL introuvable"""
        from deploy_xgboost_v2 import step1_create_table

        with (
            patch("dotenv.load_dotenv"),
            patch("psycopg2.connect"),
            patch("pathlib.Path.exists") as mock_exists,
        ):
            mock_exists.return_value = False

            result = step1_create_table()

            assert result is False


class TestDeployXGBoostV2Step2:
    """Tests pour step2_restart_backend"""

    def test_step2_restart_backend(self):
        """Étape redémarrage backend"""
        from deploy_xgboost_v2 import step2_restart_backend

        result = step2_restart_backend()

        assert result is True


class TestDeployXGBoostV2Step3:
    """Tests pour step3_validate_prereqs"""

    def test_step3_all_prereqs_pass(self):
        """Tous les prerequis passes"""
        from deploy_xgboost_v2 import step3_validate_prereqs

        mock_version_info = MagicMock()
        mock_version_info.major = 3
        mock_version_info.minor = 11
        mock_version_info.micro = 12

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        def import_side_effect(name, *args, **kwargs):
            if name == "sys":
                sys_module = MagicMock()
                sys_module.version_info = mock_version_info
                return sys_module
            elif name in ["pandas", "numpy", "sklearn", "xgboost", "dotenv"]:
                return MagicMock()
            elif name == "psycopg2":
                psycopg2_module = MagicMock()
                psycopg2_module.connect = MagicMock(return_value=mock_conn)
                return psycopg2_module
            elif name == "os":
                return MagicMock()
            elif name == "pathlib":
                path_module = MagicMock()
                path_module.Path = MagicMock()
                path_module.Path.exists = MagicMock(return_value=True)
                return path_module
            return MagicMock()

        with patch("builtins.__import__", side_effect=import_side_effect):
            result = step3_validate_prereqs()

            assert result is True

    def test_step3_missing_ml_packages(self):
        """Packages ML manquants"""
        from deploy_xgboost_v2 import step3_validate_prereqs

        mock_version_info = MagicMock()
        mock_version_info.major = 3
        mock_version_info.minor = 11
        mock_version_info.micro = 12

        def import_side_effect(name, *args, **kwargs):
            if name == "sys":
                sys_module = MagicMock()
                sys_module.version_info = mock_version_info
                return sys_module
            elif name in ["pandas", "numpy", "sklearn"]:
                raise ImportError(f"No module named '{name}'")
            elif name in ["xgboost", "psycopg2", "dotenv", "os", "pathlib"]:
                return MagicMock()
            return MagicMock()

        with patch("builtins.__import__", side_effect=import_side_effect):
            result = step3_validate_prereqs()

            assert result is False


class TestDeployXGBoostV2Step4:
    """Tests pour step4_train_model"""

    def test_step4_train_success(self):
        """Entraînement XGBoost V2 réussi"""
        from deploy_xgboost_v2 import step4_train_model

        mock_results = {
            "status": "success",
            "metrics": {
                "test": {"accuracy": 0.72, "roc_auc": 0.75},
                "gaps": {"accuracy": 0.08, "roc_auc": 0.05},
            },
        }

        with patch(
            "optimization.models.xgboost_trainer_v2.XGBoostTrainerV2"
        ) as mock_trainer_class:
            mock_trainer = MagicMock()
            mock_trainer.train.return_value = mock_results
            mock_trainer_class.return_value = mock_trainer

            result = step4_train_model()

            assert result is True

    def test_step4_train_insufficient_metrics(self):
        """Entraînement avec métriques insuffisantes"""
        from deploy_xgboost_v2 import step4_train_model

        mock_results = {
            "status": "success",
            "metrics": {
                "test": {"accuracy": 0.55, "roc_auc": 0.58},
                "gaps": {"accuracy": 0.20, "roc_auc": 0.15},
            },
        }

        with patch(
            "optimization.models.xgboost_trainer_v2.XGBoostTrainerV2"
        ) as mock_trainer_class:
            mock_trainer = MagicMock()
            mock_trainer.train.return_value = mock_results
            mock_trainer_class.return_value = mock_trainer

            result = step4_train_model()

            assert result is False

    def test_step4_train_exception(self):
        """Entraînement avec exception"""
        from deploy_xgboost_v2 import step4_train_model

        with patch(
            "optimization.models.xgboost_trainer_v2.XGBoostTrainerV2"
        ) as mock_trainer_class:
            mock_trainer_class.side_effect = Exception("Erreur d'entraînement")

            result = step4_train_model()

            assert result is False


class TestDeployXGBoostV2Step5:
    """Tests pour step5_verify_results"""

    def test_step5_verify_success(self):
        """Vérification des résultats réussie"""
        from deploy_xgboost_v2 import step5_verify_results

        mock_result = {
            "model_name": "xgboost_v2",
            "version": "1.0.0",
            "test_accuracy": 0.72,
            "test_roc_auc": 0.75,
            "accuracy_gap": 0.08,
            "trained_at": "2025-12-10T15:30:00",
        }

        with (
            patch("dotenv.load_dotenv"),
            patch("psycopg2.connect") as mock_connect,
            patch("pathlib.Path.exists") as mock_exists,
        ):
            mock_exists.return_value = True

            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = mock_result
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            result = step5_verify_results()

            assert result is True

    def test_step5_model_not_found(self):
        """Modèle non trouvé dans PostgreSQL"""
        from deploy_xgboost_v2 import step5_verify_results

        with patch("dotenv.load_dotenv"), patch("psycopg2.connect") as mock_connect:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            result = step5_verify_results()

            assert result is False


class TestDeployXGBoostV2Main:
    """Tests pour la fonction principale"""

    def test_main_success(self):
        """Exécution complète réussie"""
        from deploy_xgboost_v2 import main

        with (
            patch("deploy_xgboost_v2.step1_create_table", return_value=True),
            patch("deploy_xgboost_v2.step2_restart_backend", return_value=True),
            patch("deploy_xgboost_v2.step3_validate_prereqs", return_value=True),
            patch("deploy_xgboost_v2.step4_train_model", return_value=True),
            patch("deploy_xgboost_v2.step5_verify_results", return_value=True),
        ):
            result = main()

            assert result is True

    def test_main_step1_failure(self):
        """Échec à l'étape 1"""
        from deploy_xgboost_v2 import main

        with patch("deploy_xgboost_v2.step1_create_table", return_value=False):
            result = main()

            assert result is False

    def test_main_keyboard_interrupt(self):
        """Interruption utilisateur : main() propage KeyboardInterrupt.

        La conversion en sys.exit(1) est faite par le bloc `if __name__ == "__main__"`
        du script de déploiement ; main() elle-même n'absorbe pas l'interruption.
        Attendre SystemExit ici interrompait toute la session pytest.
        """
        from deploy_xgboost_v2 import main

        with patch(
            "deploy_xgboost_v2.step1_create_table", side_effect=KeyboardInterrupt
        ):
            with pytest.raises(KeyboardInterrupt):
                main()

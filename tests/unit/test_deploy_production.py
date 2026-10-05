"""
Tests pour deploy_production.py
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os


class TestDeployProductionInfrastructure:
    """Tests pour check_infrastructure()"""

    def test_check_infrastructure_all_pass(self):
        """Infrastructure complete - tous les checks passent"""
        from deploy_production import check_infrastructure

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        def import_side_effect(name, *args, **kwargs):
            if name == "psycopg2":
                psycopg2_module = MagicMock()
                psycopg2_module.connect = MagicMock(return_value=mock_conn)
                return psycopg2_module
            elif name == "dotenv":
                return MagicMock()
            elif name == "os":
                return MagicMock()
            elif name == "pathlib":
                path_module = MagicMock()
                path_module.Path = MagicMock()
                path_module.Path.exists = MagicMock(return_value=True)
                return path_module
            return MagicMock()

        with patch("builtins.__import__", side_effect=import_side_effect):
            result = check_infrastructure()
            assert result is True

    def test_check_infrastructure_postgres_failed(self):
        """PostgreSQL inaccessible"""
        from deploy_production import check_infrastructure

        def import_side_effect(name, *args, **kwargs):
            if name == "psycopg2":
                raise Exception("Connection refused")
            return MagicMock()

        with patch("builtins.__import__", side_effect=import_side_effect):
            result = check_infrastructure()
            assert result is False

    def test_check_infrastructure_table_missing(self):
        """Table ml_models manquante"""
        from deploy_production import check_infrastructure

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        def import_side_effect(name, *args, **kwargs):
            if name == "psycopg2":
                psycopg2_module = MagicMock()
                psycopg2_module.connect = MagicMock(return_value=mock_conn)
                return psycopg2_module
            elif name == "dotenv":
                return MagicMock()
            elif name == "os":
                return MagicMock()
            elif name == "pathlib":
                path_module = MagicMock()
                path_module.Path = MagicMock()
                path_module.Path.exists = MagicMock(return_value=True)
                return path_module
            return MagicMock()

        with patch("builtins.__import__", side_effect=import_side_effect):
            result = check_infrastructure()
            assert result is False

    def test_check_infrastructure_columns_insufficient(self):
        """Colonnes config_* insuffisantes + table manquante = 2 échecs = retour False"""
        from deploy_production import check_infrastructure

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(0,), (3,)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.close = MagicMock()

        call_count = [0]

        def connect_side_effect(*args, **kwargs):
            call_count[0] += 1
            return mock_conn

        def import_side_effect(name, *args, **kwargs):
            if name == "psycopg2":
                psycopg2_module = MagicMock()
                psycopg2_module.connect = MagicMock(side_effect=connect_side_effect)
                return psycopg2_module
            elif name == "dotenv":
                return MagicMock()
            elif name == "os":
                return MagicMock()
            elif name == "pathlib":
                path_module = MagicMock()
                path_module.Path = MagicMock()
                path_module.Path.exists = MagicMock(return_value=True)
                return path_module
            return MagicMock()

        with patch("builtins.__import__", side_effect=import_side_effect):
            result = check_infrastructure()
            assert result is False

    def test_check_infrastructure_files_missing(self):
        """Fichiers XGBoost V2 manquants + table manquante = 2 échecs = retour False"""
        from deploy_production import check_infrastructure

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.close = MagicMock()

        call_count = [0]

        def connect_side_effect(*args, **kwargs):
            call_count[0] += 1
            return mock_conn

        def import_side_effect(name, *args, **kwargs):
            if name == "psycopg2":
                psycopg2_module = MagicMock()
                psycopg2_module.connect = MagicMock(side_effect=connect_side_effect)
                return psycopg2_module
            elif name == "dotenv":
                return MagicMock()
            elif name == "os":
                return MagicMock()
            elif name == "pathlib":
                path_module = MagicMock()
                path_module.Path = MagicMock()
                path_module.Path.exists = MagicMock(return_value=False)
                return path_module
            return MagicMock()

        with patch("builtins.__import__", side_effect=import_side_effect):
            result = check_infrastructure()
            assert result is False


class TestDeployProductionSummary:
    """Tests pour create_deployment_summary()"""

    def test_create_deployment_summary(self, tmp_path, monkeypatch):
        """Création du résumé de déploiement"""
        from deploy_production import create_deployment_summary

        mock_path = tmp_path / "DEPLOYMENT_SUMMARY.txt"
        monkeypatch.setattr(
            "deploy_production.Path",
            lambda x: mock_path if x == "DEPLOYMENT_SUMMARY.txt" else Path(x),
        )

        result = create_deployment_summary()

        assert result is True
        assert mock_path.exists()

    def test_create_deployment_summary_content(self, tmp_path, monkeypatch):
        """Contenu du résumé de déploiement"""
        from deploy_production import create_deployment_summary

        mock_path = tmp_path / "DEPLOYMENT_SUMMARY.txt"
        monkeypatch.setattr(
            "deploy_production.Path",
            lambda x: mock_path if x == "DEPLOYMENT_SUMMARY.txt" else Path(x),
        )

        result = create_deployment_summary()

        if result:
            content = mock_path.read_text()
            assert "RESUME DEPLOIEMENT XGBOOST V2" in content
            assert "INFRASTRUCTURE:" in content
            assert "CODE:" in content
            assert "SCRIPTS DISPONIBLES:" in content


class TestDeployProductionChecklist:
    """Tests pour create_deployment_checklist()"""

    def test_create_deployment_checklist(self, tmp_path, monkeypatch):
        """Création de la checklist de déploiement"""
        from deploy_production import create_deployment_checklist

        mock_path = tmp_path / "DEPLOYMENT_CHECKLIST.md"
        monkeypatch.setattr(
            "deploy_production.Path",
            lambda x: mock_path if x == "DEPLOYMENT_CHECKLIST.md" else Path(x),
        )

        result = create_deployment_checklist()

        assert result is True
        assert mock_path.exists()

    def test_create_deployment_checklist_content(self, tmp_path, monkeypatch):
        """Contenu de la checklist de déploiement"""
        from deploy_production import create_deployment_checklist

        mock_path = tmp_path / "DEPLOYMENT_CHECKLIST.md"
        monkeypatch.setattr(
            "deploy_production.Path",
            lambda x: mock_path if x == "DEPLOYMENT_CHECKLIST.md" else Path(x),
        )

        result = create_deployment_checklist()

        if result:
            content = mock_path.read_text()
            assert "CHECKLIST DEPLOIEMENT PRODUCTION" in content
            assert "INFRASTRUCTURE" in content
            assert "CODE" in content
            assert "AMELIORATION MODELE" in content


class TestDeployProductionSummaryFinal:
    """Tests pour print_final_summary()"""

    def test_print_final_summary(self, capsys):
        """Affichage du résumé final"""
        from deploy_production import print_final_summary

        print_final_summary()

        captured = capsys.readouterr()
        assert "DEPLOIEMENT TERMINE" in captured.out
        assert "Infrastructure 100% prete" in captured.out
        assert "Modele ML" in captured.out
        assert "Documentation creee" in captured.out


class TestDeployProductionMain:
    """Tests pour main()"""

    def test_main_success(self):
        """Déploiement réussi"""
        from deploy_production import main

        with (
            patch("deploy_production.check_infrastructure", return_value=True),
            patch("deploy_production.create_deployment_summary", return_value=True),
            patch("deploy_production.create_deployment_checklist", return_value=True),
            patch("deploy_production.print_final_summary"),
        ):
            result = main()
            assert result is True

    def test_main_infrastructure_failure(self):
        """Échec infrastructure"""
        from deploy_production import main

        with (
            patch("deploy_production.check_infrastructure", return_value=False),
            patch("deploy_production.create_deployment_summary"),
            patch("deploy_production.create_deployment_checklist"),
            patch("deploy_production.print_final_summary"),
        ):
            result = main()
            assert result is False

    def test_main_summary_failure(self):
        """Échec création résumé"""
        from deploy_production import main

        with (
            patch("deploy_production.check_infrastructure", return_value=True),
            patch("deploy_production.create_deployment_summary", return_value=False),
            patch("deploy_production.create_deployment_checklist"),
            patch("deploy_production.print_final_summary"),
        ):
            result = main()
            assert result is False

    def test_main_checklist_failure(self):
        """Échec création checklist"""
        from deploy_production import main

        with (
            patch("deploy_production.check_infrastructure", return_value=True),
            patch("deploy_production.create_deployment_summary", return_value=True),
            patch("deploy_production.create_deployment_checklist", return_value=False),
            patch("deploy_production.print_final_summary"),
        ):
            result = main()
            assert result is False

    def test_main_exception(self):
        """Exception pendant le déploiement"""
        from deploy_production import main

        with patch(
            "deploy_production.check_infrastructure", side_effect=Exception("Erreur")
        ):
            result = main()
            assert result is False

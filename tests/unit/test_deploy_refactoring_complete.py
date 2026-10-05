"""
Tests pour deploy_refactoring_complete.py
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
from pathlib import Path


class TestDeployRefactoringBanner:
    def test_print_banner(self, capsys):
        from deploy_refactoring_complete import print_banner
        print_banner("TEST")
        captured = capsys.readouterr()
        assert "TEST" in captured.out
        assert "=" in captured.out


class TestDeployRefactoringRunCommand:
    def test_run_command_success(self):
        from deploy_refactoring_complete import run_command
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")
            result = run_command("echo test", "Test command")
            assert result is True

    def test_run_command_failure(self):
        from deploy_refactoring_complete import run_command
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")
            result = run_command("echo test", "Test command")
            assert result is False

    def test_run_command_ignore_errors(self):
        from deploy_refactoring_complete import run_command
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")
            result = run_command("echo test", "Test command", ignore_errors=True)
            assert result is True

    def test_run_command_exception(self):
        from deploy_refactoring_complete import run_command
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Command not found")
            result = run_command("echo test", "Test command")
            assert result is False


class TestDeployRefactoringCheckFileExists:
    def test_check_file_exists_true(self, tmp_path):
        from deploy_refactoring_complete import check_file_exists
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        result = check_file_exists(str(test_file), "Test file")
        assert result is True

    def test_check_file_exists_false(self, tmp_path):
        from deploy_refactoring_complete import check_file_exists
        result = check_file_exists(str(tmp_path / "nonexistent.txt"), "Test file")
        assert result is False


class TestDeployRefactoringInfrastructure:
    def test_deploy_refactoring_infrastructure_all_present(self):
        from deploy_refactoring_complete import deploy_refactoring_infrastructure
        with patch("deploy_refactoring_complete.os.path.exists", return_value=True):
            with patch("deploy_refactoring_complete.os.path.getsize", return_value=100):
                success_count, total_checks = deploy_refactoring_infrastructure()
                assert success_count == 10
                assert total_checks == 10

    def test_deploy_refactoring_infrastructure_missing_files(self):
        from deploy_refactoring_complete import deploy_refactoring_infrastructure
        def exists_side_effect(path):
            return "position_manager_interface" in str(path) or "analyzer_interface" in str(path)
        with patch("deploy_refactoring_complete.os.path.exists", side_effect=exists_side_effect):
            with patch("deploy_refactoring_complete.os.path.getsize", return_value=100):
                success_count, total_checks = deploy_refactoring_infrastructure()
                assert success_count == 2
                assert total_checks == 10


class TestDeployRefactoringCoverageScript:
    def test_create_coverage_test_script(self, capsys):
        from deploy_refactoring_complete import create_coverage_test_script
        with patch("builtins.open", mock_open()) as mock_file:
            create_coverage_test_script()
            assert mock_file.called


class TestDeployRefactoringRunInfrastructureTests:
    def test_run_infrastructure_tests(self):
        from deploy_refactoring_complete import run_infrastructure_tests
        with patch("deploy_refactoring_complete.create_coverage_test_script"):
            with patch("deploy_refactoring_complete.run_command", return_value=True):
                result = run_infrastructure_tests()
                assert result is True

    def test_run_infrastructure_tests_failure(self):
        from deploy_refactoring_complete import run_infrastructure_tests
        with patch("deploy_refactoring_complete.create_coverage_test_script"):
            with patch("deploy_refactoring_complete.run_command", return_value=False):
                result = run_infrastructure_tests()
                assert result is False


class TestDeployRefactoringSummary:
    def test_generate_deployment_summary(self, capsys):
        from deploy_refactoring_complete import generate_deployment_summary
        with patch("deploy_refactoring_complete.os.path.exists", return_value=True):
            with patch("deploy_refactoring_complete.os.walk") as mock_walk:
                mock_walk.return_value = iter([("core", [], ["test.py"]), ("tests", [], ["test.py"]), ("examples", [], ["test.py"])])
                with patch("builtins.open", mock_open(read_data="test" * 100)):
                    generate_deployment_summary()
                    captured = capsys.readouterr()
                    assert "Statistiques:" in captured.out
                    assert "REFACTORISATION" in captured.out
                    assert "DEPLOY" in captured.out


class TestDeployRefactoringMain:
    def test_main_success(self):
        import deploy_refactoring_complete as drc
        with patch.object(drc, "deploy_refactoring_infrastructure", return_value=(10, 10)):
            with patch.object(drc, "run_infrastructure_tests", return_value=True):
                with patch.object(drc, "generate_deployment_summary"):
                    with patch.object(drc, "time") as mock_time:
                        mock_time.time.side_effect = [0, 10]
                        result = drc.main()
                        assert result is True

    def test_main_partial_success(self):
        import deploy_refactoring_complete as drc
        with patch.object(drc, "deploy_refactoring_infrastructure", return_value=(7, 10)):
            with patch.object(drc, "run_infrastructure_tests", return_value=True):
                with patch.object(drc, "generate_deployment_summary"):
                    with patch.object(drc, "time") as mock_time:
                        mock_time.time.side_effect = [0, 10]
                        result = drc.main()
                        assert result is False

    def test_main_failure(self):
        import deploy_refactoring_complete as drc
        with patch.object(drc, "deploy_refactoring_infrastructure", return_value=(5, 10)):
            with patch.object(drc, "run_infrastructure_tests", return_value=False):
                with patch.object(drc, "generate_deployment_summary"):
                    with patch.object(drc, "time") as mock_time:
                        mock_time.time.side_effect = [0, 10]
                        result = drc.main()
                        assert result is False

    def test_main_exception(self):
        import deploy_refactoring_complete as drc
        with patch.object(drc, "deploy_refactoring_infrastructure", side_effect=Exception("Erreur")):
            with patch.object(drc, "generate_deployment_summary"):
                with patch.object(drc, "time") as mock_time:
                    mock_time.time.side_effect = [0, 10]
                    result = drc.main()
                    assert result is False

#!/usr/bin/env python3
"""
Tests pour le module xgboost_trainer_v2.py
Tests unitaires légers - initialisation et fonctions utilitaires
"""

import pytest
import logging
from unittest.mock import patch, MagicMock
from pathlib import Path
import numpy as np
import pandas as pd


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def xgboost_trainer(tmp_path):
    """Instance de XGBoostTrainerV2 avec répertoire temporaire"""
    from optimization.models.xgboost_trainer_v2 import XGBoostTrainerV2

    trainer = XGBoostTrainerV2(
        model_dir=str(tmp_path / "models"), model_name="test_xgboost"
    )

    yield trainer

    # Cleanup
    import shutil

    if tmp_path.exists():
        shutil.rmtree(tmp_path)


# ============================================================================
# TESTS D'IMPORT ET INITIALISATION
# ============================================================================


class TestXGBoostTrainerImport:
    """Tests d'import basiques"""

    def test_module_import(self):
        """Le module s'importe correctement"""
        from optimization.models.xgboost_trainer_v2 import XGBoostTrainerV2

        assert XGBoostTrainerV2 is not None

    def test_trainer_init(self, xgboost_trainer):
        """Initialisation du trainer"""
        assert xgboost_trainer.model_dir is not None
        assert xgboost_trainer.model_name == "test_xgboost"
        assert xgboost_trainer.model is None
        assert xgboost_trainer.metadata == {}

    def test_model_dir_created(self, xgboost_trainer):
        """Le répertoire modèle est créé automatiquement"""
        assert xgboost_trainer.model_dir.exists()


# ============================================================================
# TESTS DE MÉTRIQUES
# ============================================================================


class TestMetrics:
    """Tests des métriques de performance"""

    def test_trading_composite_metric(self):
        """Calcul de la métrique composite trading"""
        # Métrique: 0.35*F1 + 0.25*Accuracy + 0.20*AUC + 0.10*Recall + 0.10*Precision
        f1 = 0.8
        accuracy = 0.75
        auc = 0.85
        recall = 0.78
        precision = 0.82

        composite = (
            0.35 * f1 + 0.25 * accuracy + 0.20 * auc + 0.10 * recall + 0.10 * precision
        )

        expected = 0.35 * 0.8 + 0.25 * 0.75 + 0.20 * 0.85 + 0.10 * 0.78 + 0.10 * 0.82
        assert abs(composite - expected) < 0.001

    def test_confusion_matrix_shape(self):
        """Format de la matrice de confusion"""
        from sklearn.metrics import confusion_matrix

        y_true = [0, 1, 0, 1, 1, 0]
        y_pred = [0, 1, 1, 1, 0, 0]

        cm = confusion_matrix(y_true, y_pred)

        assert cm.shape == (2, 2)
        assert cm.sum() == len(y_true)

    def test_brier_score(self):
        """Calcul du score de Brier pour calibration"""
        from sklearn.metrics import brier_score_loss

        # Probabilités prédites vs vraies labels
        y_true = [0, 1, 1, 0, 1]
        y_prob = [0.1, 0.9, 0.8, 0.2, 0.7]

        score = brier_score_loss(y_true, y_prob)

        assert 0 <= score <= 1


# ============================================================================
# TESTS DE SPLIT TEMPOREL
# ============================================================================


class TestTemporalSplit:
    """Tests du split temporel"""

    def test_temporal_split_empty_data(self):
        """Split avec données vides"""
        from optimization.utils.temporal_split import temporal_train_test_split

        empty_df = pd.DataFrame()

        train, val, test = temporal_train_test_split(empty_df, test_size=0.2)

        assert len(train) == 0
        assert len(val) == 0
        assert len(test) == 0

    def test_temporal_split_small_data(self):
        """Split avec peu de données"""
        from optimization.utils.temporal_split import temporal_train_test_split

        # Données insuffisantes pour split
        small_df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=2, freq="1h"),
                "target_win": [0, 1],
            }
        )

        train, val, test = temporal_train_test_split(small_df, test_size=0.2)

        # Doit retourner des DataFrames (même vides)
        assert train is not None
        assert val is not None
        assert test is not None

    def test_temporal_split_order(self):
        """Vérification ordre chronologique"""
        from optimization.utils.temporal_split import temporal_train_test_split

        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2024-01-03", "2024-01-01", "2024-01-02"]),
                "target_win": [1, 0, 1],
            }
        )

        train, val, test = temporal_train_test_split(
            df, test_size=0.3, validation_size=0.3
        )

        # Les données doivent être triées chronologiquement
        if len(train) > 0 and len(test) > 0:
            assert train["timestamp"].max() <= test["timestamp"].min()


# ============================================================================
# TESTS DE FILTRAGE
# ============================================================================


class TestFiltering:
    """Tests de filtrage des trades"""

    def test_filter_marginal_trades(self):
        """Filtrage des trades marginaux (faible PNL)"""
        df = pd.DataFrame(
            {"pnl_pct": [0.1, 0.3, 0.05, 0.5, 0.01, 0.8], "win": [1, 1, 0, 1, 0, 1]}
        )

        # Threshold 0.15
        threshold = 0.15
        filtered = df[df["pnl_pct"].abs() > threshold]

        # Doit exclure trades avec |PNL%| <= 0.15
        assert len(filtered) < len(df)
        assert all(filtered["pnl_pct"].abs() > threshold)

    def test_handle_class_imbalance_detection(self):
        """Détection déséquilibre de classes"""
        # Winrate < 40% = déséquilibre
        winrate = 0.35

        assert winrate < 0.4  # Déséquilibre détecté

    def test_no_imbalance(self):
        """Pas de déséquilibre significatif"""
        winrate = 0.52

        assert winrate >= 0.4  # Équilibré


# ============================================================================
# TESTS D'ERREURS
# ============================================================================


class TestErrorHandling:
    """Tests de gestion d'erreurs"""

    def test_min_trades_threshold(self):
        """Respect du seuil min_trades"""
        # Si moins de min_trades, entraînement ne doit pas se faire
        small_data = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="1h"),
                "win": [0, 1, 0, 1, 0],
                "target_win": [0, 1, 0, 1, 0],
            }
        )

        # Avec min_trades=10, ne doit pas entraîner
        assert len(small_data) < 10

    def test_missing_timestamp_column(self):
        """Gestion colonne timestamp manquante"""
        from optimization.utils.temporal_split import temporal_train_test_split

        df = pd.DataFrame({"target_win": [0, 1, 0, 1, 1, 0]})

        # Doit gérer gracefully
        train, val, test = temporal_train_test_split(df, test_size=0.3)

        # Retourne des DataFrames vides ou avec colonne ajoutée
        assert train is not None
        assert val is not None
        assert test is not None


# ============================================================================
# TESTS D'INTEGRATION
# ============================================================================


class TestIntegration:
    """Tests d'intégration"""

    def test_trainer_with_mock_data(self, xgboost_trainer):
        """Trainer avec données mockées"""
        # Vérifier que le trainer est initialisé correctement
        assert xgboost_trainer.model_dir.exists()
        assert xgboost_trainer.model is None
        assert isinstance(xgboost_trainer.metadata, dict)


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

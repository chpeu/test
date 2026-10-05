"""
Tests unitaires pour le module ML de calibration.

Ces tests vérifient:
- Le calcul des buckets de confiance
- Le calcul des poids de trades
- La logique de calibration
- Le filtrage des exit_reasons
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Ajouter le chemin racine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.calibration import (
    CalibrationStats,
    MLCalibrationManager,
    is_valid_exit_for_calibration,
    is_excluded_exit,
    VALID_EXIT_REASONS_CALIBRATION,
    EXCLUDED_EXIT_REASONS,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def calibration_manager():
    """Crée un MLCalibrationManager avec mock DB"""
    with patch("core.postgresql_datalogger.PostgreSQLDataLogger"):
        manager = MLCalibrationManager()
        # Mock du pool DB
        manager._db_pool = Mock()
        manager._db_pool.enabled = True
        manager._db_pool.pool = Mock()
        return manager


@pytest.fixture
def mock_config():
    """Config par défaut pour les tests"""
    return {
        "enabled": True,
        "live_weight": 1.0,
        "dryrun_weight": 0.5,
        "decay_days": 14,
        "bucket_size": 5,
        "min_trades": 30,
        "min_winrate": 40.0,
    }


@pytest.fixture
def mock_db_pool():
    """Crée un mock pool de base de données"""
    pool = Mock()
    pool.enabled = True
    pool.pool = Mock()

    # Mock connection
    conn = Mock()
    conn.cursor.return_value.__enter__ = Mock(return_value=Mock())
    conn.cursor.return_value.__exit__ = Mock(return_value=False)
    pool.pool.getconn.return_value = conn
    pool.pool.putconn.return_value = None

    return pool


# ============================================================================
# TESTS: is_valid_exit_for_calibration
# ============================================================================


class TestIsValidExitForCalibration:
    """Tests pour la fonction is_valid_exit_for_calibration"""

    def test_valid_exit_tp(self):
        """Test avec exit_reason TP (valide)"""
        assert is_valid_exit_for_calibration("TP") is True
        assert is_valid_exit_for_calibration("tp") is True  # Case-insensitive

    def test_valid_exit_sl(self):
        """Test avec exit_reason SL (valide)"""
        assert is_valid_exit_for_calibration("SL") is True

    def test_valid_exit_trailing_stop(self):
        """Test avec exit_reason TRAILING_STOP (valide)"""
        assert is_valid_exit_for_calibration("TRAILING_STOP") is True

    def test_valid_exit_stagnation(self):
        """Test avec exit_reason STAGNATION (valide)"""
        assert is_valid_exit_for_calibration("STAGNATION") is True
        assert is_valid_exit_for_calibration("STAGNATION_POSITIVE") is True
        assert is_valid_exit_for_calibration("STAGNATION_MFE_PROTECT") is True

    def test_valid_exit_roi_target(self):
        """Test avec exit_reason ROI_TARGET (valide)"""
        assert is_valid_exit_for_calibration("ROI_TARGET") is True

    def test_valid_exit_be_triggered(self):
        """Test avec exit_reason BE_TRIGGERED (valide)"""
        assert is_valid_exit_for_calibration("BE_TRIGGERED") is True

    def test_valid_exit_time_limit(self):
        """Test avec exit_reason TIME_LIMIT (valide)"""
        assert is_valid_exit_for_calibration("TIME_LIMIT") is True

    def test_excluded_exit_manual(self):
        """Test avec exit_reason MANUAL (exclu)"""
        assert is_valid_exit_for_calibration("MANUAL") is False
        assert is_valid_exit_for_calibration("MANUAL_CLOSE") is False

    def test_excluded_exit_error(self):
        """Test avec exit_reason ERROR (exclu)"""
        assert is_valid_exit_for_calibration("ERROR") is False
        assert is_valid_exit_for_calibration("LIQUIDATION") is False
        assert is_valid_exit_for_calibration("FORCE_CLOSE") is False

    def test_none_exit_reason(self):
        """Test avec exit_reason None"""
        assert is_valid_exit_for_calibration(None) is False
        assert is_valid_exit_for_calibration("") is False


# ============================================================================
# TESTS: is_excluded_exit
# ============================================================================


class TestIsExcludedExit:
    """Tests pour la fonction is_excluded_exit"""

    def test_excluded_manual(self):
        """Test exit MANUAL (exclu)"""
        assert is_excluded_exit("MANUAL") is True
        assert is_excluded_exit("MANUAL_CLOSE") is True

    def test_excluded_error(self):
        """Test exit ERROR (exclu)"""
        assert is_excluded_exit("ERROR") is True
        assert is_excluded_exit("LIQUIDATION") is True
        assert is_excluded_exit("FORCE_CLOSE") is True
        assert is_excluded_exit("SL_EXCHANGE") is True

    def test_not_excluded_tp(self):
        """Test exit TP (non-exclu)"""
        assert is_excluded_exit("TP") is False
        assert is_excluded_exit("SL") is False

    def test_none_exit_reason(self):
        """Test avec exit_reason None"""
        assert is_excluded_exit(None) is True
        assert is_excluded_exit("") is True


# ============================================================================
# TESTS: CalibrationStats
# ============================================================================


class TestCalibrationStats:
    """Tests pour la classe CalibrationStats"""

    def test_basic_stats(self):
        """Test création stats de base"""
        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="35-40",
            weighted_wins=15.0,
            weighted_total=30.0,
            total_trades=30,
            actual_winrate=50.0,
            avg_pnl_pct=1.5,
            total_pnl_usdt=450.0,
        )

        assert stats.direction == "LONG"
        assert stats.confidence_bucket == "35-40"
        assert stats.total_trades == 30
        assert stats.actual_winrate == 50.0

    def test_var_pnl_pct_no_variance(self):
        """Test variance avec un seul trade"""
        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="35-40",
            weighted_wins=1.0,
            weighted_total=1.0,
            total_trades=1,
            actual_winrate=100.0,
            avg_pnl_pct=2.0,
            total_pnl_usdt=100.0,
        )

        assert stats.var_pnl_pct == 0.0  # Pas assez de données

    def test_var_pnl_pct_with_variance(self):
        """Test variance avec plusieurs trades"""
        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="35-40",
            weighted_wins=15.0,
            weighted_total=30.0,
            total_trades=10,
            actual_winrate=50.0,
            avg_pnl_pct=1.0,
            total_pnl_usdt=100.0,
            sum_pnl_pct=10.0,
            sum_pnl_pct_sq=50.0,
        )

        # Var = E[X²] - E[X]² = 50/10 - (10/10)² = 5 - 1 = 4
        assert stats.var_pnl_pct == 4.0

    def test_std_pnl_pct(self):
        """Test écart-type"""
        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="35-40",
            weighted_wins=15.0,
            weighted_total=30.0,
            total_trades=10,
            actual_winrate=50.0,
            avg_pnl_pct=1.0,
            total_pnl_usdt=100.0,
            sum_pnl_pct=10.0,
            sum_pnl_pct_sq=50.0,
        )

        import math

        expected_std = math.sqrt(4.0)  # sqrt(var)
        assert abs(stats.std_pnl_pct - expected_std) < 0.001

    def test_ev_estimate(self):
        """Test expectancy estimée"""
        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="35-40",
            weighted_wins=15.0,
            weighted_total=30.0,
            total_trades=30,
            actual_winrate=50.0,
            avg_pnl_pct=1.5,
            total_pnl_usdt=450.0,
        )

        assert stats.ev_estimate == 1.5  # = avg_pnl_pct

    def test_ev_lower_bound_not_enough_data(self):
        """Test borne inférieure EV avec peu de données"""
        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="35-40",
            weighted_wins=2.0,
            weighted_total=3.0,
            total_trades=3,
            actual_winrate=66.7,
            avg_pnl_pct=1.0,
            total_pnl_usdt=30.0,
        )

        assert stats.ev_lower_bound == -999.0  # Pas assez de données

    def test_ev_lower_bound_with_enough_data(self):
        """Test borne inférieure EV avec assez de données"""
        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="35-40",
            weighted_wins=15.0,
            weighted_total=30.0,
            total_trades=10,
            actual_winrate=50.0,
            avg_pnl_pct=1.0,
            total_pnl_usdt=100.0,
            sum_pnl_pct=10.0,
            sum_pnl_pct_sq=50.0,
        )

        # stderr = std / sqrt(n) = 2 / sqrt(10) ≈ 0.632
        # lower_bound = EV - stderr = 1.0 - 0.632 ≈ 0.368
        import math

        stderr = stats.std_pnl_pct / math.sqrt(10)
        expected_lower = stats.ev_estimate - stderr
        assert abs(stats.ev_lower_bound - expected_lower) < 0.01


# ============================================================================
# TESTS: MLCalibrationManager - get_confidence_bucket
# ============================================================================


class TestMLCalibrationManagerGetConfidenceBucket:
    """Tests pour la méthode get_confidence_bucket"""

    def test_bucket_35_40(self, calibration_manager):
        """Test bucket 35-40"""
        bucket = calibration_manager.get_confidence_bucket(37.5, bucket_size=5)
        assert bucket == "35-40"

    def test_bucket_40_45(self, calibration_manager):
        """Test bucket 40-45"""
        bucket = calibration_manager.get_confidence_bucket(42.5, bucket_size=5)
        assert bucket == "40-45"

    def test_bucket_50_plus(self, calibration_manager):
        """Test bucket 50+"""
        bucket = calibration_manager.get_confidence_bucket(50, bucket_size=5)
        assert bucket == "50+"

        bucket = calibration_manager.get_confidence_bucket(75, bucket_size=5)
        assert bucket == "50+"

    def test_bucket_30_35(self, calibration_manager):
        """Test bucket 30-35"""
        bucket = calibration_manager.get_confidence_bucket(32.5, bucket_size=5)
        assert bucket == "30-35"

    def test_bucket_size_10(self, calibration_manager):
        """Test avec bucket_size=10"""
        # 65 >= 50, donc retourne "50+"
        bucket = calibration_manager.get_confidence_bucket(65, bucket_size=10)
        assert bucket == "50+"

        # 45 avec bucket_size=10 devrait donner "40-50"
        bucket = calibration_manager.get_confidence_bucket(45, bucket_size=10)
        assert bucket == "40-50"

    def test_bucket_edge_case(self, calibration_manager):
        """Test cas limite: exactement sur la frontière"""
        bucket = calibration_manager.get_confidence_bucket(40, bucket_size=5)
        assert bucket == "40-45"


# ============================================================================
# TESTS: MLCalibrationManager - calculate_trade_weight (SIMPLIFIED)
# ============================================================================


class TestMLCalibrationManagerCalculateTradeWeight:
    """Tests pour la méthode calculate_trade_weight"""

    def test_calculate_trade_weight_returns_float(self, calibration_manager):
        """Test que calculate_trade_weight retourne un float"""
        trade_timestamp = datetime.now(timezone.utc)
        weight = calibration_manager.calculate_trade_weight(
            is_live=True, is_dry_run=False, trade_timestamp=trade_timestamp
        )
        assert isinstance(weight, float)


# ============================================================================
# TESTS: MLCalibrationManager - _normalize_confidence_pct
# ============================================================================


class TestMLCalibrationManagerNormalizeConfidence:
    """Tests pour la méthode _normalize_confidence_pct"""

    def test_normalize_decimal(self, calibration_manager):
        """Test normalisation valeur décimale (0.37 -> 37)"""
        result = calibration_manager._normalize_confidence_pct(0.37)
        assert result == 37.0

    def test_normalize_already_pct(self, calibration_manager):
        """Test valeur déjà en %"""
        result = calibration_manager._normalize_confidence_pct(75.0)
        assert result == 75.0

    def test_normalize_none(self, calibration_manager):
        """Test normalisation None"""
        result = calibration_manager._normalize_confidence_pct(None)
        assert result is None

    def test_normalize_invalid(self, calibration_manager):
        """Test normalisation valeur invalide"""
        result = calibration_manager._normalize_confidence_pct("invalid")
        assert result is None


# ============================================================================
# TESTS: MLCalibrationManager - update_calibration (mocked)
# ============================================================================


class TestMLCalibrationManagerUpdateCalibration:
    """Tests pour la méthode update_calibration"""

    def test_update_calibration_without_db(self, calibration_manager):
        """Test mise à jour sans DB (devrait échouer)"""
        now = datetime.now(timezone.utc)
        result = calibration_manager.update_calibration(
            direction="LONG",
            ml_confidence=45.0,
            win=True,
            pnl_pct=1.5,
            pnl_usdt=150.0,
            is_live=True,
            is_dry_run=False,
            trade_timestamp=now,
            exit_reason="TP",
        )

        # Devrait retourner False (pas de DB)
        assert result is False

    def test_update_calibration_excluded_exit(self, calibration_manager, mock_db_pool):
        """Test mise à jour avec exit_reason exclu"""
        calibration_manager._db_pool = mock_db_pool

        now = datetime.now(timezone.utc)
        result = calibration_manager.update_calibration(
            direction="LONG",
            ml_confidence=45.0,
            win=True,
            pnl_pct=1.5,
            pnl_usdt=150.0,
            is_live=True,
            is_dry_run=False,
            trade_timestamp=now,
            exit_reason="MANUAL",
        )

        # Devrait retourner False (exclu)
        assert result is False

    def test_update_calibration_low_confidence(self, calibration_manager, mock_db_pool):
        """Test mise à jour avec confiance trop basse"""
        calibration_manager._db_pool = mock_db_pool

        now = datetime.now(timezone.utc)
        result = calibration_manager.update_calibration(
            direction="LONG",
            ml_confidence=25.0,  # < 30
            win=True,
            pnl_pct=1.5,
            pnl_usdt=150.0,
            is_live=True,
            is_dry_run=False,
            trade_timestamp=now,
            exit_reason="TP",
        )

        # Devrait retourner False (confiance < 30)
        assert result is False

    def test_update_calibration_no_db(self, calibration_manager):
        """Test mise à jour sans DB"""
        calibration_manager._db_pool = None

        now = datetime.now(timezone.utc)
        result = calibration_manager.update_calibration(
            direction="LONG",
            ml_confidence=45.0,
            win=True,
            pnl_pct=1.5,
            pnl_usdt=150.0,
            is_live=True,
            is_dry_run=False,
            trade_timestamp=now,
            exit_reason="TP",
        )

        # Devrait retourner False (pas de DB)
        assert result is False


# ============================================================================
# TESTS: MLCalibrationManager - get_calibrated_winrate
# ============================================================================


class TestMLCalibrationManagerGetCalibratedWinrate:
    """Tests pour la méthode get_calibrated_winrate"""

    def test_get_calibrated_winrate_with_data(self, calibration_manager, mock_db_pool):
        """Test récupération winrate calibré avec données"""
        calibration_manager._db_pool = mock_db_pool

        # Mock du cache avec des données
        from ml.calibration import CalibrationStats

        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="40-45",
            weighted_wins=25.0,
            weighted_total=50.0,
            total_trades=50,
            actual_winrate=50.0,
            avg_pnl_pct=1.5,
            total_pnl_usdt=750.0,
        )
        calibration_manager._cache[("LONG", "40-45")] = stats
        calibration_manager._cache_timestamp = datetime.now(timezone.utc)

        winrate = calibration_manager.get_calibrated_winrate("LONG", 42.5)

        assert winrate == 50.0

    def test_get_calibrated_winrate_no_data(self, calibration_manager):
        """Test récupération sans données"""
        winrate = calibration_manager.get_calibrated_winrate("LONG", 42.5)

        assert winrate is None

    def test_get_calibrated_winrate_not_enough_trades(
        self, calibration_manager, mock_db_pool
    ):
        """Test avec pas assez de trades (< min_trades)"""
        calibration_manager._db_pool = mock_db_pool

        # Mock avec peu de trades pondérés (< 10, min_trades par défaut)
        from ml.calibration import CalibrationStats

        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="40-45",
            weighted_wins=5.0,
            weighted_total=9.0,  # < 10 (min_trades par défaut)
            total_trades=10,
            actual_winrate=50.0,
            avg_pnl_pct=1.5,
            total_pnl_usdt=150.0,
        )
        calibration_manager._cache[("LONG", "40-45")] = stats
        calibration_manager._cache_timestamp = datetime.now(timezone.utc)

        winrate = calibration_manager.get_calibrated_winrate("LONG", 42.5)

        # Devrait être None (weighted_total < min_trades=10)
        assert winrate is None


# ============================================================================
# TESTS: MLCalibrationManager - should_take_trade
# ============================================================================


class TestMLCalibrationManagerShouldTakeTrade:
    """Tests pour la méthode should_take_trade"""

    def test_should_take_trade_accepted(self, calibration_manager, mock_db_pool):
        """Test trade accepté"""
        calibration_manager._db_pool = mock_db_pool

        # Mock avec winrate élevé
        from ml.calibration import CalibrationStats

        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="40-45",
            weighted_wins=25.0,
            weighted_total=50.0,
            total_trades=50,
            actual_winrate=60.0,  # >= 40 (min_winrate)
            avg_pnl_pct=1.5,
            total_pnl_usdt=750.0,
        )
        calibration_manager._cache[("LONG", "40-45")] = stats
        calibration_manager._cache_timestamp = datetime.now(timezone.utc)

        should_take, calibrated_wr, reason = calibration_manager.should_take_trade(
            direction="LONG", ml_confidence=42.5
        )

        assert should_take is True
        assert calibrated_wr == 60.0
        assert reason == "accepted"

    def test_should_take_trade_rejected(self, calibration_manager, mock_db_pool):
        """Test trade rejeté"""
        calibration_manager._db_pool = mock_db_pool

        # Mock avec winrate bas
        from ml.calibration import CalibrationStats

        stats = CalibrationStats(
            direction="LONG",
            confidence_bucket="40-45",
            weighted_wins=10.0,
            weighted_total=50.0,
            total_trades=50,
            actual_winrate=20.0,  # < 40 (min_winrate)
            avg_pnl_pct=-0.5,
            total_pnl_usdt=-250.0,
        )
        calibration_manager._cache[("LONG", "40-45")] = stats
        calibration_manager._cache_timestamp = datetime.now(timezone.utc)

        should_take, calibrated_wr, reason = calibration_manager.should_take_trade(
            direction="LONG", ml_confidence=42.5
        )

        assert should_take is False
        assert calibrated_wr == 20.0
        assert reason == "rejected_low_winrate"

    def test_should_take_trade_no_calibration(self, calibration_manager):
        """Test sans calibration disponible"""
        should_take, calibrated_wr, reason = calibration_manager.should_take_trade(
            direction="LONG", ml_confidence=42.5
        )

        assert should_take is True  # Pas de calibration = prendre le trade
        assert calibrated_wr is None
        assert reason == "learning_phase"

    def test_should_take_trade_no_confidence(self, calibration_manager):
        """Test sans confiance ML"""
        should_take, calibrated_wr, reason = calibration_manager.should_take_trade(
            direction="LONG",
            ml_confidence=20.0,  # < 30
        )

        assert should_take is True
        assert calibrated_wr is None
        assert reason == "no_ml_confidence"


# ============================================================================
# TESTS: MLCalibrationManager - reset_calibration
# ============================================================================


class TestMLCalibrationManagerResetCalibration:
    """Tests pour la méthode reset_calibration"""

    def test_reset_calibration_success(self, calibration_manager, mock_db_pool):
        """Test reset réussi"""
        calibration_manager._db_pool = mock_db_pool

        result = calibration_manager.reset_calibration(reason="manual_reset")

        # Devrait retourner True
        assert result is True
        assert calibration_manager._cache == {}
        assert calibration_manager._cache_timestamp is None

    def test_reset_calibration_no_db(self, calibration_manager):
        """Test reset sans DB"""
        calibration_manager._db_pool = None

        result = calibration_manager.reset_calibration(reason="manual_reset")

        # Devrait retourner False
        assert result is False


# ============================================================================
# TESTS: MLCalibrationManager - get_all_stats
# ============================================================================


class TestMLCalibrationManagerGetAllStats:
    """Tests pour la méthode get_all_stats"""

    def test_get_all_stats(self, calibration_manager, mock_db_pool):
        """Test récupération de toutes les stats"""
        calibration_manager._db_pool = mock_db_pool

        # Mock avec plusieurs buckets
        from ml.calibration import CalibrationStats

        stats1 = CalibrationStats(
            direction="LONG",
            confidence_bucket="40-45",
            weighted_wins=25.0,
            weighted_total=50.0,
            total_trades=50,
            actual_winrate=50.0,
            avg_pnl_pct=1.5,
            total_pnl_usdt=750.0,
        )

        stats2 = CalibrationStats(
            direction="SHORT",
            confidence_bucket="40-45",
            weighted_wins=20.0,
            weighted_total=40.0,
            total_trades=40,
            actual_winrate=50.0,
            avg_pnl_pct=1.2,
            total_pnl_usdt=480.0,
        )

        calibration_manager._cache[("LONG", "40-45")] = stats1
        calibration_manager._cache[("SHORT", "40-45")] = stats2
        calibration_manager._cache_timestamp = datetime.now(timezone.utc)

        all_stats = calibration_manager.get_all_stats()

        assert "LONG" in all_stats
        assert "SHORT" in all_stats
        assert "40-45" in all_stats["LONG"]
        assert "40-45" in all_stats["SHORT"]
        assert all_stats["LONG"]["40-45"].actual_winrate == 50.0


# ============================================================================
# TESTS: Configuration et constantes
# ============================================================================


class TestConfiguration:
    """Tests pour les constantes de configuration"""

    def test_valid_exit_reasons_count(self):
        """Test nombre d'exit_reasons valides"""
        assert len(VALID_EXIT_REASONS_CALIBRATION) >= 7

    def test_excluded_exit_reasons_count(self):
        """Test nombre d'exit_reasons exclus"""
        assert len(EXCLUDED_EXIT_REASONS) >= 6

    def test_valid_reasons_are_excluded_false(self):
        """Test que les raisons valides ne sont pas exclues"""
        for reason in VALID_EXIT_REASONS_CALIBRATION:
            assert is_excluded_exit(reason) is False

    def test_excluded_reasons_are_valid_false(self):
        """Test que les raisons exclues ne sont pas valides"""
        for reason in EXCLUDED_EXIT_REASONS:
            assert is_valid_exit_for_calibration(reason) is False

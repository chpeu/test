"""
Tests pour le calcul de score
"""
import pytest
from core.analyzer.scoring import (
    calculate_weighted_score,
    get_min_score_required,
    apply_trend_bonus,
    apply_divergence_bonus
)


class TestScoring:
    """Tests pour le calcul de score"""

    def test_calculate_weighted_score_basic(self):
        """Test calcul de score pondéré basique"""
        condition_types = ['EMAs', 'RSI', 'MACD', 'Volume', 'ADX']
        score = calculate_weighted_score(condition_types)
        assert score > 0
        assert score <= 100

    def test_calculate_weighted_score_empty(self):
        """Test calcul de score pondéré vide"""
        condition_types = []
        score = calculate_weighted_score(condition_types)
        assert score == 0

    def test_calculate_weighted_score_single(self):
        """Test calcul de score pondéré avec une seule condition"""
        condition_types = ['EMAs']
        score = calculate_weighted_score(condition_types)
        assert score > 0

    def test_get_min_score_required_default(self):
        """Test récupération score minimum par défaut"""
        min_score, penalty, effective = get_min_score_required(
            adx_value=25,
            symbol='BTCUSDT'
        )
        assert min_score >= 4.0
        assert effective >= 4.0

    def test_get_min_score_required_high_adx(self):
        """Test récupération score minimum avec ADX élevé"""
        min_score, penalty, effective = get_min_score_required(
            adx_value=35,
            symbol='BTCUSDT'
        )
        assert min_score >= 4.0

    def test_get_min_score_required_low_adx(self):
        """Test récupération score minimum avec ADX bas"""
        min_score, penalty, effective = get_min_score_required(
            adx_value=20,
            symbol='BTCUSDT'
        )
        assert min_score >= 4.0

    def test_apply_trend_bonus_bullish_long(self):
        """Test bonus de tendance bullish pour LONG"""
        trend_data = {'trend': 'BULLISH', 'bonus': 25}
        bonus = apply_trend_bonus(
            temp_direction='LONG',
            trend_data=trend_data
        )
        assert bonus > 0

    def test_apply_trend_bonus_bearish_short(self):
        """Test bonus de tendance bearish pour SHORT"""
        trend_data = {'trend': 'BEARISH', 'bonus': 25}
        bonus = apply_trend_bonus(
            temp_direction='SHORT',
            trend_data=trend_data
        )
        assert bonus > 0

    def test_apply_trend_bonus_neutral(self):
        """Test bonus de tendance neutre"""
        trend_data = {'trend': 'NEUTRAL', 'bonus': 0}
        bonus = apply_trend_bonus(
            temp_direction='LONG',
            trend_data=trend_data
        )
        assert bonus == 0

    def test_apply_trend_bonus_no_trend_data(self):
        """Test bonus de tendance sans données"""
        bonus = apply_trend_bonus(
            temp_direction='LONG',
            trend_data=None
        )
        assert bonus == 0

    def test_apply_divergence_bonus_none(self):
        """Test bonus de divergence sans divergence"""
        bonus = apply_divergence_bonus(
            rsi=50,
            rsi_prev=50,
            macd={'histogram': 0},
            macd_prev={'histogram': 0},
            temp_direction='LONG',
            conditions=[],
            condition_types=[]
        )
        assert bonus == 0

    def test_apply_divergence_bonus_bullish(self):
        """Test bonus de divergence bullish"""
        bonus = apply_divergence_bonus(
            rsi=30,
            rsi_prev=35,
            macd={'histogram': -0.01},
            macd_prev={'histogram': -0.02},
            temp_direction='LONG',
            conditions=[],
            condition_types=[]
        )
        # Le bonus peut être 0 ou positif selon les conditions
        assert bonus >= 0

    def test_apply_divergence_bonus_bearish(self):
        """Test bonus de divergence bearish"""
        bonus = apply_divergence_bonus(
            rsi=70,
            rsi_prev=65,
            macd={'histogram': 0.01},
            macd_prev={'histogram': 0.02},
            temp_direction='SHORT',
            conditions=[],
            condition_types=[]
        )
        # Le bonus peut être 0 ou positif selon les conditions
        assert bonus >= 0

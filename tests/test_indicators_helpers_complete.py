#!/usr/bin/env python3
"""
Tests complets pour utils/indicators_helpers.py - Couverture 100%
"""

import pytest
from unittest.mock import Mock
from utils.indicators_helpers import (
    INDICATOR_FIELDS_1M,
    INDICATOR_FIELDS_5M_SUFFIXES,
    extract_indicators_1m,
    extract_indicators_5m,
    build_indicators_from_analysis,
    count_non_null_values
)


class TestIndicatorConstants:
    """Tests pour les constantes d'indicateurs"""

    def test_indicator_fields_1m_constants(self):
        """Test constantes INDICATOR_FIELDS_1M"""
        expected_fields = [
            'rsi', 'rsi_prev', 'macd', 'macd_signal', 'macd_hist', 'macd_hist_prev',
            'adx', 'di_plus', 'di_minus', 'di_gap',
            'ema9', 'ema21', 'ema_diff_pct',
            'atr', 'atr_pct',
            'bb_upper', 'bb_middle', 'bb_lower', 'bb_width',
            'bb_distance_to_lower', 'bb_distance_to_upper',
            'volume', 'volume_avg', 'volume_ratio', 'volume_spike'
        ]
        
        assert len(INDICATOR_FIELDS_1M) == len(expected_fields)
        for field in expected_fields:
            assert field in INDICATOR_FIELDS_1M

    def test_indicator_fields_5m_suffixes_constants(self):
        """Test constantes INDICATOR_FIELDS_5M_SUFFIXES"""
        # Vérifier que tous les champs 1m ont un mapping 5m
        expected_mappings = [
            ('rsi', 'rsi_5m'),
            ('rsi_prev', 'rsi_prev_5m'),
            ('macd', 'macd_5m'),
            ('macd_signal', 'macd_signal_5m'),
            ('macd_hist', 'macd_hist_5m'),
            ('macd_hist_prev', 'macd_hist_prev_5m'),
            ('adx', 'adx_5m'),
            ('di_plus', 'di_plus_5m'),
            ('di_minus', 'di_minus_5m'),
            ('di_gap', 'di_gap_5m'),
            ('ema9', 'ema9_5m'),
            ('ema21', 'ema21_5m'),
            ('ema_diff_pct', 'ema_diff_pct_5m'),
            ('atr', ['atr5m', 'atr_5m']),  # Cas spécial avec liste
            ('atr_pct', 'atr_pct_5m'),
            ('bb_upper', 'bb_upper_5m'),
            ('bb_middle', 'bb_middle_5m'),
            ('bb_lower', 'bb_lower_5m'),
            ('bb_width', 'bb_width_5m'),
            ('bb_distance_to_lower', 'bb_distance_to_lower_5m'),
            ('bb_distance_to_upper', 'bb_distance_to_upper_5m'),
            ('volume', 'volume_5m'),
            ('volume_avg', 'volume_avg_5m'),
            ('volume_ratio', 'volume_ratio_5m'),
            ('volume_spike', 'volume_spike_5m'),
        ]
        
        assert len(INDICATOR_FIELDS_5M_SUFFIXES) == len(expected_mappings)
        for mapping in expected_mappings:
            assert mapping in INDICATOR_FIELDS_5M_SUFFIXES


class TestExtractIndicators1m:
    """Tests pour extract_indicators_1m"""

    def test_extract_indicators_1m_complete_data(self):
        """Test extraction avec toutes les données"""
        source = {
            'rsi': 65.5,
            'rsi_prev': 63.2,
            'macd': 0.5,
            'macd_signal': 0.4,
            'macd_hist': 0.1,
            'macd_hist_prev': 0.05,
            'adx': 35.0,
            'di_plus': 25.0,
            'di_minus': 15.0,
            'di_gap': 10.0,
            'ema9': 50000.0,
            'ema21': 49500.0,
            'ema_diff_pct': 1.0,
            'atr': 1500.0,
            'atr_pct': 3.0,
            'bb_upper': 52000.0,
            'bb_middle': 50000.0,
            'bb_lower': 48000.0,
            'bb_width': 4000.0,
            'bb_distance_to_lower': 2000.0,
            'bb_distance_to_upper': 2000.0,
            'volume': 1000000.0,
            'volume_avg': 800000.0,
            'volume_ratio': 1.25,
            'volume_spike': False,
            'extra_field': 'ignored'  # Champ supplémentaire ignoré
        }
        
        indicators = extract_indicators_1m(source)
        
        # Vérifier que tous les champs attendus sont présents
        for field in INDICATOR_FIELDS_1M:
            assert field in indicators
        
        # Vérifier les valeurs
        assert indicators['rsi'] == 65.5
        assert indicators['macd'] == 0.5
        assert indicators['volume_ratio'] == 1.25
        assert indicators['volume_spike'] is False
        
        # Vérifier que les champs extra ne sont pas inclus
        assert 'extra_field' not in indicators

    def test_extract_indicators_1m_partial_data(self):
        """Test extraction avec données partielles"""
        source = {
            'rsi': 70.0,
            'macd': 0.3,
            'volume': 500000.0
            # Autres champs manquants
        }
        
        indicators = extract_indicators_1m(source)
        
        # Tous les champs doivent être présents
        assert len(indicators) == len(INDICATOR_FIELDS_1M)
        
        # Les champs présents ont des valeurs
        assert indicators['rsi'] == 70.0
        assert indicators['macd'] == 0.3
        assert indicators['volume'] == 500000.0
        
        # Les champs manquants sont None
        assert indicators['rsi_prev'] is None
        assert indicators['adx'] is None
        assert indicators['atr'] is None

    def test_extract_indicators_1m_empty_source(self):
        """Test extraction avec source vide"""
        source = {}
        
        indicators = extract_indicators_1m(source)
        
        # Tous les champs doivent être présents mais None
        assert len(indicators) == len(INDICATOR_FIELDS_1M)
        for field in INDICATOR_FIELDS_1M:
            assert indicators[field] is None

    def test_extract_indicators_1m_volume_ratio_fallback(self):
        """Test fallback volume_ratio vers volumeSpike"""
        source = {
            'volumeSpike': 2.5,  # Fallback value
            'rsi': 65.0
        }
        
        indicators = extract_indicators_1m(source)
        
        # volume_ratio doit utiliser la valeur de volumeSpike
        assert indicators['volume_ratio'] == 2.5
        assert indicators['rsi'] == 65.0

    def test_extract_indicators_1m_volume_ratio_priority(self):
        """Test priorité volume_ratio sur volumeSpike"""
        source = {
            'volume_ratio': 1.8,
            'volumeSpike': 2.5,  # Ignoré car volume_ratio existe
            'rsi': 60.0
        }
        
        indicators = extract_indicators_1m(source)
        
        # volume_ratio doit prendre sa propre valeur
        assert indicators['volume_ratio'] == 1.8
        assert indicators['rsi'] == 60.0


class TestExtractIndicators5m:
    """Tests pour extract_indicators_5m"""

    def test_extract_indicators_5m_complete_data(self):
        """Test extraction 5m avec toutes les données"""
        source = {
            'rsi_5m': 68.0,
            'rsi_prev_5m': 66.5,
            'macd_5m': 0.7,
            'macd_signal_5m': 0.6,
            'macd_hist_5m': 0.1,
            'macd_hist_prev_5m': 0.08,
            'adx_5m': 40.0,
            'di_plus_5m': 28.0,
            'di_minus_5m': 18.0,
            'di_gap_5m': 10.0,
            'ema9_5m': 51000.0,
            'ema21_5m': 50000.0,
            'ema_diff_pct_5m': 2.0,
            'atr_5m': 1800.0,  # Format standard
            'atr_pct_5m': 3.6,
            'bb_upper_5m': 53000.0,
            'bb_middle_5m': 51000.0,
            'bb_lower_5m': 49000.0,
            'bb_width_5m': 4000.0,
            'bb_distance_to_lower_5m': 2000.0,
            'bb_distance_to_upper_5m': 2000.0,
            'volume_5m': 1200000.0,
            'volume_avg_5m': 1000000.0,
            'volume_ratio_5m': 1.2,
            'volume_spike_5m': True
        }
        
        indicators = extract_indicators_5m(source)
        
        # Vérifier que tous les champs attendus sont présents (sans suffixe _5m)
        expected_fields = [target for target, _ in INDICATOR_FIELDS_5M_SUFFIXES]
        for field in expected_fields:
            assert field in indicators
        
        # Vérifier les valeurs (les clés de sortie n'ont pas de suffixe _5m)
        assert indicators['rsi'] == 68.0
        assert indicators['macd'] == 0.7
        assert indicators['atr'] == 1800.0
        assert indicators['volume_spike'] is True

    def test_extract_indicators_5m_atr_multiple_keys(self):
        """Test extraction ATR avec clés multiples"""
        # Test avec atr5m (ancienne nomenclature)
        source_old = {'atr5m': 1500.0}
        indicators_old = extract_indicators_5m(source_old)
        assert indicators_old['atr'] == 1500.0
        
        # Test avec atr_5m (nouvelle nomenclature)
        source_new = {'atr_5m': 1600.0}
        indicators_new = extract_indicators_5m(source_new)
        assert indicators_new['atr'] == 1600.0
        
        # Test avec les deux (priorité au premier trouvé dans la liste)
        source_both = {'atr5m': 1500.0, 'atr_5m': 1600.0}
        indicators_both = extract_indicators_5m(source_both)
        assert indicators_both['atr'] == 1500.0  # atr5m est trouvé en premier

    def test_extract_indicators_5m_partial_data(self):
        """Test extraction 5m avec données partielles"""
        source = {
            'rsi_5m': 72.0,
            'volume_5m': 800000.0
            # Autres champs manquants
        }
        
        indicators = extract_indicators_5m(source)
        
        # Tous les champs doivent être présents
        expected_fields = [target for target, _ in INDICATOR_FIELDS_5M_SUFFIXES]
        assert len(indicators) == len(expected_fields)
        
        # Les champs présents ont des valeurs
        assert indicators['rsi'] == 72.0
        assert indicators['volume'] == 800000.0
        
        # Les champs manquants sont None
        assert indicators['macd'] is None
        assert indicators['atr'] is None

    def test_extract_indicators_5m_empty_source(self):
        """Test extraction 5m avec source vide"""
        source = {}
        
        indicators = extract_indicators_5m(source)
        
        # Tous les champs doivent être présents mais None
        expected_fields = [target for target, _ in INDICATOR_FIELDS_5M_SUFFIXES]
        assert len(indicators) == len(expected_fields)
        for field in expected_fields:
            assert indicators[field] is None


class TestBuildIndicatorsFromAnalysis:
    """Tests pour build_indicators_from_analysis"""

    def test_build_indicators_from_analysis_existing_1m(self):
        """Test avec indicators_1m existants"""
        existing_indicators = {'rsi': 65.0, 'macd': 0.5}
        analysis = {
            'indicators_1m': existing_indicators,
            'analysis_1m': {'rsi': 70.0, 'macd': 0.8},  # Ignoré
            'rsi': 60.0,  # Ignoré
        }
        
        mock_logger = Mock()
        result = build_indicators_from_analysis(analysis, '1m', mock_logger)
        
        assert result == existing_indicators
        mock_logger.debug.assert_called_with("Using existing indicators_1m from analysis")

    def test_build_indicators_from_analysis_existing_5m(self):
        """Test avec indicators_5m existants"""
        existing_indicators = {'rsi': 68.0, 'volume': 1000000.0}
        analysis = {
            'indicators_5m': existing_indicators,
            'analysis_5m': {'rsi': 72.0},  # Ignoré
        }
        
        mock_logger = Mock()
        result = build_indicators_from_analysis(analysis, '5m', mock_logger)
        
        assert result == existing_indicators
        mock_logger.debug.assert_called_with("Using existing indicators_5m from analysis")

    def test_build_indicators_from_analysis_nested_1m(self):
        """Test extraction depuis analysis_1m"""
        nested_data = {'rsi': 75.0, 'macd': 0.9, 'volume': 1500000.0}
        analysis = {
            'analysis_1m': nested_data,
            'rsi': 60.0,  # Ignoré car analysis_1m prioritaire
        }
        
        mock_logger = Mock()
        result = build_indicators_from_analysis(analysis, '1m', mock_logger)
        
        # Doit contenir tous les champs INDICATOR_FIELDS_1M
        assert len(result) == len(INDICATOR_FIELDS_1M)
        assert result['rsi'] == 75.0
        assert result['macd'] == 0.9
        assert result['volume'] == 1500000.0
        mock_logger.debug.assert_called_with("Extracting indicators_1m from analysis_1m")

    def test_build_indicators_from_analysis_nested_5m(self):
        """Test extraction depuis analysis_5m"""
        nested_data = {'rsi': 78.0, 'atr': 2000.0, 'volume_spike': True}
        analysis = {
            'analysis_5m': nested_data,
        }
        
        mock_logger = Mock()
        result = build_indicators_from_analysis(analysis, '5m', mock_logger)
        
        # Doit contenir tous les champs de extract_indicators_1m (car analysis_5m utilise les mêmes noms)
        assert len(result) == len(INDICATOR_FIELDS_1M)
        assert result['rsi'] == 78.0
        assert result['atr'] == 2000.0
        assert result['volume_spike'] is True
        mock_logger.debug.assert_called_with("Extracting indicators_5m from analysis_5m")

    def test_build_indicators_from_analysis_direct_1m(self):
        """Test extraction directe pour 1m"""
        analysis = {
            'rsi': 62.0,
            'macd': 0.4,
            'volume_ratio': 1.3,
            'volumeSpike': 2.0  # Fallback pour volume_ratio
        }
        
        mock_logger = Mock()
        result = build_indicators_from_analysis(analysis, '1m', mock_logger)
        
        assert len(result) == len(INDICATOR_FIELDS_1M)
        assert result['rsi'] == 62.0
        assert result['macd'] == 0.4
        assert result['volume_ratio'] == 1.3  # Pas de fallback car volume_ratio existe
        mock_logger.debug.assert_called_with("Extracting indicators_1m directly from analysis")

    def test_build_indicators_from_analysis_direct_5m(self):
        """Test extraction directe pour 5m"""
        analysis = {
            'rsi_5m': 64.0,
            'atr_5m': 1700.0,
            'volume_spike_5m': False
        }
        
        mock_logger = Mock()
        result = build_indicators_from_analysis(analysis, '5m', mock_logger)
        
        expected_fields = [target for target, _ in INDICATOR_FIELDS_5M_SUFFIXES]
        assert len(result) == len(expected_fields)
        assert result['rsi'] == 64.0
        assert result['atr'] == 1700.0
        assert result['volume_spike'] is False
        mock_logger.debug.assert_called_with("Extracting indicators_5m directly from analysis")

    def test_build_indicators_from_analysis_invalid_input(self):
        """Test avec entrées invalides"""
        # Test avec None
        result = build_indicators_from_analysis(None, '1m')
        assert result == {}
        
        # Test avec type incorrect
        result = build_indicators_from_analysis("not a dict", '1m')
        assert result == {}
        
        # Test avec dict vide
        result = build_indicators_from_analysis({}, '1m')
        assert result == {}

    def test_build_indicators_from_analysis_no_logger(self):
        """Test sans logger"""
        analysis = {'rsi': 55.0}
        
        # Ne doit pas planter même sans logger
        result = build_indicators_from_analysis(analysis, '1m', None)
        assert result['rsi'] == 55.0

    def test_build_indicators_from_analysis_invalid_timeframe(self):
        """Test avec timeframe invalide"""
        analysis = {'rsi': 50.0}
        
        result = build_indicators_from_analysis(analysis, 'invalid', None)
        assert result == {}

    def test_build_indicators_from_analysis_empty_existing(self):
        """Test avec existing indicators vides"""
        analysis = {
            'indicators_1m': {},  # Vide, doit être ignoré
            'rsi': 45.0
        }
        
        mock_logger = Mock()
        result = build_indicators_from_analysis(analysis, '1m', mock_logger)
        
        # Doit fallback vers extraction directe
        assert result['rsi'] == 45.0
        mock_logger.debug.assert_called_with("Extracting indicators_1m directly from analysis")

    def test_build_indicators_from_analysis_invalid_existing(self):
        """Test avec existing indicators invalides"""
        analysis = {
            'indicators_1m': "not a dict",  # Type incorrect
            'rsi': 40.0
        }
        
        result = build_indicators_from_analysis(analysis, '1m', None)
        
        # Doit fallback vers extraction directe
        assert result['rsi'] == 40.0

    def test_build_indicators_from_analysis_empty_nested(self):
        """Test avec nested analysis vide"""
        analysis = {
            'analysis_1m': {},  # Vide
            'rsi': 38.0
        }
        
        mock_logger = Mock()
        result = build_indicators_from_analysis(analysis, '1m', mock_logger)
        
        # Doit fallback vers extraction directe
        assert result['rsi'] == 38.0
        mock_logger.debug.assert_called_with("Extracting indicators_1m directly from analysis")

    def test_build_indicators_from_analysis_invalid_nested(self):
        """Test avec nested analysis invalide"""
        analysis = {
            'analysis_1m': "not a dict",  # Type incorrect
            'rsi': 35.0
        }
        
        result = build_indicators_from_analysis(analysis, '1m', None)
        
        # Doit fallback vers extraction directe
        assert result['rsi'] == 35.0


class TestCountNonNullValues:
    """Tests pour count_non_null_values"""

    def test_count_non_null_values_all_present(self):
        """Test comptage avec toutes valeurs présentes"""
        indicators = {
            'rsi': 65.0,
            'macd': 0.5,
            'volume': 1000000.0,
            'volume_spike': False  # False compte comme non-null
        }
        
        count = count_non_null_values(indicators)
        assert count == 4

    def test_count_non_null_values_mixed(self):
        """Test comptage avec valeurs mixtes"""
        indicators = {
            'rsi': 70.0,
            'macd': None,
            'volume': 0.0,  # 0 compte comme non-null
            'atr': None,
            'volume_spike': True
        }
        
        count = count_non_null_values(indicators)
        assert count == 3  # rsi, volume (0.0), volume_spike

    def test_count_non_null_values_all_null(self):
        """Test comptage avec toutes valeurs null"""
        indicators = {
            'rsi': None,
            'macd': None,
            'volume': None
        }
        
        count = count_non_null_values(indicators)
        assert count == 0

    def test_count_non_null_values_empty_dict(self):
        """Test comptage avec dictionnaire vide"""
        indicators = {}
        
        count = count_non_null_values(indicators)
        assert count == 0

    def test_count_non_null_values_zero_and_false_values(self):
        """Test que 0 et False comptent comme non-null"""
        indicators = {
            'value_zero': 0,
            'value_false': False,
            'value_empty_string': '',
            'value_null': None,
            'value_normal': 42
        }
        
        count = count_non_null_values(indicators)
        assert count == 4  # Tout sauf None


if __name__ == "__main__":
    # Lancement des tests
    pytest.main([__file__, "-v", "--tb=short"])

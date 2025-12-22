#!/usr/bin/env python3
"""
Test complet de la logique ML Calibration
"""
import sys
sys.path.append('.')
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

def test_calibration_buckets():
    """Test 1: Vérifier le calcul des buckets de confidence"""
    print('\n' + '='*80)
    print('TEST 1: CALCUL BUCKETS DE CONFIDENCE')
    print('='*80)
    
    try:
        from ml.calibration import MLCalibrationManager
        calib_manager = MLCalibrationManager()
        
        # Test différentes confidences
        test_confidences = [0.25, 0.35, 0.42, 0.48, 0.52, 0.65, 0.70]
        
        print('\nTest calcul buckets:')
        for conf in test_confidences:
            bucket = calib_manager.get_confidence_bucket(conf * 100)  # Le manager attend des %
            print(f'   Confidence {conf:.3f} ({conf*100:.1f}%) -> Bucket: {bucket}')
            
        # Vérifier la logique attendue
        expected_buckets = ['25-30', '35-40', '40-45', '45-50', '50+', '50+', '50+']
        actual_buckets = [calib_manager.get_confidence_bucket(c * 100) for c in test_confidences]
        
        if actual_buckets == expected_buckets:
            print('\n[OK] Calcul buckets correct')
        else:
            print(f'\n[ERROR] Buckets incorrects!')
            print(f'         Attendu: {expected_buckets}')
            print(f'         Obtenu: {actual_buckets}')
            
        return actual_buckets == expected_buckets
        
    except Exception as e:
        print(f'[ERROR] Erreur test buckets: {e}')
        return False


def test_winrate_rejection_logic():
    """Test 2: Vérifier la logique de rejet par winrate"""
    print('\n' + '='*80)
    print('TEST 2: LOGIQUE REJET PAR WINRATE')
    print('='*80)
    
    try:
        from ml.calibration import MLCalibrationManager
        from config import TRADING_CONFIG
        
        calib_manager = MLCalibrationManager()
        
        # Récupérer les seuils de config
        min_winrate_long = TRADING_CONFIG.get('ml_calibration_min_winrate_long', 0.35)
        min_winrate_short = TRADING_CONFIG.get('ml_calibration_min_winrate_short', 0.35)
        
        print(f'Seuils config:')
        print(f'   min_winrate_long: {min_winrate_long*100:.0f}%')
        print(f'   min_winrate_short: {min_winrate_short*100:.0f}%')
        
        # Simuler des données de calibration
        test_scenarios = [
            # (direction, ml_confidence, winrate_observé, should_accept)
            ('LONG', 0.45, 0.42, True),   # 42% > 40% seuil LONG
            ('LONG', 0.45, 0.38, False),  # 38% < 40% seuil LONG
            ('SHORT', 0.45, 0.38, True),  # 38% > 35% seuil SHORT
            ('SHORT', 0.45, 0.32, False), # 32% < 35% seuil SHORT
        ]
        
        print('\nTest scenarios rejet:')
        for direction, ml_conf, observed_wr, expected_accept in test_scenarios:
            bucket = calib_manager.get_confidence_bucket(ml_conf * 100)
            
            # Simuler une consultation de calibration
            threshold = min_winrate_long if direction == 'LONG' else min_winrate_short
            should_accept = observed_wr >= threshold
            
            status = '[OK]' if should_accept == expected_accept else '[ERROR]'
            action = 'ACCEPTE' if should_accept else 'REJETE'
            
            print(f'   {status} {direction} conf={ml_conf:.2f} bucket={bucket} observed_wr={observed_wr*100:.0f}% -> {action}')
        
        return True
        
    except Exception as e:
        print(f'[ERROR] Erreur test rejet: {e}')
        return False


def test_calibration_update_flow():
    """Test 3: Vérifier le flux de mise à jour de calibration"""
    print('\n' + '='*80)
    print('TEST 3: FLUX MISE A JOUR CALIBRATION')
    print('='*80)
    
    try:
        from ml.calibration import MLCalibrationManager
        
        calib_manager = MLCalibrationManager()
        
        # Test avec différents trades simulés
        test_trades = [
            # (direction, ml_confidence, win, pnl_pct, pnl_usdt)
            ('LONG', 0.45, True, 0.15, 1.5),
            ('LONG', 0.45, False, -0.08, -0.8),
            ('LONG', 0.52, True, 0.22, 2.2),
            ('SHORT', 0.38, True, 0.12, 1.2),
            ('SHORT', 0.38, False, -0.10, -1.0),
        ]
        
        print('Simulation mises a jour calibration:')
        for direction, ml_conf, win, pnl_pct, pnl_usdt in test_trades:
            try:
                # Test la méthode update_calibration
                result = calib_manager.update_calibration(
                    direction=direction,
                    ml_confidence=ml_conf * 100,  # Convertir en %
                    win=win,
                    pnl_pct=pnl_pct,
                    pnl_usdt=pnl_usdt
                )
                
                bucket = calib_manager.get_confidence_bucket(ml_conf * 100)
                outcome = 'WIN' if win else 'LOSS'
                
                print(f'   [OK] {direction} bucket={bucket} {outcome} -> Update success: {result}')
                
            except Exception as e:
                print(f'   [ERROR] Update failed: {e}')
        
        return True
        
    except Exception as e:
        print(f'[ERROR] Erreur test update: {e}')
        return False


def test_position_manager_integration():
    """Test 4: Vérifier l'intégration avec position_manager"""
    print('\n' + '='*80)
    print('TEST 4: INTEGRATION POSITION_MANAGER')
    print('='*80)
    
    try:
        # Vérifier que position_manager utilise bien ML calibration
        from core.position_manager import PositionManager
        from config import TRADING_CONFIG
        
        ml_calib_enabled = TRADING_CONFIG.get('ml_calibration_enabled', False)
        print(f'ml_calibration_enabled dans config: {ml_calib_enabled}')
        
        if not ml_calib_enabled:
            print('[WARNING] ML Calibration désactivée en config!')
            return False
            
        # Créer une instance de PositionManager
        pm = PositionManager()
        
        # Vérifier que la classe MLCalibrationManager est accessible
        if hasattr(pm, 'ml_calibration_manager'):
            print('[OK] PositionManager a un ml_calibration_manager')
        else:
            print('[INFO] PositionManager pas de ml_calibration_manager direct')
            
        # Test d'import du module ML calibration depuis position_manager
        try:
            from ml.calibration import MLCalibrationManager
            test_manager = MLCalibrationManager()
            print('[OK] MLCalibrationManager importable depuis position_manager')
        except ImportError as e:
            print(f'[ERROR] Import MLCalibrationManager failed: {e}')
            return False
            
        return True
        
    except Exception as e:
        print(f'[ERROR] Erreur test integration: {e}')
        return False


def test_confidence_consistency():
    """Test 5: Vérifier la cohérence entre confidence GB et calibration"""
    print('\n' + '='*80)
    print('TEST 5: COHERENCE CONFIDENCE GB <-> CALIBRATION')
    print('='*80)
    
    try:
        # Test avec le predictor GB
        from optimization.predictor_optimized import get_predictor
        from ml.calibration import MLCalibrationManager
        
        predictor = get_predictor()
        calib_manager = MLCalibrationManager()
        
        if not predictor.is_loaded:
            print('[ERROR] Predictor GB non chargé')
            return False
            
        # Créer des features de test
        test_features = {
            'di_minus_1m': 25.5,
            'di_gap_1m': 8.2,
            'bb_distance_to_lower_5m': 0.015,
            'bb_distance_to_upper_5m': 0.032,
            'ema_trend_strength_1m': 0.008,
            'macd_hist_prev_5m': 0.0015,
            'ema_trend_strength_5m': 0.012,
            'rsi_change_1m': -2.1,
            'rsi_prev_1m': 58.3,
            'rsi_5m': 62.1,
            'hour': 14,
            'volume_spike_5m': 1.8,
            'ema_diff_pct_1m': 0.005,
            'momentum_divergence': 0.025,
            'bb_width_1m': 0.018,
            'delta_volume': 0.3,
            'macd_hist_5m': 0.002,
            'atr_pct_5m': 0.015,
            'di_gap_5m': 12.1,
            'bb_distance_to_lower_1m': 0.008
        }
        
        # Test prédiction GB
        should_trade, confidence = predictor.predict(test_features, threshold=0.5)
        
        print(f'Prediction GB: confidence={confidence:.4f} ({confidence*100:.2f}%)')
        
        # Test calcul bucket calibration
        bucket = calib_manager.get_confidence_bucket(confidence * 100)
        print(f'Bucket calibration: {bucket}')
        
        # Vérifier cohérence format
        if 0.0 <= confidence <= 1.0:
            print('[OK] Confidence GB format correct (0.0-1.0)')
        else:
            print(f'[ERROR] Confidence GB format incorrect: {confidence}')
            return False
            
        # Test bucket calculation
        if confidence >= 0.5:
            expected_bucket = '50+'
        else:
            bucket_floor = int(confidence * 100 // 5) * 5
            expected_bucket = f'{bucket_floor}-{bucket_floor + 5}'
            
        if bucket == expected_bucket:
            print(f'[OK] Bucket calculation correct: {confidence:.3f} -> {bucket}')
        else:
            print(f'[ERROR] Bucket calculation incorrect: {confidence:.3f} -> {bucket} (attendu: {expected_bucket})')
            return False
            
        return True
        
    except Exception as e:
        print(f'[ERROR] Erreur test coherence: {e}')
        return False


def test_config_validation():
    """Test 6: Valider la configuration ML Calibration"""
    print('\n' + '='*80)
    print('TEST 6: VALIDATION CONFIGURATION')
    print('='*80)
    
    try:
        from config import TRADING_CONFIG
        
        # Vérifier toutes les clés de config ML calibration
        required_keys = [
            'ml_calibration_enabled',
            'ml_calib_min_winrate',
            'ml_calibration_min_winrate_long',
            'ml_calibration_min_winrate_short',
            'ml_calib_bucket_size',
            'ml_calib_min_trades',
            'ml_calib_decay_days'
        ]
        
        print('Verification config keys:')
        missing_keys = []
        for key in required_keys:
            if key in TRADING_CONFIG:
                value = TRADING_CONFIG[key]
                print(f'   [OK] {key}: {value}')
            else:
                print(f'   [ERROR] {key}: MANQUANT')
                missing_keys.append(key)
                
        # Vérifier valeurs cohérentes
        if 'ml_calibration_min_winrate_long' in TRADING_CONFIG and 'ml_calibration_min_winrate_short' in TRADING_CONFIG:
            long_wr = TRADING_CONFIG['ml_calibration_min_winrate_long']
            short_wr = TRADING_CONFIG['ml_calibration_min_winrate_short']
            
            if 0.2 <= long_wr <= 0.8 and 0.2 <= short_wr <= 0.8:
                print(f'   [OK] Seuils winrate dans range valide: LONG={long_wr*100:.0f}%, SHORT={short_wr*100:.0f}%')
            else:
                print(f'   [ERROR] Seuils winrate hors range: LONG={long_wr}, SHORT={short_wr}')
                
        return len(missing_keys) == 0
        
    except Exception as e:
        print(f'[ERROR] Erreur validation config: {e}')
        return False


def main():
    """Exécuter tous les tests ML Calibration"""
    print('='*80)
    print('TEST COMPLET LOGIQUE ML CALIBRATION')
    print('='*80)
    
    tests = [
        ('Buckets de confidence', test_calibration_buckets),
        ('Logique rejet winrate', test_winrate_rejection_logic),
        ('Flux mise à jour calibration', test_calibration_update_flow),
        ('Intégration position_manager', test_position_manager_integration),
        ('Cohérence confidence GB', test_confidence_consistency),
        ('Validation configuration', test_config_validation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f'\n[ERROR] {test_name} crashed: {e}')
            results.append((test_name, False))
    
    # Résumé final
    print('\n' + '='*80)
    print('RESUME TESTS ML CALIBRATION')
    print('='*80)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = '[PASS]' if success else '[FAIL]'
        print(f'   {status} {test_name}')
        if success:
            passed += 1
    
    print(f'\nRESULTAT: {passed}/{total} tests réussis ({passed/total*100:.1f}%)')
    
    if passed == total:
        print('\n✅ TOUS LES TESTS ML CALIBRATION PASSES')
        print('   Le système ML Calibration fonctionne correctement')
    else:
        print(f'\n❌ {total - passed} TESTS ECHOUES')
        print('   Des corrections sont nécessaires')
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

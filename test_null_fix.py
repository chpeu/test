#!/usr/bin/env python3
"""
Test rapide pour vérifier que les corrections NULL fonctionnent
"""
import sys
sys.path.insert(0, '.')

from core.postgresql_datalogger import PostgreSQLDataLogger
import uuid
from datetime import datetime
import json

def test_scan_insert():
    """Tester l'insertion d'un scan avec tous les nouveaux champs"""
    logger = PostgreSQLDataLogger()
    
    # Créer session d'abord
    session_id = logger.get_or_create_session()
    print(f"📋 Session créée: {session_id}")
    
    # Données de scan avec contexte complet
    scan_data = {
        'market_data': {
            'price': 1.234,
            'spread_pct': 0.05,
            'book_depth': 1000.0,
            'balance_score': 0.8,
            'bid_vol': 50000,
            'ask_vol': 45000,
            'orderbook_imbalance_ratio': 0.1,
            'recent_volume': 250000,
            'vol5': 180000,
            'vol15': 320000,
            'scalability_score': 85.5
        },
        'indicators_1m': {
            'rsi': 45.2,
            'macd_hist': 0.001,
            'adx': 25.3,
            'atr': 0.02,
            'ema9': 1.235,
            'ema21': 1.240
        },
        'scores': {
            'score_total': 8.5,
            'score_1m': 4.2,
            'score_5m': 4.3
        },
        'is_opportunity': True,
        'opportunity_direction': 'LONG',
        'ml_confidence': 73.5,
        'params_snapshot': {
            'min_score_required': 7.0,
            'use_confluence': True,
            'volume_multiplier': 1.5
        },
        # Colonnes contexte (précédemment NULL)
        'market_regime': 'TRENDING',
        'market_regime_avg_atr': 0.025,
        'market_regime_avg_adx': 28.5,
        'session_market': 'EU',
        'hour_utc': 14,
        'regime_at_scan': 'BULLISH',
        'regime_confidence_at_scan': 0.85,
        'scan_duration_ms': 125.5
    }
    
    print("🧪 Test insert scan avec contexte complet...")
    scan_id = logger.log_scan(
        symbol='TEST/USDT',
        scan_data=scan_data,
        session_id=session_id,
        use_batch=False  # Mode direct pour test immédiat
    )
    
    if scan_id:
        print(f"✅ Scan inséré avec ID: {scan_id}")
        return True
    else:
        print("❌ Échec insertion scan")
        return False

def test_trade_insert():
    """Tester l'insertion d'un trade avec tous les nouveaux champs"""
    logger = PostgreSQLDataLogger()
    
    # Données de trade complètes
    trade_data = {
        'symbol': 'TEST/USDT',
        'direction': 'LONG',
        'entry_price': 1.234,
        'exit_price': 1.256,
        'size_usdt': 100.0,
        'tp_price': 1.280,
        'sl_price': 1.210,
        'gross_pnl_usdt': 1.78,
        'gross_pnl_pct': 1.78,
        'fees_usdt': 0.15,
        'duration_seconds': 180,
        'reason': 'TP_HIT',
        'entry_indicators': {
            'rsi_1m': 42.5,
            'macd_hist_1m': 0.001,
            'adx_1m': 26.8,
            'atr_1m': 0.02
        },
        'entry_scalability': {
            'spread_pct': 0.05,
            'balance_score': 0.82,
            'recent_volume': 275000,
            'vol5': 185000
        },
        'config_snapshot': {
            'min_score_required': 7.0,
            'use_confluence': True,
            'rsi_final_filter_enabled': True,
            'rsi_final_long_max': 65.0
        },
        # Colonnes précédemment NULL
        'ml_confidence': 75.2,
        'setup_score': 8.7,
        'ml_prediction': 'BUY',
        'ml_features': {'feature1': 0.8, 'feature2': -0.3},
        'price_at_signal': 1.2335,
        'price_at_order_sent': 1.2338,
        'time_to_fill_entry_ms': 125,
        'entry_slippage_pct': 0.02,
        'trade_notes': 'Test trade après fix NULL',
        'user_rating': 4
    }
    
    print("🧪 Test insert trade avec données complètes...")
    trade_id = logger.log_trade(
        trade_data=trade_data,
        session_id=str(uuid.uuid4())
    )
    
    if trade_id:
        print(f"✅ Trade inséré avec ID: {trade_id}")
        return True
    else:
        print("❌ Échec insertion trade")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("🔧 TEST CORRECTIONS NULL COLUMNS")
    print("=" * 60)
    
    success = 0
    total = 2
    
    try:
        if test_scan_insert():
            success += 1
    except Exception as e:
        print(f"❌ Erreur test scan: {e}")
    
    try:
        if test_trade_insert():
            success += 1
    except Exception as e:
        print(f"❌ Erreur test trade: {e}")
    
    print("=" * 60)
    print(f"📊 RÉSULTAT: {success}/{total} tests réussis")
    
    if success == total:
        print("✅ Tous les tests passent - corrections NULL OK!")
        sys.exit(0)
    else:
        print("❌ Certains tests échouent - vérifier les logs")
        sys.exit(1)

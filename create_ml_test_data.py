#!/usr/bin/env python3
"""
Script pour créer des données de test ML avec les nouvelles colonnes
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.postgresql_datalogger import PostgreSQLDataLogger

async def create_test_data():
    pg = PostgreSQLDataLogger()
    
    if not pg.enabled:
        print("❌ PostgreSQL désactivé")
        return False
    
    print("🔄 Création de données de test ML...")
    
    # Créer un scan de test complet avec toutes les données requises
    scan_data = {
        'symbol': 'BTCUSDT',
        'price': 45000.0,
        'is_opportunity': False,
        'opportunity_direction': None,
        'reject_reason': None,
        'reject_reason_category': None,
        'ml_confidence': None,
        'setup_score': 85.5,
        'trend_detected': True,
        'session_id': pg.get_or_create_session()
    }
    
    # Logger le scan
    print("📊 Création d'un scan de test...")
    scan_id = pg.log_scan('BTCUSDT', scan_data)
    print(f"✅ Scan créé avec ID: {scan_id}")
    
    if scan_id:
        # Tester les différents types de rejets ML
        test_cases = [
            {
                'reason': 'GradientBoosting confidence 42.3% < seuil 55.0%',
                'category': 'ml_gb_confidence',
                'confidence': 42.3,
                'threshold': 55.0,
                'winrate': None
            },
            {
                'reason': 'ML prédit loss avec confiance 78.5% >= seuil 70.0%',
                'category': 'ml_xgboost_soft', 
                'confidence': 78.5,
                'threshold': 70.0,
                'winrate': None
            },
            {
                'reason': 'Calibrated winrate 38.2% < minimum 45.0%',
                'category': 'ml_calibration_winrate',
                'confidence': 67.8,
                'threshold': 45.0,
                'winrate': 38.2
            }
        ]
        
        print("🧪 Test des rejets ML...")
        for i, case in enumerate(test_cases):
            success = await pg.update_ml_rejection_async(
                symbol='BTCUSDT',
                reject_reason=case['reason'],
                reject_category=case['category'],
                ml_confidence=case['confidence'],
                ml_threshold_used=case['threshold'],
                calibrated_winrate=case['winrate']
            )
            status = "OK" if success else "FAIL"
            print(f"  ✅ Test ML {i+1} ({case['category']}): {status}")
    
    # Vérifier les données créées
    print("🔍 Vérification des données créées...")
    result = pg._execute_query("""
        SELECT symbol, reject_reason_category, ml_confidence, 
               ml_threshold_used, ml_threshold_type, calibrated_winrate
        FROM scan_logs 
        WHERE symbol = 'BTCUSDT' 
        AND reject_reason_category IS NOT NULL
        ORDER BY timestamp DESC LIMIT 5
    """, fetch=True)
    
    if result:
        print(f"✅ Trouvé {len(result)} rejets ML avec nouvelles colonnes:")
        for row in result:
            print(f"  - {row[1]}: confidence={row[2]}, threshold={row[3]}, type={row[4]}, winrate={row[5]}")
        return True
    else:
        print("⚠️ Aucun rejet ML trouvé après insertion")
        return False

if __name__ == "__main__":
    success = asyncio.run(create_test_data())
    print(f"🏁 Résultat: {'Succès' if success else 'Échec'}")

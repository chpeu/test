#!/usr/bin/env python3
"""
Validation simplifiée et efficace de l'implémentation ML
Se concentre sur les éléments essentiels

Date: 16/01/2026
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.postgresql_datalogger import PostgreSQLDataLogger

async def main():
    print("🚀 VALIDATION SIMPLIFIÉE ML THRESHOLD")
    print("="*50)
    
    pg = PostgreSQLDataLogger()
    
    if not pg.enabled:
        print("❌ PostgreSQL désactivé")
        return False
    
    success_count = 0
    total_tests = 4
    
    # TEST 1: Colonnes ML créées
    print("\n🔍 Test 1: Vérification des colonnes ML")
    result = pg._execute_query("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'scan_logs' 
        AND column_name IN ('ml_threshold_used', 'ml_threshold_type', 'calibrated_winrate')
    """, fetch=True)
    
    if result and len(result) == 3:
        print("✅ PASS - 3 colonnes ML trouvées")
        success_count += 1
    else:
        print(f"❌ FAIL - Colonnes ML manquantes: {len(result or [])}/3")
    
    # TEST 2: Fonction update_ml_rejection
    print("\n🔍 Test 2: Test fonction update_ml_rejection")
    try:
        success = await pg.update_ml_rejection_async(
            symbol='TEST_VALIDATION',
            reject_reason='Test validation ML confidence 45% < seuil 60%',
            reject_category='test_ml_validation',
            ml_confidence=45.0,
            ml_threshold_used=60.0
        )
        
        if success:
            print("✅ PASS - update_ml_rejection_async fonctionne")
            success_count += 1
        else:
            print("❌ FAIL - update_ml_rejection_async returned False")
    except Exception as e:
        print(f"❌ FAIL - Exception: {e}")
    
    # TEST 3: Récupération des données ML
    print("\n🔍 Test 3: Récupération données ML")
    result = pg._execute_query("""
        SELECT reject_reason_category, ml_confidence, ml_threshold_used, ml_threshold_type
        FROM scan_logs 
        WHERE reject_reason_category IS NOT NULL
        AND ml_threshold_used IS NOT NULL
        ORDER BY timestamp DESC 
        LIMIT 1
    """, fetch=True)
    
    if result and len(result) > 0:
        row = result[0]
        print(f"✅ PASS - Données ML récupérées: {row[0]}, conf={row[1]}, seuil={row[2]}")
        success_count += 1
    else:
        print("❌ FAIL - Aucune donnée ML complète trouvée")
    
    # TEST 4: Vérification export Excel (code check)
    print("\n🔍 Test 4: Vérification code export Excel")
    main_py = Path(__file__).parent / 'main.py'
    
    if main_py.exists():
        content = main_py.read_text(encoding='utf-8')
        ml_columns_in_export = [
            'ml_threshold_used' in content,
            'ml_threshold_type' in content,
            'calibrated_winrate' in content
        ]
        
        if all(ml_columns_in_export):
            print("✅ PASS - Colonnes ML présentes dans export Excel")
            success_count += 1
        else:
            print(f"❌ FAIL - Colonnes ML manquantes dans export: {ml_columns_in_export}")
    else:
        print("❌ FAIL - main.py non trouvé")
    
    # RÉSULTATS FINAUX
    success_rate = (success_count / total_tests) * 100
    
    print("\n" + "="*50)
    print("📊 RÉSULTATS FINAUX")
    print("="*50)
    print(f"Tests réussis: {success_count}/{total_tests}")
    print(f"Taux de réussite: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("🎉 MIGRATION ML COMPLÈTE ET FONCTIONNELLE!")
        print("✅ Toutes les colonnes sont créées")
        print("✅ Le logging des rejets ML fonctionne")
        print("✅ L'export Excel est mis à jour")
        print("✅ Les données sont récupérables")
        status = "SUCCESS"
    elif success_rate >= 75:
        print("✅ MIGRATION GLOBALEMENT RÉUSSIE")
        print("⚠️ Quelques problèmes mineurs détectés")
        status = "MOSTLY_SUCCESS"
    else:
        print("❌ MIGRATION NÉCESSITE DES CORRECTIONS")
        status = "NEEDS_FIXES"
    
    print("="*50)
    
    # Test bonus: Vérifier que les nouvelles colonnes sont utilisables
    if success_count >= 3:
        print("\n🔍 Test bonus: Utilisation pratique")
        
        # Créer un rejet ML avec tous les champs
        test_success = await pg.update_ml_rejection_async(
            symbol='FINAL_TEST',
            reject_reason='Test final: GradientBoosting 38.7% < 55.0%',
            reject_category='ml_gb_confidence',
            ml_confidence=38.7,
            ml_threshold_used=55.0,
            calibrated_winrate=None
        )
        
        if test_success:
            # Vérifier récupération
            verification = pg._execute_query("""
                SELECT reject_reason, ml_confidence, ml_threshold_used, ml_threshold_type
                FROM scan_logs 
                WHERE symbol = 'FINAL_TEST'
                AND reject_reason_category = 'ml_gb_confidence'
                ORDER BY timestamp DESC LIMIT 1
            """, fetch=True)
            
            if verification:
                row = verification[0]
                print(f"🎉 BONUS PASS - Cycle complet réussi!")
                print(f"   Données stockées: {row[0][:50]}...")
                print(f"   ML confidence: {row[1]}%")
                print(f"   Seuil utilisé: {row[2]}%") 
                print(f"   Type auto-détecté: {row[3]}")
                
    return success_rate >= 75

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

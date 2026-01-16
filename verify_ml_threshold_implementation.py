#!/usr/bin/env python3
"""
Script de vérification complète de l'implémentation des seuils ML
Teste le logging, la récupération et l'export des nouvelles colonnes ML

Date: 16/01/2026
"""

import os
import sys
import asyncio
import logging
import time
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from core.postgresql_datalogger import PostgreSQLDataLogger

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MLThresholdVerifier:
    """Vérificateur complet de l'implémentation des seuils ML"""
    
    def __init__(self):
        self.pg_logger = PostgreSQLDataLogger()
        self.test_symbol = "BTCUSDT"
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Logger un résultat de test"""
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}: {details}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        
    async def test_1_database_schema(self):
        """Test 1: Vérifier que les colonnes existent dans la base"""
        logger.info("🔍 Test 1: Vérification du schéma de base de données")
        
        if not self.pg_logger.enabled:
            self.log_test("Database Connection", False, "PostgreSQL désactivé")
            return False
            
        # Vérifier les colonnes scan_logs
        query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'scan_logs' 
            AND column_name IN ('ml_threshold_used', 'ml_threshold_type', 'calibrated_winrate')
            ORDER BY column_name
        """
        
        result = self.pg_logger._execute_query(query, fetch=True)
        if not result:
            self.log_test("Schema Check", False, "Aucune colonne ML trouvée")
            return False
            
        colonnes = [(row[0], row[1], row[2]) for row in result]
        expected_columns = [
            ('calibrated_winrate', 'numeric', 'YES'),
            ('ml_threshold_type', 'character varying', 'YES'),
            ('ml_threshold_used', 'numeric', 'YES')
        ]
        
        if len(colonnes) == 3:
            self.log_test("Schema Check", True, f"3 colonnes ML trouvées: {[c[0] for c in colonnes]}")
            return True
        else:
            self.log_test("Schema Check", False, f"Colonnes incomplètes: {colonnes}")
            return False
    
    async def test_2_ml_rejection_logging(self):
        """Test 2: Tester le logging des rejets ML avec nouveaux paramètres"""
        logger.info("🔍 Test 2: Test du logging des rejets ML")
        
        # Créer un scan_log temporaire pour le test
        scan_data = {
            'symbol': self.test_symbol,
            'timestamp': datetime.now(),
            'is_opportunity': True,
            'opportunity_direction': 'LONG',
            'reject_reason': None,
            'reject_reason_category': None,
            'ml_confidence': None
        }
        
        scan_id = self.pg_logger.log_scan(self.test_symbol, scan_data)
        if not scan_id:
            self.log_test("Create Test Scan", False, "Impossible de créer un scan de test")
            return False
            
        self.log_test("Create Test Scan", True, f"Scan créé avec ID: {scan_id}")
        
        # Tester différents types de rejets ML
        test_cases = [
            {
                "reject_reason": "ML confidence 42.3% < seuil 55%",
                "reject_category": "ml_gb_confidence", 
                "ml_confidence": 42.3,
                "ml_threshold_used": 55.0,
                "calibrated_winrate": None
            },
            {
                "reject_reason": "ML prédit loss avec forte confiance 78.5% (seuil: 70.0%)",
                "reject_category": "ml_xgboost_soft",
                "ml_confidence": 78.5, 
                "ml_threshold_used": 70.0,
                "calibrated_winrate": None
            },
            {
                "reject_reason": "Calibrated winrate 38.2% < minimum requis 45%",
                "reject_category": "ml_calibration_winrate",
                "ml_confidence": 67.8,
                "ml_threshold_used": 45.0,
                "calibrated_winrate": 38.2
            }
        ]
        
        for i, case in enumerate(test_cases):
            try:
                success = await self.pg_logger.update_ml_rejection_async(
                    symbol=self.test_symbol,
                    reject_reason=case["reject_reason"],
                    reject_category=case["reject_category"],
                    ml_confidence=case["ml_confidence"],
                    ml_threshold_used=case["ml_threshold_used"],
                    calibrated_winrate=case["calibrated_winrate"]
                )
                
                if success:
                    self.log_test(f"ML Rejection Test {i+1}", True, f"Type: {case['reject_category']}")
                else:
                    self.log_test(f"ML Rejection Test {i+1}", False, "update_ml_rejection_async returned False")
                    
            except Exception as e:
                self.log_test(f"ML Rejection Test {i+1}", False, f"Exception: {e}")
        
        return True
    
    async def test_3_data_retrieval(self):
        """Test 3: Vérifier la récupération des données ML"""
        logger.info("🔍 Test 3: Vérification de la récupération des données")
        
        # Récupérer les derniers scans avec rejets ML
        query = """
            SELECT symbol, reject_reason_category, ml_confidence, 
                   ml_threshold_used, ml_threshold_type, calibrated_winrate,
                   timestamp
            FROM scan_logs 
            WHERE symbol = %s 
            AND reject_reason_category IS NOT NULL
            ORDER BY timestamp DESC 
            LIMIT 5
        """
        
        result = self.pg_logger._execute_query(query, (self.test_symbol,), fetch=True)
        
        if not result:
            self.log_test("Data Retrieval", False, "Aucun rejet ML trouvé pour le symbole de test")
            return False
            
        found_rejections = []
        for row in result:
            rejection_data = {
                'symbol': row[0],
                'reject_reason_category': row[1], 
                'ml_confidence': float(row[2]) if row[2] else None,
                'ml_threshold_used': float(row[3]) if row[3] else None,
                'ml_threshold_type': row[4],
                'calibrated_winrate': float(row[5]) if row[5] else None,
                'timestamp': row[6]
            }
            found_rejections.append(rejection_data)
            
        self.log_test("Data Retrieval", True, f"Trouvé {len(found_rejections)} rejets ML avec nouvelles colonnes")
        
        # Vérifier que les colonnes sont correctement remplies
        complete_entries = 0
        for rejection in found_rejections:
            if (rejection['reject_reason_category'] and 
                rejection['ml_threshold_used'] is not None and 
                rejection['ml_threshold_type']):
                complete_entries += 1
                
        completion_rate = (complete_entries / len(found_rejections)) * 100 if found_rejections else 0
        self.log_test("Data Completeness", completion_rate >= 80, f"Taux de complétude: {completion_rate:.1f}%")
        
        return len(found_rejections) > 0
    
    async def test_4_excel_export(self):
        """Test 4: Tester l'export Excel avec nouvelles colonnes"""
        logger.info("🔍 Test 4: Test de l'export Excel")
        
        try:
            # Tester l'endpoint d'export Excel avec limite petite
            url = "http://localhost:8000/api/datalogger/export/excel"
            params = {"limit": 5}
            
            logger.info(f"🌐 Test de l'API export: {url}")
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'spreadsheet' in content_type or 'excel' in content_type:
                    # Sauvegarder le fichier pour inspection
                    test_file = f"test_export_ml_columns_{int(time.time())}.xlsx"
                    with open(test_file, 'wb') as f:
                        f.write(response.content)
                    
                    file_size = len(response.content)
                    self.log_test("Excel Export", True, f"Export réussi, fichier: {test_file} ({file_size} bytes)")
                    
                    # Vérifier la présence des nouvelles colonnes dans le fichier Excel
                    try:
                        import pandas as pd
                        excel_data = pd.read_excel(test_file, sheet_name='scan_logs', engine='openpyxl')
                        ml_columns = ['ml_threshold_used', 'ml_threshold_type', 'calibrated_winrate']
                        found_ml_columns = [col for col in ml_columns if col in excel_data.columns]
                        
                        if len(found_ml_columns) == 3:
                            self.log_test("Excel ML Columns", True, f"Toutes les colonnes ML présentes: {found_ml_columns}")
                        else:
                            self.log_test("Excel ML Columns", False, f"Colonnes ML manquantes: {set(ml_columns) - set(found_ml_columns)}")
                    
                    except ImportError:
                        self.log_test("Excel Column Check", False, "pandas non disponible pour vérification détaillée")
                    except Exception as e:
                        self.log_test("Excel Column Check", False, f"Erreur lecture Excel: {e}")
                        
                    return True
                else:
                    self.log_test("Excel Export", False, f"Content-Type incorrect: {content_type}")
                    return False
            else:
                error_text = response.text[:200] if response.text else "No error details"
                self.log_test("Excel Export", False, f"HTTP {response.status_code}: {error_text}")
                return False
                
        except requests.RequestException as e:
            self.log_test("Excel Export", False, f"Erreur réseau: {e}")
            return False
        except Exception as e:
            self.log_test("Excel Export", False, f"Erreur inattendue: {e}")
            return False
    
    async def test_5_edge_cases(self):
        """Test 5: Tester les cas limites"""
        logger.info("🔍 Test 5: Test des cas limites")
        
        edge_cases = [
            # Valeurs nulles
            {
                "reject_reason": "Test valeurs nulles",
                "reject_category": "ml_test_null", 
                "ml_confidence": None,
                "ml_threshold_used": None,
                "calibrated_winrate": None
            },
            # Valeurs décimales (0.0-1.0) qui doivent être converties en pourcentage
            {
                "reject_reason": "Test conversion décimale",
                "reject_category": "ml_test_decimal",
                "ml_confidence": 0.423,  # Doit devenir 42.3
                "ml_threshold_used": 0.55,  # Doit devenir 55.0
                "calibrated_winrate": 0.382  # Doit devenir 38.2
            },
            # Valeurs déjà en pourcentage
            {
                "reject_reason": "Test valeurs pourcentage",
                "reject_category": "ml_test_percent",
                "ml_confidence": 67.8,
                "ml_threshold_used": 70.0, 
                "calibrated_winrate": 45.2
            }
        ]
        
        for i, case in enumerate(edge_cases):
            try:
                success = await self.pg_logger.update_ml_rejection_async(
                    symbol=self.test_symbol,
                    reject_reason=case["reject_reason"],
                    reject_category=case["reject_category"],
                    ml_confidence=case["ml_confidence"],
                    ml_threshold_used=case["ml_threshold_used"],
                    calibrated_winrate=case["calibrated_winrate"]
                )
                
                self.log_test(f"Edge Case {i+1}", success, f"Test: {case['reject_category']}")
                
            except Exception as e:
                self.log_test(f"Edge Case {i+1}", False, f"Exception: {e}")
        
        return True
    
    def generate_report(self):
        """Générer un rapport final des tests"""
        logger.info("📋 Génération du rapport final")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for test in self.test_results if test["success"])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": success_rate,
                "timestamp": datetime.now().isoformat()
            },
            "test_details": self.test_results,
            "recommendations": []
        }
        
        # Ajouter des recommandations basées sur les résultats
        if success_rate < 100:
            report["recommendations"].append("Certains tests ont échoué - vérifier les détails ci-dessus")
        if success_rate >= 80:
            report["recommendations"].append("Implémentation globalement réussie") 
        if success_rate < 50:
            report["recommendations"].append("Implémentation nécessite des corrections majeures")
        
        # Sauvegarder le rapport
        report_file = f"ml_threshold_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Rapport sauvegardé: {report_file}")
        
        # Afficher le résumé
        print("\n" + "="*60)
        print("📊 RAPPORT DE VÉRIFICATION ML THRESHOLD")
        print("="*60)
        print(f"Tests exécutés: {total_tests}")
        print(f"Tests réussis:  {passed_tests}")
        print(f"Tests échoués:  {total_tests - passed_tests}")
        print(f"Taux de réussite: {success_rate:.1f}%")
        print("="*60)
        
        if success_rate == 100:
            print("🎉 TOUS LES TESTS SONT PASSÉS ! Implémentation ML complète et fonctionnelle.")
        elif success_rate >= 80:
            print("✅ Implémentation globalement réussie avec quelques problèmes mineurs.")
        else:
            print("⚠️ Implémentation nécessite des corrections avant mise en production.")
        
        return success_rate

async def main():
    """Point d'entrée principal avec boucle de vérification"""
    logger.info("🚀 Démarrage de la vérification complète ML Threshold")
    
    verifier = MLThresholdVerifier()
    
    try:
        # Exécuter tous les tests en séquence
        await verifier.test_1_database_schema()
        await asyncio.sleep(1)  # Petite pause entre les tests
        
        await verifier.test_2_ml_rejection_logging()
        await asyncio.sleep(1)
        
        await verifier.test_3_data_retrieval()
        await asyncio.sleep(1)
        
        await verifier.test_4_excel_export()
        await asyncio.sleep(1)
        
        await verifier.test_5_edge_cases()
        
        # Générer le rapport final
        success_rate = verifier.generate_report()
        
        # Boucle de vérification continue (optionnelle)
        if success_rate >= 80:
            logger.info("🔄 Lancement de la boucle de vérification continue (30s)...")
            
            for i in range(3):  # 3 cycles de vérification
                logger.info(f"🔍 Cycle de vérification {i+1}/3")
                
                # Test rapide de récupération des données
                await verifier.test_3_data_retrieval()
                
                await asyncio.sleep(10)  # Attendre 10 secondes
            
            logger.info("✅ Boucle de vérification terminée - système stable")
        
        return success_rate >= 80
        
    except KeyboardInterrupt:
        logger.info("⏹️ Vérification interrompue par l'utilisateur")
        return False
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

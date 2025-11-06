#!/usr/bin/env python3
"""
🧪 TEST DES FONCTIONNALITÉS IMPLÉMENTÉES
Test complet de toutes les améliorations de la Phase 6-8
"""

import asyncio
import sys
import logging
from datetime import datetime
from typing import Dict, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FeatureTester:
    """Testeur de fonctionnalités implémentées"""
    
    def __init__(self):
        self.results = []
    
    def log_test(self, feature: str, test_name: str, passed: bool, details: str = ""):
        """Logger un résultat de test"""
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} | {feature} | {test_name} | {details}")
        self.results.append({
            'feature': feature,
            'test': test_name,
            'passed': passed,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
    
    async def test_recovery_mode_progressive(self):
        """Test Recovery Mode Progressif"""
        logger.info("\n" + "="*60)
        logger.info("TEST 1: RECOVERY MODE PROGRESSIF")
        logger.info("="*60)
        
        try:
            from core.position_manager import PositionManager, PositionConfig
            from config import TRADING_CONFIG
            
            config = PositionConfig()
            manager = PositionManager(config)
            
            # Test 1.1: Mode SIMPLE
            logger.info("\n[1.1] Test mode SIMPLE")
            recovery_config = TRADING_CONFIG.get('recovery_mode', {})
            original_mode = recovery_config.get('mode', 'PROGRESSIVE')
            
            # Forcer mode SIMPLE temporairement
            recovery_config['mode'] = 'SIMPLE'
            level = manager.get_recovery_level(3)
            
            if level and level.get('level') == 1:
                self.log_test("Recovery Mode", "Mode SIMPLE (loss_streak=3)", True, 
                            f"Niveau 1 activé | boost={level.get('min_score_boost')}")
            else:
                self.log_test("Recovery Mode", "Mode SIMPLE (loss_streak=3)", False, 
                            "Niveau non activé correctement")
            
            # Test 1.2: Mode PROGRESSIVE - Niveau 1 (2 losses)
            logger.info("\n[1.2] Test mode PROGRESSIVE - Niveau 1")
            recovery_config['mode'] = 'PROGRESSIVE'
            level1 = manager.get_recovery_level(2)
            
            if level1 and level1.get('level') == 1:
                self.log_test("Recovery Mode", "PROGRESSIVE Niveau 1 (loss_streak=2)", True,
                            f"boost={level1.get('min_score_boost')}, réduction={level1.get('position_size_reduction')}")
            else:
                self.log_test("Recovery Mode", "PROGRESSIVE Niveau 1 (loss_streak=2)", False,
                            "Niveau 1 non activé")
            
            # Test 1.3: Mode PROGRESSIVE - Niveau 2 (3 losses)
            logger.info("\n[1.3] Test mode PROGRESSIVE - Niveau 2")
            level2 = manager.get_recovery_level(3)
            
            if level2 and level2.get('level') == 2:
                self.log_test("Recovery Mode", "PROGRESSIVE Niveau 2 (loss_streak=3)", True,
                            f"boost={level2.get('min_score_boost')}, réduction={level2.get('position_size_reduction')}")
            else:
                self.log_test("Recovery Mode", "PROGRESSIVE Niveau 2 (loss_streak=3)", False,
                            "Niveau 2 non activé")
            
            # Test 1.4: Mode PROGRESSIVE - Niveau 3 (5 losses)
            logger.info("\n[1.4] Test mode PROGRESSIVE - Niveau 3")
            level3 = manager.get_recovery_level(5)
            
            if level3 and level3.get('level') == 3:
                confluence_forced = level3.get('confluence_forced', False)
                self.log_test("Recovery Mode", "PROGRESSIVE Niveau 3 (loss_streak=5)", True,
                            f"boost={level3.get('min_score_boost')}, réduction={level3.get('position_size_reduction')}, confluence={confluence_forced}")
            else:
                self.log_test("Recovery Mode", "PROGRESSIVE Niveau 3 (loss_streak=5)", False,
                            "Niveau 3 non activé")
            
            # Restaurer mode original
            recovery_config['mode'] = original_mode
            
        except Exception as e:
            logger.error(f"Erreur test Recovery Mode: {e}")
            self.log_test("Recovery Mode", "Test global", False, str(e))
    
    async def test_seuils_adaptatifs_atr(self):
        """Test Seuils Adaptatifs ATR"""
        logger.info("\n" + "="*60)
        logger.info("TEST 2: SEUILS ADAPTATIFS ATR")
        logger.info("="*60)
        
        try:
            from core.position_manager import PositionManager, PositionConfig, Position
            
            config = PositionConfig()
            manager = PositionManager(config)
            
            # Créer une position test avec ATR faible
            logger.info("\n[2.1] Test ATR faible (0.2%)")
            position_low_atr = Position(
                symbol="TEST_USDT",
                direction="LONG",
                entry=10000.0,
                sl=9975.0,
                tp=10025.0,
                size=100.0,
                atr=20.0,  # ATR = 0.2%
                timestamp=datetime.now().timestamp()
            )
            manager.active_position = position_low_atr
            
            threshold_low = manager.get_adaptive_early_threshold(15)
            
            # ATR < 0.3% → multiplier 0.7 → seuil moins strict
            expected_low = -0.12 * 0.7  # -0.084%
            if abs(threshold_low - expected_low) < 0.01:
                self.log_test("Seuils Adaptatifs", "ATR faible (0.2%)", True,
                            f"Seuil adapté: {threshold_low:.3f}% (base: -0.12%, mult: 0.7)")
            else:
                self.log_test("Seuils Adaptatifs", "ATR faible (0.2%)", False,
                            f"Attendu: {expected_low:.3f}%, obtenu: {threshold_low:.3f}%")
            
            # Créer une position test avec ATR élevé
            logger.info("\n[2.2] Test ATR élevé (1.0%)")
            position_high_atr = Position(
                symbol="TEST_USDT",
                direction="LONG",
                entry=10000.0,
                sl=9975.0,
                tp=10025.0,
                size=100.0,
                atr=100.0,  # ATR = 1.0%
                timestamp=datetime.now().timestamp()
            )
            manager.active_position = position_high_atr
            
            threshold_high = manager.get_adaptive_early_threshold(15)
            
            # ATR > 0.8% → multiplier 1.3 → seuil plus strict
            # Mais borné à max -0.15%
            expected_high = max(-0.15, -0.12 * 1.3)  # -0.15% (borné)
            if abs(threshold_high - expected_high) < 0.01:
                self.log_test("Seuils Adaptatifs", "ATR élevé (1.0%)", True,
                            f"Seuil adapté: {threshold_high:.3f}% (base: -0.12%, mult: 1.3, borné)")
            else:
                self.log_test("Seuils Adaptatifs", "ATR élevé (1.0%)", False,
                            f"Attendu: {expected_high:.3f}%, obtenu: {threshold_high:.3f}%")
            
            # Test ATR normal
            logger.info("\n[2.3] Test ATR normal (0.5%)")
            position_normal_atr = Position(
                symbol="TEST_USDT",
                direction="LONG",
                entry=10000.0,
                sl=9975.0,
                tp=10025.0,
                size=100.0,
                atr=50.0,  # ATR = 0.5%
                timestamp=datetime.now().timestamp()
            )
            manager.active_position = position_normal_atr
            
            threshold_normal = manager.get_adaptive_early_threshold(15)
            
            # ATR normal → multiplier 1.0 → seuil standard
            if abs(threshold_normal - (-0.12)) < 0.01:
                self.log_test("Seuils Adaptatifs", "ATR normal (0.5%)", True,
                            f"Seuil standard: {threshold_normal:.3f}% (mult: 1.0)")
            else:
                self.log_test("Seuils Adaptatifs", "ATR normal (0.5%)", False,
                            f"Attendu: -0.12%, obtenu: {threshold_normal:.3f}%")
            
        except Exception as e:
            logger.error(f"Erreur test Seuils Adaptatifs: {e}")
            self.log_test("Seuils Adaptatifs", "Test global", False, str(e))
    
    async def test_position_sizing_adaptatif(self):
        """Test Position Sizing Adaptatif"""
        logger.info("\n" + "="*60)
        logger.info("TEST 3: POSITION SIZING ADAPTATIF")
        logger.info("="*60)
        
        try:
            from core.position_manager import PositionManager, PositionConfig
            
            config = PositionConfig()
            manager = PositionManager(config)
            capital = 1000.0
            sl_percent = 0.25
            
            # Test 3.1: Setup EXCELLENT (score ≥ 12)
            logger.info("\n[3.1] Setup EXCELLENT (score=12)")
            setup_excellent = {'totalScore': 12.0, 'symbol': 'TEST_USDT'}
            size_excellent = manager.calculate_adaptive_position_size(setup_excellent, capital, sl_percent)
            
            # Base = 20 USDT (2%), excellent = 1.4x = 28 USDT
            expected_range = (25, 30)
            if expected_range[0] <= size_excellent <= expected_range[1]:
                self.log_test("Position Sizing", "Setup EXCELLENT (score=12)", True,
                            f"Taille: {size_excellent:.2f} USDT (mult: 1.4)")
            else:
                self.log_test("Position Sizing", "Setup EXCELLENT (score=12)", False,
                            f"Attendu: {expected_range}, obtenu: {size_excellent:.2f}")
            
            # Test 3.2: Setup GOOD (score ≥ 10)
            logger.info("\n[3.2] Setup GOOD (score=10)")
            setup_good = {'totalScore': 10.0, 'symbol': 'TEST_USDT'}
            size_good = manager.calculate_adaptive_position_size(setup_good, capital, sl_percent)
            
            # Base = 20 USDT (2%), good = 1.2x = 24 USDT
            expected_range = (22, 26)
            if expected_range[0] <= size_good <= expected_range[1]:
                self.log_test("Position Sizing", "Setup GOOD (score=10)", True,
                            f"Taille: {size_good:.2f} USDT (mult: 1.2)")
            else:
                self.log_test("Position Sizing", "Setup GOOD (score=10)", False,
                            f"Attendu: {expected_range}, obtenu: {size_good:.2f}")
            
            # Test 3.3: Setup WEAK (score < 8)
            logger.info("\n[3.3] Setup WEAK (score=7)")
            setup_weak = {'totalScore': 7.0, 'symbol': 'TEST_USDT'}
            size_weak = manager.calculate_adaptive_position_size(setup_weak, capital, sl_percent)
            
            # Base = 20 USDT (2%), weak = 0.8x = 16 USDT
            expected_range = (15, 18)
            if expected_range[0] <= size_weak <= expected_range[1]:
                self.log_test("Position Sizing", "Setup WEAK (score=7)", True,
                            f"Taille: {size_weak:.2f} USDT (mult: 0.8)")
            else:
                self.log_test("Position Sizing", "Setup WEAK (score=7)", False,
                            f"Attendu: {expected_range}, obtenu: {size_weak:.2f}")
            
            # Test 3.4: Loss Streak (réduction)
            logger.info("\n[3.4] Loss Streak (réduction)")
            config.loss_streak = 2
            setup_normal = {'totalScore': 10.0, 'symbol': 'TEST_USDT'}
            size_streak = manager.calculate_adaptive_position_size(setup_normal, capital, sl_percent)
            
            # Base = 20 USDT, good = 1.2x, streak = 0.85x → 20.4 USDT
            expected_range = (18, 22)
            if expected_range[0] <= size_streak <= expected_range[1]:
                self.log_test("Position Sizing", "Loss Streak (loss_streak=2)", True,
                            f"Taille: {size_streak:.2f} USDT (streak mult: 0.85)")
            else:
                self.log_test("Position Sizing", "Loss Streak (loss_streak=2)", False,
                            f"Attendu: {expected_range}, obtenu: {size_streak:.2f}")
            
        except Exception as e:
            logger.error(f"Erreur test Position Sizing: {e}")
            self.log_test("Position Sizing", "Test global", False, str(e))
    
    async def test_correlation_filter(self):
        """Test Correlation Filter (Static)"""
        logger.info("\n" + "="*60)
        logger.info("TEST 4: CORRELATION FILTER (STATIC)")
        logger.info("="*60)
        
        try:
            from core.analyzer import TechnicalAnalyzer
            from config import TRADING_CONFIG
            
            analyzer = TechnicalAnalyzer()
            
            # Test 4.1: Mode SOFT - Pénalité
            logger.info("\n[4.1] Mode SOFT avec corrélation")
            correlation_config = TRADING_CONFIG.get('correlation_filter', {})
            original_mode = correlation_config.get('mode', 'SOFT')
            
            correlation_config['mode'] = 'SOFT'
            correlation_config['enabled'] = True
            
            # BTC avec ETH active (même groupe BTC_GROUP)
            active_positions = ['ETH/USDT:USDT']
            result_soft = await analyzer._check_correlation('BTC/USDT:USDT', active_positions)
            
            if result_soft.get('valid') and result_soft.get('penalty', 0) < 0:
                self.log_test("Correlation Filter", "Mode SOFT avec pénalité", True,
                            f"Pénalité: {result_soft['penalty']}, groupe: {result_soft.get('group')}")
            else:
                self.log_test("Correlation Filter", "Mode SOFT avec pénalité", False,
                            f"Attendu pénalité < 0, obtenu: {result_soft}")
            
            # Test 4.2: Mode HARD - Rejet
            logger.info("\n[4.2] Mode HARD avec corrélation")
            correlation_config['mode'] = 'HARD'
            correlation_config['max_positions_per_group'] = 1
            
            result_hard = await analyzer._check_correlation('BTC/USDT:USDT', active_positions)
            
            if not result_hard.get('valid'):
                self.log_test("Correlation Filter", "Mode HARD avec rejet", True,
                            f"Rejeté: {result_hard.get('reason')}")
            else:
                self.log_test("Correlation Filter", "Mode HARD avec rejet", False,
                            f"Attendu rejet, obtenu: {result_hard}")
            
            # Test 4.3: Pas de corrélation
            logger.info("\n[4.3] Pas de corrélation")
            active_positions_no_corr = ['DOGE/USDT:USDT']  # MEME_GROUP
            result_no_corr = await analyzer._check_correlation('BTC/USDT:USDT', active_positions_no_corr)
            
            if result_no_corr.get('valid') and result_no_corr.get('penalty', 0) == 0:
                self.log_test("Correlation Filter", "Pas de corrélation", True,
                            "Aucune pénalité/rejet")
            else:
                self.log_test("Correlation Filter", "Pas de corrélation", False,
                            f"Attendu valide sans pénalité, obtenu: {result_no_corr}")
            
            # Restaurer mode original
            correlation_config['mode'] = original_mode
            
        except Exception as e:
            logger.error(f"Erreur test Correlation Filter: {e}")
            self.log_test("Correlation Filter", "Test global", False, str(e))
    
    async def test_database_sqlite(self):
        """Test Database SQLite"""
        logger.info("\n" + "="*60)
        logger.info("TEST 5: DATABASE SQLITE")
        logger.info("="*60)
        
        try:
            from core.database import TradeDatabase
            import tempfile
            import os
            
            # Créer DB temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
                db_path = tmp.name
            
            logger.info(f"\n[5.1] Initialisation DB: {db_path}")
            db = TradeDatabase(db_path)
            
            if db.conn:
                self.log_test("Database SQLite", "Initialisation", True, f"DB créée: {db_path}")
            else:
                self.log_test("Database SQLite", "Initialisation", False, "Connexion None")
                return
            
            # Test 5.2: Insertion trade
            logger.info("\n[5.2] Insertion trade")
            test_trade = {
                'timestamp': '2025-01-06T12:00:00',
                'date': '2025-01-06',
                'time': '12:00:00',
                'symbol': 'BTC/USDT:USDT',
                'direction': 'LONG',
                'entry': 45000.0,
                'exit': 45250.0,
                'gross_pnl_pct': 0.55,
                'gross_pnl_usdt': 5.5,
                'net_pnl_pct': 0.50,
                'net_pnl_usdt': 5.0,
                'fees': 0.04,
                'slippage': 0.01,
                'total_costs': 0.05,
                'reason': 'TP',
                'duration': 120,
                'condition_types': ['EMAs', 'MACD', 'RSI']
            }
            
            trade_id = db.insert_trade(test_trade)
            if trade_id > 0:
                self.log_test("Database SQLite", "Insertion trade", True, f"ID: {trade_id}")
            else:
                self.log_test("Database SQLite", "Insertion trade", False, f"ID invalide: {trade_id}")
            
            # Test 5.3: Récupération trade
            logger.info("\n[5.3] Récupération trade")
            trades = db.get_all_trades()
            
            if len(trades) == 1 and trades[0].get('symbol') == 'BTC/USDT:USDT':
                self.log_test("Database SQLite", "Récupération trade", True, f"{len(trades)} trade(s)")
            else:
                self.log_test("Database SQLite", "Récupération trade", False, 
                            f"Attendu 1 trade BTC, obtenu: {len(trades)}")
            
            # Test 5.4: Filtrage par date
            logger.info("\n[5.4] Filtrage par date")
            trades_by_date = db.get_trades_by_date_range('2025-01-06', '2025-01-06')
            
            if len(trades_by_date) == 1:
                self.log_test("Database SQLite", "Filtrage par date", True, 
                            f"{len(trades_by_date)} trade(s) trouvé(s)")
            else:
                self.log_test("Database SQLite", "Filtrage par date", False,
                            f"Attendu 1, obtenu: {len(trades_by_date)}")
            
            # Cleanup
            db.close()
            os.unlink(db_path)
            
        except Exception as e:
            logger.error(f"Erreur test Database SQLite: {e}")
            self.log_test("Database SQLite", "Test global", False, str(e))
    
    async def test_metrics_par_condition(self):
        """Test Métriques par Condition"""
        logger.info("\n" + "="*60)
        logger.info("TEST 6: MÉTRIQUES PAR CONDITION")
        logger.info("="*60)
        
        try:
            from core.metrics import ConditionMetrics
            
            logger.info("\n[6.1] Enregistrement trades")
            metrics = ConditionMetrics()
            
            # Enregistrer trades gagnants
            metrics.record_trade(['EMAs', 'MACD'], won=True)
            metrics.record_trade(['EMAs', 'RSI'], won=True)
            metrics.record_trade(['EMAs', 'MACD', 'ADX_DI'], won=True)
            
            # Enregistrer trade perdant
            metrics.record_trade(['EMAs', 'Pattern'], won=False)
            
            # Vérifier stats EMAs
            emas_stats = metrics.condition_stats.get('EMAs')
            if emas_stats and emas_stats['total'] == 4 and emas_stats['wins'] == 3:
                winrate = emas_stats['winrate']
                self.log_test("Métriques", "Stats EMAs", True,
                            f"Total: {emas_stats['total']}, Wins: {emas_stats['wins']}, Winrate: {winrate:.1f}%")
            else:
                self.log_test("Métriques", "Stats EMAs", False,
                            f"Stats incorrectes: {emas_stats}")
            
            # Test 6.2: Meilleures conditions
            logger.info("\n[6.2] Meilleures conditions")
            best = metrics.get_best_conditions(min_samples=2)
            
            if len(best) > 0:
                top_condition = best[0]
                self.log_test("Métriques", "Meilleures conditions", True,
                            f"Top: {top_condition['condition']} ({top_condition['winrate']:.1f}%)")
            else:
                self.log_test("Métriques", "Meilleures conditions", False,
                            "Aucune condition trouvée")
            
            # Test 6.3: Pires conditions
            logger.info("\n[6.3] Pires conditions")
            worst = metrics.get_worst_conditions(min_samples=1)
            
            if len(worst) > 0:
                self.log_test("Métriques", "Pires conditions", True,
                            f"{len(worst)} condition(s) trouvée(s)")
            else:
                self.log_test("Métriques", "Pires conditions", False,
                            "Aucune condition trouvée")
            
        except Exception as e:
            logger.error(f"Erreur test Métriques: {e}")
            self.log_test("Métriques", "Test global", False, str(e))
    
    def generate_report(self):
        """Générer rapport de test"""
        logger.info("\n" + "="*60)
        logger.info("RAPPORT DE TEST")
        logger.info("="*60)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed
        
        logger.info(f"\nTotal tests: {total}")
        logger.info(f"✅ Passed: {passed} ({passed/total*100:.1f}%)")
        logger.info(f"❌ Failed: {failed} ({failed/total*100:.1f}%)")
        
        if failed > 0:
            logger.info("\n❌ Tests échoués:")
            for result in self.results:
                if not result['passed']:
                    logger.info(f"  - {result['feature']} | {result['test']}")
                    if result['details']:
                        logger.info(f"    Details: {result['details']}")
        
        return self.results
    
    async def run_all_tests(self):
        """Exécuter tous les tests"""
        logger.info("="*60)
        logger.info("🧪 DÉBUT DES TESTS DES FONCTIONNALITÉS")
        logger.info("="*60)
        
        try:
            await self.test_recovery_mode_progressive()
            await self.test_seuils_adaptatifs_atr()
            await self.test_position_sizing_adaptatif()
            await self.test_correlation_filter()
            await self.test_database_sqlite()
            await self.test_metrics_par_condition()
        except Exception as e:
            logger.error(f"Erreur globale: {e}")
        
        return self.generate_report()


async def main():
    """Point d'entrée principal"""
    tester = FeatureTester()
    results = await tester.run_all_tests()
    
    # Sauvegarder résultats
    import json
    with open('test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\n✅ Résultats sauvegardés dans test_results.json")


if __name__ == "__main__":
    asyncio.run(main())


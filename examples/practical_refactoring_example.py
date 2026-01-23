#!/usr/bin/env python3
"""
Exemple Pratique - Refactorisation Sécurisée en Action
Démontre l'utilisation réelle de la refactorisation avec migration progressive
"""

import asyncio
import time
import logging
from typing import Dict, Any, List
from dataclasses import dataclass

# Imports refactorisation
from core.feature_flags import (
    get_feature_flags_manager, 
    enable_flag, 
    disable_flag, 
    is_flag_enabled
)
from core.factories.position_manager_factory import PositionManagerFactory
from core.interfaces.position_manager_interface import PositionSetup, PositionManagerConfig
from core.interfaces.analyzer_interface import AnalyzerConfig
from core.implementations.testable_analyzer import TestableAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class TradingSession:
    """Session de trading avec métriques"""
    session_id: str
    start_time: float
    positions_opened: int = 0
    positions_closed: int = 0
    total_pnl: float = 0.0
    errors: List[str] = None
    legacy_mode: bool = True
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class PracticalRefactoringDemo:
    """
    Démo pratique de la refactorisation sécurisée
    
    Simule un environnement trading réel avec:
    - Migration progressive
    - Monitoring performance  
    - Rollback automatique
    - Comparaison legacy vs nouveau
    """
    
    def __init__(self):
        self.fm = get_feature_flags_manager()
        self.sessions: Dict[str, TradingSession] = {}
        self.performance_metrics = {
            'legacy': {'total_time': 0, 'operations': 0, 'errors': 0},
            'testable': {'total_time': 0, 'operations': 0, 'errors': 0}
        }
        
        logger.info("🚀 PracticalRefactoringDemo initialisé")
    
    def simulate_production_environment(self):
        """Simuler environnement production avec données réalistes"""
        
        print("=" * 60)
        print("🏭 SIMULATION ENVIRONNEMENT PRODUCTION")
        print("=" * 60)
        
        # Phase 1: Mode 100% Legacy (baseline)
        print("\n📊 Phase 1: Baseline Legacy (5 minutes)")
        self._run_trading_simulation("phase1_legacy", legacy_mode=True, duration_minutes=0.5)
        
        # Phase 2: Migration 10% Testable
        print("\n📈 Phase 2: Migration 10% Testable")
        enable_flag('use_testable_position_manager', 10.0)
        self._run_trading_simulation("phase2_10pct", mixed_mode=True, duration_minutes=0.5)
        
        # Phase 3: Migration 50% Testable
        print("\n🚀 Phase 3: Migration 50% Testable") 
        enable_flag('use_testable_position_manager', 50.0)
        self._run_trading_simulation("phase3_50pct", mixed_mode=True, duration_minutes=0.5)
        
        # Phase 4: Migration 100% Testable
        print("\n✨ Phase 4: Migration 100% Testable")
        enable_flag('use_testable_position_manager', 100.0)
        self._run_trading_simulation("phase4_100pct", legacy_mode=False, duration_minutes=0.5)
        
        # Rapport final
        self._generate_final_report()
    
    def _run_trading_simulation(self, session_id: str, legacy_mode: bool = None, mixed_mode: bool = False, duration_minutes: float = 1.0):
        """Simuler session trading"""
        
        session = TradingSession(
            session_id=session_id,
            start_time=time.time(),
            legacy_mode=legacy_mode if legacy_mode is not None else True
        )
        
        # Symboles réalistes pour tests
        symbols = [
            'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 
            'AVAX/USDT:USDT', 'MATIC/USDT:USDT', 'DOT/USDT:USDT',
            'ADA/USDT:USDT', 'LINK/USDT:USDT'
        ]
        
        # Configurations réalistes
        configs = [
            {'direction': 'LONG', 'risk': 1.5, 'loss_streak': 0},
            {'direction': 'SHORT', 'risk': 2.0, 'loss_streak': 1},
            {'direction': 'LONG', 'risk': 2.5, 'loss_streak': 2},  # Recovery mode
            {'direction': 'SHORT', 'risk': 1.0, 'loss_streak': 3}, # Recovery mode
            {'direction': 'LONG', 'risk': 3.0, 'loss_streak': 0}
        ]
        
        operations_count = int(30 * duration_minutes)  # 30 opérations par minute
        start_time = time.time()
        
        print(f"   🔄 Exécution {operations_count} opérations...")
        
        for i in range(operations_count):
            # Sélection aléatoire 
            symbol = symbols[i % len(symbols)]
            config = configs[i % len(configs)]
            
            try:
                # Déterminer mode (legacy/testable/mixed)
                if mixed_mode:
                    use_testable = is_flag_enabled('use_testable_position_manager', f"user_{i}")
                else:
                    use_testable = not legacy_mode
                
                # Test complet: Analyze + Position
                success = self._execute_trade_operation(
                    symbol, config, use_testable, session
                )
                
                if success:
                    session.positions_opened += 1
                    session.total_pnl += self._simulate_pnl()
                
            except Exception as e:
                session.errors.append(f"Operation {i}: {str(e)}")
                self._track_error(use_testable, str(e))
        
        # Finaliser session
        session_duration = time.time() - start_time
        session.positions_closed = session.positions_opened  # Simplifié
        
        self.sessions[session_id] = session
        
        print(f"   ⏱️  Durée: {session_duration:.2f}s")
        print(f"   📈 Positions: {session.positions_opened}")
        print(f"   💰 PnL: {session.total_pnl:.2f} USDT")
        print(f"   ❌ Erreurs: {len(session.errors)}")
        
        # Métriques performance
        mode = 'legacy' if (legacy_mode and not mixed_mode) else 'testable'
        if not mixed_mode:
            self.performance_metrics[mode]['total_time'] += session_duration
            self.performance_metrics[mode]['operations'] += operations_count
            self.performance_metrics[mode]['errors'] += len(session.errors)
    
    def _execute_trade_operation(self, symbol: str, config: Dict, use_testable: bool, session: TradingSession) -> bool:
        """Exécuter opération complète trading"""
        
        operation_start = time.time()
        
        try:
            # 1. Analysis Phase
            analyzer_result = self._run_analysis(symbol, config, use_testable)
            if not analyzer_result['success']:
                return False
            
            # 2. Position Management Phase  
            pm_result = self._run_position_management(analyzer_result['setup'], use_testable)
            if not pm_result['success']:
                return False
            
            # 3. Track performance
            operation_time = time.time() - operation_start
            mode = 'testable' if use_testable else 'legacy'
            
            if mode in self.performance_metrics:
                self.performance_metrics[mode]['total_time'] += operation_time
                self.performance_metrics[mode]['operations'] += 1
            
            return True
            
        except Exception as e:
            self._track_error(use_testable, str(e))
            return False
    
    def _run_analysis(self, symbol: str, config: Dict, use_testable: bool) -> Dict:
        """Phase analyse"""
        
        if use_testable:
            # Utiliser TestableAnalyzer
            analyzer_config = AnalyzerConfig(test_mode=True)
            analyzer = TestableAnalyzer(analyzer_config)
            analyzer.test_mode = True
            
            # Mock data réaliste
            mock_data = self._generate_realistic_market_data(symbol, config)
            
            async def analyze():
                return await analyzer.analyze_pair_testable(symbol, mock_data)
            
            result = asyncio.run(analyze())
            
            if result.success and result.setup:
                return {
                    'success': True,
                    'setup': {
                        'symbol': result.setup.symbol,
                        'direction': result.setup.direction,
                        'entry_price': result.setup.entry_price,
                        'sl_price': result.setup.sl_price,
                        'tp_price': result.setup.tp_price,
                        'atr': result.setup.atr,
                        'score': result.setup.total_score,
                        'risk_per_trade': config['risk'],
                        'loss_streak': config['loss_streak']
                    }
                }
            else:
                return {'success': False, 'reason': result.reason}
        else:
            # Simuler legacy analyzer (mock)
            time.sleep(0.001)  # Simule latence legacy
            
            if self._should_simulate_opportunity(config):
                return {
                    'success': True,
                    'setup': self._generate_legacy_setup(symbol, config)
                }
            else:
                return {'success': False, 'reason': 'No opportunity (legacy)'}
    
    def _run_position_management(self, setup: Dict, use_testable: bool) -> Dict:
        """Phase gestion position"""
        
        try:
            # Factory avec mode approprié
            pm = PositionManagerFactory.create(testing_mode=use_testable)
            
            # Convertir setup si nécessaire
            if use_testable:
                from core.interfaces.position_manager_interface import setup_from_dict
                pos_setup = setup_from_dict(setup)
            else:
                pos_setup = setup  # Legacy format
            
            # Calculs position
            size = pm.calculate_position_size(pos_setup, 1000.0)  # 1000 USDT capital
            
            if size > 0:
                # Simuler ouverture
                if use_testable:
                    result = pm.open_position(pos_setup)
                    return {'success': result.success, 'size': result.position_size}
                else:
                    # Mock legacy open
                    return {'success': True, 'size': size}
            else:
                return {'success': False, 'reason': 'Invalid position size'}
                
        except Exception as e:
            return {'success': False, 'reason': str(e)}
    
    def _generate_realistic_market_data(self, symbol: str, config: Dict) -> Dict:
        """Générer données marché réalistes"""
        
        # Prix de base selon symbole
        base_prices = {
            'BTC/USDT:USDT': 45000.0,
            'ETH/USDT:USDT': 3000.0,
            'SOL/USDT:USDT': 100.0,
            'AVAX/USDT:USDT': 35.0,
            'MATIC/USDT:USDT': 1.2,
            'DOT/USDT:USDT': 8.0,
            'ADA/USDT:USDT': 0.5,
            'LINK/USDT:USDT': 15.0
        }
        
        base_price = base_prices.get(symbol, 100.0)
        atr = base_price * 0.015  # 1.5% ATR typical
        
        # Score variable selon config
        base_score = 75.0
        if config['loss_streak'] >= 3:
            base_score += 10.0  # Recovery boost
        if config['direction'] == 'LONG':
            base_score += 5.0   # Slight LONG bias
        
        # Variability
        import random
        score_variation = random.uniform(-10, 15)
        final_score = max(60, min(95, base_score + score_variation))
        
        return {
            'base_score': final_score,
            'direction': config['direction'],
            'entry_price': base_price,
            'sl_price': base_price * (0.98 if config['direction'] == 'LONG' else 1.02),
            'tp_price': base_price * (1.03 if config['direction'] == 'LONG' else 0.97),
            'atr': atr,
            'spread_pct': random.uniform(0.005, 0.025),  # 0.5% - 2.5%
            'volume_ratio': random.uniform(1.2, 3.0),
            'loss_streak': config['loss_streak'],
            'manipulation_score': random.uniform(0.05, 0.3),
            'liquidity_ratio': random.uniform(1.5, 4.0)
        }
    
    def _generate_legacy_setup(self, symbol: str, config: Dict) -> Dict:
        """Générer setup legacy format"""
        
        market_data = self._generate_realistic_market_data(symbol, config)
        
        return {
            'symbol': symbol,
            'direction': config['direction'],
            'entry_price': market_data['entry_price'],
            'entry': market_data['entry_price'],
            'sl_price': market_data['sl_price'], 
            'sl': market_data['sl_price'],
            'tp_price': market_data['tp_price'],
            'tp': market_data['tp_price'],
            'atr': market_data['atr'],
            'score': market_data['base_score'],
            'totalScore': market_data['base_score'],
            'risk_per_trade': config['risk'],
            'loss_streak': config['loss_streak']
        }
    
    def _should_simulate_opportunity(self, config: Dict) -> bool:
        """Simuler si opportunity détectée (70% chance)"""
        import random
        base_chance = 0.7
        
        # Recovery mode = plus de chances
        if config['loss_streak'] >= 2:
            base_chance += 0.15
        
        return random.random() < base_chance
    
    def _simulate_pnl(self) -> float:
        """Simuler PnL réaliste"""
        import random
        
        # Distribution PnL réaliste (légèrement négative en moyenne)
        outcomes = [
            # Grands gains (15%)
            *[random.uniform(50, 200) for _ in range(15)],
            # Petits gains (25%) 
            *[random.uniform(5, 50) for _ in range(25)],
            # Petites pertes (35%)
            *[random.uniform(-50, -5) for _ in range(35)],
            # Grandes pertes/SL (25%)
            *[random.uniform(-100, -50) for _ in range(25)]
        ]
        
        return random.choice(outcomes)
    
    def _track_error(self, use_testable: bool, error: str):
        """Tracker erreurs pour métriques"""
        mode = 'testable' if use_testable else 'legacy'
        if mode in self.performance_metrics:
            self.performance_metrics[mode]['errors'] += 1
            
        # Auto-rollback si trop d'erreurs testable
        if use_testable:
            error_rate = self.performance_metrics['testable']['errors'] / max(1, self.performance_metrics['testable']['operations'])
            if error_rate > 0.1:  # 10% erreurs max
                print(f"⚠️ ERROR RATE CRITIQUE: {error_rate:.3f} - Rollback recommandé")
    
    def _generate_final_report(self):
        """Générer rapport final de migration"""
        
        print("\n" + "=" * 60)
        print("📊 RAPPORT FINAL DE MIGRATION")
        print("=" * 60)
        
        # Résumé sessions
        print("\n🔍 Résumé des Sessions:")
        for session_id, session in self.sessions.items():
            duration = time.time() - session.start_time if session_id == list(self.sessions.keys())[-1] else 60.0
            ops_per_sec = session.positions_opened / duration if duration > 0 else 0
            error_rate = len(session.errors) / max(1, session.positions_opened)
            
            print(f"  {session_id}:")
            print(f"    📈 Positions: {session.positions_opened}")
            print(f"    ⚡ Ops/sec: {ops_per_sec:.2f}")
            print(f"    💰 PnL: {session.total_pnl:.2f} USDT")
            print(f"    ❌ Error Rate: {error_rate:.3f}")
        
        # Comparaison performance
        print("\n⚖️ Comparaison Performance:")
        
        legacy_metrics = self.performance_metrics['legacy']
        testable_metrics = self.performance_metrics['testable']
        
        if legacy_metrics['operations'] > 0 and testable_metrics['operations'] > 0:
            legacy_avg_time = legacy_metrics['total_time'] / legacy_metrics['operations']
            testable_avg_time = testable_metrics['total_time'] / testable_metrics['operations']
            
            legacy_error_rate = legacy_metrics['errors'] / legacy_metrics['operations']
            testable_error_rate = testable_metrics['errors'] / testable_metrics['operations']
            
            performance_delta = ((testable_avg_time - legacy_avg_time) / legacy_avg_time) * 100
            
            print(f"  Legacy:")
            print(f"    ⏱️ Temps moyen: {legacy_avg_time:.6f}s")
            print(f"    🔢 Opérations: {legacy_metrics['operations']}")
            print(f"    ❌ Taux erreur: {legacy_error_rate:.4f}")
            
            print(f"  Testable:")
            print(f"    ⏱️ Temps moyen: {testable_avg_time:.6f}s")  
            print(f"    🔢 Opérations: {testable_metrics['operations']}")
            print(f"    ❌ Taux erreur: {testable_error_rate:.4f}")
            
            print(f"\n📈 Delta Performance: {performance_delta:+.2f}%")
            
            if performance_delta < 10:
                print("✅ Performance acceptable")
            else:
                print("⚠️ Performance dégradée - Optimisation requise")
        
        # Recommandations
        print("\n🎯 Recommandations:")
        
        total_errors = sum(len(s.errors) for s in self.sessions.values())
        total_positions = sum(s.positions_opened for s in self.sessions.values())
        global_error_rate = total_errors / max(1, total_positions)
        
        if global_error_rate < 0.05:
            print("  ✅ Migration réussie - Taux erreur acceptable")
            print("  🚀 Recommandation: Déployer en production")
        elif global_error_rate < 0.10:
            print("  ⚠️ Migration acceptable avec surveillance")
            print("  👀 Recommandation: Monitoring renforcé")
        else:
            print("  ❌ Migration problématique")
            print("  🔙 Recommandation: Rollback et investigation")
        
        # Flag status final
        print(f"\n🏁 Status Final Feature Flags:")
        for flag_name in ['use_testable_position_manager', 'use_testable_analyzer']:
            status = self.fm.get_flag_status(flag_name)
            print(f"  {flag_name}: {status['rollout_percentage']:.1f}% ({'✅ ON' if status['enabled'] else '❌ OFF'})")


def demo_emergency_rollback():
    """Démonstration rollback d'urgence"""
    
    print("\n" + "=" * 60)
    print("🚨 DÉMONSTRATION ROLLBACK D'URGENCE")
    print("=" * 60)
    
    fm = get_feature_flags_manager()
    
    # Activer flag
    print("\n1️⃣ Activation flag testable...")
    enable_flag('use_testable_position_manager', 100.0)
    print(f"   Status: {is_flag_enabled('use_testable_position_manager')}")
    
    # Simuler problème critique
    print("\n2️⃣ Simulation problème critique...")
    
    # Métriques critiques
    fm.update_metrics('use_testable_position_manager', {
        'error_rate': 0.15,      # 15% erreurs (> 5% limite)
        'success_rate': 0.80,    # 80% succès (< 95% limite)
        'performance_delta': -0.30  # -30% performance (< -20% limite)
    })
    
    print("   ❌ Error rate: 15% (limite: 5%)")
    print("   ❌ Success rate: 80% (limite: 95%)")  
    print("   ❌ Performance: -30% (limite: -20%)")
    
    # Vérifier rollback automatique
    print("\n3️⃣ Vérification rollback automatique...")
    
    # Le système devrait détecter et rollback
    time.sleep(0.1)  # Laisser temps au système
    
    final_status = is_flag_enabled('use_testable_position_manager')
    print(f"   Status après métriques: {final_status}")
    
    if not final_status:
        print("   ✅ ROLLBACK AUTOMATIQUE RÉUSSI!")
    else:
        print("   ⚠️ Rollback manuel requis...")
        from core.feature_flags import emergency_rollback
        emergency_rollback('use_testable_position_manager', 'Demo emergency')
        print("   ✅ ROLLBACK MANUEL EXÉCUTÉ!")
    
    # Vérification finale
    final_check = is_flag_enabled('use_testable_position_manager')
    print(f"\n🏁 Status final: {'❌ DÉSACTIVÉ' if not final_check else '⚠️ ENCORE ACTIF'}")


def demo_ab_testing():
    """Démonstration A/B testing"""
    
    print("\n" + "=" * 60)
    print("🧪 DÉMONSTRATION A/B TESTING")
    print("=" * 60)
    
    fm = get_feature_flags_manager()
    
    # Configuration A/B 50%
    enable_flag('use_testable_position_manager', 50.0)
    
    print("⚖️ Test 100 utilisateurs avec rollout 50%:")
    
    group_a_count = 0  # Legacy
    group_b_count = 0  # Testable
    
    for user_id in range(100):
        if is_flag_enabled('use_testable_position_manager', f'user_{user_id}'):
            group_b_count += 1
        else:
            group_a_count += 1
    
    print(f"   👥 Groupe A (Legacy): {group_a_count} utilisateurs")
    print(f"   🚀 Groupe B (Testable): {group_b_count} utilisateurs")
    print(f"   📊 Distribution: {group_a_count}% / {group_b_count}%")
    
    # Validation distribution
    if 40 <= group_b_count <= 60:
        print("   ✅ Distribution A/B correcte")
    else:
        print("   ⚠️ Distribution A/B déséquilibrée")


def main():
    """Point d'entrée principal"""
    
    print("🎭 DÉMONSTRATION REFACTORISATION SÉCURISÉE")
    print("Cas d'usage réel: Migration PositionManager + TechnicalAnalyzer")
    
    try:
        # 1. Demo environnement production
        demo = PracticalRefactoringDemo()
        demo.simulate_production_environment()
        
        # 2. Demo rollback d'urgence
        demo_emergency_rollback()
        
        # 3. Demo A/B testing
        demo_ab_testing()
        
        print("\n🎉 DÉMONSTRATION TERMINÉE AVEC SUCCÈS!")
        print("La refactorisation sécurisée est opérationnelle.")
        
    except Exception as e:
        print(f"\n❌ ERREUR DEMO: {e}")
        print("Rollback automatique recommandé.")


if __name__ == "__main__":
    # Configuration logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    main()

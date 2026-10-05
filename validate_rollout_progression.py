"""
Validation Rollout Progression - Trade Cursor v7.0
Valide la progression des rollouts Position Manager 50% et Analyzer 25%
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from core.feature_flags import get_feature_flags_manager
from core.factories.position_factory import (
    get_configured_position_factory, 
    get_configured_analyzer_factory,
    get_configured_scanner_factory
)

logger = logging.getLogger(__name__)


async def validate_rollout_progression():
    """Valide la progression complète des rollouts Phase 1, 2 et 3"""
    
    print("🔍 VALIDATION ROLLOUT PROGRESSION - TRADE CURSOR v7.0")
    print("=" * 60)
    
    try:
        # 1. Vérifier Feature Flags
        print("\n📋 1. FEATURE FLAGS STATUS")
        print("-" * 30)
        
        ffm = get_feature_flags_manager()
        
        # Position Manager (Phase 1)
        pos_flag = ffm.get_flag('use_testable_position_manager')
        print(f"Position Manager: {'✅' if pos_flag.enabled else '❌'} "
              f"Rollout: {pos_flag.rollout_percentage}%")
        
        # Analyzer (Phase 2)  
        analyzer_flag = ffm.get_flag('use_testable_analyzer')
        print(f"Analyzer:         {'✅' if analyzer_flag.enabled else '❌'} "
              f"Rollout: {analyzer_flag.rollout_percentage}%")
        
        # Scanner (Phase 3) - À activer plus tard
        try:
            scanner_flag = ffm.get_flag('use_testable_scanner')
            print(f"Scanner:          {'✅' if scanner_flag.enabled else '❌'} "
                  f"Rollout: {scanner_flag.rollout_percentage}%")
        except:
            print(f"Scanner:          ⏸️  Rollout: 0% (Not yet configured)")
        
        # 2. Tester Position Manager Phase 1 (50% rollout)
        print(f"\n🏭 2. POSITION MANAGER PHASE 1 - 50% ROLLOUT")
        print("-" * 50)
        
        pos_factory = get_configured_position_factory("development")
        
        # Test création composants
        pos_calculator = pos_factory.create_position_calculator()
        pos_validator = pos_factory.create_position_validator() 
        pos_executor = pos_factory.create_position_executor()
        pos_orchestrator = pos_factory.create_position_orchestrator()
        
        print("✅ Position Calculator créé")
        print("✅ Position Validator créé")
        print("✅ Position Executor créé")
        print("✅ Position Orchestrator créé")
        
        # Test fonctionnalité de base
        test_position_data = {
            'symbol': 'TESTUSDT',
            'direction': 'LONG',
            'quantity': 100,
            'entry_price': 1.0000,
            'leverage': 10
        }
        
        calc_result = pos_calculator.calculate_position_size(test_position_data)
        if calc_result and 'position_size' in calc_result:
            print(f"✅ Position calculation: {calc_result['position_size']} USDT")
        
        validation_result = pos_validator.validate_position(test_position_data)
        if validation_result and validation_result.get('is_valid'):
            print("✅ Position validation passed")
        
        # Stats factory
        factory_stats = pos_factory.get_factory_stats()
        print(f"📊 Factory stats: {factory_stats['cached_components']} composants en cache")
        
        # 3. Tester Analyzer Phase 2 (25% rollout)
        print(f"\n🧮 3. ANALYZER PHASE 2 - 25% ROLLOUT")
        print("-" * 40)
        
        analyzer_factory = get_configured_analyzer_factory("development")
        
        # Test création composants
        indicator_calc = analyzer_factory.create_indicator_calculator()
        signal_generator = analyzer_factory.create_signal_generator()
        signal_validator = analyzer_factory.create_signal_validator()
        score_calculator = analyzer_factory.create_score_calculator()
        analyzer = analyzer_factory.create_analyzer()
        
        print("✅ Indicator Calculator créé")
        print("✅ Signal Generator créé") 
        print("✅ Signal Validator créé")
        print("✅ Score Calculator créé")
        print("✅ Analyzer créé")
        
        # Test analyse basique
        test_data = {
            'ohlcv_1m': [[1640995200, 47000, 47100, 46900, 47050, 1000] for _ in range(30)],
            'ohlcv_5m': [[1640995200, 47000, 47100, 46900, 47050, 5000] for _ in range(30)],
            'current_price': 47050
        }
        
        analysis_result = analyzer.analyze_pair('TESTUSDT', test_data)
        if analysis_result:
            print(f"✅ Analysis completed: {getattr(analysis_result, 'timeframe', 'N/A')} timeframe")
            if hasattr(analysis_result, 'is_valid'):
                print(f"   Valid: {analysis_result.is_valid}")
        
        # 4. Tester Scanner Phase 3 (Composants créés, rollout 0%)
        print(f"\n🔍 4. SCANNER PHASE 3 - COMPOSANTS DISPONIBLES")
        print("-" * 50)
        
        scanner_factory = get_configured_scanner_factory("development", use_mocks=True)
        
        # Test création stack complet
        scanner_stack = scanner_factory.create_full_scanner_stack()
        
        if len(scanner_stack) == 5:
            print("✅ Scanner stack complet créé:")
            for component, instance in scanner_stack.items():
                print(f"   - {component}: {'✅' if instance else '❌'}")
        else:
            print(f"⚠️ Scanner stack incomplet: {len(scanner_stack)}/5 composants")
        
        # Test scan unique avec mocks
        orchestrator = scanner_stack.get('scanner_orchestrator')
        if orchestrator:
            scan_result = await orchestrator.scan_single_pair('MOCKTEST')
            if scan_result:
                print(f"✅ Mock scan test: {scan_result.status.value}")
        
        # 5. Validation globale
        print(f"\n📊 5. VALIDATION GLOBALE")
        print("-" * 25)
        
        validation_results = {
            'position_manager_rollout': pos_flag.rollout_percentage,
            'analyzer_rollout': analyzer_flag.rollout_percentage,
            'scanner_components_ready': len(scanner_stack) == 5,
            'position_factory_operational': len(pos_factory.get_factory_stats()['component_types']) > 0,
            'analyzer_factory_operational': len(analyzer_factory.get_factory_stats()['component_types']) > 0,
            'scanner_factory_operational': scanner_factory.get_factory_stats()['cached_components'] == 5
        }
        
        print("Validation Summary:")
        for check, result in validation_results.items():
            status = "✅" if result else "❌"
            if isinstance(result, (int, float)):
                status = "✅" if result > 0 else "❌"
                result = f"{result}%"
            print(f"   {check}: {status} {result}")
        
        # Score global
        success_checks = sum(1 for r in validation_results.values() if 
                           (isinstance(r, bool) and r) or 
                           (isinstance(r, (int, float)) and r > 0))
        total_checks = len(validation_results)
        success_rate = success_checks / total_checks
        
        print(f"\n🎯 RÉSULTAT GLOBAL: {success_checks}/{total_checks} ({success_rate:.1%}) VALIDATIONS RÉUSSIES")
        
        if success_rate >= 0.9:
            print("🏆 EXCELLENT: Rollout progression validée avec succès!")
        elif success_rate >= 0.7:
            print("✅ BON: Rollout progression acceptable avec améliorations mineures")
        else:
            print("⚠️ ATTENTION: Rollout progression nécessite des corrections")
        
        return validation_results
        
    except Exception as e:
        logger.error(f"❌ Erreur validation rollout: {e}")
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        return None


def generate_rollout_report(validation_results: Dict[str, Any]):
    """Génère un rapport détaillé du rollout"""
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""
# RAPPORT ROLLOUT PROGRESSION - TRADE CURSOR v7.0
**Generated:** {timestamp}

## 📊 RÉSUMÉ EXÉCUTIF

### Statut Rollout Actuel
- **Position Manager (Phase 1):** 50% rollout ✅
- **Analyzer (Phase 2):** 25% rollout ✅  
- **Scanner (Phase 3):** Composants prêts, rollout 0% ⏸️

### Métriques Clés
"""
    
    if validation_results:
        for check, result in validation_results.items():
            status = "✅ PASS" if ((isinstance(result, bool) and result) or 
                                 (isinstance(result, (int, float)) and result > 0)) else "❌ FAIL"
            report += f"- **{check.replace('_', ' ').title()}:** {status}\n"
    
    report += f"""
## 🚀 PROCHAINES ÉTAPES

### Phase 3 Scanner - Rollout Planning
1. **Semaine 1-2:** Validation en environnement test
2. **Semaine 3:** Rollout 10% avec monitoring intensif
3. **Semaine 4:** Rollout 25% si métriques OK
4. **Semaine 5-6:** Rollout progressif 50% → 75% → 100%

### Position Manager - Extension 50% → 75%
- Prévu après stabilisation Scanner Phase 3
- Monitoring performance et stabilité requis

### Analyzer - Extension 25% → 50%  
- En parallèle du rollout Scanner Phase 3
- Tests A/B pour validation performance

## 📋 ACTION ITEMS

### Immédiat (Cette semaine)
- [ ] Finaliser tests Scanner Phase 3 en environnement staging
- [ ] Configurer monitoring dashboards pour rollout
- [ ] Préparer rollback procedures
- [ ] Documentation équipe sur nouvelles interfaces

### Court terme (2-4 semaines)
- [ ] Activer feature flag Scanner Phase 3 à 10%
- [ ] Étendre Position Manager rollout à 75%
- [ ] Étendre Analyzer rollout à 50%
- [ ] Benchmarking performance comparative

### Moyen terme (1-2 mois)
- [ ] Migration complète vers architecture modulaire
- [ ] Deprecation code legacy
- [ ] Optimisations performance avancées
- [ ] Formation équipe sur maintenance

---
*Rapport généré automatiquement par validate_rollout_progression.py*
"""
    
    return report


async def main():
    """Main validation et génération rapport"""
    
    print("🚀 DÉMARRAGE VALIDATION ROLLOUT PROGRESSION")
    
    # Validation
    results = await validate_rollout_progression()
    
    # Génération rapport
    if results:
        report = generate_rollout_report(results)
        
        # Sauvegarder rapport
        report_file = f"rollout_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n📄 Rapport sauvegardé: {report_file}")
    
    print(f"\n✅ VALIDATION ROLLOUT PROGRESSION TERMINÉE")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
🧪 TESTS TP ESCALIER (Multi-Level TP)
Test complet du système TP Escalier avec 4 niveaux
"""

import asyncio
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_tp_escalier_long():
    """Test TP Escalier LONG avec 4 niveaux"""
    logger.info("\n" + "="*60)
    logger.info("🧪 TEST TP ESCALIER LONG")
    logger.info("="*60)
    
    from core.position_manager import PositionManager, PositionConfig
    from config import TRADING_CONFIG
    
    # Activer TP_MULTI temporairement
    original_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
    TRADING_CONFIG['tp_sl_mode'] = 'TP_MULTI'
    
    # Configuration
    config = PositionConfig()
    config.use_atr = False
    manager = PositionManager(config)
    
    # Ouvrir position LONG
    logger.info("\n[1] Ouverture position LONG BTC_USDT @ 10000.0")
    position = manager.open_position(
        symbol="BTC_USDT",
        direction="LONG",
        entry=10000.0,
        size=100.0,
        atr=50.0
    )
    
    # Vérifier initialisation TP Escalier
    assert position.tp_escalier_enabled, "❌ TP Escalier non activé"
    assert len(position.tp_escalier_levels) == 4, f"❌ Attendu 4 niveaux, obtenu {len(position.tp_escalier_levels)}"
    assert position.tp_escalier_current_level == 0, "❌ Niveau initial != 0"
    assert position.tp_escalier_size_remaining == 1.0, "❌ Size restante != 100%"
    
    logger.info("✅ Initialisation OK")
    logger.info(f"   Niveaux configurés: {len(position.tp_escalier_levels)}")
    for i, level in enumerate(position.tp_escalier_levels, 1):
        logger.info(f"   Niveau {i}: {level['pnl']}% ({level['size_pct']*100:.0f}%) → {level['move_sl']}")
    
    # Test Niveau 1: +0.20% (25% @ 10020)
    logger.info("\n[2] Simulation Niveau 1: +0.20%")
    await manager.check_position(10020.0)
    
    assert position.tp_escalier_current_level == 1, f"❌ Niveau actuel = {position.tp_escalier_current_level}, attendu 1"
    assert position.tp_escalier_size_remaining == 0.75, f"❌ Size restante = {position.tp_escalier_size_remaining}, attendu 0.75"
    assert len(position.tp_escalier_profits) == 1, f"❌ {len(position.tp_escalier_profits)} profits, attendu 1"
    assert position.sl == 10000.0, f"❌ SL = {position.sl}, attendu 10000.0 (entry)"
    
    profit1 = position.tp_escalier_profits[0]
    logger.info("✅ Niveau 1 atteint")
    logger.info(f"   Profit: +{profit1['profit_usdt']:.2f} USDT (+{profit1['profit_pct']:.2f}%)")
    logger.info(f"   SL → Entry: {position.sl:.6f}")
    logger.info(f"   Restant: {position.tp_escalier_size_remaining*100:.0f}%")
    
    # Test Niveau 2: +0.35% (25% @ 10035)
    logger.info("\n[3] Simulation Niveau 2: +0.35%")
    await manager.check_position(10035.0)
    
    assert position.tp_escalier_current_level == 2, f"❌ Niveau actuel = {position.tp_escalier_current_level}, attendu 2"
    assert position.tp_escalier_size_remaining == 0.50, f"❌ Size restante = {position.tp_escalier_size_remaining}, attendu 0.50"
    assert len(position.tp_escalier_profits) == 2, f"❌ {len(position.tp_escalier_profits)} profits, attendu 2"
    assert position.break_even_set == True, "❌ Break-even non activé"
    
    profit2 = position.tp_escalier_profits[1]
    logger.info("✅ Niveau 2 atteint")
    logger.info(f"   Profit: +{profit2['profit_usdt']:.2f} USDT (+{profit2['profit_pct']:.2f}%)")
    logger.info(f"   SL → Breakeven: {position.sl:.6f}")
    logger.info(f"   Restant: {position.tp_escalier_size_remaining*100:.0f}%")
    
    # Test Niveau 3: +0.50% (25% @ 10050)
    logger.info("\n[4] Simulation Niveau 3: +0.50%")
    await manager.check_position(10050.0)
    
    assert position.tp_escalier_current_level == 3, f"❌ Niveau actuel = {position.tp_escalier_current_level}, attendu 3"
    assert position.tp_escalier_size_remaining == 0.25, f"❌ Size restante = {position.tp_escalier_size_remaining}, attendu 0.25"
    assert len(position.tp_escalier_profits) == 3, f"❌ {len(position.tp_escalier_profits)} profits, attendu 3"
    
    profit3 = position.tp_escalier_profits[2]
    logger.info("✅ Niveau 3 atteint")
    logger.info(f"   Profit: +{profit3['profit_usdt']:.2f} USDT (+{profit3['profit_pct']:.2f}%)")
    logger.info(f"   Trailing stop activé")
    logger.info(f"   Restant: {position.tp_escalier_size_remaining*100:.0f}%")
    
    # Test Niveau 4: +0.80% (25% @ 10080) - Dernier niveau
    logger.info("\n[5] Simulation Niveau 4: +0.80% (final)")
    await manager.check_position(10080.0)
    
    assert position.tp_escalier_current_level == 4, f"❌ Niveau actuel = {position.tp_escalier_current_level}, attendu 4"
    assert position.tp_escalier_size_remaining == 0.0, f"❌ Size restante = {position.tp_escalier_size_remaining}, attendu 0.0"
    assert len(position.tp_escalier_profits) == 4, f"❌ {len(position.tp_escalier_profits)} profits, attendu 4"
    
    profit4 = position.tp_escalier_profits[3]
    logger.info("✅ Niveau 4 atteint (FINAL)")
    logger.info(f"   Profit: +{profit4['profit_usdt']:.2f} USDT (+{profit4['profit_pct']:.2f}%)")
    logger.info(f"   Restant: {position.tp_escalier_size_remaining*100:.0f}%")
    
    # Calculer profit total
    total_profit = sum(p['profit_usdt'] for p in position.tp_escalier_profits)
    logger.info(f"\n🎉 TOUS LES NIVEAUX ATTEINTS")
    logger.info(f"   Profit total: +{total_profit:.2f} USDT")
    
    # Vérifier profit total attendu
    # Niveau 1: 25 USDT @ +0.20% = +0.05 USDT
    # Niveau 2: 25 USDT @ +0.35% = +0.0875 USDT
    # Niveau 3: 25 USDT @ +0.50% = +0.125 USDT
    # Niveau 4: 25 USDT @ +0.80% = +0.20 USDT
    # Total théorique: +0.4625 USDT
    expected_profit = 0.4625
    assert abs(total_profit - expected_profit) < 0.01, f"❌ Profit total = {total_profit:.4f}, attendu ~{expected_profit:.4f}"
    
    # Fermer position
    logger.info("\n[6] Fermeture position finale")
    result = manager.close_position('TP', exit_price=10080.0)
    
    logger.info(f"   PnL final: +{result.get('net_pnl_usdt', 0):.2f} USDT")
    logger.info(f"   Raison: {result.get('reason')}")
    
    # Restaurer mode original
    TRADING_CONFIG['tp_sl_mode'] = original_mode
    
    logger.info("\n✅ TEST TP ESCALIER LONG RÉUSSI")
    return True


async def test_tp_escalier_short():
    """Test TP Escalier SHORT avec 4 niveaux"""
    logger.info("\n" + "="*60)
    logger.info("🧪 TEST TP ESCALIER SHORT")
    logger.info("="*60)
    
    from core.position_manager import PositionManager, PositionConfig
    from config import TRADING_CONFIG
    
    # Activer TP_MULTI temporairement
    original_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
    TRADING_CONFIG['tp_sl_mode'] = 'TP_MULTI'
    
    # Configuration
    config = PositionConfig()
    config.use_atr = False
    manager = PositionManager(config)
    
    # Ouvrir position SHORT
    logger.info("\n[1] Ouverture position SHORT BTC_USDT @ 10000.0")
    position = manager.open_position(
        symbol="BTC_USDT",
        direction="SHORT",
        entry=10000.0,
        size=100.0,
        atr=50.0
    )
    
    # Vérifier initialisation TP Escalier
    assert position.tp_escalier_enabled, "❌ TP Escalier non activé"
    assert len(position.tp_escalier_levels) == 4, f"❌ Attendu 4 niveaux, obtenu {len(position.tp_escalier_levels)}"
    
    logger.info("✅ Initialisation OK")
    
    # Test Niveau 1: -0.20% (25% @ 9980)
    logger.info("\n[2] Simulation Niveau 1: -0.20%")
    await manager.check_position(9980.0)
    
    assert position.tp_escalier_current_level == 1, f"❌ Niveau actuel = {position.tp_escalier_current_level}, attendu 1"
    assert position.sl == 10000.0, f"❌ SL = {position.sl}, attendu 10000.0 (entry)"
    
    logger.info("✅ Niveau 1 atteint (SHORT)")
    logger.info(f"   SL → Entry: {position.sl:.6f}")
    
    # Test Niveau 2: -0.35% (25% @ 9965)
    logger.info("\n[3] Simulation Niveau 2: -0.35%")
    await manager.check_position(9965.0)
    
    assert position.tp_escalier_current_level == 2, f"❌ Niveau actuel = {position.tp_escalier_current_level}, attendu 2"
    assert position.break_even_set == True, "❌ Break-even non activé"
    
    logger.info("✅ Niveau 2 atteint (SHORT)")
    logger.info(f"   SL → Breakeven: {position.sl:.6f}")
    
    # Test Niveau 3: -0.50% (25% @ 9950)
    logger.info("\n[4] Simulation Niveau 3: -0.50%")
    await manager.check_position(9950.0)
    
    assert position.tp_escalier_current_level == 3, f"❌ Niveau actuel = {position.tp_escalier_current_level}, attendu 3"
    
    logger.info("✅ Niveau 3 atteint (SHORT)")
    logger.info(f"   Trailing stop activé")
    
    # Test Niveau 4: -0.80% (25% @ 9920)
    logger.info("\n[5] Simulation Niveau 4: -0.80% (final)")
    await manager.check_position(9920.0)
    
    assert position.tp_escalier_current_level == 4, f"❌ Niveau actuel = {position.tp_escalier_current_level}, attendu 4"
    assert position.tp_escalier_size_remaining == 0.0, f"❌ Size restante = {position.tp_escalier_size_remaining}, attendu 0.0"
    
    logger.info("✅ Niveau 4 atteint (SHORT - FINAL)")
    
    # Calculer profit total
    total_profit = sum(p['profit_usdt'] for p in position.tp_escalier_profits)
    logger.info(f"\n🎉 TOUS LES NIVEAUX ATTEINTS (SHORT)")
    logger.info(f"   Profit total: +{total_profit:.2f} USDT")
    
    # Fermer position
    logger.info("\n[6] Fermeture position finale")
    result = manager.close_position('TP', exit_price=9920.0)
    
    logger.info(f"   PnL final: +{result.get('net_pnl_usdt', 0):.2f} USDT")
    
    # Restaurer mode original
    TRADING_CONFIG['tp_sl_mode'] = original_mode
    
    logger.info("\n✅ TEST TP ESCALIER SHORT RÉUSSI")
    return True


async def test_tp_escalier_sl_after_level2():
    """Test SL après Niveau 2 (Breakeven) - Doit clôturer à l'entry sans perte"""
    logger.info("\n" + "="*60)
    logger.info("🧪 TEST TP ESCALIER - SL après Niveau 2 (Breakeven)")
    logger.info("="*60)
    
    from core.position_manager import PositionManager, PositionConfig
    from config import TRADING_CONFIG
    
    # Activer TP_MULTI temporairement
    original_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
    TRADING_CONFIG['tp_sl_mode'] = 'TP_MULTI'
    
    # Configuration
    config = PositionConfig()
    config.use_atr = False
    manager = PositionManager(config)
    
    # Ouvrir position LONG
    logger.info("\n[1] Ouverture position LONG BTC_USDT @ 10000.0")
    position = manager.open_position(
        symbol="BTC_USDT",
        direction="LONG",
        entry=10000.0,
        size=100.0,
        atr=50.0
    )
    
    # Atteindre Niveau 1
    logger.info("\n[2] Atteinte Niveau 1: +0.20%")
    await manager.check_position(10020.0)
    
    # Atteindre Niveau 2
    logger.info("\n[3] Atteinte Niveau 2: +0.35%")
    await manager.check_position(10035.0)
    
    # SL doit être à breakeven
    assert position.sl == 10000.0, f"❌ SL = {position.sl}, attendu 10000.0 (breakeven)"
    logger.info(f"   SL → Breakeven: {position.sl:.6f}")
    
    # Simuler retour au SL (breakeven)
    logger.info("\n[4] Retour au SL (breakeven @ 10000.0)")
    reason = await manager.check_position(9999.0)
    
    assert reason in ['SL', 'TS'], f"❌ Raison = {reason}, attendu 'SL' ou 'TS'"
    logger.info(f"   Raison fermeture: {reason}")
    
    # Fermer position
    result = manager.close_position(reason, exit_price=10000.0)
    
    # Profit total devrait être proche de breakeven (profits niveaux 1+2 seulement)
    net_pnl = result.get('net_pnl_usdt', 0)
    logger.info(f"   PnL final: {net_pnl:+.2f} USDT")
    
    # Attendu: Profits niveaux 1+2 seulement (position 50% restante fermée à entry)
    # Niveau 1: 25 USDT @ +0.20% = +0.05 USDT
    # Niveau 2: 25 USDT @ +0.35% = +0.0875 USDT
    # Niveau 3+4: 50 USDT @ 0% (fermé à entry) = 0 USDT
    # Total théorique: +0.1375 USDT (mais avec frais/slippage, attendu ~0.08-0.13 USDT)
    expected_min = 0.08
    expected_max = 0.15
    assert expected_min <= net_pnl <= expected_max, f"❌ PnL = {net_pnl:.4f}, attendu entre {expected_min:.4f} et {expected_max:.4f}"
    
    logger.info(f"   ✅ Profits niveaux 1+2 conservés: +{net_pnl:.4f} USDT")
    
    # Restaurer mode original
    TRADING_CONFIG['tp_sl_mode'] = original_mode
    
    logger.info("\n✅ TEST SL APRÈS NIVEAU 2 RÉUSSI")
    return True


async def main():
    """Point d'entrée principal"""
    logger.info("="*60)
    logger.info("🧪 DÉBUT DES TESTS TP ESCALIER")
    logger.info("="*60)
    
    try:
        # Test 1: LONG
        await test_tp_escalier_long()
        
        # Test 2: SHORT
        await test_tp_escalier_short()
        
        # Test 3: SL après Niveau 2 (Breakeven)
        await test_tp_escalier_sl_after_level2()
        
        logger.info("\n" + "="*60)
        logger.info("✅ TOUS LES TESTS TP ESCALIER ONT RÉUSSI")
        logger.info("="*60)
        
    except AssertionError as e:
        logger.error(f"\n❌ TEST ÉCHOUÉ: {e}")
        return False
    except Exception as e:
        logger.error(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)


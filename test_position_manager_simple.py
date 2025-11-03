#!/usr/bin/env python3
"""
Test Position Manager - Version simplifiée sans dépendances
"""

import sys
sys.path.insert(0, '.')

# Import direct pour éviter les dépendances
from core.position_manager import PositionManager, PositionConfig


def test_fixed_mode():
    """Test mode FIXE"""
    print("\n=== TEST MODE FIXE ===")
    
    config = PositionConfig(
        use_atr=False,
        use_break_even=True,
        use_trailing_stop=True,
        use_partial_tp=True
    )
    
    manager = PositionManager(config)
    
    # Ouvrir position LONG
    pos = manager.open_position(
        symbol="BTC_USDT",
        direction="LONG",
        entry=10000.0,
        size=100.0,
        confirmed_by="1m+5m"
    )
    
    print(f"Position ouverte: {pos.symbol}")
    print(f"Entry: {pos.entry}")
    print(f"SL: {pos.sl} (-0.25%)")
    print(f"TP: {pos.tp} (+0.25%)")
    
    # Vérifier que c'est correct
    assert pos.sl == 9975.0, f"SL attendu 9975.0, obtenu {pos.sl}"
    assert pos.tp == 10025.0, f"TP attendu 10025.0, obtenu {pos.tp}"
    
    print("✅ Mode FIXE validé!")


def test_atr_mode():
    """Test mode ATR"""
    print("\n=== TEST MODE ATR ===")
    
    config = PositionConfig(
        use_atr=True,
        atr_mult_tp=3.0,
        atr_mult_sl=1.5
    )
    
    manager = PositionManager(config)
    
    # Ouvrir position LONG avec ATR
    pos = manager.open_position(
        symbol="ETH_USDT",
        direction="LONG",
        entry=2000.0,
        size=100.0,
        atr=10.0,  # 0.5% ATR
        confirmed_by="1m only"
    )
    
    print(f"Position ouverte: {pos.symbol}")
    print(f"Entry: {pos.entry}")
    print(f"SL: {pos.sl}")
    print(f"TP: {pos.tp}")
    
    # ATR = 10 (0.5%), TP = 3x, SL = 1.5x
    # Expected: TP = 2000 + 10*3 = 2030, SL = 2000 - 10*1.5 = 1985
    expected_tp = 2030.0
    expected_sl = 1985.0
    
    assert pos.tp == expected_tp, f"TP attendu {expected_tp}, obtenu {pos.tp}"
    assert pos.sl == expected_sl, f"SL attendu {expected_sl}, obtenu {pos.sl}"
    
    print("✅ Mode ATR validé!")


def test_win_loss_streaks():
    """Test ajustement selon win/loss streaks"""
    print("\n=== TEST WIN/LOSS STREAKS ===")
    
    config = PositionConfig(use_atr=True)
    manager = PositionManager(config)
    
    # Test win streak agressif
    config.win_streak = 3
    pos1 = manager.open_position(
        symbol="BNB_USDT",
        direction="LONG",
        entry=300.0,
        size=100.0,
        atr=3.0
    )
    print(f"Win streak 3: TP={pos1.tp}, SL={pos1.sl}")
    # TP devrait être 4x ATR = 300 + 3*4 = 312
    assert pos1.tp == 312.0, f"Win streak TP attendu 312.0, obtenu {pos1.tp}"
    
    # Test loss streak prudent
    config.win_streak = 0
    config.loss_streak = 2
    pos2 = manager.open_position(
        symbol="ADA_USDT",
        direction="LONG",
        entry=1.0,
        size=100.0,
        atr=0.01
    )
    print(f"Loss streak 2: TP={pos2.tp}, SL={pos2.sl}")
    # TP devrait être 1.5x ATR = 1 + 0.01*1.5 = 1.015
    assert pos2.tp == 1.015, f"Loss streak TP attendu 1.015, obtenu {pos2.tp}"
    
    print("✅ Win/Loss streaks validés!")


def test_check_levels():
    """Test vérification TP/SL"""
    print("\n=== TEST VÉRIFICATION NIVEAUX ===")
    
    config = PositionConfig(use_atr=False)
    manager = PositionManager(config)
    
    pos = manager.open_position(
        symbol="BTC_USDT",
        direction="LONG",
        entry=10000.0,
        size=100.0
    )
    
    # Vérifier TP
    import asyncio
    
    async def check_tp():
        reason = await manager.check_position(10025.0)
        assert reason == 'TP', f"Attendu 'TP', obtenu {reason}"
        print(f"✅ TP touché correctement")
    
    async def check_sl():
        # Reset position
        manager.active_position = pos
        reason = await manager.check_position(9975.0)
        assert reason == 'SL', f"Attendu 'SL', obtenu {reason}"
        print(f"✅ SL touché correctement")
    
    # Test SHORT
    async def check_short():
        pos_short = manager.open_position(
            symbol="BTC_USDT",
            direction="SHORT",
            entry=10000.0,
            size=100.0
        )
        reason = await manager.check_position(9975.0)  # -0.25%
        assert reason == 'TP', f"SHORT TP: Attendu 'TP', obtenu {reason}"
        print(f"✅ SHORT TP touché correctement")
        
        manager.active_position = pos_short
        reason = await manager.check_position(10025.0)  # +0.25%
        assert reason == 'SL', f"SHORT SL: Attendu 'SL', obtenu {reason}"
        print(f"✅ SHORT SL touché correctement")
    
    asyncio.run(check_tp())
    asyncio.run(check_sl())
    asyncio.run(check_short())


if __name__ == '__main__':
    test_fixed_mode()
    test_atr_mode()
    test_win_loss_streaks()
    test_check_levels()
    print("\n✅ TOUS LES TESTS PASSÉS!")




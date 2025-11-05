#!/usr/bin/env python3
"""
Test Position Manager
"""

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
    
    # Simuler check position
    import asyncio
    
    async def check():
        # Vérifier TP
        reason = await manager.check_position(10025.0)
        print(f"Check à 10025: {reason}")
        
        # Vérifier SL
        manager.active_position = pos  # Reset
        reason = await manager.check_position(9975.0)
        print(f"Check à 9975: {reason}")
    
    asyncio.run(check())


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
    expected_tp = 2000.0 + (10.0 * 3.0)  # 2030
    expected_sl = 2000.0 - (10.0 * 1.5)  # 1985
    
    print(f"Expected TP: {expected_tp}")
    print(f"Expected SL: {expected_sl}")
    print(f"Actual TP: {pos.tp}")
    print(f"Actual SL: {pos.sl}")


def test_break_even():
    """Test break-even progressif"""
    print("\n=== TEST BREAK-EVEN ATR ===")
    
    config = PositionConfig(use_atr=True)
    
    manager = PositionManager(config)
    
    pos = manager.open_position(
        symbol="SOL_USDT",
        direction="LONG",
        entry=100.0,
        size=100.0,
        atr=1.0  # 1% ATR
    )
    
    # Simuler BE 50%
    pnl = manager._calculate_pnl(100.5)  # +0.5% = 50% of 1% ATR
    manager._update_atr_mode_sl(100.5, pnl)
    
    print(f"PnL: {pnl:.2f}%")
    print(f"SL après BE 50%: {pos.sl}")
    print(f"Break-even set: {pos.break_even_set}")


def test_win_loss_streaks():
    """Test ajustement selon win/loss streaks"""
    print("\n=== TEST WIN/LOSS STREAKS ===")
    
    config = PositionConfig(use_atr=True)
    manager = PositionManager(config)
    
    # Test win streak
    config.win_streak = 3
    pos1 = manager.open_position(
        symbol="BNB_USDT",
        direction="LONG",
        entry=300.0,
        size=100.0,
        atr=3.0
    )
    print(f"Win streak 3: TP={pos1.tp}, SL={pos1.sl}")
    
    # Test loss streak
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


if __name__ == '__main__':
    test_fixed_mode()
    test_atr_mode()
    test_break_even()
    test_win_loss_streaks()
    print("\n✅ Tests terminés!")






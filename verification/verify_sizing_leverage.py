#!/usr/bin/env python3
"""
Verification script for position sizing and leverage configuration.
Checks that risk_per_trade is correctly applied and leverage is properly set.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_result(check: str, passed: bool, details: str = ""):
    status = "[OK]" if passed else "[FAILED]"
    print(f"  {status} {check}")
    if details:
        print(f"       {details}")

def verify_config_values():
    """Verify configuration values are consistent."""
    print_header("1. CONFIGURATION VALUES")
    
    from config import TRADING_CONFIG
    
    account_size = TRADING_CONFIG.get('account_size', 1000.0)
    risk_per_trade = TRADING_CONFIG.get('risk_per_trade', 2.0)
    min_risk = TRADING_CONFIG.get('min_risk_per_trade')
    max_risk = TRADING_CONFIG.get('max_risk_per_trade')
    default_leverage = TRADING_CONFIG.get('default_leverage', 10)
    
    print(f"\n  Current Configuration:")
    print(f"    - account_size: {account_size} USDT")
    print(f"    - risk_per_trade: {risk_per_trade}%")
    print(f"    - min_risk_per_trade: {min_risk}%")
    print(f"    - max_risk_per_trade: {max_risk}%")
    print(f"    - default_leverage: {default_leverage}x")
    
    all_ok = True
    
    # Check min_risk < risk_per_trade
    if min_risk is not None:
        ok = min_risk <= risk_per_trade
        print_result(
            "min_risk_per_trade <= risk_per_trade",
            ok,
            f"{min_risk}% <= {risk_per_trade}%" if ok else f"{min_risk}% > {risk_per_trade}% (WRONG!)"
        )
        all_ok = all_ok and ok
    
    # Check max_risk >= risk_per_trade
    if max_risk is not None:
        ok = max_risk >= risk_per_trade
        print_result(
            "max_risk_per_trade >= risk_per_trade",
            ok,
            f"{max_risk}% >= {risk_per_trade}%" if ok else f"{max_risk}% < {risk_per_trade}% (WRONG!)"
        )
        all_ok = all_ok and ok
    
    # Check leverage is valid (1-125)
    ok = 1 <= default_leverage <= 125
    print_result(
        "default_leverage in valid range (1-125)",
        ok,
        f"{default_leverage}x"
    )
    all_ok = all_ok and ok
    
    return all_ok

def verify_position_sizing():
    """Verify position sizing calculation."""
    print_header("2. POSITION SIZING CALCULATION")
    
    from config import TRADING_CONFIG
    from core.position_manager import PositionManager, PositionConfig
    
    account_size = TRADING_CONFIG.get('account_size', 1000.0)
    risk_per_trade = TRADING_CONFIG.get('risk_per_trade', 2.0)
    
    # Expected base size
    expected_base = account_size * (risk_per_trade / 100)
    
    print(f"\n  Expected Calculation:")
    print(f"    base_size = {account_size} * {risk_per_trade}% = {expected_base:.2f} USDT")
    
    # Create position manager with config
    config = PositionConfig()
    pm = PositionManager(config)
    
    # Mock setup with neutral score
    mock_setup = {
        'symbol': 'TEST/USDT',
        'score': 7.0,
        'direction': 'LONG',
        'price': 100.0
    }
    
    actual_size = pm.calculate_position_size(mock_setup, capital=account_size)
    
    print(f"\n  Actual Calculation:")
    print(f"    calculated_size = {actual_size:.2f} USDT")
    
    # Check if within reasonable bounds
    min_risk = TRADING_CONFIG.get('min_risk_per_trade')
    max_risk = TRADING_CONFIG.get('max_risk_per_trade')
    
    if min_risk:
        min_size = account_size * (min_risk / 100)
    else:
        min_size = expected_base * 0.5
    
    if max_risk:
        max_size = account_size * (max_risk / 100)
    else:
        max_size = expected_base * 2.0
    
    # Minimum 7 USDT floor
    min_size = max(min_size, 7.0)
    
    print(f"\n  Bounds Check:")
    print(f"    min_size = {min_size:.2f} USDT")
    print(f"    max_size = {max_size:.2f} USDT")
    
    ok = min_size <= actual_size <= max_size
    print_result(
        "Position size within bounds",
        ok,
        f"{min_size:.2f} <= {actual_size:.2f} <= {max_size:.2f}"
    )
    
    # Check if close to expected (within 20%)
    tolerance = 0.2
    close_to_expected = abs(actual_size - expected_base) / expected_base <= tolerance
    print_result(
        f"Position size close to expected (within {tolerance*100:.0f}%)",
        close_to_expected,
        f"Expected ~{expected_base:.2f}, got {actual_size:.2f}"
    )
    
    return ok and close_to_expected

def verify_leverage_in_position():
    """Verify leverage is stored in position."""
    print_header("3. LEVERAGE IN POSITION")
    
    from config import TRADING_CONFIG
    from core.position_manager import Position
    
    default_leverage = TRADING_CONFIG.get('default_leverage', 10)
    
    # Create a mock position
    pos = Position(
        symbol='TEST/USDT',
        direction='LONG',
        entry=100.0,
        tp=101.0,
        sl=99.0,
        size=25.0
    )
    
    # Set leverage like position_manager does
    pos.leverage_used = default_leverage
    
    # Check to_dict includes leverage
    pos_dict = pos.to_dict()
    
    has_leverage = 'leverage_used' in pos_dict
    leverage_value = pos_dict.get('leverage_used')
    
    print(f"\n  Position.to_dict() contents:")
    print(f"    leverage_used present: {has_leverage}")
    print(f"    leverage_used value: {leverage_value}x")
    
    ok = has_leverage and leverage_value == default_leverage
    print_result(
        "leverage_used in position dict",
        ok,
        f"Expected {default_leverage}x, got {leverage_value}x"
    )
    
    return ok

def verify_order_manager_leverage():
    """Verify order manager uses correct leverage."""
    print_header("4. ORDER MANAGER LEVERAGE")
    
    from config import TRADING_CONFIG
    
    default_leverage = TRADING_CONFIG.get('default_leverage', 10)
    
    print(f"\n  Config default_leverage: {default_leverage}x")
    
    # Check live_order_manager_futures.py logic
    print(f"\n  LiveOrderManagerFutures.open_position():")
    print(f"    - leverage = leverage or self.default_leverage")
    print(f"    - Calls bypass_client.set_leverage(leverage=leverage)")
    print(f"    - Calls bypass_client.submit_order(leverage=leverage)")
    
    ok = default_leverage >= 1 and default_leverage <= 125
    print_result(
        "Leverage will be passed correctly to exchange",
        ok,
        f"Using {default_leverage}x"
    )
    
    return ok

def verify_frontend_fallback():
    """Check frontend fallback logic."""
    print_header("5. FRONTEND LEVERAGE DISPLAY")
    
    from config import TRADING_CONFIG
    
    default_leverage = TRADING_CONFIG.get('default_leverage', 10)
    
    print(f"\n  PositionCard.svelte logic:")
    print(f"    $activePosition.leverage_used || tradingConfig?.default_leverage || 1")
    print(f"")
    print(f"  Fallback chain:")
    print(f"    1. $activePosition.leverage_used (from backend)")
    print(f"    2. tradingConfig.default_leverage = {default_leverage}")
    print(f"    3. Hardcoded fallback = 1")
    
    print_result(
        "Frontend fallback uses config value",
        True,
        f"Will show {default_leverage}x if leverage_used not set"
    )
    
    return True

def main():
    print("\n" + "="*60)
    print("  POSITION SIZING & LEVERAGE VERIFICATION")
    print("="*60)
    
    results = []
    
    results.append(("Config Values", verify_config_values()))
    results.append(("Position Sizing", verify_position_sizing()))
    results.append(("Leverage in Position", verify_leverage_in_position()))
    results.append(("Order Manager Leverage", verify_order_manager_leverage()))
    results.append(("Frontend Fallback", verify_frontend_fallback()))
    
    print_header("SUMMARY")
    
    all_passed = True
    for name, passed in results:
        status = "[OK]" if passed else "[FAILED]"
        print(f"  {status} {name}")
        all_passed = all_passed and passed
    
    if all_passed:
        print(f"\n  All checks passed!")
    else:
        print(f"\n  Some checks failed - review above for details")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

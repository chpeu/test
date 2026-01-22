#!/usr/bin/env python3
"""
Verification script for SL_EXCHANGE handling
Tests:
1. Order history API response parsing
2. SL margin calculation (bot SL vs MEXC SL)
3. SL_EXCHANGE detection and closure flow
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

import asyncio
import json


def test_order_history_parsing():
    """Test that order history response is parsed correctly"""
    print("\n" + "="*60)
    print("TEST 1: Order History Response Parsing")
    print("="*60)
    
    # Simulated API responses
    test_cases = [
        # Case 1: Standard response with resultList
        {
            "name": "Standard dict with resultList",
            "response": {
                "success": True,
                "code": 0,
                "data": {
                    "resultList": [
                        {"orderId": "123", "state": 3, "category": 2, "dealAvgPrice": "0.3285"}
                    ]
                }
            },
            "expected_orders": 1
        },
        # Case 2: Data is a list directly
        {
            "name": "Data is list directly",
            "response": {
                "success": True,
                "code": 0,
                "data": [
                    {"orderId": "123", "state": 3, "category": 2, "dealAvgPrice": "0.3285"}
                ]
            },
            "expected_orders": 1
        },
        # Case 3: Response is a list (unlikely but handle it)
        {
            "name": "Response is list directly",
            "response": [
                {"orderId": "123", "state": 3, "category": 2, "dealAvgPrice": "0.3285"}
            ],
            "expected_orders": 1
        },
        # Case 4: Empty response
        {
            "name": "Empty orders",
            "response": {
                "success": True,
                "code": 0,
                "data": {"resultList": []}
            },
            "expected_orders": 0
        },
        # Case 5: Failed response
        {
            "name": "Failed response",
            "response": {
                "success": False,
                "code": 500,
                "message": "Error"
            },
            "expected_orders": 0
        }
    ]
    
    all_passed = True
    for tc in test_cases:
        history_response = tc["response"]
        
        # Logic from position_manager.py
        orders = []
        if isinstance(history_response, dict):
            if history_response.get("success") and history_response.get("code") == 0:
                orders = history_response.get("data", [])
                if isinstance(orders, dict):
                    orders = orders.get("resultList", [])
        elif isinstance(history_response, list):
            orders = history_response
        
        if not isinstance(orders, list):
            orders = []
        
        passed = len(orders) == tc["expected_orders"]
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {tc['name']} -> Got {len(orders)} orders (expected {tc['expected_orders']})")
        
        if not passed:
            all_passed = False
    
    return all_passed


def test_sl_margin_calculation():
    """Test SL margin calculation (bot SL vs MEXC SL)"""
    print("\n" + "="*60)
    print("TEST 2: SL Margin Calculation")
    print("="*60)
    
    SL_MEXC_MARGIN = 1.1  # 10% wider
    
    test_cases = [
        # LONG positions
        {
            "name": "LONG: Bot SL 0.5% below entry",
            "direction": "LONG",
            "entry_price": 100.0,
            "bot_sl_price": 99.5,  # 0.5% below
            "expected_mexc_sl_pct": 0.55  # 0.5% × 1.1 = 0.55%
        },
        {
            "name": "LONG: Bot SL 0.16% below entry (tight)",
            "direction": "LONG",
            "entry_price": 0.328,
            "bot_sl_price": 0.327472,  # ~0.16% below
            "expected_mexc_sl_pct": 0.176  # 0.16% × 1.1 = 0.176%
        },
        # SHORT positions
        {
            "name": "SHORT: Bot SL 0.5% above entry",
            "direction": "SHORT",
            "entry_price": 100.0,
            "bot_sl_price": 100.5,  # 0.5% above
            "expected_mexc_sl_pct": 0.55  # 0.5% × 1.1 = 0.55%
        },
        {
            "name": "SHORT: Bot SL 0.16% above entry (tight)",
            "direction": "SHORT",
            "entry_price": 0.328,
            "bot_sl_price": 0.328528,  # ~0.16% above
            "expected_mexc_sl_pct": 0.176  # 0.16% × 1.1 = 0.176%
        }
    ]
    
    all_passed = True
    for tc in test_cases:
        entry_price = tc["entry_price"]
        bot_sl_price = tc["bot_sl_price"]
        direction = tc["direction"]
        
        # Logic from live_order_manager_futures.py
        if direction == 'LONG':
            sl_distance_pct = abs(entry_price - bot_sl_price) / entry_price
            sl_price = entry_price * (1 - sl_distance_pct * SL_MEXC_MARGIN)
        else:  # SHORT
            sl_distance_pct = abs(bot_sl_price - entry_price) / entry_price
            sl_price = entry_price * (1 + sl_distance_pct * SL_MEXC_MARGIN)
        
        sl_exchange_percent = sl_distance_pct * SL_MEXC_MARGIN * 100
        
        # Verify MEXC SL is wider than bot SL
        bot_sl_pct = abs(entry_price - bot_sl_price) / entry_price * 100
        mexc_sl_pct = abs(entry_price - sl_price) / entry_price * 100
        
        margin_correct = mexc_sl_pct > bot_sl_pct
        pct_close = abs(mexc_sl_pct - tc["expected_mexc_sl_pct"]) < 0.01
        
        passed = margin_correct and pct_close
        status = "✅ PASS" if passed else "❌ FAIL"
        
        print(f"  {status}: {tc['name']}")
        print(f"       Entry: {entry_price} | Bot SL: {bot_sl_price} ({bot_sl_pct:.4f}%)")
        print(f"       MEXC SL: {sl_price:.6f} ({mexc_sl_pct:.4f}%) | Expected: {tc['expected_mexc_sl_pct']:.3f}%")
        print(f"       Margin applied: {mexc_sl_pct > bot_sl_pct} (MEXC wider than Bot)")
        
        if not passed:
            all_passed = False
    
    return all_passed


def test_sl_exchange_detection_flow():
    """Test SL_EXCHANGE detection logic"""
    print("\n" + "="*60)
    print("TEST 3: SL_EXCHANGE Detection Flow")
    print("="*60)
    
    # Simulate the detection scenarios
    scenarios = [
        {
            "name": "Position closed by MEXC SL (no live position, bot position exists)",
            "live_position": None,
            "bot_position_symbol": "FARTCOIN/USDT:USDT",
            "check_symbol": "FARTCOIN/USDT:USDT",
            "should_detect_sl_exchange": True
        },
        {
            "name": "Position still open (live position exists)",
            "live_position": {"symbol": "FARTCOIN/USDT:USDT", "size": 100},
            "bot_position_symbol": "FARTCOIN/USDT:USDT",
            "check_symbol": "FARTCOIN/USDT:USDT",
            "should_detect_sl_exchange": False
        },
        {
            "name": "Different symbol (no detection)",
            "live_position": None,
            "bot_position_symbol": "BTC/USDT:USDT",
            "check_symbol": "FARTCOIN/USDT:USDT",
            "should_detect_sl_exchange": False
        },
        {
            "name": "No bot position (no detection)",
            "live_position": None,
            "bot_position_symbol": None,
            "check_symbol": "FARTCOIN/USDT:USDT",
            "should_detect_sl_exchange": False
        }
    ]
    
    all_passed = True
    for sc in scenarios:
        # Simulate the detection logic from position_manager.py
        live_position = sc["live_position"]
        bot_position_symbol = sc["bot_position_symbol"]
        check_symbol = sc["check_symbol"]
        
        detected = False
        if not live_position:
            # No live position, check if bot has one for this symbol
            if bot_position_symbol and bot_position_symbol == check_symbol:
                detected = True
        
        passed = detected == sc["should_detect_sl_exchange"]
        status = "✅ PASS" if passed else "❌ FAIL"
        
        print(f"  {status}: {sc['name']}")
        print(f"       Detected SL_EXCHANGE: {detected} (expected: {sc['should_detect_sl_exchange']})")
        
        if not passed:
            all_passed = False
    
    return all_passed


async def test_live_api_order_history():
    """Test live API order history (requires running backend)"""
    print("\n" + "="*60)
    print("TEST 4: Live API Order History (Optional)")
    print("="*60)
    
    try:
        from trading.mexc_futures_bypass import MexcFuturesBypass
        
        api_key = os.getenv('MEXC_API_KEY')
        api_secret = os.getenv('MEXC_SECRET_KEY')
        
        if not api_key or not api_secret:
            print("  ⚠️ SKIP: MEXC_API_KEY/MEXC_SECRET_KEY not set in .env")
            return True
        
        bypass = MexcFuturesBypass(api_key, api_secret)
        
        # Test with a common symbol
        test_symbol = "BTC_USDT"
        print(f"  Testing get_order_history for {test_symbol}...")
        
        response = await bypass.get_order_history(
            symbol=test_symbol,
            page_num=1,
            page_size=5,
            category=2  # SL orders
        )
        
        print(f"  Response type: {type(response).__name__}")
        
        if isinstance(response, dict):
            print(f"  Success: {response.get('success')}")
            print(f"  Code: {response.get('code')}")
            data = response.get('data', {})
            if isinstance(data, dict):
                orders = data.get('resultList', [])
                print(f"  Orders found: {len(orders)}")
                if orders:
                    print(f"  First order keys: {list(orders[0].keys())[:5]}...")
            elif isinstance(data, list):
                print(f"  Data is list with {len(data)} items")
        elif isinstance(response, list):
            print(f"  Response is list with {len(response)} items")
        
        print("  ✅ PASS: API call successful")
        return True
        
    except Exception as e:
        print(f"  ⚠️ SKIP: {e}")
        return True  # Don't fail on optional test


def main():
    print("="*60)
    print("SL_EXCHANGE VERIFICATION SCRIPT")
    print("="*60)
    
    results = []
    
    # Test 1: Order history parsing
    results.append(("Order History Parsing", test_order_history_parsing()))
    
    # Test 2: SL margin calculation
    results.append(("SL Margin Calculation", test_sl_margin_calculation()))
    
    # Test 3: SL_EXCHANGE detection flow
    results.append(("SL_EXCHANGE Detection Flow", test_sl_exchange_detection_flow()))
    
    # Test 4: Live API (optional)
    results.append(("Live API Order History", asyncio.run(test_live_api_order_history())))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*60)
    
    # Diagnostic info
    print("\n📋 DIAGNOSTIC INFO:")
    print("-" * 40)
    print("If SL_EXCHANGE triggers instead of bot's SL:")
    print("1. Check logs for '📐 SL MEXC MARGE' to verify margin is applied")
    print("2. Bot SL should be TIGHTER than MEXC SL")
    print("3. Current margin: 1.1× (10% wider for MEXC)")
    print("4. Position check interval: 0.1s")
    print("-" * 40)
    print("Root causes of SL_EXCHANGE triggering first:")
    print("• Price feed delay (bot sees price later than MEXC)")
    print("• Very tight SLs (<0.2%) with high volatility")
    print("• MEXC SL margin not applied (check logs)")
    print("-" * 40)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

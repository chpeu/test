"""
Test des indicateurs techniques
"""
from core.indicators import Indicators


def test_indicators():
    """Test de tous les indicateurs"""
    print("Test Indicateurs Techniques...")
    
    # Données de test
    closes = [100, 101, 102, 103, 102, 101, 100, 99, 98, 97, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    
    # Test 1: EMA
    print("\n1. Test EMA(9)...")
    ema9 = Indicators.calculate_ema(closes, 9)
    print(f"   OK EMA9: {ema9:.2f}")
    
    # Test 2: RSI
    print("\n2. Test RSI(14)...")
    rsi = Indicators.calculate_rsi(closes, 14)
    print(f"   OK RSI: {rsi:.2f}")
    
    rsi_prev = Indicators.calculate_rsi_previous(closes, 14)
    print(f"   OK RSI Previous: {rsi_prev:.2f}")
    
    # Test 3: ATR
    print("\n3. Test ATR(14)...")
    atr = Indicators.calculate_atr(highs, lows, closes, 14)
    print(f"   OK ATR: {atr:.2f}")
    
    # Test 4: MACD
    print("\n4. Test MACD(3,10,16)...")
    macd = Indicators.calculate_macd(closes, 3, 10, 16)
    print(f"   OK MACD: {macd}")
    
    macd_prev = Indicators.calculate_macd_previous(closes, 3, 10, 16)
    print(f"   OK MACD Previous: {macd_prev}")
    
    # Test 5: Bollinger
    print("\n5. Test Bollinger Bands(20,2)...")
    bb = Indicators.calculate_bollinger_bands(closes, 20, 2)
    print(f"   OK BB: {bb}")
    
    # Test 6: ADX
    print("\n6. Test ADX(14)...")
    adx = Indicators.calculate_adx(highs, lows, closes, 14)
    print(f"   OK ADX: {adx}")
    
    # Test 7: Pattern
    print("\n7. Test Pattern Detection...")
    candle = {'open': 100, 'high': 105, 'low': 98, 'close': 104}
    pattern = Indicators.detect_pattern(candle)
    print(f"   OK Pattern: {pattern}")
    
    print("\nTOUS LES TESTS REUSSIS!")


if __name__ == "__main__":
    test_indicators()


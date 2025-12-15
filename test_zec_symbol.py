#!/usr/bin/env python3
"""Test pour vérifier le format du symbole ZEC dans CCXT"""
import ccxt

def test_zec_symbol():
    ex = ccxt.mexc({
        'options': {'defaultType': 'swap'},
        'enableRateLimit': True
    })

    try:
        markets = ex.load_markets()

        # Chercher tous les symboles contenant ZEC
        zec_symbols = [s for s in markets.keys() if 'ZEC' in s]

        print("=" * 60)
        print("SYMBOLES ZEC TROUVES DANS CCXT:")
        print("=" * 60)
        for symbol in zec_symbols:
            market = markets[symbol]
            print(f"Symbol: {symbol}")
            print(f"  Type: {market.get('type')}")
            print(f"  Quote: {market.get('quote')}")
            print(f"  Maker fee: {market.get('maker')}")
            print(f"  Taker fee: {market.get('taker')}")
            print()

        print("=" * 60)
        print("VERIFICATION EXCLUSION:")
        print("=" * 60)

        from config import TRADING_CONFIG
        excluded = set(TRADING_CONFIG.get('excluded_symbols', []))
        print(f"Excluded symbols config: {excluded}")
        print()

        for symbol in zec_symbols:
            is_excluded = symbol in excluded
            print(f"{symbol}: {'EXCLU' if is_excluded else 'NON EXCLU'}")

        print("=" * 60)

    finally:
        pass

if __name__ == "__main__":
    test_zec_symbol()

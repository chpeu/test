
import asyncio
import os
import sys
from dotenv import load_dotenv
import ccxt.async_support as ccxt

async def dump_mexc_markets():
    print("🔍 Dumping MEXC Futures Markets for filter analysis...")
    load_dotenv()
    
    exchange = ccxt.mexc({
        'options': {'defaultType': 'swap'},
        'enableRateLimit': True
    })
    
    try:
        markets = await exchange.load_markets()
        print(f"Total markets: {len(markets)}")
        
        futures_usdt = [m for s, m in markets.items() if m.get('type') == 'swap' and m.get('quote') == 'USDT' and m.get('active')]
        print(f"Total USDT Futures active: {len(futures_usdt)}")
        
        # Test Fee Filter (0.06%)
        pass_fee = [m for m in futures_usdt if m.get('taker', 0) <= 0.0006]
        print(f"Paires passant le filtre taker_fee <= 0.06%: {len(pass_fee)}")
        
        # Sample some tickers for Volume and Funding
        sample_size = 50
        sample_symbols = [m['symbol'] for m in pass_fee[:sample_size]]
        
        print(f"\n📈 Analyse détaillée sur un échantillon de {len(sample_symbols)} paires:")
        tickers = await exchange.fetch_tickers(sample_symbols)
        
        for symbol in sample_symbols:
            ticker = tickers.get(symbol, {})
            vol_24h = ticker.get('quoteVolume', 0)
            
            # Fetch funding
            funding_rate = 0.0
            try:
                funding = await exchange.fetch_funding_rate(symbol)
                funding_rate = float(funding.get('fundingRate', 0)) * 100
            except:
                pass
                
            fee = markets[symbol].get('taker', 0) * 100
            print(f"  - {symbol:15} | Vol24h: {vol_24h:10,.0f} | Funding: {funding_rate:8.4f}% | Taker Fee: {fee:6.4f}%")
            
    except Exception as e:
        print(f"💥 Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(dump_mexc_markets())

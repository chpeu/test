import asyncio
from api.mexc import get_mexc_client

async def check_btc_fees():
    client = get_mexc_client()
    print("Loading markets...")
    markets = await client.exchange.load_markets()
    
    btc_symbol = 'BTC/USDT:USDT'
    if btc_symbol in markets:
        market = markets[btc_symbol]
        print(f"Details for {btc_symbol}:")
        print(f"  Type: {market['type']}")
        print(f"  Quote: {market['quote']}")
        print(f"  Maker Fee: {market.get('maker')}")
        print(f"  Taker Fee: {market.get('taker')}")
        
        # Check volume 24h
        ticker = await client.exchange.fetch_ticker(btc_symbol)
        print(f"  Volume 24h: {ticker.get('quoteVolume')} USDT")
        
        # Check funding rate
        funding = await client.exchange.fetch_funding_rate(btc_symbol)
        print(f"  Funding Rate: {funding.get('fundingRate') * 100 if funding else 'N/A'}%")
    else:
        print(f"Symbol {btc_symbol} not found in markets.")
        # Print some symbols that ARE found
        print(f"Sample symbols: {list(markets.keys())[:10]}")

    await client.exchange.close()

if __name__ == "__main__":
    asyncio.run(check_btc_fees())

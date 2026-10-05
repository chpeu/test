import asyncio
from api.mexc import get_mexc_client

async def check_aster_specs():
    client = get_mexc_client()
    print("Loading markets...")
    markets = await client.exchange.load_markets()
    
    symbol = 'ASTER/USDT:USDT'
    if symbol in markets:
        market = markets[symbol]
        print(f"Details for {symbol}:")
        print(f"  Contract Size: {market.get('contractSize')}")
        print(f"  Type: {market.get('type')}")
        print(f"  Linear: {market.get('linear')}")
        print(f"  Inverse: {market.get('inverse')}")
        print(f"  Precision: {market.get('precision')}")
        print(f"  Limits: {market.get('limits')}")
    else:
        print(f"Symbol {symbol} not found in markets.")
        # Search for partial match
        matches = [s for s in markets.keys() if 'ASTER' in s]
        print(f"Matches for 'ASTER': {matches}")

    await client.exchange.close()

if __name__ == "__main__":
    asyncio.run(check_aster_specs())

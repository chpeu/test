"""
Script de diagnostic pour tester le token MEXC
"""
import asyncio
import aiohttp
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

async def test_token():
    token = os.getenv("MEXC_BROWSER_TOKEN", "")
    print(f"Token: {token[:30]}..." if len(token) > 30 else f"Token: {token}")
    print(f"Token length: {len(token)}")
    
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "authorization": token,
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": "https://www.mexc.com",
        "referer": "https://www.mexc.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    }
    
    # Test 1: Account asset (private endpoint)
    print("\n--- Test 1: /private/account/asset/USDT ---")
    async with aiohttp.ClientSession() as session:
        url = "https://futures.mexc.com/api/v1/private/account/asset/USDT"
        async with session.get(url, headers=headers) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Response: {data}")
    
    # Test 2: Public endpoint (should work without auth)
    print("\n--- Test 2: /public/market/ticker (public) ---")
    async with aiohttp.ClientSession() as session:
        url = "https://futures.mexc.com/api/v1/contract/ticker?symbol=BTC_USDT"
        async with session.get(url, headers=headers) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            success = data.get("success", False)
            print(f"Success: {success}")
            if success:
                print("Public API works!")
    
    # Test 3: Try with different auth header format
    print("\n--- Test 3: Bearer format ---")
    headers2 = headers.copy()
    headers2["authorization"] = f"Bearer {token}"
    async with aiohttp.ClientSession() as session:
        url = "https://futures.mexc.com/api/v1/private/account/asset/USDT"
        async with session.get(url, headers=headers2) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Response: {data}")

if __name__ == "__main__":
    asyncio.run(test_token())

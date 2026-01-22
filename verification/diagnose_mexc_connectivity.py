import asyncio
import os
import sys
import time
from dotenv import load_dotenv
import ccxt.async_support as ccxt

# Charger .env
load_dotenv()

async def diagnose_mexc():
    print("🔍 Diagnostic Connectivité MEXC...")
    
    api_key = os.getenv('MEXC_API_KEY')
    api_secret = os.getenv('MEXC_API_SECRET')
    
    print(f"🔑 API Key présente: {'✅ Oui' if api_key else '❌ Non'}")
    print(f"🔑 API Secret présent: {'✅ Oui' if api_secret else '❌ Non'}")
    
    if not api_key or not api_secret:
        print("❌ Diagnostic arrêté: Clés manquantes dans .env")
        return

    exchange = ccxt.mexc({
        'apiKey': api_key,
        'secret': api_secret,
        'options': {'defaultType': 'swap'},
        'enableRateLimit': True
    })

    try:
        print("\n🌐 1. Test connectivité publique (load_markets)...")
        start = time.time()
        await exchange.load_markets()
        print(f"✅ Succès ({time.time() - start:.2f}s)")

        print("\n🕒 2. Test Time Drift...")
        server_time = await exchange.fetch_time()
        local_time = int(time.time() * 1000)
        drift = server_time - local_time
        print(f"⏱️ Heure Serveur: {server_time}")
        print(f"⏱️ Heure Locale:  {local_time}")
        print(f"⏱️ Drift: {drift}ms")
        if abs(drift) > 5000:
            print("⚠️ Attention: Drift important (>5s), peut causer des 403/401")
        else:
            print("✅ Drift acceptable")

        print("\n🔐 3. Test Authentification (fetch_balance)...")
        try:
            balance = await exchange.fetch_balance()
            print("✅ Authentification réussie")
            print(f"💰 Balance USDT: {balance.get('USDT', {}).get('total', 'N/A')}")
        except Exception as e:
            print(f"❌ Erreur Authentification: {e}")
            if "403" in str(e) or "Access Denied" in str(e):
                print("🚨 CONFIRMÉ: Erreur 403 Forbidden sur requête privée.")
                print("👉 Causes possibles: IP non autorisée, clés sans permissions 'Trade', ou compte restreint.")

        print("\n📝 4. Test Permissions Ordre (create_order - simulation via fetch_open_orders)...")
        try:
            orders = await exchange.fetch_open_orders()
            print(f"✅ Lecture ordres réussie ({len(orders)} ouverts)")
        except Exception as e:
            print(f"❌ Erreur Lecture Ordres: {e}")

    except Exception as e:
        print(f"💥 Erreur critique: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(diagnose_mexc())

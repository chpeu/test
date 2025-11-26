#!/usr/bin/env python3
"""
Test du mode Bypass MEXC Futures

Usage:
    # Test connexion (sans token)
    python test_bypass.py --test-public
    
    # Test avec token (balance, positions)
    python test_bypass.py --token "WEB_xxx..."
    
    # Test ordre DRY_RUN
    python test_bypass.py --token "WEB_xxx..." --dry-run
    
    # Test ordre LIVE (ATTENTION: passe un vrai ordre!)
    python test_bypass.py --token "WEB_xxx..." --live --symbol BTC_USDT --amount 0.001
"""

import asyncio
import argparse
import logging
import sys
import os
import io

# Fix encodage Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading.mexc_futures_bypass import (
    MexcFuturesBypass,
    OrderSide,
    OrderType,
    OpenType,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


async def test_public_endpoints():
    """Tester les endpoints publics (sans authentification)"""
    print("\n" + "="*60)
    print("🧪 TEST ENDPOINTS PUBLICS")
    print("="*60)
    
    # Créer client sans token (endpoints publics uniquement)
    client = MexcFuturesBypass(browser_token="dummy", debug=True)
    
    # Test ticker
    print("\n📊 Test getTicker(BTC_USDT)...")
    ticker = await client.get_ticker("BTC_USDT")
    if ticker.get("success"):
        data = ticker.get("data", {})
        print(f"   ✅ BTC Price: {data.get('lastPrice', 'N/A')}")
        print(f"   ✅ 24h Volume: {data.get('volume24', 'N/A')}")
    else:
        print(f"   ❌ Erreur: {ticker}")
    
    # Test contract detail
    print("\n📋 Test getContractDetail(BTC_USDT)...")
    detail = await client.get_contract_detail("BTC_USDT")
    if detail.get("success"):
        data = detail.get("data", [{}])[0] if isinstance(detail.get("data"), list) else detail.get("data", {})
        print(f"   ✅ Symbol: {data.get('symbol', 'N/A')}")
        print(f"   ✅ Min Vol: {data.get('minVol', 'N/A')}")
        print(f"   ✅ Max Leverage: {data.get('maxLeverage', 'N/A')}")
    else:
        print(f"   ❌ Erreur: {detail}")
    
    await client.close()
    print("\n✅ Tests endpoints publics terminés")


async def test_private_endpoints(token: str):
    """Tester les endpoints privés (avec authentification)"""
    print("\n" + "="*60)
    print("🔐 TEST ENDPOINTS PRIVÉS")
    print("="*60)
    
    client = MexcFuturesBypass(browser_token=token, debug=True)
    
    # Test balance
    print("\n💰 Test getAccountAsset(USDT)...")
    asset = await client.get_account_asset("USDT")
    if asset:
        print(f"   ✅ Available Balance: {asset.available_balance:.4f} USDT")
        print(f"   ✅ Equity: {asset.equity:.4f} USDT")
        print(f"   ✅ Unrealized PnL: {asset.unrealized_pnl:.4f} USDT")
    else:
        print("   ❌ Erreur récupération balance (token invalide?)")
    
    # Test positions
    print("\n📈 Test getOpenPositions()...")
    positions = await client.get_open_positions()
    if positions:
        print(f"   ✅ {len(positions)} position(s) ouverte(s):")
        for pos in positions:
            print(f"      - {pos.symbol} {pos.direction} | Vol: {pos.hold_vol} | PnL: {pos.unrealized_pnl:.2f}")
    else:
        print("   ℹ️ Aucune position ouverte")
    
    # Test connexion
    print("\n🔌 Test testConnection()...")
    connected = await client.test_connection()
    print(f"   {'✅' if connected else '❌'} Connexion: {'OK' if connected else 'FAILED'}")
    
    await client.close()
    print("\n✅ Tests endpoints privés terminés")


async def test_dry_run_order(token: str):
    """Tester un ordre en mode DRY_RUN (simulation)"""
    print("\n" + "="*60)
    print("🧪 TEST ORDRE DRY_RUN")
    print("="*60)
    
    from trading.live_order_manager_futures import LiveOrderManagerFutures
    
    # Créer manager en mode DRY_RUN
    manager = LiveOrderManagerFutures(
        browser_token=token,
        default_leverage=10,
        dry_run=True,
        use_bypass=True
    )
    
    print("\n📤 Test ouverture position LONG BTC...")
    result = manager.open_position(
        symbol="BTC/USDT",
        direction="LONG",
        entry_price=50000.0,
        size_usdt=100.0,
        leverage=10
    )
    
    if result.success:
        print(f"   ✅ Order ID: {result.order_id}")
        print(f"   ✅ Filled Price: {result.filled_price}")
        print(f"   ✅ Filled Amount: {result.filled_amount}")
        print(f"   ✅ Leverage: {result.leverage}x")
        print(f"   ✅ Liquidation Price: {result.liquidation_price}")
        print(f"   ✅ Latency: {result.latency_ms:.0f}ms")
    else:
        print(f"   ❌ Erreur: {result.error_message}")
    
    print("\n📥 Test fermeture position...")
    close_result = manager.close_position(
        symbol="BTC/USDT",
        direction="LONG",
        entry_price=50000.0,
        current_price=50500.0,  # +1%
        size_amount=result.filled_amount if result.success else 0.002
    )
    
    if close_result.success:
        print(f"   ✅ Order ID: {close_result.order_id}")
        print(f"   ✅ PnL: {close_result.actual_pnl_usdt:+.2f} USDT")
    else:
        print(f"   ❌ Erreur: {close_result.error_message}")
    
    print("\n📊 Stats:")
    stats = manager.get_stats()
    print(f"   Orders placed: {stats['orders_placed']}")
    print(f"   Orders filled: {stats['orders_filled']}")
    print(f"   Total PnL: {stats['total_pnl_usdt']:+.2f} USDT")
    
    print("\n✅ Tests DRY_RUN terminés")


async def test_live_order(token: str, symbol: str, amount: float):
    """Tester un ordre LIVE (⚠️ ATTENTION: passe un vrai ordre!)"""
    print("\n" + "="*60)
    print("⚠️  TEST ORDRE LIVE - ARGENT RÉEL!")
    print("="*60)
    
    confirm = input(f"\n⚠️ Voulez-vous vraiment passer un ordre LIVE sur {symbol}? (oui/non): ")
    if confirm.lower() != "oui":
        print("❌ Annulé")
        return
    
    client = MexcFuturesBypass(browser_token=token, debug=True)
    
    # Récupérer prix actuel
    ticker = await client.get_ticker(symbol)
    if not ticker.get("success"):
        print(f"❌ Impossible de récupérer le prix de {symbol}")
        await client.close()
        return
    
    current_price = float(ticker.get("data", {}).get("lastPrice", 0))
    print(f"\n📊 Prix actuel {symbol}: {current_price}")
    
    # Passer ordre LONG market
    print(f"\n📤 Passage ordre LONG {symbol} | Vol: {amount} | Leverage: 10x...")
    result = await client.submit_order(
        symbol=symbol,
        side=OrderSide.OPEN_LONG,
        vol=amount,
        price=current_price,
        order_type=OrderType.MARKET,
        open_type=OpenType.ISOLATED,
        leverage=10
    )
    
    if result.success:
        print(f"   ✅ ORDRE PASSÉ!")
        print(f"   ✅ Order ID: {result.order_id}")
        print(f"   ✅ Data: {result.data}")
        
        # Attendre 2 secondes puis fermer
        print("\n⏳ Attente 2 secondes avant fermeture...")
        await asyncio.sleep(2)
        
        # Fermer position
        print(f"\n📥 Fermeture position...")
        close_result = await client.submit_order(
            symbol=symbol,
            side=OrderSide.CLOSE_LONG,
            vol=amount,
            price=current_price,
            order_type=OrderType.MARKET,
            open_type=OpenType.ISOLATED,
            leverage=10,
            reduce_only=True
        )
        
        if close_result.success:
            print(f"   ✅ Position fermée! Order ID: {close_result.order_id}")
        else:
            print(f"   ❌ Erreur fermeture: {close_result.error_message}")
    else:
        print(f"   ❌ ERREUR: {result.error_message}")
        print(f"   ❌ Code: {result.error_code}")
        print(f"   ❌ Data: {result.data}")
    
    await client.close()
    print("\n✅ Test LIVE terminé")


def main():
    parser = argparse.ArgumentParser(description="Test MEXC Futures Bypass Mode")
    parser.add_argument("--test-public", action="store_true", help="Tester endpoints publics")
    parser.add_argument("--token", type=str, help="Browser token (WEB_xxx...)")
    parser.add_argument("--dry-run", action="store_true", help="Test ordre DRY_RUN")
    parser.add_argument("--live", action="store_true", help="Test ordre LIVE (⚠️ argent réel!)")
    parser.add_argument("--symbol", type=str, default="BTC_USDT", help="Symbole pour test LIVE")
    parser.add_argument("--amount", type=float, default=0.001, help="Quantité pour test LIVE")
    
    args = parser.parse_args()
    
    if args.test_public:
        asyncio.run(test_public_endpoints())
    elif args.token:
        if args.live:
            asyncio.run(test_live_order(args.token, args.symbol, args.amount))
        elif args.dry_run:
            asyncio.run(test_dry_run_order(args.token))
        else:
            asyncio.run(test_private_endpoints(args.token))
    else:
        print("Usage:")
        print("  python test_bypass.py --test-public")
        print("  python test_bypass.py --token 'WEB_xxx...'")
        print("  python test_bypass.py --token 'WEB_xxx...' --dry-run")
        print("  python test_bypass.py --token 'WEB_xxx...' --live --symbol BTC_USDT --amount 0.001")


if __name__ == "__main__":
    main()

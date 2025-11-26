#!/usr/bin/env python3
"""
MEXC Futures Bypass Client
Utilise les endpoints browser (reverse-engineered) pour bypasser le blocage API futures.

Basé sur: https://github.com/oboshto/mexc-futures-sdk

⚠️ DISCLAIMER: Ce client utilise des endpoints non-officiels.
   MEXC ne supporte pas officiellement le trading futures via API.
   Utiliser à vos propres risques.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, List, Optional, Union

import aiohttp
import websockets
import random

logger = logging.getLogger(__name__)

# ============================================================================
# Rate Limiting & Protection Anti-Ban
# ============================================================================

class RateLimiter:
    """
    Rate limiter pour éviter le bannissement MEXC
    
    Limites estimées (non-documentées):
    - REST API: ~10 requêtes/seconde
    - WebSocket: ~5 messages/seconde
    """
    
    def __init__(self, max_requests_per_second: float = 5.0):
        self.max_requests = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()
        self.request_count = 0
        self.request_count_window_start = 0.0
    
    async def acquire(self):
        """Attendre si nécessaire pour respecter le rate limit"""
        async with self._lock:
            now = time.time()
            
            # Reset compteur toutes les secondes
            if now - self.request_count_window_start >= 1.0:
                self.request_count = 0
                self.request_count_window_start = now
            
            # Vérifier si on dépasse la limite
            if self.request_count >= self.max_requests:
                wait_time = 1.0 - (now - self.request_count_window_start)
                if wait_time > 0:
                    logger.debug(f"⏳ Rate limit: attente {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    self.request_count = 0
                    self.request_count_window_start = time.time()
            
            # Ajouter un délai minimum entre requêtes + jitter aléatoire
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                jitter = random.uniform(0.05, 0.15)  # 50-150ms de jitter
                wait_time = self.min_interval - elapsed + jitter
                await asyncio.sleep(wait_time)
            
            self.last_request_time = time.time()
            self.request_count += 1


# Rate limiter global
_rate_limiter = RateLimiter(max_requests_per_second=3.0)  # Conservateur: 3 req/s


# ============================================================================
# Enums et Types
# ============================================================================

class OrderSide(IntEnum):
    """Direction de l'ordre"""
    OPEN_LONG = 1      # Ouvrir position LONG
    CLOSE_SHORT = 2    # Fermer position SHORT
    OPEN_SHORT = 3     # Ouvrir position SHORT
    CLOSE_LONG = 4     # Fermer position LONG


class OrderType(IntEnum):
    """Type d'ordre"""
    LIMIT = 1          # Ordre limite
    POST_ONLY = 2      # Post Only Maker
    IOC = 3            # Immediate or Cancel
    FOK = 4            # Fill or Kill
    MARKET = 5         # Ordre market
    CONVERT = 6        # Convert market to current price


class OpenType(IntEnum):
    """Type de marge"""
    ISOLATED = 1       # Marge isolée
    CROSS = 2          # Marge croisée


class OrderState(IntEnum):
    """État de l'ordre"""
    UNINFORMED = 1
    UNCOMPLETED = 2
    COMPLETED = 3
    CANCELLED = 4
    INVALID = 5


class PositionType(IntEnum):
    """Type de position"""
    LONG = 1
    SHORT = 2


@dataclass
class OrderResult:
    """Résultat d'un ordre"""
    success: bool
    order_id: Optional[int] = None
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    data: Optional[Dict] = None


@dataclass
class Position:
    """Position ouverte"""
    position_id: int
    symbol: str
    position_type: int  # 1=long, 2=short
    open_type: int      # 1=isolated, 2=cross
    hold_vol: float     # Volume détenu
    hold_avg_price: float
    liquidate_price: float
    leverage: int
    unrealized_pnl: float
    margin: float
    
    @property
    def direction(self) -> str:
        return "LONG" if self.position_type == 1 else "SHORT"


@dataclass
class AccountAsset:
    """Asset du compte"""
    currency: str
    available_balance: float
    frozen_balance: float
    equity: float
    unrealized_pnl: float


# ============================================================================
# Endpoints
# ============================================================================

ENDPOINTS = {
    # Private endpoints (require authentication)
    "SUBMIT_ORDER": "/private/order/submit",
    "CANCEL_ORDER": "/private/order/cancel",
    "CANCEL_ALL_ORDERS": "/private/order/cancel_all",
    "GET_ORDER": "/private/order/get",
    "ORDER_HISTORY": "/private/order/list/history_orders",
    "OPEN_POSITIONS": "/private/position/open_positions",
    "POSITION_HISTORY": "/private/position/list/history_positions",
    "ACCOUNT_ASSET": "/private/account/asset",
    
    # Public endpoints
    "TICKER": "/contract/ticker",
    "CONTRACT_DETAIL": "/contract/detail",
    "CONTRACT_DEPTH": "/contract/depth",
}

# Headers par défaut (simule navigateur Chrome)
DEFAULT_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "dnt": "1",
    "origin": "https://www.mexc.com",
    "pragma": "no-cache",
    "referer": "https://www.mexc.com/",
    "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "x-language": "en-US",
}


# ============================================================================
# Signature MEXC
# ============================================================================

def mexc_sign(auth_token: str, body: Any) -> tuple:
    """
    Générer signature MEXC pour requêtes POST
    
    Algorithme (reverse-engineered):
    1. timestamp = Date.now() en millisecondes
    2. g = MD5(authToken + timestamp)[7:]  (substring à partir de l'index 7)
    3. s = JSON.stringify(body)
    4. sign = MD5(timestamp + s + g)
    
    Args:
        auth_token: Token browser (WEB_xxx...)
        body: Corps de la requête (dict ou list)
        
    Returns:
        Tuple (timestamp, signature)
    """
    timestamp = str(int(time.time() * 1000))
    
    # Étape 1: g = MD5(authToken + timestamp)[7:]
    hash1 = hashlib.md5((auth_token + timestamp).encode()).hexdigest()
    g = hash1[7:]
    
    # Étape 2: s = JSON.stringify(body) - format compact
    s = json.dumps(body, separators=(',', ':'))
    
    # Étape 3: sign = MD5(timestamp + s + g)
    sign = hashlib.md5((timestamp + s + g).encode()).hexdigest()
    
    return timestamp, sign


def ws_sign(api_key: str, secret_key: str) -> tuple:
    """
    Générer signature WebSocket (HMAC SHA256)
    
    Args:
        api_key: Clé API MEXC
        secret_key: Secret API MEXC
        
    Returns:
        Tuple (timestamp, signature)
    """
    timestamp = str(int(time.time() * 1000))
    signature_string = f"{api_key}{timestamp}"
    signature = hmac.new(
        secret_key.encode(),
        signature_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return timestamp, signature


# ============================================================================
# Client REST
# ============================================================================

class MexcFuturesBypass:
    """
    Client REST pour MEXC Futures utilisant les endpoints browser
    
    Usage:
        client = MexcFuturesBypass(browser_token="WEB_xxx...")
        
        # Récupérer balance
        balance = await client.get_account_asset("USDT")
        
        # Passer un ordre
        result = await client.submit_order(
            symbol="BTC_USDT",
            side=OrderSide.OPEN_LONG,
            vol=0.001,
            price=50000,
            order_type=OrderType.MARKET,
            leverage=10
        )
    """
    
    BASE_URL = "https://futures.mexc.com/api/v1"
    
    def __init__(
        self,
        browser_token: str,
        timeout: int = 30,
        debug: bool = False
    ):
        """
        Initialiser le client
        
        Args:
            browser_token: Token d'authentification browser (WEB_xxx...)
                          Récupérable depuis DevTools > Network > Headers > authorization
            timeout: Timeout des requêtes en secondes
            debug: Activer les logs de debug
        """
        self.browser_token = browser_token
        self.timeout = timeout
        self.debug = debug
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Obtenir ou créer la session HTTP"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session
    
    async def close(self):
        """Fermer la session HTTP"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    def _build_headers(self, body: Any = None) -> Dict[str, str]:
        """
        Construire les headers pour une requête
        
        Args:
            body: Corps de la requête (pour signature POST)
            
        Returns:
            Dict des headers
        """
        headers = DEFAULT_HEADERS.copy()
        headers["authorization"] = self.browser_token
        
        # Ajouter signature pour les requêtes POST avec body
        if body is not None:
            timestamp, sign = mexc_sign(self.browser_token, body)
            headers["x-mxc-nonce"] = timestamp
            headers["x-mxc-sign"] = sign
            
            if self.debug:
                logger.debug(f"🔐 MEXC Signature: nonce={timestamp}, sign={sign}")
        
        return headers
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        body: Any = None,
        skip_rate_limit: bool = False
    ) -> Dict:
        """
        Effectuer une requête HTTP avec rate limiting
        
        Args:
            method: GET ou POST
            endpoint: Endpoint (ex: /private/order/submit)
            params: Query params (GET)
            body: Corps JSON (POST)
            skip_rate_limit: Ignorer le rate limit (pour urgences)
            
        Returns:
            Réponse JSON
        """
        # 🔥 Rate limiting pour éviter bannissement
        if not skip_rate_limit:
            await _rate_limiter.acquire()
        
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"
        headers = self._build_headers(body)
        
        if self.debug:
            logger.debug(f"🌐 {method} {url}")
            if body:
                logger.debug(f"📦 Body: {json.dumps(body)}")
        
        try:
            if method == "GET":
                async with session.get(url, headers=headers, params=params) as resp:
                    # Vérifier le status HTTP
                    if resp.status == 429:
                        logger.warning("⚠️ Rate limit atteint (429) - attente 5s")
                        await asyncio.sleep(5)
                        return {"success": False, "code": 429, "message": "Rate limit exceeded"}
                    if resp.status == 403:
                        logger.error("❌ Accès refusé (403) - token expiré ou IP bannie?")
                        return {"success": False, "code": 403, "message": "Access denied - check token"}
                    data = await resp.json()
            else:  # POST
                async with session.post(url, headers=headers, json=body) as resp:
                    if resp.status == 429:
                        logger.warning("⚠️ Rate limit atteint (429) - attente 5s")
                        await asyncio.sleep(5)
                        return {"success": False, "code": 429, "message": "Rate limit exceeded"}
                    if resp.status == 403:
                        logger.error("❌ Accès refusé (403) - token expiré ou IP bannie?")
                        return {"success": False, "code": 403, "message": "Access denied - check token"}
                    data = await resp.json()
            
            if self.debug:
                logger.debug(f"✅ Response: {json.dumps(data)}")
            
            return data
            
        except aiohttp.ClientError as e:
            logger.error(f"❌ HTTP Error: {e}")
            return {"success": False, "code": -1, "message": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON Decode Error: {e}")
            return {"success": False, "code": -2, "message": "Invalid JSON response"}
    
    # ========================================================================
    # Trading Methods
    # ========================================================================
    
    async def submit_order(
        self,
        symbol: str,
        side: Union[OrderSide, int],
        vol: float,
        price: float,
        order_type: Union[OrderType, int] = OrderType.MARKET,
        open_type: Union[OpenType, int] = OpenType.ISOLATED,
        leverage: int = 10,
        position_id: Optional[int] = None,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        reduce_only: bool = False,
        external_oid: Optional[str] = None
    ) -> OrderResult:
        """
        Soumettre un ordre
        
        Args:
            symbol: Symbole (ex: "BTC_USDT")
            side: Direction (1=open long, 2=close short, 3=open short, 4=close long)
            vol: Volume (nombre de contrats)
            price: Prix (requis même pour market orders)
            order_type: Type d'ordre (1=limit, 5=market)
            open_type: Type de marge (1=isolated, 2=cross)
            leverage: Levier (1-125)
            position_id: ID position (pour fermeture)
            stop_loss_price: Prix SL
            take_profit_price: Prix TP
            reduce_only: Reduce only (one-way mode)
            external_oid: ID externe optionnel
            
        Returns:
            OrderResult avec order_id si succès
        """
        body = {
            "symbol": symbol,
            "side": int(side),
            "vol": vol,
            "price": price,
            "type": int(order_type),
            "openType": int(open_type),
            "leverage": leverage,
        }
        
        if position_id is not None:
            body["positionId"] = position_id
        if stop_loss_price is not None:
            body["stopLossPrice"] = stop_loss_price
        if take_profit_price is not None:
            body["takeProfitPrice"] = take_profit_price
        if reduce_only:
            body["reduceOnly"] = True
        if external_oid:
            body["externalOid"] = external_oid
        
        logger.info(f"🚀 Submit order: {symbol} side={side} vol={vol} price={price} leverage={leverage}x")
        
        response = await self._request("POST", ENDPOINTS["SUBMIT_ORDER"], body=body)
        
        if response.get("success") and response.get("code") == 0:
            order_id = response.get("data")
            logger.info(f"✅ Order submitted: ID={order_id}")
            return OrderResult(success=True, order_id=order_id, data=response)
        else:
            error_msg = response.get("message", "Unknown error")
            error_code = response.get("code", -1)
            logger.error(f"❌ Order failed: code={error_code}, message={error_msg}")
            return OrderResult(
                success=False,
                error_code=error_code,
                error_message=error_msg,
                data=response
            )
    
    async def cancel_order(self, order_ids: List[int]) -> Dict:
        """
        Annuler des ordres
        
        Args:
            order_ids: Liste des IDs d'ordres à annuler (max 50)
            
        Returns:
            Réponse avec résultats par ordre
        """
        if not order_ids:
            return {"success": False, "message": "No order IDs provided"}
        if len(order_ids) > 50:
            return {"success": False, "message": "Cannot cancel more than 50 orders at once"}
        
        logger.info(f"🛑 Cancel orders: {order_ids}")
        
        response = await self._request("POST", ENDPOINTS["CANCEL_ORDER"], body=order_ids)
        
        if response.get("success"):
            logger.info(f"✅ Orders cancelled")
        else:
            logger.error(f"❌ Cancel failed: {response}")
        
        return response
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict:
        """
        Annuler tous les ordres
        
        Args:
            symbol: Symbole optionnel (si None, annule tous)
            
        Returns:
            Réponse
        """
        body = {}
        if symbol:
            body["symbol"] = symbol
        
        logger.info(f"🛑 Cancel all orders: symbol={symbol or 'ALL'}")
        
        return await self._request("POST", ENDPOINTS["CANCEL_ALL_ORDERS"], body=body)
    
    async def get_order(self, order_id: int) -> Dict:
        """
        Récupérer détails d'un ordre
        
        Args:
            order_id: ID de l'ordre
            
        Returns:
            Détails de l'ordre
        """
        endpoint = f"{ENDPOINTS['GET_ORDER']}/{order_id}"
        return await self._request("GET", endpoint)
    
    async def get_order_history(
        self,
        symbol: str,
        page_num: int = 1,
        page_size: int = 20,
        states: int = 0,
        category: int = 0
    ) -> Dict:
        """
        Récupérer historique des ordres
        
        Args:
            symbol: Symbole
            page_num: Numéro de page
            page_size: Taille de page
            states: Filtre états
            category: Filtre catégorie
            
        Returns:
            Liste des ordres
        """
        params = {
            "symbol": symbol,
            "page_num": page_num,
            "page_size": page_size,
            "states": states,
            "category": category,
        }
        return await self._request("GET", ENDPOINTS["ORDER_HISTORY"], params=params)
    
    # ========================================================================
    # Position Methods
    # ========================================================================
    
    async def get_open_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        Récupérer les positions ouvertes
        
        Args:
            symbol: Symbole optionnel pour filtrer
            
        Returns:
            Liste des positions
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        response = await self._request("GET", ENDPOINTS["OPEN_POSITIONS"], params=params)
        
        if not response.get("success") or response.get("code") != 0:
            logger.error(f"❌ Failed to get positions: {response}")
            return []
        
        positions = []
        for p in response.get("data", []):
            try:
                positions.append(Position(
                    position_id=p.get("positionId"),
                    symbol=p.get("symbol"),
                    position_type=p.get("positionType"),
                    open_type=p.get("openType"),
                    hold_vol=float(p.get("holdVol", 0)),
                    hold_avg_price=float(p.get("holdAvgPrice", 0)),
                    liquidate_price=float(p.get("liquidatePrice", 0)),
                    leverage=int(p.get("leverage", 1)),
                    unrealized_pnl=float(p.get("unrealized", 0)),
                    margin=float(p.get("im", 0)),
                ))
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"⚠️ Error parsing position: {e}")
        
        return positions
    
    async def get_position_history(
        self,
        symbol: Optional[str] = None,
        position_type: Optional[int] = None,
        page_num: int = 1,
        page_size: int = 20
    ) -> Dict:
        """
        Récupérer historique des positions
        
        Args:
            symbol: Symbole optionnel
            position_type: 1=long, 2=short
            page_num: Numéro de page
            page_size: Taille de page
            
        Returns:
            Historique des positions
        """
        params = {
            "page_num": page_num,
            "page_size": page_size,
        }
        if symbol:
            params["symbol"] = symbol
        if position_type:
            params["type"] = position_type
        
        return await self._request("GET", ENDPOINTS["POSITION_HISTORY"], params=params)
    
    # ========================================================================
    # Account Methods
    # ========================================================================
    
    async def get_account_asset(self, currency: str = "USDT") -> Optional[AccountAsset]:
        """
        Récupérer balance d'un asset
        
        Args:
            currency: Devise (ex: "USDT")
            
        Returns:
            AccountAsset ou None
        """
        endpoint = f"{ENDPOINTS['ACCOUNT_ASSET']}/{currency}"
        response = await self._request("GET", endpoint)
        
        if not response.get("success") or response.get("code") != 0:
            logger.error(f"❌ Failed to get asset: {response}")
            return None
        
        data = response.get("data", {})
        try:
            return AccountAsset(
                currency=data.get("currency", currency),
                available_balance=float(data.get("availableBalance", 0)),
                frozen_balance=float(data.get("frozenBalance", 0)),
                equity=float(data.get("equity", 0)),
                unrealized_pnl=float(data.get("unrealized", 0)),
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"❌ Error parsing asset: {e}")
            return None
    
    # ========================================================================
    # Market Data Methods
    # ========================================================================
    
    async def get_ticker(self, symbol: str) -> Dict:
        """
        Récupérer ticker d'un symbole
        
        Args:
            symbol: Symbole (ex: "BTC_USDT")
            
        Returns:
            Données ticker
        """
        return await self._request("GET", ENDPOINTS["TICKER"], params={"symbol": symbol})
    
    async def get_contract_detail(self, symbol: Optional[str] = None) -> Dict:
        """
        Récupérer détails d'un contrat
        
        Args:
            symbol: Symbole optionnel
            
        Returns:
            Détails du contrat
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", ENDPOINTS["CONTRACT_DETAIL"], params=params)
    
    async def get_contract_depth(self, symbol: str, limit: int = 20) -> Dict:
        """
        Récupérer carnet d'ordres
        
        Args:
            symbol: Symbole
            limit: Profondeur
            
        Returns:
            Carnet d'ordres
        """
        endpoint = f"{ENDPOINTS['CONTRACT_DEPTH']}/{symbol}"
        return await self._request("GET", endpoint, params={"limit": limit})
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    async def test_connection(self) -> bool:
        """
        Tester la connexion API
        
        Returns:
            True si connexion OK
        """
        try:
            response = await self.get_ticker("BTC_USDT")
            return response.get("success", False)
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
    
    def convert_symbol(self, ccxt_symbol: str) -> str:
        """
        Convertir symbole format ccxt vers format MEXC
        
        Args:
            ccxt_symbol: "BTC/USDT:USDT" ou "BTC/USDT"
            
        Returns:
            "BTC_USDT"
        """
        # Retirer le :USDT si présent
        symbol = ccxt_symbol.replace(":USDT", "")
        # Remplacer / par _
        return symbol.replace("/", "_")
    
    def convert_symbol_to_ccxt(self, mexc_symbol: str) -> str:
        """
        Convertir symbole format MEXC vers format ccxt
        
        Args:
            mexc_symbol: "BTC_USDT"
            
        Returns:
            "BTC/USDT:USDT"
        """
        # Remplacer _ par /
        base_quote = mexc_symbol.replace("_", "/")
        # Ajouter :USDT pour futures
        return f"{base_quote}:USDT"


# ============================================================================
# WebSocket Client
# ============================================================================

class MexcFuturesWebSocket:
    """
    Client WebSocket pour MEXC Futures
    
    Utilise les API Keys classiques (pas le browser token)
    
    Usage:
        ws = MexcFuturesWebSocket(api_key="xxx", secret_key="yyy")
        
        @ws.on_order_update
        def handle_order(data):
            print(f"Order update: {data}")
        
        await ws.connect()
        await ws.login()
        await ws.subscribe_to_all()
    """
    
    WS_URL = "wss://contract.mexc.com/edge"
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        auto_reconnect: bool = True,
        reconnect_interval: int = 5,
        ping_interval: int = 15,
        debug: bool = False
    ):
        """
        Initialiser le client WebSocket
        
        Args:
            api_key: Clé API MEXC
            secret_key: Secret API MEXC
            auto_reconnect: Reconnexion automatique
            reconnect_interval: Délai reconnexion (secondes)
            ping_interval: Intervalle ping (secondes)
            debug: Mode debug
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.ping_interval = ping_interval
        self.debug = debug
        
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._logged_in = False
        self._ping_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_order_update = None
        self._on_position_update = None
        self._on_asset_update = None
        self._on_connected = None
        self._on_disconnected = None
        self._on_error = None
    
    # ========================================================================
    # Decorators for callbacks
    # ========================================================================
    
    def on_order_update(self, func):
        """Décorateur pour callback order update"""
        self._on_order_update = func
        return func
    
    def on_position_update(self, func):
        """Décorateur pour callback position update"""
        self._on_position_update = func
        return func
    
    def on_asset_update(self, func):
        """Décorateur pour callback asset update"""
        self._on_asset_update = func
        return func
    
    def on_connected(self, func):
        """Décorateur pour callback connected"""
        self._on_connected = func
        return func
    
    def on_disconnected(self, func):
        """Décorateur pour callback disconnected"""
        self._on_disconnected = func
        return func
    
    def on_error(self, func):
        """Décorateur pour callback error"""
        self._on_error = func
        return func
    
    # ========================================================================
    # Connection Methods
    # ========================================================================
    
    async def connect(self):
        """Connecter au WebSocket"""
        logger.info("🔌 Connecting to MEXC Futures WebSocket...")
        
        try:
            self._ws = await websockets.connect(self.WS_URL)
            self._connected = True
            logger.info("✅ WebSocket connected")
            
            # Démarrer les tâches
            self._ping_task = asyncio.create_task(self._ping_loop())
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            if self._on_connected:
                await self._call_callback(self._on_connected)
                
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            if self._on_error:
                await self._call_callback(self._on_error, e)
            raise
    
    async def disconnect(self):
        """Déconnecter du WebSocket"""
        logger.info("🔌 Disconnecting WebSocket...")
        
        self.auto_reconnect = False
        self._connected = False
        self._logged_in = False
        
        # Annuler les tâches
        if self._ping_task:
            self._ping_task.cancel()
        if self._receive_task:
            self._receive_task.cancel()
        
        # Fermer la connexion
        if self._ws:
            await self._ws.close()
            self._ws = None
    
    async def login(self, subscribe: bool = True):
        """
        Se connecter (login) au WebSocket
        
        Args:
            subscribe: S'abonner automatiquement aux données privées
        """
        if not self._connected:
            raise RuntimeError("WebSocket not connected")
        
        timestamp, signature = ws_sign(self.api_key, self.secret_key)
        
        message = {
            "subscribe": subscribe,
            "method": "login",
            "param": {
                "apiKey": self.api_key,
                "signature": signature,
                "reqTime": timestamp,
            }
        }
        
        await self._send(message)
    
    async def subscribe_to_all(self):
        """S'abonner à toutes les données privées"""
        if not self._logged_in:
            raise RuntimeError("Must login first")
        
        await self._send({
            "method": "personal.filter",
            "param": {"filters": []}
        })
    
    async def subscribe_to_orders(self, symbols: Optional[List[str]] = None):
        """S'abonner aux mises à jour d'ordres"""
        filters = [{"filter": "order"}]
        if symbols:
            filters[0]["rules"] = symbols
        
        await self._send({
            "method": "personal.filter",
            "param": {"filters": filters}
        })
    
    async def subscribe_to_positions(self, symbols: Optional[List[str]] = None):
        """S'abonner aux mises à jour de positions"""
        filters = [{"filter": "position"}]
        if symbols:
            filters[0]["rules"] = symbols
        
        await self._send({
            "method": "personal.filter",
            "param": {"filters": filters}
        })
    
    async def subscribe_to_assets(self):
        """S'abonner aux mises à jour de balance"""
        await self._send({
            "method": "personal.filter",
            "param": {"filters": [{"filter": "asset"}]}
        })
    
    # ========================================================================
    # Internal Methods
    # ========================================================================
    
    async def _send(self, message: Dict):
        """Envoyer un message"""
        if self._ws and self._connected:
            msg_str = json.dumps(message)
            if self.debug:
                logger.debug(f"➡️ WS Send: {msg_str}")
            await self._ws.send(msg_str)
    
    async def _ping_loop(self):
        """Boucle de ping"""
        while self._connected:
            try:
                await asyncio.sleep(self.ping_interval)
                if self._connected:
                    await self._send({"method": "ping"})
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ping error: {e}")
    
    async def _receive_loop(self):
        """Boucle de réception"""
        while self._connected:
            try:
                if self._ws:
                    message = await self._ws.recv()
                    await self._handle_message(json.loads(message))
            except asyncio.CancelledError:
                break
            except websockets.ConnectionClosed as e:
                logger.warning(f"🔌 WebSocket closed: {e}")
                self._connected = False
                self._logged_in = False
                
                if self._on_disconnected:
                    await self._call_callback(self._on_disconnected, e)
                
                if self.auto_reconnect:
                    await self._reconnect()
                break
            except Exception as e:
                logger.error(f"❌ Receive error: {e}")
                if self._on_error:
                    await self._call_callback(self._on_error, e)
    
    async def _reconnect(self):
        """Reconnexion automatique"""
        logger.info(f"🔌 Reconnecting in {self.reconnect_interval}s...")
        await asyncio.sleep(self.reconnect_interval)
        
        try:
            await self.connect()
            await self.login()
            await self.subscribe_to_all()
        except Exception as e:
            logger.error(f"❌ Reconnect failed: {e}")
    
    async def _handle_message(self, message: Dict):
        """Traiter un message reçu"""
        if self.debug:
            logger.debug(f"⬅️ WS Recv: {json.dumps(message)}")
        
        channel = message.get("channel", "")
        data = message.get("data")
        
        # Pong
        if channel == "pong":
            return
        
        # Login response
        if channel == "rs.login":
            if data == "success" or (isinstance(data, dict) and data.get("code") == 0):
                self._logged_in = True
                logger.info("✅ WebSocket login successful")
            else:
                logger.error(f"❌ WebSocket login failed: {data}")
            return
        
        # Filter response
        if channel == "rs.personal.filter":
            if data == "success" or (isinstance(data, dict) and data.get("code") == 0):
                logger.info("✅ WebSocket filter set")
            return
        
        # Private data updates
        if channel == "push.personal.order" and self._on_order_update:
            await self._call_callback(self._on_order_update, data)
        elif channel == "push.personal.position" and self._on_position_update:
            await self._call_callback(self._on_position_update, data)
        elif channel == "push.personal.asset" and self._on_asset_update:
            await self._call_callback(self._on_asset_update, data)
    
    async def _call_callback(self, callback, *args):
        """Appeler un callback (sync ou async)"""
        if asyncio.iscoroutinefunction(callback):
            await callback(*args)
        else:
            callback(*args)
    
    @property
    def connected(self) -> bool:
        return self._connected
    
    @property
    def logged_in(self) -> bool:
        return self._logged_in


# ============================================================================
# Factory Function
# ============================================================================

def create_bypass_client(
    browser_token: Optional[str] = None,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    debug: bool = False
) -> tuple:
    """
    Créer les clients REST et WebSocket
    
    Args:
        browser_token: Token browser pour REST API
        api_key: Clé API pour WebSocket
        secret_key: Secret API pour WebSocket
        debug: Mode debug
        
    Returns:
        Tuple (rest_client, ws_client)
    """
    rest_client = None
    ws_client = None
    
    if browser_token:
        rest_client = MexcFuturesBypass(browser_token=browser_token, debug=debug)
    
    if api_key and secret_key:
        ws_client = MexcFuturesWebSocket(
            api_key=api_key,
            secret_key=secret_key,
            debug=debug
        )
    
    return rest_client, ws_client

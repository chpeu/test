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

class AdaptiveRateLimiter:
    """
    🔥 AMÉLIORATION 1: Rate limiter ADAPTATIF pour éviter le bannissement MEXC

    S'adapte automatiquement aux limites réelles de MEXC:
    - Réduit agressivement si 429 détecté (-30%)
    - Augmente progressivement si stable (+5% après 20 succès)
    - Stop immédiat si 403 (token expiré/IP bannie)

    Limites estimées (non-documentées):
    - REST API: ~10 requêtes/seconde
    - WebSocket: ~5 messages/seconde
    """

    def __init__(self, initial_rate: float = 3.0, min_rate: float = 1.0, max_rate: float = 10.0):
        self.max_requests = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.min_interval = 1.0 / initial_rate
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()
        self.request_count = 0
        self.request_count_window_start = 0.0

        # 🔥 Adaptation automatique
        self.consecutive_success = 0
        self.consecutive_429 = 0
        self.total_requests = 0
        self.total_429 = 0
        self.total_403 = 0
        self.disabled = False  # Si 403, désactiver complètement

    async def acquire(self):
        """Attendre si nécessaire pour respecter le rate limit"""
        if self.disabled:
            logger.error("❌ Rate limiter désactivé (403 détecté)")
            await asyncio.sleep(60)  # Attendre 60s avant retry
            return

        async with self._lock:
            now = time.time()

            # Reset compteur toutes les secondes
            if now - self.request_count_window_start >= 1.0:
                self.request_count = 0
                self.request_count_window_start = now

            # Vérifier si on dépasse la limite (adaptative)
            if self.request_count >= self.max_requests:
                wait_time = 1.0 - (now - self.request_count_window_start)
                if wait_time > 0:
                    logger.debug(f"⏳ Rate limit: attente {wait_time:.2f}s (rate={self.max_requests:.2f} req/s)")
                    await asyncio.sleep(wait_time)
                    self.request_count = 0
                    self.request_count_window_start = time.time()

            # Recalculer min_interval selon rate actuel
            self.min_interval = 1.0 / self.max_requests

            # Ajouter un délai minimum entre requêtes + jitter aléatoire
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                jitter = random.uniform(0.05, 0.15)  # 50-150ms de jitter
                wait_time = self.min_interval - elapsed + jitter
                await asyncio.sleep(wait_time)

            self.last_request_time = time.time()
            self.request_count += 1
            self.total_requests += 1

    def on_response_success(self):
        """🔥 Appelé après requête réussie (200)"""
        self.consecutive_success += 1
        self.consecutive_429 = 0  # Reset compteur 429

        # Augmenter progressivement le rate après 20 succès consécutifs
        if self.consecutive_success >= 20:
            old_rate = self.max_requests
            self.max_requests = min(self.max_requests * 1.05, self.max_rate)  # +5%, max 10 req/s
            if self.max_requests > old_rate:
                logger.info(f"📈 Rate limite augmenté: {old_rate:.2f} → {self.max_requests:.2f} req/s")
            self.consecutive_success = 0

    def on_response_429(self):
        """🔥 Appelé après détection 429 (rate limit exceeded)"""
        self.consecutive_429 += 1
        self.total_429 += 1
        self.consecutive_success = 0  # Reset compteur succès

        old_rate = self.max_requests
        self.max_requests = max(self.max_requests * 0.7, self.min_rate)  # -30%, min 1 req/s
        logger.warning(
            f"⚠️ 429 détecté ({self.consecutive_429}x consécutif) - "
            f"Rate limite réduit: {old_rate:.2f} → {self.max_requests:.2f} req/s"
        )

    def on_response_403(self):
        """🔥 Appelé après détection 403 (token expiré ou IP bannie)"""
        self.total_403 += 1
        self.disabled = True
        logger.error(
            f"❌ 403 détecté - Rate limiter DÉSACTIVÉ | "
            f"Token expiré ou IP bannie | Arrêt trading requis"
        )

    def get_stats(self) -> dict:
        """Récupérer statistiques du rate limiter"""
        return {
            'current_rate': self.max_requests,
            'total_requests': self.total_requests,
            'total_429': self.total_429,
            'total_403': self.total_403,
            'consecutive_success': self.consecutive_success,
            'disabled': self.disabled
        }


# Rate limiter global adaptatif
_rate_limiter = AdaptiveRateLimiter(initial_rate=3.0, min_rate=1.0, max_rate=10.0)


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


@dataclass
class ContractSpec:
    """Spécifications d'un contrat futures"""
    symbol: str
    min_vol: float          # Volume minimum (en contrats)
    max_vol: float          # Volume maximum (en contrats)
    vol_unit: float         # Unité de volume (step)
    price_unit: float       # Unité de prix (tick size)
    price_precision: int    # Décimales prix
    vol_precision: int      # Décimales volume
    contract_size: float = 1.0  # 🔥 Taille du contrat (1 contrat = X tokens)
    
    def round_volume(self, vol: float) -> float:
        """Arrondir le volume selon les specs du contrat"""
        # Arrondir au vol_unit le plus proche (vers le bas)
        if self.vol_unit > 0:
            vol = (vol // self.vol_unit) * self.vol_unit
        # Appliquer la précision
        vol = round(vol, self.vol_precision)
        # 🔥 FIX: Ne pas forcer min_vol ici, laisser le code appelant vérifier
        # Si vol < min_vol, le code appelant doit rejeter l'ordre
        # Seulement appliquer la limite max
        if vol > self.max_vol:
            vol = self.max_vol
        return vol
    
    def round_price(self, price: float) -> float:
        """Arrondir le prix selon les specs du contrat"""
        if self.price_unit > 0:
            price = round(price / self.price_unit) * self.price_unit
        return round(price, self.price_precision)


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
    "CHANGE_LEVERAGE": "/private/position/change_leverage",  # 🔥 Changer levier (position existante)
    "SET_LEVERAGE": "/private/account/change_leverage",  # 🔥 Changer levier par défaut (avant ouverture)
    
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
# 🔥 AMÉLIORATION 2: Cache Persistant des Specs Contrats
# ============================================================================

SPECS_CACHE_FILE = "data/contract_specs_cache.json"


def load_specs_cache() -> Dict[str, Dict]:
    """
    Charger le cache des specs contrats depuis fichier

    Returns:
        Dict des specs par symbole ou {} si cache invalide/expiré
    """
    from pathlib import Path

    if not Path(SPECS_CACHE_FILE).exists():
        return {}

    try:
        with open(SPECS_CACHE_FILE, 'r') as f:
            cache = json.load(f)

        # Vérifier age du cache (expire après 24h)
        cache_time = cache.get('timestamp', 0)
        if cache_time > time.time() - 86400:  # 24h
            logger.info(f"✅ Cache specs chargé: {len(cache.get('specs', {}))} contrats")
            return cache.get('specs', {})
        else:
            logger.warning(f"⚠️ Cache specs expiré ({(time.time() - cache_time) / 3600:.1f}h)")
            return {}

    except Exception as e:
        logger.error(f"❌ Erreur lecture cache specs: {e}")
        return {}


def save_specs_cache(specs: Dict[str, Dict]):
    """
    Sauvegarder le cache des specs contrats dans fichier

    Args:
        specs: Dict des specs par symbole
    """
    from pathlib import Path

    try:
        # Créer répertoire data/ si inexistant
        Path(SPECS_CACHE_FILE).parent.mkdir(parents=True, exist_ok=True)

        with open(SPECS_CACHE_FILE, 'w') as f:
            json.dump({
                'timestamp': time.time(),
                'specs': specs
            }, f, indent=2)

        logger.debug(f"💾 Cache specs sauvegardé: {len(specs)} contrats")

    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde cache specs: {e}")


# ============================================================================
# 🔥 AMÉLIORATION 3: Token Health Monitor
# ============================================================================

class TokenHealthMonitor:
    """
    Moniteur de santé du token browser

    Vérifie périodiquement la validité du token et envoie des alertes si expiré.
    Check toutes les 5 minutes (configurable).
    """

    def __init__(
        self,
        client: 'MexcFuturesBypass',
        check_interval: int = 300,  # 5 minutes
        telegram_notifier: Optional[Any] = None
    ):
        """
        Initialiser le moniteur

        Args:
            client: Instance du client MexcFuturesBypass
            check_interval: Intervalle de vérification en secondes (défaut 300s = 5min)
            telegram_notifier: Instance du TelegramNotifier pour alertes
        """
        self.client = client
        self.check_interval = check_interval
        self.telegram_notifier = telegram_notifier
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_check_time = 0
        self._consecutive_failures = 0
        self._token_healthy = True

    async def start(self):
        """Démarrer le monitoring"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"✅ Token Health Monitor démarré (check toutes les {self.check_interval}s)")

    async def stop(self):
        """Arrêter le monitoring"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Token Health Monitor arrêté")

    async def _monitor_loop(self):
        """Boucle de monitoring principale"""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)

                if self._running:
                    await self._check_token_health()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erreur monitoring token: {e}")

    async def _check_token_health(self):
        """Vérifier la santé du token"""
        try:
            self._last_check_time = time.time()

            # Tenter de récupérer l'asset USDT (requête simple)
            response = await self.client.get_account_asset("USDT")

            if response.get("code") == 403:
                # Token expiré ou IP bannie
                self._consecutive_failures += 1
                self._token_healthy = False

                error_msg = (
                    f"🔴 TOKEN MEXC EXPIRÉ\n\n"
                    f"Le token browser a expiré ou l'IP est bannie.\n"
                    f"Échecs consécutifs: {self._consecutive_failures}\n\n"
                    f"Actions requises:\n"
                    f"1. Ouvrir DevTools sur mexc.com\n"
                    f"2. Copier nouveau token (Headers > authorization)\n"
                    f"3. Mettre à jour MEXC_BROWSER_TOKEN\n"
                    f"4. Redémarrer le bot\n\n"
                    f"⚠️ Trading ARRÊTÉ jusqu'au renouvellement"
                )

                logger.error(f"❌ {error_msg}")

                # Envoyer notification Telegram si disponible
                if self.telegram_notifier and hasattr(self.telegram_notifier, 'send_message'):
                    try:
                        await self.telegram_notifier.send_message(
                            error_msg,
                            bypass_throttle=True
                        )
                    except Exception as e:
                        logger.error(f"Erreur envoi notification Telegram: {e}")

                # Désactiver le rate limiter (via callback)
                _rate_limiter.on_response_403()

            elif response.get("code") == 429:
                # Rate limit atteint
                logger.warning("⚠️ Rate limit atteint lors du check token")
                _rate_limiter.on_response_429()

            elif response.get("success") and response.get("code") == 0:
                # Token OK
                if not self._token_healthy:
                    logger.info("✅ Token restauré et fonctionnel")

                    if self.telegram_notifier and hasattr(self.telegram_notifier, 'send_message'):
                        try:
                            await self.telegram_notifier.send_message(
                                "✅ Token MEXC restauré\n\nLe trading peut reprendre.",
                                bypass_throttle=True
                            )
                        except:
                            pass

                self._token_healthy = True
                self._consecutive_failures = 0
                logger.debug("✅ Token valide (health check OK)")

            else:
                # Autre erreur
                logger.warning(f"⚠️ Health check token: réponse inattendue {response}")

        except Exception as e:
            logger.error(f"❌ Erreur check token health: {e}")
            self._consecutive_failures += 1

    def get_status(self) -> Dict:
        """Récupérer le statut du moniteur"""
        return {
            'running': self._running,
            'token_healthy': self._token_healthy,
            'consecutive_failures': self._consecutive_failures,
            'last_check_time': self._last_check_time,
            'next_check_in': max(0, self.check_interval - (time.time() - self._last_check_time))
        }


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
        debug: bool = False,
        enable_token_monitor: bool = True,
        token_check_interval: int = 300,  # 5 minutes
        telegram_notifier: Optional[Any] = None
    ):
        """
        Initialiser le client

        Args:
            browser_token: Token d'authentification browser (WEB_xxx...)
                          Récupérable depuis DevTools > Network > Headers > authorization
            timeout: Timeout des requêtes en secondes
            debug: Activer les logs de debug
            enable_token_monitor: 🔥 Activer le monitoring token (check périodique)
            token_check_interval: 🔥 Intervalle check token en secondes (défaut 300s = 5min)
            telegram_notifier: 🔥 Instance TelegramNotifier pour alertes
        """
        self.browser_token = browser_token
        self.timeout = timeout
        self.debug = debug
        self._session: Optional[aiohttp.ClientSession] = None
        
        # 🔥 TELEGRAM: Stocker le notifier pour les erreurs critiques
        self.telegram_notifier = telegram_notifier

        # 🔥 AMÉLIORATION 2: Cache persistant chargé depuis fichier
        cached_specs = load_specs_cache()
        self._contract_specs: Dict[str, ContractSpec] = {}

        # Convertir les dicts du cache en objets ContractSpec
        for symbol, spec_dict in cached_specs.items():
            try:
                self._contract_specs[symbol] = ContractSpec(**spec_dict)
            except Exception as e:
                logger.warning(f"⚠️ Spec cache invalide pour {symbol}: {e}")

        # 🔥 AMÉLIORATION 3: Token Health Monitor
        self._token_monitor: Optional[TokenHealthMonitor] = None
        if enable_token_monitor:
            self._token_monitor = TokenHealthMonitor(
                client=self,
                check_interval=token_check_interval,
                telegram_notifier=telegram_notifier
            )
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Obtenir ou créer la session HTTP"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session
    
    async def close(self):
        """Fermer la session HTTP et arrêter le monitoring"""
        # 🔥 Arrêter le token monitor si actif
        if self._token_monitor:
            await self._token_monitor.stop()

        # 🔥 Sauvegarder le cache des specs avant fermeture
        if self._contract_specs:
            specs_dict = {
                symbol: {
                    'symbol': spec.symbol,
                    'min_vol': spec.min_vol,
                    'max_vol': spec.max_vol,
                    'vol_unit': spec.vol_unit,
                    'price_unit': spec.price_unit,
                    'price_precision': spec.price_precision,
                    'vol_precision': spec.vol_precision
                }
                for symbol, spec in self._contract_specs.items()
            }
            save_specs_cache(specs_dict)

        # Fermer session HTTP
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
                    # 🔥 Vérifier le status HTTP et notifier le rate limiter
                    if resp.status == 429:
                        _rate_limiter.on_response_429()  # 🔥 Callback rate limiter
                        logger.warning("⚠️ Rate limit atteint (429) - attente 5s")
                        await asyncio.sleep(5)
                        return {"success": False, "code": 429, "message": "Rate limit exceeded"}
                    if resp.status == 403:
                        _rate_limiter.on_response_403()  # 🔥 Callback rate limiter
                        logger.error("❌ Accès refusé (403) - token expiré ou IP bannie?")
                        # 🔥 TELEGRAM: Notifier erreur 403
                        if self.telegram_notifier and hasattr(self.telegram_notifier, 'send_error_sync'):
                            self.telegram_notifier.send_error_sync(
                                "Token MEXC expiré (403)",
                                "Accès refusé - token browser expiré ou IP bannie"
                            )
                        return {"success": False, "code": 403, "message": "Access denied - check token"}
                    data = await resp.json()
            else:  # POST
                # 🔥 IMPORTANT: Utiliser le même format JSON que la signature (compact, sans espaces)
                body_str = json.dumps(body, separators=(',', ':')) if body else None
                post_headers = headers.copy()
                post_headers["content-type"] = "application/json"
                async with session.post(url, headers=post_headers, data=body_str) as resp:
                    if resp.status == 429:
                        _rate_limiter.on_response_429()  # 🔥 Callback rate limiter
                        logger.warning("⚠️ Rate limit atteint (429) - attente 5s")
                        await asyncio.sleep(5)
                        return {"success": False, "code": 429, "message": "Rate limit exceeded"}
                    if resp.status == 403:
                        _rate_limiter.on_response_403()  # 🔥 Callback rate limiter
                        logger.error("❌ Accès refusé (403) - token expiré ou IP bannie?")
                        # 🔥 TELEGRAM: Notifier erreur 403
                        if self.telegram_notifier and hasattr(self.telegram_notifier, 'send_error_sync'):
                            self.telegram_notifier.send_error_sync(
                                "Token MEXC expiré (403)",
                                "Accès refusé - token browser expiré ou IP bannie"
                            )
                        return {"success": False, "code": 403, "message": "Access denied - check token"}
                    data = await resp.json()

            # 🔥 Requête réussie → notifier le rate limiter
            if data.get("success") and data.get("code") == 0:
                _rate_limiter.on_response_success()

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
    
    async def set_leverage(
        self,
        symbol: str,
        leverage: int,
        open_type: Union[OpenType, int] = OpenType.ISOLATED,
        position_type: int = 1  # 1=long, 2=short
    ) -> bool:
        """
        🔥 Configurer le levier pour une paire AVANT d'ouvrir une position
        
        IMPORTANT: En mode marge isolée, le levier doit être configuré
        sur le compte pour chaque paire avant de passer un ordre.
        
        Args:
            symbol: Symbole (ex: "DOGE_USDT")
            leverage: Levier souhaité (1-125)
            open_type: Type de marge (1=isolated, 2=cross)
            position_type: Type de position (1=long, 2=short)
            
        Returns:
            True si succès, False sinon
        """
        leverage = min(125, max(1, leverage))
        
        # 🔥 Format MEXC: positionType + leverage + openType + symbol
        body = {
            "symbol": symbol,
            "positionType": position_type,  # 1=long, 2=short
            "leverage": leverage,
            "openType": int(open_type),
        }
        
        logger.info(f"⚙️ Configuration levier: {symbol} → {leverage}x (posType={position_type}, openType={open_type})")
        
        # Essayer d'abord l'endpoint account
        response = await self._request("POST", ENDPOINTS.get("SET_LEVERAGE", ENDPOINTS["CHANGE_LEVERAGE"]), body=body)
        
        if response.get("success") and response.get("code") == 0:
            logger.info(f"✅ Levier configuré: {symbol} = {leverage}x")
            return True
        
        # Si échec, essayer l'endpoint position
        if response.get("code") != 0:
            response = await self._request("POST", ENDPOINTS["CHANGE_LEVERAGE"], body=body)
            if response.get("success") and response.get("code") == 0:
                logger.info(f"✅ Levier configuré (fallback): {symbol} = {leverage}x")
                return True
        
        error_msg = response.get("message", "Unknown error")
        error_code = response.get("code", -1)
        logger.warning(f"⚠️ Échec configuration levier {symbol}: code={error_code}, msg={error_msg}")
        # Ne pas bloquer - le levier dans l'ordre pourrait quand même fonctionner
        return False
    
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
        
        # 🔥 DEBUG: Log critique pour diagnostiquer les ordres qui echouent
        logger.warning(
            f"🚀 SUBMIT ORDER CRITIQUE: {symbol} | side={side} | vol={vol} | price={price} | "
            f"leverage={leverage}x | valeur_usdt={vol * price:.2f} USDT"
        )
        logger.info(f"📋 Order body: {body}")
        
        response = await self._request("POST", ENDPOINTS["SUBMIT_ORDER"], body=body)
        logger.info(f"📋 Order response: {response}")
        
        if response.get("success") and response.get("code") == 0:
            order_id = response.get("data")
            logger.info(f"✅ Order submitted: ID={order_id}")
            return OrderResult(success=True, order_id=order_id, data=response)
        else:
            error_msg = response.get("message", "Unknown error")
            error_code = response.get("code", -1)
            logger.error(f"❌ Order failed: code={error_code}, message={error_msg}")
            
            # 🔥 TELEGRAM: Notifier erreurs critiques (401, 403, etc.)
            if self.telegram_notifier and hasattr(self.telegram_notifier, 'send_error_sync'):
                # Erreurs d'authentification critiques
                if error_code in [401, 403] or "login" in error_msg.lower() or "expired" in error_msg.lower():
                    self.telegram_notifier.send_error_sync(
                        f"Erreur MEXC ({error_code})",
                        f"{symbol} | {error_msg}"
                    )
            
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
    
    async def get_contract_spec(self, symbol: str) -> Optional[ContractSpec]:
        """
        Récupérer et cacher les spécifications d'un contrat
        
        Args:
            symbol: Symbole (ex: "BTC_USDT")
            
        Returns:
            ContractSpec ou None si erreur
        """
        # Vérifier le cache
        if symbol in self._contract_specs:
            return self._contract_specs[symbol]
        
        # Récupérer depuis l'API
        response = await self.get_contract_detail(symbol)
        
        if not response.get("success") or response.get("code") != 0:
            logger.warning(f"⚠️ Impossible de récupérer specs pour {symbol}")
            return None
        
        data = response.get("data", {})
        
        try:
            # Calculer la précision à partir des unités
            vol_unit = float(data.get("volUnit", 1))
            price_unit = float(data.get("priceUnit", 0.01))
            
            # Calculer le nombre de décimales
            vol_precision = len(str(vol_unit).split('.')[-1]) if '.' in str(vol_unit) else 0
            price_precision = len(str(price_unit).split('.')[-1]) if '.' in str(price_unit) else 0
            
            # 🔥 Récupérer contractSize (taille du contrat en tokens)
            contract_size = float(data.get("contractSize", 1))
            
            # 🔥 FIX: Corriger contractSize UNIQUEMENT pour symboles où MEXC API retourne 1.0 alors que c'est faux
            # NOTE: La plupart des symboles (SHIB, BTC, ETH, etc.) sont CORRECTS dans l'API
            # Ces overrides sont pour les cas où l'API ment (retourne 1.0 alors que c'est différent)
            CONTRACT_SIZE_OVERRIDES = {
                # Micro-contrats: API dit 1.0 mais c'est faux
                # 'SOL_USDT': 0.1,     # Désactivé: l'API retourne bien 0.1 maintenant (problème de cache)
                # Ajouter ici d'autres symboles si nécessaire après vérification manuelle
            }
            if symbol in CONTRACT_SIZE_OVERRIDES and contract_size == 1.0:
                correct_size = CONTRACT_SIZE_OVERRIDES[symbol]
                logger.warning(f"⚠️ Override contractSize pour {symbol}: {contract_size} → {correct_size}")
                contract_size = correct_size
            
            spec = ContractSpec(
                symbol=symbol,
                min_vol=float(data.get("minVol", 1)),
                max_vol=float(data.get("maxVol", 1000000)),
                vol_unit=vol_unit,
                price_unit=price_unit,
                price_precision=price_precision,
                vol_precision=vol_precision,
                contract_size=contract_size,
            )
            
            logger.info(f"📋 ContractSpec {symbol}: contractSize={contract_size}, minVol={spec.min_vol}")
            
            # Cacher en mémoire
            self._contract_specs[symbol] = spec

            # 🔥 AMÉLIORATION 2: Sauvegarder dans cache persistant (avec contract_size!)
            specs_dict = {
                s: {
                    'symbol': sp.symbol,
                    'min_vol': sp.min_vol,
                    'max_vol': sp.max_vol,
                    'vol_unit': sp.vol_unit,
                    'price_unit': sp.price_unit,
                    'price_precision': sp.price_precision,
                    'vol_precision': sp.vol_precision,
                    'contract_size': sp.contract_size,  # 🔥 CRITIQUE
                }
                for s, sp in self._contract_specs.items()
            }
            save_specs_cache(specs_dict)

            if self.debug:
                logger.debug(f"📋 ContractSpec {symbol}: minVol={spec.min_vol}, maxVol={spec.max_vol}, volUnit={spec.vol_unit}")

            return spec

        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"❌ Error parsing contract spec {symbol}: {e}")
            return None
    
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

    async def start_monitoring(self):
        """
        🔥 AMÉLIORATION 3: Démarrer le monitoring token

        À appeler après initialisation du client pour activer le check périodique du token.
        """
        if self._token_monitor:
            await self._token_monitor.start()
        else:
            logger.warning("⚠️ Token monitor non initialisé (enable_token_monitor=False)")

    def get_monitor_status(self) -> Optional[Dict]:
        """
        🔥 AMÉLIORATION 3: Récupérer le statut du token monitor

        Returns:
            Dict avec statut ou None si désactivé
        """
        if self._token_monitor:
            return self._token_monitor.get_status()
        return None

    def get_rate_limiter_stats(self) -> Dict:
        """
        🔥 AMÉLIORATION 1: Récupérer les stats du rate limiter

        Returns:
            Dict avec stats du rate limiter
        """
        return _rate_limiter.get_stats()

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
        pong_timeout: int = 60,  # 🔥 AMÉLIORATION 4: Timeout pong
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
            pong_timeout: 🔥 Timeout max sans pong (secondes) - déclenche reconnexion forcée
            debug: Mode debug
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout  # 🔥 AMÉLIORATION 4
        self.debug = debug

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._logged_in = False
        self._ping_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None  # 🔥 AMÉLIORATION 4

        # 🔥 AMÉLIORATION 4: Heartbeat monitoring
        self.last_pong_time = 0.0

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
            self.last_pong_time = time.time()  # 🔥 AMÉLIORATION 4: Init pong timestamp
            logger.info("✅ WebSocket connected")

            # Démarrer les tâches
            self._ping_task = asyncio.create_task(self._ping_loop())
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._watchdog_task = asyncio.create_task(self._watchdog_loop())  # 🔥 AMÉLIORATION 4

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
        if self._watchdog_task:  # 🔥 AMÉLIORATION 4
            self._watchdog_task.cancel()

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

    async def _watchdog_loop(self):
        """
        🔥 AMÉLIORATION 4: Watchdog pour détecter connexions zombies

        Surveille le temps écoulé depuis le dernier pong.
        Si pas de pong depuis pong_timeout secondes → reconnexion forcée.
        """
        while self._connected:
            try:
                await asyncio.sleep(10)  # Check toutes les 10s

                if not self._connected:
                    break

                # Vérifier si pas de pong depuis trop longtemps
                elapsed = time.time() - self.last_pong_time

                if elapsed > self.pong_timeout:
                    logger.error(
                        f"❌ WebSocket zombie détecté ! "
                        f"Pas de pong depuis {elapsed:.0f}s (max {self.pong_timeout}s) "
                        f"→ Reconnexion forcée"
                    )

                    # Forcer reconnexion
                    self._connected = False
                    self._logged_in = False

                    if self._on_disconnected:
                        await self._call_callback(
                            self._on_disconnected,
                            Exception(f"Watchdog timeout: {elapsed:.0f}s sans pong")
                        )

                    if self.auto_reconnect:
                        await self._reconnect()
                    break

                elif self.debug and elapsed > self.pong_timeout * 0.5:
                    # Warning si on dépasse 50% du timeout
                    logger.warning(
                        f"⚠️ Watchdog: {elapsed:.0f}s depuis dernier pong "
                        f"({elapsed / self.pong_timeout * 100:.0f}% du timeout)"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Watchdog error: {e}")

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

        # 🔥 AMÉLIORATION 4: Pong reçu → mettre à jour timestamp
        if channel == "pong":
            self.last_pong_time = time.time()
            if self.debug:
                logger.debug("💓 Pong reçu")
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

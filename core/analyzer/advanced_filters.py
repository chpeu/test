"""
Advanced Filters pour Trade Cursor
OPT #15: Anti-Whipsaw Filter
OPT #16: Retest Breakout Confirmation
OPT #18: Candle Close Confirmation
OPT #19: Momentum Continuity Filter
"""

import time
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from config import TRADING_CONFIG

logger = logging.getLogger(__name__)


# =============================================================================
# OPT #15: Anti-Whipsaw Filter
# =============================================================================

def check_whipsaw_filter(
    klines: List[List],
    symbol: str,
    lookback: int = None,
    threshold_pct: float = None,
    max_alternations: int = None
) -> Optional[Dict]:
    """
    🔥 OPT #15: Détecter les marchés en whipsaw (zigzag rapide)
    
    Un whipsaw est caractérisé par des mouvements alternés rapides:
    - Bougie 1: +0.3%
    - Bougie 2: -0.4%
    - Bougie 3: +0.2%
    - etc.
    
    Args:
        klines: Liste des bougies [timestamp, open, high, low, close, volume]
        symbol: Symbole pour logging
        lookback: Nombre de bougies à analyser (défaut: config)
        threshold_pct: Amplitude minimum pour compter (défaut: config)
        max_alternations: Nombre max d'alternances avant rejet (défaut: config)
    
    Returns:
        None si pas de whipsaw, Dict avec raison si whipsaw détecté
    """
    # Vérifier si filtre activé
    if not TRADING_CONFIG.get('use_anti_whipsaw', True):
        return None
    
    # Paramètres depuis config ou arguments
    lookback = lookback or TRADING_CONFIG.get('whipsaw_lookback', 5)
    threshold_pct = threshold_pct or TRADING_CONFIG.get('whipsaw_threshold_pct', 0.2)
    max_alternations = max_alternations or TRADING_CONFIG.get('whipsaw_max_alternations', 3)
    
    if not klines or len(klines) < lookback:
        return None
    
    # Analyser les N dernières bougies
    directions = []
    for i in range(-lookback, 0):
        try:
            open_price = float(klines[i][1])
            close_price = float(klines[i][4])
            
            if open_price <= 0:
                continue
                
            change_pct = (close_price - open_price) / open_price * 100
            
            # Ne compter que les mouvements significatifs
            if abs(change_pct) >= threshold_pct:
                directions.append(1 if change_pct > 0 else -1)
        except (IndexError, ValueError, TypeError):
            continue
    
    if len(directions) < 2:
        return None
    
    # Compter les alternances (changements de direction)
    alternations = sum(
        1 for i in range(len(directions) - 1)
        if directions[i] != directions[i + 1]
    )
    
    # Si trop d'alternances = whipsaw détecté
    if alternations >= max_alternations:
        reason = (
            f"Whipsaw détecté: {alternations} alternances sur {lookback} bougies "
            f"(seuil: {max_alternations}, amplitude min: {threshold_pct}%)"
        )
        logger.debug(f"⚡ {symbol}: {reason}")
        return {
            'rejected': True,
            'reason': reason,
            'reject_category': 'whipsaw_filter',
            'alternations': alternations,
            'lookback': lookback
        }
    
    return None


# =============================================================================
# OPT #16: Retest Breakout Confirmation
# =============================================================================

@dataclass
class PendingBreakout:
    """Représente un breakout en attente de confirmation par retest"""
    symbol: str
    level: float  # Niveau cassé (ex: EMA21)
    direction: str  # 'LONG' ou 'SHORT'
    breakout_price: float  # Prix au moment du breakout
    timestamp: float  # Timestamp du breakout
    confirmed: bool = False
    expired: bool = False


class RetestConfirmationManager:
    """
    🔥 OPT #16: Gérer la confirmation des breakouts par retest
    
    Workflow:
    1. Breakout détecté (prix casse EMA21 + ATR)
    2. Stocker le niveau cassé comme "pending"
    3. Attendre que le prix revienne tester ce niveau
    4. Si retest réussi → confirmer le trade
    5. Si timeout → abandonner
    """
    
    def __init__(self):
        self.pending_breakouts: Dict[str, PendingBreakout] = {}
    
    def detect_breakout(
        self,
        symbol: str,
        price: float,
        ema21: float,
        atr: float,
        direction: str
    ) -> Optional[str]:
        """
        Phase 1: Détecter un breakout initial
        
        Args:
            symbol: Symbole
            price: Prix actuel
            ema21: EMA 21
            atr: ATR
            direction: Direction du setup détecté
        
        Returns:
            'PENDING_LONG', 'PENDING_SHORT' si breakout détecté, None sinon
        """
        if not TRADING_CONFIG.get('use_retest_confirmation', False):
            return None
        
        breakout_threshold = atr * TRADING_CONFIG.get('breakout_threshold', 0.3)
        
        # Breakout haussier
        if direction == 'LONG' and price > ema21 + breakout_threshold:
            self.pending_breakouts[symbol] = PendingBreakout(
                symbol=symbol,
                level=ema21,  # Resistance devient support
                direction='LONG',
                breakout_price=price,
                timestamp=time.time()
            )
            logger.info(
                f"📈 Breakout LONG détecté pour {symbol}: "
                f"Prix {price:.6f} > EMA21 {ema21:.6f} + {breakout_threshold:.6f}"
            )
            return 'PENDING_LONG'
        
        # Breakout baissier
        if direction == 'SHORT' and price < ema21 - breakout_threshold:
            self.pending_breakouts[symbol] = PendingBreakout(
                symbol=symbol,
                level=ema21,  # Support devient resistance
                direction='SHORT',
                breakout_price=price,
                timestamp=time.time()
            )
            logger.info(
                f"📉 Breakout SHORT détecté pour {symbol}: "
                f"Prix {price:.6f} < EMA21 {ema21:.6f} - {breakout_threshold:.6f}"
            )
            return 'PENDING_SHORT'
        
        return None
    
    def check_retest_confirmation(
        self,
        symbol: str,
        price: float
    ) -> Optional[str]:
        """
        Phase 2: Vérifier si le prix a retesté le niveau cassé
        
        Args:
            symbol: Symbole
            price: Prix actuel
        
        Returns:
            'CONFIRMED_LONG', 'CONFIRMED_SHORT' si retest réussi,
            'PENDING' si encore en attente,
            None si pas de pending ou expiré
        """
        if symbol not in self.pending_breakouts:
            return None
        
        pending = self.pending_breakouts[symbol]
        
        # Vérifier timeout
        timeout = TRADING_CONFIG.get('retest_timeout_seconds', 300)
        if time.time() - pending.timestamp > timeout:
            logger.info(f"⏰ Timeout retest pour {symbol} après {timeout}s")
            del self.pending_breakouts[symbol]
            return None
        
        # Vérifier retest
        level = pending.level
        tolerance_pct = TRADING_CONFIG.get('retest_tolerance_pct', 0.1)
        distance_to_level = abs(price - level) / level * 100
        
        if distance_to_level <= tolerance_pct:
            # Prix a retesté le niveau
            if pending.direction == 'LONG' and price >= level:
                # Retest support réussi → CONFIRMER LONG
                logger.info(
                    f"✅ Retest LONG confirmé pour {symbol}: "
                    f"Prix {price:.6f} proche du niveau {level:.6f} (dist: {distance_to_level:.3f}%)"
                )
                del self.pending_breakouts[symbol]
                return 'CONFIRMED_LONG'
            
            elif pending.direction == 'SHORT' and price <= level:
                # Retest resistance réussi → CONFIRMER SHORT
                logger.info(
                    f"✅ Retest SHORT confirmé pour {symbol}: "
                    f"Prix {price:.6f} proche du niveau {level:.6f} (dist: {distance_to_level:.3f}%)"
                )
                del self.pending_breakouts[symbol]
                return 'CONFIRMED_SHORT'
        
        return 'PENDING'
    
    def has_pending(self, symbol: str) -> bool:
        """Vérifier si un breakout est en attente pour ce symbole"""
        return symbol in self.pending_breakouts
    
    def get_pending(self, symbol: str) -> Optional[PendingBreakout]:
        """Récupérer le breakout en attente pour ce symbole"""
        return self.pending_breakouts.get(symbol)
    
    def clear_pending(self, symbol: str):
        """Supprimer le breakout en attente pour ce symbole"""
        if symbol in self.pending_breakouts:
            del self.pending_breakouts[symbol]
    
    def cleanup_expired(self):
        """Nettoyer tous les breakouts expirés"""
        timeout = TRADING_CONFIG.get('retest_timeout_seconds', 300)
        now = time.time()
        
        expired = [
            symbol for symbol, pending in self.pending_breakouts.items()
            if now - pending.timestamp > timeout
        ]
        
        for symbol in expired:
            del self.pending_breakouts[symbol]
        
        if expired:
            logger.debug(f"🧹 Nettoyé {len(expired)} breakouts expirés")


# Instance globale du manager
_retest_manager = RetestConfirmationManager()


def get_retest_manager() -> RetestConfirmationManager:
    """Récupérer l'instance globale du manager de retest"""
    return _retest_manager


# =============================================================================
# OPT #18: Candle Close Confirmation
# =============================================================================

def is_candle_close_imminent(
    timeframe: str = '1m',
    threshold_seconds: int = None
) -> bool:
    """
    🔥 OPT #18: Vérifier si on est proche de la fermeture de bougie
    
    Args:
        timeframe: Timeframe de la bougie ('1m', '5m', '15m', '1h')
        threshold_seconds: Seuil en secondes (défaut: config)
    
    Returns:
        True si proche de la fermeture, False sinon
    """
    if not TRADING_CONFIG.get('use_candle_close', False):
        return True  # Désactivé = toujours OK
    
    threshold = threshold_seconds or TRADING_CONFIG.get('candle_close_threshold_seconds', 5)
    
    # Convertir timeframe en secondes
    interval_map = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600
    }
    
    interval_seconds = interval_map.get(timeframe, 60)
    
    now = time.time()
    seconds_until_close = interval_seconds - (now % interval_seconds)
    
    return seconds_until_close <= threshold


def check_candle_close_filter(
    symbol: str,
    timeframe: str = '1m'
) -> Optional[Dict]:
    """
    Vérifier si on peut entrer (proche de la fermeture de bougie)
    
    Returns:
        None si OK, Dict avec raison si doit attendre
    """
    if not TRADING_CONFIG.get('use_candle_close', False):
        return None
    
    if is_candle_close_imminent(timeframe):
        return None
    
    threshold = TRADING_CONFIG.get('candle_close_threshold_seconds', 5)
    interval_map = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600}
    interval_seconds = interval_map.get(timeframe, 60)
    
    now = time.time()
    seconds_until_close = interval_seconds - (now % interval_seconds)
    
    reason = (
        f"Attente fermeture bougie: {seconds_until_close:.0f}s restantes "
        f"(seuil: {threshold}s)"
    )
    
    return {
        'rejected': True,
        'reason': reason,
        'reject_category': 'candle_close_filter',
        'seconds_until_close': seconds_until_close
    }


# =============================================================================
# OPT #19: Momentum Continuity Filter
# =============================================================================

def check_momentum_continuity(
    klines: List[List],
    direction: str,
    symbol: str,
    lookback: int = None
) -> Optional[Dict]:
    """
    🔥 OPT #19: Vérifier que le momentum est croissant sur N bougies
    
    Pour un LONG:
    - RSI doit être croissant (ou stable)
    - Corps des bougies doivent être majoritairement haussiers
    
    Pour un SHORT:
    - RSI doit être décroissant (ou stable)
    - Corps des bougies doivent être majoritairement baissiers
    
    Args:
        klines: Liste des bougies
        direction: 'LONG' ou 'SHORT'
        symbol: Symbole pour logging
        lookback: Nombre de bougies à vérifier
    
    Returns:
        None si momentum OK, Dict avec raison si momentum contraire
    """
    if not TRADING_CONFIG.get('use_momentum_continuity', True):
        return None
    
    lookback = lookback or TRADING_CONFIG.get('momentum_lookback', 3)
    
    if not klines or len(klines) < lookback + 1:
        return None
    
    # Analyser les N dernières bougies (exclure la bougie en cours)
    bullish_count = 0
    bearish_count = 0
    
    for i in range(-lookback - 1, -1):
        try:
            open_price = float(klines[i][1])
            close_price = float(klines[i][4])
            
            if close_price > open_price:
                bullish_count += 1
            elif close_price < open_price:
                bearish_count += 1
            # Doji = neutre, ne compte pas
        except (IndexError, ValueError, TypeError):
            continue
    
    # Vérifier cohérence avec direction
    if direction == 'LONG':
        # Pour LONG, on veut majoritairement des bougies haussières
        if bearish_count > bullish_count:
            reason = (
                f"Momentum contraire pour LONG: {bearish_count} bougies baissières "
                f"vs {bullish_count} haussières sur {lookback} bougies"
            )
            logger.debug(f"📉 {symbol}: {reason}")
            return {
                'rejected': True,
                'reason': reason,
                'reject_category': 'momentum_filter',
                'bullish_count': bullish_count,
                'bearish_count': bearish_count
            }
    
    elif direction == 'SHORT':
        # Pour SHORT, on veut majoritairement des bougies baissières
        if bullish_count > bearish_count:
            reason = (
                f"Momentum contraire pour SHORT: {bullish_count} bougies haussières "
                f"vs {bearish_count} baissières sur {lookback} bougies"
            )
            logger.debug(f"📈 {symbol}: {reason}")
            return {
                'rejected': True,
                'reason': reason,
                'reject_category': 'momentum_filter',
                'bullish_count': bullish_count,
                'bearish_count': bearish_count
            }
    
    return None


# =============================================================================
# OPT #17: Cooldown Manager
# =============================================================================

@dataclass
class CooldownState:
    """État du cooldown"""
    last_trade_close_time: float = 0.0
    last_trade_symbol: str = ""
    last_trade_direction: str = ""


class CooldownManager:
    """
    🔥 OPT #17: Gérer le cooldown entre les trades
    """
    
    def __init__(self):
        self.state = CooldownState()
    
    def record_trade_close(self, symbol: str, direction: str):
        """Enregistrer la fermeture d'un trade"""
        self.state.last_trade_close_time = time.time()
        self.state.last_trade_symbol = symbol
        self.state.last_trade_direction = direction
        logger.debug(f"⏱️ Cooldown démarré pour {symbol} {direction}")
    
    def can_trade(self, symbol: str) -> tuple[bool, Optional[str]]:
        """
        Vérifier si on peut trader (cooldown respecté)
        
        Returns:
            (True, None) si OK
            (False, reason) si cooldown actif
        """
        if not TRADING_CONFIG.get('use_cooldown', True):
            return True, None
        
        if self.state.last_trade_close_time == 0:
            return True, None
        
        elapsed = time.time() - self.state.last_trade_close_time
        cooldown = TRADING_CONFIG.get('cooldown_seconds', 30)
        
        # Cooldown supplémentaire pour même symbole
        if symbol == self.state.last_trade_symbol:
            cooldown = TRADING_CONFIG.get('cooldown_same_symbol', 60)
        
        if elapsed < cooldown:
            remaining = cooldown - elapsed
            reason = f"Cooldown actif: {remaining:.0f}s restantes (dernier trade: {self.state.last_trade_symbol})"
            return False, reason
        
        return True, None
    
    def get_remaining_cooldown(self, symbol: str) -> float:
        """Retourner le temps restant de cooldown en secondes"""
        if not TRADING_CONFIG.get('use_cooldown', True):
            return 0.0
        
        if self.state.last_trade_close_time == 0:
            return 0.0
        
        elapsed = time.time() - self.state.last_trade_close_time
        cooldown = TRADING_CONFIG.get('cooldown_seconds', 30)
        
        if symbol == self.state.last_trade_symbol:
            cooldown = TRADING_CONFIG.get('cooldown_same_symbol', 60)
        
        remaining = cooldown - elapsed
        return max(0.0, remaining)


# Instance globale du cooldown manager
_cooldown_manager = CooldownManager()


def get_cooldown_manager() -> CooldownManager:
    """Récupérer l'instance globale du cooldown manager"""
    return _cooldown_manager

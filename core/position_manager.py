#!/usr/bin/env python3
"""
Position Manager - Trade Cursor v6.0
Gestion des positions: TP/SL, Break-even, Trailing Stop
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Représente une position active"""
    symbol: str
    direction: str  # 'LONG' ou 'SHORT'
    entry: float
    size: float
    sl: float
    tp: float
    atr: Optional[float] = None
    atr5m: Optional[float] = None
    confirmed_by: str = ""
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    # State flags
    break_even_set: bool = False
    partial_tp_sold: bool = False
    
    # Dynamic SL (for trailing)
    dynamic_sl: Optional[float] = None


@dataclass
class PositionConfig:
    """Configuration pour la gestion de position"""
    # Mode
    use_atr: bool = False
    
    # TP/SL FIXE
    fixed_tp_pct: float = 0.25
    fixed_sl_pct: float = 0.25
    
    # TP/SL ATR multipliers
    atr_mult_tp: float = 3.0
    atr_mult_sl: float = 1.5
    atr_min: float = 0.15
    atr_max: float = 1.5
    
    # Break-even & Trailing (FIXE mode)
    use_break_even: bool = True
    break_even_trigger: float = 0.3  # %
    use_trailing_stop: bool = True
    trailing_distance: float = 0.1  # %
    use_partial_tp: bool = True
    partial_tp_trigger: float = 0.25  # %
    
    # Break-even progressif (ATR mode)
    be_atr_factor: float = 1.5
    
    # Fees
    taker_fee: float = 0.0004  # 0.04%
    use_fee_calculation: bool = True
    
    # Win/Loss streaks
    win_streak: int = 0
    loss_streak: int = 0


class PositionManager:
    """Gestionnaire de positions"""
    
    def __init__(self, config: PositionConfig):
        self.config = config
        self.active_position: Optional[Position] = None
        self.price_cache: Dict[str, Dict] = {}
        self.api_alert_shown = False
        self.last_price = 0.0
        self.last_price_update = datetime.now().timestamp() * 1000
    
    def open_position(
        self, 
        symbol: str,
        direction: str,
        entry: float,
        size: float,
        atr: Optional[float] = None,
        atr5m: Optional[float] = None,
        confirmed_by: str = ""
    ) -> Position:
        """Ouvrir une nouvelle position"""
        
        # Calculer TP/SL selon le mode
        if self.config.use_atr and atr:
            sl, tp = self._calculate_atr_levels(entry, atr, atr5m, direction)
        else:
            sl, tp = self._calculate_fixed_levels(entry, direction)
        
        # Créer la position
        self.active_position = Position(
            symbol=symbol,
            direction=direction,
            entry=entry,
            size=size,
            sl=sl,
            tp=tp,
            atr=atr,
            atr5m=atr5m,
            confirmed_by=confirmed_by
        )
        
        logger.info(
            f"🟢 POSITION OUVERTE: {direction} {symbol} | "
            f"Entry: {entry} | SL: {sl} | TP: {tp}"
        )
        
        return self.active_position
    
    def _calculate_fixed_levels(self, entry: float, direction: str) -> tuple[float, float]:
        """Calculer TP/SL en mode FIXE"""
        if direction == 'LONG':
            sl = entry * (1 - self.config.fixed_sl_pct / 100)
            tp = entry * (1 + self.config.fixed_tp_pct / 100)
        else:
            sl = entry * (1 + self.config.fixed_sl_pct / 100)
            tp = entry * (1 - self.config.fixed_tp_pct / 100)
        
        return round(sl, 6), round(tp, 6)
    
    def _calculate_atr_levels(
        self, 
        entry: float, 
        atr: float, 
        atr5m: Optional[float], 
        direction: str
    ) -> tuple[float, float]:
        """Calculer TP/SL en mode ATR"""
        
        # ATR Multi-Timeframe (70% 1m + 30% 5m)
        if atr5m:
            atr_blended = (atr * 0.7) + (atr5m * 0.3)
        else:
            atr_blended = atr
        
        # ATR en pourcentage
        atr_percent = (atr_blended / entry) * 100
        
        # Clamp ATR
        if atr_percent < self.config.atr_min:
            atr_percent = self.config.atr_min
        elif atr_percent > self.config.atr_max:
            atr_percent = self.config.atr_max
        
        # Multipliers selon win/loss streaks
        tp_mult = self.config.atr_mult_tp
        sl_mult = self.config.atr_mult_sl
        
        if self.config.win_streak >= 3:
            tp_mult = 4.0
            sl_mult = 1.2
            logger.info(f"⚖️ Gestion dynamique: Wins={self.config.win_streak} | TPx={tp_mult} | SLx={sl_mult} (agressif)")
        elif self.config.loss_streak >= 2:
            tp_mult = 1.5
            sl_mult = 1.2
            logger.info(f"⚖️ Gestion dynamique: Losses={self.config.loss_streak} | TPx={tp_mult} | SLx={sl_mult} (prudent)")
        
        # Calculer TP/SL
        if direction == 'LONG':
            sl = entry * (1 - atr_percent / 100 * sl_mult)
            tp = entry * (1 + atr_percent / 100 * tp_mult)
        else:
            sl = entry * (1 + atr_percent / 100 * sl_mult)
            tp = entry * (1 - atr_percent / 100 * tp_mult)
        
        logger.info(
            f"📊 Mode ATR: ATR%={atr_percent:.3f}% | "
            f"SL={round(sl, 6)} | TP={round(tp, 6)}"
        )
        
        return round(sl, 6), round(tp, 6)
    
    async def check_position(self, current_price: float) -> Optional[str]:
        """
        Vérifier l'état de la position
        
        Returns:
            None si position continue
            'TP', 'SL', etc. si fermeture nécessaire
        """
        if not self.active_position:
            return None
        
        # Calculer P&L
        pnl = self._calculate_pnl(current_price)
        
        # Mettre à jour le SL dynamique selon le mode
        if not self.config.use_atr:
            self._update_fixed_mode_sl(current_price, pnl)
        else:
            self._update_atr_mode_sl(current_price, pnl)
        
        # Vérifier TP/SL
        reason = self._check_levels(current_price)
        
        if reason:
            logger.info(f"🚨 Clôture position: {reason}")
            return reason
        
        return None
    
    def _calculate_pnl(self, current_price: float) -> float:
        """Calculer le P&L non réalisé"""
        entry = self.active_position.entry
        pnl = ((current_price - entry) / entry) * 100
        
        if self.active_position.direction == 'SHORT':
            pnl = -pnl
        
        return pnl
    
    def _update_fixed_mode_sl(self, current_price: float, pnl: float):
        """Mettre à jour SL en mode FIXE"""
        # TP partiel
        if self.config.use_partial_tp and not self.active_position.partial_tp_sold:
            if pnl > self.config.partial_tp_trigger:
                self.active_position.partial_tp_sold = True
                logger.info(f"🎯 TP PARTIEL 50%: Profit={pnl:.2f}%")
        
        # Break-even
        if self.config.use_break_even and not self.active_position.break_even_set:
            if pnl > self.config.break_even_trigger and self.active_position.partial_tp_sold:
                self.active_position.sl = self.active_position.entry
                self.active_position.break_even_set = True
                logger.info(f"🔒 BREAK-EVEN: SL au prix d'entrée (profit={pnl:.2f}%)")
        
        # Trailing stop
        if self.config.use_trailing_stop and self.active_position.break_even_set:
            new_sl = None
            
            if self.active_position.direction == 'LONG':
                new_sl = current_price * (1 - self.config.trailing_distance / 100)
                if new_sl > self.active_position.sl:
                    self.active_position.sl = round(new_sl, 6)
                    logger.info(f"📈 TRAILING STOP: Nouveau SL={new_sl:.6f} (profit={pnl:.2f}%)")
            else:  # SHORT
                new_sl = current_price * (1 + self.config.trailing_distance / 100)
                if new_sl < self.active_position.sl:
                    self.active_position.sl = round(new_sl, 6)
                    logger.info(f"📉 TRAILING STOP: Nouveau SL={new_sl:.6f} (profit={pnl:.2f}%)")
    
    def _update_atr_mode_sl(self, current_price: float, pnl: float):
        """Mettre à jour SL en mode ATR (break-even progressif)"""
        if not self.active_position.atr:
            return
        
        entry = self.active_position.entry
        atr_percent = (self.active_position.atr / entry) * 100
        pnl_50pct = atr_percent * 0.5
        pnl_100pct = atr_percent * 1.0
        
        # Phase 1: Lock 50% du profit
        if pnl >= pnl_50pct and not self.active_position.break_even_set:
            if self.active_position.direction == 'LONG':
                new_sl = entry + (current_price - entry) * 0.5
            else:
                new_sl = entry - (entry - current_price) * 0.5
            
            self.active_position.sl = round(new_sl, 6)
            self.active_position.break_even_set = True
            logger.info(f"🛡️ BE Progressif 50%: PnL={pnl:.2f}% → SL={new_sl:.6f}")
        
        # Phase 2: BE total
        if pnl >= pnl_100pct and self.active_position.break_even_set:
            self.active_position.sl = entry
            logger.info(f"🛡️ BE Total 100%: PnL={pnl:.2f}% → SL={entry}")
    
    def _check_levels(self, current_price: float) -> Optional[str]:
        """Vérifier si TP ou SL est touché"""
        direction = self.active_position.direction
        sl = self.active_position.sl
        tp = self.active_position.tp
        
        if direction == 'LONG':
            if current_price <= sl:
                return 'SL'
            if current_price >= tp:
                return 'TP'
        else:  # SHORT
            if current_price >= sl:
                return 'SL'
            if current_price <= tp:
                return 'TP'
        
        return None
    
    def close_position(self, reason: str, exit_price: Optional[float] = None) -> Dict[str, Any]:
        """Fermer la position et calculer le résultat"""
        if not self.active_position:
            return {}
        
        entry = self.active_position.entry
        
        # Déterminer le prix de sortie
        if reason == 'TP':
            exit_price = self.active_position.tp
        elif reason == 'SL':
            exit_price = self.active_position.sl
        elif reason == 'API_STUCK':
            # Utiliser le dernier prix connu
            if self.active_position.symbol in self.price_cache:
                exit_price = self.price_cache[self.active_position.symbol]['price']
            else:
                exit_price = entry
        else:
            exit_price = entry
        
        # Calculer P&L brut
        pnl = ((exit_price - entry) / entry) * 100
        if self.active_position.direction == 'SHORT':
            pnl = -pnl
        
        # Calculer frais et P&L net
        fees = 0
        net_pnl = pnl
        
        if self.config.use_fee_calculation:
            fees = ((entry + exit_price) / entry) * self.config.taker_fee * 100
            net_pnl = pnl - fees
        
        # Durée
        duration = int(
            (datetime.now().timestamp() - self.active_position.timestamp) 
            / 1.0
        )
        
        result = {
            'symbol': self.active_position.symbol,
            'direction': self.active_position.direction,
            'entry': round(entry, 6),
            'exit': round(exit_price, 6),
            'pnl': round(pnl, 2),
            'fees': round(fees, 2),
            'net_pnl': round(net_pnl, 2),
            'duration': duration,
            'reason': reason,
            'timestamp': self.active_position.timestamp
        }
        
        # Mettre à jour les streaks
        if net_pnl > 0:
            self.config.win_streak += 1
            self.config.loss_streak = 0
        else:
            self.config.win_streak = 0
            self.config.loss_streak += 1
        
        # Réinitialiser
        self.active_position = None
        self.active_position.break_even_set = False
        self.active_position.partial_tp_sold = False
        
        logger.info(
            f"🔴 POSITION FERMÉE: {result['symbol']} | "
            f"Raison: {reason} | PnL net: {net_pnl:.2f}%"
        )
        
        return result
    
    def update_price_cache(self, symbol: str, price: float, data: Any = None):
        """Mettre à jour le cache de prix"""
        self.price_cache[symbol] = {
            'price': price,
            'timestamp': datetime.now().timestamp() * 1000,
            'data': data
        }
    
    def get_cached_price(self, symbol: str, max_age_ms: int = 20000) -> Optional[float]:
        """Récupérer le prix en cache s'il est frais"""
        if symbol not in self.price_cache:
            return None
        
        cache = self.price_cache[symbol]
        age = datetime.now().timestamp() * 1000 - cache['timestamp']
        
        if age <= max_age_ms:
            return cache['price']
        
        return None


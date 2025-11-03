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
    
    # Scalability data for slippage calculation
    scalability_data: Optional[Dict] = None
    
    # State flags
    break_even_set: bool = False
    partial_tp_sold: bool = False
    
    # Dynamic SL (for trailing)
    dynamic_sl: Optional[float] = None
    
    # 🔥 v6.4: Position partielle physique
    size_remaining: Optional[float] = None  # Taille restante après TP partiel
    partial_profit_usdt: float = 0.0  # Profit du TP partiel en USDT
    capital: Optional[float] = None  # Capital total en USDT
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir position en dictionnaire JSON"""
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'entry': self.entry,
            'size': self.size,
            'sl': self.sl,
            'tp': self.tp,
            'atr': self.atr,
            'atr5m': self.atr5m,
            'confirmed_by': self.confirmed_by,
            'timestamp': self.timestamp,
            'break_even_set': self.break_even_set,
            'partial_tp_sold': self.partial_tp_sold,
            'dynamic_sl': self.dynamic_sl,
            'size_remaining': self.size_remaining,
            'partial_profit_usdt': self.partial_profit_usdt,
            'capital': self.capital
        }


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
    trailing_distance: float = 0.15  # % 🔥 v6.4: 0.15% au lieu de 0.1%
    use_partial_tp: bool = True
    partial_tp_trigger: float = 0.3  # % 🔥 v6.4: 0.3% au lieu de 0.25%
    
    # Break-even progressif (ATR mode)
    be_atr_factor: float = 1.5
    
    # Fees
    taker_fee: float = 0.0  # 0% pour paires scalables
    use_fee_calculation: bool = True
    
    # Slippage estimation
    use_slippage_calculation: bool = True
    
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
        confirmed_by: str = "",
        scalability_data: Optional[Dict] = None
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
            confirmed_by=confirmed_by,
            scalability_data=scalability_data
        )
        
        logger.info(
            f"🟢 POSITION OUVERTE: {direction} {symbol} | "
            f"Entry: {entry} | SL: {sl} | TP: {tp}"
        )
        
        return self.active_position
    
    def _estimate_slippage(
        self,
        order_size: float,
        spread_pct: float,
        depth: float,
        balance_score: float,
        bid_vol: Optional[float] = None,
        ask_vol: Optional[float] = None
    ) -> float:
        """
        Estime le slippage réaliste pour un ordre
        
        Args:
            order_size: Taille de l'ordre en USDT
            spread_pct: Spread moyen en %
            depth: Profondeur totale du carnet
            balance_score: Équilibre bid/ask (0-1)
            bid_vol: Volume bid total (optionnel)
            ask_vol: Volume ask total (optionnel)
            
        Returns:
            Slippage estimé en %
        """
        if spread_pct <= 0 or depth <= 0:
            return 0.0
        
        # Imbalance factor
        imbalance_factor = 1 / balance_score if balance_score > 0 else 1.0
        
        # Depth factor
        if bid_vol and ask_vol:
            # Version précise avec bid_vol/ask_vol séparés
            depth_factor = order_size / (bid_vol + ask_vol)
        else:
            # Version simplifiée avec depth total
            depth_factor = order_size / depth if depth > 0 else 0
        
        # Slippage estimé
        slippage_pct = spread_pct * (1 + depth_factor * imbalance_factor)
        
        # Limiter à un maximum raisonnable (1% = plafond)
        slippage_pct = min(slippage_pct, 1.0)
        
        return round(slippage_pct, 4)
    
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
        """Mettre à jour SL en mode FIXE avec gestion de position partielle"""
        # 🔥 v6.4: TP partiel PHYSIQUE 50% à +0.3%
        if self.config.use_partial_tp and not self.active_position.partial_tp_sold:
            if pnl >= self.config.partial_tp_trigger:  # +0.3%
                self.active_position.partial_tp_sold = True
                
                # Calculer profit du TP partiel en USDT
                size_partial = self.active_position.size * 0.5
                price_diff = abs(current_price - self.active_position.entry)
                self.active_position.partial_profit_usdt = size_partial * (price_diff / self.active_position.entry)
                self.active_position.size_remaining = self.active_position.size * 0.5
                
                logger.info(
                    f"🎯 TP PARTIEL 50%: Profit={pnl:.2f}% | "
                    f"Profit USDT={self.active_position.partial_profit_usdt:.4f} | "
                    f"Restant={self.active_position.size_remaining:.2f}"
                )
                
                # Réduire le SL initial des 50% restants pour protection immédiate
                if self.active_position.direction == 'LONG':
                    self.active_position.sl = self.active_position.entry  # Break-even immédiat
                else:
                    self.active_position.sl = self.active_position.entry
        
        # 🔥 v6.4: Trailing stop à 0.15% à partir du TP partiel
        if self.config.use_trailing_stop and self.active_position.partial_tp_sold:
            new_sl = None
            
            if self.active_position.direction == 'LONG':
                new_sl = current_price * (1 - self.config.trailing_distance / 100)
                if new_sl > self.active_position.sl:
                    self.active_position.sl = round(new_sl, 6)
                    logger.info(f"📈 TRAILING STOP: Nouveau SL={new_sl:.6f} (distance={self.config.trailing_distance}%)")
            else:  # SHORT
                new_sl = current_price * (1 + self.config.trailing_distance / 100)
                if new_sl < self.active_position.sl:
                    self.active_position.sl = round(new_sl, 6)
                    logger.info(f"📉 TRAILING STOP: Nouveau SL={new_sl:.6f} (distance={self.config.trailing_distance}%)")
    
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
        """Fermer la position et calculer le résultat (avec support position partielle)"""
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
        
        # 🔥 v6.4: Gérer la position partielle
        has_partial_tp = self.active_position.partial_tp_sold
        size_to_close = self.active_position.size
        partial_profit_usdt = self.active_position.partial_profit_usdt
        
        if has_partial_tp:
            # On ferme les 50% restants
            size_to_close = self.active_position.size_remaining or (self.active_position.size * 0.5)
        
        # Calculer P&L brut pour la partie fermée
        pnl_pct = ((exit_price - entry) / entry) * 100
        if self.active_position.direction == 'SHORT':
            pnl_pct = -pnl_pct
        
        # 🔥 v6.4: Calculer P&L en USDT
        if has_partial_tp:
            # P&L final = TP partiel + fermeture finale
            pnl_final_usdt = partial_profit_usdt + (size_to_close * pnl_pct / 100)
            pnl_total_pct = (pnl_final_usdt / self.active_position.size) * 100
        else:
            # Position fermée en entier
            pnl_final_usdt = self.active_position.size * (pnl_pct / 100)
            pnl_total_pct = pnl_pct
            pnl_final_usdt = pnl_final_usdt * (exit_price / entry)  # Ajustement exact
        
        # 🔥 v6.4: Calculer frais et slippage (doublé si TP partiel)
        fees = 0
        slippage = 0
        total_costs = 0
        
        if self.config.use_fee_calculation:
            fees = 0  # 0% pour paires scalables
            
            # Slippage dynamique
            if self.config.use_slippage_calculation and self.active_position.scalability_data:
                scal_data = self.active_position.scalability_data
                spread = scal_data.get('spread', 0)
                depth = scal_data.get('bookDepth', 0)
                balance = scal_data.get('balanceScore', 1.0)
                bid_vol = scal_data.get('bidVol')
                ask_vol = scal_data.get('askVol')
                
                if spread > 0 and depth > 0:
                    # 🔥 v6.4: Slippage doublé si position partielle (entrée + sortie partielle + sortie finale)
                    if has_partial_tp:
                        # 2 entrées/sorties au lieu de 1
                        slippage_partial = self._estimate_slippage(
                            self.active_position.size * 0.5, spread, depth, balance, bid_vol, ask_vol
                        )
                        slippage_final = self._estimate_slippage(
                            size_to_close, spread, depth, balance, bid_vol, ask_vol
                        )
                        slippage = slippage_partial + slippage_final
                    else:
                        # Slippage normal (entrée + sortie)
                        order_size = self.active_position.size
                        slippage_entry = self._estimate_slippage(
                            order_size, spread, depth, balance, bid_vol, ask_vol
                        )
                        slippage_exit = self._estimate_slippage(
                            order_size, spread, depth, balance, bid_vol, ask_vol
                        )
                        slippage = slippage_entry + slippage_exit
            else:
                slippage = 0.05  # Fallback
            
            total_costs = fees + slippage
        
        # 🔥 v6.4: Net P&L en % et USDT
        net_pnl_pct = pnl_total_pct - total_costs
        net_pnl_usdt = pnl_final_usdt - (total_costs / 100 * self.active_position.size)
        
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
            'pnl': round(pnl_total_pct, 2),
            'pnl_usdt': round(pnl_final_usdt, 4),  # 🔥 v6.4
            'fees': round(fees, 2),
            'slippage': round(slippage, 2),
            'total_costs': round(total_costs, 2),
            'net_pnl': round(net_pnl_pct, 2),
            'net_pnl_usdt': round(net_pnl_usdt, 4),  # 🔥 v6.4
            'duration': duration,
            'reason': reason,
            'timestamp': self.active_position.timestamp,
            'has_partial_tp': has_partial_tp,  # 🔥 v6.4
            'size_closed': round(size_to_close, 4)  # 🔥 v6.4
        }
        
        # Mettre à jour les streaks
        if net_pnl_pct > 0:
            self.config.win_streak += 1
            self.config.loss_streak = 0
        else:
            self.config.win_streak = 0
            self.config.loss_streak += 1
        
        # Réinitialiser
        self.active_position = None
        
        logger.info(
            f"🔴 POSITION FERMÉE: {result['symbol']} | "
            f"Raison: {reason} | PnL net: {net_pnl_pct:.2f}% ({net_pnl_usdt:.4f} USDT)"
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


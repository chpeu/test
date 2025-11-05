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
    fixed_tp_pct: float = 0.6  # 🔥 FIX: Aligné avec config.py (TP final pour les 50% restants après TP partiel)
    fixed_sl_pct: float = 0.25
    
    # TP/SL ATR multipliers
    atr_mult_tp: float = 1.5  # 🔥 FIX: Aligné avec config.py
    atr_mult_sl: float = 1.0  # 🔥 FIX: Aligné avec config.py
    atr_min: float = 0.15
    atr_max: float = 1.5
    
    # Break-even & Trailing (FIXE mode)
    use_break_even: bool = True
    break_even_trigger: float = 0.3  # %
    use_trailing_stop: bool = True
    trailing_distance: float = 0.15  # % 🔥 v6.4: 0.15% au lieu de 0.1%
    use_partial_tp: bool = True
    partial_tp_trigger: float = 0.3  # % TP partiel 50% à +0.3% (doit être < TP final 0.6%)
    
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
        
        # 🔥 FIX: Vérifier que entry est valide
        if not entry or entry <= 0:
            raise ValueError(f"Entry invalide: {entry}")
        
        # 🔥 FIX: Vérifier que les pourcentages sont valides
        if self.config.fixed_sl_pct <= 0 or self.config.fixed_tp_pct <= 0:
            raise ValueError(
                f"Config invalide: fixed_sl_pct={self.config.fixed_sl_pct}%, "
                f"fixed_tp_pct={self.config.fixed_tp_pct}%"
            )
        
        # Calculer TP/SL selon le mode
        # 🔥 FIX: Vérifier que ATR est valide (> 0) avant d'utiliser le mode ATR
        if self.config.use_atr and atr and atr > 0:
            sl, tp = self._calculate_atr_levels(entry, atr, atr5m, direction)
        else:
            sl, tp = self._calculate_fixed_levels(entry, direction)
        
        # 🔥 FIX: Vérifier que SL et TP sont différents de l'entry (tolérance relative pour petits prix)
        # Utiliser une tolérance relative au lieu d'absolue pour les très petits prix
        # Pour les très petits prix, utiliser une tolérance plus stricte
        if entry < 0.001:
            tolerance = max(entry * 0.0001, 0.00000001)  # 0.01% de entry ou 0.00000001 minimum
        else:
            tolerance = max(entry * 0.0001, 0.0000001)  # 0.01% de entry ou 0.0000001 minimum
        
        # Vérifier les différences
        sl_diff = abs(sl - entry)
        tp_diff = abs(tp - entry)
        
        if sl_diff < tolerance or tp_diff < tolerance:
            logger.warning(
                f"⚠️ SL ou TP trop proche de entry: entry={entry:.10f}, sl={sl:.10f}, tp={tp:.10f}. "
                f"sl_diff={sl_diff:.10f}, tp_diff={tp_diff:.10f}, tolerance={tolerance:.10f}. "
                f"Mode FIXE utilisé avec config: fixed_sl_pct={self.config.fixed_sl_pct}%, "
                f"fixed_tp_pct={self.config.fixed_tp_pct}%"
            )
            sl, tp = self._calculate_fixed_levels(entry, direction)
            
            # Vérifier à nouveau après recalcul en utilisant les valeurs retournées
            sl_new, tp_new = sl, tp  # Utiliser les nouvelles valeurs calculées
            sl_diff_new = abs(sl_new - entry)
            tp_diff_new = abs(tp_new - entry)
            
            if sl_diff_new < tolerance or tp_diff_new < tolerance:
                logger.error(
                    f"❌ ERREUR CRITIQUE: SL ou TP toujours identique après recalcul FIXE! "
                    f"entry={entry:.10f}, sl={sl_new:.10f}, tp={tp_new:.10f}, "
                    f"sl_diff={sl_diff_new:.10f}, tp_diff={tp_diff_new:.10f}, tolerance={tolerance:.10f}, "
                    f"fixed_sl_pct={self.config.fixed_sl_pct}, fixed_tp_pct={self.config.fixed_tp_pct}"
                )
                # Forcer des valeurs minimales avec garantie de différence
                # Utiliser un pourcentage plus élevé pour garantir la différence après arrondi
                min_diff_pct = max(0.1, self.config.fixed_sl_pct * 1.5)  # Au moins 0.1% ou 50% de plus que config
                if direction == 'LONG':
                    sl = entry * (1 - min_diff_pct / 100)  # -0.1% minimum
                    tp = entry * (1 + min_diff_pct / 100)  # +0.1% minimum
                else:
                    sl = entry * (1 + min_diff_pct / 100)  # +0.1% minimum
                    tp = entry * (1 - min_diff_pct / 100)  # -0.1% minimum
                
                # Arrondir avec la bonne précision
                if entry < 0.001:
                    precision = 10
                elif entry < 0.01:
                    precision = 9
                else:
                    precision = 8
                sl = round(sl, precision)
                tp = round(tp, precision)
                
                logger.warning(f"🔧 Valeurs forcées avec min_diff={min_diff_pct}%: sl={sl:.10f}, tp={tp:.10f}")
                
                # Vérifier une dernière fois que c'est différent après arrondi
                final_sl_diff = abs(sl - entry)
                final_tp_diff = abs(tp - entry)
                if final_sl_diff < tolerance or final_tp_diff < tolerance:
                    raise ValueError(
                        f"❌ IMPOSSIBLE DE CRÉER POSITION: SL/TP ne peuvent pas être différents de entry même après correction. "
                        f"entry={entry:.10f}, sl={sl:.10f}, tp={tp:.10f}, "
                        f"sl_diff={final_sl_diff:.10f}, tp_diff={final_tp_diff:.10f}, tolerance={tolerance:.10f}"
                    )
        
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
        # 🔥 FIX: Vérifier que entry est valide
        if not entry or entry <= 0:
            raise ValueError(f"Entry invalide dans _calculate_fixed_levels: {entry}")
        
        # 🔥 FIX: Vérifier que les pourcentages sont valides
        if self.config.fixed_sl_pct <= 0 or self.config.fixed_tp_pct <= 0:
            raise ValueError(
                f"Config invalide dans _calculate_fixed_levels: "
                f"fixed_sl_pct={self.config.fixed_sl_pct}%, fixed_tp_pct={self.config.fixed_tp_pct}%"
            )
        
        if direction == 'LONG':
            sl = entry * (1 - self.config.fixed_sl_pct / 100)
            tp = entry * (1 + self.config.fixed_tp_pct / 100)
        else:
            sl = entry * (1 + self.config.fixed_sl_pct / 100)
            tp = entry * (1 - self.config.fixed_tp_pct / 100)
        
        # 🔥 FIX: Vérifier que les valeurs calculées sont différentes de entry
        # Utiliser une tolérance relative pour les très petits prix
        tolerance = max(entry * 0.0001, 0.00000001)  # 0.01% de entry ou 0.00000001 minimum
        
        # Vérifier AVANT arrondi pour éviter les problèmes de précision
        sl_diff = abs(sl - entry)
        tp_diff = abs(tp - entry)
        
        if sl_diff < tolerance or tp_diff < tolerance:
            logger.error(
                f"❌ Calcul FIXE invalide (avant arrondi): entry={entry:.10f}, sl={sl:.10f}, tp={tp:.10f}, "
                f"sl_diff={sl_diff:.10f}, tp_diff={tp_diff:.10f}, tolerance={tolerance:.10f}, "
                f"fixed_sl_pct={self.config.fixed_sl_pct}%, fixed_tp_pct={self.config.fixed_tp_pct}%"
            )
            raise ValueError(f"SL ou TP trop proche de entry après calcul FIXE (diff={sl_diff:.10f}/{tp_diff:.10f} < tolerance={tolerance:.10f})")
        
        # Arrondir avec plus de précision selon la taille du prix
        # Pour les très petits prix (< 0.001), utiliser plus de décimales
        if entry < 0.001:
            precision = 10  # 10 décimales pour prix < 0.001
        elif entry < 0.01:
            precision = 9   # 9 décimales pour prix < 0.01
        else:
            precision = 8   # 8 décimales pour prix >= 0.01
        
        sl_rounded = round(sl, precision)
        tp_rounded = round(tp, precision)
        
        # Vérifier APRÈS arrondi aussi
        sl_rounded_diff = abs(sl_rounded - entry)
        tp_rounded_diff = abs(tp_rounded - entry)
        
        if sl_rounded_diff < tolerance or tp_rounded_diff < tolerance:
            logger.error(
                f"❌ Calcul FIXE invalide (après arrondi): entry={entry:.10f}, sl_rounded={sl_rounded:.10f}, tp_rounded={tp_rounded:.10f}, "
                f"sl_diff={sl_rounded_diff:.10f}, tp_diff={tp_rounded_diff:.10f}, tolerance={tolerance:.10f}, precision={precision}"
            )
            # Forcer une différence minimale en augmentant légèrement les pourcentages
            # Pour les très petits prix, utiliser un pourcentage plus élevé pour garantir la différence après arrondi
            if entry < 0.001:
                # Pour prix < 0.001, utiliser au moins 0.15% pour garantir la différence
                min_diff_pct = max(0.15, self.config.fixed_sl_pct * 1.2)
            else:
                min_diff_pct = max(0.1, self.config.fixed_sl_pct * 1.1)  # Au moins 0.1% ou 10% de plus que config
            
            if direction == 'LONG':
                sl_rounded = entry * (1 - min_diff_pct / 100)
                tp_rounded = entry * (1 + min_diff_pct / 100)
            else:
                sl_rounded = entry * (1 + min_diff_pct / 100)
                tp_rounded = entry * (1 - min_diff_pct / 100)
            
            # Réarrondir avec la bonne précision
            sl_rounded = round(sl_rounded, precision)
            tp_rounded = round(tp_rounded, precision)
            
            # Vérifier une dernière fois
            final_sl_diff = abs(sl_rounded - entry)
            final_tp_diff = abs(tp_rounded - entry)
            if final_sl_diff < tolerance or final_tp_diff < tolerance:
                # Si toujours trop proche, utiliser une différence encore plus grande
                min_diff_pct = 0.2  # Forcer 0.2% minimum
                if direction == 'LONG':
                    sl_rounded = round(entry * (1 - min_diff_pct / 100), precision)
                    tp_rounded = round(entry * (1 + min_diff_pct / 100), precision)
                else:
                    sl_rounded = round(entry * (1 + min_diff_pct / 100), precision)
                    tp_rounded = round(entry * (1 - min_diff_pct / 100), precision)
                logger.warning(f"🔧 Valeurs forcées avec min_diff={min_diff_pct}% (force): sl={sl_rounded:.10f}, tp={tp_rounded:.10f}")
            else:
                logger.warning(f"🔧 Valeurs recalculées avec min_diff={min_diff_pct}%: sl={sl_rounded:.10f}, tp={tp_rounded:.10f}")
        
        return sl_rounded, tp_rounded
    
    def _calculate_atr_levels(
        self, 
        entry: float, 
        atr: float, 
        atr5m: Optional[float], 
        direction: str
    ) -> tuple[float, float]:
        """Calculer TP/SL en mode ATR"""
        
        # 🔥 FIX: Vérifier que ATR est valide (> 0)
        if not atr or atr <= 0:
            logger.warning(f"⚠️ ATR invalide ({atr}), utilisation du mode FIXE comme fallback")
            return self._calculate_fixed_levels(entry, direction)
        
        # ATR Multi-Timeframe (70% 1m + 30% 5m)
        if atr5m and atr5m > 0:
            atr_blended = (atr * 0.7) + (atr5m * 0.3)
        else:
            atr_blended = atr
        
        # ATR en pourcentage
        if entry <= 0:
            logger.warning(f"⚠️ Entry invalide ({entry}), utilisation du mode FIXE comme fallback")
            return self._calculate_fixed_levels(entry, direction)
        
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
        
        # 🔥 FIX: Vérifier que le prix est valide
        if not current_price or current_price <= 0:
            logger.warning(f"⚠️ Prix invalide dans check_position: {current_price}")
            return None
        
        # Calculer P&L
        pnl = self._calculate_pnl(current_price)
        
        # 🔥 FIX: Log détaillé pour debug (incluant TP partiel)
        partial_tp_status = "TP partiel: OUI" if self.active_position.partial_tp_sold else "TP partiel: NON"
        logger.debug(
            f"🔍 Check position: {self.active_position.symbol} {self.active_position.direction} | "
            f"Entry={self.active_position.entry:.6f} | Prix={current_price:.6f} | "
            f"PnL={pnl:.2f}% | {partial_tp_status} | SL={self.active_position.sl:.6f} | TP={self.active_position.tp:.6f}"
        )
        
        # Mettre à jour le SL dynamique selon le mode (AVANT de vérifier TP/SL)
        # Cela permet au TP partiel de se déclencher avant le TP final
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
    
    def _calculate_pnl_usdt(self, current_price: float) -> float:
        """Calculer le P&L USDT non réalisé (incluant TP partiel si applicable)"""
        pnl_pct = self._calculate_pnl(current_price)
        pnl_pct_decimal = pnl_pct / 100
        entry = self.active_position.entry
        
        # Taille de position à considérer (50% si TP partiel vendu)
        size_to_consider = self.active_position.size
        if self.active_position.partial_tp_sold:
            size_to_consider = self.active_position.size_remaining or (self.active_position.size * 0.5)
        
        # 🔥 FIX: Calculer PnL USDT correctement
        # PnL USDT = size * (prix_diff / entry) où prix_diff = current_price - entry (LONG) ou entry - current_price (SHORT)
        if self.active_position.direction == 'LONG':
            # LONG: profit quand prix monte
            price_diff = current_price - entry
            pnl_usdt = size_to_consider * (price_diff / entry)
        else:  # SHORT
            # SHORT: profit quand prix baisse
            price_diff = entry - current_price
            pnl_usdt = size_to_consider * (price_diff / entry)
        
        # Ajouter le profit du TP partiel si vendu
        if self.active_position.partial_tp_sold:
            pnl_usdt += self.active_position.partial_profit_usdt
        
        return pnl_usdt
    
    def _update_fixed_mode_sl(self, current_price: float, pnl: float):
        """Mettre à jour SL en mode FIXE avec gestion de position partielle"""
        # 🔥 v6.4: TP partiel PHYSIQUE 50% à +0.3%
        if self.config.use_partial_tp and not self.active_position.partial_tp_sold:
            if pnl >= self.config.partial_tp_trigger:  # +0.3%
                self.active_position.partial_tp_sold = True
                
                # Calculer profit du TP partiel en USDT
                size_partial = self.active_position.size * 0.5
                entry = self.active_position.entry
                
                # 🔥 FIX: Calcul correct du profit selon direction
                if self.active_position.direction == 'LONG':
                    # LONG: profit quand prix monte
                    price_diff = current_price - entry
                    self.active_position.partial_profit_usdt = size_partial * (price_diff / entry)
                else:  # SHORT
                    # SHORT: profit quand prix baisse
                    price_diff = entry - current_price
                    self.active_position.partial_profit_usdt = size_partial * (price_diff / entry)
                
                self.active_position.size_remaining = self.active_position.size * 0.5
                
                logger.info(
                    f"🎯 TP PARTIEL 50%: Profit={pnl:.2f}% | "
                    f"Profit USDT={self.active_position.partial_profit_usdt:.4f} | "
                    f"Restant={self.active_position.size_remaining:.2f}"
                )
                
                # Réduire le SL initial des 50% restants pour protection immédiate
                self.active_position.sl = self.active_position.entry  # Break-even immédiat pour LONG et SHORT
        
        # 🔥 v6.4: Trailing stop à 0.15% à partir du TP partiel
        if self.config.use_trailing_stop and self.active_position.partial_tp_sold:
            new_sl = None
            entry = self.active_position.entry
            
            if self.active_position.direction == 'LONG':
                # LONG: trailing stop vers le haut quand prix monte
                new_sl = current_price * (1 - self.config.trailing_distance / 100)
                # Le SL doit monter (augmenter) pour protéger les gains
                if new_sl > self.active_position.sl:
                    self.active_position.sl = round(new_sl, 6)
                    logger.info(f"📈 TRAILING STOP: Nouveau SL={new_sl:.6f} (distance={self.config.trailing_distance}%)")
            else:  # SHORT
                # SHORT: trailing stop qui descend avec le prix quand prix baisse (profit augmente)
                # Pour SHORT, SL doit être au-dessus du prix actuel pour protéger les gains
                new_sl = current_price * (1 + self.config.trailing_distance / 100)
                
                # 🔥 FIX: Pour SHORT, après TP partiel, SL = entry (0.5184)
                # Quand prix baisse (ex: 0.516), new_sl = 0.516 * 1.0015 = 0.516774
                # On veut que le SL descende (new_sl < entry) mais reste au-dessus du prix actuel
                # Condition: new_sl doit être < entry (pour descendre) ET > current_price (pour protéger)
                # Mais aussi: on ne veut pas que SL remonte, donc new_sl doit être < SL actuel
                if new_sl < self.active_position.sl and new_sl > current_price:
                    self.active_position.sl = round(new_sl, 6)
                    logger.info(f"📉 TRAILING STOP: Nouveau SL={new_sl:.6f} (distance={self.config.trailing_distance}%) | Prix={current_price:.6f} | Entry={entry:.6f}")
    
    def _update_atr_mode_sl(self, current_price: float, pnl: float):
        """Mettre à jour SL en mode ATR (break-even progressif ou ATR MULTI avec TP partiel)"""
        if not self.active_position.atr:
            return
        
        entry = self.active_position.entry
        
        # 🔥 ATR MULTI: TP partiel physique 50% à 1× ATR + Trailing 0.5× ATR
        if self.active_position.atr5m and self.config.use_partial_tp:
            # Calculer ATR blended (70% 1m + 30% 5m)
            atr_blended = (self.active_position.atr * 0.7) + (self.active_position.atr5m * 0.3)
            atr_percent = (atr_blended / entry) * 100
            
            # 🔥 FIX: Vérifier que le TP final (calculé dans _calculate_atr_levels) est >= TP partiel
            # TP partiel = 1× ATR, TP final devrait être >= 1.5× ATR (par défaut)
            # Mais si les streaks dynamiques réduisent tp_mult, on doit s'assurer que TP final >= TP partiel
            tp_mult = self.config.atr_mult_tp
            if self.config.win_streak >= 3:
                tp_mult = 4.0
            elif self.config.loss_streak >= 2:
                tp_mult = 1.5
            
            # 🔥 FIX: Si tp_mult < 1.0, le TP final serait < TP partiel → problème !
            # On force un minimum de 1.5× pour le TP final en mode ATR MULTI
            if tp_mult < 1.5:
                logger.warning(
                    f"⚠️ TP multiplier ({tp_mult}) trop faible pour ATR MULTI avec TP partiel. "
                    f"Force minimum 1.5× pour garantir TP final >= TP partiel"
                )
                tp_mult = 1.5
            
            tp_partial_threshold = atr_percent * 1.0  # 1× ATR (TP partiel)
            tp_final_threshold = atr_percent * tp_mult  # TP final (doit être >= 1.5× ATR)
            trailing_distance_atr = atr_percent * 0.5  # 0.5× ATR
            
            # TP PARTIEL PHYSIQUE à 1× ATR
            if not self.active_position.partial_tp_sold and pnl >= tp_partial_threshold:
                self.active_position.partial_tp_sold = True
                
                size_partial = self.active_position.size * 0.5
                entry = self.active_position.entry
                
                # 🔥 FIX: Calcul correct du profit selon direction (comme pour FIXE mode)
                if self.active_position.direction == 'LONG':
                    # LONG: profit quand prix monte
                    price_diff = current_price - entry
                    self.active_position.partial_profit_usdt = size_partial * (price_diff / entry)
                else:  # SHORT
                    # SHORT: profit quand prix baisse
                    price_diff = entry - current_price
                    self.active_position.partial_profit_usdt = size_partial * (price_diff / entry)
                
                self.active_position.size_remaining = size_partial
                
                logger.info(
                    f"🎯 TP PARTIEL ATR 50%: Profit={pnl:.2f}% | "
                    f"Profit USDT={self.active_position.partial_profit_usdt:.4f} | "
                    f"Restant={self.active_position.size_remaining:.2f}"
                )
                
                # SL → Entry (break-even immédiat)
                self.active_position.sl = entry
            
            # TRAILING STOP ADAPTATIF (seulement après TP partiel)
            if self.active_position.partial_tp_sold and self.config.use_trailing_stop:
                new_sl = None
                if self.active_position.direction == 'LONG':
                    new_sl = current_price * (1 - trailing_distance_atr / 100)
                    if new_sl > self.active_position.sl:
                        self.active_position.sl = round(new_sl, 6)
                        logger.info(f"📈 TRAILING ATR: Nouveau SL={new_sl:.6f} (distance {trailing_distance_atr:.3f}%)")
                else:  # SHORT
                    # 🔥 FIX: SHORT trailing stop - après TP partiel, SL = entry
                    # Quand prix baisse (profit augmente), new_sl doit descendre avec le prix
                    new_sl = current_price * (1 + trailing_distance_atr / 100)
                    # Pour SHORT, SL doit être au-dessus du prix actuel mais descendre avec le prix
                    # Condition: new_sl doit être < SL actuel (pour descendre) ET > current_price (pour protéger)
                    if new_sl < self.active_position.sl and new_sl > current_price:
                        self.active_position.sl = round(new_sl, 6)
                        logger.info(f"📉 TRAILING ATR: Nouveau SL={new_sl:.6f} (distance {trailing_distance_atr:.3f}%) | Prix={current_price:.6f} | Entry={entry:.6f}")
            
            return  # ATR MULTI avec TP partiel géré, pas besoin de break-even progressif
        
        # 🔥 ATR SIMPLE: Break-even progressif (pas de TP partiel)
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
        
        # 🔥 FIX: Log détaillé pour debug
        logger.debug(
            f"🔍 Vérification TP/SL: {direction} | "
            f"Prix={current_price:.6f} | SL={sl:.6f} | TP={tp:.6f}"
        )
        
        # 🔥 FIX: En mode FIXE ou ATR avec TP partiel, vérifier que TP partiel < TP final
        # Si TP partiel pas vendu ET prix >= TP final, c'est un problème (TP partiel devrait se déclencher en premier)
        if self.config.use_partial_tp and not self.active_position.partial_tp_sold:
            # Calculer le seuil TP partiel selon le mode
            if not self.config.use_atr:
                # Mode FIXE: TP partiel à 0.3%
                tp_partial_threshold_pct = self.config.partial_tp_trigger  # 0.3%
                tp_final_threshold_pct = self.config.fixed_tp_pct  # 0.6%
            else:
                # Mode ATR MULTI: TP partiel à 1× ATR
                if self.active_position.atr5m:
                    atr_blended = (self.active_position.atr * 0.7) + (self.active_position.atr5m * 0.3)
                    atr_percent = (atr_blended / self.active_position.entry) * 100
                    tp_partial_threshold_pct = atr_percent * 1.0  # 1× ATR
                    tp_mult = self.config.atr_mult_tp
                    if self.config.win_streak >= 3:
                        tp_mult = 4.0
                    elif self.config.loss_streak >= 2:
                        tp_mult = 1.5
                    if tp_mult < 1.5:
                        tp_mult = 1.5
                    tp_final_threshold_pct = atr_percent * tp_mult  # >= 1.5× ATR
                else:
                    # Mode ATR SIMPLE: pas de TP partiel
                    tp_partial_threshold_pct = 999  # Désactiver la vérification
            
            # Vérifier si TP partiel < TP final (doit toujours être vrai)
            if tp_partial_threshold_pct < tp_final_threshold_pct:
                # Calculer PnL actuel
                current_pnl = self._calculate_pnl(current_price)
                
                # Si prix a dépassé le TP partiel mais TP partiel pas encore vendu, c'est un problème de timing
                # Mais on laisse _update_fixed_mode_sl() ou _update_atr_mode_sl() gérer le TP partiel
                # Cette vérification sert juste à logger un warning si nécessaire
                if current_pnl >= tp_partial_threshold_pct:
                    logger.debug(
                        f"⚠️ Prix au-dessus TP partiel ({tp_partial_threshold_pct:.2f}%) mais TP partiel pas encore vendu. "
                        f"Prix devrait déclencher TP partiel dans _update_*_mode_sl()"
                    )
        
        if direction == 'LONG':
            if current_price <= sl:
                logger.info(f"🛑 SL TOUCHÉ (LONG): Prix {current_price:.6f} <= SL {sl:.6f}")
                return 'SL'
            # 🔥 FIX: Si TP partiel vendu, vérifier TP final seulement pour les 50% restants
            if current_price >= tp:
                if self.config.use_partial_tp and self.active_position.partial_tp_sold:
                    # TP partiel déjà vendu, fermer les 50% restants au TP final
                    logger.info(f"🎯 TP FINAL ATTEINT (LONG, après TP partiel): Prix {current_price:.6f} >= TP {tp:.6f}")
                    return 'TP'
                else:
                    # TP partiel pas encore vendu, mais prix a atteint TP final
                    # Cela ne devrait pas arriver si le TP partiel est < TP final
                    # Mais si ça arrive, on ferme quand même (fallback)
                    logger.warning(f"⚠️ TP FINAL ATTEINT AVANT TP PARTIEL (LONG): Prix {current_price:.6f} >= TP {tp:.6f}")
                    return 'TP'
        else:  # SHORT
            if current_price >= sl:
                logger.info(f"🛑 SL TOUCHÉ (SHORT): Prix {current_price:.6f} >= SL {sl:.6f}")
                return 'SL'
            # 🔥 FIX: Si TP partiel vendu, vérifier TP final seulement pour les 50% restants
            if current_price <= tp:
                if self.config.use_partial_tp and self.active_position.partial_tp_sold:
                    # TP partiel déjà vendu, fermer les 50% restants au TP final
                    logger.info(f"🎯 TP FINAL ATTEINT (SHORT, après TP partiel): Prix {current_price:.6f} <= TP {tp:.6f}")
                    return 'TP'
                else:
                    # TP partiel pas encore vendu, mais prix a atteint TP final
                    logger.warning(f"⚠️ TP FINAL ATTEINT AVANT TP PARTIEL (SHORT): Prix {current_price:.6f} <= TP {tp:.6f}")
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
        elif reason == 'MANUAL':
            # 🔥 FIX: Pour fermeture manuelle, utiliser le prix fourni (prix actuel du marché)
            # Si exit_price n'est pas fourni, utiliser le dernier prix connu
            if exit_price is None:
                if self.active_position.symbol in self.price_cache:
                    exit_price = self.price_cache[self.active_position.symbol]['price']
                else:
                    exit_price = entry
                    logger.warning(f"⚠️ Fermeture MANUAL: pas de prix disponible, utilisation entry: {entry}")
            else:
                logger.info(f"🔧 Fermeture MANUAL: prix de sortie={exit_price:.6f} (fourni)")
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
            # 🔥 FIX: P&L final = TP partiel + fermeture finale (calcul correct)
            # Calculer PnL USDT pour la partie fermée maintenant
            if self.active_position.direction == 'LONG':
                price_diff_final = exit_price - entry
            else:  # SHORT
                price_diff_final = entry - exit_price
            
            pnl_final_usdt = partial_profit_usdt + (size_to_close * price_diff_final / entry)
            pnl_total_pct = (pnl_final_usdt / self.active_position.size) * 100
        else:
            # 🔥 FIX: Position fermée en entier - calcul correct
            # PnL USDT = size * (prix_diff / entry) où prix_diff = exit_price - entry (LONG) ou entry - exit_price (SHORT)
            if self.active_position.direction == 'LONG':
                price_diff = exit_price - entry
            else:  # SHORT
                price_diff = entry - exit_price
            
            pnl_final_usdt = self.active_position.size * (price_diff / entry)
            # 🔥 FIX: Calculer pnl_total_pct depuis pnl_final_usdt pour cohérence
            pnl_total_pct = (pnl_final_usdt / self.active_position.size) * 100
        
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
        
        # 🔥 FIX: Calculer total_costs_usdt d'abord
        total_costs_usdt = (total_costs / 100 * self.active_position.size)
        
        # 🔥 v6.4: Net P&L en % et USDT
        net_pnl_pct = pnl_total_pct - total_costs
        net_pnl_usdt = pnl_final_usdt - total_costs_usdt  # 🔥 FIX: Utiliser total_costs_usdt calculé
        
        # Durée
        duration = int(
            (datetime.now().timestamp() - self.active_position.timestamp) 
            / 1.0
        )
        
        # 🔥 FIX: Générer un ID unique pour cette fermeture pour éviter le double comptage
        import time
        closure_id = f"{self.active_position.symbol}_{self.active_position.timestamp}_{time.time()}"
        
        result = {
            'symbol': self.active_position.symbol,
            'direction': self.active_position.direction,
            'entry': round(entry, 6),
            'exit': round(exit_price, 6),
            # 🔥 FIX: PnL brut (avant frais et slippage)
            'pnl': round(pnl_total_pct, 2),  # Alias pour compatibilité
            'gross_pnl': round(pnl_total_pct, 2),  # 🔥 FIX: PnL brut explicite
            'gross_pnl_pct': round(pnl_total_pct, 2),  # 🔥 FIX: Alias pour frontend
            'pnl_usdt': round(pnl_final_usdt, 4),  # 🔥 v6.4: PnL brut USDT
            'gross_pnl_usdt': round(pnl_final_usdt, 4),  # 🔥 FIX: Alias pour frontend
            # 🔥 FIX: Coûts
            'fees': round(fees, 2),
            'slippage': round(slippage, 2),
            'total_costs': round(total_costs, 2),
            'total_costs_usdt': round(total_costs_usdt, 4),  # 🔥 FIX: Utiliser total_costs_usdt calculé
            # 🔥 FIX: PnL net (après frais et slippage)
            'net_pnl': round(net_pnl_pct, 2),
            'net_pnl_usdt': round(net_pnl_usdt, 4),  # 🔥 v6.4
            'duration': duration,
            'reason': reason,  # 🔥 FIX: Utiliser 'reason' pour compatibilité frontend
            'close_reason': reason,  # 🔥 FIX: Alias pour compatibilité
            'timestamp': self.active_position.timestamp,
            'closure_id': closure_id,  # 🔥 FIX: ID unique pour éviter double comptage
            'has_partial_tp': has_partial_tp,  # 🔥 v6.4
            'size_closed': round(size_to_close, 4),  # 🔥 v6.4
            'size': self.active_position.size  # 🔥 FIX: Ajouter size pour calcul stats
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


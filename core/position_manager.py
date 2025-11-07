#!/usr/bin/env python3
"""
Position Manager - Trade Cursor v6.0
Gestion des positions: TP/SL, Break-even, Trailing Stop
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
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
    start_time: float = field(default_factory=lambda: datetime.now().timestamp())  # 🔥 PHASE 1: Temps d'ouverture pour invalidation précoce
    
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
    
    # 🔥 PHASE 5: Métriques conditions
    condition_types: List[str] = field(default_factory=list)  # Types de conditions détectées
    
    # 🔥 PHASE 7: TP Escalier (Multi-Level TP)
    tp_escalier_enabled: bool = False
    tp_escalier_levels: List[Dict] = field(default_factory=list)  # Liste des niveaux configurés
    tp_escalier_current_level: int = 0  # Niveau actuel (0 = aucun niveau passé)
    tp_escalier_size_remaining: float = 1.0  # Taille restante (1.0 = 100%)
    tp_escalier_profits: List[Dict] = field(default_factory=list)  # Historique des TP vendus
    
    pnl_history: List[Dict] = field(default_factory=list)  # Historique PnL avec timestamp (conservé pour usage futur)
    
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
            'capital': self.capital,
            # 🔥 PHASE 7: TP Escalier
            'tp_escalier_enabled': self.tp_escalier_enabled,
            'tp_escalier_current_level': self.tp_escalier_current_level,
            'tp_escalier_size_remaining': self.tp_escalier_size_remaining,
            'tp_escalier_profits': self.tp_escalier_profits
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
    partial_tp_trigger: float = 0.25  # % TP partiel 50% à +0.25% (doit être < TP final 0.6%)
    
    # Break-even progressif (ATR mode)
    be_atr_factor: float = 1.5
    
    # Fees
    taker_fee: float = 0.0  # 0% pour paires scalables
    
    # 🔥 PHASE 6: Recovery Mode
    recovery_mode_active: bool = False
    recovery_mode_remaining_trades: int = 0
    use_fee_calculation: bool = True
    
    # Slippage estimation
    use_slippage_calculation: bool = True
    
    # Win/Loss streaks
    win_streak: int = 0
    loss_streak: int = 0


class PositionManager:
    """Gestionnaire de positions"""
    
    @staticmethod
    def _format_price(price: float, min_decimals: int = 6, max_decimals: int = 10) -> str:
        """
        Formater un prix avec le bon nombre de décimales selon sa valeur
        
        Pour les prix très petits (< 0.01), afficher plus de décimales
        Pour les prix normaux, utiliser min_decimals
        
        Args:
            price: Prix à formater
            min_decimals: Nombre minimum de décimales (défaut: 6)
            max_decimals: Nombre maximum de décimales (défaut: 10)
        
        Returns:
            String formatée du prix
        """
        if price == 0:
            return "0.0"
        
        # Pour les prix très petits (< 0.01), utiliser plus de décimales
        if price < 0.01:
            # Compter les zéros après la virgule
            price_str = f"{price:.{max_decimals}f}"
            # Supprimer les zéros de fin inutiles
            price_str = price_str.rstrip('0').rstrip('.')
            # S'assurer d'avoir au moins min_decimals chiffres significatifs après la virgule
            if '.' in price_str:
                decimals = len(price_str.split('.')[1])
                if decimals < min_decimals:
                    return f"{price:.{min_decimals}f}".rstrip('0').rstrip('.')
            return price_str
        else:
            # Pour les prix normaux, utiliser min_decimals
            return f"{price:.{min_decimals}f}"
    
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
        scalability_data: Optional[Dict] = None,
        condition_types: Optional[List[str]] = None  # 🔥 PHASE 5: Types de conditions
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
        
        # 🔥 PHASE 7: Initialiser TP Escalier si mode TP_MULTI
        from config import TRADING_CONFIG
        tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        tp_escalier_config = TRADING_CONFIG.get('tp_escalier', {})
        tp_escalier_enabled = False
        tp_escalier_levels = []
        
        if tp_sl_mode == 'TP_MULTI' and tp_escalier_config.get('enabled', False):
            tp_escalier_enabled = True
            tp_escalier_levels = tp_escalier_config.get('levels', [])
            logger.info(f"📈 TP Escalier activé: {len(tp_escalier_levels)} niveaux")
        
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
            scalability_data=scalability_data,
            condition_types=condition_types or [],  # 🔥 PHASE 5: Types de conditions
            tp_escalier_enabled=tp_escalier_enabled,  # 🔥 PHASE 7: TP Escalier
            tp_escalier_levels=tp_escalier_levels,
            tp_escalier_current_level=0,
            tp_escalier_size_remaining=1.0,
            tp_escalier_profits=[]
        )
        
        logger.info(
            f"🟢 POSITION OUVERTE: {direction} {symbol} | "
            f"Entry: {entry} | SL: {sl} | TP: {tp}"
            + (f" | TP Escalier: {len(tp_escalier_levels)} niveaux" if tp_escalier_enabled else "")
        )
        
        # 🔥 ARCHITECTURE V2: Notification position ouverte
        if hasattr(self, 'notification_manager') and self.notification_manager:
            try:
                import asyncio
                
                # Créer une fonction wrapper async pour la notification
                async def _notify_position_opened_async():
                    try:
                        await self.notification_manager.notify(
                            'position_opened',
                            {
                                'symbol': symbol,
                                'direction': direction,
                                'entry': entry,
                                'size': size,
                                'tp': tp,
                                'sl': sl,
                                'condition_types': condition_types or []
                            }
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur notification position ouverte (async): {e}")
                
                # Créer la tâche sans attendre (fire-and-forget)
                try:
                    # Essayer d'obtenir le loop en cours
                    loop = asyncio.get_running_loop()
                    # Loop en cours, créer la tâche
                    asyncio.create_task(_notify_position_opened_async())
                except RuntimeError:
                    # Pas de loop en cours, exécuter dans un nouveau thread
                    try:
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(
                                lambda: asyncio.run(_notify_position_opened_async())
                            )
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur notification position ouverte (thread): {e}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur notification position ouverte: {e}")
        
        return self.active_position
    
    def calculate_adaptive_position_size(
        self,
        setup: Dict,
        capital: float,
        sl_percent: float
    ) -> float:
        """
        Calculer taille position adaptative selon qualité du setup
        
        Args:
            setup: Dictionnaire avec les données du setup
            capital: Capital total disponible
            sl_percent: Pourcentage de stop loss
            
        Returns:
            Taille de position en USDT
        """
        from config import TRADING_CONFIG
        
        sizing_config = TRADING_CONFIG.get('position_sizing', {})
        base_risk = sizing_config.get('base_risk', 0.02)  # 2% par défaut
        min_risk = sizing_config.get('min_risk', 0.005)  # 0.5% minimum
        max_risk = sizing_config.get('max_risk', 0.03)  # 3% maximum
        
        # 1. Risk de base selon capital et SL%
        if sl_percent > 0:
            base_size = (capital * base_risk) / (sl_percent / 100)
        else:
            base_size = capital * base_risk
        
        # 2. Ajuster selon score setup
        score = setup.get('totalScore', 8)
        quality_multipliers = sizing_config.get('quality_multipliers', {})
        
        if score >= 12:
            multiplier = quality_multipliers.get('excellent', 1.4)  # +40%
        elif score >= 10:
            multiplier = quality_multipliers.get('good', 1.2)  # +20%
        elif score >= 8:
            multiplier = quality_multipliers.get('acceptable', 1.0)  # Normal
        else:
            multiplier = quality_multipliers.get('weak', 0.8)  # -20%
        
        # 3. Ajuster selon streak
        streak_multipliers = sizing_config.get('streak_multipliers', {})
        win_streak = self.config.win_streak
        loss_streak = self.config.loss_streak
        
        if win_streak >= 3:
            streak_mult = streak_multipliers.get('win_streak_3+', 1.1)  # +10%
        elif loss_streak >= 2:
            streak_mult = streak_multipliers.get('loss_streak_2+', 0.85)  # -15%
        else:
            streak_mult = 1.0
        
        # 🔥 PHASE 6: Recovery Mode Progressif - Activation et réduction de taille
        recovery_level = self.get_recovery_level(loss_streak)
        if recovery_level:
            level_num = recovery_level.get('level', 1)
            reduction = recovery_level.get('position_size_reduction', 0.7)
            
            # Activer Recovery Mode si pas déjà actif
            if not self.config.recovery_mode_active:
                self.config.recovery_mode_active = True
                self.config.recovery_mode_remaining_trades = recovery_level.get('duration_trades', 5)
                logger.warning(
                    f"🔄 RECOVERY MODE Niveau {level_num} ACTIVÉ après {loss_streak} losses "
                    f"(durée: {self.config.recovery_mode_remaining_trades} trades, "
                    f"boost: +{recovery_level.get('min_score_boost', 0):.1f}, "
                    f"réduction: {((1-reduction)*100):.0f}%)"
                )
            
            # Appliquer réduction de taille
            # Combiner avec streak_mult: recovery_mult × streak_mult
            # Exemple: 0.7 × 0.85 = 0.595 (réduction totale de 40.5%)
            streak_mult = streak_mult * reduction
            logger.debug(f"🔄 Recovery Mode Niveau {level_num}: Taille réduite (mult: {reduction:.2f}, final streak: {streak_mult:.2f})")
        
        # 4. Calculer taille finale
        final_size = base_size * multiplier * streak_mult
        
        # 5. Bornes : 0.5% - 3% du capital
        min_size = capital * min_risk
        max_size = capital * max_risk
        final_size = max(min_size, min(max_size, final_size))
        
        logger.debug(
            f"📊 Position sizing adaptatif: {setup.get('symbol', 'N/A')} | "
            f"Score={score:.1f} | Base={base_size:.0f} | "
            f"Multiplier={multiplier:.2f} | Streak={streak_mult:.2f} | "
            f"Final={final_size:.2f} USDT"
        )
        
        return round(final_size, 2)
    
    def get_recovery_level(self, loss_streak: int) -> Optional[Dict]:
        """
        🔥 PHASE 6: Obtenir niveau recovery selon loss streak (mode PROGRESSIVE)
        
        Args:
            loss_streak: Nombre de pertes consécutives
            
        Returns:
            Dict avec niveau recovery ou None
        """
        from config import TRADING_CONFIG
        
        recovery_config = TRADING_CONFIG.get('recovery_mode', {})
        
        if not recovery_config.get('enabled', False):
            return None
        
        mode = recovery_config.get('mode', 'SIMPLE')
        
        if mode == 'SIMPLE':
            # Mode simple existant (fallback)
            trigger = recovery_config.get('trigger_loss_streak', 3)
            if loss_streak >= trigger:
                return {
                    'level': 1,
                    'min_score_boost': recovery_config.get('min_score_boost', 1.5),
                    'position_size_reduction': recovery_config.get('position_size_reduction', 0.7),
                    'confluence_forced': recovery_config.get('confluence_forced', False),
                    'duration_trades': recovery_config.get('duration_trades', 5)
                }
            return None
        
        # Mode PROGRESSIVE
        levels = recovery_config.get('levels', [])
        
        # Trouver niveau le plus élevé applicable
        applicable_level = None
        for i, level in enumerate(levels):
            if loss_streak >= level['trigger_loss_streak']:
                applicable_level = {**level, 'level': i + 1}
        
        return applicable_level
    
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
            'TP', 'SL', 'EARLY_INVALIDATION', etc. si fermeture nécessaire
        """
        if not self.active_position:
            return None
        
        # 🔥 FIX: Vérifier que le prix est valide
        if not current_price or current_price <= 0:
            logger.warning(f"⚠️ Prix invalide dans check_position: {current_price}")
            return None
        
        # 🔥 PHASE 1: Invalidation précoce (30 premières secondes)
        elapsed = time.time() - self.active_position.start_time
        if elapsed <= 30:  # 30 premières secondes critiques
            early_invalidation = await self._check_early_invalidation(current_price, elapsed)
            if early_invalidation:
                return early_invalidation  # Position fermée
        
        # Calculer P&L
        pnl = self._calculate_pnl(current_price)
        
        # 🔥 FIX: Log détaillé pour debug (incluant TP partiel)
        partial_tp_status = "TP partiel: OUI" if self.active_position.partial_tp_sold else "TP partiel: NON"
        logger.debug(
            f"🔍 Check position: {self.active_position.symbol} {self.active_position.direction} | "
            f"Entry={self._format_price(self.active_position.entry)} | Prix={self._format_price(current_price)} | "
            f"PnL={pnl:.2f}% | {partial_tp_status} | SL={self._format_price(self.active_position.sl)} | TP={self._format_price(self.active_position.tp)}"
        )
        
        # Mettre à jour le SL dynamique selon le mode (AVANT de vérifier TP/SL)
        # Cela permet au TP partiel de se déclencher avant le TP final
        if not self.config.use_atr:
            self._update_fixed_mode_sl(current_price, pnl)
        else:
            await self._update_atr_mode_sl(current_price, pnl)
        
        # 🔥 PHASE 2: Trailing stop adaptatif ATR (tous modes) - déclenchement à +0.25%
        # Appelé après _update_*_mode_sl pour compléter/compléter le trailing existant
        if pnl > 0.25:  # Seuil de déclenchement à +0.25%
            await self._update_trailing_stop_adaptive(current_price)
        
        # 🔥 PHASE 7: Vérifier TP Escalier (Multi-Level TP)
        if self.active_position.tp_escalier_enabled and self.active_position.tp_escalier_levels:
            await self._check_tp_escalier_levels(current_price)
        
        # Vérifier TP/SL
        reason = self._check_levels(current_price)
        
        if reason:
            logger.info(f"🚨 Clôture position: {reason}")
            return reason
        
        return None
    
    def get_adaptive_early_threshold(self, elapsed: float) -> float:
        """
        🔥 PHASE 8: Calculer seuil Early Invalidation adaptatif selon ATR
        
        Args:
            elapsed: Temps écoulé en secondes
        
        Returns:
            Seuil PnL adaptatif (négatif)
        """
        from config import TRADING_CONFIG
        
        # Seuil de base selon temps écoulé (utiliser config actuelle)
        early_config = TRADING_CONFIG.get('early_invalidation', {})
        
        if elapsed <= 15:
            base_threshold = early_config.get('threshold_15s', -0.12)  # -0.12% pour 10-15s
        else:
            base_threshold = early_config.get('threshold_30s', -0.08)  # -0.08% pour 15-30s
        
        # Vérifier si seuils adaptatifs activés
        adaptive_config = TRADING_CONFIG.get('adaptive_thresholds', {})
        if not adaptive_config.get('enabled', True):
            return base_threshold
        
        # Calculer ATR en pourcentage (à la volée car atr_percent n'existe pas)
        position = self.active_position
        if position and position.atr and position.entry:
            atr_percent = (position.atr / position.entry) * 100
        else:
            atr_percent = 0.5  # Valeur par défaut
        
        # Ajuster selon ATR
        early_inv_config = adaptive_config.get('early_invalidation', {})
        
        if atr_percent < 0.3:  # Faible volatilité
            # Moins strict (ATR faible = mouvements plus petits)
            multiplier = early_inv_config.get('low_vol_multiplier', 0.7)
        elif atr_percent > 0.8:  # Haute volatilité
            # Plus strict (ATR élevé = mouvements plus grands)
            multiplier = early_inv_config.get('high_vol_multiplier', 1.3)
        else:  # Volatilité normale
            multiplier = 1.0
        
        adaptive_threshold = base_threshold * multiplier
        
        # Bornes de sécurité
        adaptive_threshold = max(-0.15, min(-0.05, adaptive_threshold))
        
        logger.debug(
            f"🎯 Seuil Early adaptatif: {adaptive_threshold:.3f}% "
            f"(base: {base_threshold:.2f}%, ATR: {atr_percent:.2f}%, mult: {multiplier:.2f})"
        )
        
        return adaptive_threshold
    
    async def _check_early_invalidation(self, current_price: float, elapsed: float) -> Optional[str]:
        """
        Vérifier si setup ne réagit pas comme prévu (30 premières secondes)
        Avec seuils adaptatifs ATR
        
        Returns:
            'EARLY_INVALIDATION' si position doit être fermée, None sinon
        """
        from config import TRADING_CONFIG
        
        # Attendre au moins 10s (laisser le temps au marché)
        if elapsed < 10:
            return None
        
        if elapsed > 30:
            return None  # Fenêtre fermée
        
        pnl = self._calculate_pnl(current_price)
        
        # Seuils d'invalidation selon temps écoulé
        early_config = TRADING_CONFIG.get('early_invalidation', {})
        enabled = early_config.get('enabled', True)
        
        if not enabled:
            return None
        
        # ⚡ Seuil adaptatif selon ATR
        invalidation_threshold = self.get_adaptive_early_threshold(elapsed)
        
        # Vérifier mouvement attendu
        if pnl <= invalidation_threshold:
            atr_percent = (self.active_position.atr / self.active_position.entry * 100) if (self.active_position.atr and self.active_position.entry) else 0.0
            logger.warning(
                f"⚠️ Invalidation précoce {self.active_position.direction} "
                f"{self.active_position.symbol}: "
                f"P&L {pnl:.2f}% après {elapsed:.0f}s "
                f"(seuil adaptatif: {invalidation_threshold:.2f}%, "
                f"ATR: {atr_percent:.2f}%)"
            )
            return 'EARLY_INVALIDATION'
        
        # Setup réagit correctement
        return None
    
    async def _update_trailing_stop_adaptive(self, current_price: float):
        """
        Mettre à jour trailing stop adaptatif selon volatilité (ATR)
        Déclenchement à +0.25% pour tous les modes
        """
        from config import TRADING_CONFIG
        
        position = self.active_position
        if not position:
            return
        
        # Récupérer configuration
        trailing_config = TRADING_CONFIG.get('trailing_stop', {})
        enabled = trailing_config.get('enabled', True)
        if not enabled:
            return
        
        # Calculer ATR en pourcentage
        if position.atr and position.entry > 0:
            atr_percent = (position.atr / position.entry) * 100
        else:
            # Fallback si ATR non disponible
            atr_percent = 0.5  # Valeur par défaut
        
        # Calculer distance trailing selon ATR
        atr_multiplier = trailing_config.get('atr_multiplier', 0.4)
        trailing_distance = atr_percent * atr_multiplier
        
        # Bornes : minimum 0.08%, maximum 0.25%
        min_distance = trailing_config.get('min_distance', 0.08)
        max_distance = trailing_config.get('max_distance', 0.25)
        trailing_distance = max(min_distance, min(max_distance, trailing_distance))
        
        # Calculer nouveau SL
        if position.direction == 'LONG':
            new_sl = current_price * (1 - trailing_distance / 100)
            
            # Monter SL uniquement (jamais descendre)
            if new_sl > position.sl:
                old_sl = position.sl
                position.sl = round(new_sl, 6)
                
                logger.info(
                    f"🔄 Trailing SL LONG {position.symbol}: "
                    f"{self._format_price(old_sl)} → {self._format_price(new_sl)} (-{trailing_distance:.2f}%) "
                    f"[ATR: {atr_percent:.2f}%]"
                )
        
        else:  # SHORT
            new_sl = current_price * (1 + trailing_distance / 100)
            
            # Descendre SL uniquement (jamais monter)
            if new_sl < position.sl:
                old_sl = position.sl
                position.sl = round(new_sl, 6)
                
                logger.info(
                    f"🔄 Trailing SL SHORT {position.symbol}: "
                    f"{self._format_price(old_sl)} → {self._format_price(new_sl)} (+{trailing_distance:.2f}%) "
                    f"[ATR: {atr_percent:.2f}%]"
                )
    
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
        # 🔥 v6.4: TP partiel PHYSIQUE 50% à +0.25%
        if self.config.use_partial_tp and not self.active_position.partial_tp_sold:
            if pnl >= self.config.partial_tp_trigger:  # +0.25%
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
        
        # 🔥 PHASE 2: Après TP partiel, utiliser uniquement trailing adaptatif (pas de TP final fixe)
        # Si TP partiel vendu, on désactive le TP final et on laisse le trailing adaptatif gérer
        # Cela permet de capturer des gains au-delà de 0.6% si le prix "explose"
        # Le trailing fixe (0.15%) n'est plus utilisé, remplacé par le trailing adaptatif ATR
        from config import TRADING_CONFIG
        trailing_config = TRADING_CONFIG.get('trailing_stop', {})
        use_adaptive_trailing = trailing_config.get('enabled', True)
        
        # 🔥 MODIFICATION: Après TP partiel, on n'utilise plus le trailing fixe
        # Le trailing adaptatif (géré dans check_position) prend le relais
        # Donc on ne fait rien ici si TP partiel vendu
        if False and not use_adaptive_trailing and self.config.use_trailing_stop and self.active_position.partial_tp_sold:
            new_sl = None
            entry = self.active_position.entry
            
            if self.active_position.direction == 'LONG':
                # LONG: trailing stop vers le haut quand prix monte
                new_sl = current_price * (1 - self.config.trailing_distance / 100)
                # Le SL doit monter (augmenter) pour protéger les gains
                if new_sl > self.active_position.sl:
                    self.active_position.sl = round(new_sl, 6)
                    logger.info(f"📈 TRAILING STOP: Nouveau SL={self._format_price(new_sl)} (distance={self.config.trailing_distance}%)")
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
                    logger.info(f"📉 TRAILING STOP: Nouveau SL={self._format_price(new_sl)} (distance={self.config.trailing_distance}%) | Prix={self._format_price(current_price)} | Entry={self._format_price(entry)}")
    
    async def _update_atr_mode_sl(self, current_price: float, pnl: float):
        """Mettre à jour SL en mode ATR (break-even progressif, TP Escalier, ou ATR MULTI avec TP partiel)"""
        if not self.active_position.atr:
            return
        
        # 🔥 PHASE 7: TP Escalier - Vérifier niveaux si activé
        if self.active_position.tp_escalier_enabled:
            await self._check_tp_escalier_levels(current_price)
            return  # TP Escalier gère tout, pas besoin de break-even progressif
        
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
                        logger.info(f"📈 TRAILING ATR: Nouveau SL={self._format_price(new_sl)} (distance {trailing_distance_atr:.3f}%)")
                else:  # SHORT
                    # 🔥 FIX: SHORT trailing stop - après TP partiel, SL = entry
                    # Quand prix baisse (profit augmente), new_sl doit descendre avec le prix
                    new_sl = current_price * (1 + trailing_distance_atr / 100)
                    # Pour SHORT, SL doit être au-dessus du prix actuel mais descendre avec le prix
                    # Condition: new_sl doit être < SL actuel (pour descendre) ET > current_price (pour protéger)
                    if new_sl < self.active_position.sl and new_sl > current_price:
                        self.active_position.sl = round(new_sl, 6)
                        logger.info(f"📉 TRAILING ATR: Nouveau SL={self._format_price(new_sl)} (distance {trailing_distance_atr:.3f}%) | Prix={self._format_price(current_price)} | Entry={self._format_price(entry)}")
            
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
            logger.info(f"🛡️ BE Progressif 50%: PnL={pnl:.2f}% → SL={self._format_price(new_sl)}")
        
        # Phase 2: BE total
        if pnl >= pnl_100pct and self.active_position.break_even_set:
            self.active_position.sl = entry
            logger.info(f"🛡️ BE Total 100%: PnL={pnl:.2f}% → SL={entry}")
    
    async def _check_tp_escalier_levels(self, current_price: float):
        """
        🔥 PHASE 7: Vérifier les niveaux TP Escalier et exécuter TPs partiels
        
        Args:
            current_price: Prix actuel du marché
        """
        position = self.active_position
        if not position or not position.tp_escalier_enabled or not position.tp_escalier_levels:
            return
        
        direction = position.direction
        entry = position.entry
        current_level = position.tp_escalier_current_level
        
        # Vérifier si le niveau actuel est atteint
        if current_level >= len(position.tp_escalier_levels):
            # Tous les niveaux ont été atteints
            return
        
        # Récupérer config du niveau actuel
        level_config = position.tp_escalier_levels[current_level]
        pnl_target = level_config['pnl']  # % (ex: 0.20 = +0.20%)
        size_pct = level_config['size_pct']  # % de la position (ex: 0.25 = 25%)
        move_sl = level_config['move_sl']  # 'entry', 'breakeven', 'trailing'
        
        # Calculer prix TP pour ce niveau
        if direction == 'LONG':
            tp_price = entry * (1 + pnl_target / 100)
        else:  # SHORT
            tp_price = entry * (1 - pnl_target / 100)
        
        # Vérifier si niveau atteint
        tp_hit = False
        if direction == 'LONG':
            tp_hit = current_price >= tp_price
        else:  # SHORT
            tp_hit = current_price <= tp_price
        
        if tp_hit:
            # ✅ Niveau TP Escalier atteint !
            position.tp_escalier_current_level += 1
            
            # Calculer taille vendue et restante
            size_sold_pct = size_pct
            size_sold_usdt = position.size * size_pct
            position.tp_escalier_size_remaining -= size_pct
            
            # Calculer profit de ce niveau
            if direction == 'LONG':
                profit_pct = ((tp_price - entry) / entry) * 100
                profit_usdt = size_sold_usdt * profit_pct / 100
            else:  # SHORT
                profit_pct = ((entry - tp_price) / entry) * 100
                profit_usdt = size_sold_usdt * profit_pct / 100
            
            # Enregistrer le profit de ce niveau
            profit_record = {
                'level': current_level + 1,
                'price': tp_price,
                'size_pct': size_pct,
                'size_usdt': size_sold_usdt,
                'profit_pct': profit_pct,
                'profit_usdt': profit_usdt,
                'timestamp': time.time()
            }
            position.tp_escalier_profits.append(profit_record)
            
            # Cumuler profit partiel
            position.partial_profit_usdt += profit_usdt
            
            logger.info(
                f"🎯 TP Escalier Niveau {current_level + 1}/{len(position.tp_escalier_levels)} atteint ! "
                f"Prix: {self._format_price(tp_price)} | Vendu: {size_sold_usdt:.2f} USDT ({size_pct*100:.0f}%) | "
                f"Profit: +{profit_usdt:.2f} USDT (+{profit_pct:.2f}%) | "
                f"Restant: {position.tp_escalier_size_remaining*100:.0f}%"
            )
            
            # Déplacer SL selon config niveau
            if move_sl == 'entry':
                # Déplacer SL à entry (protéger capital)
                position.sl = entry
                logger.info(f"🛡️ TP Escalier Niveau {current_level + 1}: SL → Entry ({self._format_price(entry)})")
            
            elif move_sl == 'breakeven':
                # Déplacer SL à breakeven (entry)
                position.sl = entry
                position.break_even_set = True
                logger.info(f"🛡️ TP Escalier Niveau {current_level + 1}: SL → Breakeven ({self._format_price(entry)})")
            
            elif move_sl == 'trailing':
                # Activer trailing stop adaptatif
                await self._update_trailing_stop_adaptive(current_price)
                logger.info(f"📈 TP Escalier Niveau {current_level + 1}: Trailing stop activé")
            
            # Émettre événement SocketIO si callback défini
            if hasattr(self, 'socketio_callback') and self.socketio_callback:
                await self.socketio_callback('tp_escalier_level', {
                    'symbol': position.symbol,
                    'level': current_level + 1,
                    'total_levels': len(position.tp_escalier_levels),
                    'price': tp_price,
                    'profit_usdt': profit_usdt,
                    'profit_pct': profit_pct,
                    'size_remaining_pct': position.tp_escalier_size_remaining * 100
                })
            
            # 🔥 ARCHITECTURE V2: Notification TP Escalier niveau
            if hasattr(self, 'notification_manager') and self.notification_manager:
                await self.notification_manager.notify(
                    'tp_escalier_level',
                    {
                        'symbol': position.symbol,
                        'level': current_level + 1,
                        'total_levels': len(position.tp_escalier_levels),
                        'price': tp_price,
                        'profit_usdt': profit_usdt,
                        'profit_pct': profit_pct,
                        'size_remaining_pct': position.tp_escalier_size_remaining * 100
                    }
                )
            
            # Si dernier niveau atteint, logger info
            if position.tp_escalier_current_level >= len(position.tp_escalier_levels):
                total_profit = sum(p['profit_usdt'] for p in position.tp_escalier_profits)
                logger.info(
                    f"🎉 TP Escalier: Tous les {len(position.tp_escalier_levels)} niveaux atteints ! "
                    f"Profit total cumulé: +{total_profit:.2f} USDT"
                )
    
    def _check_levels(self, current_price: float) -> Optional[str]:
        """Vérifier si TP ou SL est touché"""
        direction = self.active_position.direction
        sl = self.active_position.sl
        tp = self.active_position.tp
        
        # Calculer PnL pour déterminer si c'est un trailing stop ou SL classique
        pnl = self._calculate_pnl(current_price)
        
        # 🔥 PHASE 7: TP Escalier - Gestion spéciale
        if self.active_position.tp_escalier_enabled:
            # Si tous les niveaux sont passés, vérifier seulement SL (trailing stop gère)
            if self.active_position.tp_escalier_current_level >= len(self.active_position.tp_escalier_levels):
                # Tous niveaux passés, vérifier seulement SL (trailing stop)
                if direction == 'LONG':
                    if current_price <= sl:
                        # Après TP Escalier, c'est toujours un trailing stop
                        return 'TS'
                else:  # SHORT
                    if current_price >= sl:
                        # Après TP Escalier, c'est toujours un trailing stop
                        return 'TS'
                return None
            else:
                # Niveaux restants, ne pas vérifier TP final (géré par _check_tp_escalier_levels)
                # Vérifier seulement SL
                # Si au moins un niveau TP Escalier a été atteint, c'est probablement un trailing stop
                # (car les niveaux TP Escalier ajustent le SL vers entry/breakeven/trailing)
                has_tp_escalier_profits = len(self.active_position.tp_escalier_profits) > 0
                if direction == 'LONG':
                    if current_price <= sl:
                        # Si au moins un palier atteint OU PnL positif, c'est un trailing stop
                        if has_tp_escalier_profits or pnl >= 0:
                            return 'TS'
                        else:
                            return 'SL'
                else:  # SHORT
                    if current_price >= sl:
                        # Si au moins un palier atteint OU PnL positif, c'est un trailing stop
                        if has_tp_escalier_profits or pnl >= 0:
                            return 'TS'
                        else:
                            return 'SL'
                return None
        
        # 🔥 FIX: Log détaillé pour debug
        logger.debug(
            f"🔍 Vérification TP/SL: {direction} | "
            f"Prix={self._format_price(current_price)} | SL={self._format_price(sl)} | TP={self._format_price(tp)}"
        )
        
        # 🔥 FIX: En mode FIXE ou ATR avec TP partiel, vérifier que TP partiel < TP final
        # Si TP partiel pas vendu ET prix >= TP final, c'est un problème (TP partiel devrait se déclencher en premier)
        if self.config.use_partial_tp and not self.active_position.partial_tp_sold:
            # Calculer le seuil TP partiel selon le mode
            if not self.config.use_atr:
                # Mode FIXE: TP partiel à 0.25%
                tp_partial_threshold_pct = self.config.partial_tp_trigger  # 0.25%
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
                    tp_final_threshold_pct = 999  # Désactiver la vérification
            
            # Vérifier si TP partiel < TP final (doit toujours être vrai)
            # Ne pas vérifier si on est en mode ATR SIMPLE (les deux sont à 999)
            if tp_partial_threshold_pct < tp_final_threshold_pct and tp_final_threshold_pct < 999:
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
        
        # 🔥 MODIFICATION: En mode FIXE, si TP partiel vendu, ignorer TP final et utiliser uniquement trailing stop
        # Cela permet de capturer des gains au-delà de 0.6% si le prix "explose"
        if not self.config.use_atr and self.config.use_partial_tp and self.active_position.partial_tp_sold:
            # Mode FIXE avec TP partiel vendu : ignorer le TP final, seul le trailing stop compte
            # Le trailing stop adaptatif (géré dans check_position) fermera la position si nécessaire
            logger.debug(
                f"🔍 Mode FIXE après TP partiel: Ignorer TP final ({self._format_price(tp)}), "
                f"utiliser uniquement trailing stop (SL={self._format_price(sl)})"
            )
            # Vérifier seulement le SL (qui est le trailing stop adaptatif)
            # 🔥 FIX: Retourner 'TS' (Trailing Stop) au lieu de 'SL' pour distinguer
            if direction == 'LONG':
                if current_price <= sl:
                    logger.info(f"🚨 Trailing stop touché (LONG): {self._format_price(current_price)} <= {self._format_price(sl)}")
                    return 'TS'
            else:  # SHORT
                if current_price >= sl:
                    logger.info(f"🚨 Trailing stop touché (SHORT): {self._format_price(current_price)} >= {self._format_price(sl)}")
                    return 'TS'
            return None  # Position continue, trailing stop protège les gains
        
        # Vérification TP/SL standard (si pas de TP partiel ou TP partiel non vendu, ou mode ATR)
        if direction == 'LONG':
            if current_price <= sl:
                # Si PnL positif, c'est un trailing stop, sinon SL classique
                if pnl >= 0:
                    logger.info(f"📈 Trailing Stop touché (LONG): Prix {self._format_price(current_price)} <= SL {self._format_price(sl)} (PnL: {pnl:.2f}%)")
                    return 'TS'
                else:
                    logger.info(f"🛑 SL TOUCHÉ (LONG): Prix {self._format_price(current_price)} <= SL {self._format_price(sl)} (PnL: {pnl:.2f}%)")
                    return 'SL'
            # Vérifier TP final seulement si TP partiel pas vendu (ou mode ATR)
            if current_price >= tp:
                if self.config.use_partial_tp and self.active_position.partial_tp_sold:
                    # Mode ATR : TP final peut être atteint après TP partiel
                    if self.config.use_atr:
                        logger.info(f"🎯 TP FINAL ATTEINT (LONG, après TP partiel): Prix {self._format_price(current_price)} >= TP {self._format_price(tp)}")
                        return 'TP'
                    # Mode FIXE : ne devrait pas arriver ici (géré ci-dessus)
                    logger.debug(f"🔍 Mode FIXE: TP final atteint mais ignoré (trailing stop actif)")
                    return None
                else:
                    # TP partiel pas encore vendu, mais prix a atteint TP final
                    logger.warning(f"⚠️ TP FINAL ATTEINT AVANT TP PARTIEL (LONG): Prix {self._format_price(current_price)} >= TP {self._format_price(tp)}")
                    return 'TP'
        else:  # SHORT
            if current_price >= sl:
                # Si PnL positif, c'est un trailing stop, sinon SL classique
                if pnl >= 0:
                    logger.info(f"📈 Trailing Stop touché (SHORT): Prix {self._format_price(current_price)} >= SL {self._format_price(sl)} (PnL: {pnl:.2f}%)")
                    return 'TS'
                else:
                    logger.info(f"🛑 SL TOUCHÉ (SHORT): Prix {self._format_price(current_price)} >= SL {self._format_price(sl)} (PnL: {pnl:.2f}%)")
                    return 'SL'
            # Vérifier TP final seulement si TP partiel pas vendu (ou mode ATR)
            if current_price <= tp:
                if self.config.use_partial_tp and self.active_position.partial_tp_sold:
                    # Mode ATR : TP final peut être atteint après TP partiel
                    if self.config.use_atr:
                        logger.info(f"🎯 TP FINAL ATTEINT (SHORT, après TP partiel): Prix {self._format_price(current_price)} <= TP {self._format_price(tp)}")
                        return 'TP'
                    # Mode FIXE : ne devrait pas arriver ici (géré ci-dessus)
                    logger.debug(f"🔍 Mode FIXE: TP final atteint mais ignoré (trailing stop actif)")
                    return None
                else:
                    # TP partiel pas encore vendu, mais prix a atteint TP final
                    logger.warning(f"⚠️ TP FINAL ATTEINT AVANT TP PARTIEL (SHORT): Prix {self._format_price(current_price)} <= TP {self._format_price(tp)}")
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
        elif reason == 'SL' or reason == 'TS':
            # 🔥 FIX: TS (Trailing Stop) utilise aussi le SL actuel
            exit_price = self.active_position.sl
        elif reason == 'EARLY_INVALIDATION':
            # 🔥 FIX: Pour invalidation précoce, utiliser le prix fourni (prix actuel du marché)
            # Si exit_price n'est pas fourni, utiliser le dernier prix connu
            if exit_price is None:
                if self.active_position.symbol in self.price_cache:
                    exit_price = self.price_cache[self.active_position.symbol]['price']
                else:
                    exit_price = entry
                    logger.warning(f"⚠️ Fermeture EARLY_INVALIDATION: pas de prix disponible, utilisation entry: {entry}")
            else:
                logger.info(f"🔧 Fermeture EARLY_INVALIDATION: prix de sortie={self._format_price(exit_price)} (fourni)")
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
                logger.info(f"🔧 Fermeture MANUAL: prix de sortie={self._format_price(exit_price)} (fourni)")
        elif reason == 'API_STUCK':
            # Utiliser le dernier prix connu
            if self.active_position.symbol in self.price_cache:
                exit_price = self.price_cache[self.active_position.symbol]['price']
            else:
                exit_price = entry
        else:
            exit_price = entry
        
        # 🔥 PHASE 7: Gérer TP Escalier
        has_tp_escalier = self.active_position.tp_escalier_enabled and len(self.active_position.tp_escalier_profits) > 0
        tp_escalier_profits_usdt = sum([p['profit_usdt'] for p in self.active_position.tp_escalier_profits])
        
        # Calculer taille restante après TP Escalier
        if has_tp_escalier:
            size_to_close = self.active_position.size * self.active_position.tp_escalier_size_remaining
        else:
            size_to_close = self.active_position.size
        
        # 🔥 v6.4: Gérer la position partielle (mode FIXE/ATR)
        has_partial_tp = self.active_position.partial_tp_sold and not has_tp_escalier
        partial_profit_usdt = self.active_position.partial_profit_usdt
        
        if has_partial_tp:
            # On ferme les 50% restants
            size_to_close = self.active_position.size_remaining or (self.active_position.size * 0.5)
        
        # 🔥 FIX: Calculer P&L brut pour la partie fermée (utilise exit_price correct pour toutes les raisons)
        # Pour EARLY_INVALIDATION, exit_price est maintenant le prix actuel du marché (fourni)
        pnl_pct = ((exit_price - entry) / entry) * 100
        if self.active_position.direction == 'SHORT':
            pnl_pct = -pnl_pct
        
        # 🔥 PHASE 7: Calculer P&L en USDT (TP Escalier, TP partiel, ou position complète)
        if has_tp_escalier:
            # TP Escalier: Profits des niveaux + fermeture finale
            if self.active_position.direction == 'LONG':
                price_diff_final = exit_price - entry
            else:  # SHORT
                price_diff_final = entry - exit_price
            
            final_profit_usdt = size_to_close * (price_diff_final / entry)
            pnl_final_usdt = tp_escalier_profits_usdt + final_profit_usdt
            pnl_total_pct = (pnl_final_usdt / self.active_position.size) * 100
        elif has_partial_tp:
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
        
        # 🔥 PHASE 5: Enregistrer métriques par condition
        from core.metrics import condition_metrics
        won = pnl_total_pct > 0
        conditions = self.active_position.condition_types or []
        if conditions:
            condition_metrics.record_trade(conditions, won)
        
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
        
        # 🔥 PHASE 6: Recovery Mode - Décrémenter compteur
        from config import TRADING_CONFIG
        recovery_config = TRADING_CONFIG.get('recovery_mode', {})
        if recovery_config.get('enabled', False) and self.config.recovery_mode_active:
            self.config.recovery_mode_remaining_trades -= 1
            if self.config.recovery_mode_remaining_trades <= 0:
                self.config.recovery_mode_active = False
                logger.info("✅ Recovery Mode terminé - Retour normal")
            else:
                logger.info(f"🔄 Recovery Mode: {self.config.recovery_mode_remaining_trades} trades restants")
        
        # 🔥 FIX CRITIQUE: Sauvegarder position AVANT de la réinitialiser
        position = self.active_position
        
        # Réinitialiser
        self.active_position = None
        
        logger.info(
            f"🔴 POSITION FERMÉE: {result['symbol']} | "
            f"Raison: {reason} | PnL net: {net_pnl_pct:.2f}% ({net_pnl_usdt:.4f} USDT)"
        )
        
        # 🔥 ARCHITECTURE V2: Logger trade dans Analytics DB
        if hasattr(self, 'analytics_db') and self.analytics_db:
            try:
                import json
                import asyncio
                
                # Déterminer trading mode
                try:
                    from config import PAPER_TRADING_MODE
                    is_paper = PAPER_TRADING_MODE
                except:
                    is_paper = False
                
                # 🔥 FIX: Récupérer tp_sl_mode depuis TRADING_CONFIG (Position n'a pas cet attribut)
                from config import TRADING_CONFIG
                tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
                
                # 🔥 FIX: Calculer timestamp, date, time pour la table trades
                # datetime est déjà importé en haut du fichier, ne pas réimporter ici
                now = datetime.now()
                trade_timestamp = now.isoformat()
                trade_date = now.strftime('%Y-%m-%d')
                trade_time = now.strftime('%H:%M:%S')
                
                # 🔥 FIX: Calculer PnL brut et net pour la table trades
                # PnL brut = PnL avant frais/slippage
                gross_pnl_pct = net_pnl_pct + total_costs  # Ajouter les coûts pour obtenir le brut
                gross_pnl_usdt = net_pnl_usdt + total_costs_usdt
                
                trade_data = {
                    # Champs requis par la table trades
                    'timestamp': trade_timestamp,
                    'date': trade_date,
                    'time': trade_time,
                    'symbol': position.symbol,
                    'direction': position.direction,
                    'entry': position.entry,
                    'exit': exit_price,
                    'gross_pnl_pct': gross_pnl_pct,
                    'gross_pnl_usdt': gross_pnl_usdt,
                    'net_pnl_pct': net_pnl_pct,
                    'net_pnl_usdt': net_pnl_usdt,
                    'fees': fees,
                    'slippage': slippage,
                    'total_costs': total_costs,
                    'reason': reason,
                    'duration': int(time.time() - position.start_time),
                    'condition_types': json.dumps(position.condition_types) if position.condition_types else '[]',
                    
                    # Champs optionnels
                    'trading_mode': 'PAPER' if is_paper else 'LIVE',
                    'is_backtest': False,
                    'session_id': getattr(self, 'session_id', 'unknown'),
                    'tp_sl_mode': tp_sl_mode,
                    'break_even_triggered': position.break_even_set,
                    'trailing_stop_triggered': getattr(position, 'trailing_activated', False),
                    'tp_escalier_enabled': position.tp_escalier_enabled,
                    'tp_escalier_levels_hit': position.tp_escalier_current_level if position.tp_escalier_enabled else 0,
                    
                    # Champs supplémentaires (pour compatibilité)
                    'start_time': position.start_time,
                    'end_time': time.time(),
                    'duration_seconds': time.time() - position.start_time,
                    'size': position.size,
                    'pnl_pct': net_pnl_pct,  # Alias pour compatibilité
                    'pnl_usdt': net_pnl_usdt,  # Alias pour compatibilité
                    'exit_reason': reason,  # Alias pour compatibilité
                    'tp': position.tp,
                    'sl': position.sl,
                    'atr': position.atr,
                    'atr5m': position.atr5m,
                    'max_favorable_excursion_pct': getattr(position, 'max_favorable_excursion_pct', 0),
                    'max_adverse_excursion_pct': getattr(position, 'max_adverse_excursion_pct', 0)
                }
                
                # Logger en async (non-bloquant) - insert_trade est synchrone, utiliser run_in_executor
                # Créer une tâche async pour exécuter insert_trade dans un thread
                async def _log_trade_async():
                    try:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, self.analytics_db.insert_trade, trade_data)
                        logger.debug(f"✅ Trade loggé dans Analytics DB: {position.symbol}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur logging Analytics DB (async): {e}")
                
                # Créer la tâche sans attendre (fire-and-forget)
                try:
                    asyncio.create_task(_log_trade_async())
                except RuntimeError:
                    # Si pas de loop event, exécuter directement (synchrone)
                    try:
                        self.analytics_db.insert_trade(trade_data)
                        logger.debug(f"✅ Trade loggé dans Analytics DB: {position.symbol}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur logging Analytics DB (sync): {e}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur logging Analytics DB: {e}")
        
        # 🔥 ARCHITECTURE V2: Notification position fermée
        if hasattr(self, 'notification_manager') and self.notification_manager:
            try:
                import asyncio
                
                # Créer une fonction wrapper async pour la notification
                async def _notify_position_closed_async():
                    try:
                        # 🔥 FIX: Envoyer toutes les données nécessaires pour éviter doublons
                        # Inclure closure_id, timestamp, et toutes les données du trade
                        await self.notification_manager.notify(
                            'position_closed',
                            {
                                'symbol': position.symbol,
                                'direction': position.direction,
                                'entry': position.entry,
                                'exit': exit_price,
                                'timestamp': result.get('timestamp', time.time() * 1000),  # Timestamp en millisecondes
                                'closure_id': result.get('closure_id'),  # 🔥 FIX: Inclure closure_id
                                'reason': reason,
                                'close_reason': reason,
                                'exit_reason': reason,
                                'net_pnl_pct': net_pnl_pct,
                                'net_pnl_usdt': net_pnl_usdt,
                                'gross_pnl_pct': result.get('gross_pnl_pct', net_pnl_pct),
                                'gross_pnl_usdt': result.get('gross_pnl_usdt', net_pnl_usdt),
                                'pnl_pct': net_pnl_pct,  # Alias pour compatibilité
                                'pnl_usdt': net_pnl_usdt,  # Alias pour compatibilité
                                'fees': result.get('fees', 0),
                                'slippage': result.get('slippage', 0),
                                'total_costs': result.get('total_costs', 0),
                                'duration': int(time.time() - position.start_time),
                                'duration_seconds': int(time.time() - position.start_time),
                                'has_partial_tp': result.get('has_partial_tp', False),
                                'size_closed': result.get('size_closed', position.size),
                                'size': position.size,
                                'result': {
                                    'exit_reason': reason,
                                    'pnl_pct': net_pnl_pct,
                                    'pnl_usdt': net_pnl_usdt,
                                    'duration_seconds': int(time.time() - position.start_time)
                                }
                            }
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur notification position fermée (async): {e}")
                
                # Créer la tâche sans attendre (fire-and-forget)
                try:
                    # Essayer d'obtenir le loop en cours
                    loop = asyncio.get_running_loop()
                    # Loop en cours, créer la tâche
                    asyncio.create_task(_notify_position_closed_async())
                except RuntimeError:
                    # Pas de loop en cours, exécuter dans un nouveau thread
                    try:
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(
                                lambda: asyncio.run(_notify_position_closed_async())
                            )
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur notification position fermée (thread): {e}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur notification position fermée: {e}")
        
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


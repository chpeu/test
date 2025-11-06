"""
🏗️ ABSTRACT TRADING MANAGER - Abstraction commune Paper/Backtest/Live
Architecture proposée par l'utilisateur - Template Method Pattern

Base commune pour :
- Paper Trading (simulation temps réel)
- Backtesting (données historiques)
- Live Trading (trading réel)

Évite duplication code (DRY Principle)
Garantit cohérence logique TP/SL/PnL entre tous les modes
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class TradingPosition:
    """Position de trading (commune à tous les modes)"""
    symbol: str
    direction: str  # 'LONG' ou 'SHORT'
    entry: float
    size: float
    sl: float
    tp: float
    
    # Indicateurs
    atr: Optional[float] = None
    atr5m: Optional[float] = None
    
    # Timestamps
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    start_time: float = field(default_factory=lambda: datetime.now().timestamp())
    
    # État
    break_even_set: bool = False
    partial_tp_sold: bool = False
    trailing_active: bool = False
    
    # TP Escalier
    tp_escalier_enabled: bool = False
    tp_escalier_levels: List[Dict] = field(default_factory=list)
    tp_escalier_current_level: int = 0
    tp_escalier_size_remaining: float = 1.0
    tp_escalier_profits: List[Dict] = field(default_factory=list)
    
    # Conditions détectées
    condition_types: List[str] = field(default_factory=list)
    
    # Scalability
    scalability_data: Optional[Dict] = None
    
    # Capital
    capital: Optional[float] = None
    size_remaining: Optional[float] = None
    partial_profit_usdt: float = 0.0
    
    # Metadata
    setup_id: Optional[int] = None
    config_hash: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convertir en dict"""
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'entry': self.entry,
            'size': self.size,
            'sl': self.sl,
            'tp': self.tp,
            'atr': self.atr,
            'atr5m': self.atr5m,
            'timestamp': self.timestamp,
            'start_time': self.start_time,
            'break_even_set': self.break_even_set,
            'partial_tp_sold': self.partial_tp_sold,
            'trailing_active': self.trailing_active,
            'tp_escalier_enabled': self.tp_escalier_enabled,
            'tp_escalier_current_level': self.tp_escalier_current_level,
            'tp_escalier_size_remaining': self.tp_escalier_size_remaining,
            'tp_escalier_profits': self.tp_escalier_profits,
            'condition_types': self.condition_types,
            'setup_id': self.setup_id
        }


class AbstractTradingManager(ABC):
    """
    Base abstraite pour tous les gestionnaires de trading
    
    Implémente la logique COMMUNE :
    - check_tp_sl() : Vérification TP/SL
    - calculate_pnl() : Calcul PnL
    - apply_fees_slippage() : Application frais/slippage
    - check_early_invalidation() : Invalidation précoce
    - update_trailing_stop() : Trailing stop
    
    Classes filles implémentent :
    - execute_order() : Exécution (API réelle vs simulation)
    - get_current_price() : Source prix (live vs historique)
    """
    
    def __init__(self, initial_capital: float = 1000.0):
        """
        Initialiser manager
        
        Args:
            initial_capital: Capital initial en USDT
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: List[TradingPosition] = []
        self.active_position: Optional[TradingPosition] = None
        self.closed_trades: List[Dict] = []
        
        # Config par défaut (peut être overridée)
        self.config = {
            'taker_fee': 0.0004,  # 0.04%
            'slippage_pct': 0.05,  # 0.05%
            'fixed_tp_pct': 0.6,
            'fixed_sl_pct': 0.25,
            'early_invalidation': {
                'enabled': True,
                'threshold_15s': -0.12,
                'threshold_30s': -0.08
            },
            'trailing_stop': {
                'enabled': True,
                'distance_pct': 0.15
            }
        }
        
        logger.info(f"✅ {self.__class__.__name__} initialisé | Capital: {initial_capital} USDT")
    
    # ==================== MÉTHODES COMMUNES (implémentées) ====================
    
    def check_tp_sl(self, position: TradingPosition, current_price: float) -> Optional[str]:
        """
        ✅ LOGIQUE COMMUNE : Vérifier si TP ou SL touché
        
        Args:
            position: Position à vérifier
            current_price: Prix actuel
        
        Returns:
            'TP', 'SL', 'TS' (Trailing Stop) ou None
        """
        direction = position.direction
        sl = position.sl
        tp = position.tp
        
        # Calculer PnL actuel
        pnl_pct = self.calculate_pnl_pct(position, current_price)
        
        # TP Escalier : Gestion spéciale
        if position.tp_escalier_enabled and position.tp_escalier_levels:
            # Si tous niveaux atteints, vérifier seulement SL
            if position.tp_escalier_current_level >= len(position.tp_escalier_levels):
                if direction == 'LONG':
                    return 'TS' if current_price <= sl else None
                else:  # SHORT
                    return 'TS' if current_price >= sl else None
            else:
                # Niveaux restants, vérifier seulement SL
                has_profits = len(position.tp_escalier_profits) > 0
                if direction == 'LONG':
                    if current_price <= sl:
                        return 'TS' if (has_profits or pnl_pct >= 0) else 'SL'
                else:  # SHORT
                    if current_price >= sl:
                        return 'TS' if (has_profits or pnl_pct >= 0) else 'SL'
                return None
        
        # Mode standard
        if direction == 'LONG':
            if current_price >= tp:
                return 'TP'
            elif current_price <= sl:
                # Trailing stop si profit ou BE activé
                return 'TS' if (pnl_pct > 0 or position.break_even_set) else 'SL'
        else:  # SHORT
            if current_price <= tp:
                return 'TP'
            elif current_price >= sl:
                return 'TS' if (pnl_pct > 0 or position.break_even_set) else 'SL'
        
        return None
    
    def calculate_pnl_pct(self, position: TradingPosition, exit_price: float) -> float:
        """
        ✅ LOGIQUE COMMUNE : Calculer PnL en %
        
        Args:
            position: Position
            exit_price: Prix de sortie
        
        Returns:
            PnL en % (brut, sans fees/slippage)
        """
        entry = position.entry
        direction = position.direction
        
        if direction == 'LONG':
            pnl_pct = ((exit_price - entry) / entry) * 100
        else:  # SHORT
            pnl_pct = ((entry - exit_price) / entry) * 100
        
        return pnl_pct
    
    def calculate_pnl(self, position: TradingPosition, exit_price: float) -> Dict:
        """
        ✅ LOGIQUE COMMUNE : Calculer PnL complet (avec fees, slippage, TP Escalier)
        
        Args:
            position: Position
            exit_price: Prix de sortie
        
        Returns:
            Dict avec gross_pnl_pct, net_pnl_pct, fees, slippage, etc.
        """
        entry = position.entry
        direction = position.direction
        size = position.size
        
        # TP Escalier : PnL cumulé
        if position.tp_escalier_enabled and position.tp_escalier_profits:
            tp_escalier_profits_usdt = sum(p['profit_usdt'] for p in position.tp_escalier_profits)
            size_to_close = size * position.tp_escalier_size_remaining
            
            # PnL final partie restante
            if direction == 'LONG':
                price_diff = exit_price - entry
            else:
                price_diff = entry - exit_price
            
            final_profit_usdt = size_to_close * (price_diff / entry) if size_to_close > 0 else 0
            gross_pnl_usdt = tp_escalier_profits_usdt + final_profit_usdt
            gross_pnl_pct = (gross_pnl_usdt / size) * 100
        
        # Position partielle (mode standard)
        elif position.partial_tp_sold and position.size_remaining:
            size_to_close = position.size_remaining
            
            if direction == 'LONG':
                price_diff = exit_price - entry
            else:
                price_diff = entry - exit_price
            
            final_profit_usdt = size_to_close * (price_diff / entry)
            gross_pnl_usdt = position.partial_profit_usdt + final_profit_usdt
            gross_pnl_pct = (gross_pnl_usdt / size) * 100
        
        # Position complète
        else:
            if direction == 'LONG':
                price_diff = exit_price - entry
            else:
                price_diff = entry - exit_price
            
            gross_pnl_usdt = size * (price_diff / entry)
            gross_pnl_pct = (gross_pnl_usdt / size) * 100
        
        # Appliquer fees & slippage
        fees_pct = self.config['taker_fee'] * 100
        slippage_pct = self.config['slippage_pct']
        
        # Doubler si TP partiel (entrée + sortie partielle + sortie finale)
        multiplier = 2 if position.partial_tp_sold else 1
        
        fees_usdt = size * (fees_pct / 100) * multiplier
        slippage_usdt = size * (slippage_pct / 100) * multiplier
        total_costs_usdt = fees_usdt + slippage_usdt
        
        net_pnl_usdt = gross_pnl_usdt - total_costs_usdt
        net_pnl_pct = (net_pnl_usdt / size) * 100
        
        return {
            'gross_pnl_pct': gross_pnl_pct,
            'gross_pnl_usdt': gross_pnl_usdt,
            'net_pnl_pct': net_pnl_pct,
            'net_pnl_usdt': net_pnl_usdt,
            'fees': fees_pct,
            'slippage': slippage_pct,
            'fees_usdt': fees_usdt,
            'slippage_usdt': slippage_usdt,
            'total_costs': total_costs_usdt
        }
    
    def apply_fees_slippage(self, price: float, direction: str, order_type: str = 'MARKET') -> float:
        """
        ✅ LOGIQUE COMMUNE : Appliquer fees + slippage au prix
        
        Args:
            price: Prix nominal
            direction: 'BUY' ou 'SELL'
            order_type: 'MARKET' ou 'LIMIT'
        
        Returns:
            Prix ajusté
        """
        slippage_pct = self.config['slippage_pct']
        
        if direction == 'BUY':
            # Acheter coûte plus cher (slippage positif)
            adjusted_price = price * (1 + slippage_pct / 100)
        else:  # SELL
            # Vendre rapporte moins (slippage négatif)
            adjusted_price = price * (1 - slippage_pct / 100)
        
        return adjusted_price
    
    def check_early_invalidation(self, position: TradingPosition, current_price: float) -> bool:
        """
        ✅ LOGIQUE COMMUNE : Vérifier invalidation précoce (30s)
        
        Args:
            position: Position
            current_price: Prix actuel
        
        Returns:
            True si invalider, False sinon
        """
        if not self.config['early_invalidation']['enabled']:
            return False
        
        elapsed = time.time() - position.start_time
        
        # Seulement dans les 30 premières secondes
        if elapsed > 30:
            return False
        
        # Calculer PnL actuel
        pnl_pct = self.calculate_pnl_pct(position, current_price)
        
        # Seuils selon temps écoulé
        if elapsed <= 15:
            threshold = self.config['early_invalidation']['threshold_15s']
        else:  # 15-30s
            threshold = self.config['early_invalidation']['threshold_30s']
        
        # Invalider si perte dépasse seuil
        if pnl_pct < threshold:
            logger.info(f"⚡ Early invalidation: PnL {pnl_pct:.2f}% < {threshold:.2f}% @ {elapsed:.0f}s")
            return True
        
        return False
    
    def update_trailing_stop(self, position: TradingPosition, current_price: float):
        """
        ✅ LOGIQUE COMMUNE : Mettre à jour trailing stop
        
        Args:
            position: Position
            current_price: Prix actuel
        """
        if not self.config['trailing_stop']['enabled']:
            return
        
        distance_pct = self.config['trailing_stop']['distance_pct']
        direction = position.direction
        
        # Calculer nouveau SL
        if direction == 'LONG':
            new_sl = current_price * (1 - distance_pct / 100)
            # Seulement si monte
            if new_sl > position.sl:
                old_sl = position.sl
                position.sl = new_sl
                position.trailing_active = True
                logger.debug(f"📈 Trailing SL LONG: {old_sl:.6f} → {new_sl:.6f}")
        else:  # SHORT
            new_sl = current_price * (1 + distance_pct / 100)
            # Seulement si descend
            if new_sl < position.sl:
                old_sl = position.sl
                position.sl = new_sl
                position.trailing_active = True
                logger.debug(f"📉 Trailing SL SHORT: {old_sl:.6f} → {new_sl:.6f}")
    
    def update_break_even(self, position: TradingPosition, current_price: float):
        """
        ✅ LOGIQUE COMMUNE : Mettre à jour break-even
        
        Args:
            position: Position
            current_price: Prix actuel
        """
        if position.break_even_set:
            return
        
        # Calculer PnL actuel
        pnl_pct = self.calculate_pnl_pct(position, current_price)
        
        # Activer BE à +0.3%
        if pnl_pct >= 0.3:
            position.sl = position.entry
            position.break_even_set = True
            logger.info(f"🛡️ Break-even activé @ {pnl_pct:.2f}% | SL → Entry ({position.entry:.6f})")
    
    # ==================== HOOKS OPTIONNELS (peuvent être overridés) ====================
    
    def on_position_opened(self, position: TradingPosition):
        """
        Hook après ouverture position (optionnel)
        
        Peut être overridé par classes filles pour :
        - Paper Trading → logger
        - Backtesting → collecter stats
        - Live → notifier Telegram
        """
        logger.info(f"🟢 Position ouverte: {position.symbol} {position.direction} @ {position.entry:.6f}")
    
    def on_position_closed(self, position: TradingPosition, result: Dict):
        """
        Hook après fermeture position (optionnel)
        
        Peut être overridé par classes filles
        """
        logger.info(
            f"🔴 Position fermée: {position.symbol} | "
            f"PnL: {result['net_pnl_pct']:+.2f}% ({result['net_pnl_usdt']:+.2f} USDT) | "
            f"Raison: {result.get('reason')}"
        )
    
    def on_tick(self, timestamp: float, prices: Dict[str, float]):
        """
        Hook sur chaque tick (optionnel)
        
        Peut être overridé pour analytics temps réel
        """
        pass
    
    # ==================== MÉTHODES ABSTRAITES (doivent être implémentées) ====================
    
    @abstractmethod
    def execute_order(self, order: Dict) -> Dict:
        """
        Exécuter un ordre (ABSTRAIT - implémenté par classes filles)
        
        Args:
            order: {'type': 'BUY'/'SELL', 'symbol': ..., 'size': ...}
        
        Returns:
            {'executed': True/False, 'price': ..., 'timestamp': ...}
        """
        pass
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """
        Obtenir prix actuel (ABSTRAIT - implémenté par classes filles)
        
        Args:
            symbol: Symbole (ex: 'BTC/USDT:USDT')
        
        Returns:
            Prix actuel
        """
        pass
    
    # ==================== MÉTHODES PUBLIQUES ====================
    
    def open_position(
        self,
        symbol: str,
        direction: str,
        entry: float,
        size: float,
        sl: float,
        tp: float,
        **kwargs
    ) -> TradingPosition:
        """
        Ouvrir une position
        
        Args:
            symbol: Symbole
            direction: 'LONG' ou 'SHORT'
            entry: Prix d'entrée
            size: Taille en USDT
            sl: Stop Loss
            tp: Take Profit
            **kwargs: Autres paramètres (atr, condition_types, etc.)
        
        Returns:
            TradingPosition créée
        """
        # Créer position
        position = TradingPosition(
            symbol=symbol,
            direction=direction,
            entry=entry,
            size=size,
            sl=sl,
            tp=tp,
            **{k: v for k, v in kwargs.items() if k in TradingPosition.__dataclass_fields__}
        )
        
        # Enregistrer
        self.active_position = position
        self.positions.append(position)
        
        # Hook
        self.on_position_opened(position)
        
        return position
    
    def close_position(self, reason: str, exit_price: Optional[float] = None) -> Dict:
        """
        Fermer la position active
        
        Args:
            reason: Raison ('TP', 'SL', 'EARLY_INVALIDATION', etc.)
            exit_price: Prix de sortie (si None, utilise current_price)
        
        Returns:
            Résultat du trade
        """
        if not self.active_position:
            logger.warning("⚠️ Aucune position active à fermer")
            return {}
        
        position = self.active_position
        
        # Déterminer prix de sortie
        if exit_price is None:
            exit_price = self.get_current_price(position.symbol)
        
        # Calculer PnL
        pnl_result = self.calculate_pnl(position, exit_price)
        
        # Durée
        duration = int(time.time() - position.start_time)
        
        # Construire résultat
        result = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'symbol': position.symbol,
            'direction': position.direction,
            'entry': position.entry,
            'exit': exit_price,
            'reason': reason,
            'duration': duration,
            **pnl_result,
            'condition_types': position.condition_types,
            'tp_escalier_enabled': position.tp_escalier_enabled,
            'tp_escalier_profits': position.tp_escalier_profits,
            'break_even_triggered': position.break_even_set,
            'trailing_stop_triggered': position.trailing_active,
            'partial_tp_triggered': position.partial_tp_sold
        }
        
        # Mettre à jour capital
        self.capital += pnl_result['net_pnl_usdt']
        
        # Enregistrer
        self.closed_trades.append(result)
        
        # Reset position active
        self.active_position = None
        
        # Hook
        self.on_position_closed(position, result)
        
        return result
    
    def get_stats(self) -> Dict:
        """
        Statistiques globales
        
        Returns:
            Dict avec total_trades, winrate, profit_factor, etc.
        """
        if not self.closed_trades:
            return {
                'total_trades': 0,
                'winrate': 0,
                'profit_factor': 0,
                'total_pnl': 0,
                'capital': self.capital
            }
        
        total_trades = len(self.closed_trades)
        wins = sum(1 for t in self.closed_trades if t['net_pnl_pct'] > 0)
        losses = total_trades - wins
        winrate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        total_profit = sum(t['net_pnl_usdt'] for t in self.closed_trades if t['net_pnl_usdt'] > 0)
        total_loss = abs(sum(t['net_pnl_usdt'] for t in self.closed_trades if t['net_pnl_usdt'] < 0))
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        
        total_pnl = sum(t['net_pnl_usdt'] for t in self.closed_trades)
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'winrate': winrate,
            'profit_factor': profit_factor,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'total_pnl': total_pnl,
            'capital': self.capital,
            'roi': ((self.capital - self.initial_capital) / self.initial_capital * 100)
        }


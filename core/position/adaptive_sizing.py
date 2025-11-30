#!/usr/bin/env python3
"""
📊 ADAPTIVE SIZING PAR PAIRE/SESSION
=====================================
Ajuste la taille des positions en fonction du winrate 
en temps réel sur la session en cours pour chaque paire.

Logique:
- Trades 1-2: Taille nominale (100%)
- Si WR >= 75% après 3+ trades: Boost progressif jusqu'à 150%
- Si WR <= 40%: Réduction jusqu'à 50%
- Reset à chaque nouvelle session (ou manuellement)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PairSessionStats:
    """Statistiques d'une paire sur la session en cours"""
    symbol: str
    session_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trades: List[Dict] = field(default_factory=list)
    wins: int = 0
    losses: int = 0
    total_pnl_pct: float = 0.0
    
    @property
    def total_trades(self) -> int:
        return self.wins + self.losses
    
    @property
    def winrate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.wins / self.total_trades
    
    @property
    def avg_pnl(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl_pct / self.total_trades


def load_adaptive_sizing_config() -> 'AdaptiveSizingConfig':
    """Charge la configuration depuis TRADING_CONFIG"""
    try:
        from config import TRADING_CONFIG
        return AdaptiveSizingConfig(
            enabled=TRADING_CONFIG.get('adaptive_sizing_enabled', True),
            min_trades_for_adjustment=TRADING_CONFIG.get('adaptive_sizing_min_trades', 3),
            excellent_wr_threshold=TRADING_CONFIG.get('adaptive_sizing_excellent_wr', 0.75),
            good_wr_threshold=TRADING_CONFIG.get('adaptive_sizing_good_wr', 0.60),
            poor_wr_threshold=TRADING_CONFIG.get('adaptive_sizing_poor_wr', 0.40),
            very_poor_wr_threshold=TRADING_CONFIG.get('adaptive_sizing_very_poor_wr', 0.30),
            excellent_multiplier=TRADING_CONFIG.get('adaptive_sizing_excellent_mult', 1.50),
            good_multiplier=TRADING_CONFIG.get('adaptive_sizing_good_mult', 1.25),
            normal_multiplier=1.00,  # Fixe: zone neutre = pas d'ajustement
            poor_multiplier=TRADING_CONFIG.get('adaptive_sizing_poor_mult', 0.70),
            very_poor_multiplier=TRADING_CONFIG.get('adaptive_sizing_very_poor_mult', 0.50),
            max_multiplier=TRADING_CONFIG.get('adaptive_sizing_max_mult', 1.50),
            min_multiplier=TRADING_CONFIG.get('adaptive_sizing_min_mult', 0.50),
            auto_reset_hours=TRADING_CONFIG.get('adaptive_sizing_reset_hours', 8),
            reset_after_big_loss=TRADING_CONFIG.get('adaptive_sizing_reset_big_loss', True),
            big_loss_threshold=TRADING_CONFIG.get('adaptive_sizing_big_loss_threshold', -2.0),
        )
    except Exception as e:
        logger.warning(f"⚠️ Erreur chargement config adaptive sizing: {e}, utilisation défauts")
        return AdaptiveSizingConfig()


@dataclass
class AdaptiveSizingConfig:
    """Configuration du sizing adaptatif - Chargée depuis TRADING_CONFIG"""
    enabled: bool = True
    
    # Seuils de performance (configurables via UI)
    min_trades_for_adjustment: int = 3  # Minimum trades avant ajustement
    excellent_wr_threshold: float = 0.75  # WR >= 75% = excellent
    good_wr_threshold: float = 0.60      # WR >= 60% = bon
    poor_wr_threshold: float = 0.40      # WR <= 40% = mauvais
    very_poor_wr_threshold: float = 0.30 # WR <= 30% = très mauvais
    
    # Multiplicateurs de taille (configurables via UI)
    excellent_multiplier: float = 1.50   # +50% si excellent
    good_multiplier: float = 1.25        # +25% si bon  
    normal_multiplier: float = 1.00      # Normal
    poor_multiplier: float = 0.70        # -30% si mauvais
    very_poor_multiplier: float = 0.50   # -50% si très mauvais
    
    # Limites de sécurité (configurables via UI)
    max_multiplier: float = 1.50         # Jamais plus de +50%
    min_multiplier: float = 0.50         # Jamais moins de -50%
    
    # Progression graduelle (évite les sauts brutaux)
    gradual_increase: bool = True
    increase_step: float = 0.10          # +10% par trade gagnant consécutif
    decrease_step: float = 0.15          # -15% par trade perdant consécutif
    
    # Reset automatique (configurables via UI)
    auto_reset_hours: int = 8            # Reset après 8h d'inactivité
    reset_after_big_loss: bool = True    # Reset si perte > seuil
    big_loss_threshold: float = -2.0     # Seuil de "grosse perte" en %


class AdaptiveSizingManager:
    """
    Gestionnaire de sizing adaptatif par paire
    
    Usage:
        manager = AdaptiveSizingManager()
        
        # Avant ouverture de position
        multiplier = manager.get_size_multiplier("BTC/USDT")
        final_size = base_size * multiplier
        
        # Après fermeture de position
        manager.record_trade("BTC/USDT", pnl_pct=0.35, is_win=True)
    """
    
    def __init__(self, config: Optional[AdaptiveSizingConfig] = None):
        # Charger config depuis TRADING_CONFIG si non fournie
        self.config = config or load_adaptive_sizing_config()
        self.pair_stats: Dict[str, PairSessionStats] = {}
        self._consecutive_results: Dict[str, List[bool]] = {}  # Pour progression graduelle
        logger.info(f"📊 AdaptiveSizingManager initialisé (enabled={self.config.enabled})")
        
    def _get_or_create_stats(self, symbol: str) -> PairSessionStats:
        """Récupère ou crée les stats pour une paire"""
        if symbol not in self.pair_stats:
            self.pair_stats[symbol] = PairSessionStats(symbol=symbol)
            self._consecutive_results[symbol] = []
            logger.info(f"📊 Nouvelle session de sizing adaptatif pour {symbol}")
        
        stats = self.pair_stats[symbol]
        
        # Vérifier si reset automatique nécessaire
        if self.config.auto_reset_hours > 0:
            hours_inactive = (datetime.now(timezone.utc) - stats.session_start).total_seconds() / 3600
            if hours_inactive > self.config.auto_reset_hours and stats.total_trades > 0:
                logger.info(f"🔄 Reset auto sizing {symbol} après {hours_inactive:.1f}h d'inactivité")
                self.reset_pair(symbol)
                stats = self.pair_stats[symbol]
        
        return stats
    
    def get_size_multiplier(self, symbol: str) -> float:
        """
        Calcule le multiplicateur de taille pour une paire
        
        Args:
            symbol: Symbole de la paire (ex: "BTC/USDT")
            
        Returns:
            Multiplicateur (0.5 à 1.5)
        """
        if not self.config.enabled:
            return 1.0
        
        stats = self._get_or_create_stats(symbol)
        
        # Pas assez de trades pour ajuster
        if stats.total_trades < self.config.min_trades_for_adjustment:
            logger.debug(f"📊 {symbol}: {stats.total_trades} trades, trop tôt pour ajuster (min: {self.config.min_trades_for_adjustment})")
            return self.config.normal_multiplier
        
        wr = stats.winrate
        
        # Calcul du multiplicateur basé sur WR (utilise seuils configurables)
        if wr >= self.config.excellent_wr_threshold:
            base_mult = self.config.excellent_multiplier
            level = "🔥 EXCELLENT"
        elif wr >= self.config.good_wr_threshold:
            base_mult = self.config.good_multiplier
            level = "✅ BON"
        elif wr <= self.config.very_poor_wr_threshold:
            base_mult = self.config.very_poor_multiplier
            level = "❌ TRÈS MAUVAIS"
        elif wr <= self.config.poor_wr_threshold:
            base_mult = self.config.poor_multiplier
            level = "⚠️ MAUVAIS"
        else:
            base_mult = self.config.normal_multiplier
            level = "➖ NORMAL"
        
        # Ajustement graduel si activé
        if self.config.gradual_increase:
            base_mult = self._apply_gradual_adjustment(symbol, base_mult)
        
        # Appliquer limites de sécurité
        final_mult = max(self.config.min_multiplier, min(self.config.max_multiplier, base_mult))
        
        logger.info(
            f"📊 SIZING {symbol}: WR={wr:.0%} ({stats.wins}W/{stats.losses}L) "
            f"→ {level} → Multiplicateur: {final_mult:.0%}"
        )
        
        return final_mult
    
    def _apply_gradual_adjustment(self, symbol: str, base_mult: float) -> float:
        """Applique ajustement graduel basé sur résultats consécutifs"""
        consecutive = self._consecutive_results.get(symbol, [])
        
        if len(consecutive) < 2:
            return base_mult
        
        # Compter résultats consécutifs récents
        recent = consecutive[-5:]  # 5 derniers trades
        consecutive_wins = 0
        consecutive_losses = 0
        
        for result in reversed(recent):
            if result:  # Win
                if consecutive_losses > 0:
                    break
                consecutive_wins += 1
            else:  # Loss
                if consecutive_wins > 0:
                    break
                consecutive_losses += 1
        
        # Ajustement
        if consecutive_wins >= 2:
            adjustment = min(consecutive_wins - 1, 3) * self.config.increase_step
            return base_mult + adjustment
        elif consecutive_losses >= 2:
            adjustment = min(consecutive_losses - 1, 3) * self.config.decrease_step
            return base_mult - adjustment
        
        return base_mult
    
    def record_trade(self, symbol: str, pnl_pct: float, is_win: bool):
        """
        Enregistre le résultat d'un trade
        
        Args:
            symbol: Symbole de la paire
            pnl_pct: PnL en pourcentage
            is_win: True si trade gagnant
        """
        stats = self._get_or_create_stats(symbol)
        
        # Enregistrer
        stats.trades.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'pnl_pct': pnl_pct,
            'is_win': is_win
        })
        
        if is_win:
            stats.wins += 1
        else:
            stats.losses += 1
        
        stats.total_pnl_pct += pnl_pct
        
        # Tracker résultats consécutifs
        if symbol not in self._consecutive_results:
            self._consecutive_results[symbol] = []
        self._consecutive_results[symbol].append(is_win)
        
        # Reset si grosse perte
        if self.config.reset_after_big_loss and pnl_pct <= self.config.big_loss_threshold:
            logger.warning(f"💥 Grosse perte sur {symbol} ({pnl_pct:.2f}%), reset sizing")
            self.reset_pair(symbol)
            return
        
        logger.info(
            f"📊 Trade enregistré {symbol}: {'WIN' if is_win else 'LOSS'} {pnl_pct:+.2f}% | "
            f"Session: {stats.wins}W/{stats.losses}L = {stats.winrate:.0%} WR"
        )
    
    def reset_pair(self, symbol: str):
        """Reset les stats d'une paire"""
        self.pair_stats[symbol] = PairSessionStats(symbol=symbol)
        self._consecutive_results[symbol] = []
        logger.info(f"🔄 Stats sizing reset pour {symbol}")
    
    def reset_all(self):
        """Reset toutes les paires"""
        self.pair_stats.clear()
        self._consecutive_results.clear()
        logger.info("🔄 Stats sizing reset pour TOUTES les paires")
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Retourne les stats de toutes les paires pour affichage"""
        result = {}
        for symbol, stats in self.pair_stats.items():
            result[symbol] = {
                'symbol': symbol,
                'session_start': stats.session_start.isoformat(),
                'total_trades': stats.total_trades,
                'wins': stats.wins,
                'losses': stats.losses,
                'winrate': stats.winrate,
                'total_pnl_pct': stats.total_pnl_pct,
                'avg_pnl': stats.avg_pnl,
                'current_multiplier': self.get_size_multiplier(symbol)
            }
        return result
    
    def reload_config(self):
        """Recharge la configuration depuis TRADING_CONFIG (après modification UI)"""
        self.config = load_adaptive_sizing_config()
        logger.info(f"🔄 Configuration adaptive sizing rechargée")
    
    def get_config_dict(self) -> Dict:
        """Retourne la configuration actuelle pour l'UI"""
        return {
            'enabled': self.config.enabled,
            'min_trades': self.config.min_trades_for_adjustment,
            'thresholds': {
                'excellent_wr': self.config.excellent_wr_threshold,
                'good_wr': self.config.good_wr_threshold,
                'poor_wr': self.config.poor_wr_threshold,
                'very_poor_wr': self.config.very_poor_wr_threshold,
            },
            'multipliers': {
                'excellent': self.config.excellent_multiplier,
                'good': self.config.good_multiplier,
                'normal': self.config.normal_multiplier,
                'poor': self.config.poor_multiplier,
                'very_poor': self.config.very_poor_multiplier,
            },
            'limits': {
                'max': self.config.max_multiplier,
                'min': self.config.min_multiplier,
            },
            'reset': {
                'hours': self.config.auto_reset_hours,
                'on_big_loss': self.config.reset_after_big_loss,
                'big_loss_threshold': self.config.big_loss_threshold,
            }
        }


# Singleton global
_adaptive_sizing_manager: Optional[AdaptiveSizingManager] = None


def get_adaptive_sizing_manager() -> AdaptiveSizingManager:
    """Récupère l'instance singleton du manager"""
    global _adaptive_sizing_manager
    if _adaptive_sizing_manager is None:
        _adaptive_sizing_manager = AdaptiveSizingManager()
    return _adaptive_sizing_manager


def reset_adaptive_sizing_manager():
    """Reset le manager (utile pour tests)"""
    global _adaptive_sizing_manager
    _adaptive_sizing_manager = None

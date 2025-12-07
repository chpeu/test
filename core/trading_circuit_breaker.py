"""
Trading Circuit Breaker - Sprint 1
Protection du capital: pause trading après pertes consécutives ou drawdown.

Différent du Circuit Breaker API (pour erreurs 429/500) dans live_order_manager.

Auteur: Cascade AI
Date: 07/12/2025
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """États du circuit breaker"""
    ACTIVE = "ACTIVE"      # Trading autorisé
    PAUSED = "PAUSED"      # Pause temporaire
    STOPPED = "STOPPED"    # Arrêt jusqu'à reset manuel


@dataclass
class TradeResult:
    """Résultat d'un trade pour le circuit breaker"""
    timestamp: datetime
    symbol: str
    pnl_pct: float
    pnl_usdt: float
    is_win: bool


@dataclass
class CircuitBreakerEvent:
    """Événement du circuit breaker"""
    timestamp: datetime
    event_type: str  # "pause", "resume", "stop", "reset"
    reason: str
    state_before: str
    state_after: str
    metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "reason": self.reason,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "metrics": self.metrics
        }


class TradingCircuitBreaker:
    """
    Circuit Breaker pour protéger le capital trading.
    
    Règles:
    1. Pause après N pertes consécutives
    2. Pause si drawdown journalier dépasse seuil
    3. Arrêt si drawdown critique
    4. Boost score requis après pertes (progressif)
    5. Cooldown avant reprise
    """
    
    def __init__(
        self,
        max_consecutive_losses: int = 5,
        daily_drawdown_pause_pct: float = -2.0,
        daily_drawdown_stop_pct: float = -5.0,
        pause_duration_minutes: int = 30,
        score_boost_per_loss: float = 0.5,
        max_score_boost: float = 2.0
    ):
        """
        Initialise le circuit breaker trading.
        
        Args:
            max_consecutive_losses: Pertes consécutives avant pause
            daily_drawdown_pause_pct: Drawdown journalier pour pause (ex: -2.0 = -2%)
            daily_drawdown_stop_pct: Drawdown journalier pour arrêt (ex: -5.0 = -5%)
            pause_duration_minutes: Durée de la pause en minutes
            score_boost_per_loss: Augmentation score requis par perte consécutive
            max_score_boost: Boost maximum du score
        """
        # Configuration
        self.max_consecutive_losses = max_consecutive_losses
        self.daily_drawdown_pause_pct = daily_drawdown_pause_pct
        self.daily_drawdown_stop_pct = daily_drawdown_stop_pct
        self.pause_duration = timedelta(minutes=pause_duration_minutes)
        self.score_boost_per_loss = score_boost_per_loss
        self.max_score_boost = max_score_boost
        
        # État
        self.state = CircuitBreakerState.ACTIVE
        self.consecutive_losses = 0
        self.daily_pnl_pct = 0.0
        self.daily_pnl_usdt = 0.0
        self.daily_trades = 0
        self.daily_wins = 0
        self.daily_losses = 0
        
        # Timing
        self.paused_until: Optional[datetime] = None
        self.pause_reason: Optional[str] = None
        self.last_trade_time: Optional[datetime] = None
        self.day_start: datetime = self._get_day_start()
        
        # Historique
        self.trade_history: List[TradeResult] = []
        self.events: List[CircuitBreakerEvent] = []
        self.max_history_size = 100
        
        # Callbacks
        self._on_state_change_callbacks: List[Callable] = []
        
        logger.info(
            f"✅ TradingCircuitBreaker initialisé | "
            f"Max losses: {max_consecutive_losses} | "
            f"Pause DD: {daily_drawdown_pause_pct}% | "
            f"Stop DD: {daily_drawdown_stop_pct}%"
        )
    
    def update_config(
        self,
        max_consecutive_losses: Optional[int] = None,
        daily_drawdown_pause_pct: Optional[float] = None,
        daily_drawdown_stop_pct: Optional[float] = None,
        pause_duration_minutes: Optional[int] = None,
        score_boost_per_loss: Optional[float] = None
    ) -> None:
        """
        🔥 FIX: Met à jour la configuration à chaud sans recréer l'instance.
        
        Args:
            max_consecutive_losses: Nouvelle valeur (None = pas de changement)
            daily_drawdown_pause_pct: Nouvelle valeur
            daily_drawdown_stop_pct: Nouvelle valeur
            pause_duration_minutes: Nouvelle valeur
            score_boost_per_loss: Nouvelle valeur
        """
        if max_consecutive_losses is not None:
            self.max_consecutive_losses = max_consecutive_losses
            logger.info(f"🔄 CB: max_consecutive_losses → {max_consecutive_losses}")
        
        if daily_drawdown_pause_pct is not None:
            self.daily_drawdown_pause_pct = daily_drawdown_pause_pct
            logger.info(f"🔄 CB: daily_drawdown_pause_pct → {daily_drawdown_pause_pct}%")
        
        if daily_drawdown_stop_pct is not None:
            self.daily_drawdown_stop_pct = daily_drawdown_stop_pct
            logger.info(f"🔄 CB: daily_drawdown_stop_pct → {daily_drawdown_stop_pct}%")
        
        if pause_duration_minutes is not None:
            self.pause_duration = timedelta(minutes=pause_duration_minutes)
            logger.info(f"🔄 CB: pause_duration → {pause_duration_minutes}min")
        
        if score_boost_per_loss is not None:
            self.score_boost_per_loss = score_boost_per_loss
            logger.info(f"🔄 CB: score_boost_per_loss → {score_boost_per_loss}")
    
    def _get_day_start(self) -> datetime:
        """Retourne le début du jour courant (minuit UTC)"""
        now = datetime.utcnow()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def _check_day_reset(self) -> None:
        """Vérifie si on doit réinitialiser les stats journalières"""
        current_day_start = self._get_day_start()
        if current_day_start > self.day_start:
            logger.info("🔄 Nouveau jour détecté - Reset stats journalières")
            self.day_start = current_day_start
            self.daily_pnl_pct = 0.0
            self.daily_pnl_usdt = 0.0
            self.daily_trades = 0
            self.daily_wins = 0
            self.daily_losses = 0
            self.trade_history.clear()
            
            # Si on était en pause journalière, reprendre
            if self.state == CircuitBreakerState.PAUSED and self.pause_reason:
                if "drawdown" in self.pause_reason.lower():
                    self._change_state(
                        CircuitBreakerState.ACTIVE,
                        "reset",
                        "Nouveau jour - reprise automatique"
                    )
    
    def on_state_change(self, callback: Callable) -> None:
        """Enregistre un callback pour les changements d'état"""
        self._on_state_change_callbacks.append(callback)
    
    def _change_state(
        self,
        new_state: CircuitBreakerState,
        event_type: str,
        reason: str
    ) -> None:
        """Change l'état et notifie les callbacks"""
        old_state = self.state
        self.state = new_state
        
        # Enregistrer l'événement
        event = CircuitBreakerEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            reason=reason,
            state_before=old_state.value,
            state_after=new_state.value,
            metrics={
                "consecutive_losses": self.consecutive_losses,
                "daily_pnl_pct": self.daily_pnl_pct,
                "daily_trades": self.daily_trades,
                "score_boost": self.get_score_boost()
            }
        )
        self.events.append(event)
        
        if len(self.events) > self.max_history_size:
            self.events = self.events[-self.max_history_size:]
        
        logger.warning(
            f"🛑 Circuit Breaker: {old_state.value} → {new_state.value} | {reason}"
        )
        
        # 🔥 SPRINT 1: Logger dans circuit_breaker_events
        self._log_event_to_db(event)
        
        # Notifier les callbacks
        for callback in self._on_state_change_callbacks:
            try:
                callback(old_state.value, new_state.value, reason)
            except Exception as e:
                logger.error(f"❌ Erreur callback CB: {e}")
    
    def record_trade(
        self,
        symbol: str,
        pnl_pct: float,
        pnl_usdt: float
    ) -> bool:
        """
        Enregistre un trade terminé et évalue l'état du circuit breaker.
        
        Args:
            symbol: Paire tradée
            pnl_pct: PnL en pourcentage
            pnl_usdt: PnL en USDT
            
        Returns:
            True si le trading reste autorisé, False sinon
        """
        self._check_day_reset()
        
        now = datetime.now()
        is_win = pnl_pct > 0
        
        # Enregistrer le trade
        trade = TradeResult(
            timestamp=now,
            symbol=symbol,
            pnl_pct=pnl_pct,
            pnl_usdt=pnl_usdt,
            is_win=is_win
        )
        self.trade_history.append(trade)
        
        if len(self.trade_history) > self.max_history_size:
            self.trade_history = self.trade_history[-self.max_history_size:]
        
        # Mettre à jour les stats
        self.last_trade_time = now
        self.daily_trades += 1
        self.daily_pnl_pct += pnl_pct
        self.daily_pnl_usdt += pnl_usdt
        
        if is_win:
            self.daily_wins += 1
            self.consecutive_losses = 0
        else:
            self.daily_losses += 1
            self.consecutive_losses += 1
        
        logger.debug(
            f"📊 Trade enregistré: {symbol} | PnL: {pnl_pct:+.2f}% | "
            f"Consec losses: {self.consecutive_losses} | Daily: {self.daily_pnl_pct:+.2f}%"
        )
        
        # Évaluer les conditions de pause/arrêt
        return self._evaluate_conditions()
    
    def _evaluate_conditions(self) -> bool:
        """Évalue les conditions et déclenche pause/arrêt si nécessaire"""
        
        # 1. Vérifier pertes consécutives
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.paused_until = datetime.now() + self.pause_duration
            self.pause_reason = f"{self.consecutive_losses} pertes consécutives"
            self._change_state(
                CircuitBreakerState.PAUSED,
                "pause",
                self.pause_reason
            )
            return False
        
        # 2. Vérifier drawdown journalier critique (STOP)
        if self.daily_pnl_pct <= self.daily_drawdown_stop_pct:
            self.pause_reason = f"Drawdown critique: {self.daily_pnl_pct:.2f}%"
            self._change_state(
                CircuitBreakerState.STOPPED,
                "stop",
                self.pause_reason
            )
            return False
        
        # 3. Vérifier drawdown journalier pause
        if self.daily_pnl_pct <= self.daily_drawdown_pause_pct:
            self.paused_until = datetime.now() + self.pause_duration
            self.pause_reason = f"Drawdown journalier: {self.daily_pnl_pct:.2f}%"
            self._change_state(
                CircuitBreakerState.PAUSED,
                "pause",
                self.pause_reason
            )
            return False
        
        return True
    
    def can_trade(self) -> bool:
        """
        Vérifie si le trading est autorisé.
        Gère aussi la reprise automatique après pause.
        """
        self._check_day_reset()
        
        if self.state == CircuitBreakerState.STOPPED:
            return False
        
        if self.state == CircuitBreakerState.PAUSED:
            now = datetime.now()
            if self.paused_until and now >= self.paused_until:
                # Pause terminée, reprendre
                self._change_state(
                    CircuitBreakerState.ACTIVE,
                    "resume",
                    "Pause terminée - reprise automatique"
                )
                self.paused_until = None
                self.pause_reason = None
                # Garder consecutive_losses pour le score boost
                return True
            return False
        
        return True
    
    def get_score_boost(self) -> float:
        """
        Retourne le boost à appliquer au score minimum requis.
        Augmente progressivement après des pertes.
        """
        if self.consecutive_losses == 0:
            return 0.0
        
        boost = self.consecutive_losses * self.score_boost_per_loss
        return min(boost, self.max_score_boost)
    
    def reset(self, manual: bool = True) -> None:
        """
        Réinitialise le circuit breaker.
        
        Args:
            manual: True si reset manuel (log différent)
        """
        trigger = "manual" if manual else "auto"
        reason = "Reset manuel" if manual else "Reset automatique"
        
        self._change_state(CircuitBreakerState.ACTIVE, "reset", reason)
        self.consecutive_losses = 0
        self.paused_until = None
        self.pause_reason = None
        
        logger.info(f"🔄 Circuit Breaker réinitialisé ({trigger})")
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut complet pour l'API"""
        remaining_pause = None
        if self.paused_until:
            remaining = (self.paused_until - datetime.now()).total_seconds()
            remaining_pause = max(0, int(remaining))
        
        return {
            "can_trade": self.can_trade(),
            "state": self.state.value,
            "consecutive_losses": self.consecutive_losses,
            "daily_pnl_pct": round(self.daily_pnl_pct, 2),
            "daily_pnl_usdt": round(self.daily_pnl_usdt, 2),
            "daily_trades": self.daily_trades,
            "daily_wins": self.daily_wins,
            "daily_losses": self.daily_losses,
            "score_boost": round(self.get_score_boost(), 1),
            "paused_until": self.paused_until.isoformat() if self.paused_until else None,
            "remaining_pause_seconds": remaining_pause,
            "pause_reason": self.pause_reason,
            "thresholds": {
                "max_consecutive_losses": self.max_consecutive_losses,
                "daily_drawdown_pause_pct": self.daily_drawdown_pause_pct,
                "daily_drawdown_stop_pct": self.daily_drawdown_stop_pct,
                "pause_duration_minutes": self.pause_duration.total_seconds() / 60
            }
        }
    
    def get_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retourne l'historique des événements"""
        return [event.to_dict() for event in self.events[-limit:]]
    
    def update_config(
        self,
        max_consecutive_losses: Optional[int] = None,
        daily_drawdown_pause_pct: Optional[float] = None,
        daily_drawdown_stop_pct: Optional[float] = None,
        pause_duration_minutes: Optional[int] = None,
        score_boost_per_loss: Optional[float] = None
    ) -> None:
        """Met à jour la configuration"""
        if max_consecutive_losses is not None:
            self.max_consecutive_losses = max_consecutive_losses
        if daily_drawdown_pause_pct is not None:
            self.daily_drawdown_pause_pct = daily_drawdown_pause_pct
        if daily_drawdown_stop_pct is not None:
            self.daily_drawdown_stop_pct = daily_drawdown_stop_pct
        if pause_duration_minutes is not None:
            self.pause_duration = timedelta(minutes=pause_duration_minutes)
        if score_boost_per_loss is not None:
            self.score_boost_per_loss = score_boost_per_loss
        
        logger.info(f"⚙️ Config Circuit Breaker mise à jour")
    
    def _log_event_to_db(self, event: CircuitBreakerEvent) -> None:
        """
        🔥 SPRINT 1: Logger l'événement dans circuit_breaker_events
        """
        try:
            from core.postgresql_datalogger import get_pg_datalogger
            pg_logger = get_pg_datalogger()
            
            if not pg_logger or not pg_logger.enabled:
                logger.debug("PostgreSQL logger non disponible pour CB events")
                return
            
            # Calculer durée de pause si c'est un resume
            pause_duration = None
            if event.event_type == "resume" and self.pause_duration:
                # Utiliser la durée de pause configurée comme estimation
                pause_duration = self.pause_duration.total_seconds()
            
            query = """
                INSERT INTO circuit_breaker_events (
                    timestamp, session_id, event_type, reason,
                    state_before, state_after,
                    consecutive_losses, daily_pnl_pct, daily_pnl_usdt,
                    daily_trades, daily_wins, daily_losses,
                    score_boost, pause_duration_seconds
                ) VALUES (
                    NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            session_id = pg_logger.get_or_create_session()
            metrics = event.metrics or {}
            
            params = (
                session_id,
                event.event_type,
                event.reason[:500] if event.reason else None,  # Limiter la longueur
                event.state_before,
                event.state_after,
                self.consecutive_losses,
                round(self.daily_pnl_pct, 4),
                round(self.daily_pnl_usdt, 2),
                self.daily_trades,
                self.daily_wins,
                self.daily_losses,
                metrics.get('score_boost', 0),
                pause_duration
            )
            
            pg_logger._execute_query(query, params, commit=True)
            logger.info(f"📝 Événement CB loggé: {event.event_type}")
            
        except Exception as e:
            logger.error(f"❌ Erreur logging CB event: {e}")


# Instance globale
_trading_cb: Optional[TradingCircuitBreaker] = None


def get_trading_circuit_breaker() -> TradingCircuitBreaker:
    """Retourne l'instance globale du circuit breaker trading, configurée depuis TRADING_CONFIG"""
    global _trading_cb
    if _trading_cb is None:
        # Charger config depuis TRADING_CONFIG
        try:
            from config import TRADING_CONFIG
            _trading_cb = TradingCircuitBreaker(
                max_consecutive_losses=TRADING_CONFIG.get('trading_cb_max_consecutive_losses', 5),
                daily_drawdown_pause_pct=TRADING_CONFIG.get('trading_cb_daily_drawdown_pause_pct', -2.0),
                daily_drawdown_stop_pct=TRADING_CONFIG.get('trading_cb_daily_drawdown_stop_pct', -5.0),
                pause_duration_minutes=TRADING_CONFIG.get('trading_cb_pause_duration_minutes', 30),
                score_boost_per_loss=TRADING_CONFIG.get('trading_cb_score_boost_per_loss', 0.5)
            )
            logger.info(
                f"✅ Trading Circuit Breaker initialisé: "
                f"max_losses={_trading_cb.max_consecutive_losses}, "
                f"pause_pct={_trading_cb.daily_drawdown_pause_pct}%, "
                f"stop_pct={_trading_cb.daily_drawdown_stop_pct}%"
            )
        except ImportError:
            logger.warning("⚠️ TRADING_CONFIG non disponible, utilisation valeurs par défaut")
            _trading_cb = TradingCircuitBreaker()
    return _trading_cb


def init_trading_circuit_breaker(**kwargs) -> TradingCircuitBreaker:
    """Initialise l'instance globale avec des paramètres personnalisés"""
    global _trading_cb
    _trading_cb = TradingCircuitBreaker(**kwargs)
    return _trading_cb

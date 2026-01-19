"""
PostExitManager - Gestion centralisée des trackers post-exit
Trade Cursor v7.0
"""

from typing import Dict, Optional, List, Any
from datetime import datetime, timezone
import asyncio
import logging
import threading

from .tracker import PostExitTracker

logger = logging.getLogger(__name__)

# Singleton instance
_manager_instance: Optional['PostExitManager'] = None
_manager_lock = threading.Lock()


def get_post_exit_manager() -> 'PostExitManager':
    """Obtenir l'instance singleton du PostExitManager"""
    global _manager_instance
    if _manager_instance is None:
        with _manager_lock:
            if _manager_instance is None:
                _manager_instance = PostExitManager()
    return _manager_instance


class PostExitManager:
    """Gestionnaire centralisé des trackers post-exit"""
    
    DEFAULT_CONFIG = {
        # Durée de suivi
        "tracking_duration_seconds": 300,      # 5 minutes
        "sample_interval_ms": 1000,            # 1 sample/seconde
        
        # Durée adaptative
        "adaptive_duration": True,
        "min_duration_seconds": 60,            # Min 1 minute
        "max_duration_seconds": 600,           # Max 10 minutes
        "duration_multiplier": 2.0,            # durée = trade_duration × multiplier
        
        # Gestion ressources
        "max_concurrent_trackers": 15,
        
        # Persistence
        "store_raw_samples": True,
        "enabled": True,                       # Master switch
    }
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        
        # Trackers actifs: symbol -> tracker
        self.active_trackers: Dict[str, PostExitTracker] = {}
        
        # Trackers terminés: trade_id -> metrics (gardé en mémoire pour accès rapide)
        self.completed_metrics: Dict[int, Dict] = {}
        self._completed_max_size = 100  # Garder les 100 derniers
        
        self._lock = asyncio.Lock()
        self._sync_lock = threading.Lock()
        
        logger.info(f"📊 PostExitManager initialisé (max_trackers={self.config['max_concurrent_trackers']})")
    
    async def start_tracking(
        self,
        trade_id: int,
        symbol: str,
        direction: str,
        exit_price: float,
        exit_reason: str,
        realized_pnl_pct: float,
        realized_pnl_usdt: float,
        original_sl: float,
        original_tp: float,
        entry_price: float,
        trade_duration_sec: Optional[float] = None,
        used_params: Optional[Dict] = None
    ) -> Optional[PostExitTracker]:
        """
        Démarrer le tracking pour un trade fermé
        
        Args:
            trade_id: ID du trade en DB
            symbol: Symbole (ex: BTCUSDT)
            direction: LONG ou SHORT
            exit_price: Prix de sortie
            exit_reason: Raison de sortie (TP_HIT, SL_HIT, TRAILING_STOP, etc.)
            realized_pnl_pct: PnL% réalisé
            realized_pnl_usdt: PnL$ réalisé
            original_sl: SL original du trade
            original_tp: TP original du trade
            entry_price: Prix d'entrée
            trade_duration_sec: Durée du trade en secondes
            used_params: Dict avec les params utilisés (sl_pct, tp_pct, be_trigger, etc.)
            
        Returns:
            PostExitTracker si créé, None si désactivé ou limite atteinte
        """
        if not self.config.get("enabled", True):
            return None
        
        async with self._lock:
            # Vérifier limite de trackers
            if len(self.active_trackers) >= self.config["max_concurrent_trackers"]:
                # Arrêter le plus ancien
                oldest_symbol = min(
                    self.active_trackers.keys(),
                    key=lambda s: self.active_trackers[s].start_time
                )
                await self._complete_tracker(oldest_symbol, reason="limit_reached")
                logger.warning(f"⚠️ PostExit: Limite atteinte, arrêt forcé du tracker {oldest_symbol}")
            
            # Si déjà un tracker sur ce symbol, le terminer
            if symbol in self.active_trackers:
                await self._complete_tracker(symbol, reason="new_trade_same_symbol")
            
            # Calculer durée adaptative
            duration = self.config["tracking_duration_seconds"]
            if self.config.get("adaptive_duration") and trade_duration_sec:
                adaptive_duration = min(
                    self.config["max_duration_seconds"],
                    max(
                        self.config["min_duration_seconds"],
                        int(trade_duration_sec * self.config.get("duration_multiplier", 2.0))
                    )
                )
                duration = adaptive_duration
            
            # Extraire params utilisés
            used_params = used_params or {}
            
            # Créer tracker
            tracker = PostExitTracker(
                trade_id=trade_id,
                symbol=symbol,
                direction=direction,
                exit_price=exit_price,
                exit_timestamp=datetime.now(timezone.utc),
                exit_reason=exit_reason,
                realized_pnl_pct=realized_pnl_pct,
                realized_pnl_usdt=realized_pnl_usdt,
                original_sl=original_sl,
                original_tp=original_tp,
                entry_price=entry_price,
                tracking_duration_sec=duration,
                sample_interval_ms=self.config["sample_interval_ms"],
                used_sl_pct=used_params.get('sl_pct'),
                used_tp_pct=used_params.get('tp_pct'),
                used_be_trigger=used_params.get('be_trigger'),
                used_trailing_trigger=used_params.get('trailing_trigger'),
                used_trailing_min_distance=used_params.get('trailing_min_distance'),
                used_partial_tp_pct=used_params.get('partial_tp_pct'),
            )
            
            self.active_trackers[symbol] = tracker
            logger.info(
                f"📊 PostExit: Démarrage tracking {symbol} pour {duration}s "
                f"(trade #{trade_id}, exit={exit_reason}, pnl={realized_pnl_pct:.2f}%)"
            )
            
            return tracker
    
    def start_tracking_sync(self, **kwargs) -> Optional[PostExitTracker]:
        """
        Version synchrone de start_tracking pour appel depuis code sync
        
        Gère les cas:
        1. Appelé depuis thread avec event loop running (main thread FastAPI)
        2. Appelé depuis thread sans event loop (position_sync thread)
        """
        symbol = kwargs.get('symbol', 'N/A')
        
        try:
            # 🔥 FIX: Essayer d'obtenir une loop existante
            try:
                loop = asyncio.get_running_loop()
                # Loop running - fire-and-forget
                asyncio.run_coroutine_threadsafe(
                    self.start_tracking(**kwargs),
                    loop
                )
                logger.debug(f"📊 PostExit tracking lancé (running loop) pour {symbol}")
                return None
            except RuntimeError:
                # Pas de loop running dans ce thread
                pass
            
            # 🔥 FIX: Créer une nouvelle loop pour ce thread
            # Utiliser asyncio.run() qui crée et ferme proprement une loop
            logger.debug(f"📊 PostExit: Création nouvelle loop pour {symbol}")
            result = asyncio.run(self.start_tracking(**kwargs))
            logger.info(f"✅ PostExit tracking démarré (nouvelle loop) pour {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"❌ PostExit start_tracking_sync error: {e}", exc_info=True)
            return None
    
    async def on_price_update(self, symbol: str, price: float) -> None:
        """
        Appelé à chaque mise à jour de prix (depuis WebSocket)
        
        Args:
            symbol: Symbole mis à jour
            price: Nouveau prix
        """
        if symbol not in self.active_trackers:
            return
        
        tracker = self.active_trackers[symbol]
        sample_added = tracker.add_sample(price)
        
        # Si tracking terminé
        if not tracker.is_active:
            await self._complete_tracker(symbol, reason="duration_complete")
    
    def on_price_update_sync(self, symbol: str, price: float) -> None:
        """Version synchrone pour appel depuis WebSocket callback"""
        if symbol not in self.active_trackers:
            return
        
        tracker = self.active_trackers[symbol]
        sample_added = tracker.add_sample(price)
        
        # Log périodique pour debug
        if sample_added and len(tracker.samples) % 30 == 1:
            logger.warning(f"📊 PostExit {symbol}: {len(tracker.samples)} samples collectés, is_active={tracker.is_active}")
        
        # Si tracking terminé
        if not tracker.is_active:
            logger.warning(f"🟢 PostExit {symbol}: Tracking terminé, lancement complétion...")
            # Planifier la complétion dans un thread
            threading.Thread(
                target=self._complete_tracker_sync,
                args=(symbol, "duration_complete"),
                daemon=True
            ).start()
    
    def _complete_tracker_sync(self, symbol: str, reason: str) -> None:
        """Version synchrone de _complete_tracker"""
        try:
            logger.warning(f"🔄 PostExit {symbol}: _complete_tracker_sync démarré...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._complete_tracker(symbol, reason))
            loop.close()
            logger.warning(f"✅ PostExit {symbol}: Complétion terminée, result={result is not None}")
        except Exception as e:
            logger.error(f"❌ PostExit _complete_tracker_sync error: {e}", exc_info=True)
    
    async def _complete_tracker(self, symbol: str, reason: str = "complete") -> Optional[Dict]:
        """
        Terminer un tracker et sauvegarder les résultats
        
        Args:
            symbol: Symbole du tracker à terminer
            reason: Raison de la fin (complete, limit_reached, new_trade_same_symbol)
            
        Returns:
            Dict des métriques finales ou None
        """
        if symbol not in self.active_trackers:
            return None
        
        tracker = self.active_trackers.pop(symbol)
        tracker.is_active = False
        
        # Calculer métriques finales
        metrics = tracker.compute_final_metrics()
        
        if not metrics:
            logger.warning(f"⚠️ PostExit {symbol}: Pas de samples collectés")
            return None
        
        # Stocker pour accès rapide
        trade_id = tracker.trade_id
        self.completed_metrics[trade_id] = metrics
        
        # Limiter taille du cache
        if len(self.completed_metrics) > self._completed_max_size:
            oldest_id = min(self.completed_metrics.keys())
            del self.completed_metrics[oldest_id]
        
        # Sauvegarder en DB
        logger.warning(f"💾 PostExit {symbol}: Sauvegarde DB avec {metrics.get('sample_count', 0)} samples...")
        save_ok = await self._save_to_database(tracker, metrics)
        logger.warning(f"💾 PostExit {symbol}: Sauvegarde DB = {save_ok}")
        
        efficiency = metrics.get("exit_efficiency_pct", 0)
        grade = metrics.get("exit_timing_grade", "?")
        mfe = metrics.get("post_exit_mfe_pct", 0)
        
        logger.info(
            f"✅ PostExit {symbol}: Terminé ({reason}) | "
            f"Efficiency: {efficiency:.1f}% ({grade}) | "
            f"MFE post-exit: {mfe:.2f}% | "
            f"Samples: {metrics.get('sample_count', 0)}"
        )
        
        return metrics
    
    async def _save_to_database(self, tracker: PostExitTracker, metrics: Dict) -> bool:
        """
        Sauvegarder les résultats en DB PostgreSQL
        
        Args:
            tracker: Tracker avec les samples
            metrics: Métriques calculées
            
        Returns:
            True si sauvegarde réussie
        """
        try:
            from core.postgresql_datalogger import get_datalogger
            
            datalogger = get_datalogger()
            if not datalogger:
                logger.warning("❌ PostExit DB: DataLogger non disponible")
                return False
            if not datalogger.enabled:
                logger.warning("❌ PostExit DB: DataLogger désactivé")
                return False
            
            conn = datalogger._get_connection()
            if not conn:
                logger.warning("❌ PostExit DB: Connexion non disponible")
                return False
            
            logger.warning(f"🔍 PostExit DB: trade_id={metrics['trade_id']} (type={type(metrics['trade_id']).__name__})")
            
            try:
                with conn.cursor() as cur:
                    # 1. Insérer les métriques agrégées
                    cur.execute("""
                        INSERT INTO trade_post_exit_analysis (
                            trade_id, exit_price, exit_timestamp, exit_reason, direction,
                            realized_pnl_pct, realized_pnl_usdt,
                            used_sl_pct, used_tp_pct, used_be_trigger, used_trailing_trigger,
                            used_trailing_min_distance, used_partial_tp_pct,
                            tracking_duration_sec, sample_count, sample_interval_ms,
                            post_exit_mfe_pct, post_exit_mfe_price, post_exit_mfe_timestamp, time_to_mfe_sec,
                            post_exit_mae_pct, post_exit_mae_price, post_exit_mae_timestamp,
                            post_exit_final_pct, post_exit_final_price,
                            exit_efficiency_pct, regret_pct, regret_usdt, exit_timing_grade,
                            would_have_hit_original_tp, would_have_hit_original_sl, price_returned_to_entry,
                            ml_optimal_sl_pct, ml_optimal_trailing_trigger, ml_optimal_be_trigger, ml_should_use_partial
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s,
                            %s, %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s
                        )
                        ON CONFLICT (trade_id) DO UPDATE SET
                            exit_efficiency_pct = EXCLUDED.exit_efficiency_pct,
                            post_exit_mfe_pct = EXCLUDED.post_exit_mfe_pct,
                            sample_count = EXCLUDED.sample_count
                    """, (
                        metrics['trade_id'],
                        metrics['exit_price'],
                        tracker.exit_timestamp,
                        metrics['exit_reason'],
                        metrics['direction'],
                        metrics['realized_pnl_pct'],
                        metrics['realized_pnl_usdt'],
                        metrics.get('used_sl_pct'),
                        metrics.get('used_tp_pct'),
                        metrics.get('used_be_trigger'),
                        metrics.get('used_trailing_trigger'),
                        metrics.get('used_trailing_min_distance'),
                        metrics.get('used_partial_tp_pct'),
                        metrics['tracking_duration_sec'],
                        metrics['sample_count'],
                        metrics['sample_interval_ms'],
                        metrics['post_exit_mfe_pct'],
                        metrics.get('post_exit_mfe_price'),
                        tracker.post_exit_mfe_timestamp,
                        metrics.get('time_to_mfe_sec'),
                        metrics['post_exit_mae_pct'],
                        metrics.get('post_exit_mae_price'),
                        tracker.post_exit_mae_timestamp,
                        metrics['post_exit_final_pct'],
                        metrics.get('post_exit_final_price'),
                        metrics['exit_efficiency_pct'],
                        metrics['regret_pct'],
                        metrics['regret_usdt'],
                        metrics['exit_timing_grade'],
                        metrics['would_have_hit_original_tp'],
                        metrics['would_have_hit_original_sl'],
                        metrics['price_returned_to_entry'],
                        metrics.get('ml_optimal_sl_pct'),
                        metrics.get('ml_optimal_trailing_trigger'),
                        metrics.get('ml_optimal_be_trigger'),
                        metrics.get('ml_should_use_partial'),
                    ))
                    
                    # 2. Insérer les samples bruts si configuré
                    if self.config.get("store_raw_samples", True):
                        samples_data = tracker.get_samples_for_db()
                        if samples_data:
                            from psycopg2.extras import execute_values
                            execute_values(
                                cur,
                                """
                                INSERT INTO trade_post_exit_samples 
                                (trade_id, sample_index, timestamp, price, pnl_vs_exit_pct, cumulative_mfe_pct, cumulative_mae_pct)
                                VALUES %s
                                ON CONFLICT (trade_id, sample_index) DO NOTHING
                                """,
                                [
                                    (
                                        s['trade_id'],
                                        s['sample_index'],
                                        s['timestamp'],
                                        s['price'],
                                        s['pnl_vs_exit_pct'],
                                        s['cumulative_mfe_pct'],
                                        s['cumulative_mae_pct']
                                    )
                                    for s in samples_data
                                ]
                            )
                    
                    conn.commit()
                    logger.debug(f"✅ PostExit {tracker.symbol}: Sauvegardé en DB (trade #{tracker.trade_id})")
                    return True
                    
            except Exception as e:
                conn.rollback()
                logger.error(f"❌ PostExit DB save error: {e}", exc_info=True)
                return False
            finally:
                datalogger._return_connection(conn)
                
        except ImportError:
            logger.debug("PostgreSQL DataLogger non importable")
            return False
        except Exception as e:
            logger.error(f"❌ PostExit _save_to_database error: {e}")
            return False
    
    def get_active_trackers_count(self) -> int:
        """Nombre de trackers actifs"""
        return len(self.active_trackers)
    
    def get_active_symbols(self) -> List[str]:
        """Liste des symboles en cours de tracking"""
        return list(self.active_trackers.keys())
    
    def get_tracker_status(self) -> Dict[str, Any]:
        """Status complet du manager"""
        return {
            "enabled": self.config.get("enabled", True),
            "active_count": len(self.active_trackers),
            "completed_count": len(self.completed_metrics),
            "active_symbols": list(self.active_trackers.keys()),
            "config": {
                "tracking_duration_seconds": self.config["tracking_duration_seconds"],
                "sample_interval_ms": self.config["sample_interval_ms"],
                "max_concurrent_trackers": self.config["max_concurrent_trackers"],
                "adaptive_duration": self.config.get("adaptive_duration", True),
            }
        }
    
    def get_recent_metrics(self, limit: int = 10) -> List[Dict]:
        """Récupérer les métriques des derniers trades terminés"""
        sorted_metrics = sorted(
            self.completed_metrics.values(),
            key=lambda m: m.get('trade_id', 0),
            reverse=True
        )
        return sorted_metrics[:limit]
    
    def is_tracking(self, symbol: str) -> bool:
        """Vérifier si un symbole est en cours de tracking"""
        return symbol in self.active_trackers

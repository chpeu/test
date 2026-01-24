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
        # Durée de suivi - Optimisé pour capturer les MFE tardifs (max observé ~8.7 min)
        "tracking_duration_seconds": 600,      # 10 minutes (was 5 min)
        "sample_interval_ms": 2000,            # 1 sample/2 secondes (was 1s) - réduit charge DB
        
        # Durée adaptative
        "adaptive_duration": True,
        "min_duration_seconds": 120,           # Min 2 minutes (was 1 min)
        "max_duration_seconds": 900,           # Max 15 minutes (was 10 min)
        "duration_multiplier": 2.0,            # durée = trade_duration × multiplier
        
        # Gestion ressources
        "max_concurrent_trackers": 15,
        
        # Persistence - Survivre aux redémarrages
        "store_raw_samples": True,
        "persist_on_shutdown": True,           # Sauvegarder en DB avant arrêt
        "restore_on_startup": True,            # Restaurer depuis DB au démarrage
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
            from core.postgresql_datalogger import get_pg_datalogger
            
            datalogger = get_pg_datalogger()
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
                            exit_price = EXCLUDED.exit_price,
                            exit_timestamp = EXCLUDED.exit_timestamp,
                            exit_reason = EXCLUDED.exit_reason,
                            direction = EXCLUDED.direction,
                            realized_pnl_pct = EXCLUDED.realized_pnl_pct,
                            realized_pnl_usdt = EXCLUDED.realized_pnl_usdt,
                            used_sl_pct = COALESCE(EXCLUDED.used_sl_pct, trade_post_exit_analysis.used_sl_pct),
                            used_tp_pct = COALESCE(EXCLUDED.used_tp_pct, trade_post_exit_analysis.used_tp_pct),
                            used_be_trigger = COALESCE(EXCLUDED.used_be_trigger, trade_post_exit_analysis.used_be_trigger),
                            used_trailing_trigger = COALESCE(EXCLUDED.used_trailing_trigger, trade_post_exit_analysis.used_trailing_trigger),
                            used_trailing_min_distance = COALESCE(EXCLUDED.used_trailing_min_distance, trade_post_exit_analysis.used_trailing_min_distance),
                            used_partial_tp_pct = COALESCE(EXCLUDED.used_partial_tp_pct, trade_post_exit_analysis.used_partial_tp_pct),
                            tracking_duration_sec = EXCLUDED.tracking_duration_sec,
                            sample_count = EXCLUDED.sample_count,
                            sample_interval_ms = EXCLUDED.sample_interval_ms,
                            post_exit_mfe_pct = EXCLUDED.post_exit_mfe_pct,
                            post_exit_mfe_price = COALESCE(EXCLUDED.post_exit_mfe_price, trade_post_exit_analysis.post_exit_mfe_price),
                            post_exit_mfe_timestamp = COALESCE(EXCLUDED.post_exit_mfe_timestamp, trade_post_exit_analysis.post_exit_mfe_timestamp),
                            time_to_mfe_sec = COALESCE(EXCLUDED.time_to_mfe_sec, trade_post_exit_analysis.time_to_mfe_sec),
                            post_exit_mae_pct = COALESCE(EXCLUDED.post_exit_mae_pct, trade_post_exit_analysis.post_exit_mae_pct),
                            post_exit_mae_price = COALESCE(EXCLUDED.post_exit_mae_price, trade_post_exit_analysis.post_exit_mae_price),
                            post_exit_mae_timestamp = COALESCE(EXCLUDED.post_exit_mae_timestamp, trade_post_exit_analysis.post_exit_mae_timestamp),
                            post_exit_final_pct = COALESCE(EXCLUDED.post_exit_final_pct, trade_post_exit_analysis.post_exit_final_pct),
                            post_exit_final_price = COALESCE(EXCLUDED.post_exit_final_price, trade_post_exit_analysis.post_exit_final_price),
                            exit_efficiency_pct = EXCLUDED.exit_efficiency_pct,
                            regret_pct = COALESCE(EXCLUDED.regret_pct, trade_post_exit_analysis.regret_pct),
                            regret_usdt = COALESCE(EXCLUDED.regret_usdt, trade_post_exit_analysis.regret_usdt),
                            exit_timing_grade = COALESCE(EXCLUDED.exit_timing_grade, trade_post_exit_analysis.exit_timing_grade),
                            would_have_hit_original_tp = COALESCE(EXCLUDED.would_have_hit_original_tp, trade_post_exit_analysis.would_have_hit_original_tp),
                            would_have_hit_original_sl = COALESCE(EXCLUDED.would_have_hit_original_sl, trade_post_exit_analysis.would_have_hit_original_sl),
                            price_returned_to_entry = COALESCE(EXCLUDED.price_returned_to_entry, trade_post_exit_analysis.price_returned_to_entry),
                            ml_optimal_sl_pct = COALESCE(EXCLUDED.ml_optimal_sl_pct, trade_post_exit_analysis.ml_optimal_sl_pct),
                            ml_optimal_trailing_trigger = COALESCE(EXCLUDED.ml_optimal_trailing_trigger, trade_post_exit_analysis.ml_optimal_trailing_trigger),
                            ml_optimal_be_trigger = COALESCE(EXCLUDED.ml_optimal_be_trigger, trade_post_exit_analysis.ml_optimal_be_trigger),
                            ml_should_use_partial = COALESCE(EXCLUDED.ml_should_use_partial, trade_post_exit_analysis.ml_should_use_partial)
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
    
    # ========== PERSISTANCE DES TRACKERS ==========
    
    async def persist_active_trackers(self) -> int:
        """
        Sauvegarder tous les trackers actifs en DB pour survivre aux redémarrages.
        Appelé périodiquement ou avant shutdown.
        
        Returns:
            Nombre de trackers persistés
        """
        if not self.active_trackers:
            return 0
        
        try:
            from core.postgresql_datalogger import get_pg_datalogger
            import json
            
            datalogger = get_pg_datalogger()
            if not datalogger or not datalogger.enabled:
                return 0
            
            conn = datalogger._get_connection()
            if not conn:
                return 0
            
            persisted = 0
            
            try:
                with conn.cursor() as cur:
                    for symbol, tracker in self.active_trackers.items():
                        # Préparer les samples en JSON compact
                        samples_json = json.dumps([
                            {
                                'ts': s.timestamp.isoformat(),
                                'p': s.price,
                                'pnl': s.pnl_vs_exit_pct,
                                'mfe': s.cumulative_mfe_pct,
                                'mae': s.cumulative_mae_pct
                            }
                            for s in tracker.samples
                        ])
                        
                        cur.execute("""
                            INSERT INTO post_exit_active_trackers (
                                trade_id, symbol, direction,
                                exit_price, exit_timestamp, exit_reason,
                                realized_pnl_pct, realized_pnl_usdt,
                                original_sl, original_tp, entry_price,
                                used_sl_pct, used_tp_pct, used_be_trigger,
                                used_trailing_trigger, used_trailing_min_distance, used_partial_tp_pct,
                                tracking_duration_sec, sample_interval_ms,
                                start_time, samples_collected,
                                post_exit_mfe_pct, post_exit_mfe_price, post_exit_mfe_timestamp,
                                post_exit_mae_pct, post_exit_mae_price, post_exit_mae_timestamp,
                                would_have_hit_original_tp, would_have_hit_original_sl, price_returned_to_entry,
                                samples_json
                            ) VALUES (
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s,
                                %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,
                                %s
                            )
                            ON CONFLICT (trade_id) DO UPDATE SET
                                samples_collected = EXCLUDED.samples_collected,
                                post_exit_mfe_pct = EXCLUDED.post_exit_mfe_pct,
                                post_exit_mfe_price = EXCLUDED.post_exit_mfe_price,
                                post_exit_mfe_timestamp = EXCLUDED.post_exit_mfe_timestamp,
                                post_exit_mae_pct = EXCLUDED.post_exit_mae_pct,
                                would_have_hit_original_tp = EXCLUDED.would_have_hit_original_tp,
                                would_have_hit_original_sl = EXCLUDED.would_have_hit_original_sl,
                                price_returned_to_entry = EXCLUDED.price_returned_to_entry,
                                samples_json = EXCLUDED.samples_json,
                                updated_at = NOW()
                        """, (
                            str(tracker.trade_id), tracker.symbol, tracker.direction,
                            tracker.exit_price, tracker.exit_timestamp, tracker.exit_reason,
                            tracker.realized_pnl_pct, tracker.realized_pnl_usdt,
                            tracker.original_sl, tracker.original_tp, tracker.entry_price,
                            tracker.used_sl_pct, tracker.used_tp_pct, tracker.used_be_trigger,
                            tracker.used_trailing_trigger, tracker.used_trailing_min_distance, tracker.used_partial_tp_pct,
                            tracker.tracking_duration_sec, tracker.sample_interval_ms,
                            datetime.fromtimestamp(tracker.start_time, tz=timezone.utc), len(tracker.samples),
                            tracker.post_exit_mfe_pct, tracker.post_exit_mfe_price, tracker.post_exit_mfe_timestamp,
                            tracker.post_exit_mae_pct, tracker.post_exit_mae_price, tracker.post_exit_mae_timestamp,
                            tracker.would_have_hit_original_tp, tracker.would_have_hit_original_sl, tracker.price_returned_to_entry,
                            samples_json
                        ))
                        persisted += 1
                    
                    conn.commit()
                    logger.info(f"💾 PostExit: {persisted} trackers persistés en DB")
                    
            finally:
                datalogger._return_connection(conn)
            
            return persisted
            
        except Exception as e:
            logger.error(f"❌ PostExit persist error: {e}", exc_info=True)
            return 0
    
    def persist_active_trackers_sync(self) -> int:
        """Version synchrone de persist_active_trackers"""
        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self.persist_active_trackers())
            loop.close()
            return result
        except Exception as e:
            logger.error(f"❌ PostExit persist_sync error: {e}")
            return 0
    
    async def restore_active_trackers(self) -> int:
        """
        Restaurer les trackers actifs depuis la DB après un redémarrage.
        Appelé au démarrage du backend.
        
        Returns:
            Nombre de trackers restaurés
        """
        try:
            from core.postgresql_datalogger import get_pg_datalogger
            from psycopg2.extras import RealDictCursor
            import json
            from .tracker import PostExitSample
            
            datalogger = get_pg_datalogger()
            if not datalogger or not datalogger.enabled:
                return 0
            
            conn = datalogger._get_connection()
            if not conn:
                return 0
            
            restored = 0
            deleted = 0
            
            try:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # Récupérer les trackers non expirés
                cur.execute("""
                    SELECT * FROM post_exit_active_trackers
                    WHERE start_time + (tracking_duration_sec || ' seconds')::interval > NOW()
                """)
                
                rows = cur.fetchall()
                
                for row in rows:
                    # Recréer le tracker
                    tracker = PostExitTracker(
                        trade_id=row['trade_id'],
                        symbol=row['symbol'],
                        direction=row['direction'],
                        exit_price=float(row['exit_price']),
                        exit_timestamp=row['exit_timestamp'],
                        exit_reason=row['exit_reason'] or '',
                        realized_pnl_pct=float(row['realized_pnl_pct'] or 0),
                        realized_pnl_usdt=float(row['realized_pnl_usdt'] or 0),
                        original_sl=float(row['original_sl'] or 0),
                        original_tp=float(row['original_tp'] or 0),
                        entry_price=float(row['entry_price']),
                        tracking_duration_sec=row['tracking_duration_sec'],
                        sample_interval_ms=row['sample_interval_ms'],
                        used_sl_pct=float(row['used_sl_pct']) if row['used_sl_pct'] else None,
                        used_tp_pct=float(row['used_tp_pct']) if row['used_tp_pct'] else None,
                        used_be_trigger=float(row['used_be_trigger']) if row['used_be_trigger'] else None,
                        used_trailing_trigger=float(row['used_trailing_trigger']) if row['used_trailing_trigger'] else None,
                        used_trailing_min_distance=float(row['used_trailing_min_distance']) if row['used_trailing_min_distance'] else None,
                        used_partial_tp_pct=float(row['used_partial_tp_pct']) if row['used_partial_tp_pct'] else None,
                    )
                    
                    # Restaurer l'état
                    tracker.start_time = row['start_time'].timestamp()
                    tracker.post_exit_mfe_pct = float(row['post_exit_mfe_pct'] or 0)
                    tracker.post_exit_mfe_price = float(row['post_exit_mfe_price']) if row['post_exit_mfe_price'] else None
                    tracker.post_exit_mfe_timestamp = row['post_exit_mfe_timestamp']
                    tracker.post_exit_mae_pct = float(row['post_exit_mae_pct'] or 0)
                    tracker.post_exit_mae_price = float(row['post_exit_mae_price']) if row['post_exit_mae_price'] else None
                    tracker.post_exit_mae_timestamp = row['post_exit_mae_timestamp']
                    tracker.would_have_hit_original_tp = row['would_have_hit_original_tp'] or False
                    tracker.would_have_hit_original_sl = row['would_have_hit_original_sl'] or False
                    tracker.price_returned_to_entry = row['price_returned_to_entry'] or False
                    
                    # Restaurer les samples
                    samples_data = row['samples_json'] or []
                    if isinstance(samples_data, str):
                        samples_data = json.loads(samples_data)
                    
                    for s in samples_data:
                        sample = PostExitSample(
                            timestamp=datetime.fromisoformat(s['ts']),
                            price=s['p'],
                            pnl_vs_exit_pct=s['pnl'],
                            cumulative_mfe_pct=s['mfe'],
                            cumulative_mae_pct=s['mae']
                        )
                        tracker.samples.append(sample)
                    
                    if tracker.samples:
                        tracker.last_sample_time = tracker.samples[-1].timestamp.timestamp()
                    
                    # Ajouter au manager
                    self.active_trackers[row['symbol']] = tracker
                    restored += 1
                    
                    logger.info(f"🔄 PostExit: Restauré tracker {row['symbol']} ({len(tracker.samples)} samples)")
                
                # Supprimer les trackers expirés de la DB
                cur.execute("""
                    DELETE FROM post_exit_active_trackers
                    WHERE start_time + (tracking_duration_sec || ' seconds')::interval <= NOW()
                    RETURNING trade_id
                """)
                deleted = cur.rowcount
                
                # Supprimer les trackers restaurés de la DB (ils sont maintenant en mémoire)
                if restored > 0:
                    cur.execute("DELETE FROM post_exit_active_trackers")
                
                conn.commit()
                
                if restored > 0 or deleted > 0:
                    logger.info(f"🔄 PostExit: {restored} trackers restaurés, {deleted} expirés supprimés")
                    
            finally:
                datalogger._return_connection(conn)
            
            return restored
            
        except Exception as e:
            logger.error(f"❌ PostExit restore error: {e}", exc_info=True)
            return 0
    
    def restore_active_trackers_sync(self) -> int:
        """Version synchrone de restore_active_trackers"""
        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self.restore_active_trackers())
            loop.close()
            return result
        except Exception as e:
            logger.error(f"❌ PostExit restore_sync error: {e}")
            return 0
    
    async def cleanup_and_persist(self) -> None:
        """
        Appeler avant shutdown: terminer proprement et persister les trackers actifs.
        """
        if self.active_trackers:
            logger.info(f"🛑 PostExit: Shutdown - {len(self.active_trackers)} trackers actifs à persister...")
            await self.persist_active_trackers()
            logger.info("✅ PostExit: Trackers persistés, prêts pour restauration au prochain démarrage")

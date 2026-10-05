"""
Pair Scorer - Score Pair Dynamique
Sprint 2 - Phase 2.2 - 07/12/2025

Ajuste le score minimum par paire selon performance historique.
Bonus pour paires performantes, malus pour paires sous-performantes.

Auteur: Cascade AI
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)


@dataclass
class PairStats:
    """Statistiques d'une paire"""
    symbol: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    winrate: float = 0.0
    avg_pnl_pct: float = 0.0
    total_pnl_pct: float = 0.0
    score_adjustment: float = 0.0
    wr_component: float = 0.0
    pnl_component: float = 0.0
    last_updated: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }


class PairScorer:
    """
    Calcule un ajustement de score par paire basé sur performance historique.
    
    Fonctionnalités:
    - Analyse historique des trades par paire
    - Calcul bonus/malus [-max_adjustment, +max_adjustment]
    - Cache en mémoire avec refresh périodique
    - Persistance en base de données
    """
    
    def __init__(
        self,
        enabled: bool = True,
        min_trades: int = 15,
        max_adjustment: float = 2.0,
        lookback_days: int = 30,
        refresh_minutes: int = 60
    ):
        """
        Initialise le Pair Scorer.
        
        Args:
            enabled: Activer/désactiver la fonctionnalité
            min_trades: Nombre minimum de trades pour calculer un ajustement
            max_adjustment: Ajustement maximum (positif ou négatif)
            lookback_days: Nombre de jours d'historique à analyser
            refresh_minutes: Intervalle de refresh des stats en minutes
        """
        self.enabled = enabled
        self.min_trades = min_trades
        self.max_adjustment = max_adjustment
        self.lookback_days = lookback_days
        self.refresh_interval = timedelta(minutes=refresh_minutes)
        
        # Cache des stats par paire
        self._stats_cache: Dict[str, PairStats] = {}
        self._last_refresh: Optional[datetime] = None
        self._lock = threading.Lock()
        
        # Callbacks
        self._on_stats_updated_callbacks: List[callable] = []
        
        logger.info(
            f"✅ PairScorer initialisé | "
            f"enabled={enabled} | min_trades={min_trades} | "
            f"max_adj=±{max_adjustment} | lookback={lookback_days}j"
        )
    
    def update_config(
        self,
        enabled: Optional[bool] = None,
        min_trades: Optional[int] = None,
        max_adjustment: Optional[float] = None,
        lookback_days: Optional[int] = None,
        refresh_minutes: Optional[int] = None
    ) -> None:
        """Met à jour la configuration à chaud."""
        if enabled is not None:
            self.enabled = enabled
            logger.info(f"🔄 PairScorer: enabled → {enabled}")
        
        if min_trades is not None:
            self.min_trades = min_trades
            logger.info(f"🔄 PairScorer: min_trades → {min_trades}")
        
        if max_adjustment is not None:
            self.max_adjustment = max_adjustment
            logger.info(f"🔄 PairScorer: max_adjustment → ±{max_adjustment}")
        
        if lookback_days is not None:
            self.lookback_days = lookback_days
            logger.info(f"🔄 PairScorer: lookback_days → {lookback_days}")
        
        if refresh_minutes is not None:
            self.refresh_interval = timedelta(minutes=refresh_minutes)
            logger.info(f"🔄 PairScorer: refresh_interval → {refresh_minutes}min")
    
    def calculate_adjustment(
        self,
        winrate: float,
        avg_pnl_pct: float,
        total_trades: int
    ) -> Tuple[float, float, float]:
        """
        Calcule l'ajustement de score basé sur performance.
        
        Args:
            winrate: Taux de réussite en % (0-100)
            avg_pnl_pct: PnL moyen en %
            total_trades: Nombre total de trades
            
        Returns:
            Tuple (adjustment, wr_component, pnl_component)
        """
        if total_trades < self.min_trades:
            return 0.0, 0.0, 0.0
        
        # Composante winrate (60% du poids)
        # Baseline = 50%, chaque 10% écart = ±0.6
        wr_component = (winrate - 50) / 10 * 0.6
        
        # Composante PnL moyen (40% du poids)
        # Baseline = 0%, chaque 0.1% écart = ±0.4
        pnl_component = (avg_pnl_pct / 0.1) * 0.4
        
        # Total borné
        total = wr_component + pnl_component
        adjustment = max(-self.max_adjustment, min(self.max_adjustment, total))
        
        return adjustment, wr_component, pnl_component
    
    def get_score_adjustment(self, symbol: str) -> float:
        """
        Retourne l'ajustement de score pour une paire.
        
        Args:
            symbol: Symbole de la paire (ex: "BTC/USDT:USDT")
            
        Returns:
            Ajustement de score [-max_adjustment, +max_adjustment]
            Positif = paire performante = score min réduit = plus permissif
            Négatif = paire sous-performante = score min augmenté = plus strict
        """
        if not self.enabled:
            return 0.0
        
        # Vérifier si refresh nécessaire
        self._check_refresh()
        
        with self._lock:
            if symbol in self._stats_cache:
                return self._stats_cache[symbol].score_adjustment
        
        # Pas de stats pour cette paire
        return 0.0
    
    def get_pair_stats(self, symbol: str) -> Optional[PairStats]:
        """Retourne les stats complètes d'une paire."""
        with self._lock:
            return self._stats_cache.get(symbol)
    
    def get_all_stats(self) -> Dict[str, PairStats]:
        """Retourne toutes les stats en cache."""
        with self._lock:
            return self._stats_cache.copy()
    
    def _check_refresh(self) -> None:
        """Vérifie si un refresh est nécessaire."""
        now = datetime.now()
        
        if self._last_refresh is None:
            self.refresh_stats()
        elif now - self._last_refresh > self.refresh_interval:
            self.refresh_stats()
    
    def refresh_stats(self, force: bool = False) -> bool:
        """
        Rafraîchit les stats depuis la base de données.
        
        Args:
            force: Forcer le refresh même si pas dans l'intervalle
            
        Returns:
            True si refresh effectué
        """
        if not self.enabled and not force:
            return False
        
        try:
            from core.postgresql_datalogger import get_pg_datalogger
            pg_logger = get_pg_datalogger()
            
            if not pg_logger or not pg_logger.enabled:
                logger.warning("⚠️ PostgreSQL non disponible pour refresh pair stats")
                return False
            
            # Requête pour calculer les stats par paire
            query = """
                SELECT 
                    symbol,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN NOT win THEN 1 ELSE 0 END) as losses,
                    ROUND(100.0 * SUM(CASE WHEN win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as winrate,
                    ROUND(AVG(pnl_pct)::numeric, 4) as avg_pnl_pct,
                    ROUND(SUM(pnl_pct)::numeric, 4) as total_pnl_pct
                FROM trades
                WHERE timestamp_entry > NOW() - INTERVAL '%s days'
                  AND pnl_pct IS NOT NULL
                GROUP BY symbol
                HAVING COUNT(*) >= %s
            """
            
            results = pg_logger._execute_query(
                query % (self.lookback_days, self.min_trades),
                fetch=True
            )
            
            if not results:
                logger.info("📊 Aucune paire avec assez de trades pour le pair scoring")
                self._last_refresh = datetime.now()
                return True
            
            # Mettre à jour le cache
            new_cache: Dict[str, PairStats] = {}
            now = datetime.now()
            
            for row in results:
                symbol = row[0]
                total_trades = row[1]
                wins = row[2]
                losses = row[3]
                winrate = float(row[4]) if row[4] else 0.0
                avg_pnl_pct = float(row[5]) if row[5] else 0.0
                total_pnl_pct = float(row[6]) if row[6] else 0.0
                
                adjustment, wr_comp, pnl_comp = self.calculate_adjustment(
                    winrate, avg_pnl_pct, total_trades
                )
                
                new_cache[symbol] = PairStats(
                    symbol=symbol,
                    total_trades=total_trades,
                    wins=wins,
                    losses=losses,
                    winrate=winrate,
                    avg_pnl_pct=avg_pnl_pct,
                    total_pnl_pct=total_pnl_pct,
                    score_adjustment=adjustment,
                    wr_component=wr_comp,
                    pnl_component=pnl_comp,
                    last_updated=now
                )
            
            with self._lock:
                self._stats_cache = new_cache
                self._last_refresh = now
            
            # Persister en base
            self._save_stats_to_db(new_cache)
            
            logger.info(
                f"📊 PairScorer refresh: {len(new_cache)} paires analysées | "
                f"Lookback: {self.lookback_days}j"
            )
            
            # Log les top/bottom paires
            sorted_pairs = sorted(
                new_cache.values(),
                key=lambda x: x.score_adjustment,
                reverse=True
            )
            
            if sorted_pairs:
                top = sorted_pairs[0]
                bottom = sorted_pairs[-1]
                logger.info(
                    f"   📈 Top: {top.symbol} (adj={top.score_adjustment:+.2f}, WR={top.winrate:.1f}%)"
                )
                logger.info(
                    f"   📉 Bottom: {bottom.symbol} (adj={bottom.score_adjustment:+.2f}, WR={bottom.winrate:.1f}%)"
                )
            
            # Notifier les callbacks
            for callback in self._on_stats_updated_callbacks:
                try:
                    callback(new_cache)
                except Exception as e:
                    logger.error(f"❌ Erreur callback pair scorer: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur refresh pair stats: {e}")
            return False
    
    def _save_stats_to_db(self, stats: Dict[str, PairStats]) -> None:
        """Persiste les stats en base de données."""
        try:
            from core.postgresql_datalogger import get_pg_datalogger
            pg_logger = get_pg_datalogger()
            
            if not pg_logger or not pg_logger.enabled:
                return
            
            for pair_stats in stats.values():
                query = """
                    INSERT INTO pair_performance_stats (
                        symbol, total_trades, wins, losses, winrate,
                        avg_pnl_pct, total_pnl_pct, score_adjustment,
                        wr_component, pnl_component, lookback_days, last_updated
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    )
                    ON CONFLICT (symbol) DO UPDATE SET
                        total_trades = EXCLUDED.total_trades,
                        wins = EXCLUDED.wins,
                        losses = EXCLUDED.losses,
                        winrate = EXCLUDED.winrate,
                        avg_pnl_pct = EXCLUDED.avg_pnl_pct,
                        total_pnl_pct = EXCLUDED.total_pnl_pct,
                        score_adjustment = EXCLUDED.score_adjustment,
                        wr_component = EXCLUDED.wr_component,
                        pnl_component = EXCLUDED.pnl_component,
                        lookback_days = EXCLUDED.lookback_days,
                        last_updated = NOW()
                """
                
                params = (
                    pair_stats.symbol,
                    pair_stats.total_trades,
                    pair_stats.wins,
                    pair_stats.losses,
                    pair_stats.winrate,
                    pair_stats.avg_pnl_pct,
                    pair_stats.total_pnl_pct,
                    pair_stats.score_adjustment,
                    pair_stats.wr_component,
                    pair_stats.pnl_component,
                    self.lookback_days
                )
                
                pg_logger._execute_query(query, params)
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde pair stats: {e}")
    
    def on_stats_updated(self, callback: callable) -> None:
        """Enregistre un callback appelé lors du refresh des stats."""
        self._on_stats_updated_callbacks.append(callback)
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut complet pour l'API."""
        with self._lock:
            pairs_with_bonus = sum(1 for s in self._stats_cache.values() if s.score_adjustment > 0.5)
            pairs_with_malus = sum(1 for s in self._stats_cache.values() if s.score_adjustment < -0.5)
            pairs_neutral = len(self._stats_cache) - pairs_with_bonus - pairs_with_malus
            
            return {
                "enabled": self.enabled,
                "total_pairs_analyzed": len(self._stats_cache),
                "pairs_with_bonus": pairs_with_bonus,
                "pairs_with_malus": pairs_with_malus,
                "pairs_neutral": pairs_neutral,
                "min_trades": self.min_trades,
                "max_adjustment": self.max_adjustment,
                "lookback_days": self.lookback_days,
                "refresh_interval_minutes": self.refresh_interval.total_seconds() / 60,
                "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None
            }
    
    def get_top_pairs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retourne les paires avec le meilleur ajustement."""
        with self._lock:
            sorted_pairs = sorted(
                self._stats_cache.values(),
                key=lambda x: x.score_adjustment,
                reverse=True
            )
            return [p.to_dict() for p in sorted_pairs[:limit]]
    
    def get_bottom_pairs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retourne les paires avec le pire ajustement."""
        with self._lock:
            sorted_pairs = sorted(
                self._stats_cache.values(),
                key=lambda x: x.score_adjustment
            )
            return [p.to_dict() for p in sorted_pairs[:limit]]


# Instance globale
_pair_scorer: Optional[PairScorer] = None


def get_pair_scorer() -> PairScorer:
    """Retourne l'instance globale du pair scorer, configurée depuis TRADING_CONFIG."""
    global _pair_scorer
    if _pair_scorer is None:
        try:
            from config import TRADING_CONFIG
            _pair_scorer = PairScorer(
                enabled=TRADING_CONFIG.get('pair_scorer_enabled', True),
                min_trades=TRADING_CONFIG.get('pair_scorer_min_trades', 15),
                max_adjustment=TRADING_CONFIG.get('pair_scorer_max_adjustment', 2.0),
                lookback_days=TRADING_CONFIG.get('pair_scorer_lookback_days', 30),
                refresh_minutes=TRADING_CONFIG.get('pair_scorer_refresh_minutes', 60)
            )
        except ImportError:
            logger.warning("⚠️ TRADING_CONFIG non disponible, utilisation valeurs par défaut")
            _pair_scorer = PairScorer()
    return _pair_scorer


def init_pair_scorer(**kwargs) -> PairScorer:
    """Initialise l'instance globale avec des paramètres personnalisés."""
    global _pair_scorer
    _pair_scorer = PairScorer(**kwargs)
    return _pair_scorer

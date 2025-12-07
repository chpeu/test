"""
ML Auto-Calibration System
===========================

Recalibre automatiquement la confiance ML basée sur les résultats live réels.
La confiance affichée devient le winrate réel observé par bucket (direction + confidence range).

Fonctionnalités:
- Pondération des trades (live > dry-run, récents > anciens)
- Recalibration par bucket (direction + confidence range)  
- Seuil minimum de trades avant activation
- Decay exponentiel basé sur l'ancienneté
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class CalibrationStats:
    """Statistiques de calibration pour un bucket"""
    direction: str
    confidence_bucket: str
    weighted_wins: float
    weighted_total: float
    total_trades: int
    actual_winrate: Optional[float]
    avg_pnl_pct: float
    total_pnl_usdt: float


class MLCalibrationManager:
    """
    Gestionnaire de calibration ML.
    
    Recalibre la confiance ML selon les résultats live réels.
    """
    
    def __init__(self, db_pool=None):
        """
        Initialise le gestionnaire de calibration.
        
        Args:
            db_pool: Pool de connexions PostgreSQL (optionnel, utilisera get_db_pool sinon)
        """
        self._db_pool = db_pool
        self._cache: Dict[Tuple[str, str], CalibrationStats] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Refresh cache toutes les 60 secondes
        
    def _get_db_pool(self):
        """Récupère le pool de connexions DB"""
        if self._db_pool:
            return self._db_pool
        try:
            # Utiliser le PostgreSQLDataLogger existant
            from core.postgresql_datalogger import PostgreSQLDataLogger
            # Créer une instance singleton si nécessaire
            if not hasattr(self, '_pg_logger'):
                self._pg_logger = PostgreSQLDataLogger()
            if self._pg_logger.enabled and self._pg_logger.pool:
                return self._pg_logger
            return None
        except Exception as e:
            logger.debug(f"Erreur récupération DB pool: {e}")
            return None
    
    def _get_config(self) -> Dict:
        """Récupère la configuration de calibration"""
        try:
            from config import TRADING_CONFIG
            return {
                'enabled': TRADING_CONFIG.get('ml_calibration_enabled', True),
                'live_weight': TRADING_CONFIG.get('ml_calib_live_weight', 1.0),
                'dryrun_weight': TRADING_CONFIG.get('ml_calib_dryrun_weight', 0.5),
                'decay_days': TRADING_CONFIG.get('ml_calib_decay_days', 14),
                'min_trades': TRADING_CONFIG.get('ml_calib_min_trades', 30),
                'min_winrate': TRADING_CONFIG.get('ml_calib_min_winrate', 40.0),
                'bucket_size': TRADING_CONFIG.get('ml_calib_bucket_size', 5),
            }
        except Exception as e:
            logger.warning(f"Erreur lecture config calibration: {e}")
            return {
                'enabled': True,
                'live_weight': 1.0,
                'dryrun_weight': 0.5,
                'decay_days': 14,
                'min_trades': 30,
                'min_winrate': 40.0,
                'bucket_size': 5,
            }
    
    def get_confidence_bucket(self, ml_confidence: float, bucket_size: int = 5) -> str:
        """
        Détermine le bucket de confiance.
        
        Args:
            ml_confidence: Confiance ML (ex: 37.5)
            bucket_size: Taille des buckets (défaut: 5)
            
        Returns:
            Bucket string (ex: '35-40', '50+')
        """
        if ml_confidence >= 50:
            return '50+'
        
        # Calculer le bucket
        bucket_start = int(ml_confidence // bucket_size) * bucket_size
        bucket_end = bucket_start + bucket_size
        
        return f"{bucket_start}-{bucket_end}"
    
    def calculate_trade_weight(
        self, 
        is_live: bool, 
        is_dry_run: bool, 
        trade_timestamp: datetime
    ) -> float:
        """
        Calcule le poids d'un trade pour la calibration.
        
        Args:
            is_live: True si trade live
            is_dry_run: True si trade dry-run
            trade_timestamp: Date/heure du trade
            
        Returns:
            Poids entre 0 et 1
        """
        config = self._get_config()
        
        # 1. Poids par type de trade
        if is_live and not is_dry_run:
            type_weight = config['live_weight']
        elif is_dry_run:
            type_weight = config['dryrun_weight']
        else:
            type_weight = 0.2  # Paper trading / backtest
        
        # 2. Poids par ancienneté (decay exponentiel)
        now = datetime.now(timezone.utc)
        if trade_timestamp.tzinfo is None:
            trade_timestamp = trade_timestamp.replace(tzinfo=timezone.utc)
        
        days_ago = (now - trade_timestamp).total_seconds() / 86400
        half_life = config['decay_days']
        
        # Decay exponentiel: weight = 0.5^(days_ago / half_life)
        age_weight = 0.5 ** (days_ago / half_life)
        
        return type_weight * age_weight
    
    def update_calibration(
        self,
        direction: str,
        ml_confidence: float,
        win: bool,
        pnl_pct: float,
        pnl_usdt: float,
        is_live: bool,
        is_dry_run: bool,
        trade_timestamp: datetime
    ) -> bool:
        """
        Met à jour les statistiques de calibration après un trade.
        
        Args:
            direction: 'LONG' ou 'SHORT'
            ml_confidence: Confiance ML du trade
            win: True si trade gagnant
            pnl_pct: PnL en %
            pnl_usdt: PnL en USDT
            is_live: True si trade live
            is_dry_run: True si dry-run
            trade_timestamp: Date/heure du trade
            
        Returns:
            True si mise à jour réussie
        """
        config = self._get_config()
        
        if not config['enabled']:
            return False
        
        # Ne prendre que les trades avec ML confidence valide
        if ml_confidence is None or ml_confidence < 30:
            logger.debug(f"Trade ignoré pour calibration: ml_confidence={ml_confidence}")
            return False
        
        # Calculer le bucket et le poids
        bucket = self.get_confidence_bucket(ml_confidence, config['bucket_size'])
        weight = self.calculate_trade_weight(is_live, is_dry_run, trade_timestamp)
        
        logger.info(
            f"Calibration update: {direction} {bucket} | "
            f"Win={win} | Weight={weight:.3f} | PnL={pnl_pct:.3f}%"
        )
        
        # Mise à jour en base
        pg_logger = self._get_db_pool()
        if not pg_logger:
            logger.debug("Pas de connexion DB pour calibration")
            return False
        
        try:
            conn = pg_logger.pool.getconn()
            try:
                with conn.cursor() as cur:
                    # Récupérer l'ancien winrate et stats avant mise à jour
                    cur.execute("""
                        SELECT actual_winrate, total_trades, weighted_total
                        FROM ml_calibration
                        WHERE direction = %s AND confidence_bucket = %s
                    """, (direction, bucket))
                    row = cur.fetchone()
                    old_winrate = float(row[0]) if row and row[0] else None
                    old_trades = row[1] if row else 0
                    
                    # Mise à jour
                    cur.execute("""
                        UPDATE ml_calibration
                        SET 
                            weighted_wins = weighted_wins + %s,
                            weighted_total = weighted_total + %s,
                            total_trades = total_trades + 1,
                            avg_pnl_pct = (avg_pnl_pct * total_trades + %s) / (total_trades + 1),
                            total_pnl_usdt = total_pnl_usdt + %s
                        WHERE direction = %s AND confidence_bucket = %s
                    """, (
                        weight if win else 0,  # weighted_wins
                        weight,                 # weighted_total
                        pnl_pct,               # pour avg_pnl_pct
                        pnl_usdt,              # total_pnl_usdt
                        direction,
                        bucket
                    ))
                    
                    # Récupérer le nouveau winrate après mise à jour
                    cur.execute("""
                        SELECT actual_winrate, total_trades, weighted_total
                        FROM ml_calibration
                        WHERE direction = %s AND confidence_bucket = %s
                    """, (direction, bucket))
                    row = cur.fetchone()
                    new_winrate = float(row[0]) if row and row[0] else 0
                    new_trades = row[1] if row else 0
                    new_weighted_total = float(row[2]) if row and row[2] else 0
                    
                    conn.commit()
                    
                    # Enregistrer dans l'historique si changement significatif
                    should_log = False
                    reason = "update"
                    
                    # 1. Premier trade avec ML confidence dans ce bucket
                    if old_trades == 0:
                        should_log = True
                        reason = "first_trade"
                    
                    # 2. Passage au seuil min_trades (phase apprentissage -> active)
                    elif old_trades < config['min_trades'] and new_trades >= config['min_trades']:
                        should_log = True
                        reason = "phase_active"
                    
                    # 3. Changement significatif de winrate (>5%)
                    elif old_winrate is not None and abs(new_winrate - old_winrate) >= 5.0:
                        should_log = True
                        reason = "significant_change"
                    
                    # 4. Tous les 10 trades (snapshot périodique)
                    elif new_trades % 10 == 0:
                        should_log = True
                        reason = f"snapshot_{new_trades}"
                    
                    if should_log:
                        self._log_to_history(
                            direction, bucket, old_winrate, new_winrate,
                            new_trades, new_weighted_total, reason
                        )
                    
            finally:
                pg_logger.pool.putconn(conn)
                    
            # Invalider le cache
            self._cache_timestamp = None
            
            logger.info(f"[OK] Calibration mise a jour: {direction} {bucket}")
            return True
            
        except Exception as e:
            logger.error(f"[ERR] Erreur mise a jour calibration: {e}")
            return False
    
    def _log_to_history(
        self,
        direction: str,
        bucket: str,
        old_winrate: Optional[float],
        new_winrate: float,
        total_trades: int,
        weighted_total: float,
        reason: str = "update"
    ) -> bool:
        """
        Enregistre un changement dans l'historique de calibration.
        
        Args:
            direction: LONG ou SHORT
            bucket: Bucket de confiance
            old_winrate: Ancien winrate (None si premier)
            new_winrate: Nouveau winrate
            total_trades: Nombre de trades
            weighted_total: Total pondéré
            reason: Raison (update, reset, significant_change, etc.)
        """
        pg_logger = self._get_db_pool()
        if not pg_logger:
            return False
        
        try:
            conn = pg_logger.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO ml_calibration_history 
                        (direction, confidence_bucket, old_winrate, new_winrate, 
                         total_trades, weighted_total, reason, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        direction, bucket, old_winrate, new_winrate,
                        total_trades, weighted_total, reason
                    ))
                    conn.commit()
                    logger.debug(f"[HISTORY] {direction} {bucket}: {old_winrate} -> {new_winrate} ({reason})")
                    return True
            finally:
                pg_logger.pool.putconn(conn)
        except Exception as e:
            logger.warning(f"[WARN] Erreur log historique: {e}")
            return False

    def get_calibrated_winrate(
        self, 
        direction: str, 
        ml_confidence: float
    ) -> Optional[float]:
        """
        Récupère le winrate réel calibré pour une direction et confiance.
        
        Args:
            direction: 'LONG' ou 'SHORT'
            ml_confidence: Confiance ML
            
        Returns:
            Winrate réel (%) ou None si pas assez de données
        """
        config = self._get_config()
        bucket = self.get_confidence_bucket(ml_confidence, config['bucket_size'])
        
        stats = self._get_stats(direction, bucket)
        if not stats:
            logger.debug(f"[CALIB DEBUG] No stats for {direction} {bucket}")
            return None
        
        # Vérifier minimum de trades
        if stats.weighted_total < config['min_trades']:
            logger.debug(
                f"Pas assez de trades pour calibration: {direction} {bucket} "
                f"({stats.total_trades} trades, {stats.weighted_total:.1f} < {config['min_trades']} pondéré)"
            )
            return None
        
        logger.debug(f"[CALIB DEBUG] Returning WR {stats.actual_winrate} (Total {stats.weighted_total} >= {config['min_trades']})")
        return stats.actual_winrate
    
    def should_take_trade(
        self, 
        direction: str, 
        ml_confidence: float
    ) -> Tuple[bool, Optional[float], str]:
        """
        Détermine si un trade doit être pris selon la calibration.
        
        Args:
            direction: 'LONG' ou 'SHORT'
            ml_confidence: Confiance ML
            
        Returns:
            Tuple (should_take, calibrated_winrate, reason)
        """
        config = self._get_config()
        
        if not config['enabled']:
            return True, None, "calibration_disabled"
        
        if ml_confidence is None or ml_confidence < 30:
            return True, None, "no_ml_confidence"
        
        calibrated_wr = self.get_calibrated_winrate(direction, ml_confidence)
        
        if calibrated_wr is None:
            return True, None, "learning_phase"
        
        bucket = self.get_confidence_bucket(ml_confidence, config['bucket_size'])
        min_wr = config['min_winrate']
        
        if calibrated_wr >= min_wr:
            logger.info(
                f"✅ Trade accepté (calibration): {direction} {bucket} | "
                f"WR réel={calibrated_wr:.1f}% >= seuil {min_wr}%"
            )
            return True, calibrated_wr, "accepted"
        else:
            logger.warning(
                f"🚫 Trade rejeté (calibration): {direction} {bucket} | "
                f"WR réel={calibrated_wr:.1f}% < seuil {min_wr}%"
            )
            return False, calibrated_wr, "rejected_low_winrate"
    
    def _get_stats(self, direction: str, bucket: str) -> Optional[CalibrationStats]:
        """Récupère les stats d'un bucket (avec cache)"""
        self._refresh_cache_if_needed()
        
        key = (direction, bucket)
        return self._cache.get(key)
    
    def _refresh_cache_if_needed(self):
        """Refresh le cache si nécessaire"""
        now = datetime.now(timezone.utc)
        
        if self._cache_timestamp and \
           (now - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds:
            return
        
        pg_logger = self._get_db_pool()
        if not pg_logger:
            return
        
        try:
            conn = pg_logger.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT direction, confidence_bucket, 
                               weighted_wins, weighted_total, total_trades,
                               actual_winrate, avg_pnl_pct, total_pnl_usdt
                        FROM ml_calibration
                    """)
                    rows = cur.fetchall()
            finally:
                pg_logger.pool.putconn(conn)
                    
            self._cache = {}
            for row in rows:
                stats = CalibrationStats(
                    direction=row[0],
                    confidence_bucket=row[1],
                    weighted_wins=float(row[2]) if row[2] is not None else 0.0,
                    weighted_total=float(row[3]) if row[3] is not None else 0.0,
                    total_trades=row[4] or 0,
                    actual_winrate=float(row[5]) if row[5] is not None else 0.0,
                    avg_pnl_pct=float(row[6]) if row[6] is not None else 0.0,
                    total_pnl_usdt=float(row[7]) if row[7] is not None else 0.0,
                )
                self._cache[(stats.direction, stats.confidence_bucket)] = stats
            
            self._cache_timestamp = now
            logger.debug(f"Cache calibration rafraîchi: {len(self._cache)} buckets")
            
        except Exception as e:
            logger.error(f"Erreur refresh cache calibration: {e}")
    
    def get_all_stats(self) -> Dict[str, Dict[str, CalibrationStats]]:
        """
        Récupère toutes les statistiques de calibration.
        
        Returns:
            Dict {direction: {bucket: stats}}
        """
        self._refresh_cache_if_needed()
        
        result = {'LONG': {}, 'SHORT': {}}
        for (direction, bucket), stats in self._cache.items():
            result[direction][bucket] = stats
        
        return result
    
    def reset_calibration(self, reason: str = "manual_reset") -> bool:
        """
        Remet à zéro toutes les statistiques de calibration.
        
        Args:
            reason: Raison du reset (pour historique)
            
        Returns:
            True si réussi
        """
        pg_logger = self._get_db_pool()
        if not pg_logger:
            return False
        
        try:
            conn = pg_logger.pool.getconn()
            try:
                with conn.cursor() as cur:
                    # Sauvegarder dans l'historique avant reset
                    try:
                        cur.execute("""
                            INSERT INTO ml_calibration_history 
                            (direction, confidence_bucket, old_winrate, new_winrate, 
                             total_trades, weighted_total, reason, created_at)
                            SELECT direction, confidence_bucket, actual_winrate, 0,
                                   total_trades, weighted_total, %s, NOW()
                            FROM ml_calibration
                            WHERE total_trades > 0
                        """, (reason,))
                        logger.info(f"[HISTORY] Snapshot avant reset ({reason})")
                    except Exception as e:
                        logger.warning(f"[WARN] Erreur log historique reset: {e}")
                    
                    # Reset
                    cur.execute("""
                        UPDATE ml_calibration
                        SET 
                            weighted_wins = 0,
                            weighted_total = 0,
                            total_trades = 0,
                            actual_winrate = NULL,
                            avg_pnl_pct = 0,
                            total_pnl_usdt = 0,
                            updated_at = NOW()
                    """)
                    conn.commit()
            finally:
                pg_logger.pool.putconn(conn)
            
            # Invalider cache
            self._cache = {}
            self._cache_timestamp = None
            
            logger.info(f"[RESET] Calibration resetee: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"[ERR] Erreur reset calibration: {e}")
            return False
    
    def seed_from_historical_trades(self, days: int = 30) -> int:
        """
        Initialise la calibration à partir des trades historiques.
        
        Args:
            days: Nombre de jours à considérer
            
        Returns:
            Nombre de trades traités
        """
        pg_logger = self._get_db_pool()
        if not pg_logger:
            return 0
        
        try:
            conn = pg_logger.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(f"""
                        SELECT 
                            direction,
                            ml_confidence,
                            win,
                            net_pnl_pct,
                            net_pnl_usdt,
                            is_live_trade,
                            is_dry_run,
                            timestamp_entry
                        FROM trades
                        WHERE timestamp_entry >= NOW() - INTERVAL '{days} days'
                          AND ml_confidence IS NOT NULL
                          AND ml_confidence >= 30
                          AND timestamp_exit IS NOT NULL
                        ORDER BY timestamp_entry
                    """)
                    rows = cur.fetchall()
            finally:
                pg_logger.pool.putconn(conn)
            
            count = 0
            for row in rows:
                direction, ml_conf, win, pnl_pct, pnl_usdt, is_live, is_dry, ts = row
                
                if ml_conf and direction:
                    self.update_calibration(
                        direction=direction,
                        ml_confidence=float(ml_conf),
                        win=win or False,
                        pnl_pct=float(pnl_pct) if pnl_pct else 0,
                        pnl_usdt=float(pnl_usdt) if pnl_usdt else 0,
                        is_live=is_live or False,
                        is_dry_run=is_dry or False,
                        trade_timestamp=ts
                    )
                    count += 1
            
            logger.info(f"📊 Calibration seedée avec {count} trades des {days} derniers jours")
            return count
            
        except Exception as e:
            logger.error(f"❌ Erreur seed calibration: {e}")
            return 0


# Instance globale
_calibration_manager: Optional[MLCalibrationManager] = None


def get_calibration_manager() -> MLCalibrationManager:
    """Récupère l'instance globale du gestionnaire de calibration"""
    global _calibration_manager
    if _calibration_manager is None:
        _calibration_manager = MLCalibrationManager()
    return _calibration_manager

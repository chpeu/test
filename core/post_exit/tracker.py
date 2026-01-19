"""
PostExitTracker - Suivi des prix après clôture d'un trade
Trade Cursor v7.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class PostExitSample:
    """Un échantillon de prix post-exit"""
    timestamp: datetime
    price: float
    pnl_vs_exit_pct: float
    cumulative_mfe_pct: float
    cumulative_mae_pct: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'pnl_vs_exit_pct': self.pnl_vs_exit_pct,
            'cumulative_mfe_pct': self.cumulative_mfe_pct,
            'cumulative_mae_pct': self.cumulative_mae_pct
        }


@dataclass
class PostExitTracker:
    """Tracker pour un trade fermé - collecte les prix post-exit"""
    
    # Identifiants
    trade_id: int
    symbol: str
    direction: str  # LONG ou SHORT
    
    # Contexte de sortie
    exit_price: float
    exit_timestamp: datetime
    exit_reason: str
    realized_pnl_pct: float
    realized_pnl_usdt: float
    
    # Niveaux originaux (pour analyse would_have_hit)
    original_sl: float
    original_tp: float
    entry_price: float
    
    # Params utilisés
    used_sl_pct: Optional[float] = None
    used_tp_pct: Optional[float] = None
    used_be_trigger: Optional[float] = None
    used_trailing_trigger: Optional[float] = None
    used_trailing_min_distance: Optional[float] = None
    used_partial_tp_pct: Optional[float] = None
    
    # Configuration
    tracking_duration_sec: int = 300
    sample_interval_ms: int = 1000
    
    # State
    samples: List[PostExitSample] = field(default_factory=list)
    is_active: bool = True
    start_time: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    last_sample_time: float = 0.0
    
    # Métriques calculées (mises à jour à chaque sample)
    post_exit_mfe_pct: float = 0.0
    post_exit_mfe_price: Optional[float] = None
    post_exit_mfe_timestamp: Optional[datetime] = None
    
    post_exit_mae_pct: float = 0.0
    post_exit_mae_price: Optional[float] = None
    post_exit_mae_timestamp: Optional[datetime] = None
    
    # Flags
    would_have_hit_original_tp: bool = False
    would_have_hit_original_sl: bool = False
    price_returned_to_entry: bool = False
    
    def add_sample(self, price: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Ajouter un échantillon de prix
        
        Returns:
            True si sample ajouté, False si ignoré (interval trop court ou tracking terminé)
        """
        if not self.is_active:
            return False
        
        ts = timestamp or datetime.now(timezone.utc)
        current_time = ts.timestamp()
        
        # Vérifier interval minimum entre samples
        if self.last_sample_time > 0:
            elapsed_since_last = (current_time - self.last_sample_time) * 1000  # en ms
            if elapsed_since_last < self.sample_interval_ms * 0.9:  # 10% de tolérance
                return False
        
        # Calculer PnL vs exit
        if self.direction == "LONG":
            pnl_vs_exit = (price - self.exit_price) / self.exit_price * 100
        else:
            pnl_vs_exit = (self.exit_price - price) / self.exit_price * 100
        
        # Update MFE (favorable = profit supplémentaire)
        if pnl_vs_exit > self.post_exit_mfe_pct:
            self.post_exit_mfe_pct = pnl_vs_exit
            self.post_exit_mfe_price = price
            self.post_exit_mfe_timestamp = ts
        
        # Update MAE (adverse = mouvement contre nous)
        if pnl_vs_exit < 0 and abs(pnl_vs_exit) > self.post_exit_mae_pct:
            self.post_exit_mae_pct = abs(pnl_vs_exit)
            self.post_exit_mae_price = price
            self.post_exit_mae_timestamp = ts
        
        # Vérifier flags
        if not self.would_have_hit_original_tp:
            if self.direction == "LONG" and price >= self.original_tp:
                self.would_have_hit_original_tp = True
            elif self.direction == "SHORT" and price <= self.original_tp:
                self.would_have_hit_original_tp = True
        
        if not self.would_have_hit_original_sl:
            if self.direction == "LONG" and price <= self.original_sl:
                self.would_have_hit_original_sl = True
            elif self.direction == "SHORT" and price >= self.original_sl:
                self.would_have_hit_original_sl = True
        
        if not self.price_returned_to_entry:
            entry_tolerance = self.entry_price * 0.0005  # 0.05% tolérance
            if abs(price - self.entry_price) <= entry_tolerance:
                self.price_returned_to_entry = True
        
        # Créer sample
        sample = PostExitSample(
            timestamp=ts,
            price=price,
            pnl_vs_exit_pct=round(pnl_vs_exit, 4),
            cumulative_mfe_pct=round(self.post_exit_mfe_pct, 4),
            cumulative_mae_pct=round(self.post_exit_mae_pct, 4)
        )
        self.samples.append(sample)
        self.last_sample_time = current_time
        
        # Vérifier si tracking terminé
        elapsed = current_time - self.start_time
        if elapsed >= self.tracking_duration_sec:
            self.is_active = False
            logger.debug(f"📊 PostExit {self.symbol}: Tracking terminé après {elapsed:.0f}s ({len(self.samples)} samples)")
        
        return True
    
    def compute_final_metrics(self) -> Dict[str, Any]:
        """Calculer les métriques finales après tracking"""
        if not self.samples:
            return {}
        
        final_sample = self.samples[-1]
        
        # Exit efficiency: realized / (realized + missed)
        # Si realized est négatif (perte), on calcule différemment
        if self.realized_pnl_pct >= 0:
            total_potential = self.realized_pnl_pct + self.post_exit_mfe_pct
            exit_efficiency = (self.realized_pnl_pct / total_potential * 100) if total_potential > 0 else 100.0
        else:
            # Pour les trades perdants, efficiency = 100% si on aurait perdu plus en tenant
            if self.post_exit_mae_pct > abs(self.realized_pnl_pct):
                exit_efficiency = 100.0  # Bonne décision de sortir
            else:
                # On aurait pu perdre moins ou même gagner
                exit_efficiency = max(0, 50 - self.post_exit_mfe_pct * 10)  # Pénalité
        
        exit_efficiency = max(0, min(100, exit_efficiency))
        
        # Time to MFE
        time_to_mfe = None
        if self.post_exit_mfe_timestamp:
            time_to_mfe = int(self.post_exit_mfe_timestamp.timestamp() - self.start_time)
        
        # Regret (PnL manqué)
        regret_pct = self.post_exit_mfe_pct
        regret_usdt = 0.0
        if self.realized_pnl_pct != 0 and regret_pct > 0:
            regret_usdt = regret_pct * abs(self.realized_pnl_usdt) / abs(self.realized_pnl_pct)
        
        # Exit timing grade
        if exit_efficiency >= 90:
            grade = "A+"
        elif exit_efficiency >= 80:
            grade = "A"
        elif exit_efficiency >= 70:
            grade = "B+"
        elif exit_efficiency >= 60:
            grade = "B"
        elif exit_efficiency >= 50:
            grade = "C"
        elif exit_efficiency >= 40:
            grade = "D"
        else:
            grade = "F"
        
        # ML Targets
        ml_optimal_sl_pct = self._compute_optimal_sl()
        ml_optimal_trailing_trigger = self._compute_optimal_trailing_trigger()
        ml_optimal_be_trigger = self._compute_optimal_be_trigger()
        
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "direction": self.direction,
            
            # Contexte sortie
            "exit_price": self.exit_price,
            "exit_timestamp": self.exit_timestamp.isoformat() if isinstance(self.exit_timestamp, datetime) else self.exit_timestamp,
            "exit_reason": self.exit_reason,
            "realized_pnl_pct": round(self.realized_pnl_pct, 4),
            "realized_pnl_usdt": round(self.realized_pnl_usdt, 4),
            
            # Params utilisés
            "used_sl_pct": self.used_sl_pct,
            "used_tp_pct": self.used_tp_pct,
            "used_be_trigger": self.used_be_trigger,
            "used_trailing_trigger": self.used_trailing_trigger,
            "used_trailing_min_distance": self.used_trailing_min_distance,
            "used_partial_tp_pct": self.used_partial_tp_pct,
            
            # Config tracking
            "tracking_duration_sec": self.tracking_duration_sec,
            "sample_count": len(self.samples),
            "sample_interval_ms": self.sample_interval_ms,
            
            # MFE post-exit
            "post_exit_mfe_pct": round(self.post_exit_mfe_pct, 4),
            "post_exit_mfe_price": self.post_exit_mfe_price,
            "post_exit_mfe_timestamp": self.post_exit_mfe_timestamp.isoformat() if self.post_exit_mfe_timestamp else None,
            "time_to_mfe_sec": time_to_mfe,
            
            # MAE post-exit
            "post_exit_mae_pct": round(self.post_exit_mae_pct, 4),
            "post_exit_mae_price": self.post_exit_mae_price,
            "post_exit_mae_timestamp": self.post_exit_mae_timestamp.isoformat() if self.post_exit_mae_timestamp else None,
            
            # Final
            "post_exit_final_pct": round(final_sample.pnl_vs_exit_pct, 4),
            "post_exit_final_price": final_sample.price,
            
            # Métriques dérivées
            "exit_efficiency_pct": round(exit_efficiency, 2),
            "regret_pct": round(regret_pct, 4),
            "regret_usdt": round(regret_usdt, 4),
            "exit_timing_grade": grade,
            
            # Flags
            "would_have_hit_original_tp": self.would_have_hit_original_tp,
            "would_have_hit_original_sl": self.would_have_hit_original_sl,
            "price_returned_to_entry": self.price_returned_to_entry,
            
            # ML Targets
            "ml_optimal_sl_pct": ml_optimal_sl_pct,
            "ml_optimal_trailing_trigger": ml_optimal_trailing_trigger,
            "ml_optimal_be_trigger": ml_optimal_be_trigger,
            "ml_should_use_partial": self.would_have_hit_original_tp and self.post_exit_mfe_pct > 0.1,
        }
    
    def _compute_optimal_sl(self) -> Optional[float]:
        """Calculer le SL optimal basé sur les données post-exit"""
        if self.realized_pnl_pct >= 0:
            # Trade gagnant: SL optimal = max(used_sl, post_exit_mae * 1.1)
            if self.used_sl_pct and self.post_exit_mae_pct > 0:
                return round(max(self.used_sl_pct, self.post_exit_mae_pct * 1.1), 4)
            return self.used_sl_pct
        else:
            # Trade perdant: si on aurait pu gagner, SL était peut-être trop serré
            if self.post_exit_mfe_pct > 0.1:  # Aurait pu récupérer
                return round(self.post_exit_mae_pct * 1.2, 4) if self.post_exit_mae_pct > 0 else None
            return self.used_sl_pct
    
    def _compute_optimal_trailing_trigger(self) -> Optional[float]:
        """Calculer le trailing trigger optimal"""
        if self.realized_pnl_pct <= 0:
            return None
        
        # Si MFE post-exit atteint rapidement (< 60s), trailing trigger devrait être plus bas
        if self.post_exit_mfe_timestamp and self.post_exit_mfe_pct > 0.05:
            time_to_mfe = self.post_exit_mfe_timestamp.timestamp() - self.start_time
            if time_to_mfe < 60:
                # Prix a continué vite dans notre direction -> on aurait dû tenir
                return round(self.realized_pnl_pct * 0.7, 4)
        
        return self.used_trailing_trigger
    
    def _compute_optimal_be_trigger(self) -> Optional[float]:
        """Calculer le BE trigger optimal"""
        # Si le trade est revenu à l'entrée après notre sortie, BE était bon
        if self.price_returned_to_entry:
            return self.used_be_trigger
        
        # Si on a eu un bon MFE post-exit sans revenir à entry, BE était peut-être trop tôt
        if self.post_exit_mfe_pct > 0.15 and not self.would_have_hit_original_sl:
            return round((self.used_be_trigger or 0.2) * 1.3, 4)
        
        return self.used_be_trigger
    
    def get_samples_for_db(self) -> List[Dict[str, Any]]:
        """Retourner les samples formatés pour insertion DB"""
        return [
            {
                "trade_id": self.trade_id,
                "sample_index": i,
                "timestamp": s.timestamp,
                "price": s.price,
                "pnl_vs_exit_pct": s.pnl_vs_exit_pct,
                "cumulative_mfe_pct": s.cumulative_mfe_pct,
                "cumulative_mae_pct": s.cumulative_mae_pct
            }
            for i, s in enumerate(self.samples)
        ]

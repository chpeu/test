"""
Market Regime Selector - Sprint 1
Détecte le régime de marché (CALME, NORMAL, VOLATILE) basé sur ATR live
et charge dynamiquement la configuration optimale.

Auteur: Cascade AI
Date: 07/12/2025
"""

import logging
import json
import asyncio
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict, fields
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Régimes de marché possibles"""
    CALME = "CALME"
    NORMAL = "NORMAL"
    VOLATILE = "VOLATILE"
    CHOPPY = "CHOPPY"  # Optionnel pour Sprint 2
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeConfig:
    """Configuration associée à un régime"""
    name: str
    optimal_atr_min: float  # ATR 1m min
    optimal_atr_max: float  # ATR 1m max
    min_score_required: float
    atr_mult_sl: float
    atr_mult_tp: float
    break_even_atr_mult: float
    trailing_trigger_atr_mult: float
    max_position_time: int  # secondes
    volume_multiplier: float = 1.0
    sl_exchange_percent: float = 0.30  # SL MEXC fixe par régime
    # Paramètres stagnation par régime
    stagnation_timeout: int = 120  # secondes avant sortie stagnation
    stagnation_min_pnl: float = 0.05  # PnL% minimum pour rester
    stagnation_max_loss: float = -0.08  # PnL% max loss avant sortie
    # 🔥 ATR 5m avec valeurs par défaut (compatibilité DB)
    optimal_atr_min_5m: float = 0.15  # ATR 5m min par défaut
    optimal_atr_max_5m: float = 0.80  # ATR 5m max par défaut
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RegimeChange:
    """Historique d'un changement de régime"""
    timestamp: datetime
    old_regime: str
    new_regime: str
    avg_atr: float
    avg_adx: float
    trigger: str  # "auto" ou "manual"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "old_regime": self.old_regime,
            "new_regime": self.new_regime,
            "avg_atr": self.avg_atr,
            "avg_adx": self.avg_adx,
            "trigger": self.trigger
        }


# 🔥 FIX 08/12/2025: Configurations par régime ajustées selon analyse du jour
# CALME: 35.7% WR avec score=6.0 → TROP BAS, augmenté à 8.5
# NORMAL: 75% WR avec score=7.0 → OK, légèrement augmenté
# VOLATILE: bon ratio, ajusté pour capture momentum
# CHOPPY: 100% WR (3 trades) → strict OK
# 🔥 FIX 08/12/2025: Seuils PLUS STRICTS pour filtrer les mauvais trades
# CALME: Peu de mouvement = exiger score très élevé
# NORMAL: Score 8+ pour qualité
# VOLATILE: Mouvements clairs = signaux fiables, score légèrement réduit
# CHOPPY: Pas de tendance = très strict
DEFAULT_REGIME_CONFIGS: Dict[str, RegimeConfig] = {
    "CALME": RegimeConfig(
        name="CALME",
        optimal_atr_min=0.05,
        optimal_atr_max=0.20,
        optimal_atr_min_5m=0.10,  # 🔥 ATR 5m adapté au calme
        optimal_atr_max_5m=0.35,  # 🔥 ATR 5m adapté au calme
        min_score_required=8.5,
        atr_mult_sl=0.8,
        atr_mult_tp=1.8,
        break_even_atr_mult=0.8,
        trailing_trigger_atr_mult=1.0,
        max_position_time=180,
        volume_multiplier=0.7,  # 🔥 Optimisé: 0.7 (winrate 41.2% vs 40.9% à 1.0)
        sl_exchange_percent=0.25,
        stagnation_timeout=360,
        stagnation_min_pnl=0.05,
        stagnation_max_loss=-0.08
    ),
    "NORMAL": RegimeConfig(
        name="NORMAL",
        optimal_atr_min=0.15,
        optimal_atr_max=0.40,
        optimal_atr_min_5m=0.20,  # 🔥 ATR 5m adapté au normal
        optimal_atr_max_5m=0.60,  # 🔥 ATR 5m adapté au normal
        min_score_required=8.0,
        atr_mult_sl=1.2,
        atr_mult_tp=2.2,
        break_even_atr_mult=1.2,
        trailing_trigger_atr_mult=1.5,
        max_position_time=240,
        volume_multiplier=0.8,  # 🔥 Optimisé: 0.8 (winrate 41.8% vs 40.6% à 1.1)
        sl_exchange_percent=0.30,
        stagnation_timeout=480,
        stagnation_min_pnl=0.04,
        stagnation_max_loss=-0.10
    ),
    "VOLATILE": RegimeConfig(
        name="VOLATILE",
        optimal_atr_min=0.30,
        optimal_atr_max=1.5,
        optimal_atr_min_5m=0.40,  # 🔥 ATR 5m adapté au volatile
        optimal_atr_max_5m=2.0,   # 🔥 ATR 5m adapté au volatile
        min_score_required=7.5,
        atr_mult_sl=1.5,
        atr_mult_tp=2.5,
        break_even_atr_mult=1.5,
        trailing_trigger_atr_mult=2.0,
        max_position_time=180,
        volume_multiplier=1.2,  # 🔥 Optimisé: 1.2 (100% winrate maintenu, plus de trades)
        sl_exchange_percent=0.35,
        stagnation_timeout=600,
        stagnation_min_pnl=0.02,
        stagnation_max_loss=-0.12
    ),
    "CHOPPY": RegimeConfig(
        name="CHOPPY",
        optimal_atr_min=0.05,
        optimal_atr_max=0.25,
        optimal_atr_min_5m=0.10,  # 🔥 ATR 5m adapté au choppy
        optimal_atr_max_5m=0.40,  # 🔥 ATR 5m adapté au choppy
        min_score_required=10.0,
        atr_mult_sl=0.7,
        atr_mult_tp=1.5,
        break_even_atr_mult=0.5,
        trailing_trigger_atr_mult=0.8,
        max_position_time=60,
        volume_multiplier=0.7,  # 🔥 Optimisé: 0.7 (winrate 44.4% vs 40% à 0.8)
        sl_exchange_percent=0.20,
        stagnation_timeout=180,
        stagnation_min_pnl=0.08,
        stagnation_max_loss=-0.05
    )
}


class MarketRegimeSelector:
    """
    Sélecteur de régime de marché basé sur ATR live.
    
    Fonctionnalités:
    - Calcul ATR moyen sur top pairs
    - Détection automatique du régime
    - Chargement config optimale par régime
    - Historique des changements
    - API pour frontend
    """
    
    def __init__(
        self,
        config_dir: Optional[Path] = None,
        check_interval_minutes: int = 60,
        atr_sample_size: int = 10
    ):
        """
        Initialise le sélecteur de régime.
        
        Args:
            config_dir: Répertoire des configs par régime
            check_interval_minutes: Intervalle entre les vérifications auto
            atr_sample_size: Nombre de paires à analyser pour ATR moyen
        """
        self.config_dir = config_dir or Path("config/regimes")
        self.check_interval = timedelta(minutes=check_interval_minutes)
        self.atr_sample_size = atr_sample_size
        
        # État actuel
        self.current_regime: MarketRegime = MarketRegime.UNKNOWN
        self.current_config: Optional[RegimeConfig] = None
        self.last_check: Optional[datetime] = None
        self.next_check: Optional[datetime] = None
        self.regime_since: Optional[datetime] = None
        
        # Métriques
        self.avg_atr: float = 0.0
        self.avg_adx: float = 0.0
        self.atr_values: List[float] = []
        self.atr_sample_count: int = 0  # 🔥 FIX: Compteur pour widget Samples
        
        # Historique
        self.history: List[RegimeChange] = []
        self.max_history_size: int = 100
        
        # Configs chargées
        self.regime_configs: Dict[str, RegimeConfig] = DEFAULT_REGIME_CONFIGS.copy()
        
        # Callbacks
        self._on_regime_change_callbacks: List[callable] = []
        
        # 🔥 PHASE 1B: Attributs V2 pour médiane, smoothing, hystérésis
        self.last_atr_median: Optional[float] = None
        self.last_atr_smoothed: Optional[float] = None
        self.last_outliers_count: int = 0
        self.hysteresis_was_applied: bool = False
        self._ema_value: Optional[float] = None

        self._calibration_task = None
        self._last_calibration_attempt: Optional[datetime] = None
        
        # Initialiser
        self._load_regime_configs()
        logger.info("✅ MarketRegimeSelector initialisé")
    
    def _load_regime_configs(self) -> None:
        """Charge les configurations depuis les fichiers JSON"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        for regime_name in ["CALME", "NORMAL", "VOLATILE", "CHOPPY"]:
            config_file = self.config_dir / f"{regime_name.lower()}.json"
            
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        data = json.load(f)
                        # 🔥 FIX: Fusionner avec valeurs par défaut pour compatibilité
                        default_config = DEFAULT_REGIME_CONFIGS.get(regime_name)
                        updated = False
                        if default_config:
                            default_data = default_config.to_dict()
                            # Ajouter les clés manquantes depuis les defaults
                            for key, value in default_data.items():
                                if key not in data:
                                    data[key] = value
                                    updated = True
                                    logger.info(f"⚙️ Ajout paramètre manquant {key}={value} pour {regime_name}")
                        # 🔥 FIX: Filtrer les clés obsolètes (ex: rsi_filter_mode supprimé)
                        valid_keys = {f.name for f in fields(RegimeConfig)}
                        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                        # Supprimer les clés obsolètes du fichier
                        if len(filtered_data) < len(data):
                            obsolete_keys = set(data.keys()) - valid_keys
                            logger.info(f"🗑️ Suppression clés obsolètes {obsolete_keys} pour {regime_name}")
                            data = filtered_data
                            updated = True
                        self.regime_configs[regime_name] = RegimeConfig(**filtered_data)
                        # Sauvegarder si des paramètres ont été ajoutés
                        if updated:
                            with open(config_file, 'w') as fw:
                                json.dump(data, fw, indent=2)
                            logger.info(f"💾 Config régime {regime_name} mise à jour avec nouveaux paramètres")
                        logger.debug(f"✅ Config régime {regime_name} chargée depuis {config_file}")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur chargement config {regime_name}: {e}")
            else:
                # Créer le fichier avec valeurs par défaut
                try:
                    with open(config_file, 'w') as f:
                        json.dump(self.regime_configs[regime_name].to_dict(), f, indent=2)
                    logger.info(f"📝 Config régime {regime_name} créée: {config_file}")
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de créer config {regime_name}: {e}")
    
    def save_regime_config(self, regime_name: str) -> bool:
        """Sauvegarde la configuration d'un régime"""
        if regime_name not in self.regime_configs:
            return False
        
        config_file = self.config_dir / f"{regime_name.lower()}.json"
        try:
            with open(config_file, 'w') as f:
                json.dump(self.regime_configs[regime_name].to_dict(), f, indent=2)
            logger.info(f"💾 Config régime {regime_name} sauvegardée")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde config {regime_name}: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # 🔥 PHASE 1B: Méthodes V2 (médiane, smoothing, hystérésis)
    # ═══════════════════════════════════════════════════════════════════════
    
    def calculate_atr_metric(self, atr_values: List[float]) -> float:
        """
        Calcule la métrique ATR selon la config V2.
        
        Features:
        - Filtrage des outliers (si activé)
        - Médiane au lieu de moyenne (si activé)
        
        Returns:
            ATR calculé (médiane ou moyenne selon config)
        """
        from utils.config_persistence import get_config_value
        
        use_median = get_config_value('market_regime_use_median', False)
        outlier_filter = get_config_value('market_regime_outlier_filter', True)
        outlier_threshold = get_config_value('market_regime_outlier_std_threshold', 2.5)
        
        values = atr_values.copy()
        self.last_outliers_count = 0
        
        # Filtrer les outliers si activé et assez de données
        if outlier_filter and len(values) >= 5:
            mean = statistics.mean(values)
            try:
                std = statistics.stdev(values)
                if std > 0:
                    original_count = len(values)
                    values = [v for v in values if abs(v - mean) <= outlier_threshold * std]
                    self.last_outliers_count = original_count - len(values)
                    
                    if self.last_outliers_count > 0:
                        logger.debug(
                            f"🔍 Outliers filtrés: {self.last_outliers_count} paires exclues "
                            f"(seuil: {outlier_threshold}σ)"
                        )
            except statistics.StatisticsError:
                pass  # Pas assez de variance
        
        # Fallback si tout filtré
        if not values:
            values = atr_values
        
        # Calcul final
        if use_median:
            result = statistics.median(values)
            self.last_atr_median = result
            logger.debug(f"📊 ATR Médian: {result:.4f}% (n={len(values)})")
        else:
            result = sum(values) / len(values)
            self.last_atr_median = None
            logger.debug(f"📊 ATR Moyen: {result:.4f}% (n={len(values)})")
        
        return result
    
    def apply_smoothing(self, new_value: float) -> float:
        """
        Applique un lissage EMA pour stabiliser les changements.
        
        Formula: EMA = α × new + (1-α) × previous
        
        Returns:
            Valeur lissée (ou brute si smoothing désactivé)
        """
        from utils.config_persistence import get_config_value
        
        use_smoothing = get_config_value('market_regime_use_smoothing', False)
        alpha = get_config_value('market_regime_smoothing_alpha', 0.3)
        
        if not use_smoothing:
            self.last_atr_smoothed = new_value
            return new_value
        
        # Initialisation au premier appel
        if self._ema_value is None:
            self._ema_value = new_value
            self.last_atr_smoothed = new_value
            logger.debug(f"📈 EMA initialisé: {new_value:.4f}%")
            return new_value
        
        # Calcul EMA
        smoothed = alpha * new_value + (1 - alpha) * self._ema_value
        self._ema_value = smoothed
        self.last_atr_smoothed = smoothed
        
        logger.debug(
            f"📈 Lissage EMA: brut={new_value:.4f}% → lissé={smoothed:.4f}% (α={alpha})"
        )
        
        return smoothed
    
    def should_change_regime(
        self,
        current: MarketRegime,
        proposed: MarketRegime,
        atr_value: float
    ) -> bool:
        """
        Applique l'hystérésis pour éviter le flip-flop.
        
        Avec buffer 10%:
        - CALME→NORMAL: ATR > 0.22 (pas 0.20)
        - NORMAL→CALME: ATR < 0.18 (pas 0.20)
        
        Returns:
            True si le changement doit être appliqué
        """
        from utils.config_persistence import get_config_value
        
        use_hysteresis = get_config_value('market_regime_use_hysteresis', False)
        buffer = get_config_value('market_regime_hysteresis_buffer', 0.10)
        
        self.hysteresis_was_applied = False
        
        if not use_hysteresis:
            return current != proposed
        
        if current == proposed:
            return False
        
        # Seuils de base
        threshold_calme = get_config_value('market_regime_atr_calme_max', 0.20)
        threshold_normal = get_config_value('market_regime_atr_normal_max', 0.40)
        
        # Map des transitions avec seuils bufferisés
        transitions = {
            # Montées (plus difficile)
            (MarketRegime.CALME, MarketRegime.NORMAL): (threshold_calme * (1 + buffer), '>'),
            (MarketRegime.NORMAL, MarketRegime.VOLATILE): (threshold_normal * (1 + buffer), '>'),
            (MarketRegime.CALME, MarketRegime.VOLATILE): (threshold_normal * (1 + buffer), '>'),
            
            # Descentes (plus difficile)
            (MarketRegime.NORMAL, MarketRegime.CALME): (threshold_calme * (1 - buffer), '<'),
            (MarketRegime.VOLATILE, MarketRegime.NORMAL): (threshold_normal * (1 - buffer), '<'),
            (MarketRegime.VOLATILE, MarketRegime.CALME): (threshold_calme * (1 - buffer), '<'),
        }
        
        key = (current, proposed)
        if key not in transitions:
            return True  # Transition non définie → autoriser
        
        threshold_with_buffer, direction = transitions[key]
        
        # Vérifier si le seuil bufferisé est franchi
        if direction == '>':
            should_change = atr_value > threshold_with_buffer
        else:
            should_change = atr_value < threshold_with_buffer
        
        # Logger si bloqué par hystérésis
        if not should_change and current != proposed:
            self.hysteresis_was_applied = True
            logger.info(
                f"🚫 Hystérésis: {current.value}→{proposed.value} BLOQUÉ | "
                f"ATR={atr_value:.3f}% {direction} {threshold_with_buffer:.3f}% requis"
            )
        
        return should_change
    
    def calculate_combined_atr(
        self,
        atr_1m_values: List[float],
        atr_5m_values: List[float]
    ) -> float:
        """
        Combine ATR 1m et 5m avec pondération configurable.
        
        Returns:
            ATR combiné (ou ATR 1m seul si 5m désactivé)
        """
        from utils.config_persistence import get_config_value
        
        use_atr_5m = get_config_value('market_regime_use_atr_5m', False)
        weight_1m = get_config_value('market_regime_atr_1m_weight', 0.40)
        weight_5m = get_config_value('market_regime_atr_5m_weight', 0.60)
        
        # Calcul ATR 1m (avec médiane/outliers si activés)
        atr_1m = self.calculate_atr_metric(atr_1m_values)
        last_atr_median_1m = getattr(self, 'last_atr_median', None)
        last_outliers_count_1m = getattr(self, 'last_outliers_count', 0)
        
        if not use_atr_5m or not atr_5m_values:
            return atr_1m
        
        # Calcul ATR 5m
        atr_5m = self.calculate_atr_metric(atr_5m_values)
        # Préserver les métriques V2 (médiane/outliers) de l'ATR 1m pour le logging
        self.last_atr_median = last_atr_median_1m
        self.last_outliers_count = last_outliers_count_1m
        
        # Pondération
        combined = weight_1m * atr_1m + weight_5m * atr_5m
        
        logger.debug(
            f"📊 ATR Combiné: 1m={atr_1m:.4f}%×{weight_1m} + 5m={atr_5m:.4f}%×{weight_5m} = {combined:.4f}%"
        )
        
        return combined

    # ═══════════════════════════════════════════════════════════════════════
    # 🔥 PHASE 1D: Auto-Calibration Seuils ATR + BTC Indicator
    # ═══════════════════════════════════════════════════════════════════════
    
    async def calibrate_thresholds(self) -> Dict[str, float]:
        """
        Calibre les seuils ATR basé sur percentiles historiques (7 jours).
        
        Returns:
            Dict avec threshold_calme, threshold_volatile, calibrated
        """
        from utils.config_persistence import get_config_value
        
        # Valeurs par défaut (fixes)
        default_thresholds = {
            'threshold_calme': 0.20,
            'threshold_volatile': 0.40,
            'calibrated': False,
            'samples': 0
        }
        
        if not get_config_value('market_regime_auto_calibration_enabled', False):
            return default_thresholds
        
        lookback_days = get_config_value('market_regime_calibration_lookback_days', 7)
        p_calme = get_config_value('market_regime_calibration_percentile_calme', 33)
        p_volatile = get_config_value('market_regime_calibration_percentile_volatile', 66)
        min_samples = get_config_value('market_regime_calibration_min_samples', 50)
        
        try:
            # Query PostgreSQL pour percentiles
            from core.postgresql_datalogger import get_pg_datalogger
            pg_logger = get_pg_datalogger()
            
            if not pg_logger or not getattr(pg_logger, 'enabled', False):
                logger.warning("⚠️ Calibration: Pool PostgreSQL non disponible")
                return default_thresholds
            
            query = f"""
                SELECT 
                    COUNT(*) as samples,
                    PERCENTILE_CONT({p_calme / 100.0}) WITHIN GROUP (ORDER BY avg_atr) as p_calme,
                    PERCENTILE_CONT({p_volatile / 100.0}) WITHIN GROUP (ORDER BY avg_atr) as p_volatile
                FROM market_regime_history
                WHERE created_at > NOW() - INTERVAL '{lookback_days} days'
                  AND avg_atr IS NOT NULL
                  AND avg_atr > 0
            """

            result = pg_logger._execute_query(query, fetch=True)
            row = result[0] if result else None

            samples = int(row[0]) if row and row[0] is not None else 0
            p_calme_val = float(row[1]) if row and row[1] is not None else None
            p_volatile_val = float(row[2]) if row and row[2] is not None else None

            if samples < min_samples or p_calme_val is None or p_volatile_val is None:
                logger.info(
                    f"📊 Calibration: Pas assez de données ({samples}/{min_samples}), "
                    f"utilisation seuils fixes"
                )
                return default_thresholds
            
            threshold_calme = p_calme_val
            threshold_volatile = p_volatile_val
            
            # Stocker en cache
            self._calibrated_thresholds = {
                'threshold_calme': round(threshold_calme, 4),
                'threshold_volatile': round(threshold_volatile, 4),
                'calibrated': True,
                'samples': samples,
                'timestamp': datetime.now()
            }
            
            logger.info(
                f"✅ Calibration réussie ({samples} samples, {lookback_days}j): "
                f"CALME < {threshold_calme:.3f}% (P{p_calme}) | "
                f"VOLATILE > {threshold_volatile:.3f}% (P{p_volatile})"
            )
            
            return self._calibrated_thresholds
            
        except Exception as e:
            logger.error(f"❌ Erreur calibration seuils: {e}")
            return default_thresholds
    
    def get_calibrated_thresholds(self) -> Dict[str, float]:
        """
        Retourne les seuils calibrés (cache) ou valeurs par défaut.
        """
        if hasattr(self, '_calibrated_thresholds') and self._calibrated_thresholds:
            # Vérifier si cache encore valide (6h)
            cache_age = datetime.now() - self._calibrated_thresholds.get('timestamp', datetime.min)
            if cache_age.total_seconds() < 6 * 3600:  # 6 heures
                return self._calibrated_thresholds
        
        # Retourner valeurs fixes
        return {
            'threshold_calme': 0.20,
            'threshold_volatile': 0.40,
            'calibrated': False
        }
    
    async def get_btc_status(self) -> Optional[Dict]:
        """
        Récupère le status BTC pour confirmation régime.
        
        Returns:
            Dict avec price, pct_change_1h, pct_change_24h, is_volatile, trend
        """
        from utils.config_persistence import get_config_value
        
        if not get_config_value('market_regime_btc_indicator_enabled', False):
            return None
        
        try:
            from core.btc_indicator import get_btc_indicator
            btc = get_btc_indicator()
            status = await btc.get_btc_status()
            return status.to_dict() if status else None
        except Exception as e:
            logger.debug(f"BTCIndicator non disponible: {e}")
            return None
    
    def should_force_volatile_from_btc(self, current_regime: str) -> bool:
        """
        Vérifie si BTC volatil devrait forcer le régime VOLATILE.
        """
        from utils.config_persistence import get_config_value
        
        if not get_config_value('market_regime_btc_indicator_enabled', False):
            return False
        
        if not get_config_value('market_regime_btc_force_volatile_enabled', True):
            return False
        
        try:
            from core.btc_indicator import get_btc_indicator
            btc = get_btc_indicator()
            return btc.should_force_volatile(current_regime)
        except Exception:
            return False

    def on_regime_change(self, callback: callable) -> None:
        """Enregistre un callback appelé lors d'un changement de régime"""
        self._on_regime_change_callbacks.append(callback)
    
    def _notify_regime_change(self, old_regime: MarketRegime, new_regime: MarketRegime) -> None:
        """Notifie les callbacks d'un changement de régime"""
        for callback in self._on_regime_change_callbacks:
            try:
                callback(old_regime.value, new_regime.value, self.avg_atr, self.avg_adx)
            except Exception as e:
                logger.error(f"❌ Erreur callback régime: {e}")
    
    def determine_regime(self, avg_atr: float, avg_adx: float = 25.0) -> MarketRegime:
        """
        Détermine le régime de marché basé sur ATR et ADX.
        
        Args:
            avg_atr: ATR moyen en pourcentage
            avg_adx: ADX moyen (optionnel)
            
        Returns:
            MarketRegime détecté
        """
        from utils.config_persistence import get_config_value
        
        # 🔥 PHASE 1D: Utiliser seuils calibrés si disponibles
        calibrated = self.get_calibrated_thresholds()
        use_calibration = get_config_value('market_regime_auto_calibration_enabled', False)
        
        if use_calibration and calibrated.get('calibrated', False):
            atr_calme_max = calibrated['threshold_calme']
            atr_normal_max = calibrated['threshold_volatile']
            logger.debug(f"📊 Seuils calibrés: CALME<{atr_calme_max:.3f}%, VOLATILE>{atr_normal_max:.3f}%")
        else:
            # Fallback: seuils fixes depuis config
            try:
                from config import TRADING_CONFIG
                atr_calme_max = TRADING_CONFIG.get('market_regime_atr_calme_max', 0.20)
                atr_normal_max = TRADING_CONFIG.get('market_regime_atr_normal_max', 0.40)
            except ImportError:
                atr_calme_max = 0.20
                atr_normal_max = 0.40

        if get_config_value('market_regime_use_seasonality', False):
            hour = datetime.now().hour
            if 0 <= hour < 7:
                multiplier = 0.90
            elif 7 <= hour < 15:
                multiplier = 1.00
            else:
                multiplier = 1.10
            atr_calme_max = atr_calme_max * multiplier
            atr_normal_max = atr_normal_max * multiplier
        
        # ADX pour choppy
        try:
            from config import TRADING_CONFIG
            adx_choppy = TRADING_CONFIG.get('market_regime_adx_choppy', 20)
        except ImportError:
            adx_choppy = 20
        
        # Choppy si ADX très faible (pas de tendance)
        if avg_adx < adx_choppy:
            regime = MarketRegime.CHOPPY
        # Sinon basé sur ATR
        elif avg_atr < atr_calme_max:
            regime = MarketRegime.CALME
        elif avg_atr < atr_normal_max:
            regime = MarketRegime.NORMAL
        else:
            regime = MarketRegime.VOLATILE
        
        # 🔥 PHASE 1D: BTC peut forcer VOLATILE
        if self.should_force_volatile_from_btc(regime.value):
            regime = MarketRegime.VOLATILE
        
        return regime
    
    async def check_regime(
        self,
        atr_values: List[float],
        atr_5m_values: Optional[List[float]] = None,
        adx_values: Optional[List[float]] = None,
        force: bool = False,
        trigger: str = "auto"
    ) -> Tuple[MarketRegime, bool]:
        """
        Vérifie et met à jour le régime de marché.
        
        Args:
            atr_values: Liste des ATR% des paires analysées
            adx_values: Liste des ADX (optionnel)
            force: Forcer la vérification même si pas dans l'intervalle
            trigger: "auto" ou "manual"
            
        Returns:
            Tuple (régime actuel, changement effectué)
        """
        now = datetime.now()

        from utils.config_persistence import get_config_value

        try:
            if get_config_value('market_regime_btc_indicator_enabled', False):
                try:
                    await asyncio.wait_for(self.get_btc_status(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass
        except Exception:
            pass

        try:
            if get_config_value('market_regime_auto_calibration_enabled', False):
                should_calibrate = True
                cache = getattr(self, '_calibrated_thresholds', None)
                if isinstance(cache, dict):
                    ts = cache.get('timestamp')
                    if isinstance(ts, datetime):
                        if (now - ts).total_seconds() < 6 * 3600:
                            should_calibrate = False

                if should_calibrate:
                    last_attempt = getattr(self, '_last_calibration_attempt', None)
                    if not last_attempt or (now - last_attempt).total_seconds() >= 30 * 60:
                        task = getattr(self, '_calibration_task', None)
                        if not task or task.done():
                            self._calibration_task = asyncio.create_task(self.calibrate_thresholds())
                        self._last_calibration_attempt = now
        except Exception:
            pass
        
        # 🔥 FIX: Toujours mettre à jour les valeurs ATR/ADX pour le widget Samples
        # (même si on ne fait pas de check complet)
        if atr_values:
            self.atr_values = atr_values
            self.atr_sample_count = len(atr_values)
        # Calculer moyennes
        if not atr_values:
            logger.warning("⚠️ Pas de valeurs ATR fournies")
            return self.current_regime, False

        v2_enabled = get_config_value('market_regime_v2_enabled', False)
        if v2_enabled:
            atr_metric = self.calculate_combined_atr(atr_values, atr_5m_values or [])
            self.avg_atr = self.apply_smoothing(atr_metric)
        else:
            self.avg_atr = sum(atr_values) / len(atr_values)
        self.avg_adx = sum(adx_values) / len(adx_values) if adx_values else 25.0
        
        # Déterminer le nouveau régime
        new_regime = self.determine_regime(self.avg_atr, self.avg_adx)
        old_regime = self.current_regime
        changed = new_regime != old_regime

        if changed and v2_enabled:
            if not self.should_change_regime(old_regime, new_regime, self.avg_atr):
                changed = False
                new_regime = old_regime

        if changed and not force and trigger == "auto" and self.regime_since:
            min_duration_minutes = get_config_value('market_regime_min_duration_minutes', 30)
            if (now - self.regime_since).total_seconds() < (min_duration_minutes * 60):
                changed = False
                new_regime = old_regime
        
        # Mettre à jour l'état
        self.last_check = now
        self.next_check = now + self.check_interval
        
        if changed:
            self.current_regime = new_regime
            self.current_config = self.regime_configs.get(new_regime.value)
            self.regime_since = now
            
            # Ajouter à l'historique
            change = RegimeChange(
                timestamp=now,
                old_regime=old_regime.value,
                new_regime=new_regime.value,
                avg_atr=self.avg_atr,
                avg_adx=self.avg_adx,
                trigger=trigger
            )
            self.history.append(change)
            
            # Limiter la taille de l'historique
            if len(self.history) > self.max_history_size:
                self.history = self.history[-self.max_history_size:]
            
            # Notifier
            logger.info(
                f"🌡️ RÉGIME CHANGÉ: {old_regime.value} → {new_regime.value} | "
                f"ATR: {self.avg_atr:.3f}% | ADX: {self.avg_adx:.1f}"
            )
            self._notify_regime_change(old_regime, new_regime)
            
            # 🔥 SPRINT 1: Logger dans market_regime_history
            self._log_regime_change_to_db(old_regime, new_regime, trigger)
        else:
            logger.debug(
                f"🌡️ Régime stable: {new_regime.value} | "
                f"ATR: {self.avg_atr:.3f}% | ADX: {self.avg_adx:.1f}"
            )
        
        return self.current_regime, changed
    
    def get_active_config(self) -> Dict[str, Any]:
        """
        Retourne la configuration active pour le régime actuel.
        À merger avec TRADING_CONFIG.
        """
        if not self.current_config:
            return {}
        
        return {
            "min_score_required": self.current_config.min_score_required,
            "atr_mult_sl": self.current_config.atr_mult_sl,
            "atr_mult_tp": self.current_config.atr_mult_tp,
            "break_even_atr_mult": self.current_config.break_even_atr_mult,
            "trailing_trigger_atr_mult": self.current_config.trailing_trigger_atr_mult,
            "position_timeout": self.current_config.max_position_time,
            "optimal_atr_min_1m": self.current_config.optimal_atr_min,
            "optimal_atr_max_1m": self.current_config.optimal_atr_max,
            "optimal_atr_min_5m": self.current_config.optimal_atr_min_5m,  # 🔥 ATR 5m
            "optimal_atr_max_5m": self.current_config.optimal_atr_max_5m,  # 🔥 ATR 5m
            "volume_multiplier": self.current_config.volume_multiplier,
            "sl_exchange_percent": self.current_config.sl_exchange_percent,
            # Paramètres stagnation par régime
            "stagnation_exit_timeout_seconds": self.current_config.stagnation_timeout,
            "stagnation_exit_min_pnl_to_stay": self.current_config.stagnation_min_pnl,
            "stagnation_exit_max_loss_to_exit": self.current_config.stagnation_max_loss
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut complet pour l'API"""
        return {
            "current_regime": self.current_regime.value,
            "avg_atr": round(self.avg_atr, 4),
            "avg_adx": round(self.avg_adx, 1),
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "next_check": self.next_check.isoformat() if self.next_check else None,
            "regime_since": self.regime_since.isoformat() if self.regime_since else None,
            "config_active": self.get_active_config(),
            "atr_sample_count": self.atr_sample_count,  # 🔥 FIX: Utiliser le compteur dédié
            "check_interval_minutes": self.check_interval.total_seconds() / 60
        }
    
    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retourne l'historique des changements de régime"""
        return [change.to_dict() for change in self.history[-limit:]]
    
    def get_regime_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Retourne les seuils de chaque régime"""
        return {
            regime: {
                "atr_min": config.optimal_atr_min,
                "atr_max": config.optimal_atr_max,
                "min_score": config.min_score_required
            }
            for regime, config in self.regime_configs.items()
        }
    
    def update_regime_threshold(
        self,
        regime_name: str,
        atr_min: Optional[float] = None,
        atr_max: Optional[float] = None,
        min_score: Optional[float] = None
    ) -> bool:
        """Met à jour les seuils d'un régime"""
        if regime_name not in self.regime_configs:
            return False
        
        config = self.regime_configs[regime_name]
        
        if atr_min is not None:
            config.optimal_atr_min = atr_min
        if atr_max is not None:
            config.optimal_atr_max = atr_max
        if min_score is not None:
            config.min_score_required = min_score
        
        return self.save_regime_config(regime_name)
    
    def _log_regime_change_to_db(
        self,
        old_regime: MarketRegime,
        new_regime: MarketRegime,
        trigger: str = "auto"
    ) -> None:
        """
        🔥 SPRINT 1 + PHASE 1A: Logger le changement de régime dans market_regime_history
        """
        try:
            from core.postgresql_datalogger import get_pg_datalogger
            from utils.session_detector import get_current_session
            from utils.config_persistence import get_config_value
            
            pg_logger = get_pg_datalogger()
            
            if not pg_logger or not pg_logger.enabled:
                logger.debug("PostgreSQL logger non disponible pour régime history")
                return
            
            # Calculer la durée dans l'ancien régime
            old_duration_minutes = None
            if self.regime_since:
                from datetime import datetime
                old_duration_minutes = (datetime.now() - self.regime_since).total_seconds() / 60
            
            # 🔥 PHASE 1A: Contexte session
            session_info = get_current_session()
            session_market = session_info['name']
            
            # 🔥 PHASE 1A: Metadata V2
            v2_enabled = get_config_value('market_regime_v2_enabled', False)
            detection_method = 'RULE_BASED_V2' if v2_enabled else 'RULE_BASED_V1'
            atr_median = getattr(self, 'last_atr_median', None)
            atr_smoothed = getattr(self, 'last_atr_smoothed', None)
            hysteresis_applied = getattr(self, 'hysteresis_was_applied', False)
            outliers_count = getattr(self, 'last_outliers_count', 0)
            ml_confidence = None  # Phase 3
            
            # Insérer dans la table avec colonnes Phase 1A
            query = """
                INSERT INTO market_regime_history (
                    timestamp, session_id, old_regime, new_regime,
                    avg_atr, avg_adx, sample_count, trigger,
                    old_regime_duration_minutes,
                    -- PHASE 1A columns
                    detection_method, atr_median, atr_smoothed,
                    session_market, hysteresis_applied, outliers_filtered_count,
                    ml_confidence
                ) VALUES (
                    NOW(), %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            session_id = pg_logger.get_or_create_session()
            
            params = (
                session_id,
                old_regime.value,
                new_regime.value,
                round(self.avg_atr, 4),
                round(self.avg_adx, 1) if self.avg_adx else None,
                self.atr_sample_count,
                trigger,
                round(old_duration_minutes, 1) if old_duration_minutes else None,
                # PHASE 1A values
                detection_method,
                atr_median,
                atr_smoothed,
                session_market,
                hysteresis_applied,
                outliers_count,
                ml_confidence
            )
            
            pg_logger._execute_query(query, params)
            logger.info(f"📝 Changement régime loggé: {old_regime.value} → {new_regime.value} [{session_market}]")
            
        except Exception as e:
            logger.error(f"❌ Erreur logging régime history: {e}")


# Instance globale
_regime_selector: Optional[MarketRegimeSelector] = None


def get_regime_selector() -> MarketRegimeSelector:
    """Retourne l'instance globale du sélecteur de régime, configurée depuis TRADING_CONFIG"""
    global _regime_selector
    if _regime_selector is None:
        # Charger config depuis TRADING_CONFIG
        try:
            from config import TRADING_CONFIG
            _regime_selector = MarketRegimeSelector(
                check_interval_minutes=TRADING_CONFIG.get('market_regime_check_interval', 60),
                atr_sample_size=TRADING_CONFIG.get('market_regime_sample_count', 10)
            )
            logger.info(
                f"✅ MarketRegimeSelector configuré: "
                f"interval={_regime_selector.check_interval}, "
                f"samples={_regime_selector.atr_sample_size}"
            )
        except ImportError:
            logger.warning("⚠️ TRADING_CONFIG non disponible, utilisation valeurs par défaut")
            _regime_selector = MarketRegimeSelector()
    return _regime_selector


def init_regime_selector(**kwargs) -> MarketRegimeSelector:
    """Initialise l'instance globale avec des paramètres personnalisés"""
    global _regime_selector
    _regime_selector = MarketRegimeSelector(**kwargs)
    return _regime_selector

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
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
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
    optimal_atr_min: float
    optimal_atr_max: float
    min_score_required: float
    atr_mult_sl: float
    atr_mult_tp: float
    break_even_atr_mult: float
    trailing_trigger_atr_mult: float
    max_position_time: int  # secondes
    volume_multiplier: float = 1.0  # 🔥 NOUVEAU
    rsi_filter_mode: str = "STANDARD"  # 🔥 NOUVEAU: STRICT, STANDARD, PERMISSIVE
    sl_exchange_percent: float = 0.30  # 🔥 SL MEXC fixe par régime (filet de sécurité)
    
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
        optimal_atr_min=0.0,
        optimal_atr_max=0.15,
        min_score_required=9.0,  # 🔥 Très strict (peu de mouvement = danger)
        atr_mult_sl=0.8,
        atr_mult_tp=1.8,
        break_even_atr_mult=0.8,
        trailing_trigger_atr_mult=1.0,
        max_position_time=360,
        volume_multiplier=1.0,
        rsi_filter_mode="STRICT",
        sl_exchange_percent=0.25
    ),
    "NORMAL": RegimeConfig(
        name="NORMAL",
        optimal_atr_min=0.15,
        optimal_atr_max=0.25,
        min_score_required=8.0,  # 🔥 Plus strict (était 7.5)
        atr_mult_sl=1.2,
        atr_mult_tp=2.2,
        break_even_atr_mult=1.2,
        trailing_trigger_atr_mult=1.5,
        max_position_time=300,
        volume_multiplier=1.1,
        rsi_filter_mode="PERMISSIVE",
        sl_exchange_percent=0.30
    ),
    "VOLATILE": RegimeConfig(
        name="VOLATILE",
        optimal_atr_min=0.35,
        optimal_atr_max=1.0,
        min_score_required=7.5,  # 🔥 Légèrement moins strict (mouvements clairs)
        atr_mult_sl=1.5,
        atr_mult_tp=2.5,
        break_even_atr_mult=1.5,
        trailing_trigger_atr_mult=2.0,
        max_position_time=180,
        volume_multiplier=1.5,
        rsi_filter_mode="PERMISSIVE",
        sl_exchange_percent=0.35
    ),
    "CHOPPY": RegimeConfig(
        name="CHOPPY",
        optimal_atr_min=0.0,
        optimal_atr_max=0.20,
        min_score_required=10.0,  # 🔥 Très strict (pas de tendance = danger)
        atr_mult_sl=0.7,
        atr_mult_tp=1.5,
        break_even_atr_mult=0.5,
        trailing_trigger_atr_mult=0.8,
        max_position_time=60,
        volume_multiplier=0.8,
        rsi_filter_mode="STRICT",
        sl_exchange_percent=0.20
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
                        self.regime_configs[regime_name] = RegimeConfig(**data)
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
        # 🔥 FIX: Utiliser les seuils de TRADING_CONFIG au lieu de valeurs hardcodées
        try:
            from config import TRADING_CONFIG
            adx_choppy = TRADING_CONFIG.get('market_regime_adx_choppy', 20)
            atr_calme_max = TRADING_CONFIG.get('market_regime_atr_calme_max', 0.20)
            atr_normal_max = TRADING_CONFIG.get('market_regime_atr_normal_max', 0.40)
        except ImportError:
            adx_choppy = 20
            atr_calme_max = 0.20
            atr_normal_max = 0.40
        
        # Choppy si ADX très faible (pas de tendance)
        if avg_adx < adx_choppy:
            return MarketRegime.CHOPPY
        
        # Sinon basé sur ATR
        if avg_atr < atr_calme_max:
            return MarketRegime.CALME
        elif avg_atr < atr_normal_max:
            return MarketRegime.NORMAL
        else:
            return MarketRegime.VOLATILE
    
    async def check_regime(
        self,
        atr_values: List[float],
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
        
        # 🔥 FIX: Toujours mettre à jour les valeurs ATR/ADX pour le widget Samples
        # (même si on ne fait pas de check complet)
        if atr_values:
            self.atr_values = atr_values
            self.atr_sample_count = len(atr_values)
        
        # Vérifier si on doit checker
        if not force and self.last_check:
            if now < self.last_check + self.check_interval:
                return self.current_regime, False
        
        # Calculer moyennes
        if not atr_values:
            logger.warning("⚠️ Pas de valeurs ATR fournies")
            return self.current_regime, False
        self.avg_atr = sum(atr_values) / len(atr_values)
        self.avg_adx = sum(adx_values) / len(adx_values) if adx_values else 25.0
        
        # Déterminer le nouveau régime
        new_regime = self.determine_regime(self.avg_atr, self.avg_adx)
        old_regime = self.current_regime
        changed = new_regime != old_regime
        
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
            "volume_multiplier": self.current_config.volume_multiplier,
            "rsi_filter_mode": self.current_config.rsi_filter_mode,
            "sl_exchange_percent": self.current_config.sl_exchange_percent  # 🔥 SL MEXC
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
        🔥 SPRINT 1: Logger le changement de régime dans market_regime_history
        """
        try:
            from core.postgresql_datalogger import get_pg_datalogger
            pg_logger = get_pg_datalogger()
            
            if not pg_logger or not pg_logger.enabled:
                logger.debug("PostgreSQL logger non disponible pour régime history")
                return
            
            # Calculer la durée dans l'ancien régime
            old_duration_minutes = None
            if self.regime_since:
                from datetime import datetime
                old_duration_minutes = (datetime.now() - self.regime_since).total_seconds() / 60
            
            # Insérer dans la table
            query = """
                INSERT INTO market_regime_history (
                    timestamp, session_id, old_regime, new_regime,
                    avg_atr, avg_adx, sample_count, trigger,
                    old_regime_duration_minutes
                ) VALUES (
                    NOW(), %s, %s, %s, %s, %s, %s, %s, %s
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
                round(old_duration_minutes, 1) if old_duration_minutes else None
            )
            
            pg_logger._execute_query(query, params)
            logger.info(f"📝 Changement régime loggé: {old_regime.value} → {new_regime.value}")
            
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

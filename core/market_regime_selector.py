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


# Configurations par régime (valeurs par défaut)
DEFAULT_REGIME_CONFIGS: Dict[str, RegimeConfig] = {
    "CALME": RegimeConfig(
        name="CALME",
        optimal_atr_min=0.0,
        optimal_atr_max=0.20,
        min_score_required=6.0,  # Plus permissif en marché calme
        atr_mult_sl=1.0,
        atr_mult_tp=2.5,
        break_even_atr_mult=0.4,
        trailing_trigger_atr_mult=0.8,
        max_position_time=180  # 3 min max
    ),
    "NORMAL": RegimeConfig(
        name="NORMAL",
        optimal_atr_min=0.20,
        optimal_atr_max=0.40,
        min_score_required=7.0,
        atr_mult_sl=1.2,
        atr_mult_tp=3.0,
        break_even_atr_mult=0.5,
        trailing_trigger_atr_mult=1.0,
        max_position_time=300  # 5 min
    ),
    "VOLATILE": RegimeConfig(
        name="VOLATILE",
        optimal_atr_min=0.40,
        optimal_atr_max=1.0,
        min_score_required=8.0,  # Plus strict en volatile
        atr_mult_sl=1.5,
        atr_mult_tp=4.0,
        break_even_atr_mult=0.6,
        trailing_trigger_atr_mult=1.2,
        max_position_time=120  # 2 min max (sorties rapides)
    ),
    "CHOPPY": RegimeConfig(
        name="CHOPPY",
        optimal_atr_min=0.0,
        optimal_atr_max=1.0,
        min_score_required=9.0,  # Très strict (ADX < 20)
        atr_mult_sl=0.8,
        atr_mult_tp=2.0,
        break_even_atr_mult=0.3,
        trailing_trigger_atr_mult=0.6,
        max_position_time=90  # 1.5 min max
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
        # Choppy si ADX très faible (pas de tendance)
        if avg_adx < 20:
            return MarketRegime.CHOPPY
        
        # Sinon basé sur ATR
        if avg_atr < 0.20:
            return MarketRegime.CALME
        elif avg_atr < 0.40:
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
        
        # Vérifier si on doit checker
        if not force and self.last_check:
            if now < self.last_check + self.check_interval:
                return self.current_regime, False
        
        # Calculer moyennes
        if not atr_values:
            logger.warning("⚠️ Pas de valeurs ATR fournies")
            return self.current_regime, False
        
        self.atr_values = atr_values
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
            "atr_sample_count": len(self.atr_values),
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

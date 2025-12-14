"""
Gestionnaire de Configuration Effective - Séparation Base vs Effective

Ce module gère la séparation entre:
- BASE_CONFIG: Valeurs configurées manuellement via les sliders (ne changent jamais automatiquement)
- EFFECTIVE_CONFIG: Valeurs réellement utilisées par le bot (base + ajustements régime/CB/pair scorer)

Principe:
- Les sliders frontend modifient BASE_CONFIG
- Quand le régime/CB/pair scorer est actif, il calcule des AJUSTEMENTS
- EFFECTIVE_CONFIG = BASE_CONFIG + ajustements
- L'onglet "Variables en cours" affiche EFFECTIVE_CONFIG
- TRADING_CONFIG n'est JAMAIS modifié par le régime

Auteur: Cascade AI
Date: 08/12/2025
"""

import logging
from typing import Dict, Any, Optional
from copy import deepcopy
from threading import Lock

logger = logging.getLogger(__name__)

# Lock pour thread-safety
_config_lock = Lock()

# Variables modifiables par le régime/CB/pair scorer
REGIME_ADJUSTABLE_KEYS = [
    'min_score_required',
    'atr_mult_sl',
    'atr_mult_tp',
    'break_even_atr_mult',
    'trailing_trigger_atr_mult',
    'trailing_distance_mult',  # 🔥 SPRINT 3: Distance trailing adaptative
    'position_timeout',
    'optimal_atr_min_1m',
    'optimal_atr_max_1m',
    'optimal_atr_min_5m',  # 🔥 ATR 5m par régime
    'optimal_atr_max_5m',  # 🔥 ATR 5m par régime
    'volume_multiplier',
    'sl_exchange_percent',  # 🔥 SL MEXC fixe par régime
    # 🔥 NOUVEAU: Paramètres stagnation par régime
    'stagnation_exit_timeout_seconds',
    'stagnation_exit_min_pnl_to_stay',
    'stagnation_exit_max_loss_to_exit',
    # 🔥 Filtre RSI Final (configurable)
    'rsi_final_filter_enabled',
    'rsi_final_long_max',
    'rsi_final_short_min',
]

# Stockage des ajustements actifs (ne modifie pas TRADING_CONFIG)
_active_adjustments: Dict[str, Dict[str, Any]] = {
    'regime': {},      # Ajustements du Market Regime Selector
    'circuit_breaker': {},  # Ajustements du Circuit Breaker (ex: score_boost)
    'pair_scorer': {},  # Ajustements du Pair Scorer
    'local_trade': {},  # 🔥 SPRINT 3: Ajustements locaux du trade actif (ATR adaptatif)
}


def get_base_config() -> Dict[str, Any]:
    """
    Retourne les valeurs BASE de TRADING_CONFIG (sans ajustements).
    Ce sont les valeurs configurées manuellement via les sliders.
    """
    from config import TRADING_CONFIG
    return deepcopy(TRADING_CONFIG)


def set_regime_adjustments(adjustments: Dict[str, Any]) -> None:
    """
    Définit les ajustements du Market Regime Selector.
    NE MODIFIE PAS TRADING_CONFIG.
    
    Args:
        adjustments: Dict avec les valeurs à ajuster (ex: {'min_score_required': 8.0})
    """
    with _config_lock:
        _active_adjustments['regime'] = deepcopy(adjustments) if adjustments else {}
        logger.debug(f"🌡️ Ajustements régime mis à jour: {_active_adjustments['regime']}")


def set_circuit_breaker_adjustments(adjustments: Dict[str, Any]) -> None:
    """
    Définit les ajustements du Circuit Breaker.
    Ex: score_boost après pertes consécutives.
    
    Args:
        adjustments: Dict avec les valeurs à ajuster (ex: {'score_boost': 1.5})
    """
    with _config_lock:
        _active_adjustments['circuit_breaker'] = deepcopy(adjustments) if adjustments else {}
        logger.debug(f"🛑 Ajustements CB mis à jour: {_active_adjustments['circuit_breaker']}")


def set_pair_scorer_adjustments(adjustments: Dict[str, Any]) -> None:
    """
    Définit les ajustements du Pair Scorer.
    Ex: ajustement de score par paire.
    
    Args:
        adjustments: Dict avec les ajustements par paire
    """
    with _config_lock:
        _active_adjustments['pair_scorer'] = deepcopy(adjustments) if adjustments else {}
        logger.debug(f"📊 Ajustements Pair Scorer mis à jour: {_active_adjustments['pair_scorer']}")


def set_local_trade_adjustments(adjustments: Dict[str, Any]) -> None:
    """
    🔥 SPRINT 3: Définit les ajustements locaux du trade actif.
    Ces ajustements sont calculés à l'ouverture du trade basés sur l'ATR local.
    
    Args:
        adjustments: Dict avec les valeurs adaptées (ex: {'atr_mult_tp': 1.2, 'local_regime': 'MEDIUM'})
    """
    with _config_lock:
        _active_adjustments['local_trade'] = deepcopy(adjustments) if adjustments else {}
        if adjustments:
            logger.info(f"⚡ Ajustements trade local: régime={adjustments.get('local_regime', 'UNKNOWN')} | {adjustments.get('adjustment_reason', '')}")


def clear_all_adjustments() -> None:
    """Réinitialise tous les ajustements (ex: quand régime est désactivé)."""
    with _config_lock:
        _active_adjustments['regime'] = {}
        _active_adjustments['circuit_breaker'] = {}
        _active_adjustments['pair_scorer'] = {}
        _active_adjustments['local_trade'] = {}
        logger.info("🔄 Tous les ajustements effacés")


def clear_local_trade_adjustments() -> None:
    """🔥 SPRINT 3: Efface les ajustements du trade local (appelé à la fermeture du trade)."""
    with _config_lock:
        _active_adjustments['local_trade'] = {}
        logger.debug("🔄 Ajustements trade local effacés")


def get_active_adjustments() -> Dict[str, Dict[str, Any]]:
    """Retourne tous les ajustements actifs pour debug/affichage."""
    with _config_lock:
        return deepcopy(_active_adjustments)


def get_effective_config() -> Dict[str, Any]:
    """
    Calcule et retourne la configuration EFFECTIVE.
    EFFECTIVE = BASE + ajustements régime + ajustements CB + ajustements pair scorer.
    
    Cette fonction est utilisée par le bot pour obtenir les vraies valeurs à utiliser.
    """
    from config import TRADING_CONFIG
    
    with _config_lock:
        # Commencer avec une copie de TRADING_CONFIG (valeurs base)
        effective = deepcopy(TRADING_CONFIG)
        
        # Appliquer les ajustements du régime (si régime activé)
        if TRADING_CONFIG.get('market_regime_enabled', True):
            for key, value in _active_adjustments.get('regime', {}).items():
                if value is not None:
                    effective[key] = value
        
        # Appliquer les ajustements du Circuit Breaker
        if TRADING_CONFIG.get('trading_circuit_breaker_enabled', True):
            cb_adj = _active_adjustments.get('circuit_breaker', {})
            
            # Score boost: s'ajoute au min_score_required
            score_boost = cb_adj.get('score_boost', 0)
            if score_boost > 0:
                current_min_score = effective.get('min_score_required', 7.0)
                effective['min_score_required'] = current_min_score + score_boost
                effective['_cb_score_boost'] = score_boost  # Pour affichage
        
        # 🔥 SPRINT 3: Appliquer les ajustements locaux du trade actif
        local_adj = _active_adjustments.get('local_trade', {})
        if local_adj:
            for key, value in local_adj.items():
                if value is not None and key in REGIME_ADJUSTABLE_KEYS:
                    effective[key] = value
            # Ajouter métadonnées pour affichage
            effective['_local_regime'] = local_adj.get('local_regime', 'UNKNOWN')
            effective['_local_atr_pct'] = local_adj.get('atr_pct')
            effective['_local_adjustment_reason'] = local_adj.get('adjustment_reason')
        
        # Les ajustements Pair Scorer sont appliqués dynamiquement par paire
        # (pas ici car dépend du symbole)
        
        return effective


def get_effective_value(key: str, symbol: Optional[str] = None) -> Any:
    """
    Retourne la valeur effective d'une clé spécifique.
    Optionnellement prend en compte le symbole pour Pair Scorer.
    
    Args:
        key: Clé de configuration (ex: 'min_score_required')
        symbol: Symbole pour ajustements Pair Scorer (optionnel)
        
    Returns:
        Valeur effective
    """
    effective = get_effective_config()
    base_value = effective.get(key)
    
    # Si Pair Scorer activé et symbole fourni
    if symbol and effective.get('pair_scorer_enabled', True):
        with _config_lock:
            pair_adj = _active_adjustments.get('pair_scorer', {})
            symbol_adj = pair_adj.get(symbol, {})
            
            if key == 'min_score_required':
                # Pair scorer ajuste le score min par paire
                adjustment = symbol_adj.get('score_adjustment', 0)
                if base_value is not None:
                    return base_value + adjustment
    
    return base_value


def get_config_summary() -> Dict[str, Any]:
    """
    Retourne un résumé complet pour l'API et le frontend.
    Inclut base_config, effective_config, et détail des ajustements.
    """
    from config import TRADING_CONFIG
    
    effective = get_effective_config()
    regime_enabled = TRADING_CONFIG.get('market_regime_enabled', True)
    
    # 🔥 14/12/2025: ATR MAX désactivé si régime actif (données prouvent ATR haut = rentable)
    # Ne pas inclure ATR MAX dans les différences si régime actif
    atr_max_keys = ['optimal_atr_max_1m', 'optimal_atr_max_5m']
    
    # Calculer les différences pour affichage
    differences = {}
    for key in REGIME_ADJUSTABLE_KEYS:
        # 🔥 Skip ATR MAX si régime actif (ces valeurs ne sont plus utilisées)
        if regime_enabled and key in atr_max_keys:
            continue
            
        base_val = TRADING_CONFIG.get(key)
        eff_val = effective.get(key)
        if base_val != eff_val and eff_val is not None:
            differences[key] = {
                'base': base_val,
                'effective': eff_val,
                'delta': eff_val - base_val if isinstance(base_val, (int, float)) and isinstance(eff_val, (int, float)) else None
            }
    
    # 🔥 Ajouter info ATR MAX désactivé pour le frontend
    atr_max_disabled = regime_enabled
    
    return {
        'base_config': {k: TRADING_CONFIG.get(k) for k in REGIME_ADJUSTABLE_KEYS},
        'effective_config': {k: effective.get(k) for k in REGIME_ADJUSTABLE_KEYS},
        'adjustments': get_active_adjustments(),
        'differences': differences,
        'regime_enabled': regime_enabled,
        'cb_enabled': TRADING_CONFIG.get('trading_circuit_breaker_enabled', True),
        'pair_scorer_enabled': TRADING_CONFIG.get('pair_scorer_enabled', True),
        'atr_max_disabled': atr_max_disabled,  # 🔥 NOUVEAU: Info pour frontend
    }


# Singleton instance pour accès global
_instance = None

def get_effective_config_manager():
    """Retourne l'instance singleton du gestionnaire."""
    global _instance
    if _instance is None:
        _instance = EffectiveConfigManager()
    return _instance


class EffectiveConfigManager:
    """
    Classe manager pour une gestion plus avancée si nécessaire.
    """
    
    def __init__(self):
        self._callbacks = []
    
    def on_effective_change(self, callback: callable) -> None:
        """Enregistre un callback appelé quand effective_config change."""
        self._callbacks.append(callback)
    
    def notify_change(self, source: str) -> None:
        """Notifie les callbacks d'un changement."""
        effective = get_effective_config()
        for callback in self._callbacks:
            try:
                callback(source, effective)
            except Exception as e:
                logger.error(f"❌ Erreur callback effective_config: {e}")
    
    def update_from_regime(self, regime_config: Dict[str, Any]) -> None:
        """Met à jour depuis le régime et notifie."""
        set_regime_adjustments(regime_config)
        self.notify_change('regime')
    
    def update_from_cb(self, cb_adjustments: Dict[str, Any]) -> None:
        """Met à jour depuis le CB et notifie."""
        set_circuit_breaker_adjustments(cb_adjustments)
        self.notify_change('circuit_breaker')
    
    def update_from_pair_scorer(self, pair_adjustments: Dict[str, Any]) -> None:
        """Met à jour depuis le Pair Scorer et notifie."""
        set_pair_scorer_adjustments(pair_adjustments)
        self.notify_change('pair_scorer')

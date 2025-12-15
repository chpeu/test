"""
Detection de la session de marche basee sur l'heure UTC.
Utilise par: postgresql_datalogger, market_regime_selector, analyzer

Version: 1.0
Date: 10/12/2025
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Configuration des sessions (heures UTC)
DEFAULT_SESSIONS = {
    "ASIA": {
        "start_hour_utc": 0,
        "end_hour_utc": 7,
        "atr_threshold_multiplier": 0.80,
        "min_score_adjustment": 0.5,
        "description": "Marche asiatique - Range/Calme"
    },
    "EUROPE_OPEN": {
        "start_hour_utc": 7,
        "end_hour_utc": 9,
        "atr_threshold_multiplier": 1.20,
        "min_score_adjustment": 0.0,
        "description": "Ouverture Europe - Breakouts"
    },
    "EUROPE": {
        "start_hour_utc": 9,
        "end_hour_utc": 13,
        "atr_threshold_multiplier": 1.00,
        "min_score_adjustment": 0.0,
        "description": "Session Europe - Normal"
    },
    "US_PREMARKET": {
        "start_hour_utc": 13,
        "end_hour_utc": 14,
        "atr_threshold_multiplier": 1.10,
        "min_score_adjustment": 0.3,
        "description": "Pre-ouverture US - Anticipation"
    },
    "US_OPEN": {
        "start_hour_utc": 14,
        "end_hour_utc": 16,
        "atr_threshold_multiplier": 1.50,
        "min_score_adjustment": -0.5,
        "description": "Ouverture US - MAX Volatilite"
    },
    "US_SESSION": {
        "start_hour_utc": 16,
        "end_hour_utc": 20,
        "atr_threshold_multiplier": 1.20,
        "min_score_adjustment": 0.0,
        "description": "Session US active"
    },
    "US_CLOSE": {
        "start_hour_utc": 20,
        "end_hour_utc": 21,
        "atr_threshold_multiplier": 1.30,
        "min_score_adjustment": -0.3,
        "description": "Cloture US - Pic secondaire"
    },
    "NIGHT": {
        "start_hour_utc": 21,
        "end_hour_utc": 24,
        "atr_threshold_multiplier": 0.70,
        "min_score_adjustment": 1.0,
        "description": "Nuit - Tres calme"
    }
}


def get_sessions_config() -> Dict[str, Dict]:
    """Retourne la config des sessions (depuis config ou defaut)"""
    try:
        from config import MARKET_REGIME_V2_CONFIG
        return MARKET_REGIME_V2_CONFIG.get('sessions', DEFAULT_SESSIONS)
    except ImportError:
        return DEFAULT_SESSIONS


def get_current_session(hour_utc: Optional[int] = None) -> Dict[str, Any]:
    """
    Retourne la session de marche actuelle.
    
    Args:
        hour_utc: Heure UTC (0-23). Si None, utilise l'heure actuelle.
    
    Returns:
        Dict avec: name, description, atr_multiplier, score_adjustment, hour_utc
    
    Example:
        >>> session = get_current_session()
        >>> print(f"Session: {session['name']}, Multiplier: {session['atr_multiplier']}")
    """
    if hour_utc is None:
        hour_utc = datetime.now(timezone.utc).hour
    
    sessions = get_sessions_config()
    
    for session_name, config in sessions.items():
        start = config['start_hour_utc']
        end = config['end_hour_utc']
        
        # Cas normal (pas de passage minuit)
        if start < end:
            if start <= hour_utc < end:
                return _format_session_result(session_name, config, hour_utc)
        # Cas passage minuit (ex: NIGHT 21-24 puis ASIA 0-7)
        else:
            if hour_utc >= start or hour_utc < end:
                return _format_session_result(session_name, config, hour_utc)
    
    # Fallback (ne devrait pas arriver)
    logger.warning(f"Session non trouvee pour heure UTC {hour_utc}")
    return {
        "name": "UNKNOWN",
        "description": "Session non identifiee",
        "atr_multiplier": 1.0,
        "score_adjustment": 0.0,
        "hour_utc": hour_utc
    }


def _format_session_result(name: str, config: Dict, hour_utc: int) -> Dict[str, Any]:
    """Formate le resultat de session"""
    return {
        "name": name,
        "description": config.get('description', ''),
        "atr_multiplier": config.get('atr_threshold_multiplier', 1.0),
        "score_adjustment": config.get('min_score_adjustment', 0.0),
        "hour_utc": hour_utc,
        "start_hour": config.get('start_hour_utc'),
        "end_hour": config.get('end_hour_utc')
    }


def get_day_info(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Retourne les informations du jour.
    
    Returns:
        Dict avec: day_of_week (0-6), day_name, is_weekend, hour_utc, minute
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    return {
        "day_of_week": dt.weekday(),  # 0=Lundi, 6=Dimanche
        "day_name": dt.strftime("%A"),
        "is_weekend": dt.weekday() >= 5,
        "hour_utc": dt.hour,
        "minute": dt.minute,
        "timestamp_utc": dt.isoformat()
    }


def get_full_context() -> Dict[str, Any]:
    """
    Retourne le contexte complet (session + jour).
    Pratique pour le logging.
    """
    session = get_current_session()
    day = get_day_info()
    
    return {
        **session,
        **day,
        "context_string": f"{session['name']}_{day['day_name'][:3]}_{day['hour_utc']:02d}h"
    }


# ═══════════════════════════════════════════════════════════════════════════
# TESTS UNITAIRES
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Test Session Detector ===\n")
    
    # Test chaque heure
    print("Sessions par heure UTC:")
    print("-" * 60)
    for hour in range(24):
        session = get_current_session(hour)
        print(f"  {hour:02d}:00 UTC -> {session['name']:15s} (x{session['atr_multiplier']:.2f})")
    
    print("\n" + "-" * 60)
    print("Session actuelle:")
    ctx = get_full_context()
    print(f"  {ctx['context_string']}")
    print(f"  Multiplier ATR: x{ctx['atr_multiplier']}")
    print(f"  Ajustement Score: {ctx['score_adjustment']:+.1f}")

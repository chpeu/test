"""
Système de scoring pour évaluer la qualité des setups
Calcul de scores pondérés, bonus trend, divergences, etc.
"""

from typing import List, Dict, Optional
from config import CONDITION_WEIGHTS, TRADING_CONFIG, TREND_BONUS_CONFIG
from utils.logger import get_logger


logger = get_logger()


def calculate_weighted_score(condition_types: List[str]) -> float:
    """
    Calcule le score pondéré basé sur les types de conditions

    Args:
        condition_types: Liste des types de conditions (ex: ['EMAs', 'RSI', 'Volume'])

    Returns:
        Score pondéré total
    """
    score = 0.0
    for cond_type in condition_types:
        score += CONDITION_WEIGHTS.get(cond_type, 1.0)  # Par défaut 1.0 si type inconnu
    return score


def get_min_score_required(
    adx_value: float,
    use_weighted: bool = True,
    symbol: str = None
) -> tuple:
    """
    Calcule le score minimum requis selon ADX (tolérance dynamique)
    et applique l'ajustement pair scorer si disponible.

    Args:
        adx_value: Valeur ADX
        use_weighted: Si True, utilise scoring pondéré, sinon comptage simple
        symbol: Symbole de la paire pour ajustement pair scorer (optionnel)

    Returns:
        Tuple (score_minimum, pair_adjustment, effective_min_score)
        - score_minimum: Score de base après ajustements ADX/régime
        - pair_adjustment: Ajustement par paire [-2, +2]
        - effective_min_score: Score effectif après tous ajustements
    """
    pair_adjustment = 0.0
    
    if use_weighted:
        # 🔥 FIX: Toujours lire depuis TRADING_CONFIG (mis à jour dynamiquement)
        base_min_score = TRADING_CONFIG.get('min_score_required', 7.5)
        
        # 🔥 FIX: Si l'utilisateur a modifié min_score_required (≠ 7.5), utiliser directement cette valeur
        # Sinon, appliquer les ajustements ADX selon les valeurs par défaut
        if base_min_score != 7.5:
            # Valeur modifiée par l'utilisateur → utiliser directement sans ajustement ADX
            min_score_required = base_min_score
            logger.debug(f"📊 get_min_score_required: Utilisation valeur personnalisée {min_score_required:.1f} (ADX={adx_value:.1f}, ajustement ADX désactivé)")
        else:
            # Valeur par défaut → appliquer ajustements ADX
            if adx_value > 30:
                min_score_required = TRADING_CONFIG.get('min_score_adx_high', 7.0)
            elif adx_value < 25:
                min_score_required = TRADING_CONFIG.get('min_score_adx_low', 8.0)
            else:
                min_score_required = base_min_score
    else:
        # Système ancien (comptage simple)
        min_conditions = 6  # Par défaut
        if adx_value > 30:
            min_conditions = 5
        elif adx_value >= 25:
            min_conditions = 5.5
        min_score_required = min_conditions
    
    # 🔥 SPRINT 2: Appliquer ajustement Pair Scorer
    if symbol and TRADING_CONFIG.get('pair_scorer_enabled', True):
        try:
            from core.pair_scorer import get_pair_scorer
            pair_scorer = get_pair_scorer()
            if pair_scorer.enabled:
                pair_adjustment = pair_scorer.get_score_adjustment(symbol)
        except Exception as e:
            logger.debug(f"⚠️ Pair scorer non disponible: {e}")
    
    # Score effectif = base - pair_adjustment (bonus réduit le min, malus l'augmente)
    effective_min_score = min_score_required - pair_adjustment
    
    # Borner le score effectif (minimum 4.0, pas de limite haute)
    effective_min_score = max(4.0, effective_min_score)

    return min_score_required, pair_adjustment, effective_min_score


def apply_trend_bonus(
    trend_data: Optional[Dict],
    temp_direction: str,
    use_weighted: bool = True
) -> float:
    """
    Calcule le bonus de trend aligné avec la direction

    Args:
        trend_data: Dict avec 'trend', 'strength', 'bonus'
        temp_direction: Direction temporaire ('LONG', 'SHORT', 'NEUTRAL')
        use_weighted: Si True, utilise divisor configuré

    Returns:
        Bonus de score (float)
    """
    trend_score_bonus = 0.0

    if trend_data and temp_direction != 'NEUTRAL':
        if isinstance(trend_data, dict):
            bonus_value = trend_data.get('bonus', 0)
            divisor = TREND_BONUS_CONFIG.get('bonus_divisor', 5)

            if temp_direction == 'LONG' and trend_data.get('trend') == 'BULLISH':
                trend_score_bonus = bonus_value / divisor  # 25 → 5.0
            elif temp_direction == 'SHORT' and trend_data.get('trend') == 'BEARISH':
                trend_score_bonus = bonus_value / divisor
        else:
            logger.warning(
                f"⚠️ trend_data invalide (attendu dict, reçu {type(trend_data).__name__})"
            )

    return trend_score_bonus


def apply_divergence_bonus(
    rsi: float,
    rsi_prev: float,
    macd: Dict,
    macd_prev: Dict,
    temp_direction: str,
    conditions: List[str],
    condition_types: List[str]
) -> int:
    """
    Détecte divergence RSI/MACD et ajoute bonus

    Args:
        rsi: RSI actuel
        rsi_prev: RSI précédent
        macd: MACD actuel
        macd_prev: MACD précédent
        temp_direction: Direction temporaire
        conditions: Liste des conditions (modifiée in-place)
        condition_types: Liste des types de conditions (modifiée in-place)

    Returns:
        Bonus divergence (0 ou 1)
    """
    # ✅ Vérifier si la divergence est activée
    use_divergence = TRADING_CONFIG.get('use_divergence', True)
    if not use_divergence:
        return 0  # Divergence désactivée
    
    divergence_bonus = 0

    if temp_direction == 'LONG':
        # Divergence haussière : RSI baisse mais MACD monte
        if rsi < rsi_prev and macd['histogram'] > macd_prev['histogram']:
            divergence_bonus = 1
            conditions.append("Divergence+ ↑")
            condition_types.append('Divergence')

    elif temp_direction == 'SHORT':
        # Divergence baissière : RSI monte mais MACD baisse
        if rsi > rsi_prev and macd['histogram'] < macd_prev['histogram']:
            divergence_bonus = 1
            conditions.append("Divergence- ↓")
            condition_types.append('Divergence')

    return divergence_bonus


def calculate_final_score(
    condition_types: List[str],
    trend_bonus: float,
    divergence_bonus: int,
    use_weighted: bool = True,
    use_direct_score: bool = True
) -> float:
    """
    Calcule le score final en combinant score pondéré, trend bonus et divergence

    Args:
        condition_types: Liste des types de conditions
        trend_bonus: Bonus de trend
        divergence_bonus: Bonus de divergence
        use_weighted: Si True, utilise scoring pondéré
        use_direct_score: Si True, ajoute trend_bonus directement

    Returns:
        Score final
    """
    if use_weighted:
        base_score = calculate_weighted_score(condition_types)

        if use_direct_score:
            # Ajouter directement le trend bonus au score
            final_score = base_score + trend_bonus
        else:
            # Système ancien : trend bonus conditionnel
            final_score = base_score
    else:
        # Comptage simple
        final_score = len(condition_types)

    return final_score


def evaluate_setup_score(
    long_condition_types: List[str],
    short_condition_types: List[str],
    adx: Dict,
    trend_data: Optional[Dict] = None,
    symbol: str = None
) -> Dict:
    """
    Évalue les scores LONG et SHORT et détermine la direction

    Args:
        long_condition_types: Types de conditions LONG
        short_condition_types: Types de conditions SHORT
        adx: Dict ADX
        trend_data: Données de trend (optionnel)
        symbol: Symbole de la paire pour pair scorer (optionnel)

    Returns:
        Dict avec 'direction', 'long_score', 'short_score', 'min_required', 
        'pair_adjustment', 'effective_min_score'
    """
    use_weighted = TRADING_CONFIG.get('use_weighted_scoring', True)

    # Calculer scores
    long_score = calculate_weighted_score(long_condition_types) if use_weighted else len(long_condition_types)
    short_score = calculate_weighted_score(short_condition_types) if use_weighted else len(short_condition_types)

    # Score minimum requis (avec pair scorer si symbol fourni)
    min_score_base, pair_adjustment, effective_min_score = get_min_score_required(
        adx['adx'], use_weighted, symbol
    )

    # Direction basée sur le score effectif (après ajustement pair)
    temp_direction = 'NEUTRAL'
    if long_score >= effective_min_score:
        temp_direction = 'LONG'
    elif short_score >= effective_min_score:
        temp_direction = 'SHORT'

    # Trend bonus
    trend_bonus = apply_trend_bonus(trend_data, temp_direction, use_weighted)

    # Ajouter trend bonus si configuré
    if TREND_BONUS_CONFIG.get('use_direct_score', True):
        if temp_direction == 'LONG':
            long_score += trend_bonus
        elif temp_direction == 'SHORT':
            short_score += trend_bonus

    # Réévaluer direction après bonus (toujours avec score effectif)
    direction = 'NEUTRAL'
    if long_score >= effective_min_score:
        direction = 'LONG'
    elif short_score >= effective_min_score:
        direction = 'SHORT'

    return {
        'direction': direction,
        'temp_direction': temp_direction,
        'long_score': long_score,
        'short_score': short_score,
        'min_required': min_score_base,  # Score de base (avant pair adjustment)
        'pair_adjustment': pair_adjustment,  # 🔥 SPRINT 2: Ajustement pair scorer
        'effective_min_score': effective_min_score,  # 🔥 Score effectif utilisé
        'trend_bonus': trend_bonus
    }

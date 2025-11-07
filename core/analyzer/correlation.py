"""
Vérifications de corrélation entre paires
Corrélation statique (groupes) et dynamique (prix réels)
"""

from typing import Dict, Optional, List
from config import TRADING_CONFIG
from utils.logger import get_logger


logger = get_logger()


async def check_static_correlation(
    symbol: str,
    active_positions: Optional[List[str]]
) -> Dict:
    """
    Vérifier si le symbole est corrélé avec des positions actives (groupes statiques)

    Args:
        symbol: Symbole de la paire (ex: BTC/USDT:USDT)
        active_positions: Liste des symboles de positions actives

    Returns:
        Dict avec valid (bool), reason (str si rejeté), group (str si trouvé), penalty (float si SOFT)
    """
    correlation_config = TRADING_CONFIG.get('correlation_filter', {})
    if not correlation_config.get('enabled', False):
        return {'valid': True, 'reason': None, 'group': None, 'penalty': 0.0}

    if not active_positions:
        return {'valid': True, 'reason': None, 'group': None, 'penalty': 0.0}

    # Extraire le symbole de base (ex: BTC/USDT:USDT → BTC)
    base_symbol = symbol.split('/')[0].split(':')[0].upper()

    # Identifier le groupe de corrélation
    groups = correlation_config.get('groups', {})
    symbol_group = None

    for group_name, group_symbols in groups.items():
        for group_symbol in group_symbols:
            if group_symbol.upper() in base_symbol or base_symbol in group_symbol.upper():
                symbol_group = group_name
                break
        if symbol_group:
            break

    if not symbol_group:
        # Pas de groupe = OK
        return {'valid': True, 'reason': None, 'group': None, 'penalty': 0.0}

    # Compter les positions actives dans le même groupe
    count_in_group = 0
    correlated_symbols = []

    for active_symbol in active_positions:
        active_base = active_symbol.split('/')[0].split(':')[0].upper()
        group_symbols = groups.get(symbol_group, [])

        for group_symbol in group_symbols:
            if group_symbol.upper() in active_base or active_base in group_symbol.upper():
                count_in_group += 1
                correlated_symbols.append(active_symbol)
                break

    max_positions = correlation_config.get('max_positions_per_group', 1)
    mode = correlation_config.get('mode', 'HARD')

    if mode == 'SOFT':
        # SOFT mode: Appliquer pénalité au score
        if count_in_group >= max_positions:
            penalty = correlation_config.get('penalty_score', -1.5)
            reason = f"Corrélation avec {', '.join(correlated_symbols[:2])} (groupe: {symbol_group})"
            logger.warning(f"⚠️ {symbol} - Corrélation détectée (SOFT mode): {reason} - Pénalité: {penalty}")
            return {
                'valid': True,  # Toujours valide en SOFT mode
                'reason': reason,
                'group': symbol_group,
                'penalty': penalty,
                'correlated_count': count_in_group
            }
        else:
            return {'valid': True, 'reason': None, 'group': symbol_group, 'penalty': 0.0}
    else:
        # HARD mode: Rejeter si max atteint
        if count_in_group >= max_positions:
            reason = f"Corrélation avec {', '.join(correlated_symbols[:2])} (groupe: {symbol_group}, max: {max_positions})"
            logger.warning(f"⚠️ {symbol} - Setup rejeté (HARD mode): {reason}")
            return {
                'valid': False,
                'reason': reason,
                'group': symbol_group,
                'penalty': 0.0,
                'correlated_count': count_in_group
            }
        else:
            return {'valid': True, 'reason': None, 'group': symbol_group, 'penalty': 0.0}


def check_dynamic_correlation(
    correlation_filter,
    symbol: str,
    current_price: float,
    active_positions: Optional[List[str]],
    setup_score: float
) -> Dict:
    """
    Vérifier corrélation dynamique (basée sur prix réels)

    Args:
        correlation_filter: Instance de DynamicCorrelationFilter
        symbol: Symbole de la paire
        current_price: Prix actuel
        active_positions: Liste des symboles de positions actives
        setup_score: Score du setup (pour appliquer pénalité)

    Returns:
        Dict avec penalty (float), correlated_with (str), correlation (float), adjusted_score (float)
    """
    dynamic_corr_config = TRADING_CONFIG.get('dynamic_correlation', {})

    if not dynamic_corr_config.get('enabled', False) or not correlation_filter or not active_positions:
        return {
            'penalty': 0.0,
            'correlated_with': None,
            'correlation': 0.0,
            'adjusted_score': setup_score
        }

    # Mettre à jour prix actuel
    if current_price > 0:
        correlation_filter.update_price(symbol, current_price)

    # Vérifier corrélation dynamique
    corr_check = correlation_filter.check_correlation(symbol, active_positions)

    if corr_check['penalty'] < 0:
        penalty = corr_check['penalty']
        max_penalty = dynamic_corr_config.get('max_penalty', -3.0)
        penalty = max(max_penalty, penalty)  # Limiter pénalité max

        adjusted_score = setup_score + penalty

        logger.warning(
            f"⚠️ {symbol} corrélé dynamiquement avec {corr_check['correlated_with']} "
            f"(corrélation: {corr_check['correlation']:.2f}) - "
            f"Pénalité: {penalty:.2f}, Score: {adjusted_score:.1f}"
        )

        return {
            'penalty': penalty,
            'correlated_with': corr_check['correlated_with'],
            'correlation': corr_check['correlation'],
            'adjusted_score': adjusted_score
        }

    return {
        'penalty': 0.0,
        'correlated_with': None,
        'correlation': 0.0,
        'adjusted_score': setup_score
    }

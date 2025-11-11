"""
Callbacks pour la boucle de scanner automatique
Exécuté toutes les 45 secondes pour scanner les setups
"""

import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Variables globales injectées par init_instances()
_scanner = None
_analyzer = None
_position_manager = None
_price_provider = None
_app_state = None
_sio = None  # 🔥 MIGRATION COMPLÈTE: Gardé pour compatibilité, mais utiliser _ws_manager
_ws_manager = None  # 🔥 MIGRATION COMPLÈTE: WebSocket natif
_scanner_lock = None


def set_scanner(scanner):
    """Injecter l'instance scanner"""
    global _scanner
    _scanner = scanner


def set_analyzer(analyzer):
    """Injecter l'instance analyzer"""
    global _analyzer
    _analyzer = analyzer


def set_position_manager(position_manager):
    """Injecter l'instance position_manager"""
    global _position_manager
    _position_manager = position_manager


def set_price_provider(price_provider):
    """Injecter l'instance price_provider"""
    global _price_provider
    _price_provider = price_provider


def set_app_state(app_state):
    """Injecter l'état de l'application"""
    global _app_state
    _app_state = app_state


def set_socketio(sio):
    """Injecter l'instance SocketIO (legacy - gardé pour compatibilité)"""
    global _sio
    _sio = sio

def set_websocket_manager(ws_manager):
    """🔥 MIGRATION COMPLÈTE: Injecter l'instance WebSocketManager"""
    global _ws_manager
    _ws_manager = ws_manager


def set_scanner_lock(lock):
    """Injecter le lock du scanner"""
    global _scanner_lock
    _scanner_lock = lock


async def scanner_loop_callback():
    """
    Callback appelé toutes les 45 secondes pour scanner les setups

    Procédure:
    1. Vérifier qu'aucune position n'est active
    2. Si top_pairs vide, effectuer scan initial
    3. Scanner les top N paires en parallèle
    4. Analyser les résultats et ouvrir position si setup trouvé
    5. Émettre événements SocketIO de mise à jour
    """
    if not _scanner or not _app_state or not _scanner_lock:
        logger.debug("⚠️ Instances non disponibles pour scanner_loop_callback")
        return

    try:
        # Acquérir le lock pour éviter les scans multiples en parallèle
        async with _scanner_lock:
            # Vérifier qu'on n'a pas déjà une position active
            if _app_state.get('active_position') or (
                _position_manager and _position_manager.active_position
            ):
                # BUG #11 FIX: Logging informatif au lieu de debug
                active_pos = _position_manager.active_position if _position_manager else _app_state.get('active_position')
                symbol = active_pos.symbol if hasattr(active_pos, 'symbol') else active_pos.get('symbol', 'UNKNOWN') if isinstance(active_pos, dict) else 'UNKNOWN'
                logger.info(f"⏸️ Scanner ignoré: position active sur {symbol}")
                return

            # Si on n'a pas de top_pairs, les scanner d'abord
            if not _app_state.get('top_pairs'):
                await _scan_initial_top_pairs()
                return

            # Scanner les top pairs
            await _scan_top_pairs()

    except Exception as e:
        logger.error(f"❌ Erreur scanner_loop_callback: {e}")


async def _scan_initial_top_pairs():
    """
    Effectuer un scan initial des top pairs

    Procédure:
    1. Scanner les top 20 paires
    2. Mettre en cache les résultats
    3. Démarrer WebSocket pour monitoring
    4. Émettre événement SocketIO
    """
    if not _scanner or not _app_state:
        return

    try:
        logger.info("📊 Scan initial des top pairs...")
        top_pairs = await _scanner.scan_top_pairs(20)

        if top_pairs:
            _app_state['top_pairs'] = top_pairs

            # Démarrer WebSocket si price_provider disponible
            if _price_provider:
                symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
                if symbols:
                    try:
                        await _price_provider.start_websocket(symbols)
                        logger.info(f"✅ WebSocket démarré: {len(symbols)} symboles")
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur démarrage WebSocket: {e}")

            # 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif uniquement
            if _ws_manager:
                await _ws_manager.emit('top_pairs_update', {'pairs': top_pairs})

    except Exception as e:
        logger.error(f"❌ Erreur scan initial: {e}")


async def _scan_top_pairs():
    """
    Scanner les top pairs actuelles pour chercher des setups

    Procédure:
    1. Récupérer top N paires depuis app_state
    2. Lancer analyses en parallèle avec scan_pair_for_setup()
    3. Compter les résultats (setups valides, rejets, erreurs)
    4. Ouvrir position si setup trouvé
    5. Émettre événements SocketIO
    """
    if not _app_state or not _app_state.get('top_pairs'):
        return

    try:
        from config import TRADING_CONFIG

        pairs_to_scan = _app_state.get('top_pairs', [])[:TRADING_CONFIG.get('top_pairs_limit', 20)]

        if not pairs_to_scan:
            return

        logger.info(f"🔍 Scanning {len(pairs_to_scan)} paires...")

        # Lancer analyses en parallèle
        scan_tasks = [
            scan_pair_for_setup(pair.get('symbol', ''))
            for pair in pairs_to_scan
            if pair.get('symbol')
        ]

        if not scan_tasks:
            return

        results = await asyncio.gather(*scan_tasks, return_exceptions=True)

        # Compter les résultats CORRECTEMENT
        # Un setup VALIDE a les clés: 'symbol', 'direction', 'price', 'entry', etc.
        # Un setup REJETÉ a seulement: 'reason' ou {'symbol': ..., 'reason': ...}
        valid_setups = []
        rejections = []
        errors = []

        for r in results:
            if isinstance(r, Exception):
                errors.append(r)
            elif r and isinstance(r, dict):
                # Setup valide = a 'direction' ET 'entry' (ou 'price')
                if 'direction' in r and ('entry' in r or 'price' in r):
                    valid_setups.append(r)
                else:
                    # Rejet
                    rejections.append(r)
            # else: None = aussi une erreur/skip

        logger.info(f"📊 Résumé: {len(valid_setups)} setups valides, {len(rejections)} rejets, {len(errors)} erreurs")

        # Si on a trouvé un setup valide, ouvrir une position
        if valid_setups and _position_manager:
            # Prendre le meilleur setup (premier dans la liste)
            best_setup = valid_setups[0]

            try:
                # BUG #7 FIX: Valider que entry est présent et valide
                entry = best_setup.get('entry') or best_setup.get('price')
                if not entry or entry <= 0:
                    logger.error(f"❌ Entry invalide pour {best_setup.get('symbol')}: {entry}")
                    return

                # BUG #4 FIX: Calculer position_size correctement
                from config import TRADING_CONFIG
                capital = TRADING_CONFIG.get('account_size', 1000.0)
                position_size = _position_manager.calculate_position_size(
                    setup=best_setup,
                    capital=capital,
                    base_risk=0.01,  # 1%
                    min_risk=0.005,  # 0.5%
                    max_risk=0.03   # 3%
                )

                # BUG #5 FIX: Récupérer scalability_data depuis top_pairs
                symbol = best_setup.get('symbol')
                scalability_data = None
                if _app_state and _app_state.get('top_pairs'):
                    for pair in _app_state['top_pairs']:
                        if pair.get('symbol') == symbol:
                            # 🔥 FIX: Utiliser les bonnes clés depuis le scanner (spread, bookDepth, balanceScore, bidVol, askVol)
                            spread_value = pair.get('spread', 0)
                            book_depth = pair.get('bookDepth', 0)
                            balance_score = pair.get('balanceScore', 1.0)
                            bid_vol = pair.get('bidVol', 0)
                            ask_vol = pair.get('askVol', 0)
                            
                            # Vérifier si spread est NaN ou invalide
                            if isinstance(spread_value, float) and (spread_value != spread_value or spread_value == float('nan')):
                                spread_value = 0
                            
                            # 🔥 FIX: Si spread ou depth sont à 0, essayer de récupérer depuis best_setup
                            if spread_value == 0 and best_setup.get('spread_pct'):
                                spread_value = best_setup.get('spread_pct', 0)
                                logger.info(f"💹 Utilisation spread depuis best_setup: {spread_value}%")
                            
                            # 🔥 FIX: Si depth est à 0, calculer depuis bid_vol + ask_vol
                            if book_depth == 0 and (bid_vol > 0 or ask_vol > 0):
                                book_depth = bid_vol + ask_vol
                                logger.info(f"💹 Calcul depth depuis volumes: {book_depth}")
                            
                            scalability_data = {
                                'spread_pct': spread_value,
                                'depth': book_depth,
                                'balance': balance_score,
                                'bid_vol': bid_vol,
                                'ask_vol': ask_vol
                            }
                            
                            logger.info(f"💹 Données scalabilité récupérées depuis top_pairs: spread={spread_value}%, depth={book_depth}, balance={balance_score}")
                            break
                    
                    # 🔥 FIX: Si scalability_data est toujours None ou invalide, essayer depuis best_setup
                    if not scalability_data or (scalability_data.get('spread_pct', 0) == 0 and scalability_data.get('depth', 0) == 0):
                        logger.warning(f"💹 Données scalabilité manquantes dans top_pairs pour {symbol}, tentative depuis best_setup")
                        if best_setup.get('spread_pct'):
                            scalability_data = {
                                'spread_pct': best_setup.get('spread_pct', 0),
                                'depth': best_setup.get('orderbook_depth', 0) or (best_setup.get('bid_vol', 0) + best_setup.get('ask_vol', 0)),
                                'balance': best_setup.get('orderbook_balance', 1.0),
                                'bid_vol': best_setup.get('bid_vol'),
                                'ask_vol': best_setup.get('ask_vol')
                            }
                            logger.info(f"💹 Données scalabilité depuis best_setup: spread={scalability_data.get('spread_pct')}%, depth={scalability_data.get('depth')}")
                else:
                    logger.warning(f"💹 top_pairs non disponible pour récupérer scalability_data pour {symbol}")

                logger.info(f"🎯 Tentative d'ouverture de position: {symbol} {best_setup.get('direction')} (size={position_size:.2f} USDT)")

                # BUG #12 FIX: Fallback atr5m sur atr si absent
                atr = best_setup.get('atr')
                atr5m = best_setup.get('atr5m') or atr  # Fallback sur atr si atr5m absent

                # BUG #6 FIX: Gestion correcte des erreurs avec try/except spécifiques
                # Ouvrir la position (méthode synchrone)
                position_result = _position_manager.open_position(
                    symbol=symbol,
                    direction=best_setup.get('direction'),
                    entry=entry,
                    size=position_size,  # BUG #4: Size calculée correctement
                    atr=atr,
                    atr5m=atr5m,  # BUG #12: Avec fallback
                    confirmed_by=', '.join(best_setup.get('condition_types', [])),
                    scalability_data=scalability_data,  # BUG #5: Données récupérées
                    condition_types=best_setup.get('condition_types', [])
                )

                logger.info(f"✅ Position ouverte: {symbol} {best_setup.get('direction')}")

                # BUG #3 et #9 FIX: Utiliser to_dict() au lieu de créer manuellement
                if _app_state is not None:
                    _app_state['active_position'] = position_result.to_dict()

                # 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif uniquement
                if _ws_manager:
                    await _ws_manager.emit('position_opened', position_result.to_dict())

            except ValueError as e:
                logger.error(f"❌ Erreur validation position: {e}")
            except Exception as e:
                logger.error(f"❌ Erreur ouverture position: {e}", exc_info=True)

        # 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif uniquement
        if _ws_manager:
            await _ws_manager.emit('volume_stats_update', {
                'total': len(results),
                'validated': len(valid_setups),
                'ratio': (len(valid_setups) / len(results) * 100) if results else 0
            })

    except Exception as e:
        logger.error(f"❌ Erreur scan top pairs: {e}")


async def scan_pair_for_setup(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Analyser une paire pour chercher un setup valide

    Args:
        symbol: Symbole de la paire (ex: BTCUSDT)

    Returns:
        Dict avec setup valide: {'symbol': '...', 'direction': '...', 'price': ..., ...}
        Dict avec raison de rejet: {'reason': '...'}
        None si erreur

    Procédure:
    1. Vérifier que le symbol est valide
    2. Appeler analyzer.analyze_pair()
    3. Retourner le résultat ou la raison de rejet
    4. Logger détails en DEBUG
    """
    if not _analyzer or not symbol:
        return None

    try:
        logger.debug(f"🔎 Analyse setup: {symbol}")

        # Récupérer configuration
        from config import TRADING_CONFIG

        use_confluence = TRADING_CONFIG.get('use_confluence', False)
        volume_multiplier = TRADING_CONFIG.get('volume_multiplier', 1.0)
        trend_timeframe = TRADING_CONFIG.get('trend_timeframe', '15m')

        # Calculer trend_data
        trend_data = await _analyzer.calculate_trend_data(symbol, trend_timeframe)

        # Analyser la paire
        analysis = await _analyzer.analyze_pair(
            symbol,
            trend_data=trend_data,
            volume_multiplier=volume_multiplier,
            use_confluence=use_confluence,
            return_reason=True,
            active_positions=[],
            position_manager=_position_manager
        )

        return analysis

    except Exception as e:
        logger.error(f"❌ Erreur analyse {symbol}: {e}")
        return None

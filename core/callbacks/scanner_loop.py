"""
Callbacks pour la boucle de scanner automatique
Exécuté toutes les 45 secondes pour scanner les setups
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from core.postgresql_datalogger import PostgreSQLDataLogger
from core.simple_pg_logger import SimplePGLogger

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
_pg_datalogger = None  # 🔥 PHASE 1: PostgreSQL DataLogger pour ML (injection)
_pg_datalogger_instance = None  # 🔥 Force Initialization: Instance créée automatiquement
_simple_logger = SimplePGLogger()  # 🔥 Simple Logger: Logger ultra-simple sans batch


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


def set_pg_datalogger(pg_datalogger):
    """🔥 PHASE 1: Injecter l'instance PostgreSQLDataLogger"""
    global _pg_datalogger
    _pg_datalogger = pg_datalogger


def get_pg_datalogger():
    """🔥 Force Initialization: Récupérer ou créer l'instance PostgreSQLDataLogger"""
    global _pg_datalogger_instance
    
    # Si une instance a été injectée, l'utiliser en priorité
    if _pg_datalogger is not None:
        return _pg_datalogger
    
    # Sinon, créer une instance si elle n'existe pas
    if _pg_datalogger_instance is None:
        try:
            _pg_datalogger_instance = PostgreSQLDataLogger()
            logger.info("✅ PostgreSQL DataLogger créé (Force Initialization)")
        except Exception as e:
            logger.error(f"❌ Erreur création PostgreSQL DataLogger: {e}")
            return None
    
    return _pg_datalogger_instance


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
                    # 🔥 DEBUG: Vérifier si le setup contient les indicateurs
                    symbol_check = r.get('symbol', 'UNKNOWN')
                    logger.info(f"🔍 DEBUG valid_setups.append({symbol_check}): contient indicators_1m: {'indicators_1m' in r}, indicators_5m: {'indicators_5m' in r}")
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
                
                # 🔥 DEBUG: Log pour voir ce qui est disponible
                logger.info(f"💹 DEBUG: Recherche scalability_data pour {symbol}")
                logger.info(f"💹 DEBUG: best_setup contient spread_pct={best_setup.get('spread_pct')}, keys={list(best_setup.keys())[:10]}")
                
                if _app_state and _app_state.get('top_pairs'):
                    logger.info(f"💹 DEBUG: top_pairs contient {len(_app_state['top_pairs'])} paires")
                    found_pair = False
                    for pair in _app_state['top_pairs']:
                        if pair.get('symbol') == symbol:
                            found_pair = True
                            # 🔥 FIX: Utiliser les bonnes clés depuis le scanner (spread, bookDepth, balanceScore, bidVol, askVol)
                            spread_value = pair.get('spread', 0)
                            book_depth = pair.get('bookDepth', 0)
                            balance_score = pair.get('balanceScore', 1.0)
                            bid_vol = pair.get('bidVol', 0)
                            ask_vol = pair.get('askVol', 0)
                            
                            logger.info(f"💹 DEBUG: Données brutes depuis top_pairs: spread={spread_value}, bookDepth={book_depth}, balanceScore={balance_score}, bidVol={bid_vol}, askVol={ask_vol}")
                            
                            # Vérifier si spread est NaN ou invalide
                            if isinstance(spread_value, float) and (spread_value != spread_value or spread_value == float('nan')):
                                logger.warning(f"💹 DEBUG: spread est NaN, remplacement par 0")
                                spread_value = 0
                            
                            # 🔥 FIX: Si spread ou depth sont à 0, essayer de récupérer depuis best_setup
                            if spread_value == 0:
                                if best_setup.get('spread_pct'):
                                    spread_value = best_setup.get('spread_pct', 0)
                                    logger.info(f"💹 Utilisation spread depuis best_setup: {spread_value}%")
                                else:
                                    logger.warning(f"💹 DEBUG: spread=0 et best_setup.spread_pct non disponible")
                            
                            # 🔥 FIX: Si depth est à 0, calculer depuis bid_vol + ask_vol
                            if book_depth == 0:
                                if bid_vol > 0 or ask_vol > 0:
                                    book_depth = bid_vol + ask_vol
                                    logger.info(f"💹 Calcul depth depuis volumes: {book_depth}")
                                else:
                                    logger.warning(f"💹 DEBUG: depth=0 et volumes bid/ask aussi à 0")
                            
                            scalability_data = {
                                'spread_pct': spread_value,
                                'depth': book_depth,
                                'book_depth': book_depth,  # Alias
                                'balance': balance_score,
                                'balance_score': balance_score,  # Alias
                                'bid_vol': bid_vol,
                                'ask_vol': ask_vol,
                                # Paramètres du scan de scalabilité
                                'recent_volume': pair.get('recentVolume'),
                                'recentVolume': pair.get('recentVolume'),  # Alias
                                'vol5': pair.get('vol5'),
                                'vol15': pair.get('vol15'),
                                'scalability_score': pair.get('score'),
                                'score': pair.get('score'),  # Alias
                            }
                            
                            logger.info(f"💹 Données scalabilité récupérées depuis top_pairs: spread={spread_value}%, depth={book_depth}, balance={balance_score}")
                            break
                    
                    if not found_pair:
                        logger.warning(f"💹 DEBUG: Paire {symbol} non trouvée dans top_pairs")
                    
                    # 🔥 FIX: Si scalability_data est toujours None ou invalide, essayer depuis best_setup
                    if not scalability_data or (scalability_data.get('spread_pct', 0) == 0 and scalability_data.get('depth', 0) == 0):
                        logger.warning(f"💹 Données scalabilité manquantes/invalides dans top_pairs pour {symbol}, tentative depuis best_setup")
                        logger.info(f"💹 DEBUG: best_setup keys: {list(best_setup.keys())}")
                        if best_setup.get('spread_pct'):
                            # Essayer de récupérer depth depuis orderbook_check si disponible
                            orderbook_depth = 0
                            if 'orderbook_check' in best_setup:
                                orderbook_check = best_setup['orderbook_check']
                                # orderbook_check retourne bid_value et ask_value
                                bid_value = orderbook_check.get('bid_value', 0)
                                ask_value = orderbook_check.get('ask_value', 0)
                                orderbook_depth = bid_value + ask_value
                                logger.info(f"💹 DEBUG: Depth calculé depuis orderbook_check: {orderbook_depth}")
                            elif 'orderbook_bid_value' in best_setup and 'orderbook_ask_value' in best_setup:
                                # Utiliser les valeurs stockées directement
                                bid_value = best_setup.get('orderbook_bid_value', 0)
                                ask_value = best_setup.get('orderbook_ask_value', 0)
                                orderbook_depth = bid_value + ask_value
                                logger.info(f"💹 DEBUG: Depth calculé depuis orderbook_bid/ask_value: {orderbook_depth}")
                            elif 'orderbook_ratio' in best_setup:
                                # Si on a le ratio mais pas les valeurs, essayer de récupérer depuis l'orderbook directement
                                logger.warning(f"💹 DEBUG: orderbook_check non disponible mais orderbook_ratio présent")
                            
                            scalability_data = {
                                'spread_pct': best_setup.get('spread_pct', 0),
                                'depth': orderbook_depth or best_setup.get('orderbook_depth', 0) or (best_setup.get('bid_vol', 0) + best_setup.get('ask_vol', 0)),
                                'book_depth': orderbook_depth or best_setup.get('orderbook_depth', 0) or (best_setup.get('bid_vol', 0) + best_setup.get('ask_vol', 0)),  # Alias
                                'balance': best_setup.get('orderbook_balance', 1.0) or best_setup.get('orderbook_check', {}).get('balance', 1.0),
                                'balance_score': best_setup.get('orderbook_balance', 1.0) or best_setup.get('orderbook_check', {}).get('balance', 1.0),  # Alias
                                'bid_vol': best_setup.get('bid_vol'),
                                'ask_vol': best_setup.get('ask_vol'),
                                # Paramètres du scan de scalabilité (essayer depuis best_setup ou top_pairs)
                                'recent_volume': best_setup.get('recent_volume') or best_setup.get('recentVolume'),
                                'recentVolume': best_setup.get('recent_volume') or best_setup.get('recentVolume'),  # Alias
                                'vol5': best_setup.get('vol5'),
                                'vol15': best_setup.get('vol15'),
                                'scalability_score': best_setup.get('scalability_score') or best_setup.get('score'),
                                'score': best_setup.get('scalability_score') or best_setup.get('score'),  # Alias
                            }
                            logger.info(f"💹 Données scalabilité depuis best_setup: spread={scalability_data.get('spread_pct')}%, depth={scalability_data.get('depth')}")
                        else:
                            logger.error(f"💹 ERREUR: Impossible de récupérer spread_pct depuis best_setup pour {symbol}")
                else:
                    logger.warning(f"💹 top_pairs non disponible pour récupérer scalability_data pour {symbol}")

                logger.info(f"🎯 Tentative d'ouverture de position: {symbol} {best_setup.get('direction')} (size={position_size:.2f} USDT)")

                # ✅ Stocker scan_uuid, opportunity_id et setup complet pour Point C
                _position_manager._last_setup_scan_uuid = best_setup.get('_scan_uuid')
                _position_manager._last_setup_opportunity_id = best_setup.get('_opportunity_id')
                
                # 🔥 DEBUG: Vérifier si best_setup contient les indicateurs
                logger.info(f"🔍 DEBUG best_setup pour {symbol}: contient indicators_1m: {'indicators_1m' in best_setup}, indicators_5m: {'indicators_5m' in best_setup}")
                if 'indicators_1m' in best_setup:
                    logger.info(f"✅ indicators_1m présent dans best_setup: {len(best_setup.get('indicators_1m', {}))} clés")
                if 'indicators_5m' in best_setup:
                    logger.info(f"✅ indicators_5m présent dans best_setup: {len(best_setup.get('indicators_5m', {}))} clés")
                
                _position_manager._last_setup = best_setup  # Stocker setup complet pour récupérer indicateurs
                
                # 🔥 DEBUG: Vérifier après stockage
                logger.info(f"🔍 DEBUG _last_setup après stockage: contient indicators_1m: {'indicators_1m' in _position_manager._last_setup}, indicators_5m: {'indicators_5m' in _position_manager._last_setup}")

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

                # 🔥 FIX: Redémarrer WebSocket UNIQUEMENT sur le symbole de la position
                # Ceci garantit que current_price sera mis à jour correctement pendant la position
                if _price_provider:
                    try:
                        # Arrêter WebSocket actuel
                        if hasattr(_price_provider, 'stop_websocket'):
                            await _price_provider.stop_websocket()
                            logger.debug("🔌 WebSocket arrêté pour position")

                        # Redémarrer WebSocket uniquement sur le symbole de la position
                        if hasattr(_price_provider, 'start_websocket'):
                            await _price_provider.start_websocket([symbol])
                            logger.info(f"✅ WebSocket redémarré pour position: {symbol} uniquement")
                    except Exception as e:
                        logger.error(f"❌ Erreur redémarrage WebSocket pour position: {e}")

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
        logger.warning(f"⚠️ scan_pair_for_setup({symbol}): _analyzer={_analyzer is not None}, symbol={bool(symbol)}")
        return None

    try:
        logger.info(f"🔍 DEBUG scan_pair_for_setup({symbol}): DÉBUT - _analyzer: {_analyzer is not None}")
        logger.debug(f"🔎 Analyse setup: {symbol}")
        
        # 🔥 PHASE 3: Mesurer la durée du scan
        import time
        scan_start_time = time.time()

        # Récupérer configuration
        from config import TRADING_CONFIG

        use_confluence = TRADING_CONFIG.get('use_confluence', False)
        volume_multiplier = TRADING_CONFIG.get('volume_multiplier', 1.0)
        trend_timeframe = TRADING_CONFIG.get('trend_timeframe', '15m')

        # Calculer trend_data
        trend_data = await _analyzer.calculate_trend_data(symbol, trend_timeframe)

        # Analyser la paire
        logger.info(f"🔍 DEBUG scan_pair_for_setup({symbol}): AVANT analyze_pair")
        analysis = await _analyzer.analyze_pair(
            symbol,
            trend_data=trend_data,
            volume_multiplier=volume_multiplier,
            use_confluence=use_confluence,
            return_reason=True,
            active_positions=[],
            position_manager=_position_manager
        )
        logger.info(f"🔍 DEBUG scan_pair_for_setup({symbol}): APRÈS analyze_pair, analysis: {analysis is not None}, type: {type(analysis)}")

        # 🔥 DEBUG: Vérifier ce que contient analysis
        if analysis:
            logger.info(f"🔍 DEBUG scan_pair_for_setup({symbol}): analysis type: {type(analysis)}, keys: {list(analysis.keys())[:15] if isinstance(analysis, dict) else 'N/A'}")
        else:
            logger.warning(f"⚠️ scan_pair_for_setup({symbol}): analysis est None ou False")

        # 🔥 FIX: Ajouter indicators_1m et indicators_5m à analysis IMMÉDIATEMENT après analyze_pair
        # pour qu'ils soient disponibles dans _last_setup
        if analysis and isinstance(analysis, dict):
            # Extraire les indicateurs depuis analysis si disponibles
            # Les indicateurs peuvent être dans analysis directement ou dans des sous-dictionnaires
            indicators_1m = analysis.get('indicators_1m', {})
            indicators_5m = analysis.get('indicators_5m', {})
            
            logger.info(f"🔍 DEBUG scan_pair_for_setup({symbol}): indicators_1m présent: {bool(indicators_1m)}, indicators_5m présent: {bool(indicators_5m)}")
            
            # Si les indicateurs ne sont pas présents, essayer de les construire depuis les données disponibles
            if not indicators_1m:
                logger.info(f"🔧 Construction indicators_1m depuis analysis pour {symbol}")
                # Si analysis contient 'reason' (aucun setup valide), extraire depuis analysis_1m
                if 'reason' in analysis and 'analysis_1m' in analysis and analysis['analysis_1m']:
                    analysis_1m = analysis['analysis_1m']
                    indicators_1m = {
                        'rsi': analysis_1m.get('rsi'),
                        'rsi_prev': analysis_1m.get('rsi_prev'),
                        'macd': analysis_1m.get('macd'),
                        'macd_signal': analysis_1m.get('macd_signal'),
                        'macd_hist': analysis_1m.get('macd_hist'),
                        'macd_hist_prev': analysis_1m.get('macd_hist_prev'),
                        'adx': analysis_1m.get('adx'),
                        'di_plus': analysis_1m.get('di_plus'),
                        'di_minus': analysis_1m.get('di_minus'),
                        'di_gap': analysis_1m.get('di_gap'),
                        'ema9': analysis_1m.get('ema9'),
                        'ema21': analysis_1m.get('ema21'),
                        'ema_diff_pct': analysis_1m.get('ema_diff_pct'),
                        'atr': analysis_1m.get('atr'),
                        'atr_pct': analysis_1m.get('atr_pct'),
                        'bb_upper': analysis_1m.get('bb_upper'),
                        'bb_middle': analysis_1m.get('bb_middle'),
                        'bb_lower': analysis_1m.get('bb_lower'),
                        'bb_width': analysis_1m.get('bb_width'),
                        'bb_distance_to_lower': analysis_1m.get('bb_distance_to_lower'),
                        'bb_distance_to_upper': analysis_1m.get('bb_distance_to_upper'),
                        'volume': analysis_1m.get('volume'),
                        'volume_avg': analysis_1m.get('volume_avg'),
                        'volume_ratio': analysis_1m.get('volumeSpike'),
                        'volume_spike': analysis_1m.get('volumeSpike'),
                    }
                else:
                    # Construire indicators_1m depuis les données disponibles dans analysis
                    indicators_1m = {
                        'rsi': analysis.get('rsi'),
                        'rsi_prev': analysis.get('rsi_prev'),
                        'macd': analysis.get('macd'),
                        'macd_signal': analysis.get('macd_signal'),
                        'macd_hist': analysis.get('macd_hist'),
                        'macd_hist_prev': analysis.get('macd_hist_prev'),
                        'adx': analysis.get('adx'),
                        'di_plus': analysis.get('di_plus'),
                        'di_minus': analysis.get('di_minus'),
                        'di_gap': analysis.get('di_gap'),
                        'ema9': analysis.get('ema9'),
                        'ema21': analysis.get('ema21'),
                        'ema_diff_pct': analysis.get('ema_diff_pct'),
                        'atr': analysis.get('atr'),
                        'atr_pct': analysis.get('atr_pct'),
                        'bb_upper': analysis.get('bb_upper'),
                        'bb_middle': analysis.get('bb_middle'),
                        'bb_lower': analysis.get('bb_lower'),
                        'bb_width': analysis.get('bb_width'),
                        'bb_distance_to_lower': analysis.get('bb_distance_to_lower'),
                        'bb_distance_to_upper': analysis.get('bb_distance_to_upper'),
                        'volume': analysis.get('volume'),
                        'volume_avg': analysis.get('volume_avg'),
                        'volume_ratio': analysis.get('volume_ratio') or analysis.get('volumeSpike'),
                        'volume_spike': analysis.get('volume_spike'),
                    }
            
            # Si indicators_5m n'est pas présent, essayer de le construire depuis les données disponibles
            if not indicators_5m:
                logger.info(f"🔧 Construction indicators_5m depuis analysis pour {symbol}")
                # Si analysis contient 'reason' (aucun setup valide), extraire depuis analysis_5m
                if 'reason' in analysis and 'analysis_5m' in analysis and analysis['analysis_5m']:
                    analysis_5m = analysis['analysis_5m']
                    indicators_5m = {
                        'rsi': analysis_5m.get('rsi'),
                        'rsi_prev': analysis_5m.get('rsi_prev'),
                        'macd': analysis_5m.get('macd'),
                        'macd_signal': analysis_5m.get('macd_signal'),
                        'macd_hist': analysis_5m.get('macd_hist'),
                        'macd_hist_prev': analysis_5m.get('macd_hist_prev'),
                        'adx': analysis_5m.get('adx'),
                        'di_plus': analysis_5m.get('di_plus'),
                        'di_minus': analysis_5m.get('di_minus'),
                        'di_gap': analysis_5m.get('di_gap'),
                        'ema9': analysis_5m.get('ema9'),
                        'ema21': analysis_5m.get('ema21'),
                        'ema_diff_pct': analysis_5m.get('ema_diff_pct'),
                        'atr': analysis_5m.get('atr'),
                        'atr_pct': analysis_5m.get('atr_pct'),
                        'bb_upper': analysis_5m.get('bb_upper'),
                        'bb_middle': analysis_5m.get('bb_middle'),
                        'bb_lower': analysis_5m.get('bb_lower'),
                        'bb_width': analysis_5m.get('bb_width'),
                        'bb_distance_to_lower': analysis_5m.get('bb_distance_to_lower'),
                        'bb_distance_to_upper': analysis_5m.get('bb_distance_to_upper'),
                        'volume': analysis_5m.get('volume'),
                        'volume_avg': analysis_5m.get('volume_avg'),
                        'volume_ratio': analysis_5m.get('volumeSpike'),
                        'volume_spike': analysis_5m.get('volumeSpike'),
                    }
                else:
                    # Pour indicators_5m, on peut utiliser les mêmes données ou des variantes 5m si disponibles
                    indicators_5m = {
                        'rsi': analysis.get('rsi_5m'),
                        'rsi_prev': analysis.get('rsi_prev_5m'),
                        'macd': analysis.get('macd_5m'),
                        'macd_signal': analysis.get('macd_signal_5m'),
                        'macd_hist': analysis.get('macd_hist_5m'),
                        'macd_hist_prev': analysis.get('macd_hist_prev_5m'),
                        'adx': analysis.get('adx_5m'),
                        'di_plus': analysis.get('di_plus_5m'),
                        'di_minus': analysis.get('di_minus_5m'),
                        'di_gap': analysis.get('di_gap_5m'),
                        'ema9': analysis.get('ema9_5m'),
                        'ema21': analysis.get('ema21_5m'),
                        'ema_diff_pct': analysis.get('ema_diff_pct_5m'),
                        'atr': analysis.get('atr5m') or analysis.get('atr_5m'),
                        'atr_pct': analysis.get('atr_pct_5m'),
                        'bb_upper': analysis.get('bb_upper_5m'),
                        'bb_middle': analysis.get('bb_middle_5m'),
                        'bb_lower': analysis.get('bb_lower_5m'),
                        'bb_width': analysis.get('bb_width_5m'),
                        'bb_distance_to_lower': analysis.get('bb_distance_to_lower_5m'),
                        'bb_distance_to_upper': analysis.get('bb_distance_to_upper_5m'),
                        'volume': analysis.get('volume_5m'),
                        'volume_avg': analysis.get('volume_avg_5m'),
                        'volume_ratio': analysis.get('volume_ratio_5m'),
                        'volume_spike': analysis.get('volume_spike_5m'),
                    }
            
            # Ajouter les indicateurs à analysis
            analysis['indicators_1m'] = indicators_1m
            analysis['indicators_5m'] = indicators_5m
            logger.info(f"✅ Indicateurs ajoutés à analysis pour {symbol}: indicators_1m keys: {len(indicators_1m)}, indicators_5m keys: {len(indicators_5m)}")
        else:
            logger.warning(f"⚠️ analysis n'est pas un dict pour {symbol}: {type(analysis)}")

        # 🔥 DEBUG: Vérifier que le code atteint cette section AVANT Simple Logger
        logger.info(f"🔍 DEBUG scan_pair_for_setup({symbol}): AVANT Simple Logger, analysis type: {type(analysis)}")

        # 🔥 Simple Logger: Logger ultra-simple sans batch
        try:
            # Vérifier que _simple_logger est défini et accessible
            try:
                logger.info(f"🔍 DEBUG Simple Logger pour {symbol}: _simple_logger existe, enabled={getattr(_simple_logger, 'enabled', 'ATTRIBUT_MANQUANT')}")
            except NameError:
                logger.error(f"❌ _simple_logger n'est pas défini pour {symbol}")
                _simple_logger = None
            except Exception as e:
                logger.error(f"❌ Erreur accès _simple_logger pour {symbol}: {e}")
                _simple_logger = None
            
            if _simple_logger and hasattr(_simple_logger, 'enabled') and _simple_logger.enabled:
                logger.info(f"📝 Tentative log_scan_simple pour {symbol}")
                result = _simple_logger.log_scan_simple(symbol, {
                    'market_data': {'price': analysis.get('price') if analysis else None},
                    'indicators_1m': analysis.get('indicators_1m', {}) if analysis else {},
                    'scores': {'score_total': analysis.get('score_total') if analysis else None},
                    'is_opportunity': bool(analysis and 'direction' in analysis and ('entry' in analysis or 'price' in analysis)) if analysis else False
                })
                logger.info(f"📝 Résultat log_scan_simple pour {symbol}: {result}")
            else:
                logger.warning(f"⚠️ Simple Logger désactivé pour {symbol}")
        except Exception as e:
            logger.error(f"❌ Erreur Simple Logger pour {symbol}: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")

        # 🔥 DEBUG: Vérifier que le code atteint cette section
        logger.info(f"🔍 DEBUG scan_pair_for_setup({symbol}): APRÈS ajout indicateurs, AVANT calcul durée scan")

        # 🔥 PHASE 3: Calculer durée du scan
        try:
            scan_duration_ms = int((time.time() - scan_start_time) * 1000)
            logger.info(f"🔍 DEBUG scan_pair_for_setup({symbol}): scan_duration_ms={scan_duration_ms}ms, AVANT vérification pg_datalogger")
        except Exception as e:
            logger.error(f"❌ Erreur calcul scan_duration_ms pour {symbol}: {e}")
            scan_duration_ms = 0
        
        # 🔥 PHASE 1: Logger le scan dans PostgreSQL si activé
        # Force Initialization: Utiliser get_pg_datalogger() qui crée l'instance si nécessaire
        pg_datalogger = get_pg_datalogger()
        
        try:
            logger.info(f"🔍 DEBUG scan_pair_for_setup({symbol}): pg_datalogger={pg_datalogger is not None}, enabled={getattr(pg_datalogger, 'enabled', False) if pg_datalogger else False}")
        except Exception as e:
            logger.error(f"❌ Erreur log pg_datalogger pour {symbol}: {e}")
        
        if pg_datalogger and pg_datalogger.enabled:
            try:
                logger.info(f"📝 Tentative de log scan PostgreSQL pour {symbol}")
                # Récupérer les données du scan de scalabilité depuis top_pairs
                scalability_data = {}
                if _app_state and _app_state.get('top_pairs'):
                    for pair in _app_state['top_pairs']:
                        if pair.get('symbol') == symbol:
                            scalability_data = {
                                'recent_volume': pair.get('recentVolume'),
                                'vol5': pair.get('vol5'),
                                'vol15': pair.get('vol15'),
                                'scalability_score': pair.get('score'),
                            }
                            break
                
                # Préparer les données du scan pour PostgreSQL
                # 🔥 FIX: Récupérer le prix avec fallbacks (pour éviter NULL)
                scan_price = None
                if analysis and isinstance(analysis, dict):
                    scan_price = analysis.get('price')
                
                # Fallback: Depuis analysis_1m ou analysis_5m si disponible
                if scan_price is None and analysis:
                    analysis_1m = analysis.get('analysis_1m', {})
                    if isinstance(analysis_1m, dict):
                        scan_price = analysis_1m.get('price')
                    if scan_price is None:
                        analysis_5m = analysis.get('analysis_5m', {})
                        if isinstance(analysis_5m, dict):
                            scan_price = analysis_5m.get('price')
                
                # Extraire la valeur numérique si scan_price est un dict
                if isinstance(scan_price, dict):
                    scan_price = scan_price.get('price') or scan_price.get('lastPrice') or scan_price.get('close') or scan_price.get('value')
                
                # Vérifier que scan_price est un nombre
                if scan_price is not None and not isinstance(scan_price, (int, float)):
                    try:
                        scan_price = float(scan_price)
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Prix invalide pour {symbol}: {scan_price} (type: {type(scan_price)})")
                        scan_price = None
                
                scan_data = {
                    'scan_duration_ms': scan_duration_ms,
                    'market_data': {
                        'price': scan_price,
                        'spread_pct': analysis.get('spread_pct') if analysis else None,
                        'book_depth': analysis.get('book_depth') if analysis else None,
                        'balance_score': analysis.get('balance_score') if analysis else None,
                        'bid_vol': analysis.get('bid_vol') if analysis else None,
                        'ask_vol': analysis.get('ask_vol') if analysis else None,
                        'orderbook_imbalance_ratio': analysis.get('orderbook_imbalance_ratio') if analysis else None,
                        # Paramètres du scan de scalabilité
                        'recent_volume': scalability_data.get('recent_volume'),
                        'vol5': scalability_data.get('vol5'),
                        'vol15': scalability_data.get('vol15'),
                        'scalability_score': scalability_data.get('scalability_score'),
                    },
                    # Ajouter aussi au niveau racine pour les fallbacks
                    'price': scan_price,  # 🔥 FIX: Ajouter le prix au niveau racine pour les fallbacks
                    'recent_volume': scalability_data.get('recent_volume'),
                    'recentVolume': scalability_data.get('recent_volume'),  # Alias
                    'vol5': scalability_data.get('vol5'),
                    'vol15': scalability_data.get('vol15'),
                    'scalability_score': scalability_data.get('scalability_score'),
                    'score': scalability_data.get('scalability_score'),  # Alias
                    'indicators_1m': analysis.get('indicators_1m', {}) if analysis else {},
                    'indicators_5m': analysis.get('indicators_5m', {}) if analysis else {},
                    'filters': analysis.get('filters', {}) if analysis else {},
                    'scores': {
                        'score_1m': analysis.get('score_1m') if analysis else None,
                        'score_5m': analysis.get('score_5m') if analysis else None,
                        'score_total': analysis.get('score_total') if analysis else None,
                        'score_long_1m': analysis.get('score_long_1m') if analysis else None,
                        'score_short_1m': analysis.get('score_short_1m') if analysis else None,
                        'score_long_5m': analysis.get('score_long_5m') if analysis else None,
                        'score_short_5m': analysis.get('score_short_5m') if analysis else None,
                    },
                    'patterns': {
                        'pattern_1m': analysis.get('pattern_1m') if analysis else None,
                        'pattern_multi_1m': analysis.get('pattern_multi_1m') if analysis else None,
                        'pattern_5m': analysis.get('pattern_5m') if analysis else None,
                        'pattern_multi_5m': analysis.get('pattern_multi_5m') if analysis else None,
                    },
                    'use_confluence': use_confluence,
                    'confluence_met': analysis.get('confluence_met') if analysis else False,
                    'timeframes_aligned': analysis.get('timeframes_aligned') if analysis else False,
                    'trend_timeframe': trend_timeframe,
                    'trend_direction': trend_data.get('trend') if trend_data else None,  # 'trend' pas 'direction'
                    'trend_strength': None,  # trend_data.get('strength') est une chaîne ('STRONG', 'MODERATE', 'NONE'), pas un FLOAT
                    'trend_bonus': trend_data.get('bonus') if trend_data else None,
                    'divergence_detected': analysis.get('divergence_detected') if analysis else False,
                    'divergence_type': analysis.get('divergence_type') if analysis else None,
                    'divergence_bonus': analysis.get('divergence_bonus') if analysis else 0,
                    'is_opportunity': bool(analysis and 'direction' in analysis and ('entry' in analysis or 'price' in analysis)),
                    'opportunity_direction': analysis.get('direction') if analysis and 'direction' in analysis else None,
                    'reject_reason': analysis.get('reason') if analysis and 'reason' in analysis else None,
                    'reject_reason_category': analysis.get('reject_category') if analysis else None,
                    'params_snapshot': {
                        'volume_multiplier': volume_multiplier,
                        'use_confluence': use_confluence,
                        'trend_timeframe': trend_timeframe,
                        # Ajouter toutes les variables de TRADING_CONFIG pertinentes pour le scan
                        'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),
                        'min_conditions': TRADING_CONFIG.get('min_conditions', 6),
                        'use_weighted_scoring': TRADING_CONFIG.get('use_weighted_scoring', True),
                        'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
                        'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
                        'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
                        'optimal_atr_min_1m': TRADING_CONFIG.get('optimal_atr_min_1m', 0.12),
                        'optimal_atr_max_1m': TRADING_CONFIG.get('optimal_atr_max_1m', 0.75),
                        'optimal_atr_min_5m': TRADING_CONFIG.get('optimal_atr_min_5m', 0.22),
                        'optimal_atr_max_5m': TRADING_CONFIG.get('optimal_atr_max_5m', 1.4),
                        'use_breakout': TRADING_CONFIG.get('use_breakout', True),
                        'use_snr': TRADING_CONFIG.get('use_snr', True),
                        'use_wick': TRADING_CONFIG.get('use_wick', True),
                        'use_divergence': TRADING_CONFIG.get('use_divergence', True),
                    }
                }
                
                # Logger le scan (mode batch par défaut)
                logger.info(f"📝 Appel log_scan() pour {symbol}")
                scan_id = pg_datalogger.log_scan(symbol, scan_data, use_batch=True)
                logger.info(f"✅ log_scan() terminé pour {symbol} (scan_id={scan_id})")
                
                # Si c'est une opportunité, logger aussi dans opportunities
                # Note: En mode batch, scan_id est None, mais l'opportunité sera loggée
                # avec scan_id=None temporairement (sera mis à jour lors du flush)
                if scan_data['is_opportunity'] and analysis:
                    opportunity_data = {
                        'status': 'PENDING',
                        'direction': analysis.get('direction'),
                        'setup_score': analysis.get('score_total'),
                        'conditions_matched': analysis.get('condition_types', []),
                        'entry_price': analysis.get('entry') or analysis.get('price'),
                        'tp_price': analysis.get('tp'),
                        'sl_price': analysis.get('sl'),
                        'size_usdt': None,  # Sera calculé lors de l'ouverture
                        'risk_usdt': None,
                        'reward_risk_ratio': None,
                    }
                    # En mode batch, on passe scan_id=None temporairement
                    # Le scan_id sera résolu lors du flush batch
                    pg_datalogger.log_opportunity(
                        scan_id or 0,  # 0 = temporaire, sera mis à jour
                        symbol, 
                        opportunity_data,
                        use_batch=True
                    )
                    
            except Exception as e:
                logger.error(f"❌ Erreur logging PostgreSQL pour {symbol}: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
        
        return analysis

    except Exception as e:
        logger.error(f"❌ Erreur analyse {symbol}: {e}")
        
        # 🔥 PHASE 3: Logger l'erreur dans PostgreSQL si activé
        # Force Initialization: Utiliser get_pg_datalogger() qui crée l'instance si nécessaire
        pg_datalogger = get_pg_datalogger()
        
        if pg_datalogger and pg_datalogger.enabled:
            try:
                import traceback
                error_details = {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'stack': traceback.format_exc()
                }
                pg_datalogger.log_scan_error(
                    symbol=symbol,
                    error_type='SCAN_ERROR',
                    error_message=str(e),
                    error_details=error_details
                )
            except Exception as log_error:
                logger.warning(f"⚠️ Erreur logging erreur scan: {log_error}")
        
        return None

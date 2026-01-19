"""
Post-Exit Tracking Loop - Trade Cursor v7.0
Boucle dédiée pour récupérer les prix des symboles en tracking post-exit
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Variables globales injectées
_price_provider = None
_is_running = False
_task: Optional[asyncio.Task] = None

# Configuration
POST_EXIT_LOOP_INTERVAL_SEC = 1.0  # 1 seconde entre chaque cycle


def set_price_provider(price_provider):
    """Injecter l'instance price_provider"""
    global _price_provider
    _price_provider = price_provider


async def post_exit_loop():
    """
    Boucle principale pour le tracking post-exit
    
    Récupère les prix pour tous les symboles en cours de tracking
    et les envoie au PostExitManager.
    """
    global _is_running
    _is_running = True
    
    logger.warning("\ud83d\udd04 Post-Exit Loop démarrée")
    
    while _is_running:
        try:
            # Importer ici pour éviter import circulaire
            from core.post_exit import get_post_exit_manager
            post_exit_mgr = get_post_exit_manager()
            
            # Récupérer les symboles actifs
            active_symbols = post_exit_mgr.get_active_symbols()
            
            if not active_symbols:
                # Pas de trackers actifs, attendre (pas de log pour éviter spam)
                await asyncio.sleep(POST_EXIT_LOOP_INTERVAL_SEC * 2)
                continue
            
            # Log uniquement toutes les 30 itérations pour réduire le spam
            if not hasattr(post_exit_loop, '_iteration_count'):
                post_exit_loop._iteration_count = 0
            post_exit_loop._iteration_count += 1
            if post_exit_loop._iteration_count % 30 == 1:
                logger.warning(f"\ud83d\udcca PostExit Loop: {len(active_symbols)} symboles actifs: {active_symbols}")
            
            if not _price_provider:
                logger.warning("Pas de price provider disponible")
                await asyncio.sleep(POST_EXIT_LOOP_INTERVAL_SEC)
                continue
            
            # Récupérer les prix pour chaque symbole en tracking
            for symbol in active_symbols:
                try:
                    price_data = await _price_provider.get_price(symbol)
                    if price_data:
                        # Extraire le prix (peut être dict ou float)
                        price = None
                        if isinstance(price_data, dict):
                            # 🔥 FIX: Utiliser les bonnes clés MEXC (lastPrice, markPrice, fairPrice, referencePrice)
                            price = (
                                price_data.get('lastPrice') or 
                                price_data.get('markPrice') or 
                                price_data.get('fairPrice') or
                                price_data.get('referencePrice') or
                                price_data.get('price') or 
                                price_data.get('last') or 
                                price_data.get('mark')
                            )
                            # Convertir en float si c'est une string
                            if isinstance(price, str):
                                try:
                                    price = float(price)
                                except:
                                    price = None
                        else:
                            price = float(price_data)
                        
                        if price and price > 0:
                            post_exit_mgr.on_price_update_sync(symbol, price)
                        # Pas de log pour prix invalide (trop spammy)
                except Exception as e:
                    logger.debug(f"Erreur récupération prix {symbol}: {e}")
            
            await asyncio.sleep(POST_EXIT_LOOP_INTERVAL_SEC)
            
        except asyncio.CancelledError:
            logger.warning("Post-Exit Loop annulée")
            break
        except Exception as e:
            logger.error(f"Erreur post_exit_loop: {e}")
            await asyncio.sleep(POST_EXIT_LOOP_INTERVAL_SEC * 2)
    
    _is_running = False
    logger.warning("Post-Exit Loop arrêtée")


async def start_post_exit_loop():
    """Démarrer la boucle post-exit"""
    global _task
    
    if _task and not _task.done():
        logger.warning("⚠️ Post-Exit Loop déjà en cours")
        return
    
    _task = asyncio.create_task(post_exit_loop())
    logger.warning("\u2705 Post-Exit Loop task créée")


async def stop_post_exit_loop():
    """Arrêter la boucle post-exit"""
    global _is_running, _task
    
    _is_running = False
    
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    
    _task = None
    logger.info("🛑 Post-Exit Loop stoppée")


def is_running() -> bool:
    """Vérifier si la boucle est en cours"""
    return _is_running

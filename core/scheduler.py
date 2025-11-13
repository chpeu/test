#!/usr/bin/env python3
"""
Scheduler pour les boucles automatiques
- Scanner loop: 45s
- Position check loop: 2s
- Scalability refresh: 90s
"""

import asyncio
import logging
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class Scheduler:
    """Gestionnaire de tâches périodiques"""
    
    def __init__(self):
        self.scanner_task: Optional[asyncio.Task] = None
        self.position_check_task: Optional[asyncio.Task] = None
        self.scalability_refresh_task: Optional[asyncio.Task] = None
        self.is_running = False

        # Callbacks
        self.scanner_callback: Optional[Callable] = None
        self.position_check_callback: Optional[Callable] = None
        self.scalability_refresh_callback: Optional[Callable] = None

        # Compteurs d'erreurs pour éviter boucles infinies d'erreurs
        self.scanner_error_count = 0
        self.position_check_error_count = 0
        self.scalability_refresh_error_count = 0
        self.max_consecutive_errors = 10  # Maximum d'erreurs consécutives avant arrêt
    
    def set_scanner_callback(self, callback: Callable):
        """Définir callback pour scanner (appelé toutes les 45s)"""
        self.scanner_callback = callback
    
    def set_position_check_callback(self, callback: Callable):
        """Définir callback pour position check (appelé toutes les 0.1s)"""
        self.position_check_callback = callback
    
    def set_scalability_refresh_callback(self, callback: Callable):
        """Définir callback pour scalability refresh (appelé toutes les 90s)"""
        self.scalability_refresh_callback = callback
    
    async def _scanner_loop(self):
        """Boucle scanner - toutes les 45 secondes"""
        while self.is_running:
            try:
                if self.scanner_callback:
                    await self.scanner_callback()

                # Réinitialiser le compteur d'erreurs en cas de succès
                self.scanner_error_count = 0

                # Attendre 45 secondes
                await asyncio.sleep(45)
            except asyncio.CancelledError:
                logger.info("Scanner loop annulé")
                raise
            except Exception as e:
                self.scanner_error_count += 1
                logger.error(
                    f"Erreur dans scanner loop ({self.scanner_error_count}/{self.max_consecutive_errors}): {e}",
                    exc_info=True
                )

                if self.scanner_error_count >= self.max_consecutive_errors:
                    logger.critical(f"Trop d'erreurs consécutives dans scanner loop, arrêt de la boucle")
                    self.is_running = False
                    break

                await asyncio.sleep(5)  # Attendre un peu avant de réessayer
    
    async def _position_check_loop(self):
        """Boucle position check - toutes les 0.1 secondes (optimisé pour scalping ultra-rapide)"""
        while self.is_running:
            try:
                if self.position_check_callback:
                    await self.position_check_callback()

                # Réinitialiser le compteur d'erreurs en cas de succès
                self.position_check_error_count = 0

                # 🔥 FIX: Réduire à 0.1s pour scalping ultra-rapide (latence minimale)
                # WebSocket émet déjà en temps réel, mais cette boucle sert de backup
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                logger.info("Position check loop annulé")
                raise
            except Exception as e:
                self.position_check_error_count += 1
                logger.error(
                    f"Erreur dans position check loop ({self.position_check_error_count}/{self.max_consecutive_errors}): {e}",
                    exc_info=True
                )

                if self.position_check_error_count >= self.max_consecutive_errors:
                    logger.critical(f"Trop d'erreurs consécutives dans position check loop, arrêt de la boucle")
                    self.is_running = False
                    break

                await asyncio.sleep(1)  # Attendre un peu avant de réessayer
    
    async def _scalability_refresh_loop(self):
        """Boucle scalability refresh - toutes les 90 secondes"""
        while self.is_running:
            try:
                if self.scalability_refresh_callback:
                    await self.scalability_refresh_callback()

                # Réinitialiser le compteur d'erreurs en cas de succès
                self.scalability_refresh_error_count = 0

                # Attendre 90 secondes
                await asyncio.sleep(90)
            except asyncio.CancelledError:
                logger.info("Scalability refresh loop annulé")
                raise
            except Exception as e:
                self.scalability_refresh_error_count += 1
                logger.error(
                    f"Erreur dans scalability refresh loop ({self.scalability_refresh_error_count}/{self.max_consecutive_errors}): {e}",
                    exc_info=True
                )

                if self.scalability_refresh_error_count >= self.max_consecutive_errors:
                    logger.critical(f"Trop d'erreurs consécutives dans scalability refresh loop, arrêt de la boucle")
                    self.is_running = False
                    break

                await asyncio.sleep(10)  # Attendre un peu avant de réessayer
    
    def _handle_task_done(self, task_name: str, task: asyncio.Task):
        """Callback appelé quand une task se termine"""
        try:
            exception = task.exception()
            if exception and not isinstance(exception, asyncio.CancelledError):
                logger.error(f"Task {task_name} crashed: {exception}", exc_info=exception)
        except asyncio.CancelledError:
            logger.info(f"Task {task_name} annulée")
        except Exception as e:
            logger.error(f"Erreur dans task done callback pour {task_name}: {e}", exc_info=True)

    def start(self):
        """Démarrer toutes les boucles"""
        if self.is_running:
            logger.warning("Scheduler déjà démarré")
            return

        self.is_running = True

        # Démarrer scanner loop avec callback d'erreur
        if self.scanner_callback:
            self.scanner_task = asyncio.create_task(self._scanner_loop())
            self.scanner_task.add_done_callback(lambda t: self._handle_task_done("scanner_loop", t))
            logger.info("✅ Scanner loop démarré (45s)")

        # Démarrer position check loop avec callback d'erreur
        if self.position_check_callback:
            self.position_check_task = asyncio.create_task(self._position_check_loop())
            self.position_check_task.add_done_callback(lambda t: self._handle_task_done("position_check_loop", t))
            logger.info("✅ Position check loop démarré (0.1s)")

        # Démarrer scalability refresh loop avec callback d'erreur
        if self.scalability_refresh_callback:
            self.scalability_refresh_task = asyncio.create_task(self._scalability_refresh_loop())
            self.scalability_refresh_task.add_done_callback(lambda t: self._handle_task_done("scalability_refresh_loop", t))
            logger.info("✅ Scalability refresh loop démarré (90s)")
    
    def stop(self):
        """Arrêter toutes les boucles"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Arrêter les tâches
        if self.scanner_task:
            self.scanner_task.cancel()
            self.scanner_task = None
        
        if self.position_check_task:
            self.position_check_task.cancel()
            self.position_check_task = None
        
        if self.scalability_refresh_task:
            self.scalability_refresh_task.cancel()
            self.scalability_refresh_task = None
        
        logger.info("🛑 Scheduler arrêté")
    
    async def stop_async(self):
        """Arrêter toutes les boucles (version async)"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Arrêter les tâches proprement
        tasks = []
        if self.scanner_task:
            tasks.append(self.scanner_task)
        if self.position_check_task:
            tasks.append(self.position_check_task)
        if self.scalability_refresh_task:
            tasks.append(self.scalability_refresh_task)
        
        for task in tasks:
            task.cancel()
        
        # Attendre que les tâches se terminent
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("🛑 Scheduler arrêté")




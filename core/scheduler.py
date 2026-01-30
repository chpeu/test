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
    
    def set_scanner_callback(self, callback: Callable):
        """Définir callback pour scanner (appelé toutes les 45s)"""
        self.scanner_callback = callback
    
    def set_position_check_callback(self, callback: Callable):
        """Définir callback pour position check (appelé toutes les 0.1s)"""
        self.position_check_callback = callback
    
    def set_scalability_refresh_callback(self, callback: Callable):
        """Définir callback pour scalability refresh (appelé toutes les 90s)"""
        self.scalability_refresh_callback = callback

    def _attach_task_monitor(self, name: str, task: asyncio.Task) -> None:
        """Ajouter un callback de monitoring pour tracer les arrêts inattendus."""
        def _on_done(done_task: asyncio.Task) -> None:
            try:
                if done_task.cancelled():
                    logger.warning(f"⚠️ Tâche '{name}' annulée")
                    return
                exc = done_task.exception()
                if exc:
                    logger.error(f"❌ Tâche '{name}' arrêtée avec erreur: {exc}", exc_info=exc)
                else:
                    logger.warning(f"⚠️ Tâche '{name}' terminée sans exception (arrêt inattendu)")
            except Exception:
                logger.error(f"❌ Erreur monitoring tâche '{name}'", exc_info=True)

        task.add_done_callback(_on_done)
    
    async def _scanner_loop(self):
        """Boucle scanner - toutes les 45 secondes"""
        logger.info("📡 Boucle scanner démarrée")
        while self.is_running:
            try:
                if self.scanner_callback:
                    logger.info("🔍 Exécution du callback scanner...")
                    await self.scanner_callback()
                
                # Attendre 45 secondes
                await asyncio.sleep(45)
            except Exception as e:
                logger.error(f"Erreur dans scanner loop: {e}")
                await asyncio.sleep(5)  # Attendre un peu avant de réessayer
    
    async def _position_check_loop(self):
        """Boucle position check - toutes les 0.1 secondes (optimisé pour scalping ultra-rapide)"""
        logger.info("🛡️ Boucle position check démarrée")
        while self.is_running:
            try:
                if self.position_check_callback:
                    await self.position_check_callback()
                
                # 🔥 FIX: Réduire à 0.1s pour scalping ultra-rapide (latence minimale)
                # WebSocket émet déjà en temps réel, mais cette boucle sert de backup
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Erreur dans position check loop: {e}")
                await asyncio.sleep(1)  # Attendre un peu avant de réessayer
    
    async def _scalability_refresh_loop(self):
        """Boucle scalability refresh - toutes les 90 secondes"""
        logger.info("📊 Boucle scalability refresh démarrée")
        # 🔥 FIX: Ne pas attendre 60s au démarrage pour que le régime soit détecté immédiatement
        # (L'attente initiale causait une confusion sur l'automatisme du régime)
        
        while self.is_running:
            try:
                if self.scalability_refresh_callback:
                    logger.info("📊 Exécution du callback scalability refresh...")
                    await self.scalability_refresh_callback()
                
                # Attendre l'intervalle défini (adaptatif basé sur volatilité)
                try:
                    from core.callbacks.scalability_refresh import get_current_interval
                    interval = get_current_interval()
                except ImportError:
                    interval = 90
                
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Erreur dans scalability refresh loop: {e}")
                await asyncio.sleep(10)
    
    def start(self):
        """Démarrer toutes les boucles"""
        if self.is_running:
            logger.warning("⚠️ Scheduler déjà démarré, skip start()")
            return
        
        self.is_running = True
        logger.info("🚀 Démarrage des boucles du Scheduler...")
        
        # Démarrer scanner loop
        if self.scanner_callback:
            self.scanner_task = asyncio.create_task(self._scanner_loop())
            self._attach_task_monitor("scanner_loop", self.scanner_task)
            logger.info("✅ Scanner loop démarré (45s)")
        
        # Démarrer position check loop
        if self.position_check_callback:
            self.position_check_task = asyncio.create_task(self._position_check_loop())
            self._attach_task_monitor("position_check_loop", self.position_check_task)
            logger.info("✅ Position check loop démarré (0.1s)")
        
        # Démarrer scalability refresh loop
        if self.scalability_refresh_callback:
            self.scalability_refresh_task = asyncio.create_task(self._scalability_refresh_loop())
            self._attach_task_monitor("scalability_refresh_loop", self.scalability_refresh_task)
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




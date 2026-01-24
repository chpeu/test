"""
🔥 SPRINT 1.3: Graceful Shutdown Manager

Gère l'arrêt propre de l'application avec cleanup orchestré des ressources.

Utilisation:
```python
from core.shutdown import GracefulShutdown

shutdown_manager = GracefulShutdown()

# Enregistrer ressources à nettoyer
shutdown_manager.register("database", db.close, async_cleanup=False)
shutdown_manager.register("mexc_client", client.close, async_cleanup=True)
shutdown_manager.register("websocket", ws.disconnect, async_cleanup=True)

# Installer handlers de signaux
shutdown_manager.install_signal_handlers()

# Au shutdown (automatique sur SIGINT/SIGTERM)
# Ou manuel:
await shutdown_manager.shutdown()
```
"""
import asyncio
import signal
import logging
from typing import Dict, Callable, Optional, Any, Coroutine
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Resource:
    """Représente une ressource à nettoyer au shutdown"""
    name: str
    cleanup_func: Callable
    async_cleanup: bool
    priority: int = 0  # Plus élevé = nettoyé en premier


class GracefulShutdown:
    """
    Gestionnaire de shutdown gracieux avec cleanup orchestré des ressources.

    Features:
    - Enregistrement de ressources avec priorités
    - Cleanup async et sync
    - Gestion signaux SIGINT/SIGTERM
    - Timeout de shutdown configurable
    - Logging détaillé du processus
    - Prévention double shutdown

    Exemple:
    ```python
    shutdown = GracefulShutdown(timeout=30.0)

    # Priorité élevée = nettoyé en premier
    shutdown.register("positions", close_positions, async_cleanup=True, priority=100)
    shutdown.register("database", db.close, async_cleanup=False, priority=50)
    shutdown.register("http_session", session.close, async_cleanup=True, priority=10)

    shutdown.install_signal_handlers()

    # Au SIGINT/SIGTERM:
    # 1. close_positions (priority=100)
    # 2. db.close (priority=50)
    # 3. session.close (priority=10)
    ```
    """

    def __init__(self, timeout: float = 30.0):
        """
        Initialiser GracefulShutdown manager

        Args:
            timeout: Timeout global pour shutdown complet (secondes)
        """
        self.timeout = timeout
        self.resources: Dict[str, Resource] = {}
        self.is_shutting_down = False
        self._shutdown_event = asyncio.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def register(
        self,
        name: str,
        cleanup_func: Callable,
        async_cleanup: bool = False,
        priority: int = 0
    ) -> None:
        """
        Enregistrer une ressource à nettoyer au shutdown

        Args:
            name: Nom de la ressource (pour logging)
            cleanup_func: Fonction de cleanup (sync ou async)
            async_cleanup: True si cleanup_func est async
            priority: Priorité (plus élevé = nettoyé en premier)

        Example:
            ```python
            # Ressource sync
            shutdown.register("database", db.close, async_cleanup=False, priority=50)

            # Ressource async
            shutdown.register("client", client.close, async_cleanup=True, priority=100)
            ```
        """
        if name in self.resources:
            logger.warning(f"⚠️ Ressource '{name}' déjà enregistrée, écrasement")

        self.resources[name] = Resource(
            name=name,
            cleanup_func=cleanup_func,
            async_cleanup=async_cleanup,
            priority=priority
        )
        logger.debug(f"✅ Ressource enregistrée: {name} (priority={priority}, async={async_cleanup})")

    def unregister(self, name: str) -> bool:
        """
        Désenregistrer une ressource

        Args:
            name: Nom de la ressource

        Returns:
            True si ressource trouvée et supprimée
        """
        if name in self.resources:
            del self.resources[name]
            logger.debug(f"🗑️ Ressource désenregistrée: {name}")
            return True
        return False

    async def shutdown(self) -> None:
        """
        Effectuer shutdown gracieux de toutes les ressources

        Processus:
        1. Marquer shutdown en cours (prévenir double shutdown)
        2. Trier ressources par priorité (décroissant)
        3. Nettoyer chaque ressource avec timeout individuel
        4. Logger résultats (succès/échecs)
        5. Setter shutdown_event

        Raises:
            Aucune exception propagée (toutes catchées et loggées)
        """
        if self.is_shutting_down:
            logger.warning("⚠️ Shutdown déjà en cours, skip")
            return

        self.is_shutting_down = True
        logger.info(f"🛑 Début shutdown gracieux ({len(self.resources)} ressources)")

        # Trier par priorité (décroissant)
        sorted_resources = sorted(
            self.resources.values(),
            key=lambda r: r.priority,
            reverse=True
        )

        success_count = 0
        failure_count = 0
        timeout_per_resource = self.timeout / max(len(sorted_resources), 1)

        for resource in sorted_resources:
            try:
                logger.info(f"🔧 Cleanup '{resource.name}' (priority={resource.priority})...")

                if resource.async_cleanup:
                    # Async cleanup avec timeout
                    await asyncio.wait_for(
                        resource.cleanup_func(),
                        timeout=timeout_per_resource
                    )
                else:
                    # Sync cleanup dans executor
                    loop = asyncio.get_event_loop()
                    await asyncio.wait_for(
                        loop.run_in_executor(None, resource.cleanup_func),
                        timeout=timeout_per_resource
                    )

                logger.info(f"✅ Cleanup '{resource.name}' réussi")
                success_count += 1

            except asyncio.TimeoutError:
                logger.error(f"⏱️ Timeout cleanup '{resource.name}' ({timeout_per_resource:.1f}s)")
                failure_count += 1
            except Exception as e:
                logger.error(f"❌ Erreur cleanup '{resource.name}': {type(e).__name__}: {e}", exc_info=True)
                failure_count += 1

        # Résumé
        logger.info(f"🏁 Shutdown terminé: {success_count} succès, {failure_count} échecs")
        self._shutdown_event.set()

    def install_signal_handlers(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """
        Installer handlers pour SIGINT et SIGTERM

        Args:
            loop: Event loop (si None, utilise get_event_loop())

        Example:
            ```python
            shutdown = GracefulShutdown()
            shutdown.install_signal_handlers()
            # Maintenant CTRL+C déclenchera shutdown gracieux
            ```

        Note:
            Sur Windows, seul SIGINT est supporté (SIGTERM n'existe pas)
        """
        if loop is None:
            loop = asyncio.get_event_loop()

        self._loop = loop

        def signal_handler(sig):
            """Handler de signal qui déclenche shutdown async"""
            sig_name = signal.Signals(sig).name
            logger.info(f"🚨 Signal reçu: {sig_name}, déclenchement shutdown gracieux...")

            if not self.is_shutting_down:
                # Créer task shutdown dans la loop
                asyncio.create_task(self.shutdown())

        # SIGINT (CTRL+C)
        loop.add_signal_handler(signal.SIGINT, lambda: signal_handler(signal.SIGINT))
        logger.info("✅ Handler SIGINT installé")

        # SIGTERM (kill)
        try:
            loop.add_signal_handler(signal.SIGTERM, lambda: signal_handler(signal.SIGTERM))
            logger.info("✅ Handler SIGTERM installé")
        except (AttributeError, NotImplementedError):
            # SIGTERM non supporté sur Windows
            logger.warning("⚠️ SIGTERM non supporté sur cette plateforme (Windows?)")

    async def wait_for_shutdown(self) -> None:
        """
        Attendre que le shutdown soit complet

        Utilisation dans main():
        ```python
        shutdown = GracefulShutdown()
        shutdown.install_signal_handlers()

        # Application tourne...

        # Attendre signal shutdown
        await shutdown.wait_for_shutdown()
        print("Application arrêtée proprement")
        ```
        """
        await self._shutdown_event.wait()

    @property
    def is_shutdown_complete(self) -> bool:
        """Vérifier si shutdown est complet"""
        return self._shutdown_event.is_set()

    def __repr__(self) -> str:
        """Représentation string pour debug"""
        return (
            f"GracefulShutdown("
            f"resources={len(self.resources)}, "
            f"shutting_down={self.is_shutting_down}, "
            f"timeout={self.timeout}s"
            f")"
        )


_shutdown_manager: Optional[GracefulShutdown] = None


def set_shutdown_manager(manager: Optional[GracefulShutdown]) -> None:
    global _shutdown_manager
    _shutdown_manager = manager


def get_shutdown_manager() -> Optional[GracefulShutdown]:
    return _shutdown_manager

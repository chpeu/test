"""
Multi-Session Manager for Trade Cursor v7.0

Permet de gérer plusieurs instances de bot simultanément.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio
import logging
import random
import re

logger = logging.getLogger(__name__)


@dataclass
class BotSession:
    """Représente une session de bot"""
    session_id: str
    name: str
    pairs: List[str]
    status: str  # 'running', 'stopped', 'paused'
    strategy: str
    config: dict
    created_at: str
    stats: dict = None

    def to_dict(self):
        """Convertir en dictionnaire"""
        data = asdict(self)
        if self.stats is None:
            data['stats'] = {'trades': 0, 'pnl': 0, 'wins': 0, 'losses': 0}
        return data


class SessionManager:
    """Gestionnaire de sessions multiples"""

    def __init__(self):
        self.sessions: Dict[str, BotSession] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        logger.info("SessionManager initialized")

    def _validate_session_id(self, session_id: str) -> bool:
        """Valider le format du session_id"""
        if not session_id or not isinstance(session_id, str):
            return False
        # Accepter alphanumériques, tirets et underscores
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', session_id)) and len(session_id) <= 100

    def _handle_task_done(self, session_id: str, task: asyncio.Task):
        """Callback appelé quand une task se termine (succès ou erreur)"""
        try:
            exception = task.exception()
            if exception and not isinstance(exception, asyncio.CancelledError):
                logger.error(f"Session {session_id} crashed with error: {exception}", exc_info=exception)
                # Mettre à jour le statut de la session
                if session_id in self.sessions:
                    self.sessions[session_id].status = 'stopped'
        except asyncio.CancelledError:
            logger.info(f"Session {session_id} was cancelled")
        except Exception as e:
            logger.error(f"Error in task done callback: {e}", exc_info=True)
        finally:
            # Nettoyer la tâche de la liste
            if session_id in self.running_tasks:
                del self.running_tasks[session_id]

    def create_session(
        self,
        session_id: str,
        name: str,
        pairs: List[str],
        strategy: str = 'scalping',
        config: dict = None
    ) -> BotSession:
        """Créer une nouvelle session"""

        # Validation des entrées
        if not self._validate_session_id(session_id):
            raise ValueError(f"Invalid session_id format: {session_id}")

        if not name or not isinstance(name, str) or len(name) > 200:
            raise ValueError(f"Invalid name: must be non-empty string, max 200 chars")

        if not pairs or not isinstance(pairs, list):
            raise ValueError(f"Invalid pairs: must be non-empty list")

        if session_id in self.sessions:
            raise ValueError(f"Session {session_id} already exists")

        session = BotSession(
            session_id=session_id,
            name=name,
            pairs=pairs,
            status='stopped',
            strategy=strategy,
            config=config or {},
            created_at=datetime.now().isoformat(),
            stats={'trades': 0, 'pnl': 0.0, 'wins': 0, 'losses': 0}
        )

        self.sessions[session_id] = session
        logger.info(f"Created session: {session_id} ({name})")
        return session

    async def start_session(self, session_id: str):
        """Démarrer une session"""

        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        if session_id in self.running_tasks:
            raise ValueError(f"Session {session_id} already running")

        session = self.sessions[session_id]

        # Créer une task asyncio pour cette session avec callback d'erreur
        task = asyncio.create_task(self._run_session(session))
        task.add_done_callback(lambda t: self._handle_task_done(session_id, t))
        self.running_tasks[session_id] = task
        session.status = 'running'

        logger.info(f"Started session: {session_id}")

    async def stop_session(self, session_id: str):
        """Arrêter une session"""

        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        if session_id in self.running_tasks:
            task = self.running_tasks[session_id]
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Session {session_id} cancelled")

            del self.running_tasks[session_id]

        self.sessions[session_id].status = 'stopped'
        logger.info(f"Stopped session: {session_id}")

    async def pause_session(self, session_id: str):
        """Mettre en pause une session"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        self.sessions[session_id].status = 'paused'
        logger.info(f"Paused session: {session_id}")

    async def resume_session(self, session_id: str):
        """Reprendre une session en pause"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        self.sessions[session_id].status = 'running'
        logger.info(f"Resumed session: {session_id}")

    def delete_session(self, session_id: str):
        """Supprimer une session"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        # Vérifier que la session est arrêtée
        if self.sessions[session_id].status == 'running':
            raise ValueError(f"Cannot delete running session {session_id}")

        del self.sessions[session_id]
        logger.info(f"Deleted session: {session_id}")

    async def _run_session(self, session: BotSession):
        """Boucle principale d'une session (simulation pour démo)"""
        logger.info(f"Running session {session.session_id} with pairs: {session.pairs}")

        try:
            while True:
                # Simulation de trading
                await asyncio.sleep(10)

                # Simuler un trade (à remplacer par vraie logique)
                if session.status == 'running':
                    session.stats['trades'] += 1
                    # PnL aléatoire entre -10 et +20
                    pnl = random.uniform(-10, 20)
                    session.stats['pnl'] += pnl

                    if pnl > 0:
                        session.stats['wins'] += 1
                    else:
                        session.stats['losses'] += 1

                    logger.debug(f"Session {session.session_id} - Trade #{session.stats['trades']}: {pnl:.2f} USDT")

        except asyncio.CancelledError:
            logger.info(f"Session {session.session_id} cancelled")
            raise

    def get_all_sessions(self) -> List[dict]:
        """Retourner toutes les sessions"""
        return [session.to_dict() for session in self.sessions.values()]

    def get_session(self, session_id: str) -> Optional[dict]:
        """Retourner une session spécifique"""
        session = self.sessions.get(session_id)
        return session.to_dict() if session else None

    def get_global_stats(self) -> dict:
        """Statistiques agrégées de toutes les sessions"""

        total_trades = sum(s.stats.get('trades', 0) for s in self.sessions.values())
        total_pnl = sum(s.stats.get('pnl', 0.0) for s in self.sessions.values())
        total_wins = sum(s.stats.get('wins', 0) for s in self.sessions.values())
        total_losses = sum(s.stats.get('losses', 0) for s in self.sessions.values())

        running_sessions = sum(
            1 for s in self.sessions.values() if s.status == 'running'
        )

        return {
            'total_sessions': len(self.sessions),
            'running_sessions': running_sessions,
            'stopped_sessions': sum(1 for s in self.sessions.values() if s.status == 'stopped'),
            'paused_sessions': sum(1 for s in self.sessions.values() if s.status == 'paused'),
            'total_trades': total_trades,
            'total_pnl': round(total_pnl, 2),
            'total_wins': total_wins,
            'total_losses': total_losses,
            'win_rate': round((total_wins / total_trades * 100) if total_trades > 0 else 0, 1)
        }

    async def stop_all_sessions(self):
        """Arrêter toutes les sessions"""
        session_ids = list(self.running_tasks.keys())
        for session_id in session_ids:
            await self.stop_session(session_id)

        logger.info("All sessions stopped")


# Instance globale
session_manager = SessionManager()

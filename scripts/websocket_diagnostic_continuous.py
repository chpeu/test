#!/usr/bin/env python3
"""
🔬 DIAGNOSTIC WEBSOCKET CONTINU - Solution Définitive
Surveillance en temps réel des connexions WebSocket pour identifier les déconnexions
"""

import asyncio
import websockets
import json
import time
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional
import threading
import traceback
from dataclasses import dataclass, field

# Configuration logging très détaillé
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/websocket_diagnostic.log', 'a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ConnectionHealth:
    """État de santé d'une connexion WebSocket"""
    client_id: str
    connection_start: float = field(default_factory=time.time)
    last_ping_sent: Optional[float] = None
    last_pong_received: Optional[float] = None
    ping_count: int = 0
    pong_count: int = 0
    total_messages: int = 0
    rtt_values: List[float] = field(default_factory=list)
    disconnection_count: int = 0
    last_disconnect_reason: Optional[str] = None
    health_issues: List[str] = field(default_factory=list)
    
    @property
    def avg_rtt_ms(self) -> Optional[float]:
        return sum(self.rtt_values) / len(self.rtt_values) * 1000 if self.rtt_values else None
    
    @property
    def time_since_last_pong(self) -> Optional[float]:
        return time.time() - self.last_pong_received if self.last_pong_received else None
    
    @property
    def health_status(self) -> str:
        time_since_pong = self.time_since_last_pong
        if time_since_pong is None:
            return "🔶 NO_PONG_YET"
        elif time_since_pong > 90:
            return "🔴 CRITICAL_TIMEOUT"
        elif time_since_pong > 60:
            return "🟠 WARNING_TIMEOUT"
        elif time_since_pong > 30:
            return "🟡 SLOW_RESPONSE"
        else:
            return "🟢 HEALTHY"


class WebSocketDiagnostic:
    """Diagnostic avancé des connexions WebSocket"""
    
    def __init__(self, ws_url: str = "ws://localhost:3000/ws"):
        self.ws_url = ws_url
        self.connections: Dict[str, ConnectionHealth] = {}
        self.running = True
        self.diagnostic_start = time.time()
        self.total_reconnections = 0
        
    async def create_monitored_connection(self, client_id: str) -> None:
        """Créer et surveiller une connexion WebSocket"""
        connection_health = ConnectionHealth(client_id=client_id)
        self.connections[client_id] = connection_health
        
        reconnect_attempts = 0
        
        while self.running and reconnect_attempts < 10:
            try:
                logger.info(f"🔗 [CONNECT] Client {client_id} - Tentative connexion #{reconnect_attempts + 1}")
                
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=None,  # Désactiver ping auto pour contrôler manuellement
                    ping_timeout=None,
                    close_timeout=10,
                    max_size=10**6
                ) as websocket:
                    
                    connection_health.connection_start = time.time()
                    logger.info(f"✅ [CONNECTED] Client {client_id} connecté avec succès")
                    
                    # Envoyer client_hello
                    hello_msg = {
                        'type': 'client_hello',
                        'client_id': client_id,
                        'context': {
                            'userAgent': f'WebSocketDiagnostic/{client_id}',
                            'diagnostic': True,
                            'timestamp': time.time()
                        }
                    }
                    await websocket.send(json.dumps(hello_msg))
                    connection_health.total_messages += 1
                    
                    # Lancer les tâches de monitoring
                    ping_task = asyncio.create_task(
                        self.ping_loop(websocket, connection_health)
                    )
                    receive_task = asyncio.create_task(
                        self.receive_loop(websocket, connection_health)
                    )
                    monitor_task = asyncio.create_task(
                        self.monitor_health(connection_health)
                    )
                    
                    # Attendre qu'une tâche se termine (généralement par déconnexion)
                    done, pending = await asyncio.wait(
                        [ping_task, receive_task, monitor_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Annuler les tâches restantes
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    
                    # Analyser la raison de déconnexion
                    for task in done:
                        if task.exception():
                            connection_health.last_disconnect_reason = str(task.exception())
                            break
                    
                    connection_health.disconnection_count += 1
                    self.total_reconnections += 1
                    
                    logger.error(
                        f"💔 [DISCONNECT] Client {client_id} déconnecté: "
                        f"raison={connection_health.last_disconnect_reason or 'unknown'}, "
                        f"uptime={time.time() - connection_health.connection_start:.1f}s, "
                        f"pings={connection_health.ping_count}, "
                        f"pongs={connection_health.pong_count}"
                    )
                    
                    reconnect_attempts += 1
                    if reconnect_attempts < 10:
                        await asyncio.sleep(5)  # Attendre 5s avant reconnexion
                        
            except Exception as e:
                connection_health.last_disconnect_reason = f"Connection error: {str(e)}"
                connection_health.disconnection_count += 1
                logger.error(
                    f"❌ [CONNECTION-ERROR] Client {client_id}: {e}",
                    exc_info=True
                )
                reconnect_attempts += 1
                if reconnect_attempts < 10:
                    await asyncio.sleep(5)
    
    async def ping_loop(self, websocket, connection_health: ConnectionHealth):
        """Boucle d'envoi de pings avec diagnostic"""
        while self.running:
            try:
                await asyncio.sleep(25)  # Ping toutes les 25 secondes
                
                ping_msg = {
                    'type': 'ping',
                    'timestamp': time.time(),
                    'client_ping_id': connection_health.ping_count + 1,
                    'diagnostic': True
                }
                
                connection_health.last_ping_sent = time.time()
                connection_health.ping_count += 1
                
                await websocket.send(json.dumps(ping_msg))
                connection_health.total_messages += 1
                
                logger.info(
                    f"📤 [PING-SENT] Client {connection_health.client_id} ping #{connection_health.ping_count} "
                    f"(pong_delay={connection_health.time_since_last_pong:.1f}s)" 
                    if connection_health.time_since_last_pong else
                    f"📤 [PING-SENT] Client {connection_health.client_id} ping #{connection_health.ping_count} (first_ping)"
                )
                
                # Vérifier si on attend un pong depuis trop longtemps
                if connection_health.time_since_last_pong and connection_health.time_since_last_pong > 75:
                    connection_health.health_issues.append(
                        f"TIMEOUT: No pong for {connection_health.time_since_last_pong:.1f}s"
                    )
                    logger.error(
                        f"🚨 [PING-TIMEOUT-CRITICAL] Client {connection_health.client_id} "
                        f"pas de pong depuis {connection_health.time_since_last_pong:.1f}s - CONNEXION MOURANTE"
                    )
                
            except Exception as e:
                logger.error(f"❌ [PING-ERROR] Client {connection_health.client_id}: {e}")
                break
    
    async def receive_loop(self, websocket, connection_health: ConnectionHealth):
        """Boucle de réception avec diagnostic"""
        while self.running:
            try:
                # Timeout plus long pour les messages
                message_data = await asyncio.wait_for(websocket.recv(), timeout=90.0)
                message = json.loads(message_data)
                connection_health.total_messages += 1
                
                msg_type = message.get('type')
                
                if msg_type == 'ping':
                    # Répondre immédiatement au ping du serveur
                    pong_msg = {
                        'type': 'pong',
                        'timestamp': time.time(),
                        'ping_id': message.get('ping_id'),
                        'client_id': connection_health.client_id
                    }
                    await websocket.send(json.dumps(pong_msg))
                    connection_health.total_messages += 1
                    
                    logger.info(
                        f"📥➡️📤 [PING-PONG] Client {connection_health.client_id} "
                        f"ping#{message.get('ping_id')} reçu et pong envoyé"
                    )
                
                elif msg_type == 'pong':
                    # Pong du serveur en réponse à notre ping
                    connection_health.last_pong_received = time.time()
                    connection_health.pong_count += 1
                    
                    if connection_health.last_ping_sent:
                        rtt = connection_health.last_pong_received - connection_health.last_ping_sent
                        connection_health.rtt_values.append(rtt)
                        if len(connection_health.rtt_values) > 20:  # Garder seulement les 20 dernières valeurs
                            connection_health.rtt_values.pop(0)
                        
                        logger.info(
                            f"📥 [PONG-RECEIVED] Client {connection_health.client_id} "
                            f"pong#{message.get('ping_id', 'unknown')} RTT={rtt*1000:.1f}ms "
                            f"avg_rtt={connection_health.avg_rtt_ms:.1f}ms"
                        )
                    else:
                        logger.warning(
                            f"📥 [PONG-ORPHAN] Client {connection_health.client_id} "
                            f"pong reçu sans ping correspondant"
                        )
                
                else:
                    logger.debug(f"📥 [MSG] Client {connection_health.client_id} type={msg_type}")
                
            except asyncio.TimeoutError:
                connection_health.health_issues.append("RECV_TIMEOUT: No message for 90s")
                logger.error(
                    f"⏰ [RECEIVE-TIMEOUT] Client {connection_health.client_id} "
                    f"aucun message reçu depuis 90s"
                )
                break
            except Exception as e:
                logger.error(f"❌ [RECEIVE-ERROR] Client {connection_health.client_id}: {e}")
                break
    
    async def monitor_health(self, connection_health: ConnectionHealth):
        """Surveillance de la santé de connexion"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Vérification toutes les 30s
                
                status = connection_health.health_status
                time_since_pong = connection_health.time_since_last_pong
                
                logger.info(
                    f"💓 [HEALTH-CHECK] Client {connection_health.client_id}: "
                    f"status={status}, "
                    f"pong_delay={time_since_pong:.1f}s, " if time_since_pong else "pong_delay=none, "
                    f"pings={connection_health.ping_count}, "
                    f"pongs={connection_health.pong_count}, "
                    f"avg_rtt={connection_health.avg_rtt_ms:.1f}ms" if connection_health.avg_rtt_ms else "avg_rtt=none"
                )
                
                # Alerte critique si problème détecté
                if status.startswith("🔴") or status.startswith("🟠"):
                    logger.error(
                        f"🚨 [HEALTH-ALERT] Client {connection_health.client_id} "
                        f"en état critique: {status} - POSSIBLE DÉCONNEXION IMMINENTE"
                    )
                
            except Exception as e:
                logger.error(f"❌ [MONITOR-ERROR] Client {connection_health.client_id}: {e}")
                break
    
    async def run_diagnostic(self, num_clients: int = 2, duration_minutes: int = 10):
        """Lancer le diagnostic complet"""
        logger.info(
            f"🚀 [DIAGNOSTIC-START] Lancement surveillance WebSocket: "
            f"{num_clients} clients, durée={duration_minutes}min"
        )
        
        # Créer les connexions de surveillance
        tasks = []
        for i in range(num_clients):
            client_id = f"diagnostic_client_{i+1}"
            task = asyncio.create_task(self.create_monitored_connection(client_id))
            tasks.append(task)
        
        # Tâche de rapport périodique
        report_task = asyncio.create_task(self.periodic_report())
        tasks.append(report_task)
        
        try:
            # Attendre la durée spécifiée ou interruption
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=duration_minutes * 60
            )
        except asyncio.TimeoutError:
            logger.info(f"⏰ [DIAGNOSTIC-TIMEOUT] Fin de surveillance après {duration_minutes} minutes")
        except KeyboardInterrupt:
            logger.info("⌨️ [DIAGNOSTIC-INTERRUPTED] Interruption utilisateur")
        finally:
            self.running = False
            
            # Annuler toutes les tâches
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
        
        # Rapport final
        self.generate_final_report()
    
    async def periodic_report(self):
        """Rapport périodique détaillé"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Rapport toutes les minutes
                
                total_uptime = time.time() - self.diagnostic_start
                active_connections = len([c for c in self.connections.values() 
                                        if c.health_status.startswith("🟢") or c.health_status.startswith("🟡")])
                
                logger.info("=" * 80)
                logger.info(f"📊 [RAPPORT-PERIODIC] Uptime diagnostic: {total_uptime/60:.1f} min")
                logger.info(f"🔗 Connexions actives: {active_connections}/{len(self.connections)}")
                logger.info(f"🔄 Reconnexions totales: {self.total_reconnections}")
                
                for client_id, health in self.connections.items():
                    logger.info(
                        f"   {health.health_status} {client_id}: "
                        f"pings={health.ping_count}, pongs={health.pong_count}, "
                        f"disconnects={health.disconnection_count}, "
                        f"avg_rtt={health.avg_rtt_ms:.1f}ms" if health.avg_rtt_ms else "avg_rtt=none"
                    )
                
                logger.info("=" * 80)
                
            except Exception as e:
                logger.error(f"❌ [REPORT-ERROR]: {e}")
    
    def generate_final_report(self):
        """Générer le rapport final de diagnostic"""
        total_duration = time.time() - self.diagnostic_start
        
        logger.info("🎯" * 30)
        logger.info("🔬 RAPPORT FINAL DE DIAGNOSTIC WEBSOCKET")
        logger.info("🎯" * 30)
        logger.info(f"⏱️  Durée totale: {total_duration/60:.2f} minutes")
        logger.info(f"🔗 Clients surveillés: {len(self.connections)}")
        logger.info(f"🔄 Reconnexions totales: {self.total_reconnections}")
        
        for client_id, health in self.connections.items():
            logger.info(f"\n📋 CLIENT: {client_id}")
            logger.info(f"   Status final: {health.health_status}")
            logger.info(f"   Pings envoyés: {health.ping_count}")
            logger.info(f"   Pongs reçus: {health.pong_count}")
            logger.info(f"   Déconnexions: {health.disconnection_count}")
            logger.info(f"   RTT moyen: {health.avg_rtt_ms:.1f}ms" if health.avg_rtt_ms else "   RTT moyen: N/A")
            logger.info(f"   Dernière déconnexion: {health.last_disconnect_reason or 'N/A'}")
            
            if health.health_issues:
                logger.info(f"   🚨 Problèmes détectés:")
                for issue in health.health_issues[-5:]:  # Derniers 5 problèmes
                    logger.info(f"      - {issue}")
        
        logger.info("🎯" * 30)


def signal_handler(sig, frame):
    """Gestionnaire de signal pour arrêt propre"""
    logger.info("🛑 [SHUTDOWN] Signal d'arrêt reçu, fermeture en cours...")
    sys.exit(0)


async def main():
    """Point d'entrée principal"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    diagnostic = WebSocketDiagnostic()
    
    try:
        await diagnostic.run_diagnostic(
            num_clients=2,      # 2 clients simultanés  
            duration_minutes=10  # 10 minutes de surveillance
        )
    except Exception as e:
        logger.error(f"❌ [MAIN-ERROR] Erreur critique: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info("🔬 Démarrage du diagnostic WebSocket continu...")
    asyncio.run(main())

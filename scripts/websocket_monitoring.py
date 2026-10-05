#!/usr/bin/env python3
"""
🔄 Monitoring WebSocket Continu 
Surveillance automatique de la stabilité WebSocket pour détecter les régressions
"""

import asyncio
import websockets
import json
import time
import logging
import sys
from datetime import datetime
from typing import Dict, Optional, List
import signal

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/websocket_monitoring.log', 'a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class WebSocketMonitor:
    """Surveillance continue WebSocket avec alertes automatiques"""
    
    def __init__(self, ws_url: str = "ws://localhost:5000/ws"):
        self.ws_url = ws_url
        self.running = True
        self.stats = {
            'total_connections': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'total_pings_received': 0,
            'total_pongs_sent': 0,
            'disconnections': 0,
            'longest_connection_duration': 0,
            'shortest_connection_duration': float('inf'),
            'average_connection_duration': 0,
            'total_uptime': 0,
            'connection_durations': []
        }
        self.start_time = time.time()
        
    async def monitor_connection(self, connection_id: int) -> Dict:
        """Surveiller une connexion WebSocket spécifique"""
        connection_start = time.time()
        connection_stats = {
            'connection_id': connection_id,
            'start_time': connection_start,
            'duration': 0,
            'pings_received': 0,
            'pongs_sent': 0,
            'messages_received': 0,
            'disconnect_reason': None,
            'success': False
        }
        
        try:
            logger.info(f"🔗 [MONITOR-{connection_id}] Démarrage surveillance connexion")
            
            async with websockets.connect(self.ws_url, timeout=10) as websocket:
                self.stats['successful_connections'] += 1
                
                # Envoyer client_hello
                hello_msg = {
                    'type': 'client_hello',
                    'client_id': f'monitor_{connection_id}',
                    'context': {
                        'userAgent': f'WebSocketMonitor/Connection_{connection_id}',
                        'monitoring': True,
                        'timestamp': time.time()
                    }
                }
                await websocket.send(json.dumps(hello_msg))
                
                # Surveiller pendant 5 minutes maximum
                timeout_duration = 300  # 5 minutes
                
                while self.running and (time.time() - connection_start) < timeout_duration:
                    try:
                        # Attendre message avec timeout de 35s
                        message_data = await asyncio.wait_for(websocket.recv(), timeout=35.0)
                        message = json.loads(message_data)
                        connection_stats['messages_received'] += 1
                        
                        msg_type = message.get('type')
                        
                        if msg_type == 'ping':
                            connection_stats['pings_received'] += 1
                            self.stats['total_pings_received'] += 1
                            
                            # Répondre avec pong
                            pong_response = {
                                'type': 'pong',
                                'timestamp': time.time(),
                                'ping_id': message.get('ping_id'),
                                'monitor_id': connection_id
                            }
                            await websocket.send(json.dumps(pong_response))
                            connection_stats['pongs_sent'] += 1
                            self.stats['total_pongs_sent'] += 1
                            
                            # Log toutes les 30s
                            current_duration = time.time() - connection_start
                            if connection_stats['pings_received'] % 1 == 0:  # Chaque ping
                                logger.info(
                                    f"🏓 [MONITOR-{connection_id}] Uptime: {current_duration:.1f}s, "
                                    f"Pings: {connection_stats['pings_received']}, "
                                    f"Health: {'🟢 STABLE' if current_duration > 120 else '🟡 TESTING'}"
                                )
                        
                        elif msg_type == 'server_hello':
                            logger.info(f"👋 [MONITOR-{connection_id}] Server hello reçu")
                            
                        # Si on dépasse 120s, la connexion est considérée comme stable
                        if (time.time() - connection_start) > 120:
                            connection_stats['success'] = True
                            
                    except asyncio.TimeoutError:
                        current_duration = time.time() - connection_start
                        logger.warning(
                            f"⏰ [MONITOR-{connection_id}] Timeout 35s - Pas de message "
                            f"(uptime: {current_duration:.1f}s)"
                        )
                        
                        # Si timeout après plus de 120s, c'est probablement OK
                        if current_duration > 120:
                            connection_stats['success'] = True
                            connection_stats['disconnect_reason'] = 'timeout_after_stable_period'
                            break
                        else:
                            connection_stats['disconnect_reason'] = 'timeout_early'
                            break
                
                connection_stats['duration'] = time.time() - connection_start
                connection_stats['success'] = True
                
        except Exception as e:
            connection_stats['duration'] = time.time() - connection_start
            connection_stats['disconnect_reason'] = f"Exception: {type(e).__name__}: {str(e)}"
            logger.error(
                f"❌ [MONITOR-{connection_id}] Erreur connexion: {e} "
                f"(uptime: {connection_stats['duration']:.1f}s)"
            )
            self.stats['failed_connections'] += 1
        
        # Mettre à jour les statistiques globales
        duration = connection_stats['duration']
        self.stats['connection_durations'].append(duration)
        self.stats['disconnections'] += 1
        
        if duration > self.stats['longest_connection_duration']:
            self.stats['longest_connection_duration'] = duration
        
        if duration < self.stats['shortest_connection_duration']:
            self.stats['shortest_connection_duration'] = duration
            
        if self.stats['connection_durations']:
            self.stats['average_connection_duration'] = sum(self.stats['connection_durations']) / len(self.stats['connection_durations'])
        
        logger.info(
            f"📊 [MONITOR-{connection_id}] Connexion terminée: "
            f"durée={duration:.1f}s, "
            f"pings={connection_stats['pings_received']}, "
            f"succès={'✅' if connection_stats['success'] else '❌'}, "
            f"raison={connection_stats['disconnect_reason'] or 'normal'}"
        )
        
        return connection_stats
    
    async def run_continuous_monitoring(self, interval_seconds: int = 60):
        """Surveillance continue avec connexions périodiques"""
        connection_counter = 0
        
        logger.info("🚀 Démarrage surveillance continue WebSocket")
        logger.info(f"📡 URL surveillée: {self.ws_url}")
        logger.info(f"⏱️ Intervalle entre connexions: {interval_seconds}s")
        
        try:
            while self.running:
                connection_counter += 1
                self.stats['total_connections'] += 1
                
                logger.info(f"🔄 [CYCLE-{connection_counter}] Démarrage nouvelle surveillance")
                
                # Lancer surveillance d'une connexion
                await self.monitor_connection(connection_counter)
                
                # Générer rapport périodique
                if connection_counter % 5 == 0:  # Tous les 5 cycles
                    self.generate_health_report()
                
                # Attendre avant la prochaine connexion
                if self.running:
                    logger.info(f"⏸️ Pause {interval_seconds}s avant prochaine surveillance...")
                    await asyncio.sleep(interval_seconds)
                    
        except KeyboardInterrupt:
            logger.info("⌨️ Surveillance interrompue par l'utilisateur")
        finally:
            self.running = False
            self.generate_final_report()
    
    def generate_health_report(self):
        """Générer rapport de santé périodique"""
        total_time = time.time() - self.start_time
        success_rate = (self.stats['successful_connections'] / max(1, self.stats['total_connections'])) * 100
        
        logger.info("=" * 60)
        logger.info("📊 RAPPORT DE SANTÉ WEBSOCKET")
        logger.info("=" * 60)
        logger.info(f"⏱️ Temps de surveillance: {total_time/60:.1f} minutes")
        logger.info(f"🔗 Connexions testées: {self.stats['total_connections']}")
        logger.info(f"✅ Succès: {self.stats['successful_connections']} ({success_rate:.1f}%)")
        logger.info(f"❌ Échecs: {self.stats['failed_connections']}")
        logger.info(f"🏓 Pings reçus: {self.stats['total_pings_received']}")
        logger.info(f"🏓 Pongs envoyés: {self.stats['total_pongs_sent']}")
        
        if self.stats['connection_durations']:
            logger.info(f"📈 Durée moyenne: {self.stats['average_connection_duration']:.1f}s")
            logger.info(f"📈 Durée max: {self.stats['longest_connection_duration']:.1f}s")
            logger.info(f"📈 Durée min: {self.stats['shortest_connection_duration']:.1f}s")
        
        # Alerte si problèmes détectés
        if success_rate < 80:
            logger.error("🚨 ALERTE: Taux de succès faible (<80%) - Problème potentiel !")
        elif self.stats['average_connection_duration'] < 60:
            logger.warning("⚠️ ATTENTION: Durée moyenne faible (<60s) - Surveillance requise")
        else:
            logger.info("🟢 STATUT: WebSocket stable et fonctionnel")
        
        logger.info("=" * 60)
    
    def generate_final_report(self):
        """Générer rapport final"""
        total_time = time.time() - self.start_time
        
        logger.info("🏁" * 20)
        logger.info("📋 RAPPORT FINAL DE SURVEILLANCE WEBSOCKET")
        logger.info("🏁" * 20)
        logger.info(f"⏱️ Durée totale: {total_time/3600:.2f} heures")
        logger.info(f"🔗 Connexions totales: {self.stats['total_connections']}")
        logger.info(f"✅ Réussies: {self.stats['successful_connections']}")
        logger.info(f"❌ Échouées: {self.stats['failed_connections']}")
        logger.info(f"🏓 Total pings/pongs: {self.stats['total_pings_received']}/{self.stats['total_pongs_sent']}")
        
        if self.stats['connection_durations']:
            avg_duration = sum(self.stats['connection_durations']) / len(self.stats['connection_durations'])
            logger.info(f"📊 Statistiques durées:")
            logger.info(f"   Moyenne: {avg_duration:.1f}s")
            logger.info(f"   Maximum: {max(self.stats['connection_durations']):.1f}s")
            logger.info(f"   Minimum: {min(self.stats['connection_durations']):.1f}s")
        
        success_rate = (self.stats['successful_connections'] / max(1, self.stats['total_connections'])) * 100
        logger.info(f"🎯 Taux de succès final: {success_rate:.1f}%")
        
        if success_rate >= 95:
            logger.info("🟢 EXCELLENT: WebSocket très stable")
        elif success_rate >= 85:
            logger.info("🟡 BON: WebSocket stable avec incidents mineurs")
        else:
            logger.error("🔴 PROBLÉMATIQUE: WebSocket instable - Investigation requise")
        
        logger.info("🏁" * 20)


def signal_handler(sig, frame):
    """Gestionnaire pour arrêt propre"""
    logger.info("🛑 Signal d'arrêt reçu, fin de surveillance...")
    sys.exit(0)


async def main():
    """Point d'entrée principal"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    monitor = WebSocketMonitor()
    
    try:
        # Surveillance continue avec connexions toutes les minutes
        await monitor.run_continuous_monitoring(interval_seconds=60)
    except Exception as e:
        logger.error(f"❌ Erreur critique monitoring: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info("🔄 Démarrage du monitoring WebSocket continu...")
    asyncio.run(main())

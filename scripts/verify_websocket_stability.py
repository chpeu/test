"""
🔧 Script de Vérification Stabilité WebSocket
Teste la robustesse des connexions WebSocket et diagnostique les déconnexions
"""

import asyncio
import websockets
import json
import time
import logging
from datetime import datetime
from typing import Dict, List
import statistics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebSocketStabilityTester:
    """Testeur de stabilité WebSocket"""
    
    def __init__(self, ws_url: str = "ws://localhost:3000/ws", test_duration_minutes: int = 10):
        self.ws_url = ws_url
        self.test_duration = test_duration_minutes * 60  # Convertir en secondes
        self.connections: List[Dict] = []
        self.ping_stats = []
        self.disconnection_events = []
        self.start_time = None
        
    async def test_single_connection(self, connection_id: int, duration_seconds: int = 300):
        """Tester une connexion WebSocket unique"""
        connection_info = {
            'id': connection_id,
            'start_time': time.time(),
            'end_time': None,
            'messages_sent': 0,
            'messages_received': 0,
            'pings_sent': 0,
            'pongs_received': 0,
            'ping_rtts': [],
            'disconnections': 0,
            'last_activity': time.time(),
            'status': 'connecting'
        }
        
        try:
            logger.info(f"🔌 [Connexion {connection_id}] Connexion à {self.ws_url}")
            
            async with websockets.connect(
                self.ws_url,
                ping_interval=None,  # On gère nos propres pings
                ping_timeout=None,
                close_timeout=10
            ) as websocket:
                connection_info['status'] = 'connected'
                logger.info(f"✅ [Connexion {connection_id}] Connectée avec succès")
                
                # Envoyer client_hello
                hello_msg = {
                    'type': 'client_hello',
                    'client_id': f'stability_tester_{connection_id}',
                    'context': {
                        'userAgent': 'WebSocket Stability Tester',
                        'origin': 'stability_test'
                    }
                }
                await websocket.send(json.dumps(hello_msg))
                connection_info['messages_sent'] += 1
                
                end_time = connection_info['start_time'] + duration_seconds
                last_ping_time = time.time()
                
                while time.time() < end_time:
                    try:
                        # Envoyer un ping toutes les 30 secondes
                        if time.time() - last_ping_time >= 30:
                            ping_msg = {
                                'type': 'ping',
                                'timestamp': time.time(),
                                'ping_id': connection_info['pings_sent'] + 1
                            }
                            await websocket.send(json.dumps(ping_msg))
                            connection_info['messages_sent'] += 1
                            connection_info['pings_sent'] += 1
                            last_ping_time = time.time()
                            logger.debug(f"📡 [Connexion {connection_id}] Ping #{connection_info['pings_sent']} envoyé")
                        
                        # Écouter les messages avec timeout
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                            data = json.loads(message)
                            connection_info['messages_received'] += 1
                            connection_info['last_activity'] = time.time()
                            
                            msg_type = data.get('type')
                            if msg_type == 'pong':
                                connection_info['pongs_received'] += 1
                                ping_id = data.get('ping_id')
                                client_ts = data.get('client_ts')
                                if client_ts:
                                    rtt_ms = (time.time() - client_ts) * 1000
                                    connection_info['ping_rtts'].append(rtt_ms)
                                    logger.debug(f"🏓 [Connexion {connection_id}] Pong reçu (RTT: {rtt_ms:.1f}ms)")
                            elif msg_type == 'ping':
                                # Répondre au ping du serveur
                                pong_msg = {
                                    'type': 'pong',
                                    'timestamp': time.time(),
                                    'ping_id': data.get('ping_id')
                                }
                                await websocket.send(json.dumps(pong_msg))
                                connection_info['messages_sent'] += 1
                                logger.debug(f"🏓 [Connexion {connection_id}] Réponse pong envoyée")
                                
                        except asyncio.TimeoutError:
                            # Pas de message reçu - normal
                            continue
                        except json.JSONDecodeError:
                            logger.warning(f"⚠️ [Connexion {connection_id}] Message JSON invalide reçu")
                            continue
                            
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.error(f"❌ [Connexion {connection_id}] Connexion fermée: {e}")
                        connection_info['disconnections'] += 1
                        self.disconnection_events.append({
                            'connection_id': connection_id,
                            'time': time.time(),
                            'reason': str(e),
                            'duration_before_disconnect': time.time() - connection_info['start_time']
                        })
                        break
                    except Exception as e:
                        logger.error(f"❌ [Connexion {connection_id}] Erreur inattendue: {e}")
                        break
                
                connection_info['status'] = 'completed'
                
        except websockets.exceptions.InvalidURI:
            logger.error(f"❌ [Connexion {connection_id}] URL WebSocket invalide: {self.ws_url}")
            connection_info['status'] = 'failed_invalid_uri'
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"❌ [Connexion {connection_id}] Impossible de se connecter: {e}")
            connection_info['status'] = 'failed_connection_closed'
        except Exception as e:
            logger.error(f"❌ [Connexion {connection_id}] Erreur de connexion: {e}")
            connection_info['status'] = 'failed_other'
            
        connection_info['end_time'] = time.time()
        return connection_info
    
    async def run_stability_test(self, concurrent_connections: int = 3):
        """Exécuter le test de stabilité avec plusieurs connexions"""
        logger.info(f"🚀 Démarrage test de stabilité WebSocket")
        logger.info(f"📊 Paramètres: {concurrent_connections} connexions simultanées, durée: {self.test_duration}s")
        
        self.start_time = time.time()
        
        # Lancer plusieurs connexions en parallèle
        tasks = []
        for i in range(concurrent_connections):
            task = asyncio.create_task(
                self.test_single_connection(i + 1, self.test_duration)
            )
            tasks.append(task)
        
        # Attendre que toutes les connexions se terminent
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Traiter les résultats
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Connexion {i + 1} a échoué avec exception: {result}")
                self.connections.append({
                    'id': i + 1,
                    'status': 'failed_exception',
                    'error': str(result)
                })
            else:
                self.connections.append(result)
        
        # Générer rapport
        self.generate_report()
    
    def generate_report(self):
        """Générer un rapport de stabilité détaillé"""
        end_time = time.time()
        total_duration = end_time - self.start_time
        
        logger.info("📋 RAPPORT DE STABILITÉ WEBSOCKET")
        logger.info("=" * 50)
        logger.info(f"⏱️  Durée totale du test: {total_duration:.1f}s")
        logger.info(f"🔌 Connexions testées: {len(self.connections)}")
        
        # Statistiques de connexions
        successful_connections = [c for c in self.connections if c.get('status') == 'completed']
        failed_connections = [c for c in self.connections if c.get('status', '').startswith('failed')]
        
        logger.info(f"✅ Connexions réussies: {len(successful_connections)}")
        logger.info(f"❌ Connexions échouées: {len(failed_connections)}")
        
        if successful_connections:
            # Statistiques de ping/pong
            total_pings = sum(c.get('pings_sent', 0) for c in successful_connections)
            total_pongs = sum(c.get('pongs_received', 0) for c in successful_connections)
            pong_success_rate = (total_pongs / total_pings * 100) if total_pings > 0 else 0
            
            logger.info(f"📡 Pings envoyés: {total_pings}")
            logger.info(f"🏓 Pongs reçus: {total_pongs}")
            logger.info(f"📊 Taux de succès ping/pong: {pong_success_rate:.1f}%")
            
            # Statistiques RTT
            all_rtts = []
            for c in successful_connections:
                all_rtts.extend(c.get('ping_rtts', []))
            
            if all_rtts:
                avg_rtt = statistics.mean(all_rtts)
                median_rtt = statistics.median(all_rtts)
                max_rtt = max(all_rtts)
                min_rtt = min(all_rtts)
                
                logger.info(f"📈 RTT moyen: {avg_rtt:.1f}ms")
                logger.info(f"📊 RTT médian: {median_rtt:.1f}ms")
                logger.info(f"📈 RTT max: {max_rtt:.1f}ms")
                logger.info(f"📉 RTT min: {min_rtt:.1f}ms")
            
            # Déconnexions
            total_disconnections = len(self.disconnection_events)
            logger.info(f"🔌 Déconnexions détectées: {total_disconnections}")
            
            if self.disconnection_events:
                logger.info("🚨 DÉTAILS DES DÉCONNEXIONS:")
                for event in self.disconnection_events:
                    logger.info(
                        f"   - Connexion {event['connection_id']}: {event['reason']} "
                        f"(après {event['duration_before_disconnect']:.1f}s)"
                    )
        
        # Verdict final
        if len(successful_connections) == len(self.connections) and len(self.disconnection_events) == 0:
            logger.info("🎉 VERDICT: WEBSOCKET STABLE - Aucun problème détecté!")
        elif len(self.disconnection_events) > 0:
            logger.error(f"🚨 VERDICT: PROBLÈMES DE STABILITÉ - {len(self.disconnection_events)} déconnexions détectées")
        else:
            logger.warning("⚠️ VERDICT: PROBLÈMES DE CONNEXION - Certaines connexions ont échoué")
        
        return {
            'stable': len(self.disconnection_events) == 0 and len(failed_connections) == 0,
            'total_connections': len(self.connections),
            'successful_connections': len(successful_connections),
            'failed_connections': len(failed_connections),
            'disconnections': len(self.disconnection_events),
            'ping_success_rate': pong_success_rate if 'pong_success_rate' in locals() else 0,
            'avg_rtt': avg_rtt if 'avg_rtt' in locals() else None
        }

async def main():
    """Fonction principale"""
    import sys
    
    # Paramètres par défaut
    ws_url = "ws://localhost:3000/ws"
    duration_minutes = 5  # 5 minutes par défaut
    concurrent_connections = 2
    
    # Parser les arguments de ligne de commande
    if len(sys.argv) > 1:
        ws_url = sys.argv[1]
    if len(sys.argv) > 2:
        duration_minutes = int(sys.argv[2])
    if len(sys.argv) > 3:
        concurrent_connections = int(sys.argv[3])
    
    logger.info(f"🔧 Test de stabilité WebSocket: {ws_url}")
    logger.info(f"📊 Durée: {duration_minutes} minutes, Connexions: {concurrent_connections}")
    
    tester = WebSocketStabilityTester(ws_url, duration_minutes)
    
    try:
        await tester.run_stability_test(concurrent_connections)
    except KeyboardInterrupt:
        logger.info("⏹️ Test interrompu par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur pendant le test: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

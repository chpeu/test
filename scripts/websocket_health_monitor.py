#!/usr/bin/env python3
"""
Script de surveillance WebSocket - Détecte et diagnostique les déconnexions
Utilise pour s'assurer que le problème WebSocket soit résolu de façon permanente
"""

import asyncio
import aiohttp
import json
import time
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import traceback

# Configuration - Utiliser le port correct détecté (5000)
BACKEND_URL = "http://localhost:5000"
WEBSOCKET_URL = "ws://localhost:3000/ws"  # Frontend dev server
BACKEND_WS_URL = "ws://localhost:5000/ws"  # Backend WebSocket
CHECK_INTERVAL = 10  # secondes
MAX_DISCONNECTIONS = 5  # avant alerte critique
RECONNECT_THRESHOLD = 30  # secondes pour détecter déconnexions rapides

class WebSocketHealthMonitor:
    def __init__(self):
        self.logger = self._setup_logger()
        self.disconnections: List[Dict] = []
        self.start_time = time.time()
        self.last_backend_check = 0
        self.backend_crashes = 0
        self.session: Optional[aiohttp.ClientSession] = None
        
    def _setup_logger(self):
        """Configurer le logger"""
        logger = logging.getLogger('websocket_monitor')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
        
    async def check_backend_health(self) -> Dict:
        """Vérifier la santé du backend"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
                
            async with self.session.get(f"{BACKEND_URL}/api/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"status": "healthy", "data": data}
                else:
                    return {"status": "unhealthy", "error": f"HTTP {resp.status}"}
                    
        except aiohttp.ClientConnectorError:
            return {"status": "unreachable", "error": "Connection refused"}
        except asyncio.TimeoutError:
            return {"status": "timeout", "error": "Request timeout"}
        except Exception as e:
            return {"status": "error", "error": f"{type(e).__name__}: {e}"}
    
    async def check_websocket_connections(self) -> Dict:
        """Vérifier les connexions WebSocket actives"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
                
            async with self.session.get(f"{BACKEND_URL}/api/websocket/stats") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"status": "ok", "connections": data.get("active_connections", 0), "data": data}
                else:
                    return {"status": "error", "error": f"HTTP {resp.status}"}
                    
        except Exception as e:
            return {"status": "error", "error": f"{type(e).__name__}: {e}"}
    
    async def test_websocket_connection(self, url: str) -> Dict:
        """Tester une connexion WebSocket"""
        import websockets
        
        try:
            self.logger.info(f"🔌 Test connexion WebSocket: {url}")
            
            # Timeout court pour détecter rapidement les problèmes
            async with websockets.connect(url, ping_timeout=5, close_timeout=5) as websocket:
                # Envoyer un ping
                await websocket.send(json.dumps({"type": "ping", "timestamp": time.time()}))
                
                # Attendre la réponse (avec timeout)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "pong":
                        # Calculer RTT avec timestamp client envoyé
                        ping_timestamp = data.get("client_ts", time.time())
                        rtt_ms = (time.time() - ping_timestamp) * 1000
                        return {"status": "healthy", "rtt_ms": rtt_ms, "server_timestamp": data.get("timestamp")}
                    elif data.get("type") in ["event", "server_hello"]:
                        # Backend envoie d'abord un message d'état, puis répond au ping
                        # Attendre la réponse pong après le message d'initialisation
                        response2 = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        data2 = json.loads(response2)
                        if data2.get("type") == "pong":
                            ping_timestamp = data2.get("client_ts", time.time())
                            rtt_ms = (time.time() - ping_timestamp) * 1000
                            return {"status": "healthy", "rtt_ms": rtt_ms, "server_timestamp": data2.get("timestamp")}
                        else:
                            return {"status": "unexpected_response", "data": [data, data2]}
                    else:
                        return {"status": "unexpected_response", "data": data}
                        
                except asyncio.TimeoutError:
                    return {"status": "timeout", "error": "No pong received"}
                    
        except websockets.exceptions.ConnectionClosed as e:
            return {"status": "closed", "error": f"Connection closed: {e.code} {e.reason}"}
        except ConnectionRefusedError:
            return {"status": "refused", "error": "Connection refused"}
        except Exception as e:
            return {"status": "error", "error": f"{type(e).__name__}: {e}"}
    
    def record_disconnection(self, source: str, reason: str, duration_s: Optional[float] = None):
        """Enregistrer une déconnexion"""
        disconnection = {
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
            "source": source,
            "reason": reason,
            "duration_s": duration_s
        }
        
        self.disconnections.append(disconnection)
        
        # Garder seulement les 50 dernières
        if len(self.disconnections) > 50:
            self.disconnections = self.disconnections[-50:]
        
        self.logger.warning(f"❌ [DISCONNECTION] {source}: {reason} (duration: {duration_s}s)")
        
        # Vérifier si c'est une déconnexion rapide
        if duration_s and duration_s < RECONNECT_THRESHOLD:
            self.logger.error(f"🚨 [RAPID-DISCONNECT] {source}: Déconnexion rapide en {duration_s}s!")
    
    def analyze_disconnection_patterns(self) -> Dict:
        """Analyser les patterns de déconnexion"""
        if not self.disconnections:
            return {"status": "no_disconnections"}
        
        # Déconnexions des dernières 5 minutes
        recent_threshold = time.time() - 300
        recent = [d for d in self.disconnections if d["timestamp"] > recent_threshold]
        
        # Déconnexions rapides (< 30s)
        rapid = [d for d in self.disconnections if d.get("duration_s") is not None and d.get("duration_s", 0) < RECONNECT_THRESHOLD]
        
        # Par source
        by_source = {}
        for d in self.disconnections:
            source = d["source"]
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(d)
        
        return {
            "total_disconnections": len(self.disconnections),
            "recent_5min": len(recent),
            "rapid_disconnections": len(rapid),
            "by_source": {k: len(v) for k, v in by_source.items()},
            "last_disconnection": self.disconnections[-1] if self.disconnections else None
        }
    
    async def generate_report(self) -> Dict:
        """Générer un rapport de santé complet"""
        backend_health = await self.check_backend_health()
        ws_stats = await self.check_websocket_connections()
        
        # Test des connexions WebSocket
        backend_ws_test = await self.test_websocket_connection(BACKEND_WS_URL)
        
        # Analyser les déconnexions
        disconnection_analysis = self.analyze_disconnection_patterns()
        
        uptime_s = time.time() - self.start_time
        
        report = {
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
            "uptime_s": uptime_s,
            "uptime_str": str(timedelta(seconds=int(uptime_s))),
            "backend_health": backend_health,
            "websocket_stats": ws_stats,
            "backend_websocket_test": backend_ws_test,
            "disconnection_analysis": disconnection_analysis,
            "backend_crashes": self.backend_crashes
        }
        
        return report
    
    async def print_status(self):
        """Afficher le status actuel"""
        report = await self.generate_report()
        
        self.logger.info("=" * 60)
        self.logger.info(f"📊 WEBSOCKET HEALTH MONITOR - {report['datetime']}")
        self.logger.info(f"⏱️  Uptime: {report['uptime_str']}")
        
        # Backend
        backend = report["backend_health"]
        if backend["status"] == "healthy":
            self.logger.info(f"✅ Backend: {backend['status']}")
        else:
            self.logger.error(f"❌ Backend: {backend['status']} - {backend.get('error', 'N/A')}")
            self.backend_crashes += 1
        
        # WebSocket Stats
        ws_stats = report["websocket_stats"]
        if ws_stats["status"] == "ok":
            conn_count = ws_stats.get("connections", 0)
            self.logger.info(f"🔌 WebSocket Connections: {conn_count}")
        else:
            self.logger.warning(f"⚠️ WebSocket Stats: {ws_stats.get('error', 'Unknown error')}")
        
        # WebSocket Test
        ws_test = report["backend_websocket_test"]
        if ws_test["status"] == "healthy":
            rtt = ws_test.get("rtt_ms", 0)
            self.logger.info(f"✅ WebSocket Test: OK (RTT: {rtt:.1f}ms)")
        else:
            self.logger.error(f"❌ WebSocket Test: {ws_test['status']} - {ws_test.get('error', 'N/A')}")
            self.record_disconnection("websocket_test", ws_test.get('error', 'Unknown'))
        
        # Déconnexions
        disc = report["disconnection_analysis"]
        if disc.get("total_disconnections", 0) > 0:
            self.logger.warning(f"⚠️ Déconnexions: Total={disc['total_disconnections']}, Récentes={disc['recent_5min']}, Rapides={disc['rapid_disconnections']}")
            
            # Alerte si trop de déconnexions
            if disc["recent_5min"] >= MAX_DISCONNECTIONS:
                self.logger.error(f"🚨 ALERTE: {disc['recent_5min']} déconnexions dans les 5 dernières minutes!")
        
        self.logger.info("=" * 60)
    
    async def run_monitoring_loop(self, duration_minutes: Optional[int] = None):
        """Boucle principale de surveillance"""
        self.logger.info(f"🚀 Démarrage surveillance WebSocket (intervalle: {CHECK_INTERVAL}s)")
        
        if duration_minutes:
            self.logger.info(f"⏱️ Durée: {duration_minutes} minutes")
            end_time = time.time() + (duration_minutes * 60)
        else:
            end_time = None
            self.logger.info("⏱️ Durée: Illimitée (Ctrl+C pour arrêter)")
        
        try:
            while True:
                await self.print_status()
                
                # Vérifier si on doit s'arrêter
                if end_time and time.time() >= end_time:
                    self.logger.info("⏰ Durée écoulée, arrêt de la surveillance")
                    break
                
                await asyncio.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            self.logger.info("⛔ Arrêt demandé par l'utilisateur")
        except Exception as e:
            self.logger.error(f"❌ Erreur dans la boucle de surveillance: {e}")
            traceback.print_exc()
        finally:
            if self.session:
                await self.session.close()
    
    async def run_single_check(self):
        """Effectuer une seule vérification"""
        try:
            await self.print_status()
            
            report = await self.generate_report()
            
            # Sauvegarder le rapport
            report_file = f"websocket_health_report_{int(time.time())}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            self.logger.info(f"📄 Rapport sauvegardé: {report_file}")
            
            return report
            
        finally:
            if self.session:
                await self.session.close()

async def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="WebSocket Health Monitor")
    parser.add_argument("--duration", "-d", type=int, help="Durée en minutes (défaut: illimité)")
    parser.add_argument("--single", "-s", action="store_true", help="Une seule vérification")
    parser.add_argument("--interval", "-i", type=int, default=CHECK_INTERVAL, help="Intervalle en secondes")
    
    args = parser.parse_args()
    
    # Utiliser l'intervalle spécifié
    interval = args.interval if hasattr(args, 'interval') else CHECK_INTERVAL
    
    monitor = WebSocketHealthMonitor()
    
    if args.single:
        await monitor.run_single_check()
    else:
        await monitor.run_monitoring_loop(args.duration)

if __name__ == "__main__":
    asyncio.run(main())

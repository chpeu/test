#!/usr/bin/env python3
"""
Backend Watchdog - Surveille et redémarre automatiquement le backend bloqué
"""
import asyncio
import websockets
import json
import subprocess
import time
import os
import signal
import psutil
from datetime import datetime

class BackendWatchdog:
    def __init__(self, backend_port=5000, check_interval=30, timeout=10):
        self.backend_port = backend_port
        self.check_interval = check_interval
        self.timeout = timeout
        self.backend_process = None
        self.restart_count = 0
        self.last_successful_check = None
        self.backend_stdout_file = None
        self.backend_stderr_file = None
        self.last_health_error = None
        self.last_restart_reason = None
        self.log_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "logs",
            "backend_watchdog.log"
        )
        self._log_file = None
        try:
            os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
            self._log_file = open(self.log_file_path, "a", encoding="utf-8")
        except Exception:
            self._log_file = None
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] WATCHDOG: {message}"
        print(line)
        if self._log_file:
            try:
                self._log_file.write(line + "\n")
                self._log_file.flush()
            except Exception:
                pass
        
    async def check_websocket_health(self):
        """Test si le WebSocket backend répond"""
        try:
            async with websockets.connect(f'ws://localhost:{self.backend_port}/ws', timeout=self.timeout) as ws:
                # Test ping simple
                test_msg = {'type': 'request', 'id': 'watchdog_health', 'request_type': 'state'}
                await ws.send(json.dumps(test_msg))
                response = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                
                if response and len(response) > 50:  # Réponse valide attendue
                    self.last_successful_check = datetime.now()
                    self.last_health_error = None
                    return True
                else:
                    self.log(f"Réponse WebSocket invalide: {len(response)} chars")
                    self.last_health_error = "invalid_response"
                    return False
                    
        except Exception as e:
            self.last_health_error = str(e)
            self.log(f"WebSocket Health Check FAILED: {self.last_health_error}")
            return False
            
    def find_backend_process(self):
        """Trouve le processus backend Python en cours"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'python.exe':
                        cmdline = proc.info['cmdline']
                        if cmdline and len(cmdline) > 1 and 'main.py' in cmdline[1]:
                            return proc.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return None
        except Exception as e:
            self.log(f"Erreur recherche processus: {e}")
            return None
            
    def kill_backend_process(self):
        """Termine le processus backend bloqué"""
        try:
            pid = self.find_backend_process()
            if pid:
                self.log(f"Terminaison forcée du processus backend PID {pid}")
                subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                             capture_output=True, text=True, check=False)
                time.sleep(2)
                return True
            else:
                self.log("Aucun processus backend trouvé")
                return False
        except Exception as e:
            self.log(f"Erreur terminaison processus: {e}")
            return False
            
    def start_backend(self):
        """Démarre le backend"""
        try:
            reason = self.last_restart_reason or "watchdog_start"
            self.log(f"Démarrage du backend (reason={reason})...")
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
            os.makedirs(log_dir, exist_ok=True)

            if self.backend_stdout_file:
                try:
                    self.backend_stdout_file.close()
                except Exception:
                    pass
            if self.backend_stderr_file:
                try:
                    self.backend_stderr_file.close()
                except Exception:
                    pass

            self.backend_stdout_file = open(
                os.path.join(log_dir, "backend_stdout.log"),
                "a",
                encoding="utf-8"
            )
            self.backend_stderr_file = open(
                os.path.join(log_dir, "backend_stderr.log"),
                "a",
                encoding="utf-8"
            )

            # Démarrer en arrière-plan sans bloquer le watchdog
            env = os.environ.copy()
            env["BACKEND_REBOOT_REASON"] = reason
            self.backend_process = subprocess.Popen(
                ['python', 'main.py'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=self.backend_stdout_file,
                stderr=self.backend_stderr_file,
                env=env
            )
            
            # Attendre un peu pour que le serveur démarre
            time.sleep(8)
            self.restart_count += 1
            self.log(f"Backend redémarré (tentative #{self.restart_count}) - PID: {self.backend_process.pid}")
            return True
            
        except Exception as e:
            self.log(f"Erreur démarrage backend: {e}")
            return False
            
    async def monitor_loop(self):
        """Boucle principale de surveillance"""
        self.log("🔍 Démarrage du watchdog backend...")
        self.log(f"Surveillance: port {self.backend_port}, vérification toutes les {self.check_interval}s")
        
        while True:
            try:
                # Vérifier la santé du WebSocket
                is_healthy = await self.check_websocket_health()
                
                if is_healthy:
                    self.log("✅ Backend WebSocket: OK")
                else:
                    self.log("❌ Backend WebSocket: BLOQUE - Redémarrage nécessaire")
                    
                    # Tuer le processus bloqué
                    self.last_restart_reason = f"watchdog_ws_unhealthy:{self.last_health_error or 'no_response'}"
                    self.kill_backend_process()
                    
                    # Redémarrer
                    if self.start_backend():
                        self.log(f"✅ Backend redémarré automatiquement (total: {self.restart_count})")
                    else:
                        self.log("❌ Échec redémarrage backend")
                        
            except Exception as e:
                self.log(f"Erreur dans la boucle de surveillance: {e}")
                
            # Attendre avant la prochaine vérification
            await asyncio.sleep(self.check_interval)
            
    def run(self):
        """Démarrer le watchdog"""
        try:
            asyncio.run(self.monitor_loop())
        except KeyboardInterrupt:
            self.log("Arrêt du watchdog demandé")
            if self.backend_process:
                self.backend_process.terminate()

if __name__ == "__main__":
    watchdog = BackendWatchdog(
        backend_port=5000,      # Port du backend
        check_interval=45,      # Vérification toutes les 45 secondes  
        timeout=15              # Timeout WebSocket de 15 secondes
    )
    watchdog.run()

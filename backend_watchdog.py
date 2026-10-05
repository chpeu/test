#!/usr/bin/env python3
"""
Backend Watchdog - Surveille et redémarre automatiquement le backend bloqué
"""
import asyncio
import http.client
import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime

try:
    import psutil
except Exception:  # pragma: no cover - fallback sans dépendance
    psutil = None

class BackendWatchdog:
    def __init__(self, backend_port=5000, check_interval=30, timeout=10):
        self.backend_port = backend_port
        self.check_interval = check_interval
        self.timeout = timeout
        self.health_url = f"http://localhost:{self.backend_port}/api/health"
        self.backend_process = None
        self.restart_count = 0
        self.last_successful_check = None
        self.backend_stdout_file = None
        self.backend_stderr_file = None
        self.last_health_error = None
        self.last_restart_reason = None
        self.consecutive_failures = 0
        self.max_failures = 3
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

        if psutil is None:
            self.log("⚠️ psutil indisponible: kill via handle uniquement (fallback)")
        
    def log(self, message, *args):
        timestamp = datetime.now().strftime("%H:%M:%S")
        if args:
            try:
                message = message % args
            except Exception:
                message = f"{message} {args}"
        line = f"[{timestamp}] WATCHDOG: {message}"
        print(line)
        if self._log_file:
            try:
                self._log_file.write(line + "\n")
                self._log_file.flush()
            except Exception:
                pass
        
    def _fetch_health(self):
        request = urllib.request.Request(
            self.health_url,
            headers={"Connection": "close", "User-Agent": "BackendWatchdog/1.0"}
        )
        last_error = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    status_code = getattr(response, "status", None) or response.getcode()
                    payload = response.read()
                    data = {}
                    if payload:
                        try:
                            data = json.loads(payload.decode("utf-8", errors="replace"))
                        except Exception:
                            data = {}
                    status = data.get("status")
                    if status_code == 200 and status in ("healthy", "degraded"):
                        return True, None
                    return False, f"status={status_code} body_status={status}"
            except (
                http.client.RemoteDisconnected,
                ConnectionResetError,
                ConnectionAbortedError,
                socket.timeout,
                urllib.error.URLError,
            ) as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.25)
                    continue
                raise
        if last_error:
            raise last_error

    async def check_backend_health(self):
        """Test si le backend répond via /api/health"""
        try:
            ok, error = await asyncio.to_thread(self._fetch_health)
            if ok:
                self.last_successful_check = datetime.now()
                self.last_health_error = None
                return True
            self.last_health_error = error or "unhealthy"
            return False
        except Exception as e:
            self.last_health_error = str(e)
            return False
            
    def find_backend_process(self):
        """Trouve le processus backend Python en cours"""
        try:
            if self.backend_process and self.backend_process.poll() is None:
                return self.backend_process.pid

            if psutil is None:
                return None

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
            if self.backend_process and self.backend_process.poll() is None:
                pid = self.backend_process.pid
                self.log(f"Terminaison du processus backend via handle PID {pid}")
                try:
                    self.backend_process.terminate()
                    time.sleep(2)
                    if self.backend_process.poll() is None:
                        self.backend_process.kill()
                except Exception as e:
                    self.log(f"Erreur terminaison via handle: {e}")
                return True

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
        self.log(
            f"Surveillance: port {self.backend_port}, check /api/health toutes les {self.check_interval}s"
        )

        if not self.backend_process or self.backend_process.poll() is not None:
            self.last_restart_reason = "watchdog_startup"
            self.start_backend()
        
        while True:
            try:
                if not self.backend_process or self.backend_process.poll() is not None:
                    self.log("Backend non détecté - démarrage automatique")
                    self.last_restart_reason = "watchdog_missing_process"
                    self.start_backend()
                    await asyncio.sleep(self.check_interval)
                    continue

                # Vérifier la santé via HTTP
                is_healthy = await self.check_backend_health()
                
                if is_healthy:
                    self.consecutive_failures = 0
                    self.log("✅ Backend health: OK")
                else:
                    self.consecutive_failures += 1
                    self.log(
                        "❌ Backend health KO (%s/%s) - %s",
                        self.consecutive_failures,
                        self.max_failures,
                        self.last_health_error or "no_response"
                    )
                    if self.consecutive_failures < self.max_failures:
                        await asyncio.sleep(self.check_interval)
                        continue
                    self.consecutive_failures = 0
                    self.log("❌ Backend health KO - Redémarrage nécessaire")
                    
                    # Tuer le processus bloqué
                    self.last_restart_reason = f"watchdog_health_unhealthy:{self.last_health_error or 'no_response'}"
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

import os
import sys
import time
import subprocess
from pathlib import Path

def run_as_service():
    """Lance l'extracteur comme service Windows"""
    script_dir = Path(__file__).parent
    extractor_path = script_dir / "mexc_token_extractor.py"
    
    if not extractor_path.exists():
        print(f"Erreur: {extractor_path} non trouvé")
        return
    
    print("Demarrage service MEXC Token Extractor...")
    
    try:
        # Lancer en mode daemon
        subprocess.Popen([
            sys.executable, 
            str(extractor_path), 
            "daemon"
        ], 
        cwd=str(script_dir),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        print("OK Service demarre avec succes")
        
    except Exception as e:
        print(f"ERREUR demarrage service: {e}")

if __name__ == "__main__":
    run_as_service()

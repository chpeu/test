
import sys
import os
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
root_dir = os.getcwd()
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from main import app

print("Listing all registered routes:")
print("-" * 100)
for route in app.routes:
    if hasattr(route, 'path'):
        methods = getattr(route, 'methods', [])
        print(f"{list(methods)} {route.path}")
print("-" * 100)

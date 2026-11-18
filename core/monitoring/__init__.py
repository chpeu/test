"""
Paquet de surveillance.

`refactoring_dashboard` a été retiré le 17/11/2026 : c'était un serveur Flask
interne (donc un second serveur web à côté de FastAPI) chargé de suivre
l'avancement d'une refonte démarrée fin 2025. Flask n'est pas installé dans
l'environnement du projet : le module ne pouvait plus s'exécuter du tout.
"""

# Import pour effet de bord + ré-export du module (routeur/dashboard enregistré à
# l'import) — d'où le noqa F401.
from . import scanner_phase3_dashboard  # noqa: F401

__all__ = ["scanner_phase3_dashboard"]

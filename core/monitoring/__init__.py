# Monitoring package for refactoring

# Import des modules de monitoring
try:
    from . import refactoring_dashboard
except ImportError:
    # Flask non disponible - dashboard désactivé  
    refactoring_dashboard = None

# Import pour effet de bord + ré-export du module (routeur/dashboard enregistré à
# l'import) — d'où le noqa F401.
from . import scanner_phase3_dashboard  # noqa: F401

__all__ = ['refactoring_dashboard', 'scanner_phase3_dashboard']

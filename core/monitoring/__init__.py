# Monitoring package for refactoring

# Import des modules de monitoring
try:
    from . import refactoring_dashboard
except ImportError:
    # Flask non disponible - dashboard désactivé  
    refactoring_dashboard = None

from . import scanner_phase3_dashboard

"""
Core modules for Trade Cursor
"""
from .indicators import Indicators
import sys
import os

# Ajouter le répertoire racine au path si nécessaire
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from .scanner import ScalabilityScanner
# Import TechnicalAnalyzer depuis le fichier analyzer.py (pas le package analyzer/)
import importlib.util
import os
analyzer_file = os.path.join(os.path.dirname(__file__), 'analyzer.py')
spec = importlib.util.spec_from_file_location("core.analyzer_file", analyzer_file)
analyzer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer_module)
TechnicalAnalyzer = analyzer_module.TechnicalAnalyzer

from .position_manager import PositionManager, Position, PositionConfig
from .scheduler import Scheduler
from .metrics import MetricsCollector, get_metrics_collector

__all__ = [
    'Indicators',
    'ScalabilityScanner',
    'TechnicalAnalyzer',
    'PositionManager',
    'Position',
    'PositionConfig',
    'Scheduler',
    'MetricsCollector',
    'get_metrics_collector'
]


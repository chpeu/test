"""
Configuration pytest - Fixtures globales
"""
# Sans ce plafond, xgboost et sklearn ouvrent autant de threads que de coeurs
# du processeur. Mesure du 19/11/2026: un seul tour d'optimisation sur 260 lignes
# consommait 43 minutes de CPU pour 6 minutes montre, et la suite complete
# s'eternisait. Deux threads suffisent pour les petits jeux de tests.
import os

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient


# CRITICAL: Apply logger fixes BEFORE any imports
import logging.handlers

# Immediately disable all file-based logging
def _disable_file_logging():
    """Aggressively disable all file-based logging operations"""
    # Override problematic handler classes to prevent file operations
    
    class SafeRotatingFileHandler(logging.NullHandler):
        def __init__(self, *args, **kwargs):
            super().__init__()
    
    class SafeFileHandler(logging.NullHandler):
        def __init__(self, *args, **kwargs):
            super().__init__()
            
    class SafeTimedRotatingFileHandler(logging.NullHandler):
        def __init__(self, *args, **kwargs):
            super().__init__()
    
    # Patch logging module to replace file handlers
    logging.FileHandler = SafeFileHandler
    logging.handlers.RotatingFileHandler = SafeRotatingFileHandler
    logging.handlers.TimedRotatingFileHandler = SafeTimedRotatingFileHandler
    
    # Override any custom handlers that might exist
    try:
        from utils.logger import SafeRotatingFileHandler as CustomSafeHandler  # noqa: F401  (sonde : l'import est le test)
        import utils.logger
        utils.logger.SafeRotatingFileHandler = SafeRotatingFileHandler
    except ImportError:
        pass

# Apply immediately
_disable_file_logging()

@pytest.fixture(scope="session", autouse=True)
def configure_test_logging():
    """Configure safe logging for ALL tests - completely disable file operations"""

    def _safe_close_handler(handler):
        try:
            if isinstance(handler, logging.StreamHandler):
                return
            if hasattr(handler, 'close'):
                handler.close()
        except Exception:
            pass
    
    # GLOBAL: Disable all existing loggers and handlers
    root_logger = logging.getLogger()
    
    # Remove ALL handlers from root logger
    for handler in root_logger.handlers[:]:
        try:
            root_logger.removeHandler(handler)
            _safe_close_handler(handler)
        except Exception:
            pass
    
    # Disable propagation and set high level to minimize noise
    root_logger.setLevel(logging.CRITICAL)
    root_logger.propagate = False
    
    # Get all existing loggers and clean them aggressively
    logger_dict = logging.Logger.manager.loggerDict.copy()
    for name in logger_dict:
        try:
            logger = logging.getLogger(name)
            logger.setLevel(logging.CRITICAL)
            logger.propagate = False
            logger.disabled = True  # Completely disable
            # Remove all handlers
            for handler in logger.handlers[:]:
                try:
                    logger.removeHandler(handler)
                    _safe_close_handler(handler)
                except Exception:
                    pass
        except Exception:
            pass
    
    # Add single null handler to root to prevent any output
    null_handler = logging.NullHandler()
    root_logger.addHandler(null_handler)
    
    # Override any future logger creation to be safe
    def safe_getLogger(name=None):
        logger = original_getLogger(name) if name else original_getLogger()
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False
        logger.disabled = True  # Completely disable
        # Remove any handlers that might get added
        for handler in logger.handlers[:]:
            if not isinstance(handler, logging.NullHandler):
                try:
                    logger.removeHandler(handler)
                    _safe_close_handler(handler)
                except Exception:
                    pass
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        return logger
    
    # Store original before monkey patching
    original_getLogger = logging.getLogger
    # Monkey patch logging.getLogger to always return safe logger
    logging.getLogger = safe_getLogger
    
    # Store original for cleanup
    configure_test_logging._original_getLogger = original_getLogger


@pytest.fixture(scope="session", autouse=True)
def _recherches_optuna_hors_du_depot(tmp_path_factory):
    """Un test ne doit pas salir le dépôt (mesuré 19/11/2026).

    `api/routes/ml_common.py` pointe son carnet de dernières recherches sur
    `data/optuna_last_runs.json` en chemin relatif : la suite de tests
    réécrivait donc un fichier du projet à chaque passage ( horodatage changé,
    sans erreur nulle part). On le déplace dans un dossier temporaire le temps
    de la séance.
    """
    import api.routes.ml_common as ml_common

    chemin_temporaire = tmp_path_factory.mktemp("optuna") / "optuna_last_runs.json"
    original = ml_common.LAST_RUNS_FILE
    ml_common.LAST_RUNS_FILE = chemin_temporaire
    yield
    ml_common.LAST_RUNS_FILE = original


@pytest.fixture(scope="session", autouse=True)
def _reglages_vivants_hors_du_depot(tmp_path_factory):
    """Aucun test ne doit ecrire dans `config_overrides.json`, le fichier du robot.

    Le chemin est absolut dans `utils.config_persistence` (donc changer de dossier
    ne protege pas). Mesure du 19/11/2026: la suite complete y avait remis
    `gb_min_confidence` a 0,4, effacant la decision prise par l'IA pilote la
    veille. On remplace la cible par un fichier temporaire pour toute la seance.
    """
    import utils.config_persistence as persistance

    chemin_temporaire = tmp_path_factory.mktemp("reglages") / "config_overrides.json"
    originaux = {"persistance": persistance.CONFIG_OVERRIDES_FILE}
    persistance.CONFIG_OVERRIDES_FILE = chemin_temporaire

    import api.routes.ml_optimization as routes_ml

    if hasattr(routes_ml, "CONFIG_OVERRIDES_FILE"):
        originaux["routes_ml"] = routes_ml.CONFIG_OVERRIDES_FILE
        routes_ml.CONFIG_OVERRIDES_FILE = chemin_temporaire

    yield chemin_temporaire

    persistance.CONFIG_OVERRIDES_FILE = originaux["persistance"]
    if "routes_ml" in originaux:
        routes_ml.CONFIG_OVERRIDES_FILE = originaux["routes_ml"]


@pytest.fixture
def client():
    """Fixture TestClient FastAPI"""
    from main import app
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def _close_global_singletons():
    yield

    # ⚠️ Seulement fermer les ressources async, PAS remettre les singletons à None
    # car l'app backend peut encore tourner après les tests
    try:
        from api import price_provider as price_provider_mod

        provider = getattr(price_provider_mod, "_price_provider", None)
        if provider is not None:
            try:
                asyncio.run(provider.stop_websocket())
            except RuntimeError:
                pass

        # ❌ NE PAS faire: price_provider_mod._price_provider = None
        # L'app backend utilise encore ce singleton après les tests
    except Exception:
        pass

    try:
        from api import mexc as mexc_mod

        mexc_client = getattr(mexc_mod, "_mexc_client", None)
        if mexc_client is not None:
            try:
                asyncio.run(mexc_client.close())
            except RuntimeError:
                pass

        # ❌ NE PAS faire: mexc_mod._mexc_client = None
        # L'app backend utilise encore ce singleton après les tests
    except Exception:
        pass


@pytest.fixture
def jeu_ml():
    """Petit jeu de donnees ML synthetique (260 prises) pour les tests d'entrainement.

    Le fabricant vit dans `tests/fabrication_ml.py` et est charge par son chemin :
    le dossier des tests n'est pas un paquet, donc un `import` classique depend du
    hasard du chemin de pytest (mesure: le meme import passait dans un fichier et
    echouait dans son voisin).
    """
    import importlib.util
    from pathlib import Path

    chemin = Path(__file__).resolve().parent / "fabrication_ml.py"
    spec = importlib.util.spec_from_file_location("fabrication_ml", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.jeu_de_donnees()

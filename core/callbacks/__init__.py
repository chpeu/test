"""
Package callbacks - Boucles asynchrones automatiques exécutées par le scheduler
"""

from . import scanner_loop
from . import position_check_loop
from . import scalability_refresh

# Fonctions principales
async def scanner_loop_callback():
    """Boucle de scanner - 45 secondes"""
    return await scanner_loop.scanner_loop_callback()


async def position_check_loop_callback():
    """Boucle de vérification position - 2 secondes"""
    return await position_check_loop.position_check_loop_callback()


async def scalability_refresh_loop_callback():
    """Boucle de rafraîchissement scalabilité - 90 secondes"""
    return await scalability_refresh.scalability_refresh_loop_callback()


__all__ = [
    'scanner_loop_callback',
    'position_check_loop_callback',
    'scalability_refresh_loop_callback',
    'scanner_loop',
    'position_check_loop',
    'scalability_refresh'
]

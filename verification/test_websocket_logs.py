#!/usr/bin/env python3
"""
Script de diagnostic pour WebSocketLogHandler
Vérifie si les logs sont envoyés au frontend via WebSocket
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from core.state_manager import StateManager
from core.websocket_manager import get_websocket_manager
from utils.logger import WebSocketLogHandler

def test_websocket_handler():
    """Test si le WebSocketLogHandler fonctionne"""
    print("=" * 60)
    print("🔍 DIAGNOSTIC WebSocketLogHandler")
    print("=" * 60)

    # 1. Vérifier StateManager
    print("\n1. Vérification StateManager...")
    try:
        state = StateManager()
        print("   ✅ StateManager créé")
    except Exception as e:
        print(f"   ❌ Erreur StateManager: {e}")
        return False

    # 2. Vérifier WebSocketManager
    print("\n2. Vérification WebSocketManager...")
    try:
        ws_mgr = state.get_ws_manager()
        print(f"   ✅ WebSocketManager: {ws_mgr is not None}")
        if ws_mgr:
            print(f"   Type: {type(ws_mgr).__name__}")
        else:
            print("   ❌ WebSocketManager est None!")
            return False
    except Exception as e:
        print(f"   ❌ Erreur WebSocketManager: {e}")
        return False

    # 3. Vérifier root logger handlers
    print("\n3. Vérification root logger handlers...")
    root_logger = logging.getLogger()
    print(f"   Nombre de handlers: {len(root_logger.handlers)}")
    
    ws_handlers = [h for h in root_logger.handlers if isinstance(h, WebSocketLogHandler)]
    print(f"   Nombre de WebSocketLogHandler: {len(ws_handlers)}")
    
    if ws_handlers:
        print("   ✅ WebSocketLogHandler trouvé")
        for i, handler in enumerate(ws_handlers):
            print(f"   Handler {i}: ws_manager={handler.ws_manager is not None}")
    else:
        print("   ❌ Aucun WebSocketLogHandler trouvé!")
        print("   Handlers existants:")
        for i, handler in enumerate(root_logger.handlers):
            print(f"   Handler {i}: {type(handler).__name__}")

    # 4. Test envoi log
    print("\n4. Test envoi de log...")
    test_logger = logging.getLogger("test_websocket")
    test_logger.setLevel(logging.INFO)
    
    # Ajouter WebSocketLogHandler manuellement
    if ws_mgr:
        ws_handler = WebSocketLogHandler()
        ws_handler.set_ws_manager(ws_mgr)
        ws_handler.setLevel(logging.INFO)
        test_logger.addHandler(ws_handler)
        
        print("   Envoi de log de test...")
        test_logger.info("🧪 TEST LOG - Ceci est un message de test")
        print("   ✅ Log envoyé (vérifier sur le frontend)")
    else:
        print("   ❌ Impossible de tester - ws_manager est None")

    # 5. Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ")
    print("=" * 60)
    print(f"WebSocketManager disponible: {ws_mgr is not None}")
    print(f"WebSocketLogHandler configuré: {len(ws_handlers) > 0}")
    print(f"Logs envoyés: {'OUI' if ws_mgr and ws_handlers else 'NON'}")
    print("=" * 60)

if __name__ == "__main__":
    test_websocket_handler()

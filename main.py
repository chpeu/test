# 🔥 REMPLACEMENT: WebSocket natif endpoint

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket natif pour communication temps réel
    Remplace Socket.IO pour performance optimale
    """
    ws_manager = get_websocket_manager()
    await ws_manager.connect(websocket)
    
    try:
        # Envoyer l'état initial au client
        status_data = app_state.copy()
        if status_data.get('active_position') and hasattr(status_data['active_position'], 'to_dict'):
            status_data['active_position'] = status_data['active_position'].to_dict()
        
        await ws_manager.send_personal_message({
            'type': 'event',
            'event': 'status',
            'data': status_data,
            'timestamp': datetime.now().isoformat()
        }, websocket)
        
        # Envoyer les derniers logs
        for log_entry in app_state['logs'][-50:]:
            await ws_manager.send_personal_message({
                'type': 'event',
                'event': 'log',
                'data': log_entry,
                'timestamp': datetime.now().isoformat()
            }, websocket)
        
        logger.info("✅ WebSocket client connecté et initialisé")
        
        # Boucle de réception des messages
        while True:
            try:
                # Recevoir les messages du client (ping, commandes, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Gérer les différents types de messages
                if message.get('type') == 'ping':
                    # Répondre au ping
                    await ws_manager.send_personal_message({
                        'type': 'pong',
                        'timestamp': datetime.now().isoformat()
                    }, websocket)
                elif message.get('type') == 'request_logs':
                    # Envoyer les logs demandés
                    await ws_manager.send_personal_message({
                        'type': 'event',
                        'event': 'logs',
                        'data': app_state['logs'][-100:],
                        'timestamp': datetime.now().isoformat()
                    }, websocket)
                elif message.get('type') == 'command':
                    # Gérer les commandes (start/stop bot, etc.)
                    command = message.get('command')
                    logger.info(f"📨 Commande reçue via WebSocket: {command}")
                    # Les commandes peuvent être traitées ici si nécessaire
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logger.warning(f"⚠️ Message WebSocket invalide reçu: {data}")
            except Exception as e:
                logger.error(f"❌ Erreur traitement message WebSocket: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info("❌ WebSocket client déconnecté")
    except Exception as e:
        logger.error(f"❌ Erreur WebSocket: {e}")
    finally:
        await ws_manager.disconnect(websocket)

# Configuration endpoints
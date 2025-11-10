# Ajouter après l'endpoint /api/config (ligne ~2573)

@app.get("/api/config/complete")
async def api_get_complete_config():
    """
    🔥 NOUVEAU: Récupérer TOUTES les variables de configuration (TRADING_CONFIG complet)
    Utile pour vérifier toutes les variables prises en compte par le bot
    """
    from config import TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS, TREND_BONUS_CONFIG
    from config import RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG, WEBSOCKET_CONFIG
    
    return JSONResponse({
        'trading_config': TRADING_CONFIG,
        'risk_config': RISK_CONFIG,
        'condition_weights': CONDITION_WEIGHTS,
        'trend_bonus_config': TREND_BONUS_CONFIG,
        'retry_config': RETRY_CONFIG,
        'circuit_breaker_config': CIRCUIT_BREAKER_CONFIG,
        'websocket_config': WEBSOCKET_CONFIG,
        'timestamp': time.time()
    })

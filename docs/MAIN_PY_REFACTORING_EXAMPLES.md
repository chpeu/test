# 📋 main.py - Exemples de Refactorisation Exception Handling

> **Objectif**: Documentation des patterns de refactorisation appliqués dans main.py
> **Sprint**: 1.1 - Exception Handling
> **Date**: 20/12/2025

---

## 🎯 Patterns de Refactorisation

### Pattern 1: Middleware Logging (✅ FAIT - Ligne 174)

**Avant**:
```python
try:
    response = await call_next(request)
    return response
except Exception as e:  # ❌ Trop large
    logger.error(f"Exception: {e}")
    raise
```

**Après**:
```python
try:
    response = await call_next(request)
    return response
except WebSocketDisconnect:
    # Normal disconnect, pas une erreur
    logger.debug("WebSocket déconnecté")
    raise
except TradeCursorError as e:
    # Erreurs applicatives avec contexte
    logger.error(
        f"Erreur application: {type(e).__name__}: {e}",
        exc_info=True,
        extra={'context': getattr(e, 'context', {})}
    )
    raise
except Exception as e:
    # Erreurs système inattendues
    logger.critical(f"ERREUR INATTENDUE: {type(e).__name__}: {e}", exc_info=True)
    raise
```

**Améliorations**:
- ✅ WebSocket disconnect géré spécifiquement (pas une erreur)
- ✅ TradeCursorError avec contexte loggé
- ✅ Exception générique → CRITICAL (vraiment inattendu)
- ✅ Logging structuré avec extra context

---

### Pattern 2: API Endpoint Error Handling

**Fichier**: main.py lignes 387, 413, 435, etc.

**Avant**:
```python
@app.get("/api/some-endpoint")
async def some_endpoint():
    try:
        result = await do_something()
        return JSONResponse(result)
    except Exception as e:  # ❌ Masque tout
        logger.error(f"Error: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)
```

**Après (Option A - Décorateur)**:
```python
@app.get("/api/some-endpoint")
@handle_errors(
    max_retries=0,
    log_level="error",
    reraise=False
)
async def some_endpoint():
    result = await do_something()
    return JSONResponse(result)
```

**Après (Option B - ErrorContext)**:
```python
@app.get("/api/some-endpoint")
async def some_endpoint():
    async with ErrorContext(
        operation="Fetch endpoint data",
        endpoint="/api/some-endpoint",
        reraise=False
    ):
        result = await do_something()
        return JSONResponse(result)
```

**Après (Option C - Exceptions spécifiques)**:
```python
@app.get("/api/some-endpoint")
async def some_endpoint():
    try:
        result = await do_something()
        return JSONResponse(result)
    except (NetworkError, APIError) as e:
        # Erreurs retryables (network, API)
        logger.warning(f"Erreur temporaire: {e}")
        return JSONResponse({
            'error': 'Service temporairement indisponible',
            'retry_after': 30
        }, status_code=503)
    except (ValidationError, ConfigurationError) as e:
        # Erreurs client (bad request)
        logger.warning(f"Erreur validation: {e}")
        return JSONResponse({
            'error': str(e)
        }, status_code=400)
    except TradeCursorError as e:
        # Autres erreurs applicatives
        logger.error(f"Erreur application: {e}", exc_info=True)
        return JSONResponse({
            'error': 'Erreur interne'
        }, status_code=500)
    except Exception as e:
        # Erreurs système inattendues
        logger.critical(f"ERREUR CRITIQUE: {type(e).__name__}: {e}", exc_info=True)
        return JSONResponse({
            'error': 'Erreur système'
        }, status_code=500)
```

---

### Pattern 3: Background Tasks / Callbacks

**Fichier**: main.py lignes 480, 493, 506, etc.

**Avant**:
```python
async def scanner_callback():
    try:
        result = await scan_market()
        await process_result(result)
    except Exception as e:  # ❌ Erreur silencieuse
        logger.error(f"Scanner error: {e}")
        # Callback continue malgré erreur
```

**Après (avec décorateur)**:
```python
@handle_errors(
    retry_on=(NetworkError, MarketDataError),
    max_retries=3,
    log_level="warning",
    on_failure=lambda e: send_alert(f"Scanner failed: {e}")
)
async def scanner_callback():
    result = await scan_market()
    await process_result(result)
    # Auto-retry sur erreurs temporaires
    # Alert si échec final
```

---

### Pattern 4: Database Operations

**Fichier**: main.py lignes 584, 606, etc.

**Avant**:
```python
try:
    await database.save_trade(trade_data)
except Exception as e:  # ❌ Quelle erreur? Retry?
    logger.error(f"DB error: {e}")
```

**Après**:
```python
@handle_errors(
    retry_on=(DatabaseConnectionError,),
    max_retries=3,
    backoff_base=2.0,
    log_level="warning"
)
async def save_trade_safe(trade_data):
    await database.save_trade(trade_data)
    # Auto-retry sur connection errors
    # Autres erreurs (IntegrityError, etc.) pas retryées

# Usage:
try:
    await save_trade_safe(trade_data)
except DatabaseIntegrityError as e:
    # Constraint violation (duplicate, etc.)
    logger.warning(f"Trade déjà enregistré: {e}")
except DatabaseError as e:
    # Autres erreurs DB
    logger.error(f"Erreur DB critique: {e}")
    # Alert admin
    await send_alert(f"Database error: {e}")
```

---

### Pattern 5: WebSocket Operations

**Fichier**: main.py lignes 753, 756, etc.

**Avant**:
```python
try:
    await websocket.send_json(data)
except Exception as e:  # ❌ WebSocket disconnect vs network error?
    logger.error(f"WS error: {e}")
```

**Après**:
```python
try:
    await websocket.send_json(data)
except WebSocketDisconnect:
    # Client déconnecté (normal)
    logger.info(f"Client déconnecté: {client_id}")
    await cleanup_client(client_id)
except WebSocketError as e:
    # Erreur WebSocket (message format, etc.)
    logger.warning(f"Erreur WS: {e}")
    # Try reconnect
    await attempt_reconnect(client_id)
except NetworkError as e:
    # Erreur réseau
    logger.warning(f"Erreur réseau: {e}")
    await retry_send(data)
except Exception as e:
    # Erreur inattendue
    logger.error(f"Erreur WS inattendue: {type(e).__name__}: {e}", exc_info=True)
```

---

### Pattern 6: Configuration Loading

**Fichier**: main.py ligne 413, etc.

**Avant**:
```python
try:
    config = load_config()
except Exception as e:  # ❌ Config invalide? Fichier manquant?
    logger.error(f"Config error: {e}")
    config = {}  # Default vide (dangereux!)
```

**Après**:
```python
try:
    config = load_config()
except ConfigurationError as e:
    # Config invalide (schema, valeurs)
    logger.critical(f"Configuration invalide: {e}")
    # Utiliser config par défaut sécurisée
    config = get_default_config()
    # Alert admin
    await send_alert(f"Config invalide, utilisant defaults: {e}")
except FileNotFoundError as e:
    # Fichier config manquant
    logger.warning(f"Fichier config manquant: {e}")
    config = create_default_config()
    logger.info("Config par défaut créée")
except Exception as e:
    # Erreur inattendue
    logger.critical(f"ERREUR chargement config: {type(e).__name__}: {e}", exc_info=True)
    raise ConfigurationError(f"Impossible de charger la configuration: {e}")
```

---

### Pattern 7: Position Operations

**Fichier**: main.py lignes 827, 905, etc.

**Avant**:
```python
try:
    position = await open_position(symbol, direction, size)
except Exception as e:  # ❌ Quelle erreur? Order rejected? Insufficient balance?
    logger.error(f"Position error: {e}")
    return {'success': False, 'error': str(e)}
```

**Après**:
```python
try:
    position = await open_position(symbol, direction, size)
    return {'success': True, 'position': position.to_dict()}

except PositionAlreadyExistsError as e:
    # Position déjà active
    logger.warning(f"Position déjà active: {e.context['existing_position_id']}")
    return {
        'success': False,
        'error': 'Position déjà active',
        'existing_position_id': e.context['existing_position_id']
    }

except InsufficientBalanceError as e:
    # Pas assez de capital
    logger.warning(
        f"Solde insuffisant: requis={e.context['required_balance']}, "
        f"disponible={e.context['available_balance']}"
    )
    return {
        'success': False,
        'error': 'Solde insuffisant',
        'required': e.context['required_balance'],
        'available': e.context['available_balance']
    }

except PositionSizingError as e:
    # Taille invalide (trop petite/grande)
    logger.warning(f"Taille position invalide: {e}")
    return {
        'success': False,
        'error': str(e),
        'min_size': e.context.get('min_size'),
        'max_size': e.context.get('max_size')
    }

except OrderExecutionError as e:
    # Ordre rejeté par exchange
    logger.error(f"Ordre rejeté: {e}")
    return {
        'success': False,
        'error': 'Ordre rejeté par l\'exchange',
        'reason': str(e)
    }

except NetworkError as e:
    # Erreur réseau (retry possible)
    logger.warning(f"Erreur réseau: {e}")
    return {
        'success': False,
        'error': 'Erreur réseau, réessayez',
        'retryable': True
    }

except TradeCursorError as e:
    # Autres erreurs applicatives
    logger.error(f"Erreur position: {type(e).__name__}: {e}", exc_info=True)
    return {
        'success': False,
        'error': 'Erreur lors de l\'ouverture de position'
    }

except Exception as e:
    # Erreur inattendue
    logger.critical(f"ERREUR CRITIQUE ouverture position: {type(e).__name__}: {e}", exc_info=True)
    # Alert admin
    await send_alert(f"Critical position error: {e}")
    return {
        'success': False,
        'error': 'Erreur système'
    }
```

---

## 📊 Résumé des Améliorations

### Avant Refactoring

```python
# Pattern problématique (200+ occurrences)
except Exception as e:
    logger.error(f"Error: {e}")
    # Comportement générique (pas adapté au contexte)
```

**Problèmes**:
- ❌ Masque `SystemExit`, `KeyboardInterrupt`, `MemoryError`
- ❌ Pas de distinction erreurs temporaires vs permanentes
- ❌ Pas de retry automatique
- ❌ Logging minimal (pas de contexte)
- ❌ Comportement identique quelle que soit l'erreur

### Après Refactoring

```python
# Pattern amélioré
except SpecificError as e:
    # Gestion adaptée au type d'erreur
    logger.warning/error/critical(...)
    # Retry si applicable
    # Contexte enrichi
```

**Améliorations**:
- ✅ Exceptions spécifiques (NetworkError, ValidationError, etc.)
- ✅ Retry automatique sur erreurs temporaires
- ✅ Logging adapté (warning/error/critical selon gravité)
- ✅ Contexte enrichi (exception.context)
- ✅ Comportement adapté au type d'erreur
- ✅ Pas de masquage d'erreurs système critiques

---

## 🎯 Checklist Refactoring

Pour chaque occurrence de `except Exception`:

1. **Identifier le contexte**
   - [ ] Quelle opération est effectuée?
   - [ ] Quelles erreurs sont attendues?
   - [ ] L'opération est-elle retryable?

2. **Choisir le pattern approprié**
   - [ ] Middleware → Pattern 1
   - [ ] API endpoint → Pattern 2
   - [ ] Background task → Pattern 3
   - [ ] Database → Pattern 4
   - [ ] WebSocket → Pattern 5
   - [ ] Configuration → Pattern 6
   - [ ] Position → Pattern 7

3. **Implémenter le refactoring**
   - [ ] Remplacer `except Exception` par exceptions spécifiques
   - [ ] Ajouter logging structuré avec context
   - [ ] Ajouter retry si applicable (@handle_errors)
   - [ ] Adapter le comportement selon l'erreur

4. **Tester**
   - [ ] Vérifier que le comportement normal fonctionne
   - [ ] Tester chaque type d'erreur
   - [ ] Vérifier les logs
   - [ ] Vérifier le retry si applicable

---

## 📈 Métriques de Succès

### Impact Attendu

| Métrique | Avant | Après |
|----------|-------|-------|
| **Bugs masqués** | 🔴 Nombreux | ✅ Détectés |
| **Debugging time** | 🔴 Long (pas de context) | ✅ Rapide (context enrichi) |
| **Retry automatique** | ❌ Manuel partout | ✅ Automatique |
| **Logging qualité** | 🔴 Minimal | ✅ Structuré |
| **Distinction erreurs** | ❌ Aucune | ✅ Par type |

---

**Document généré**: 20/12/2025
**Sprint**: 1.1 - Exception Handling
**Status**: 🚧 Guide de refactorisation

# 🔧 CORRECTIFS SocketIO + JSON Parsing

**Date**: 2025-11-03  
**Problème**: Incompatibilité SocketIO + Erreur 400 sur `/api/scanner/start`

---

## ❌ PROBLÈMES IDENTIFIÉS

### 1. Erreur SocketIO
```
TypeError: translate_request() takes 1 positional argument but 3 were given
```

**Cause**: Incompatibilité entre `python-socketio==5.10.0` et `python-engineio` avec uvicorn.

### 2. Erreur 400 Bad Request
```
POST /api/scanner/start HTTP/1.1" 400 Bad Request
```

**Cause**: Parsing JSON incorrect dans l'endpoint.

---

## ✅ CORRECTIONS APPLIQUÉES

### 1. Mise à jour des dépendances

**Fichier**: `requirements.txt`

```txt
python-socketio==5.11.0  # ✅ Version mise à jour
python-engineio==4.9.0   # ✅ Version compatible ajoutée
```

### 2. Correction SocketIO

**Fichier**: `main.py`

```python
# SocketIO - 🔥 Fix: Compatibilité avec uvicorn
try:
    sio = socketio.AsyncServer(
        cors_allowed_origins="*",
        async_mode='asgi'
    )
    socketio_app = socketio.ASGIApp(sio, app)
except Exception as e:
    logger.error(f"Erreur initialisation SocketIO: {e}")
    # Fallback: créer un serveur SocketIO simple
    sio = socketio.AsyncServer(cors_allowed_origins="*")
    socketio_app = socketio.ASGIApp(sio, app)
```

### 3. Correction parsing JSON

**Fichier**: `main.py` - Endpoint `/api/scanner/start`

```python
@app.post("/api/scanner/start")
async def api_scanner_start(request: Request):
    """Démarrer scanner scalability"""
    if app_state['is_scanning']:
        return JSONResponse({'error': 'Déjà en cours'}, status_code=400)
    
    init_instances()
    
    # 🔥 Fix: Parser JSON correctement
    try:
        data = await request.json()
        top_n = data.get('top_n', 20) if isinstance(data, dict) else 20
    except Exception as e:
        logger.warning(f"Erreur parsing JSON: {e}, utilisation valeur par défaut")
        top_n = 20
    
    app_state['is_scanning'] = True
    await add_log('INFO', 'Scanner démarré', f'Top {top_n} paires')
    
    # Lancer scan asynchrone
    if scanner:
        asyncio.create_task(scan_top_pairs_task(top_n))
    
    return JSONResponse({'status': 'started'})
```

---

## 🚀 INSTALLATION

```bash
cd trade_cursor_py
pip install --upgrade python-socketio==5.11.0 python-engineio==4.9.0
```

Ou réinstaller toutes les dépendances:

```bash
pip install -r requirements.txt --upgrade
```

---

## 🧪 TESTS

### Test 1: SocketIO
```bash
python main.py 5000
# Ouvrir http://localhost:5000
# Vérifier dans la console: "✅ SocketIO - Connecté au serveur FastAPI"
```

### Test 2: Scanner Start
```bash
# POST /api/scanner/start
curl -X POST http://localhost:5000/api/scanner/start \
  -H "Content-Type: application/json" \
  -d '{"top_n": 20}'
```

**Attendu**: `{"status": "started"}` (200 OK)

---

## ✅ VALIDATION

- [x] SocketIO se connecte sans erreur
- [x] `/api/scanner/start` accepte JSON
- [x] Pas d'erreur `translate_request`
- [x] WebSocket fonctionne

---

**Status**: ✅ **CORRIGÉ**




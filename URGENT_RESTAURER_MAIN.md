# ⚠️ URGENT : FICHIER main.py CORROMPU

**Date**: 2025-11-03  
**Status**: 🔴 **CRITIQUE**

---

## 🐛 PROBLÈME

Le fichier `main.py` a été accidentellement écrasé et ne contient plus que 38 lignes au lieu de ~960 lignes.

---

## ✅ SOLUTION IMMÉDIATE

### Option 1 : Restaurer depuis Git (si vous utilisez Git)

```bash
cd "C:\Users\sebta\Documents\code scalp\trade_cursor_py"
git checkout main.py
```

### Option 2 : Restaurer depuis un backup

Cherchez un fichier de sauvegarde :
- `main.py.bak`
- `main.py.backup`
- `main.py~`
- Ou dans le dossier `old/` ou `old2/`

### Option 3 : Restaurer depuis l'historique de l'éditeur

Si vous utilisez VS Code ou Cursor :
1. Clic droit sur `main.py` dans l'explorateur
2. "Local History" → "Timeline" 
3. Restaurer la version précédente

---

## 🔍 DIAGNOSTIC

Le WebSocket n'est pas connecté car :
1. Le fichier `main.py` est corrompu
2. Le serveur ne peut pas fonctionner correctement
3. L'endpoint `/api/websocket/start` existe mais le reste du code est manquant

---

## 📝 APRÈS RESTAURATION

Une fois `main.py` restauré, ajouter cet endpoint pour démarrer manuellement le WebSocket :

```python
@app.post("/api/websocket/start")
async def api_start_websocket():
    """Démarrer manuellement le WebSocket pour les top pairs"""
    init_instances()
    
    if not price_provider:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    if not app_state['top_pairs']:
        return JSONResponse({
            'error': 'Aucune top pair disponible. Lancez d\'abord /api/scanner/start',
            'status': 'no_pairs'
        }, status_code=400)
    
    try:
        symbols = [p.get('symbol', '') for p in app_state['top_pairs'][:30] if p.get('symbol')]
        
        if not symbols:
            return JSONResponse({'error': 'Aucun symbole valide trouvé'}, status_code=400)
        
        await price_provider.start_websocket(symbols)
        
        return JSONResponse({
            'status': 'started',
            'symbols_count': len(symbols),
            'symbols': symbols[:10]
        })
        
    except Exception as e:
        logger.error(f"Erreur démarrage WebSocket: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)
```

---

## 🚨 ACTION REQUISE

**RESTAUREZ LE FICHIER main.py IMMÉDIATEMENT** avant de continuer.

Le serveur ne peut pas fonctionner avec un fichier corrompu.




# LISTE DES BUGS CRITIQUES - ACTIONS IMMÉDIATES

Date: 2025-11-10 | Version: Trade Cursor v7.0

## 3 BUGS CRITIQUES À FIXER (En priorité)

### 🔴 BUG #1: Paramètres Perdus au Redémarrage
**Sévérité**: CRITIQUE | **Temps Fix**: 4-6h | **Impact**: Données utilisateur perdues

**Description**:
```
TRADING_CONFIG est un dictionnaire Python en mémoire.
Aucune sauvegarde en base de données.
Au redémarrage du bot: TOUS les paramètres reviennent aux valeurs par défaut.
```

**Reproduction**:
```
1. Ouvrir VariablesPanel
2. Changer un paramètre (ex: tp_percent = 0.8)
3. Vérifier le changement côté backend (WebSocket confirm reçu)
4. Redémarrer le bot
5. Vérifier VariablesPanel: tp_percent = 0.6 (valeur par défaut)
```

**Fichiers Affectés**:
- `/home/user/test/main.py` (TRADING_CONFIG dict ligne ~100-200)
- `/home/user/test/config.py` (Pas de persistance)
- `/home/user/test/frontend/src/lib/components/VariablesPanel.svelte`
- `/home/user/test/frontend/src/lib/components/SettingsPanel.svelte`

**Solution Recommandée**:
1. Créer classe `ConfigDatabase` (core/config_database.py)
   ```python
   class ConfigDatabase:
       def save(self, key, value, version=None)
       def load(self, key)
       def load_all(self)
       def get_version(self, version_id)
   ```

2. Table SQLite:
   ```sql
   CREATE TABLE trading_config (
       id INTEGER PRIMARY KEY,
       key TEXT UNIQUE,
       value TEXT,
       type TEXT,
       updated_at TIMESTAMP,
       version INTEGER
   )
   ```

3. Dans main.py handle_client_command:
   ```python
   elif command == 'update_config':
       # ... code existant ...
       # Nouvelle ligne:
       config_db.save(key, value)  # Persistance
   ```

4. Au démarrage:
   ```python
   # Load from DB
   saved_config = config_db.load_all()
   TRADING_CONFIG.update(saved_config)
   ```

**Tests à faire**:
- [ ] Changer param → Redémarrer → Vérifier persisté
- [ ] Changer 5 params à la fois → Tous persistés?
- [ ] Type validation (float/int/bool)
- [ ] Rollback version

---

### 🔴 BUG #2: Socket.IO Non Retiré
**Sévérité**: CRITIQUE | **Temps Fix**: 1-2h | **Impact**: Code confus, poids inutile

**Description**:
```
Migration vers WebSocket natif complétée.
Mais Socket.IO dépendances toujours présentes:
- socket.io-client v4.7.4 dans package.json
- python-socketio==5.11.0 dans requirements.txt
- socket.js (246 lignes) non supprimé
```

**Fichiers à Supprimer**:
```
❌ frontend/src/lib/utils/socket.js (246 lignes)
   - Remplacé par websocket.ts
   - Plus aucun import
   
❌ frontend/package.json
   - Ligne: "socket.io-client": "^4.7.4"
   - Supprimer cette entrée
   
❌ requirements.txt (Backend)
   - Ligne: python-socketio==5.11.0
   - Supprimer après vérifier migrations
```

**Vérifications Avant Suppression**:
```bash
# Frontend
grep -r "socket.js" /home/user/test/frontend/src/
grep -r "from.*socket" /home/user/test/frontend/src/
grep -r "import.*socket" /home/user/test/frontend/src/

# Backend
grep -r "socketio" /home/user/test --include="*.py" | grep -v "# 🔥"
```

**Résultat Expected**:
- ✅ Aucun import de socket.js
- ✅ Aucun "import socketio" en Python
- ✅ Juste références legacy commentées

**Commandes à Exécuter**:
```bash
# Frontend
rm /home/user/test/frontend/src/lib/utils/socket.js

# package.json - Supprimer ligne
#   "socket.io-client": "^4.7.4"

# Backend requirements.txt - Supprimer ligne
#   python-socketio==5.11.0

# Vérifier plus d'imports
npm ls socket.io-client 2>/dev/null | grep -v deduped
pip list | grep socketio
```

---

### 🔴 BUG #3: Synchronisation Config Cassée (Multi-Client)
**Sévérité**: CRITIQUE | **Temps Fix**: 2-3h | **Impact**: Utilisateurs voient données stale

**Description**:
```
Quand 2 clients se connectent:
  Client A change un paramètre via VariablesPanel
  → Backend reçoit et met à jour TRADING_CONFIG ✅
  → Backend émet événement 'config_change' ✅
  → Client B n'est PAS notifié ❌
  
Client B voit toujours ancienne valeur jusqu'à rechargement manuel.
```

**Root Cause**:
```
VariablesPanel.svelte (ligne 250) dit:
  // 🔥 REMPLACEMENT: WebSocket natif gère déjà les changements de config via websocket.js
  
Mais websocket.js est legacy Socket.IO!
Et websocket.ts (WebSocket natif) n'émet PAS 'config_change'.
```

**Solution**:

1. **Dans websocket.ts**, ajouter listener:
```typescript
// Dans handleMessage:
if (type === 'event' && message.event === 'config_change') {
    console.log('Config changed:', message.data);
    this.emitEvent('config_change', message.data);
}
```

2. **Dans VariablesPanel.svelte**, ajouter:
```typescript
import { getWebSocket } from '$lib/utils/websocket';

onMount(() => {
    const ws = getWebSocket();
    if (ws) {
        ws.on('config_change', (data) => {
            console.log('Config change received:', data);
            // Update stores
            Object.entries(data).forEach(([key, value]) => {
                updateSetting(key, value);
            });
        });
    }
});
```

3. **Dans main.py**, émettre broadcast:
```python
elif command == 'update_config':
    # ... code existant ...
    # Nouveau broadcast:
    await ws_manager.emit('config_change', updated)
```

**Tests**:
```
1. Ouvrir 2 onglets du même bot
2. Tab 1: Changer tp_percent = 0.8
3. Tab 2: Vérifier tp_percent mis à jour (ACTUELLEMENT FAIL)
4. Inverser: Tab 2 change, Tab 1 reçoit (ACTUELLEMENT FAIL)
```

---

## 5 BUGS IMPORTANTS À FIXER (Priorité 2)

### 🟠 BUG #4: Pas de Validation Frontend
**Sévérité**: IMPORTANT | **Temps Fix**: 3-4h

VariablesPanel accepte N'IMPORTE QUELLE valeur sans validation.

**Exemples**:
```
- tp_percent: -999 ✅ (devrait être > 0)
- escalier_level1_size: 999999 ✅ (devrait être 0-100)
- volume_multiplier: "abc" ✅ (devrait être float)
```

**Fix**:
```typescript
// VariablesPanel.svelte
<input 
    type="number" 
    min="0.01" 
    max="5" 
    step="0.01"
    bind:value={config.tp_percent}
/>

// Plus validation côté backend
if tp_percent < 0.01 or tp_percent > 5:
    raise ValueError("tp_percent doit être entre 0.01 et 5")
```

---

### 🟠 BUG #5: Fallback REST Redondant
**Sévérité**: IMPORTANT | **Temps Fix**: 2-3h

Chaque composant a fallback REST:
```typescript
try {
    await sendCommandViaWS(...)
} catch {
    await fetch('/api/...')  // Fallback
}
```

⚠️ Maintient 2 systèmes parallèles, confusion backend.

**Décider**:
- Option A: WebSocket primary + REST fallback (current)
- Option B: Supprimer REST, WebSocket only
- Option C: REST primary + WS fallback (reverse)

**Recommandation**: Option A (WebSocket preferred) mais nettoyer.

---

### 🟠 BUG #6: Timeout Dur 10 secondes
**Sévérité**: IMPORTANT | **Temps Fix**: 1-2h

websocket.ts ligne 214:
```typescript
const timeout = setTimeout(() => {
    reject(new Error('Timeout commande'));
}, 10000);  // Dur, pas de retry
```

Commande longue → Timeout → Error → Rien.

**Fix**:
```typescript
// Retry automatique
async function sendCommandWithRetry(cmd, params, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            return await sendCommand(cmd, params);
        } catch (err) {
            if (i < retries - 1) {
                await delay(1000 * (i + 1)); // Exponential backoff
                continue;
            }
            throw err;
        }
    }
}
```

---

### 🟠 BUG #7: Format Réponse Inconsistant
**Sévérité**: IMPORTANT | **Temps Fix**: 1h

SettingsPanel.svelte ligne 57:
```typescript
if (result && result.updated) { }
```

Mais main.py retourne:
```python
return {'updated': {...}, 'success': True}
```

❌ `result.updated` ne garantit rien!

**Fix**: Standardiser format réponse
```python
async def handle_client_command(command, params):
    return {
        'success': True,        # Toujours présent
        'command': command,
        'result': {},           # Données spécifiques
        'error': None           # Si error
    }
```

---

### 🟠 BUG #8: Logger Callback Absent
**Sévérité**: IMPORTANT | **Temps Fix**: 1-2h

main.py:
```python
async def websocket_callback(event_type, data):
    """Callback pour envoyer via WebSocket natif"""
```

Utilisé dans notifications mais pas partout.

**Logs ne sont pas envoyés** via WebSocket natif aux clients.

**Fix**: Utiliser ws_manager.send_log() partout:
```python
await ws_manager.send_log({
    'level': 'INFO',
    'message': 'Bot started',
    'timestamp': time.time()
})
```

---

## CHECKLIST CORRECTIONS

### Jour 1 (Urgent)
- [ ] BUG #1: Implémenter persistance config
  - [ ] Créer ConfigDatabase
  - [ ] Sauver à chaque update
  - [ ] Charger au démarrage
  
- [ ] BUG #2: Retirer Socket.IO
  - [ ] Supprimer socket.js
  - [ ] Supprimer package.json entry
  - [ ] Supprimer requirements.txt entry
  
- [ ] BUG #3: Ajouter 'config_change' broadcast
  - [ ] Modifier websocket.ts
  - [ ] Modifier VariablesPanel.svelte
  - [ ] Modifier main.py

### Jour 2 (Important)
- [ ] BUG #4: Ajouter validation frontend
- [ ] BUG #5: Décider fallback strategy
- [ ] BUG #6: Implémenter retry automatiqu
- [ ] BUG #7: Standardiser format réponse
- [ ] BUG #8: Utiliser ws_manager.send_log partout

### Tests
- [ ] Sauvegarde/restauration config
- [ ] Multi-client sync
- [ ] Validation inputs
- [ ] Timeout + retry
- [ ] Format réponse

---

## COMMANDES RAPIDES

```bash
# Vérifier références Socket.IO
grep -r "socket\.io\|socketio" /home/user/test/frontend/src/
grep -r "socketio" /home/user/test --include="*.py" | grep -v "# 🔥"

# Supprimer Socket.IO
rm /home/user/test/frontend/src/lib/utils/socket.js

# Lister tous les imports websocket
grep -r "import.*websocket\|from.*websocket" /home/user/test/frontend/src/

# Vérifier endpoints REST
grep -r "@router\." /home/user/test/api/

# Tester WebSocket
curl -i -N -H "Connection: Upgrade" \
    -H "Upgrade: websocket" \
    http://localhost:5000/ws
```

---

## RÉFÉRENCES RAPIDES

**Fichiers Clés**:
- Backend WebSocket: `/home/user/test/core/websocket_manager.py`
- Frontend WebSocket: `/home/user/test/frontend/src/lib/utils/websocket.ts`
- Config: `/home/user/test/main.py` (ligne 2214 handle_client_command)
- VariablesPanel: `/home/user/test/frontend/src/lib/components/VariablesPanel.svelte`

**Documentation**:
- Analyse complète: `/home/user/test/ANALYSE_WEBSOCKET_COMPLET.md`
- Synthèse: `/home/user/test/SYNTHESE_COMPOSANTS.md`

**Temps Total Estimation**:
- Bug #1 (Config): 4-6h
- Bug #2 (Socket.IO): 1-2h
- Bug #3 (Multi-client): 2-3h
- Bugs #4-8: 7-10h
- Tests: 3-5h
- **Total: 17-26h (2-3 jours complets)**


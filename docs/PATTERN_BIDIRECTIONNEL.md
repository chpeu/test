# 🔄 PATTERN BIDIRECTIONNEL TEMPS RÉEL

**Version**: v7.0
**Date**: 10 Novembre 2025
**Objectif**: Garantir que TOUTES les futures fonctionnalités soient bidirectionnelles en temps réel sans rafraîchissement manuel

---

## 🎯 Principe Fondamental

**TOUT changement d'état DOIT être propagé automatiquement via WebSocket dans les DEUX directions :**

```
Frontend ←─ WebSocket événement ──→ Backend
         └─ WebSocket commande  ──→
```

**❌ INTERDIT** : Rafraîchissement manuel de la page
**✅ OBLIGATOIRE** : Mise à jour automatique temps réel via WebSocket

---

## 📋 Checklist Implémentation

Pour **CHAQUE** nouvelle fonctionnalité, suivre ces 5 étapes :

### ✅ 1. Backend : Émettre les Événements

**Fichier** : `main.py`

```python
# Quand l'état change côté backend, TOUJOURS émettre un événement
async def some_action():
    # Modifier l'état
    app_state['my_feature'] = True

    # 🔥 BIDIRECTIONNEL: Émettre l'événement pour le frontend
    await ws_manager.emit('my_feature_changed', {
        'my_feature': True,
        'timestamp': time.time()
    })
```

### ✅ 2. Backend : Commande WebSocket

**Fichier** : `main.py` dans `handle_websocket_command()`

```python
elif command == 'update_my_feature':
    # Valider avec Pydantic (si params complexes)
    try:
        validated_params = MyFeatureParams(**params)
    except ValidationError as e:
        raise ValueError(f"Invalid parameters: {e}")

    # Modifier l'état
    app_state['my_feature'] = validated_params.value

    # 🔥 BIDIRECTIONNEL: Émettre pour tous les clients
    await ws_manager.emit('my_feature_changed', {
        'my_feature': validated_params.value,
        'timestamp': time.time()
    })

    return {'status': 'success', 'my_feature': validated_params.value}
```

### ✅ 3. Frontend : Listener Événement

**Fichier** : `+page.svelte` ou composant concerné

```javascript
function setupWebSocketListeners(ws: BidirectionalWebSocket) {
    // 🔥 BIDIRECTIONNEL: Écouter l'événement du backend
    ws.on('my_feature_changed', (data: any) => {
        console.log('✅ My feature changed (événement temps réel)', data);

        // Mettre à jour le store ou variable locale
        import('$lib/stores/my-feature').then(({ myFeature }) => {
            myFeature.set(data.my_feature);
        });
    });
}
```

### ✅ 4. Frontend : Envoyer Commande

**Fichier** : Composant qui modifie la fonctionnalité

```javascript
async function updateMyFeature(newValue) {
    try {
        const { sendCommandViaWS } = await import('$lib/utils/websocket');

        // 🔥 BIDIRECTIONNEL: Envoyer commande au backend
        const result = await sendCommandViaWS('update_my_feature', {
            value: newValue
        });

        console.log('✅ My feature updated:', result);
        // Pas besoin de mettre à jour manuellement, l'événement le fera !
    } catch (err) {
        console.error('❌ Error updating my feature:', err);
    }
}
```

### ✅ 5. Store Svelte (si nécessaire)

**Fichier** : `frontend/src/lib/stores/my-feature.js`

```javascript
import { writable } from 'svelte/store';

// 🔥 BIDIRECTIONNEL: Store mis à jour automatiquement par événements WebSocket
export const myFeature = writable(false);

// Actions (optionnel)
export function updateMyFeature(value) {
    myFeature.set(value);
}
```

---

## 📚 Exemples Concrets

### Exemple 1 : Scanner (is_scanning)

**Backend** (`main.py`):
```python
# Ligne 1661-1665
await ws_manager.emit('scan_started', {
    'timestamp': time.time(),
    'is_scanning': True
})
```

**Frontend** (`+page.svelte`):
```javascript
// Ligne 105-111
ws.on('scan_started', (data: any) => {
    console.log('✅ Scanner démarré (événement temps réel)', data);
    import('$lib/stores/scanner').then(({ isScanning }) => {
        isScanning.set(true);
    });
});
```

**Store** (`scanner.js`):
```javascript
export const isScanning = writable(false);
```

**Résultat** : Quand un utilisateur clique "Start Scanner", **TOUS les clients** voient le bouton changer instantanément sans rafraîchir.

---

### Exemple 2 : Configuration (config)

**Backend** (`main.py`):
```python
# Ligne 2534-2537
await ws_manager.emit('config_change', {
    'changes': updated,
    'timestamp': time.time()
})
```

**Frontend** (`VariablesPanel.svelte`):
```javascript
// Ligne 255-268
ws.on('config_change', (data) => {
    if (data.changes) {
        Object.entries(data.changes).forEach(([key, value]) => {
            if (key in config) {
                config[key] = value;
            }
        });
        config = {...config};  // Force reactive update
    }
});
```

**Résultat** : Quand un utilisateur modifie `volume_multiplier`, **TOUS les autres onglets ouverts** voient la valeur se mettre à jour instantanément.

---

## 🛠️ Templates de Code

### Template Backend : Nouvelle Fonctionnalité

```python
# 1. Ajouter Pydantic model (si params complexes)
class MyFeatureParams(BaseModel):
    value: str = Field(..., description="Value of my feature")
    enabled: bool = Field(default=True, description="Enable feature")

# 2. Dans handle_websocket_command()
elif command == 'update_my_feature':
    try:
        validated_params = MyFeatureParams(**params)
    except ValidationError as e:
        raise ValueError(f"Invalid parameters: {e}")

    # Modifier l'état global
    app_state['my_feature'] = validated_params.model_dump()

    # 🔥 BIDIRECTIONNEL: Émettre événement
    await ws_manager.emit('my_feature_changed', {
        'my_feature': app_state['my_feature'],
        'timestamp': time.time()
    })

    return {'status': 'success', 'my_feature': app_state['my_feature']}

# 3. Dans les actions automatiques (si applicable)
async def some_automatic_action():
    # ... logique métier ...

    # 🔥 BIDIRECTIONNEL: Émettre changement d'état
    await ws_manager.emit('my_feature_changed', {
        'my_feature': new_value,
        'timestamp': time.time()
    })
```

### Template Frontend : Nouveau Composant

```svelte
<script>
    import { onMount } from 'svelte';
    import { getWebSocket, sendCommandViaWS } from '$lib/utils/websocket';
    import { myFeature } from '$lib/stores/my-feature';

    let loading = false;

    // 🔥 BIDIRECTIONNEL: Écouter les événements backend
    onMount(() => {
        const ws = getWebSocket();

        if (ws) {
            ws.on('my_feature_changed', (data) => {
                console.log('🔄 My feature changed:', data);
                $myFeature = data.my_feature;
            });
        }
    });

    // 🔥 BIDIRECTIONNEL: Envoyer commande au backend
    async function updateFeature(newValue) {
        loading = true;
        try {
            await sendCommandViaWS('update_my_feature', {
                value: newValue,
                enabled: true
            });
            console.log('✅ Feature updated');
        } catch (err) {
            console.error('❌ Error:', err);
        } finally {
            loading = false;
        }
    }
</script>

<div>
    <h3>My Feature: {$myFeature}</h3>
    <button on:click={() => updateFeature('new_value')} disabled={loading}>
        Update Feature
    </button>
</div>
```

---

## ⚠️ Erreurs Courantes à Éviter

### ❌ Erreur 1 : Oublier d'émettre l'événement

```python
# ❌ MAUVAIS
app_state['my_feature'] = True
return {'status': 'success'}
```

```python
# ✅ CORRECT
app_state['my_feature'] = True
await ws_manager.emit('my_feature_changed', {'my_feature': True})
return {'status': 'success'}
```

### ❌ Erreur 2 : Mettre à jour manuellement après commande

```javascript
// ❌ MAUVAIS
await sendCommandViaWS('update_config', {volume_multiplier: 1.5});
config.volume_multiplier = 1.5;  // ❌ Redondant !
```

```javascript
// ✅ CORRECT
await sendCommandViaWS('update_config', {volume_multiplier: 1.5});
// L'événement config_change met à jour automatiquement ✅
```

### ❌ Erreur 3 : Ne pas écouter l'événement dans le composant

```svelte
<!-- ❌ MAUVAIS: Pas de listener -->
<script>
    let myValue = 'initial';
</script>

<!-- ✅ CORRECT: Listener dans onMount -->
<script>
    import { onMount } from 'svelte';
    import { getWebSocket } from '$lib/utils/websocket';

    let myValue = 'initial';

    onMount(() => {
        const ws = getWebSocket();
        ws.on('my_value_changed', (data) => {
            myValue = data.value;  // ✅ Mise à jour automatique
        });
    });
</script>
```

### ❌ Erreur 4 : Utiliser fetch() au lieu de WebSocket

```javascript
// ❌ MAUVAIS: Utiliser REST pour mises à jour
async function update() {
    await fetch('/api/update', {method: 'POST', ...});
}
```

```javascript
// ✅ CORRECT: Utiliser WebSocket
async function update() {
    await sendCommandViaWS('update_feature', {...});
}
```

---

## 🔍 Vérification de Conformité

Avant de déployer une nouvelle fonctionnalité, vérifier **TOUS** ces points :

- [ ] **Backend émet un événement** quand l'état change
- [ ] **Backend a une commande WebSocket** pour modifier l'état
- [ ] **Frontend écoute l'événement** dans `onMount()` ou `setupWebSocketListeners()`
- [ ] **Frontend envoie la commande** via `sendCommandViaWS()` (pas fetch)
- [ ] **Store Svelte réactif** (si applicable)
- [ ] **Tous les clients** reçoivent la mise à jour simultanément
- [ ] **Aucun rafraîchissement manuel** requis
- [ ] **Test multi-onglets** : ouvrir 2 onglets, modifier dans l'un, vérifier l'autre se met à jour

---

## 📖 Documentation Audit

Référence : `docs/AUDIT_BIDIRECTIONNEL_COMPLET.md`

Pour chaque fonctionnalité, documenter dans l'audit :

| Champ | Backend → Frontend | Frontend → Backend | État | Notes |
|-------|-------------------|-------------------|------|-------|
| **my_feature** | ✅ Événement `my_feature_changed` | ✅ Commande `update_my_feature` | ✅ **BIDIRECTIONNEL** | Description |

---

## 🚀 Bénéfices

✅ **Expérience utilisateur fluide** : Mises à jour instantanées
✅ **Multi-utilisateurs** : Plusieurs clients synchronisés
✅ **Pas de bugs de cache** : Toujours l'état à jour
✅ **Scalabilité** : WebSocket plus performant que polling REST
✅ **Code maintenable** : Pattern clair et réutilisable

---

## 📝 Checklist Développeur

Avant chaque commit impliquant une fonctionnalité interactive :

```bash
# 1. Vérifier événement backend
grep "emit.*my_feature" main.py

# 2. Vérifier commande backend
grep "command == 'update_my_feature'" main.py

# 3. Vérifier listener frontend
grep "ws.on('my_feature" frontend/src

# 4. Vérifier commande frontend
grep "sendCommandViaWS.*my_feature" frontend/src

# 5. Tester multi-onglets
# Ouvrir localhost:3000 dans 2 onglets
# Modifier dans onglet 1
# Vérifier onglet 2 se met à jour automatiquement
```

---

**Créé le** : 10 Novembre 2025
**Auteur** : Claude (implémentation bidirectionnelle complète)
**Branche** : claude/fix-multiple-errors-011CUycbZyp8U3cuy4HYLNWy

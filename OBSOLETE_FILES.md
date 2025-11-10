# 📋 Fichiers Obsolètes - Migration WebSocket Natif

Ce document liste les fichiers obsolètes suite à la migration vers WebSocket natif et frontend Svelte.

## ⚠️ Status: À SUPPRIMER après validation

Ces fichiers utilisent Socket.IO (obsolète) et peuvent être supprimés en toute sécurité **après avoir confirmé que le frontend Svelte est déployé en production**.

---

## 🗑️ Fichiers Static JavaScript (Socket.IO)

### `static/js/dashboard_charts.js` (13 KB)
- **Raison**: Utilise Socket.IO (`const socket = io();`)
- **Remplacé par**: Frontend Svelte avec WebSocket natif
- **Impact suppression**: Casse `/dashboard/charts` si templates HTML encore utilisés

### `static/js/websocket_native.js` (11 KB)
- **Raison**: Wrapper JavaScript Socket.IO → WebSocket
- **Remplacé par**: `frontend/src/lib/utils/websocket-impl.ts` (TypeScript)
- **Impact suppression**: Casse `/` si template HTML index.html encore utilisé

---

## 📄 Templates HTML (Ancienne UI)

### `templates/index.html`
- **Raison**: Ancienne UI HTML avant migration Svelte
- **Remplacé par**: `frontend/src/routes/+page.svelte`
- **Endpoint**: GET `/` (main.py:1074)
- **Impact suppression**: Erreur 500 sur endpoint `/`

### `templates/dashboard_charts.html`
- **Raison**: Dashboard Chart.js + Socket.IO
- **Remplacé par**: Frontend Svelte
- **Endpoint**: GET `/dashboard/charts` (main.py:1090)
- **Impact suppression**: Erreur 500 sur endpoint `/dashboard/charts`

### `templates/backtest.html`
- **Raison**: Interface backtesting HTML
- **Remplacé par**: Frontend Svelte
- **Endpoint**: GET `/backtest` (main.py:1100)

### `templates/optimize.html`
- **Raison**: Interface ML optimization HTML
- **Remplacé par**: Frontend Svelte
- **Endpoint**: GET `/optimize` (main.py:1110)

### `templates/analytics.html`
- **Raison**: Interface analytics HTML
- **Remplacé par**: Frontend Svelte
- **Endpoint**: GET `/analytics` (main.py:1120)

### `templates/settings.html`
- **Raison**: Interface paramètres HTML
- **Remplacé par**: Frontend Svelte
- **Endpoint**: GET `/settings` (main.py:1130)

---

## ✅ Actions Recommandées

### Option 1: Suppression Immédiate (si Svelte en production)
```bash
# Supprimer fichiers static obsolètes
rm static/js/dashboard_charts.js
rm static/js/websocket_native.js

# Supprimer templates HTML obsolètes
rm templates/index.html
rm templates/dashboard_charts.html
rm templates/backtest.html
rm templates/optimize.html
rm templates/analytics.html
rm templates/settings.html

# Supprimer endpoints HTML dans main.py (lignes 1071-1133)
# Monter frontend Svelte build dans main.py:
#   app.mount("/", StaticFiles(directory="frontend/build", html=True), name="frontend")
```

### Option 2: Dépréciation Progressive (recommandé)
1. Ajouter warnings de dépréciation aux endpoints HTML
2. Rediriger `/` → frontend Svelte
3. Tester en production pendant 1 semaine
4. Supprimer les fichiers obsolètes

---

## 📊 Gain Espace Disque

- `static/js/dashboard_charts.js`: 13 KB
- `static/js/websocket_native.js`: 11 KB
- Templates HTML: ~50 KB

**Total: ~74 KB** (négligeable mais améliore maintenabilité)

---

## 🔄 Migration Status

| Composant | Status | Remplacé Par |
|-----------|--------|--------------|
| Socket.IO | ✅ Supprimé (commit 6566a12) | WebSocket natif |
| REST Polling | ✅ Supprimé (commit ca0c5f1) | WebSocket push |
| 10 Endpoints REST | ✅ Dépréciés | WebSocket commands |
| Fichiers Static | ⏳ À supprimer | websocket-impl.ts |
| Templates HTML | ⏳ À supprimer | Frontend Svelte |

---

**Dernière mise à jour**: 2025-11-10
**Branche**: claude/claude3-011CUycbZyp8U3cuy4HYLNWy

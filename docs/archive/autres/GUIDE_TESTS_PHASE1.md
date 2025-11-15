# 🧪 Guide de Tests Phase 1 - Étape par Étape

**Date**: 2025-11-08  
**Objectif**: Valider que tout fonctionne avant le déploiement

---

## ✅ Tests Automatiques Effectués

### Frontend
- ✅ **Build production réussi** : 1.76 MB total
- ✅ **build/index.js existe** : Serveur Node.js généré
- ✅ **Script 'start' présent** : Prêt pour PM2
- ✅ **Bundle size OK** : 207 KB (71 KB gzip) < 500 KB ✅

### Backend
- ✅ **Python 3.12 installé**
- ✅ **Dépendances critiques installées** : FastAPI, uvicorn, socketio
- ✅ **main.py syntaxe OK**
- ✅ **Scripts de validation présents**

### Configuration
- ✅ **.env.example existe**
- ✅ **Scripts de déploiement présents**

---

## 🧪 Tests Manuels à Effectuer

### Étape 1 : Test Backend (5 minutes)

#### 1.1 Démarrer le Backend

**Ouvrir un terminal** et exécuter :

```bash
cd "c:\Users\sebta\Documents\clone github\trade_cursor_py"
python main.py
```

**Ce que vous devriez voir** :
```
🚀 Trade Cursor v7.0 démarré (VERSION REFACTORISÉE)
🔥 FastAPI (async natif) + WebSocket
...
✅ URLs DISPONIBLES (Instance Port: 5000)
...
```

**✅ Succès si** :
- Pas d'erreur rouge
- Message "Trade Cursor v7.0 démarré" visible
- Backend écoute sur port 5000

**❌ Problème si** :
- Erreur d'import
- Port 5000 déjà utilisé
- Erreur de dépendance

---

#### 1.2 Tester l'API Backend

**Ouvrir un NOUVEAU terminal** (garder le backend running) :

```bash
# Test Health Check
curl http://localhost:5000/api/health
```

**Résultat attendu** :
```json
{"status":"healthy","timestamp":"2025-11-08T...","version":"7.0.0"}
```

**✅ Succès si** : Réponse JSON avec status "healthy"

**Tester autres endpoints** :
```bash
# Liste des sessions
curl http://localhost:5000/api/sessions

# Stats globales
curl http://localhost:5000/api/sessions/stats/global
```

**✅ Succès si** : Réponses JSON valides (même si vides)

---

### Étape 2 : Test Frontend Preview (5 minutes)

#### 2.1 Démarrer le Frontend en Preview

**Dans un NOUVEAU terminal** (garder backend running) :

```bash
cd "c:\Users\sebta\Documents\clone github\trade_cursor_py\frontend"
npm run preview
```

**Ce que vous devriez voir** :
```
  ➜  Local:   http://localhost:3000/
  ➜  press h + enter to show help
```

**✅ Succès si** :
- Pas d'erreur
- Serveur démarre sur port 3000
- Message "Local: http://localhost:3000/" visible

---

#### 2.2 Ouvrir dans le Navigateur

**Ouvrir votre navigateur** et aller sur :
```
http://localhost:3000
```

**✅ Vérifications visuelles** :
- [ ] Page se charge
- [ ] Interface s'affiche (dashboard, boutons)
- [ ] Pas d'erreurs rouges dans la console (F12)
- [ ] Thème dark/light fonctionne

**❌ Problèmes possibles** :
- Page blanche → Vérifier console (F12)
- Erreurs 404 → Vérifier que build est complet
- Erreurs WebSocket → Backend doit être running

---

### Étape 3 : Test WebSocket (2 minutes)

#### 3.1 Vérifier la Connexion

**Dans le navigateur** (F12 → Console) :

**Ce que vous devriez voir** :
- Message "🟢 Connected" ou "Socket.IO connected"
- Pas d'erreur de connexion

**Si vous voyez** :
- ❌ "🔴 Disconnected" → Backend pas running
- ❌ "Connection refused" → Port 5000 inaccessible
- ❌ "404" → Route `/socket.io` incorrecte

---

### Étape 4 : Test Fonctionnel Complet (10 minutes)

**Avec backend ET frontend running** :

#### 4.1 Test Scanner

1. **Cliquer sur "Start Scanner"** dans l'interface
2. **Vérifier** :
   - [ ] Scanner démarre (indicateur actif)
   - [ ] Logs apparaissent
   - [ ] Pas d'erreurs console

#### 4.2 Test Sessions

1. **Créer une nouvelle session** :
   - Cliquer "➕ New"
   - Remplir formulaire
   - Cliquer "Create"
2. **Vérifier** :
   - [ ] Session apparaît dans la liste
   - [ ] Boutons Start/Stop fonctionnent

#### 4.3 Test Charts

1. **Vérifier les graphiques** :
   - [ ] PnL Chart s'affiche
   - [ ] Win/Loss Chart s'affiche
   - [ ] Volume Chart s'affiche

#### 4.4 Test Export

1. **Cliquer sur "Export"** :
   - [ ] Options d'export s'affichent
   - [ ] CSV/JSON export fonctionnent (test si trades disponibles)

#### 4.5 Test Thème

1. **Toggle Dark/Light mode** :
   - [ ] Thème change
   - [ ] Préférence sauvegardée (recharger page)

---

## 📊 Checklist Complète

### Backend
- [ ] Backend démarre sans erreur
- [ ] Health check répond : `{"status":"healthy"}`
- [ ] API `/api/sessions` répond
- [ ] API `/api/sessions/stats/global` répond
- [ ] WebSocket écoute sur port 5000

### Frontend
- [ ] Build production réussi ✅ (déjà fait)
- [ ] Preview démarre sans erreur
- [ ] Application accessible sur http://localhost:3000
- [ ] Interface s'affiche correctement
- [ ] Pas d'erreurs console critiques

### Communication
- [ ] WebSocket se connecte (🟢 Connected)
- [ ] Données reçues du backend
- [ ] Actions frontend → backend fonctionnent

### Fonctionnalités
- [ ] Scanner démarre/stop
- [ ] Sessions créent/start/stop
- [ ] Charts s'affichent
- [ ] Export fonctionne
- [ ] Thème toggle fonctionne
- [ ] Notifications (si activées)

---

## 🚨 Résolution de Problèmes

### Backend ne démarre pas

**Erreur**: `ModuleNotFoundError`
```bash
# Solution: Installer dépendances
pip install -r requirements.txt
```

**Erreur**: `Port 5000 already in use`
```bash
# Solution: Changer le port
python main.py 5001
# Puis mettre à jour frontend pour utiliser port 5001
```

**Erreur**: `Import error`
```bash
# Vérifier que vous êtes dans le bon répertoire
cd "c:\Users\sebta\Documents\clone github\trade_cursor_py"
python main.py
```

---

### Frontend ne démarre pas

**Erreur**: `Port 3000 already in use`
```bash
# Solution: Utiliser autre port
npm run preview -- --port 3001
```

**Erreur**: `build/index.js not found`
```bash
# Solution: Rebuild
cd frontend
npm run build
npm run preview
```

---

### WebSocket ne se connecte pas

**Vérifier** :
1. Backend running sur port 5000
2. Frontend configuré pour port 5000
3. Pas de firewall bloquant
4. Console navigateur pour erreurs

**Test manuel WebSocket** :
```bash
# Dans un terminal
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Host: localhost:5000" \
  -H "Origin: http://localhost:3000" \
  http://localhost:5000/socket.io/?EIO=4&transport=websocket
```

---

## 📝 Notes de Test

**Date**: _______________

**Backend**:
- [ ] Démarré : Oui / Non
- [ ] Health check : OK / Erreur
- [ ] Port utilisé : 5000 / Autre

**Frontend**:
- [ ] Preview démarré : Oui / Non
- [ ] Accessible : Oui / Non
- [ ] Port utilisé : 3000 / Autre

**WebSocket**:
- [ ] Connecté : Oui / Non
- [ ] Erreurs : Aucune / Liste

**Fonctionnalités testées**:
- Scanner : OK / Erreur
- Sessions : OK / Erreur
- Charts : OK / Erreur
- Export : OK / Erreur

**Problèmes rencontrés**:
_________________________________
_________________________________

---

## ✅ Si Tous les Tests Passent

**Félicitations !** Vous êtes prêt pour la **Phase 2** :
- Créer le fichier `.env`
- Valider les variables d'environnement
- Préparer l'archive de déploiement

---

## ❌ Si Des Tests Échouent

**Ne paniquez pas !** Notez les erreurs et :
1. Vérifier les logs (console, terminal)
2. Consulter `ARCHITECTURE_EXPLAINED.md` pour comprendre
3. Vérifier que backend ET frontend tournent en même temps
4. Tester les endpoints individuellement

---

**Bon courage pour les tests ! 🚀**


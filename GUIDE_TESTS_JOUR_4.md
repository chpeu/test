# 🧪 GUIDE TESTS JOUR 4 - END-TO-END

**Date**: 2025-11-03  
**Version**: v7.0 FastAPI  
**Status**: ✅ Tests à effectuer

---

## 🎯 OBJECTIFS

Vérifier que le frontend utilise correctement les endpoints FastAPI et que tout fonctionne de bout en bout.

---

## ✅ CHECKLIST TESTS

### **Test 1: Scanner Top Pairs** ✅

**Action**:
1. Ouvrir http://localhost:5000
2. Cliquer "SCANNER LES PAIRES"

**Attendu**:
- ✅ SocketIO connecté
- ✅ Logs: "📡 Scanner Scalabilité: Récupération paires via FastAPI..."
- ✅ Logs: "⏳ Attente: Scan en cours..."
- ✅ Après ~50s: "📊 Top pairs mis à jour: X paires"
- ✅ Top 20 paires affichées

**Vérifier**:
- [ ] Top pairs récupérées via `/api/scanner/start`
- [ ] Top pairs affichées dans l'UI
- [ ] Pas d'erreur "Aucune paire scalable trouvée"

---

### **Test 2: Analyse avec FastAPI** ✅

**Action**:
1. Après avoir scanné les pairs
2. Cliquer "DÉMARRER LE SCANNER"
3. Attendre scanner loop (45s)

**Attendu**:
- ✅ Logs: "📡 Analyse FastAPI: BTC_USDT (confluence: false)"
- ✅ Logs: "📊 Prix source: BTC_USDT - WebSocket" (si WS connecté)
- ✅ Logs: "✓ 1m VALIDE" ou "✗ 1m REJETÉ"
- ✅ Logs: "✓ 5m VALIDE" ou "✗ 5m REJETÉ"
- ✅ Si setup trouvé: "✅ Setup trouvé: BTC_USDT - LONG"

**Vérifier**:
- [ ] Endpoint `/api/analyze/<symbol>` appelé
- [ ] Réponse contient `best`, `1m`, `5m`, `price_source`
- [ ] Prix source indiqué (WebSocket ou REST)
- [ ] Setup détecté si conditions remplies

---

### **Test 3: Prix WebSocket** ✅

**Action**:
1. Démarrer scanner
2. Attendre WebSocket démarrage
3. Vérifier les logs

**Attendu**:
- ✅ Logs: "WebSocket démarré: X symboles monitorés"
- ✅ `price_source: "WebSocket"` dans les analyses
- ✅ Latence prix = 0ms

**Vérifier**:
- [ ] WebSocket démarre automatiquement
- [ ] Prix récupérés via WebSocket
- [ ] Fallback REST si WebSocket down

---

### **Test 4: Ouverture Position** ✅

**Action**:
1. Attendre qu'un setup soit détecté
2. Vérifier ouverture position automatique

**Attendu**:
- ✅ Événement SocketIO `setup_detected` reçu
- ✅ Position ouverte via `/api/position/open`
- ✅ Logs: "✅ Position ouverte (FastAPI)"

**Vérifier**:
- [ ] Position créée dans PositionManager
- [ ] SocketIO émet `position_opened`
- [ ] UI affiche position active

---

### **Test 5: Check Position** ✅

**Action**:
1. Ouvrir une position
2. Attendre position check loop (2s)

**Attendu**:
- ✅ Logs: "🔄 Check Position: BTC_USDT - LONG"
- ✅ Événement SocketIO `position_update` toutes les 2s
- ✅ Prix mis à jour en temps réel
- ✅ PnL calculé

**Vérifier**:
- [ ] Endpoint `/api/position/check` appelé
- [ ] Prix récupéré via WebSocket (0ms)
- [ ] PnL affiché correctement
- [ ] TP/SL vérifiés

---

### **Test 6: Fermeture Position** ✅

**Action**:
1. Attendre que TP ou SL soit atteint
2. Vérifier fermeture automatique

**Attendu**:
- ✅ Événement SocketIO `position_closed` reçu
- ✅ Logs: "✅ Position fermée: TP/SL - PnL: X.XX USDT"
- ✅ Stats mises à jour (winrate, wins/losses)

**Vérifier**:
- [ ] Position fermée automatiquement
- [ ] PnL calculé correctement
- [ ] Stats mises à jour
- [ ] Scanner reprend après fermeture

---

### **Test 7: Scalability Refresh** ✅

**Action**:
1. Attendre scalability refresh (90s)

**Attendu**:
- ✅ Logs: "Scalability refresh: Rafraîchissement des top pairs..."
- ✅ Logs: "WebSocket mis à jour: X symboles"
- ✅ Événement SocketIO `top_pairs_update`

**Vérifier**:
- [ ] Top pairs rafraîchies
- [ ] WebSocket mis à jour
- [ ] UI mise à jour automatiquement

---

### **Test 8: Fallback** ✅

**Action**:
1. Arrêter le serveur FastAPI
2. Essayer d'analyser une paire

**Attendu**:
- ✅ Logs: "⚠️ Erreur analyse FastAPI"
- ✅ Logs: "🔄 Fallback: Utilisation méthode locale"
- ✅ Analyse continue avec ancienne méthode

**Vérifier**:
- [ ] Fallback fonctionne
- [ ] Pas de crash
- [ ] Analyse continue

---

## 📊 MÉTRIQUES À VÉRIFIER

| Métrique | Cible | Comment vérifier |
|----------|-------|-------------------|
| **Latence prix** | <50ms | Logs prix source |
| **Latence analyse** | <2s | Temps réponse `/api/analyze` |
| **Détection setup** | <45s | Temps jusqu'à premier setup |
| **Fiabilité** | >99% | Pas d'erreurs critiques |

---

## 🐛 BUGS À SURVEILLER

1. **Erreur SocketIO**: `translate_request` (déjà corrigé)
2. **Erreur 400**: Parsing JSON (déjà corrigé)
3. **Timing scan**: Pairs récupérées avant fin (déjà corrigé)
4. **WebSocket down**: Fallback REST fonctionne
5. **Position check**: Prix non disponible

---

## ✅ VALIDATION FINALE

- [ ] Tous les endpoints FastAPI fonctionnent
- [ ] WebSocket démarre automatiquement
- [ ] Prix récupérés via WebSocket
- [ ] Analyses fonctionnent
- [ ] Positions gérées automatiquement
- [ ] SocketIO fonctionne
- [ ] Fallback fonctionne
- [ ] Pas d'erreurs critiques

---

**Status**: ✅ **GUIDE CRÉÉ**

**Tests à effectuer manuellement** 🧪


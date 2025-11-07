# 🚀 LIMITES INSTANCES MULTIPLES

**Date**: Novembre 2024  
**Version**: v7.1

---

## 🎯 RÉPONSE RAPIDE

**Recommandation** : **2-3 instances maximum** pour éviter les bugs et le lag.

**Raisons principales** :
1. ✅ **API Rate Limits** : MEXC limite les appels API
2. ✅ **WebSocket** : 1 connexion par instance (limite serveur)
3. ✅ **Mémoire/CPU** : Chaque instance consomme ~200-300 MB RAM
4. ✅ **Ports** : Chaque instance nécessite un port différent

---

## 📊 ANALYSE DÉTAILLÉE

### **1. API Rate Limits MEXC**

**Limites officielles** (estimées) :
- **REST API** : ~10-20 requêtes/seconde par IP
- **WebSocket** : Pas de limite explicite (mais connexions limitées)

**Appels par instance** :
- **Scanner scalability** : ~20-30 paires × 1 appel = 20-30 appels (toutes les 90s)
- **Analyse setup** : ~9 paires × 2 timeframes × 1 appel OHLCV = 18 appels (toutes les 45s)
- **Orderbook check** : 1 appel par setup validé (cache 2s)
- **Spread check** : 1 appel par setup validé (cache 5s)
- **Position check** : 1 appel toutes les 0.1s (mais WebSocket prioritaire)

**Total par instance** :
- **Scan** : ~40-50 appels toutes les 45s = **~1-1.5 appels/seconde**
- **Position active** : ~10 appels/seconde (si WebSocket échoue)

**Avec 3 instances** :
- **~3-4.5 appels/seconde** (scanner)
- **~30 appels/seconde** (si toutes ont position active)
- ✅ **Sécurisé** si WebSocket fonctionne (réduit appels REST)

---

### **2. Connexions WebSocket**

**Limite théorique** :
- **1 connexion WebSocket par instance**
- **MEXC** : Pas de limite explicite, mais déconnexions possibles si trop de connexions

**Recommandation** :
- ✅ **2-3 instances** : Sécurisé
- ⚠️ **4-5 instances** : Risque de déconnexions WebSocket
- ❌ **6+ instances** : Déconnexions fréquentes, watchdog en surcharge

**Impact** :
- Si WebSocket déconnecté → Fallback REST (beaucoup plus d'appels API)
- Watchdog force reconnexion → Augmente la charge

---

### **3. Ressources Système**

#### **Mémoire (RAM)**

**Par instance** :
- **Base** : ~150-200 MB (Python + FastAPI + dépendances)
- **Cache** : ~50-100 MB (OHLCV, prix, orderbook)
- **WebSocket** : ~20-30 MB
- **Total** : **~200-300 MB par instance**

**Avec 3 instances** :
- **~600-900 MB** (sécurisé sur machine 4GB+)
- **~1.2-1.5 GB** (sécurisé sur machine 8GB+)

#### **CPU**

**Par instance** :
- **Idle** : ~1-2% CPU (boucles d'attente)
- **Scan actif** : ~5-10% CPU (analyse technique)
- **Position active** : ~2-5% CPU (check position)

**Avec 3 instances** :
- **Idle** : ~3-6% CPU
- **Scan actif** : ~15-30% CPU
- ✅ **Sécurisé** sur CPU moderne (4+ cores)

---

### **4. Locks et Protection**

**Locks internes** (par instance) :
- ✅ `position_lock` : Empêche positions multiples dans une instance
- ✅ `scanner_lock` : Empêche scans parallèles dans une instance

**Locks entre instances** :
- ❌ **Aucune protection** : Chaque instance est indépendante
- ⚠️ **Risque** : Plusieurs positions simultanées sur même paire (si plusieurs instances)

**Recommandation** :
- ✅ **Utiliser des paires différentes** par instance
- ✅ **Ou configurer des capital/taille différents** pour éviter sur-trading

---

### **5. Ports et Configuration**

**Configuration actuelle** :
- **Port par défaut** : 8000 (configurable)
- **SocketIO** : Même port que FastAPI

**Pour plusieurs instances** :
```bash
# Instance 1
uvicorn main:socketio_app --port 8000

# Instance 2
uvicorn main:socketio_app --port 8001

# Instance 3
uvicorn main:socketio_app --port 8002
```

**Frontend** :
- Chaque instance nécessite une URL différente :
  - `http://localhost:8000`
  - `http://localhost:8001`
  - `http://localhost:8002`

---

## 📈 RECOMMANDATIONS PAR NOMBRE D'INSTANCES

### **1 Instance** ✅ RECOMMANDÉ (Débutant)

**Avantages** :
- ✅ **Stabilité maximale** : Aucun conflit
- ✅ **Performances optimales** : Pas de partage ressources
- ✅ **Debug facile** : Logs clairs

**Configuration** :
- **Capital** : 100% sur cette instance
- **Paires** : Toutes les paires disponibles

**Ressources** :
- **RAM** : ~200-300 MB
- **CPU** : ~5-10% (scan actif)

---

### **2 Instances** ✅ RECOMMANDÉ (Intermédiaire)

**Avantages** :
- ✅ **Diversification** : 2 stratégies différentes
- ✅ **Réduction risque** : Capital divisé
- ✅ **Stabilité** : Peu de conflits

**Configuration recommandée** :
- **Instance 1** : Mode FIXE, Confluence activée (qualité)
- **Instance 2** : Mode ATR, Confluence désactivée (quantité)

**Répartition capital** :
- **Instance 1** : 50% capital (conservateur)
- **Instance 2** : 50% capital (agressif)

**Ressources** :
- **RAM** : ~400-600 MB
- **CPU** : ~10-20% (scan actif)

---

### **3 Instances** ⚠️ LIMITE (Avancé)

**Avantages** :
- ✅ **Diversification maximale** : 3 stratégies
- ✅ **Capital optimisé** : Répartition fine

**Risques** :
- ⚠️ **API Rate Limits** : Proche de la limite
- ⚠️ **WebSocket** : Risque de déconnexions
- ⚠️ **CPU/RAM** : Consommation élevée

**Configuration recommandée** :
- **Instance 1** : Mode FIXE, Confluence ON (qualité)
- **Instance 2** : Mode ATR, Confluence OFF (quantité)
- **Instance 3** : Mode ATR MULTI, Confluence ON (mix)

**Répartition capital** :
- **Instance 1** : 40% (conservateur)
- **Instance 2** : 35% (agressif)
- **Instance 3** : 25% (mix)

**Ressources** :
- **RAM** : ~600-900 MB
- **CPU** : ~15-30% (scan actif)

**Monitoring requis** :
- ✅ Vérifier logs d'erreurs API
- ✅ Surveiller déconnexions WebSocket
- ✅ Monitorer CPU/RAM

---

### **4+ Instances** ❌ DÉCONSEILLÉ

**Problèmes** :
- ❌ **API Rate Limits** : Dépassement probable
- ❌ **WebSocket** : Déconnexions fréquentes
- ❌ **CPU/RAM** : Surcharge système
- ❌ **Bugs** : Conflits entre instances
- ❌ **Lag** : Performances dégradées

**Alternative** :
- ✅ Utiliser **1 instance avec plusieurs stratégies** (changer config dynamiquement)
- ✅ Ou utiliser **serveurs différents** (IP différentes)

---

## 🔧 CONFIGURATION POUR INSTANCES MULTIPLES

### **Instance 1 (Port 8000)**

```bash
# Terminal 1
cd trade_cursor_py
uvicorn main:socketio_app --port 8000 --host 0.0.0.0
```

**Frontend** : `http://localhost:8000`

**Config recommandée** :
- Mode : FIXE
- Confluence : ON
- Capital : 50% (si 2 instances)

---

### **Instance 2 (Port 8001)**

```bash
# Terminal 2
cd trade_cursor_py
uvicorn main:socketio_app --port 8001 --host 0.0.0.0
```

**Frontend** : `http://localhost:8001`

**Config recommandée** :
- Mode : ATR
- Confluence : OFF
- Capital : 50% (si 2 instances)

---

### **Instance 3 (Port 8002)**

```bash
# Terminal 3
cd trade_cursor_py
uvicorn main:socketio_app --port 8002 --host 0.0.0.0
```

**Frontend** : `http://localhost:8002`

**Config recommandée** :
- Mode : ATR MULTI
- Confluence : ON
- Capital : 33% (si 3 instances)

---

## ⚠️ RISQUES ET LIMITATIONS

### **Risques Identifiés**

1. **API Rate Limits**
   - **Symptôme** : Erreurs 429 (Too Many Requests)
   - **Solution** : Réduire nombre d'instances ou augmenter délais

2. **WebSocket Déconnexions**
   - **Symptôme** : Prix figés, reconnexions fréquentes
   - **Solution** : Limiter à 2-3 instances max

3. **Conflits de Positions**
   - **Symptôme** : Plusieurs positions sur même paire
   - **Solution** : Utiliser paires différentes ou capital divisé

4. **Surcharge CPU/RAM**
   - **Symptôme** : Lag, freeze, crashes
   - **Solution** : Monitoring ressources, réduire instances

---

## 📊 TABLEAU RÉCAPITULATIF

| Instances | RAM | CPU | API Calls/s | WebSocket | Stabilité | Recommandation |
|------------|-----|-----|-------------|-----------|-----------|----------------|
| **1** | 200-300 MB | 5-10% | 1-1.5 | ✅ Stable | ✅ Excellente | ✅ **Recommandé** |
| **2** | 400-600 MB | 10-20% | 2-3 | ✅ Stable | ✅ Très bonne | ✅ **Recommandé** |
| **3** | 600-900 MB | 15-30% | 3-4.5 | ⚠️ Risque | ⚠️ Bonne | ⚠️ **Limite** |
| **4+** | 800+ MB | 30%+ | 4+ | ❌ Problèmes | ❌ Faible | ❌ **Déconseillé** |

---

## ✅ RECOMMANDATION FINALE

### **Pour Débutants**
- ✅ **1 instance** : Stabilité maximale, apprentissage

### **Pour Intermédiaires**
- ✅ **2 instances** : Diversification, stabilité maintenue

### **Pour Avancés**
- ⚠️ **3 instances** : Maximum recommandé, monitoring requis

### **Pour Experts**
- ❌ **4+ instances** : Déconseillé (utiliser serveurs différents ou IP différentes)

---

## 🔍 MONITORING

### **Vérifier les Limites**

1. **API Rate Limits** :
   - Chercher erreurs `429` dans les logs
   - Monitorer `ws_rest_fallback_count` (métriques)

2. **WebSocket** :
   - Chercher `⚠️ Watchdog: WebSocket silencieux`
   - Vérifier `ws_connected` dans métriques

3. **Ressources** :
   - `Task Manager` (Windows) ou `htop` (Linux)
   - Monitorer RAM et CPU

4. **Conflits** :
   - Vérifier logs pour positions multiples sur même paire
   - Surveiller `position_lock` warnings

---

## 🎯 CONCLUSION

**Réponse** : **2-3 instances maximum** pour éviter bugs et lag.

**Configuration optimale** :
- **2 instances** : Meilleur compromis stabilité/diversification
- **3 instances** : Maximum avec monitoring

**Alternative** : Utiliser 1 instance et changer la configuration dynamiquement selon les conditions de marché.

---

**Statut**: ✅ **VALIDÉ**  
**Version**: v7.1  
**Date**: Novembre 2024


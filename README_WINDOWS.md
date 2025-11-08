# 🪟 Trade Cursor v7.0 - Guide Windows

**Lancement facile sur Windows avec fichiers .bat**

---

## 🚀 Démarrage Rapide

### **Option 1: Deux fenêtres** (recommandé)

Double-cliquez sur:
```
start_svelte.bat
```

**Résultat:**
- ✅ Backend démarré (fenêtre minimisée)
- ✅ Frontend démarré (fenêtre visible)
- ✅ Navigateur ouvert automatiquement sur http://localhost:3000

**Pour arrêter:**
- Fermez les deux fenêtres
- OU double-cliquez sur `stop_svelte.bat`

---

### **Option 2: Une seule fenêtre**

Double-cliquez sur:
```
start_svelte_single_window.bat
```

**Résultat:**
- ✅ Backend + Frontend dans une seule fenêtre
- ⚠️ **Ctrl+C** arrête les deux serveurs

---

### **Arrêt propre**

Double-cliquez sur:
```
stop_svelte.bat
```

**Résultat:**
- ✅ Backend arrêté
- ✅ Frontend arrêté
- ✅ Ports 5000 et 3000 libérés

---

## 📋 Prérequis

### **1. Python 3.11+**

Télécharger: https://www.python.org/downloads/

**Installation:**
1. Cocher "Add Python to PATH"
2. Installer
3. Vérifier: `python --version`

### **2. Node.js 18+**

Télécharger: https://nodejs.org/en/download/

**Installation:**
1. Télécharger installeur Windows (.msi)
2. Installer (défaut OK)
3. Vérifier: `node -v`

### **3. Dépendances Python**

```bash
pip install -r requirements.txt
```

### **4. Dépendances Node.js**

Automatique au premier lancement, OU manuel:

```bash
cd frontend
npm install
```

---

## 🔧 Résolution de Problèmes

### ❌ "Node.js is not installed"

**Solution:**
1. Installer Node.js depuis https://nodejs.org
2. Redémarrer invite de commandes
3. Vérifier: `node -v`

---

### ❌ "Python is not installed"

**Solution:**
1. Installer Python depuis https://www.python.org
2. **Important**: Cocher "Add Python to PATH"
3. Redémarrer invite de commandes
4. Vérifier: `python --version`

---

### ❌ "npm install failed"

**Causes possibles:**
- Pas de connexion internet
- Proxy entreprise
- Antivirus bloque npm

**Solutions:**
1. Vérifier connexion internet
2. Si proxy, configurer:
   ```bash
   npm config set proxy http://proxy:port
   npm config set https-proxy http://proxy:port
   ```
3. Désactiver temporairement antivirus
4. Réessayer: `cd frontend && npm install`

---

### ❌ "Port 5000 already in use"

**Solution:**

Trouver et tuer le processus:
```bash
# Trouver PID
netstat -ano | findstr :5000

# Tuer processus (remplacer PID)
taskkill /F /PID <PID>
```

OU utiliser `stop_svelte.bat`

---

### ❌ "Port 3000 already in use"

**Solution:**

Même méthode que port 5000:
```bash
netstat -ano | findstr :3000
taskkill /F /PID <PID>
```

---

### ❌ Backend démarre mais frontend ne charge pas

**Diagnostic:**
1. Ouvrir http://localhost:5000 → Si OK, backend fonctionne
2. Ouvrir http://localhost:3000 → Si erreur, frontend problème

**Solutions:**
```bash
cd frontend
npm install
npm run dev
```

Vérifier logs dans fenêtre frontend.

---

### 🔴 Socket.IO Disconnected

**Symptôme:** Icône rouge en haut à droite

**Solutions:**
1. Backend pas lancé → Lancer `start_svelte.bat`
2. Port 5000 bloqué → Voir "Port already in use"
3. Firewall Windows → Autoriser Python et Node.js

**Test backend:**
```bash
curl http://localhost:5000/api/state
```

Si erreur → Backend pas lancé.

---

## 📂 Structure Fichiers

```
trade_cursor_py/
├── start_svelte.bat                 👈 Double-clic pour démarrer (2 fenêtres)
├── start_svelte_single_window.bat   👈 Double-clic pour démarrer (1 fenêtre)
├── stop_svelte.bat                  👈 Double-clic pour arrêter
├── start_svelte.sh                  (Linux/Mac)
├── main.py                          Backend FastAPI
├── frontend/
│   ├── src/                         Code Svelte
│   ├── package.json                 Dépendances Node.js
│   └── ...
└── README_WINDOWS.md                👈 Ce fichier
```

---

## 🎯 Utilisation Quotidienne

### **Démarrage**

1. Double-cliquer `start_svelte.bat`
2. Attendre 5-10 secondes
3. Navigateur s'ouvre sur http://localhost:3000

### **Trading**

1. Cliquer "Start Scan"
2. Voir top pairs apparaître
3. Position s'ouvre automatiquement (si setup trouvé)
4. Suivre PnL en temps réel

### **Arrêt**

- Fermer fenêtres backend/frontend
- OU double-cliquer `stop_svelte.bat`

---

## 🔐 Firewall Windows

Si Windows Defender demande autorisation:

**Pour Python:**
- ✅ Autoriser réseaux privés
- ✅ Autoriser réseaux publics (optionnel)

**Pour Node.js:**
- ✅ Autoriser réseaux privés
- ✅ Autoriser réseaux publics (optionnel)

---

## 📱 Accès depuis autre PC (même réseau)

### 1. Trouver IP de votre PC

```bash
ipconfig
```

Chercher "IPv4 Address" (ex: 192.168.1.100)

### 2. Autoriser dans Firewall

```bash
# PowerShell (Administrateur)
netsh advfirewall firewall add rule name="Trade Cursor Backend" dir=in action=allow protocol=TCP localport=5000
netsh advfirewall firewall add rule name="Trade Cursor Frontend" dir=in action=allow protocol=TCP localport=3000
```

### 3. Accéder depuis autre device

Sur autre PC/téléphone (même WiFi):

```
http://192.168.1.100:3000
```

---

## 🚀 Mode Production

### Build frontend

```bash
cd frontend
npm run build
```

### Lancer en production

```bash
# Backend
python main.py

# Frontend (production)
cd frontend
node build/index.js
```

### Service Windows (optionnel)

Utiliser **NSSM** (Non-Sucking Service Manager):

1. Télécharger: https://nssm.cc/download
2. Installer comme service:

```bash
nssm install TradeCursorBackend "C:\Python311\python.exe" "C:\path\to\trade_cursor_py\main.py"
nssm install TradeCursorFrontend "C:\Program Files\nodejs\node.exe" "C:\path\to\trade_cursor_py\frontend\build\index.js"

nssm start TradeCursorBackend
nssm start TradeCursorFrontend
```

---

## 📊 Performance Windows

### Recommandations

**Minimum:**
- CPU: 4 cores
- RAM: 8 GB
- SSD: Oui

**Optimal:**
- CPU: 8+ cores
- RAM: 16+ GB
- SSD: NVMe

### Task Manager

Surveiller performance:
- `Ctrl+Shift+Esc` → Performance
- Python: ~100-200 MB RAM
- Node.js: ~50-100 MB RAM

---

## 🔄 Mise à jour

### Git pull

```bash
cd C:\path\to\trade_cursor_py
git pull origin main
```

### Dépendances Python

```bash
pip install -r requirements.txt --upgrade
```

### Dépendances Node.js

```bash
cd frontend
npm install
```

---

## 📞 Support

### Problème persistant?

1. Vérifier logs dans fenêtres backend/frontend
2. Copier messages d'erreur
3. Créer issue GitHub avec:
   - Version Windows
   - Version Python (`python --version`)
   - Version Node.js (`node -v`)
   - Logs d'erreur
   - Steps to reproduce

---

## 🎉 C'est parti!

Double-cliquez sur `start_svelte.bat` et profitez de Trade Cursor! 🚀

**Accès:**
- 📍 Frontend: http://localhost:3000
- 📍 Backend: http://localhost:5000
- 📍 API: http://localhost:5000/api/state

**Bon trading! 💰**

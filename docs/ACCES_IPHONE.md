# 📱 Guide d'Accès depuis iPhone

## Configuration pour accéder au bot depuis votre iPhone

### ✅ Port 5000 (Backend FastAPI)

Le backend est déjà configuré pour écouter sur `0.0.0.0`, donc accessible depuis l'extérieur.

**URL d'accès :**
- **Local (même réseau WiFi)** : `http://VOTRE_IP_LOCALE:5000`
- **Tailscale** : `http://VOTRE_IP_TAILSCALE:5000`

### ✅ Port 3000 (Frontend SvelteKit - Dev)

Le frontend SvelteKit doit être configuré pour écouter sur `0.0.0.0` au lieu de `127.0.0.1`.

**Configuration effectuée :**
- ✅ `vite.config.js` modifié pour `host: '0.0.0.0'`
- ✅ Script firewall mis à jour pour le port 3000

**URL d'accès :**
- **Local (même réseau WiFi)** : `http://VOTRE_IP_LOCALE:3000`
- **Tailscale** : `http://VOTRE_IP_TAILSCALE:3000`

## 🔧 Étapes de Configuration

### 1. Configurer le Firewall Windows

Exécutez le script PowerShell en tant qu'administrateur :

```powershell
cd "c:\Users\sebta\Documents\clone github\trade_cursor_py"
.\setup_firewall.ps1
```

Le script configure automatiquement les ports 5000 et 3000.

### 2. Démarrer le Backend

```bash
cd "c:\Users\sebta\Documents\clone github\trade_cursor_py"
python main.py
```

Le backend affichera vos adresses IP :
```
🌐 Accès local: http://192.168.x.x:5000
🌐 Accès Tailscale: http://100.x.x.x:5000
```

### 3. Démarrer le Frontend (Mode Dev)

Dans un **nouveau terminal** :

```bash
cd "c:\Users\sebta\Documents\clone github\trade_cursor_py\frontend"
npm run dev
```

Le frontend devrait afficher :
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: http://192.168.x.x:3000/
  ➜  Network: http://100.x.x.x:3000/  (Tailscale)
```

### 4. Accéder depuis iPhone

**Option A : Via Tailscale (Recommandé)**
1. Assurez-vous que Tailscale est actif sur iPhone et PC
2. Ouvrez Safari ou Chrome sur iPhone
3. Accédez à : `http://VOTRE_IP_TAILSCALE:3000`

**Option B : Via réseau local**
1. Connectez iPhone et PC au même WiFi
2. Ouvrez Safari ou Chrome sur iPhone
3. Accédez à : `http://VOTRE_IP_LOCALE:3000`

## 🔍 Vérification

### Vérifier que le port 3000 est accessible

Sur votre PC Windows, testez :

```powershell
# Vérifier que le serveur écoute sur 0.0.0.0
netstat -an | findstr ":3000"
```

Vous devriez voir :
```
TCP    0.0.0.0:3000           0.0.0.0:0              LISTENING
```

Si vous voyez `127.0.0.1:3000` au lieu de `0.0.0.0:3000`, le serveur n'est pas accessible depuis l'extérieur.

### Vérifier le firewall

```powershell
Get-NetFirewallRule -DisplayName "TradeCursor_Port_3000" | Format-List
```

## ⚠️ Problèmes Courants

### Problème : "Connection refused" sur iPhone

**Solutions :**
1. Vérifiez que le frontend est bien démarré (`npm run dev`)
2. Vérifiez que `vite.config.js` contient `host: '0.0.0.0'`
3. Vérifiez que le firewall autorise le port 3000
4. Redémarrez le serveur frontend après modification de `vite.config.js`

### Problème : Page blanche sur iPhone

**Solutions :**
1. Vérifiez la console du navigateur (si possible)
2. Vérifiez que le backend (port 5000) est accessible
3. Vérifiez que les proxies dans `vite.config.js` pointent vers `localhost:5000` (correct pour le serveur dev)

### Problème : Les API ne fonctionnent pas

**Note importante :** En mode dev, Vite proxy les requêtes `/api` et `/socket.io` vers `localhost:5000`. Cela fonctionne car le proxy s'exécute sur le PC, pas sur l'iPhone.

Si vous avez des problèmes :
1. Vérifiez que le backend est bien démarré sur le port 5000
2. Vérifiez que les proxies dans `vite.config.js` sont corrects

## 🚀 Alternative : Build Production

Si vous préférez ne pas utiliser le serveur dev, vous pouvez build le frontend et le servir via FastAPI :

```bash
cd frontend
npm run build
```

Puis le backend FastAPI servira automatiquement le build depuis `frontend/build` (voir `main.py`).

Dans ce cas, vous n'avez besoin que du port 5000.

## 📝 Notes

- **Mode Dev (port 3000)** : Hot reload, meilleur pour le développement
- **Mode Production (port 5000)** : Build optimisé, servit par FastAPI
- **Tailscale** : Recommandé pour l'accès sécurisé depuis l'extérieur
- **Réseau local** : Plus rapide, mais nécessite d'être sur le même WiFi

---

**Dernière mise à jour :** 2024-01-01



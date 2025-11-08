# ⚡ Quick Start - Frontend Svelte

**Démarrage rapide en 3 commandes**

---

## 🚀 Option 1: Script automatique (recommandé)

```bash
cd /home/user/trade_cursor_py
./start_svelte.sh
```

Ouvrir http://localhost:3000

---

## 🔧 Option 2: Manuel

### Terminal 1: Backend
```bash
cd /home/user/trade_cursor_py
python main.py
```

### Terminal 2: Frontend
```bash
cd /home/user/trade_cursor_py/frontend
npm install  # Première fois seulement
npm run dev
```

Ouvrir http://localhost:3000

---

## ✅ Vérifications

### 1. Socket.IO connecté
En haut à droite: 🟢 Connected

### 2. Scanner fonctionne
Cliquer "Start Scan" → Logs apparaissent

### 3. Position temps réel
Ouvrir position → PnL s'actualise

---

## 📦 Build Production

```bash
cd frontend
npm run build
node build/index.js
```

Accéder à http://localhost:3000

---

## 🐛 Problèmes?

### Socket.IO 🔴 Disconnected
→ Backend pas lancé, faire `python main.py`

### npm install fail
→ Node.js < 18, installer version 18+

### Port 3000 occupé
→ `killall node` puis relancer

---

## 📚 Documentation complète

- [README.md](README.md) - Documentation complète
- [MIGRATION_SVELTE.md](../MIGRATION_SVELTE.md) - Guide migration
- [Svelte Docs](https://svelte.dev/docs) - Documentation officielle

---

**Prêt à trader! 🚀**

# 🏗️ Architecture Trade Cursor v7.0 - Explications

## 📊 Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────┐
│                    UTILISATEUR                          │
│              (Navigateur Web / Mobile)                   │
└────────────────────┬──────────────────────────────────┘
                     │
                     │ HTTP/HTTPS + WebSocket
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌───────────────┐         ┌───────────────┐
│   FRONTEND    │         │    BACKEND    │
│  (SvelteKit)  │◄────────┤   (FastAPI)   │
│   Port 3000   │ WebSocket│   Port 5000   │
└───────────────┘         └───────────────┘
```

---

## 🎨 FRONTEND (Port 3000)

### Qu'est-ce que c'est ?
**L'interface utilisateur** - Ce que vous voyez dans votre navigateur.

### Technologies
- **SvelteKit** : Framework JavaScript moderne
- **Socket.IO Client** : Communication temps réel avec le backend
- **Chart.js** : Graphiques et visualisations
- **HTML/CSS/JavaScript** : Rendu dans le navigateur

### Rôle
1. **Afficher l'interface** : Dashboard, charts, boutons, formulaires
2. **Interagir avec l'utilisateur** : Clics, saisies, actions
3. **Recevoir les données** : Via WebSocket et API REST
4. **Afficher les résultats** : Trades, statistiques, graphiques

### Exemples concrets
- ✅ Le bouton "Start Scanner" → Frontend
- ✅ Les graphiques de PnL → Frontend
- ✅ Le tableau des trades → Frontend
- ✅ Le thème Dark/Light → Frontend

### Où ça tourne ?
- **Développement** : `npm run dev` → http://localhost:3000
- **Production** : Serveur Node.js → Port 3000

---

## ⚙️ BACKEND (Port 5000)

### Qu'est-ce que c'est ?
**Le moteur de l'application** - La logique métier et les données.

### Technologies
- **FastAPI** : Framework Python pour API REST
- **Python-SocketIO** : Communication WebSocket
- **CCXT** : Connexion aux exchanges (MEXC)
- **SQLite** : Base de données des trades

### Rôle
1. **Scanner les marchés** : Analyser les paires de trading
2. **Gérer les positions** : Ouvrir/fermer des trades
3. **Communiquer avec MEXC** : Récupérer prix, passer ordres
4. **Stocker les données** : Sauvegarder trades, statistiques
5. **Envoyer les données** : Via WebSocket au frontend

### Exemples concrets
- ✅ Détecter un setup de trading → Backend
- ✅ Calculer les indicateurs techniques → Backend
- ✅ Ouvrir une position → Backend
- ✅ Sauvegarder un trade → Backend

### Où ça tourne ?
- **Développement** : `python main.py` → http://localhost:5000
- **Production** : PM2 + Python → Port 5000

---

## 🔌 Port 3000 vs Port 5000

### Port 3000 - FRONTEND
```
http://localhost:3000
```

**C'est quoi ?**
- L'interface web que vous voyez
- L'application SvelteKit
- Ce qui s'affiche dans votre navigateur

**Qui l'utilise ?**
- Vous (utilisateur) via le navigateur
- Le frontend communique avec le backend

**Exemple** :
```
Vous → Navigateur → http://localhost:3000
                    ↓
              Interface SvelteKit
              (Boutons, Charts, etc.)
```

---

### Port 5000 - BACKEND
```
http://localhost:5000
```

**C'est quoi ?**
- L'API REST (endpoints `/api/*`)
- Le serveur WebSocket (`/socket.io`)
- La logique métier Python

**Qui l'utilise ?**
- Le frontend (pour récupérer les données)
- Les scripts Python (pour le trading)

**Exemple** :
```
Frontend → http://localhost:5000/api/sessions
           ↓
      Backend FastAPI
      (Retourne les sessions)
```

---

## 🔄 Communication Frontend ↔ Backend

### 1. API REST (HTTP)
```
Frontend (3000)  →  GET /api/sessions  →  Backend (5000)
                   ←  JSON Response    ←
```

**Utilisation** :
- Récupérer la liste des sessions
- Obtenir les statistiques
- Exporter les trades

### 2. WebSocket (Socket.IO)
```
Frontend (3000)  ←→  /socket.io  ←→  Backend (5000)
                  (Temps réel)
```

**Utilisation** :
- Scanner en temps réel
- Mises à jour des prix
- Notifications de trades
- Changements d'état

---

## 🎯 Analogie Simple

**Frontend (3000)** = **Tableau de bord de voiture**
- Volant, pédales, écran
- Ce que vous voyez et utilisez
- Interface utilisateur

**Backend (5000)** = **Moteur de la voiture**
- Moteur, transmission, calculateur
- Ce qui fait fonctionner l'application
- Logique métier

**Communication** = **Câbles et capteurs**
- Le frontend envoie des commandes
- Le backend exécute et renvoie les résultats

---

## 📱 En Production (VM Proxmox)

### Architecture
```
Internet
   │
   ▼
Nginx (Port 80/443)
   │
   ├─→ Frontend (Port 3000) → http://votre-domaine/
   │
   └─→ Backend (Port 5000)  → http://votre-domaine/api/*
                              http://votre-domaine/socket.io
```

**Nginx** fait le reverse proxy :
- `/` → Frontend (port 3000)
- `/api/*` → Backend (port 5000)
- `/socket.io` → Backend WebSocket (port 5000)

L'utilisateur ne voit qu'un seul port (80 ou 443), Nginx route vers les bons services.

---

## 🔍 Résumé

| Aspect | Frontend (3000) | Backend (5000) |
|--------|----------------|----------------|
| **Langage** | JavaScript (Svelte) | Python (FastAPI) |
| **Rôle** | Interface utilisateur | Logique métier |
| **Visible** | Oui (navigateur) | Non (serveur) |
| **Communication** | WebSocket + REST | WebSocket + REST |
| **Données** | Affiche | Traite et stocke |
| **Exemple** | Bouton "Start" | Scanner qui analyse |

---

**En bref** :
- **Port 3000** = Ce que vous voyez (interface)
- **Port 5000** = Ce qui fait le travail (moteur)

Les deux doivent tourner en même temps pour que l'application fonctionne !


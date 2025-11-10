# 🚀 Plan de Mise en Production CORRIGÉ - Trade Cursor v7.0

**Version**: Corrigée après analyse détaillée  
**Date**: 2025-11-08  
**Dépôt**: https://github.com/chpeu/trade_cursor_py

---

## 📋 Checklist Pré-Production

### 1. Installation des Dépendances Manquantes

```bash
cd frontend

# Dépendances de base (déjà installées normalement)
npm install

# Vérifier que Chart.js est installé
npm list chart.js

# Si manquant:
npm install chart.js date-fns

# Optionnel - Pour mobile (si vous voulez builder les apps)
npm install @capacitor/core @capacitor/cli
npm install @capacitor/android @capacitor/ios
npm install @capacitor/push-notifications @capacitor/local-notifications

# Optionnel - Pour desktop (si vous voulez builder l'app)
npm install --save-dev @tauri-apps/cli
npm install @tauri-apps/api
```

### 2. Tests Locaux

```bash
# Terminal 1: Backend
python main.py

# Terminal 2: Frontend dev
cd frontend
npm run dev

# Ouvrir http://localhost:3000
```

**Tests à effectuer**:
- [ ] Connexion WebSocket établie (🟢 Connected)
- [ ] Scanner démarre/stop
- [ ] Position ouverte/fermée (simulé)
- [ ] Charts s'affichent et se mettent à jour
- [ ] Notifications fonctionnent (cliquer "Activer")
- [ ] Dark/Light mode toggle
- [ ] Settings sauvegardées (localStorage)
- [ ] Export trades CSV/JSON
- [ ] Multi-sessions: créer/start/stop
- [ ] Responsive mobile (DevTools)

### 3. Build Production Frontend

```bash
cd frontend

# Build pour production
npm run build

# Test du build
npm run preview

# Vérifier http://localhost:3000
```

**Vérifications**:
- [ ] Pas d'erreurs de build
- [ ] Bundle size raisonnable (<500KB)
- [ ] Preview fonctionne correctement
- [ ] WebSocket se connecte à localhost:5000

---

## 🖥️ Déploiement Production

### Option 1: VM Proxmox (Recommandé)

#### A. Prérequis VM

```bash
# Sur la VM Proxmox
sudo apt update
sudo apt upgrade -y

# Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip -y

# Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# PM2 (Process Manager)
sudo npm install -g pm2

# Nginx (Reverse Proxy)
sudo apt install nginx -y
```

#### B. Déployer le Code

```bash
# Sur votre machine locale
# Créer archive (exclure node_modules, __pycache__, etc.)
tar -czf trade-cursor-v7.tar.gz \
  --exclude='frontend/node_modules' \
  --exclude='frontend/build' \
  --exclude='__pycache__' \
  --exclude='.git' \
  --exclude='*.pyc' \
  --exclude='venv' \
  --exclude='.env' \
  .

# Transférer vers VM
scp trade-cursor-v7.tar.gz user@proxmox-vm:/home/user/

# Sur la VM
ssh user@proxmox-vm
cd /home/user
tar -xzf trade-cursor-v7.tar.gz
cd trade_cursor_py
```

#### C. Setup Backend

```bash
# Créer virtualenv
python3.11 -m venv venv
source venv/bin/activate

# Installer dépendances
pip install -r requirements.txt

# Créer fichier .env (copier depuis .env.example)
cp .env.example .env
nano .env  # Éditer avec vos valeurs

# Valider variables d'environnement
python scripts/validate_env.py

# Tester backend
python main.py
# Ctrl+C pour arrêter

# Créer service PM2
pm2 start main.py --name trade-cursor-backend --interpreter python3
pm2 save
pm2 startup  # Suivre les instructions
```

#### D. Setup Frontend

```bash
cd frontend

# Installer dépendances
npm install

# Build production
npm run build

# Vérifier que build/index.js existe
ls -la build/

# Démarrer avec PM2 (CORRIGÉ)
pm2 start npm --name trade-cursor-frontend -- start

# OU alternative si npm ne fonctionne pas:
# cd build
# pm2 start index.js --name trade-cursor-frontend --node-args="--port 3000"

pm2 save
```

**Note**: Assurez-vous que `package.json` contient le script `start`:
```json
{
  "scripts": {
    "start": "node build/index.js"
  }
}
```

#### E. Configuration Nginx (CORRIGÉE)

```bash
sudo nano /etc/nginx/sites-available/trade-cursor
```

**Contenu (CORRIGÉ)**:
```nginx
# HTTP → HTTPS redirect
server {
    listen 80;
    server_name trade-cursor.local;  # Remplacer par votre domaine
    return 301 https://$server_name$request_uri;
}

# HTTPS
server {
    listen 443 ssl http2;
    server_name trade-cursor.local;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/trade-cursor.local/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/trade-cursor.local/privkey.pem;

    # SSL config
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Frontend SvelteKit (port 3000)
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API (port 5000)
    location /api {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket Socket.IO (CORRIGÉ - port 5000)
    location /socket.io {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        proxy_connect_timeout 60;
        proxy_buffering off;
    }

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1000;
}
```

**Activer le site**:
```bash
sudo ln -s /etc/nginx/sites-available/trade-cursor /etc/nginx/sites-enabled/
sudo nginx -t  # Tester config
sudo systemctl reload nginx
```

#### F. SSL avec Let's Encrypt (Optionnel)

```bash
# Installer Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtenir certificat
sudo certbot --nginx -d trade-cursor.local

# Auto-renewal
sudo certbot renew --dry-run
```

#### G. Firewall

```bash
# UFW
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

---

## 🔒 Sécurité Production

### 1. Variables d'Environnement

Créer `.env` (NE JAMAIS COMMIT):
```bash
# API Keys (ne PAS commit)
MEXC_API_KEY=your_api_key_here
MEXC_SECRET_KEY=your_secret_key_here

# Database
DATABASE_URL=sqlite:///data/trades.db

# FastAPI Secret (CORRIGÉ - était "Flask Secret")
SECRET_KEY=random_secret_key_here_generate_with_openssl_rand_hex_32

# Environment
ENVIRONMENT=production
DEBUG=false
```

**Générer SECRET_KEY**:
```bash
openssl rand -hex 32
```

Charger dans `main.py`:
```python
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv('MEXC_API_KEY')
secret_key = os.getenv('MEXC_SECRET_KEY')
secret_key_app = os.getenv('SECRET_KEY')
```

### 2. Rate Limiting (CORRIGÉ)

Installer (déjà dans requirements.txt):
```bash
pip install slowapi
```

Dans `main.py` (CORRIGÉ):
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

# Initialisation
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Utilisation (request DOIT être le premier paramètre)
@app.get("/api/sessions")
@limiter.limit("10/minute")
def get_sessions(request: Request):  # Pas async
    # Votre code ici
    return {"sessions": []}
```

### 3. CORS Production (CORRIGÉ)

```python
from fastapi.middleware.cors import CORSMiddleware
import os

# Configuration CORS
allowed_origins = [
    "https://trade-cursor.local",  # Production
    "http://localhost:3000",        # Dev local
]

# Ajouter réseau local si dev
if os.getenv("ENVIRONMENT") == "development":
    allowed_origins.append("http://192.168.1.0/24")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)
```

---

## 🔍 Monitoring & Logs

### PM2 Monitoring

```bash
# Voir processus
pm2 list

# Logs en temps réel
pm2 logs

# Logs backend
pm2 logs trade-cursor-backend

# Logs frontend
pm2 logs trade-cursor-frontend

# Monitoring dashboard
pm2 monit

# Web dashboard (optionnel)
pm2 plus  # Créer compte sur pm2.io
```

### Health Check (NOUVEAU)

```bash
# Vérifier santé backend
curl http://localhost:5000/api/health

# Réponse attendue:
# {"status":"healthy","timestamp":"2025-11-08T...","version":"7.0.0"}
```

### Logs Nginx

```bash
# Access logs
sudo tail -f /var/log/nginx/access.log

# Error logs
sudo tail -f /var/log/nginx/error.log
```

### Logs Application

```bash
# Backend logs (si configuré)
tail -f logs/trade_cursor.log

# Rotation des logs (logrotate)
sudo nano /etc/logrotate.d/trade-cursor
```

```
/home/user/trade_cursor_py/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

---

## ✅ Checklist Finale

### Avant Mise en Production
- [ ] Tous les tests passent
- [ ] Build frontend sans erreurs
- [ ] Variables d'environnement configurées et validées
- [ ] SSL/HTTPS configuré
- [ ] Firewall configuré
- [ ] PM2 auto-start configuré
- [ ] Nginx reverse proxy testé
- [ ] WebSocket testé (wss://)
- [ ] Health check fonctionne
- [ ] Logs rotation configurée
- [ ] Backup strategy définie
- [ ] Monitoring en place

### Post-Déploiement
- [ ] WebSocket fonctionne (wss://)
- [ ] Notifications push fonctionnent
- [ ] Multi-sessions fonctionnent
- [ ] Export trades fonctionne
- [ ] Accès mobile testé
- [ ] Performance testée (load testing)
- [ ] Documentation utilisateur

---

## 🚨 Troubleshooting

### WebSocket ne se connecte pas
```bash
# Vérifier que backend écoute sur 0.0.0.0
# Dans main.py: uvicorn.run(socketio_app, host='0.0.0.0', port=5000)

# Vérifier firewall
sudo ufw status

# Vérifier Nginx config WebSocket
sudo nginx -t
sudo tail -f /var/log/nginx/error.log

# Tester WebSocket directement
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Host: localhost:5000" \
  -H "Origin: http://localhost:3000" \
  http://localhost:5000/socket.io/?EIO=4&transport=websocket
```

### PM2 process crash
```bash
# Voir erreurs
pm2 logs trade-cursor-backend --err
pm2 logs trade-cursor-frontend --err

# Restart
pm2 restart trade-cursor-backend
pm2 restart trade-cursor-frontend

# Delete et recréer
pm2 delete trade-cursor-backend
pm2 delete trade-cursor-frontend
pm2 start main.py --name trade-cursor-backend --interpreter python3
cd frontend
pm2 start npm --name trade-cursor-frontend -- start
```

### Build frontend échoue
```bash
# Nettoyer cache
cd frontend
rm -rf node_modules package-lock.json .svelte-kit build
npm install
npm run build
```

### Frontend ne démarre pas avec PM2
```bash
# Vérifier que build/index.js existe
cd frontend
ls -la build/

# Vérifier script start dans package.json
cat package.json | grep '"start"'

# Tester manuellement
node build/index.js

# Si erreur, vérifier logs
pm2 logs trade-cursor-frontend --lines 50
```

---

## 📊 Performance Production

### Optimisations Backend
- Utiliser Gunicorn avec workers multiples (si nécessaire)
- Redis pour cache sessions (futur)
- PostgreSQL au lieu de SQLite (>1000 trades/jour)

### Optimisations Frontend
- Activer Brotli compression (déjà dans build avec precompress: true)
- CDN pour assets statiques (futur)
- Service Workers pour cache offline (futur)

---

## 🎯 Maintenance

### Quotidienne
- Vérifier `pm2 list` (processus running)
- Vérifier logs erreurs
- Vérifier health check: `curl http://localhost:5000/api/health`

### Hebdomadaire
- Backup database
- Vérifier disk space
- Review logs pour patterns

### Mensuelle
- Update dépendances npm
- Update dépendances pip
- Review sécurité

---

## 📞 Support

En cas de problème:
1. Vérifier logs PM2/Nginx
2. Tester localhost:5000 (backend direct)
3. Tester localhost:3000 (frontend direct)
4. Vérifier health check endpoint
5. Vérifier network/firewall
6. Vérifier WebSocket connection

---

**Temps estimé déploiement complet**: 2-4 heures (première fois)  
**Temps estimé déploiement update**: 15-30 minutes

🎉 Après ce setup, votre Trade Cursor v7.0 sera en production et accessible depuis n'importe quel device!

---

## 📝 Notes de Version

**Corrections apportées**:
- ✅ Configuration PM2 frontend corrigée
- ✅ Versions package.json alignées
- ✅ Configuration Nginx WebSocket améliorée
- ✅ Code rate limiting corrigé
- ✅ Configuration CORS complétée
- ✅ Health check endpoint ajouté
- ✅ Validation variables d'environnement ajoutée

**Architecture confirmée**:
- Backend: FastAPI + python-socketio
- Frontend: SvelteKit + socket.io-client
- WebSocket: Socket.IO protocol via `/socket.io`


# 🚀 Plan de Mise en Production - Trade Cursor v7.0

Guide complet pour déployer en production.

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

### Option 1: VM Proxmox (Recommandé pour vous)

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

# Démarrer avec PM2 (Node.js adapter)
pm2 start build/index.js --name trade-cursor-frontend
pm2 save
```

#### E. Configuration Nginx

```bash
sudo nano /etc/nginx/sites-available/trade-cursor
```

**Contenu**:
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
    }

    # WebSocket (port 5000)
    location /socket.io {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
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

### Option 2: Docker (Alternative)

Créer `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build: .
    container_name: trade-cursor-backend
    ports:
      - "5000:5000"
    environment:
      - PYTHONUNBUFFERED=1
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped

  frontend:
    build: ./frontend
    container_name: trade-cursor-frontend
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
    depends_on:
      - backend
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: trade-cursor-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
      - frontend
    restart: unless-stopped
```

---

## 📱 Accès Distant

### 1. Depuis PC sur Réseau Local

```
http://192.168.1.X:3000  (IP de la VM Proxmox)
```

### 2. Depuis iPhone/Android

#### Option A: Même réseau WiFi
```
http://192.168.1.X:3000
```

Ajouter à l'écran d'accueil:
- Safari (iOS): Partager > Sur l'écran d'accueil
- Chrome (Android): Menu > Ajouter à l'écran d'accueil

#### Option B: VPN Tailscale (Recommandé)

```bash
# Sur la VM Proxmox
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Sur iPhone/Android
# Installer Tailscale app
# Se connecter avec même compte
# Accéder via: http://100.x.x.x:3000
```

#### Option C: Tunnel Cloudflare (Public)

```bash
# Sur la VM
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
./cloudflared tunnel --url http://localhost:3000

# Obtenir URL publique: https://random.trycloudflare.com
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

## 🔒 Sécurité Production

### 1. Variables d'Environnement

Créer `.env`:
```bash
# API Keys (ne PAS commit)
MEXC_API_KEY=your_api_key_here
MEXC_SECRET_KEY=your_secret_key_here

# Database
DATABASE_URL=sqlite:///data/trades.db

# Flask Secret
SECRET_KEY=random_secret_key_here

# Environment
ENVIRONMENT=production
DEBUG=false
```

Charger dans `main.py`:
```python
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('MEXC_API_KEY')
secret_key = os.getenv('MEXC_SECRET_KEY')
```

### 2. Rate Limiting

Installer:
```bash
pip install slowapi
```

Dans `main.py`:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/sessions")
@limiter.limit("10/minute")
async def get_sessions(request: Request):
    # ...
```

### 3. CORS Production

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://trade-cursor.local"],  # Votre domaine
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

---

## ✅ Checklist Finale

### Avant Mise en Production
- [ ] Tous les tests passent
- [ ] Build frontend sans erreurs
- [ ] Variables d'environnement configurées
- [ ] SSL/HTTPS configuré
- [ ] Firewall configuré
- [ ] PM2 auto-start configuré
- [ ] Nginx reverse proxy testé
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
uvicorn.run(socketio_app, host='0.0.0.0', port=5000)

# Vérifier firewall
sudo ufw status

# Vérifier Nginx config WebSocket
sudo nginx -t
```

### PM2 process crash
```bash
# Voir erreurs
pm2 logs trade-cursor-backend --err

# Restart
pm2 restart trade-cursor-backend

# Delete et recréer
pm2 delete trade-cursor-backend
pm2 start main.py --name trade-cursor-backend --interpreter python3
```

### Build frontend échoue
```bash
# Nettoyer cache
rm -rf node_modules package-lock.json
npm install
npm run build
```

---

## 📊 Performance Production

### Optimisations Backend
- Utiliser Gunicorn avec workers multiples
- Redis pour cache sessions
- PostgreSQL au lieu de SQLite (>1000 trades/jour)

### Optimisations Frontend
- Activer Brotli compression (déjà dans build)
- CDN pour assets statiques
- Service Workers pour cache offline

---

## 🎯 Maintenance

### Quotidienne
- Vérifier `pm2 list` (processus running)
- Vérifier logs erreurs

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
4. Vérifier network/firewall

---

**Temps estimé déploiement complet**: 2-4 heures (première fois)
**Temps estimé déploiement update**: 15-30 minutes

🎉 Après ce setup, votre Trade Cursor v7.0 sera en production et accessible depuis n'importe quel device!

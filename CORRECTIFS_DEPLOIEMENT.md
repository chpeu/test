# 🔧 Correctifs Détaillés - Trade Cursor v7.0

Document de référence pour corriger tous les bugs identifiés dans `PRODUCTION_DEPLOYMENT.md`.

---

## 🔴 CORRECTIF #1: Configuration PM2 Frontend

### Problème
La commande PM2 pour le frontend ne fonctionnera pas car elle ne correspond pas à la structure générée par SvelteKit.

### Solution

**Étape 1**: Ajouter script `start` dans `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite dev --port 3000",
    "build": "vite build",
    "preview": "vite preview --port 3000",
    "start": "node build/index.js",
    "check": "svelte-kit sync && svelte-check --tsconfig ./jsconfig.json",
    "check:watch": "svelte-kit sync && svelte-check --tsconfig ./jsconfig.json --watch",
    "lint": "prettier --check . && eslint .",
    "format": "prettier --write ."
  }
}
```

**Étape 2**: Modifier la section D de `PRODUCTION_DEPLOYMENT.md`:

```bash
# Ancienne commande (INCORRECTE):
# pm2 start build/index.js --name trade-cursor-frontend

# Nouvelle commande (CORRECTE):
cd frontend
npm run build
pm2 start npm --name trade-cursor-frontend -- start
```

**OU** (alternative si le script npm ne fonctionne pas):

```bash
cd frontend/build
pm2 start index.js --name trade-cursor-frontend --node-args="--port 3000"
```

---

## 🔴 CORRECTIF #2: Aligner Documentation avec Versions Réelles

### Modifier PRODUCTION_DEPLOYMENT.md ligne 17-19

**Remplacer**:
```markdown
"@sveltejs/adapter-node": "^0.0.18",
"@sveltejs/kit": "^0.0.30",
```

**Par**:
```markdown
"@sveltejs/adapter-node": "^5.0.0",
"@sveltejs/kit": "^2.8.2",
"@sveltejs/vite-plugin-svelte": "^4.0.0",
```

**Et remplacer ligne 425**:
```markdown
# Flask Secret
```

**Par**:
```markdown
# FastAPI Secret
```

---

## 🔴 CORRECTIF #3: Configuration Nginx WebSocket Améliorée

### Remplacer lignes 214-222 dans PRODUCTION_DEPLOYMENT.md

**Ancienne configuration**:
```nginx
location /socket.io {
    proxy_pass http://localhost:5000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;
}
```

**Nouvelle configuration (COMPLÈTE)**:
```nginx
# WebSocket Socket.IO (port 5000)
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
```

---

## 🟡 CORRECTIF #4: Rate Limiting FastAPI

### Remplacer lignes 449-462 dans PRODUCTION_DEPLOYMENT.md

**Ancien code (INCORRECT)**:
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

**Nouveau code (CORRECT)**:
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
def get_sessions(request: Request):  # Pas async pour slowapi
    # Votre code ici
    return {"sessions": []}
```

**Note**: `slowapi` ne fonctionne pas bien avec `async def`. Utiliser `def` ou utiliser une alternative comme `fastapi-limiter`.

---

## 🟡 CORRECTIF #5: CORS Configuration Complète

### Remplacer lignes 464-476 dans PRODUCTION_DEPLOYMENT.md

**Nouvelle configuration (COMPLÈTE)**:
```python
from fastapi.middleware.cors import CORSMiddleware

# Configuration CORS
allowed_origins = [
    "https://trade-cursor.local",  # Production
    "http://localhost:3000",        # Dev local
    "http://localhost:5173",        # Vite dev (si utilisé)
]

# Ajouter réseau local si nécessaire
import os
if os.getenv("ENVIRONMENT") == "development":
    allowed_origins.append("http://192.168.1.0/24")  # Ajuster selon votre réseau

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

## 🟡 CORRECTIF #6: Validation Variables d'Environnement

### Créer `scripts/validate_env.py`

```python
#!/usr/bin/env python3
"""Validation des variables d'environnement requises"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "SECRET_KEY",
    "ENVIRONMENT",
]

OPTIONAL_VARS = [
    "MEXC_API_KEY",
    "MEXC_SECRET_KEY",
    "DATABASE_URL",
    "DEBUG",
]

def validate_env():
    """Valider les variables d'environnement"""
    errors = []
    warnings = []

    # Vérifier variables requises
    for var in REQUIRED_VARS:
        if not os.getenv(var):
            errors.append(f"❌ Variable requise manquante: {var}")

    # Vérifier variables optionnelles
    for var in OPTIONAL_VARS:
        if not os.getenv(var):
            warnings.append(f"⚠️  Variable optionnelle manquante: {var}")

    # Afficher résultats
    if errors:
        print("❌ ERREURS:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)

    if warnings:
        print("⚠️  AVERTISSEMENTS:")
        for warning in warnings:
            print(f"  {warning}")

    print("✅ Toutes les variables requises sont présentes")
    return True

if __name__ == "__main__":
    validate_env()
```

### Ajouter dans PRODUCTION_DEPLOYMENT.md (section Setup Backend):

```bash
# Valider variables d'environnement
python scripts/validate_env.py
```

---

## 🟢 CORRECTIF #7: Health Check Endpoint

### Ajouter dans `main.py` (si pas déjà présent):

```python
@app.get("/api/health")
async def health_check():
    """Health check endpoint pour monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "7.0.0"
    }
```

### Ajouter dans PRODUCTION_DEPLOYMENT.md (section Monitoring):

```bash
# Health check
curl http://localhost:5000/api/health
```

---

## 🟢 CORRECTIF #8: Script de Déploiement Automatisé

### Créer `scripts/deploy.sh`

```bash
#!/bin/bash
# Script de déploiement automatisé pour Trade Cursor v7.0

set -e  # Arrêter en cas d'erreur

echo "🚀 Déploiement Trade Cursor v7.0"

# Variables
PROJECT_DIR="/home/user/trade_cursor_py"
VENV_DIR="$PROJECT_DIR/venv"

# 1. Backup base de données
echo "📦 Backup base de données..."
if [ -f "$PROJECT_DIR/data/trades.db" ]; then
    cp "$PROJECT_DIR/data/trades.db" "$PROJECT_DIR/data/trades.db.backup.$(date +%Y%m%d_%H%M%S)"
fi

# 2. Pull latest code (si Git)
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "📥 Pull latest code..."
    cd "$PROJECT_DIR"
    git pull
fi

# 3. Backend setup
echo "🐍 Setup backend..."
cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt
python scripts/validate_env.py

# 4. Frontend setup
echo "📦 Setup frontend..."
cd "$PROJECT_DIR/frontend"
npm install
npm run build

# 5. Restart PM2
echo "🔄 Restart PM2..."
pm2 restart trade-cursor-backend
pm2 restart trade-cursor-frontend

# 6. Vérifier status
echo "✅ Vérification status..."
pm2 list
pm2 logs --lines 20

echo "🎉 Déploiement terminé!"
```

### Rendre exécutable:
```bash
chmod +x scripts/deploy.sh
```

---

## 📋 Checklist de Correction

Avant de déployer, vérifier que tous les correctifs sont appliqués:

- [ ] ✅ Script `start` ajouté dans `package.json`
- [ ] ✅ Documentation versions alignée avec `package.json`
- [ ] ✅ Configuration Nginx WebSocket améliorée
- [ ] ✅ Code rate limiting corrigé dans `main.py`
- [ ] ✅ Configuration CORS complète
- [ ] ✅ Script validation `.env` créé
- [ ] ✅ Health check endpoint ajouté
- [ ] ✅ Script déploiement automatisé créé

---

## 🚀 Ordre d'Application des Correctifs

1. **Correctif #2**: Aligner documentation (rapide, pas de risque)
2. **Correctif #1**: Ajouter script start dans package.json
3. **Correctif #3**: Améliorer Nginx config
4. **Correctif #4**: Corriger rate limiting dans code
5. **Correctif #5**: Améliorer CORS
6. **Correctif #6**: Créer validation env
7. **Correctif #7**: Ajouter health check
8. **Correctif #8**: Créer script déploiement

---

**Note**: Tester chaque correctif individuellement avant de passer au suivant.


#!/bin/bash
# Script de déploiement automatisé pour Trade Cursor v7.0
# Créé par Auto (Cursor AI) - 2025-11-08

set -e  # Arrêter en cas d'erreur

echo "🚀 Déploiement Trade Cursor v7.0"

# Variables
PROJECT_DIR="/home/user/trade_cursor_py"
VENV_DIR="$PROJECT_DIR/venv"

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "$PROJECT_DIR/main.py" ]; then
    echo "❌ Erreur: main.py non trouvé dans $PROJECT_DIR"
    exit 1
fi

# 1. Backup base de données
echo "📦 Backup base de données..."
if [ -f "$PROJECT_DIR/data/trades.db" ]; then
    BACKUP_FILE="$PROJECT_DIR/data/trades.db.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$PROJECT_DIR/data/trades.db" "$BACKUP_FILE"
    echo "✅ Backup créé: $BACKUP_FILE"
fi

# 2. Pull latest code (si Git)
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "📥 Pull latest code..."
    cd "$PROJECT_DIR"
    git pull || echo "⚠️  Git pull échoué, continuons..."
fi

# 3. Backend setup
echo "🐍 Setup backend..."
cd "$PROJECT_DIR"

# Activer virtualenv
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Création virtualenv..."
    python3.11 -m venv venv
fi

source "$VENV_DIR/bin/activate"

# Installer dépendances
echo "📦 Installation dépendances Python..."
pip install -r requirements.txt

# Valider variables d'environnement
echo "🔍 Validation variables d'environnement..."
if [ -f "scripts/validate_env.py" ]; then
    python scripts/validate_env.py
else
    echo "⚠️  Script validate_env.py non trouvé, validation ignorée"
fi

# 4. Frontend setup
echo "📦 Setup frontend..."
cd "$PROJECT_DIR/frontend"

# Installer dépendances
echo "📦 Installation dépendances npm..."
npm install

# Build
echo "🔨 Build frontend..."
npm run build

# Vérifier que build/index.js existe
if [ ! -f "build/index.js" ]; then
    echo "❌ Erreur: build/index.js non trouvé après build"
    exit 1
fi

# 5. Restart PM2
echo "🔄 Restart PM2..."

# Backend
if pm2 list | grep -q "trade-cursor-backend"; then
    pm2 restart trade-cursor-backend
else
    echo "⚠️  trade-cursor-backend non trouvé, création..."
    cd "$PROJECT_DIR"
    pm2 start main.py --name trade-cursor-backend --interpreter python3
fi

# Frontend
if pm2 list | grep -q "trade-cursor-frontend"; then
    pm2 restart trade-cursor-frontend
else
    echo "⚠️  trade-cursor-frontend non trouvé, création..."
    cd "$PROJECT_DIR/frontend"
    pm2 start npm --name trade-cursor-frontend -- start
fi

# Sauvegarder PM2
pm2 save

# 6. Vérifier status
echo "✅ Vérification status..."
pm2 list
echo ""
echo "📋 Dernières lignes de logs:"
pm2 logs --lines 10 --nostream

echo ""
echo "🎉 Déploiement terminé!"
echo ""
echo "📊 Commandes utiles:"
echo "  pm2 logs trade-cursor-backend"
echo "  pm2 logs trade-cursor-frontend"
echo "  pm2 monit"


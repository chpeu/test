# 🚀 Guide : Migration vers GitHub

## 📋 Prérequis

- ✅ Compte GitHub créé
- ✅ Git installé et configuré
- ✅ Dépôt Git local initialisé (déjà fait ✅)

---

## 🔒 Étape 1 : Sécuriser les Fichiers Sensibles

### Vérifier que `.gitignore` est à jour

Le fichier `.gitignore` a été mis à jour pour exclure :
- ✅ `.env` (tokens Telegram, etc.)
- ✅ `*.db` (bases de données)
- ✅ `*.log` (logs)
- ✅ `trade_history_*.json` (historiques)

### Vérifier les fichiers non trackés

```bash
cd "C:\Users\sebta\Documents\code scalp\trade_cursor_py"
git status
```

**Si vous voyez `.env` ou `*.db` dans "Untracked files"** :
- ✅ C'est normal, ils sont maintenant ignorés par Git
- ✅ Ils ne seront **PAS** poussés sur GitHub

---

## 📦 Étape 2 : Créer le Dépôt GitHub

### Option A : Via l'Interface Web (Recommandé)

1. **Aller sur GitHub** : https://github.com
2. **Cliquer sur "+"** (en haut à droite) → **"New repository"**
3. **Remplir les informations** :
   - **Repository name** : `trade_cursor_py` (ou autre nom)
   - **Description** : "Automated Trading Bot for MEXC Futures - Scalping Strategy"
   - **Visibility** : 
     - 🔒 **Private** (recommandé pour code avec tokens)
     - 🌐 **Public** (si vous voulez partager)
   - **NE PAS** cocher :
     - ❌ "Add a README file" (vous en avez déjà un)
     - ❌ "Add .gitignore" (vous en avez déjà un)
     - ❌ "Choose a license" (optionnel)
4. **Cliquer sur "Create repository"**

### Option B : Via GitHub CLI (si installé)

```bash
gh repo create trade_cursor_py --private --description "Automated Trading Bot for MEXC Futures"
```

---

## 🔗 Étape 3 : Connecter le Dépôt Local à GitHub

### 3.1 Récupérer l'URL du Dépôt GitHub

Après création, GitHub affiche l'URL du dépôt :
- **HTTPS** : `https://github.com/VOTRE-USERNAME/trade_cursor_py.git`
- **SSH** : `git@github.com:VOTRE-USERNAME/trade_cursor_py.git`

### 3.2 Ajouter le Remote GitHub

```bash
cd "C:\Users\sebta\Documents\code scalp\trade_cursor_py"

# Remplacer VOTRE-USERNAME par votre nom d'utilisateur GitHub
git remote add origin https://github.com/VOTRE-USERNAME/trade_cursor_py.git

# Vérifier
git remote -v
```

**Résultat attendu** :
```
origin  https://github.com/VOTRE-USERNAME/trade_cursor_py.git (fetch)
origin  https://github.com/VOTRE-USERNAME/trade_cursor_py.git (push)
```

---

## 📤 Étape 4 : Pousser le Code sur GitHub

### 4.1 Vérifier l'État Actuel

```bash
# Vérifier qu'il n'y a pas de fichiers sensibles à commiter
git status

# Si vous voyez .env ou *.db, ils doivent être dans "Untracked files"
# (c'est normal, ils sont ignorés)
```

### 4.2 Commiter les Changements Restants (si nécessaire)

```bash
# Si vous avez des modifications non commitées (sauf .env et *.db)
git add .
git commit -m "chore: Préparation migration GitHub"
```

### 4.3 Pousser sur GitHub

```bash
# Pousser la branche master
git push -u origin master

# Si vous utilisez "main" au lieu de "master"
# git push -u origin main
```

**Résultat attendu** :
```
Enumerating objects: XXX, done.
Counting objects: 100% (XXX/XXX), done.
Delta compression using up to X threads
Compressing objects: 100% (XXX/XXX), done.
Writing objects: 100% (XXX/XXX), XXX KiB | XXX MiB/s, done.
Total XXX (delta XXX), reused XXX (delta XXX)
To https://github.com/VOTRE-USERNAME/trade_cursor_py.git
 * [new branch]      master -> master
Branch 'master' set up to track 'remote/origin/master'.
```

---

## ✅ Étape 5 : Vérification

### 5.1 Vérifier sur GitHub

1. **Aller sur votre dépôt** : `https://github.com/VOTRE-USERNAME/trade_cursor_py`
2. **Vérifier que tous les fichiers sont présents**
3. **Vérifier que `.env` et `*.db` sont ABSENTS** (c'est normal et souhaité)

### 5.2 Vérifier Localement

```bash
# Vérifier que le remote est configuré
git remote -v

# Vérifier le statut
git status

# Voir les branches
git branch -a
```

---

## 🔐 Étape 6 : Sécurité - Fichiers Sensibles

### ⚠️ IMPORTANT : Vérifier que `.env` n'est PAS sur GitHub

```bash
# Vérifier que .env n'est pas tracké
git ls-files | grep .env

# Si rien ne s'affiche → ✅ .env n'est pas tracké (bon)
# Si .env s'affiche → ❌ PROBLÈME ! (voir section "Si .env est déjà tracké")
```

### Si `.env` est déjà tracké (avant mise à jour .gitignore)

```bash
# Retirer .env du tracking Git (mais garder le fichier local)
git rm --cached .env

# Commiter la suppression
git commit -m "chore: Retirer .env du tracking Git"

# Pousser
git push origin master
```

### Créer un `.env.example`

Pour que les autres développeurs sachent quelles variables sont nécessaires :

```bash
# Créer .env.example avec les variables (sans les valeurs)
cat > .env.example << 'EOF'
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Paper Trading
PAPER_TRADING_MODE=false
PAPER_TRADING_INITIAL_CAPITAL=1000.0

# Notification Types
TELEGRAM_NOTIFY_POSITION_OPENED=true
TELEGRAM_NOTIFY_POSITION_CLOSED=true
# ... etc
EOF

# Ajouter .env.example (il sera tracké)
git add .env.example
git commit -m "docs: Ajouter .env.example pour référence"
git push origin master
```

---

## 📝 Étape 7 : Créer un README.md (si pas déjà fait)

Créer un `README.md` professionnel :

```markdown
# 🤖 Trading Bot - MEXC Futures Scalping

Bot de trading automatisé pour MEXC Futures avec stratégie de scalping.

## 🚀 Fonctionnalités

- Scanner de paires scalables
- Détection de setups multi-timeframes
- Gestion de positions avec TP/SL adaptatifs
- TP Escalier (multi-level)
- Paper Trading
- Backtesting
- Analytics et monitoring
- Notifications Telegram
- Dashboard web en temps réel

## 📋 Prérequis

- Python 3.11+
- Compte MEXC Futures (API keys)
- Bot Telegram (optionnel)

## 🔧 Installation

```bash
# Cloner le dépôt
git clone https://github.com/VOTRE-USERNAME/trade_cursor_py.git
cd trade_cursor_py

# Installer les dépendances
pip install -r requirements.txt

# Configurer .env
cp .env.example .env
# Éditer .env avec vos tokens
```

## 🎯 Utilisation

```bash
# Démarrer le bot
python main.py 5000

# Accéder au dashboard
http://localhost:5000
```

## 📚 Documentation

- [Guide Telegram](GUIDE_TELEGRAM.md)
- [Guide Multi-Instances](GUIDE_MULTI_INSTANCES.md)
- [Guide Commandes Telegram](GUIDE_TELEGRAM_COMMANDES.md)

## ⚠️ Avertissement

Ce bot est fourni à des fins éducatives. Le trading comporte des risques de perte en capital.

## 📄 Licence

[Votre licence]
```

---

## 🔄 Étape 8 : Workflow Futur

### Pousser des Changements

```bash
# 1. Faire vos modifications
# 2. Vérifier les changements
git status

# 3. Ajouter les fichiers
git add .

# 4. Commiter
git commit -m "feat: Description des changements"

# 5. Pousser
git push origin master
```

### Récupérer les Changements

```bash
# Récupérer les dernières modifications
git pull origin master
```

### Créer une Branche

```bash
# Créer une nouvelle branche
git checkout -b feature/nouvelle-fonctionnalite

# Faire vos modifications
# ...

# Commiter
git add .
git commit -m "feat: Nouvelle fonctionnalité"

# Pousser la branche
git push -u origin feature/nouvelle-fonctionnalite

# Créer une Pull Request sur GitHub
```

---

## 🛡️ Sécurité - Checklist

Avant de pousser sur GitHub, vérifier :

- [ ] `.env` est dans `.gitignore` ✅
- [ ] `*.db` est dans `.gitignore` ✅
- [ ] Aucun token/secret dans le code source
- [ ] `.env.example` créé (sans valeurs réelles)
- [ ] README.md créé
- [ ] Dépôt en **Private** (si contient du code sensible)

---

## 🆘 Dépannage

### Erreur : "remote origin already exists"

```bash
# Vérifier le remote actuel
git remote -v

# Si c'est le mauvais, le supprimer
git remote remove origin

# Puis ajouter le bon
git remote add origin https://github.com/VOTRE-USERNAME/trade_cursor_py.git
```

### Erreur : "Authentication failed"

```bash
# Utiliser un Personal Access Token (PAT)
# 1. GitHub → Settings → Developer settings → Personal access tokens
# 2. Générer un token avec permissions "repo"
# 3. Utiliser le token comme mot de passe lors du push
```

### Erreur : "refusing to merge unrelated histories"

```bash
# Si GitHub a créé un README automatiquement
git pull origin master --allow-unrelated-histories
git push origin master
```

---

## 📋 Commandes Rapides

```bash
# État actuel
git status

# Voir les remotes
git remote -v

# Ajouter remote
git remote add origin https://github.com/VOTRE-USERNAME/trade_cursor_py.git

# Pousser
git push -u origin master

# Vérifier que .env n'est pas tracké
git ls-files | grep .env

# Voir l'historique
git log --oneline -10
```

---

*Guide créé le : 2025-01-07*


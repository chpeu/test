# 🐳 Guide Docker pour Windows - Trade Cursor

Guide complet pour lancer une instance de Trade Cursor avec Docker sous Windows.

---

## 📋 Table des Matières

- [Prérequis](#prérequis)
- [Installation Docker Desktop](#installation-docker-desktop)
- [Premier Lancement](#premier-lancement)
- [Commandes PowerShell](#commandes-powershell)
- [Multi-Instances](#multi-instances)
- [Configuration](#configuration)
- [Troubleshooting Windows](#troubleshooting-windows)
- [Commandes Utiles](#commandes-utiles)

---

## 📦 Prérequis

### Système

- ✅ **Windows 10/11** (64-bit)
- ✅ **4 GB RAM minimum** (8 GB recommandé)
- ✅ **Espace disque** : 2 GB pour Docker Desktop + 1 GB pour les images

### Logiciels

- ✅ **Docker Desktop** (à installer)
- ✅ **PowerShell** (inclus avec Windows)
- ✅ **Git** (optionnel, pour cloner depuis GitHub)

---

## 🔧 Installation Docker Desktop

### Étape 1 : Télécharger Docker Desktop

1. Allez sur : https://www.docker.com/products/docker-desktop/
2. Cliquez sur **"Download for Windows"**
3. Téléchargez le fichier `Docker Desktop Installer.exe`

### Étape 2 : Installer Docker Desktop

1. **Double-cliquez** sur `Docker Desktop Installer.exe`
2. Suivez l'assistant d'installation
3. ✅ Cochez **"Use WSL 2 instead of Hyper-V"** (recommandé)
4. Cliquez sur **"Install"**
5. Redémarrez votre ordinateur si demandé

### Étape 3 : Démarrer Docker Desktop

1. **Lancez Docker Desktop** depuis le menu Démarrer
2. Attendez que Docker démarre (icône dans la barre des tâches)
3. Vérifiez que l'icône Docker est **verte** (pas orange/rouge)

### Étape 4 : Vérifier l'Installation

Ouvrez **PowerShell** (clic droit > Exécuter en tant qu'administrateur) :

```powershell
# Vérifier la version Docker
docker --version
# Résultat attendu : Docker version 24.x.x, build xxxxx

# Vérifier Docker Compose
docker-compose --version
# Résultat attendu : Docker Compose version v2.x.x

# Tester Docker
docker run hello-world
# Si ça fonctionne, vous verrez "Hello from Docker!"
```

✅ **Si toutes les commandes fonctionnent, Docker est installé correctement !**

---

## 🚀 Premier Lancement

### Étape 1 : Ouvrir le Dossier du Projet

1. Ouvrez **PowerShell** dans le dossier du projet :
   - Clic droit sur le dossier `trade_cursor_py`
   - Sélectionnez **"Ouvrir dans le terminal"** ou **"Ouvrir dans PowerShell"**

   OU

2. Ouvrez **PowerShell** manuellement :
   ```powershell
   cd "C:\Users\sebta\Documents\clone github\trade_cursor_py"
   ```

### Étape 2 : Vérifier les Fichiers Docker

Vérifiez que ces fichiers existent :
- ✅ `Dockerfile`
- ✅ `docker-compose.yml`
- ✅ `requirements.txt`

```powershell
# Lister les fichiers Docker
Get-ChildItem -Filter "*docker*"
Get-ChildItem -Filter "Dockerfile"
```

### Étape 3 : Créer le Fichier .env (Optionnel)

Si vous avez des clés API, créez un fichier `.env` :

```powershell
# Créer le fichier .env
New-Item -Path ".env" -ItemType File -Force

# Éditer avec Notepad
notepad .env
```

Contenu du fichier `.env` :
```env
# API MEXC (optionnel si mode testnet)
MEXC_API_KEY=your_api_key_here
MEXC_API_SECRET=your_api_secret_here

# Configuration optionnelle
INSTANCE_NAME=trade-bot-1
LOG_LEVEL=INFO
```

### Étape 4 : Build l'Image Docker

```powershell
# Build l'image Docker (première fois, peut prendre 5-10 minutes)
docker-compose build
```

**Ce que fait cette commande** :
- ✅ Télécharge l'image Python 3.11
- ✅ Installe toutes les dépendances (`requirements.txt`)
- ✅ Copie le code de l'application
- ✅ Crée l'image Docker

**Résultat attendu** :
```
[+] Building 45.2s (10/10) FINISHED
 => [internal] load build definition from Dockerfile
 => => transferring dockerfile: 2B
 => [1/5] FROM docker.io/library/python:3.11-slim
 => ...
 => => naming to docker.io/library/trade_cursor_py-trade-bot-1
```

### Étape 5 : Lancer l'Instance

```powershell
# Lancer l'instance en arrière-plan
docker-compose up -d trade-bot-1
```

**Résultat attendu** :
```
[+] Running 2/2
 ✔ Container trade-cursor-5000  Started
```

### Étape 6 : Vérifier que ça Fonctionne

```powershell
# Vérifier l'état des conteneurs
docker-compose ps
```

**Résultat attendu** :
```
NAME                  STATUS      PORTS
trade-cursor-5000     Up 30s      0.0.0.0:5000->5000/tcp
```

### Étape 7 : Accéder à l'Interface Web

Ouvrez votre navigateur et allez sur :
```
http://localhost:5000
```

✅ **Vous devriez voir l'interface de Trade Cursor !**

---

## 💻 Commandes PowerShell

### Commandes de Base

```powershell
# Build l'image (première fois ou après modifications)
docker-compose build

# Lancer instance 1 en arrière-plan
docker-compose up -d trade-bot-1

# Lancer instance 1 en mode visible (voir les logs)
docker-compose up trade-bot-1

# Voir les logs en temps réel
docker-compose logs -f trade-bot-1

# Arrêter l'instance
docker-compose stop trade-bot-1

# Redémarrer l'instance
docker-compose restart trade-bot-1

# Arrêter et supprimer le conteneur
docker-compose down trade-bot-1

# Voir l'état des conteneurs
docker-compose ps
```

### Commandes de Logs

```powershell
# Voir les logs en temps réel (suivre)
docker-compose logs -f trade-bot-1

# Voir les 100 dernières lignes
docker-compose logs --tail=100 trade-bot-1

# Voir les logs depuis une date
docker-compose logs --since 2025-01-07T10:00:00 trade-bot-1

# Voir tous les logs (toutes les instances)
docker-compose logs -f
```

### Commandes de Debug

```powershell
# Entrer dans le conteneur (bash)
docker-compose exec trade-bot-1 bash

# Exécuter une commande dans le conteneur
docker-compose exec trade-bot-1 python --version

# Voir les variables d'environnement
docker-compose exec trade-bot-1 env

# Voir l'utilisation des ressources
docker stats trade-cursor-5000
```

### Commandes de Nettoyage

```powershell
# Arrêter tous les conteneurs
docker-compose down

# Arrêter et supprimer les volumes (ATTENTION : supprime les données)
docker-compose down -v

# Supprimer les images inutilisées
docker image prune

# Supprimer tous les conteneurs arrêtés
docker container prune

# Rebuild sans cache (après modifications majeures)
docker-compose build --no-cache
```

---

## 🔄 Multi-Instances

### Activer les Instances 2 et 3

1. **Ouvrir `docker-compose.yml`** avec un éditeur de texte :
   ```powershell
   notepad docker-compose.yml
   ```

2. **Décommenter les sections** `trade-bot-2` et `trade-bot-3` :
   - Retirez les `#` au début de chaque ligne
   - De la ligne 37 à 55 pour `trade-bot-2`
   - De la ligne 57 à 75 pour `trade-bot-3`

3. **Sauvegarder** le fichier

### Lancer Toutes les Instances

```powershell
# Build toutes les images
docker-compose build

# Lancer toutes les instances en arrière-plan
docker-compose up -d
```

**Résultat attendu** :
```
[+] Running 4/4
 ✔ Container trade-cursor-5000  Started
 ✔ Container trade-cursor-5001  Started
 ✔ Container trade-cursor-5002  Started
```

### Vérifier l'État

```powershell
docker-compose ps
```

**Résultat attendu** :
```
NAME                  STATUS      PORTS
trade-cursor-5000     Up 2 min    0.0.0.0:5000->5000/tcp
trade-cursor-5001     Up 2 min    0.0.0.0:5001->5001/tcp
trade-cursor-5002     Up 2 min    0.0.0.0:5002->5002/tcp
```

### Accéder aux Interfaces

- ✅ Instance 1 : http://localhost:5000
- ✅ Instance 2 : http://localhost:5001
- ✅ Instance 3 : http://localhost:5002

---

## ⚙️ Configuration

### Variables d'Environnement

Les variables d'environnement peuvent être définies dans :

1. **Fichier `.env`** (recommandé) :
   ```env
   MEXC_API_KEY=your_key
   MEXC_API_SECRET=your_secret
   ```

2. **Dans `docker-compose.yml`** :
   ```yaml
   environment:
     - MEXC_API_KEY=${MEXC_API_KEY}
     - MEXC_API_SECRET=${MEXC_API_SECRET}
   ```

3. **Directement dans PowerShell** (temporaire) :
   ```powershell
   $env:MEXC_API_KEY="your_key"
   docker-compose up -d
   ```

### Volumes (Persistence des Données)

Les données sont automatiquement sauvegardées dans :

```
.\data\instance1\   # Historique trades, DB analytics
.\logs\instance1\   # Logs de l'instance 1

.\data\instance2\   # Instance 2
.\logs\instance2\

.\data\instance3\   # Instance 3
.\logs\instance3\
```

Ces dossiers sont créés automatiquement par Docker.

**Voir les données** :
```powershell
# Lister les fichiers de données
Get-ChildItem -Recurse .\data\instance1\

# Voir les logs
Get-Content .\logs\instance1\app.log -Tail 50
```

---

## 🔍 Troubleshooting Windows

### Problème 1 : "Docker Desktop is not running"

**Symptôme** :
```
error during connect: This error may indicate that the docker daemon is not running
```

**Solution** :
1. Lancez **Docker Desktop** depuis le menu Démarrer
2. Attendez que l'icône soit **verte**
3. Réessayez la commande

### Problème 2 : "Port already in use"

**Symptôme** :
```
Error: bind: address already in use
```

**Solution** :
```powershell
# Trouver le processus utilisant le port 5000
Get-NetTCPConnection -LocalPort 5000 | Select-Object OwningProcess

# Tuer le processus (remplacez <PID> par le numéro)
Stop-Process -Id <PID> -Force

# OU arrêter tous les conteneurs Docker
docker-compose down
```

### Problème 3 : "Cannot connect to Docker daemon"

**Symptôme** :
```
Cannot connect to the Docker daemon. Is the docker daemon running?
```

**Solution** :
1. Vérifiez que **Docker Desktop** est lancé
2. Redémarrez Docker Desktop
3. Vérifiez que **WSL 2** est activé (si vous utilisez WSL 2)

### Problème 4 : "Permission denied" sur les Volumes

**Symptôme** :
```
Permission denied: ./data/instance1
```

**Solution** :
```powershell
# Créer les dossiers manuellement
New-Item -ItemType Directory -Force -Path ".\data\instance1"
New-Item -ItemType Directory -Force -Path ".\logs\instance1"

# Donner les permissions (si nécessaire)
icacls ".\data" /grant Everyone:F /T
```

### Problème 5 : Conteneur Redémarre en Boucle

**Symptôme** :
```
STATUS: Restarting (1) 2 seconds ago
```

**Solution** :
```powershell
# Voir les logs pour identifier l'erreur
docker-compose logs trade-bot-1

# Vérifier le healthcheck
docker inspect trade-cursor-5000 | Select-String -Pattern "Health" -Context 0,10
```

**Causes communes** :
- Port déjà utilisé
- Dépendance manquante dans `requirements.txt`
- Erreur dans le code
- DB analytics corrompue

### Problème 6 : "Build failed" - Erreur de Dépendances

**Symptôme** :
```
ERROR: Could not find a version that satisfies the requirement ...
```

**Solution** :
```powershell
# Vérifier requirements.txt
Get-Content requirements.txt

# Rebuild sans cache
docker-compose build --no-cache
```

### Problème 7 : PowerShell vs CMD

**Si vous utilisez CMD au lieu de PowerShell** :

Les commandes sont les mêmes, mais :
- PowerShell : `Get-ChildItem` = CMD : `dir`
- PowerShell : `Get-Content` = CMD : `type`
- PowerShell : `New-Item` = CMD : `mkdir`

**Recommandation** : Utilisez **PowerShell** (plus moderne et puissant)

---

## 📝 Commandes Utiles - Résumé

### Démarrage Rapide

```powershell
# 1. Aller dans le dossier du projet
cd "C:\Users\sebta\Documents\clone github\trade_cursor_py"

# 2. Build l'image (première fois)
docker-compose build

# 3. Lancer l'instance
docker-compose up -d trade-bot-1

# 4. Voir les logs
docker-compose logs -f trade-bot-1

# 5. Accéder à l'interface
# Ouvrir http://localhost:5000 dans le navigateur
```

### Gestion Quotidienne

```powershell
# Voir l'état
docker-compose ps

# Voir les logs
docker-compose logs -f trade-bot-1

# Redémarrer
docker-compose restart trade-bot-1

# Arrêter
docker-compose stop trade-bot-1

# Démarrer
docker-compose start trade-bot-1
```

### Après Modification du Code

```powershell
# Rebuild l'image
docker-compose build --no-cache

# Redémarrer
docker-compose up -d --build trade-bot-1
```

### Nettoyage

```powershell
# Arrêter tous les conteneurs
docker-compose down

# Supprimer les images inutilisées
docker image prune

# Supprimer tous les conteneurs arrêtés
docker container prune
```

---

## 🎯 Exemple Complet : Premier Lancement

```powershell
# 1. Ouvrir PowerShell dans le dossier du projet
cd "C:\Users\sebta\Documents\clone github\trade_cursor_py"

# 2. Vérifier que Docker fonctionne
docker --version
docker-compose --version

# 3. Build l'image (première fois, 5-10 minutes)
docker-compose build

# 4. Lancer l'instance en arrière-plan
docker-compose up -d trade-bot-1

# 5. Vérifier l'état
docker-compose ps

# 6. Voir les logs
docker-compose logs -f trade-bot-1

# 7. Ouvrir le navigateur
# http://localhost:5000
```

---

## 📊 Comparaison : Avec vs Sans Docker

### Sans Docker (Méthode Classique)

```powershell
# Installer Python 3.11
# Installer toutes les dépendances
pip install -r requirements.txt

# Lancer l'instance
python main.py 5000
```

**Problèmes** :
- ❌ Doit installer Python et dépendances
- ❌ Conflits de versions possibles
- ❌ Difficile de gérer plusieurs instances
- ❌ Environnement différent selon la machine

### Avec Docker

```powershell
# Build une fois
docker-compose build

# Lancer
docker-compose up -d trade-bot-1
```

**Avantages** :
- ✅ Pas besoin d'installer Python
- ✅ Environnement isolé et reproductible
- ✅ Facile de gérer plusieurs instances
- ✅ Même environnement partout (Windows, Linux, Cloud)

---

## 🚀 Prochaines Étapes

1. ✅ **Lancer votre première instance** avec Docker
2. ✅ **Tester l'interface** sur http://localhost:5000
3. ✅ **Configurer les variables d'environnement** (`.env`)
4. ✅ **Activer les instances 2 et 3** si nécessaire
5. ✅ **Monitorer les logs** régulièrement

---

## 📚 Ressources

- **Docker Desktop** : https://www.docker.com/products/docker-desktop/
- **Documentation Docker** : https://docs.docker.com/
- **Documentation Docker Compose** : https://docs.docker.com/compose/
- **Guide général Docker** : `DOCKER_README.md` (dans ce projet)

---

**Version** : 1.0  
**Dernière mise à jour** : 2025-01-07  
**Système** : Windows 10/11


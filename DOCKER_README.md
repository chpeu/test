# 🐳 Docker Guide - Trade Cursor v7.0

Guide complet pour conteneuriser et déployer Trade Cursor avec Docker.

## 📋 Table des Matières

- [Qu'est-ce que Docker ?](#quest-ce-que-docker-)
- [Prérequis](#prérequis)
- [Quick Start](#quick-start)
- [Déploiement Multi-Instances](#déploiement-multi-instances)
- [Configuration](#configuration)
- [Commandes Utiles](#commandes-utiles)
- [Troubleshooting](#troubleshooting)

---

## Qu'est-ce que Docker ?

**Docker** = Conteneurisation de votre application

Un conteneur Docker est une "boîte" qui contient :
- ✅ Votre application
- ✅ Python 3.11 et toutes les dépendances
- ✅ Configuration
- ✅ Tout ce dont l'application a besoin

### Avantages pour Trade Cursor

#### 1. Multi-instances simplifiées

**Sans Docker**:
```bash
# Terminal 1
python main.py 5000

# Terminal 2
python main.py 5001

# Terminal 3
python main.py 5002
```

**Avec Docker**:
```bash
docker-compose up
```
Une seule commande, toutes les instances démarrent !

#### 2. Déploiement simplifié

**Sans Docker**:
1. Installer Python 3.11
2. Installer toutes les dépendances
3. Configurer l'environnement
4. Copier les fichiers
5. Configurer les variables d'environnement
6. Démarrer l'application

**Avec Docker**:
```bash
docker-compose up -d
```
Une seule commande !

#### 3. Reproductibilité

- ✅ Même environnement partout (Windows, Linux, Cloud)
- ✅ Même version Python (3.11)
- ✅ Mêmes dépendances
- ✅ Même configuration
- ✅ Plus de "ça marche sur ma machine mais pas sur le serveur"

---

## Prérequis

### Installer Docker

**Ubuntu/Debian**:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Redémarrer la session
```

**Windows/Mac**:
- Télécharger [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Installer Docker Compose

Docker Compose est inclus avec Docker Desktop. Sur Linux :
```bash
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

Vérifier l'installation :
```bash
docker --version
docker-compose --version
```

---

## Quick Start

### 1. Build l'image Docker

```bash
cd /path/to/trade_cursor_py
docker-compose build
```

Cela va :
- Créer l'image Docker
- Installer Python 3.11
- Installer toutes les dépendances
- Copier le code

### 2. Lancer une instance

```bash
docker-compose up trade-bot-1
```

L'application démarre sur `http://localhost:5000`

### 3. Lancer en arrière-plan

```bash
docker-compose up -d trade-bot-1
```

### 4. Voir les logs

```bash
docker-compose logs -f trade-bot-1
```

### 5. Arrêter l'instance

```bash
docker-compose down
```

---

## Déploiement Multi-Instances

### Configuration

Éditez `docker-compose.yml` et décommentez les instances 2 et 3 :

```yaml
services:
  trade-bot-1:
    # ... (déjà activé)

  trade-bot-2:  # ← Décommenter cette section
    build:
      context: .
      dockerfile: Dockerfile
      args:
        PORT: 5001
    # ...

  trade-bot-3:  # ← Décommenter cette section
    build:
      context: .
      dockerfile: Dockerfile
      args:
        PORT: 5002
    # ...
```

### Lancer toutes les instances

```bash
docker-compose up -d
```

Résultat :
- ✅ Instance 1 sur `http://localhost:5000`
- ✅ Instance 2 sur `http://localhost:5001`
- ✅ Instance 3 sur `http://localhost:5002`

### Vérifier l'état

```bash
docker-compose ps
```

Résultat :
```
NAME                  STATUS      PORTS
trade-cursor-5000     Up 2 min    0.0.0.0:5000->5000/tcp
trade-cursor-5001     Up 2 min    0.0.0.0:5001->5001/tcp
trade-cursor-5002     Up 2 min    0.0.0.0:5002->5002/tcp
```

---

## Configuration

### Variables d'Environnement

Créez un fichier `.env` à la racine :

```env
# API MEXC (optionnel si mode testnet)
MEXC_API_KEY=your_api_key_here
MEXC_API_SECRET=your_api_secret_here

# Configuration optionnelle
INSTANCE_NAME=trade-bot-1
LOG_LEVEL=INFO
```

### Volumes (Persistence des Données)

Les données sont automatiquement sauvegardées dans :
```
./data/instance1/   # Historique trades, DB analytics
./logs/instance1/   # Logs de l'instance 1

./data/instance2/   # Instance 2
./logs/instance2/

./data/instance3/   # Instance 3
./logs/instance3/
```

Ces dossiers sont créés automatiquement.

---

## Commandes Utiles

### Build & Démarrage

```bash
# Build toutes les images
docker-compose build

# Build sans cache (après modifications majeures)
docker-compose build --no-cache

# Lancer instance 1 seulement
docker-compose up trade-bot-1

# Lancer toutes les instances
docker-compose up

# Lancer en arrière-plan
docker-compose up -d

# Rebuild et redémarrer
docker-compose up -d --build
```

### Logs & Monitoring

```bash
# Voir logs en temps réel (instance 1)
docker-compose logs -f trade-bot-1

# Voir logs de toutes les instances
docker-compose logs -f

# Voir les 100 dernières lignes
docker-compose logs --tail=100 trade-bot-1

# Entrer dans le conteneur (debug)
docker-compose exec trade-bot-1 bash

# Vérifier la santé (healthcheck)
docker inspect trade-cursor-5000 | grep Health -A 10
```

### Gestion

```bash
# Arrêter toutes les instances
docker-compose down

# Arrêter et supprimer les volumes
docker-compose down -v

# Redémarrer une instance
docker-compose restart trade-bot-1

# Arrêter une instance
docker-compose stop trade-bot-1

# Démarrer une instance arrêtée
docker-compose start trade-bot-1
```

### Nettoyage

```bash
# Supprimer images inutilisées
docker image prune

# Supprimer tous les conteneurs arrêtés
docker container prune

# Supprimer tout (ATTENTION : supprime tout Docker)
docker system prune -a
```

---

## Troubleshooting

### Erreur "port already in use"

```bash
# Trouver le processus utilisant le port 5000
lsof -i :5000
# ou
netstat -tulpn | grep 5000

# Tuer le processus
kill -9 <PID>
```

### Conteneur redémarre en boucle

```bash
# Voir les logs
docker-compose logs trade-bot-1

# Vérifier le healthcheck
docker inspect trade-cursor-5000 | grep Health -A 20
```

Causes communes :
- Port déjà utilisé
- Dépendance manquante dans requirements.txt
- Erreur dans le code
- DB analytics corrompue

### Rebuild après modification du code

```bash
# Rebuild sans cache
docker-compose build --no-cache

# Redémarrer
docker-compose up -d
```

### Accéder aux logs persistants

```bash
# Logs de l'instance 1
tail -f logs/instance1/app.log

# Historique trades
cat data/instance1/trade_history.json
```

### Tester sans Docker

```bash
# Revenir au mode normal
python main.py
```

---

## Production

### Recommandations

1. **Utiliser un reverse proxy** (Nginx, Traefik) pour :
   - HTTPS
   - Load balancing
   - Rate limiting

2. **Monitorer les healthchecks** :
```bash
watch -n 5 'docker-compose ps'
```

3. **Automatiser le redémarrage** :
   - Docker Compose inclut déjà `restart: unless-stopped`
   - Les conteneurs redémarrent automatiquement en cas de crash

4. **Backup automatique** :
```bash
# Backup quotidien
0 2 * * * tar -czf /backup/trade-data-$(date +\%Y\%m\%d).tar.gz ./data/
```

5. **Logs rotatifs** :
   - Configurer logrotate pour éviter que les logs ne remplissent le disque

---

## Déploiement Cloud

### Docker Hub

```bash
# Tag l'image
docker tag trade-cursor:latest username/trade-cursor:v7.0

# Push vers Docker Hub
docker push username/trade-cursor:v7.0
```

### Serveur distant

```bash
# Sur le serveur
docker pull username/trade-cursor:v7.0
docker-compose up -d
```

---

## Support

- **Issues GitHub** : [Lien vers votre repo]
- **Documentation** : `README.md`
- **Logs** : Toujours inclure les logs lors d'un bug report

---

**Version** : 7.0
**Dernière mise à jour** : 2025-11-08

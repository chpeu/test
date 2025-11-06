# 📱 GUIDE COMPLET - Configuration Telegram

**Date**: 2025-11-06  
**Architecture V2 - Notifications Telegram**

---

## 🎯 OBJECTIF

Configurer un bot Telegram pour recevoir des notifications en temps réel de ton bot trading.

---

## 📋 ÉTAPE 1 : Créer un Bot Telegram

### 1.1 Ouvrir Telegram et chercher BotFather

1. Ouvre l'application **Telegram** (mobile ou desktop)
2. Dans la barre de recherche, tape : **`@BotFather`**
3. Clique sur le bot officiel (vérifié avec ✓)

### 1.2 Créer un nouveau bot

1. Envoie la commande : `/newbot`
2. BotFather demande : **"Alright, a new bot. How are we going to call it? Please choose a name for your bot."**
3. Réponds avec un nom (ex: `Mon Trading Bot`)
4. BotFather demande : **"Good. Now let's choose a username for your bot. It must end in `bot`. Like this, for example: TetrisBot or tetris_bot."**
5. Réponds avec un username unique (ex: `mon_trading_bot_2025`)
6. BotFather répond avec quelque chose comme :
   ```
   Done! Congratulations on your new bot. You will find it at t.me/mon_trading_bot_2025. 
   You can now add a description, about section and profile picture for your bot, see /help for a list of commands.
   
   Use this token to access the HTTP API:
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890
   
   Keep your token secure and store it safely, it can be used by anyone to control your bot.
   ```

### 1.3 Copier le Token

**⚠️ IMPORTANT** : Copie le **token** (ex: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890`)

Ce token est **confidentiel** ! Ne le partage jamais publiquement.

---

## 📋 ÉTAPE 2 : Obtenir ton Chat ID

### 2.1 Méthode 1 : Via @userinfobot (Recommandé)

1. Cherche **`@userinfobot`** dans Telegram
2. Envoie `/start` au bot
3. Le bot répond avec ton **User ID** (ex: `123456789`)
4. **C'est ton Chat ID !** ✅

### 2.2 Méthode 2 : Via @getidsbot

1. Cherche **`@getidsbot`** dans Telegram
2. Envoie `/start` au bot
3. Le bot répond avec ton **ID** (ex: `Your ID: 123456789`)
4. **C'est ton Chat ID !** ✅

### 2.3 Méthode 3 : Via API Telegram (Avancé)

Si tu veux recevoir les notifications dans un **groupe** ou **channel** :

1. Ajoute ton bot au groupe/channel
2. Envoie un message dans le groupe/channel
3. Visite : `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Remplace `<TOKEN>` par ton token
4. Cherche `"chat":{"id":-123456789}` dans la réponse
5. Le nombre négatif est le Chat ID du groupe/channel

---

## 📋 ÉTAPE 3 : Configurer dans le Bot Trading

### 3.1 Méthode 1 : Variables d'Environnement (Recommandé)

#### Windows PowerShell

```powershell
# Définir variables d'environnement
$env:TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890"
$env:TELEGRAM_CHAT_ID="123456789"

# Lancer le bot
python main.py
```

#### Windows CMD

```cmd
set TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890
set TELEGRAM_CHAT_ID=123456789
python main.py
```

#### Linux/Mac

```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890"
export TELEGRAM_CHAT_ID="123456789"
python main.py
```

### 3.2 Méthode 2 : Fichier .env (Plus Sécurisé)

#### Créer fichier `.env`

```bash
# .env (à la racine du projet)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890
TELEGRAM_CHAT_ID=123456789
```

#### Modifier `config.py` pour charger .env

```python
# Ajouter en haut de config.py
from dotenv import load_dotenv
load_dotenv()

# Modifier les lignes Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", None)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", None)
```

**Installation** :
```bash
pip install python-dotenv
```

### 3.3 Méthode 3 : Directement dans `config.py` (Non Recommandé)

⚠️ **ATTENTION** : Ne commit jamais le token dans Git !

```python
# config.py
TELEGRAM_BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890"  # ⚠️ Risqué
TELEGRAM_CHAT_ID = "123456789"
```

**Ajouter au `.gitignore`** :
```
.env
config_local.py
```

---

## 📋 ÉTAPE 4 : Vérifier la Configuration

### 4.1 Lancer le Bot

```bash
python main.py
```

### 4.2 Vérifier les Logs

Tu devrais voir :
```
📱 Notification Manager initialisé (Telegram activé)
```

Si tu vois :
```
📱 Notification Manager initialisé (Telegram désactivé)
```

→ Vérifie que les variables d'environnement sont bien définies.

### 4.3 Tester avec une Position

1. Laisse le bot détecter un setup
2. Quand une position s'ouvre, tu devrais recevoir un message Telegram ✅

---

## 📱 TYPES DE NOTIFICATIONS

### 1. Position Ouverte

```
🟢 POSITION OUVERTE 🟢

📊 Symbole: BTC/USDT:USDT
📈 Direction: LONG
💰 Entry: 42000.50
💵 Size: 30.00 USDT

🎯 TP: 42252.30 (+0.60%)
🛡️ SL: 41895.20 (-0.25%)

🔍 Conditions: EMA, RSI, MACD, ADX

⏰ 23:15:42
```

### 2. Position Fermée

```
✅ POSITION FERMÉE ✅

📊 Symbole: BTC/USDT:USDT
📈 Direction: LONG
🚪 Raison: TP

🟢 PnL: +18.50 USDT (+0.62%)

⏱️ Durée: 2m 15s

⏰ 23:17:57
```

### 3. TP Escalier Niveau

```
🎯 TP ESCALIER Niveau 2/4 🎯

📊 Symbole: BTC/USDT:USDT
💰 Profit Partiel: +9.25 USDT (+0.31%)
📉 Restant: 50%

⏰ 23:16:30
```

### 4. Early Invalidation

```
⚡ EARLY INVALIDATION ⚡

📊 Symbole: ETH/USDT:USDT
📈 Direction: LONG
📉 PnL: -0.15%

⚠️ Position fermée rapidement (pas de réaction attendue)

⏰ 23:20:15
```

### 5. Erreur Système

```
🚨 ERREUR SYSTÈME 🚨

❌ Type: WebSocket Disconnection
📝 Détails: Connection lost, reconnecting...

⏰ 23:25:10
```

### 6. Reconnexion

```
🔄 RECONNEXION 🔄

🔌 Service: WebSocket
✅ Statut: Reconnecté avec succès

⏰ 23:25:12
```

### 7. Résumé Journalier

```
📊 RÉSUMÉ JOURNALIER 📊

📈 Trades: 12 (8W / 4L)
🎯 Winrate: 66.7%
💰 PnL Total: +45.30 USDT

🏆 Meilleur: +12.50 USDT
💔 Pire: -8.20 USDT

📅 2025-11-06
```

### 8. Recovery Mode

```
🛡️ RECOVERY MODE NIVEAU 2 🛡️

⏸️ Pause: 10 minutes
⚠️ Trading temporairement suspendu

⏰ 23:30:00
```

---

## 🔧 PERSONNALISATION

### Modifier le Throttling (Délai entre messages)

```python
# config.py
NOTIFICATION_THROTTLE_SECONDS = 5  # 5 secondes au lieu de 2
```

### Désactiver le Batching

```python
# config.py
NOTIFICATION_BATCHING_ENABLED = False  # Messages immédiats
```

### Modifier l'Intervalle de Batching

```python
# config.py
NOTIFICATION_BATCH_INTERVAL = 10  # 10 secondes au lieu de 5
```

---

## 🐛 DÉPANNAGE

### Problème : "Telegram désactivé"

**Cause** : Variables d'environnement non définies

**Solution** :
```powershell
# Vérifier
echo $env:TELEGRAM_BOT_TOKEN
echo $env:TELEGRAM_CHAT_ID

# Si vides, redéfinir
$env:TELEGRAM_BOT_TOKEN="TON_TOKEN"
$env:TELEGRAM_CHAT_ID="TON_CHAT_ID"
```

### Problème : "Unauthorized" ou "Invalid token"

**Cause** : Token incorrect

**Solution** :
1. Vérifie que tu as copié le token complet
2. Vérifie qu'il n'y a pas d'espaces avant/après
3. Recrée un bot si nécessaire (`/newbot` dans BotFather)

### Problème : "Chat not found"

**Cause** : Chat ID incorrect

**Solution** :
1. Vérifie ton Chat ID avec `@userinfobot`
2. Assure-toi que c'est un nombre (pas de guillemets)
3. Pour groupes : Assure-toi que le bot est ajouté au groupe

### Problème : Messages ne sont pas reçus

**Causes possibles** :
1. Bot pas démarré → Vérifie les logs
2. Throttling trop élevé → Réduis `NOTIFICATION_THROTTLE_SECONDS`
3. Batching activé → Attends quelques secondes ou désactive batching
4. Erreur silencieuse → Vérifie les logs du bot

### Problème : Trop de messages (Spam)

**Solution** :
```python
# Augmenter throttling
NOTIFICATION_THROTTLE_SECONDS = 5

# Activer batching
NOTIFICATION_BATCHING_ENABLED = True
NOTIFICATION_BATCH_INTERVAL = 10
```

---

## 🔒 SÉCURITÉ

### ⚠️ IMPORTANT : Ne Jamais Commit le Token

1. **Utilise `.gitignore`** :
   ```
   .env
   config_local.py
   *.env
   ```

2. **Vérifie avant commit** :
   ```bash
   git status
   # Vérifie qu'aucun fichier avec token n'est listé
   ```

3. **Si token commité par erreur** :
   - Change le token immédiatement dans BotFather (`/revoke` puis `/newbot`)
   - Supprime le token du commit (git history)

### 🔐 Bonnes Pratiques

1. ✅ Utilise variables d'environnement
2. ✅ Utilise fichier `.env` (non commité)
3. ✅ Limite accès au token (seulement toi)
4. ✅ Change le token régulièrement
5. ✅ Ne partage jamais le token publiquement

---

## 📊 STATISTIQUES NOTIFICATIONS

### Vérifier les Stats

```python
# Dans le code
from notifications import create_notification_manager

notifier = create_notification_manager(...)
stats = notifier.get_stats()

print(f"Messages envoyés: {stats['total_messages']}")
print(f"Réussis: {stats['successful']}")
print(f"Échoués: {stats['failed']}")
```

---

## 🎯 EXEMPLE COMPLET

### Setup Complet (Windows PowerShell)

```powershell
# 1. Créer bot Telegram (via @BotFather)
# Token reçu: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890

# 2. Obtenir Chat ID (via @userinfobot)
# Chat ID: 123456789

# 3. Configurer variables
$env:TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890"
$env:TELEGRAM_CHAT_ID="123456789"

# 4. Lancer bot
cd "C:\Users\sebta\Documents\code scalp\trade_cursor_py"
python main.py

# 5. Vérifier logs
# Tu devrais voir: "📱 Notification Manager initialisé (Telegram activé)"

# 6. Tester
# Attendre qu'une position s'ouvre
# Tu devrais recevoir un message Telegram ✅
```

---

## ✅ CHECKLIST FINALE

- [ ] Bot Telegram créé via @BotFather
- [ ] Token copié et sécurisé
- [ ] Chat ID obtenu via @userinfobot
- [ ] Variables d'environnement définies
- [ ] Bot trading lancé
- [ ] Logs montrent "Telegram activé"
- [ ] Message de test reçu ✅

---

## 🎉 C'EST PRÊT !

Une fois configuré, tu recevras automatiquement :
- ✅ Notifications position ouverte/fermée
- ✅ Alertes TP Escalier
- ✅ Erreurs système
- ✅ Résumés journaliers

**Bon trading avec notifications ! 📱🚀**


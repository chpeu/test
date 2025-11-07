# 📱 Guide : Commandes Telegram

## ✅ Système de Commandes Implémenté

Le bot Telegram peut maintenant recevoir et exécuter des commandes via webhook.

---

## 🔧 Configuration du Webhook

### 1. Prérequis

- ✅ Bot Telegram créé (via [@BotFather](https://t.me/BotFather))
- ✅ `TELEGRAM_BOT_TOKEN` configuré dans `.env`
- ✅ Bot accessible publiquement (pour production) ou via tunnel (pour développement)

### 2. Configuration du Webhook

#### Option A : Production (bot accessible publiquement)

```bash
# Configurer le webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://votre-domaine.com/api/telegram/webhook"

# Vérifier le webhook
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

#### Option B : Développement Local (avec ngrok)

```bash
# 1. Installer ngrok
# https://ngrok.com/download

# 2. Démarrer ngrok (exposer le port 5000)
ngrok http 5000

# 3. Récupérer l'URL (ex: https://abc123.ngrok.io)

# 4. Configurer le webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://abc123.ngrok.io/api/telegram/webhook"

# 5. Vérifier
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

### 3. Vérification

Accéder à `/api/telegram/webhook/info` pour voir les instructions détaillées :
```
http://localhost:5000/api/telegram/webhook/info
```

---

## 📋 Commandes Disponibles

### `/help` ou `/start`
Affiche la liste des commandes disponibles.

**Exemple** :
```
/help
```

**Réponse** :
```
📱 **COMMANDES DISPONIBLES** [Instance 5000]

/help - Afficher cette aide
/stats - Statistiques de la session
/report - Rapport détaillé (trades, winrate, PnL)
/status - État actuel (position active, scanner)
/trades - Derniers 10 trades

💡 **Exemple**: Envoyez `/stats` pour voir les statistiques

⏰ 14:32:15
```

---

### `/stats`
Affiche les statistiques globales de la session.

**Exemple** :
```
/stats
```

**Réponse** :
```
📊 **STATISTIQUES** [Instance 5000]

📈 **Total Trades**: 25
✅ **Wins**: 18
❌ **Losses**: 7
🎯 **Winrate**: 72.0%

💰 **PnL Total**: +45.32 USDT (+2.27%)

🏆 **Meilleur Trade**: +8.50 USDT
💔 **Pire Trade**: -3.20 USDT

📅 **Aujourd'hui**: 5 trades | +12.50 USDT

⏰ 14:32:15
```

---

### `/report`
Affiche un rapport détaillé avec statistiques par direction, raisons de fermeture, etc.

**Exemple** :
```
/report
```

**Réponse** :
```
📊 **RAPPORT DÉTAILLÉ** [Instance 5000]

📈 **GLOBAL**
• Trades: 25 (18W / 7L)
• Winrate: 72.0%
• PnL Total: +45.32 USDT (+2.27%)
• Durée moyenne: 3m 45s

📊 **PAR DIRECTION**
• LONG: 15 trades | +28.50 USDT
• SHORT: 10 trades | +16.82 USDT

🎯 **TOP 5 RAISONS DE FERMETURE**
• 🎯 TP: 12 trades | +35.20 USDT
• 📈 TS: 6 trades | +18.50 USDT
• 🛑 SL: 7 trades | -8.38 USDT
• ⚡ EARLY_INVALIDATION: 2 trades | -2.00 USDT
• ⏱️ TIMEOUT: 1 trade | -1.00 USDT

⏰ 2025-01-07 14:32:15
```

---

### `/status`
Affiche l'état actuel du bot (position active, scanner).

**Exemple** :
```
/status
```

**Réponse** (avec position active) :
```
📡 **STATUT** [Instance 5000]

🟢 **POSITION ACTIVE**
• Symbole: `BTC/USDT:USDT`
• Direction: LONG
• Entry: 43250.000000
• TP: 43358.125000
• SL: 43242.187500
• Size: 30.00 USDT
• Durée: 2m 15s

🔍 **Scanner**: ❓ Inconnu

⏰ 14:32:15
```

**Réponse** (sans position active) :
```
📡 **STATUT** [Instance 5000]

⚪ **Aucune position active**

🔍 **Scanner**: ❓ Inconnu

⏰ 14:32:15
```

---

### `/trades`
Affiche les 10 derniers trades.

**Exemple** :
```
/trades
```

**Réponse** :
```
📋 **DERNIERS 10 TRADES** [Instance 5000]

1. ✅ BTC/USDT:USDT LONG
   🎯 TP | +5.20 USDT (+0.17%)
   📅 2025-01-07 14:30:00

2. ✅ ETH/USDT:USDT SHORT
   📈 TS | +3.50 USDT (+0.12%)
   📅 2025-01-07 14:25:00

3. ❌ SOL/USDT:USDT LONG
   🛑 SL | -2.10 USDT (-0.07%)
   📅 2025-01-07 14:20:00

...

⏰ 14:32:15
```

---

## 🔍 Détails Techniques

### Endpoint Webhook

**URL** : `POST /api/telegram/webhook`

**Format Telegram Update** :
```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 1,
    "from": {
      "id": 123456789,
      "is_bot": false,
      "first_name": "John"
    },
    "chat": {
      "id": 123456789,
      "type": "private"
    },
    "date": 1234567890,
    "text": "/stats"
  }
}
```

### Gestion des Commandes

1. **Réception** : Le webhook reçoit l'update Telegram
2. **Parsing** : Extraction de la commande et du `chat_id`
3. **Exécution** : Le `TelegramCommandHandler` exécute la commande
4. **Réponse** : Envoi de la réponse via l'API Telegram directement

### Multi-Instances

Chaque instance affiche son port dans les réponses :
- `[Instance 5000]` pour l'instance sur le port 5000
- `[Instance 5001]` pour l'instance sur le port 5001
- etc.

Cela permet d'identifier facilement quelle instance répond.

---

## 🚀 Utilisation

1. **Configurer le webhook** (voir section Configuration)
2. **Envoyer une commande** dans Telegram :
   ```
   /help
   ```
3. **Recevoir la réponse** automatiquement

---

## ⚠️ Notes Importantes

- **Sécurité** : Le webhook est public. Pour la production, ajouter une authentification.
- **Rate Limiting** : Les réponses aux commandes ne sont pas throttlées (bypass_throttle=True).
- **Chat ID** : Le bot répond au `chat_id` qui a envoyé la commande (pas forcément le chat_id configuré dans `.env`).
- **Multi-Instances** : Chaque instance peut recevoir des commandes indépendamment.

---

## 🔧 Dépannage

### Le webhook ne reçoit pas les commandes

1. Vérifier que le webhook est configuré :
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
   ```

2. Vérifier les logs du bot pour voir si les updates arrivent

3. Tester le webhook manuellement :
   ```bash
   curl -X POST "http://localhost:5000/api/telegram/webhook" \
     -H "Content-Type: application/json" \
     -d '{"update_id": 1, "message": {"chat": {"id": 123456789}, "text": "/help"}}'
   ```

### Les réponses ne sont pas envoyées

1. Vérifier que `TELEGRAM_BOT_TOKEN` est configuré
2. Vérifier les logs pour les erreurs d'API Telegram
3. Vérifier que le bot a les permissions pour envoyer des messages

---

*Document créé le : 2025-01-07*


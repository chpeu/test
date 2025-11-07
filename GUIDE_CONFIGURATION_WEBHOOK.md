# 🔧 Guide : Configuration Webhook Telegram

## ⚠️ Problème Actuel

L'erreur **405 Method Not Allowed** indique que :
1. Le webhook est configuré avec une URL placeholder (`votre-domaine.com`)
2. Le serveur n'est pas accessible publiquement
3. L'URL doit pointer vers votre serveur réel

---

## ✅ Solution : Configurer le Webhook Correctement

### Option 1 : Production (Serveur Accessible Publiquement)

Si votre bot tourne sur un serveur avec une URL publique :

```bash
# 1. Remplacer "votre-domaine.com" par votre vraie URL
# Exemple : https://mon-serveur.com/api/telegram/webhook

# 2. Configurer le webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://mon-serveur.com/api/telegram/webhook"

# 3. Vérifier
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

---

### Option 2 : Développement Local (avec ngrok)

Pour tester en local, utiliser **ngrok** pour exposer votre serveur :

#### Étape 1 : Installer ngrok

1. Télécharger depuis : https://ngrok.com/download
2. Extraire l'exécutable
3. Ajouter au PATH (optionnel)

#### Étape 2 : Démarrer ngrok

```bash
# Exposer le port 5000 (ou le port de votre instance)
ngrok http 5000
```

**Résultat** :
```
Forwarding    https://abc123.ngrok.io -> http://localhost:5000
```

#### Étape 3 : Configurer le Webhook

```bash
# Utiliser l'URL ngrok (remplacer abc123.ngrok.io par votre URL)
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://abc123.ngrok.io/api/telegram/webhook"
```

#### Étape 4 : Vérifier

```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

**Résultat attendu** :
```json
{
  "ok": true,
  "result": {
    "url": "https://abc123.ngrok.io/api/telegram/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "last_error_date": 0,
    "last_error_message": "",
    "max_connections": 40
  }
}
```

---

### Option 3 : Désactiver le Webhook (Polling)

Si vous ne voulez pas utiliser de webhook, vous pouvez désactiver le webhook et utiliser le polling :

```bash
# Désactiver le webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/deleteWebhook"

# Vérifier
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

**Note** : Le polling nécessite une implémentation supplémentaire (non implémenté actuellement).

---

## 🔍 Vérification de l'Endpoint

### Tester l'endpoint localement

```bash
# Tester que l'endpoint répond bien en POST
curl -X POST "http://localhost:5000/api/telegram/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "update_id": 1,
    "message": {
      "message_id": 1,
      "from": {"id": 123456789, "is_bot": false, "first_name": "Test"},
      "chat": {"id": 123456789, "type": "private"},
      "date": 1234567890,
      "text": "/help"
    }
  }'
```

**Résultat attendu** : `{"ok": true}`

### Vérifier les logs du bot

Si le webhook fonctionne, vous devriez voir dans les logs :
```
✅ Réponse Telegram envoyée à chat_id 123456789
```

---

## 🚨 Erreurs Courantes

### 1. Erreur 405 Method Not Allowed

**Cause** : L'URL du webhook pointe vers un serveur qui n'accepte pas POST, ou l'URL est incorrecte.

**Solution** :
- Vérifier que l'URL pointe vers `/api/telegram/webhook`
- Vérifier que le serveur est accessible
- Utiliser ngrok pour le développement local

### 2. Erreur 404 Not Found

**Cause** : L'endpoint n'existe pas ou l'URL est mal formée.

**Solution** :
- Vérifier que `app.include_router(api_router)` est appelé dans `main.py`
- Vérifier que l'URL est `https://votre-domaine.com/api/telegram/webhook` (avec `/api/`)

### 3. Erreur SSL/Certificate

**Cause** : Le certificat SSL n'est pas valide (ngrok utilise un certificat valide).

**Solution** :
- Utiliser HTTPS (obligatoire pour Telegram)
- Vérifier que le certificat est valide

---

## 📋 Checklist

- [ ] Bot Telegram créé (via @BotFather)
- [ ] `TELEGRAM_BOT_TOKEN` configuré dans `.env`
- [ ] Serveur accessible publiquement OU ngrok configuré
- [ ] Webhook configuré avec la bonne URL
- [ ] Webhook vérifié avec `getWebhookInfo`
- [ ] Endpoint testé localement avec `curl`
- [ ] Bot redémarré après configuration

---

## 🔧 Commandes Utiles

### Vérifier le webhook actuel
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

### Configurer le webhook
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://votre-url.com/api/telegram/webhook"
```

### Supprimer le webhook
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/deleteWebhook"
```

### Tester l'endpoint localement
```bash
curl -X POST "http://localhost:5000/api/telegram/webhook" \
  -H "Content-Type: application/json" \
  -d '{"update_id": 1, "message": {"chat": {"id": 123456789}, "text": "/help"}}'
```

---

## 🎯 Exemple Complet (ngrok)

```bash
# 1. Démarrer le bot
python main.py 5000

# 2. Dans un autre terminal, démarrer ngrok
ngrok http 5000

# 3. Copier l'URL HTTPS (ex: https://abc123.ngrok.io)

# 4. Configurer le webhook
curl -X POST "https://api.telegram.org/bot8595258034:AAG1EUKLY3wuQPuRhkg5ttJ90e7f9zya2A8/setWebhook?url=https://abc123.ngrok.io/api/telegram/webhook"

# 5. Vérifier
curl "https://api.telegram.org/bot8595258034:AAG1EUKLY3wuQPuRhkg5ttJ90e7f9zya2A8/getWebhookInfo"

# 6. Tester dans Telegram
# Envoyer /help au bot
```

---

## ⚠️ Notes Importantes

1. **HTTPS obligatoire** : Telegram exige HTTPS pour les webhooks
2. **URL complète** : L'URL doit inclure `/api/telegram/webhook`
3. **Port** : Si vous utilisez un port autre que 80/443, l'inclure dans l'URL (ex: `https://domaine.com:5000/api/telegram/webhook`)
4. **ngrok gratuit** : La version gratuite change l'URL à chaque redémarrage
5. **Multi-instances** : Chaque instance doit avoir son propre webhook (ou utiliser un reverse proxy)

---

*Document créé le : 2025-01-07*


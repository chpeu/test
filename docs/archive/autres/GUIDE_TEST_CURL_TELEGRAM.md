# 📱 Guide : Tester Telegram avec cURL

**Explication détaillée de la commande curl pour tester l'API Telegram**

---

## 🔍 QU'EST-CE QUE cURL ?

**cURL** est un outil en ligne de commande pour faire des requêtes HTTP. Il permet de tester des APIs directement depuis le terminal.

**Disponibilité** :
- ✅ **Windows 10/11** : Inclus par défaut (PowerShell ou CMD)
- ✅ **Linux/Mac** : Inclus par défaut
- ✅ **Alternative** : Si pas disponible, installer depuis [curl.se](https://curl.se/)

---

## 📝 COMMANDE COMPLÈTE EXPLIQUÉE

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": <CHAT_ID>, "text": "Test"}'
```

### **Décomposition ligne par ligne** :

#### **Ligne 1 : `curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage"`**

- `curl` : Commande cURL
- `-X POST` : Méthode HTTP POST (envoyer des données)
- `"https://api.telegram.org/bot<TOKEN>/sendMessage"` : URL de l'API Telegram
  - `https://api.telegram.org` : Serveur API Telegram
  - `/bot<TOKEN>` : Endpoint avec votre token de bot
  - `/sendMessage` : Action à effectuer (envoyer un message)
  - **⚠️ IMPORTANT** : Remplacer `<TOKEN>` par votre vrai token (ex: `123456789:ABC-DEF...`)

#### **Ligne 2 : `-H "Content-Type: application/json"`**

- `-H` : Option pour ajouter un header HTTP
- `"Content-Type: application/json"` : Indique que les données envoyées sont au format JSON
- **Nécessaire** : L'API Telegram attend du JSON

#### **Ligne 3 : `-d '{"chat_id": <CHAT_ID>, "text": "Test"}'`**

- `-d` : Option pour envoyer des données (body de la requête)
- `'{"chat_id": <CHAT_ID>, "text": "Test"}'` : Données JSON
  - `chat_id` : ID du chat où envoyer le message
  - `text` : Texte du message à envoyer
  - **⚠️ IMPORTANT** : Remplacer `<CHAT_ID>` par votre vrai Chat ID (ex: `1488999617` ou `-123456789`)

#### **Le `\` à la fin des lignes 1 et 2**

- `\` : Permet de continuer la commande sur la ligne suivante (pour lisibilité)
- **Windows PowerShell** : Peut nécessiter un ` (backtick) au lieu de `\`
- **Alternative** : Écrire la commande sur une seule ligne (sans `\`)

---

## 🔧 EXEMPLES CONCRETS

### **Exemple 1 : Chat Privé (Chat ID positif)**

**Token** : `123456789:ABC-DEF123456ghIkl-zyx57W2v1u123ew11`  
**Chat ID** : `1488999617`

**Commande** :
```bash
curl -X POST "https://api.telegram.org/bot123456789:ABC-DEF123456ghIkl-zyx57W2v1u123ew11/sendMessage" -H "Content-Type: application/json" -d "{\"chat_id\": 1488999617, \"text\": \"Test depuis curl\"}"
```

**Version multi-lignes (Linux/Mac)** :
```bash
curl -X POST "https://api.telegram.org/bot123456789:ABC-DEF123456ghIkl-zyx57W2v1u123ew11/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": 1488999617, "text": "Test depuis curl"}'
```

**Version PowerShell (Windows)** :
```powershell
curl.exe -X POST "https://api.telegram.org/bot123456789:ABC-DEF123456ghIkl-zyx57W2v1u123ew11/sendMessage" `
  -H "Content-Type: application/json" `
  -d '{\"chat_id\": 1488999617, \"text\": \"Test depuis curl\"}'
```

### **Exemple 2 : Groupe (Chat ID négatif)**

**Token** : `123456789:ABC-DEF123456ghIkl-zyx57W2v1u123ew11`  
**Chat ID** : `-123456789` (groupe)

**Commande** :
```bash
curl -X POST "https://api.telegram.org/bot123456789:ABC-DEF123456ghIkl-zyx57W2v1u123ew11/sendMessage" -H "Content-Type: application/json" -d "{\"chat_id\": -123456789, \"text\": \"Test depuis curl\"}"
```

---

## 💻 COMMENT EXÉCUTER

### **Windows PowerShell**

1. **Ouvrir PowerShell**
2. **Copier-coller la commande** (remplacer `<TOKEN>` et `<CHAT_ID>`)
3. **Appuyer sur Entrée**

**Note** : Si `curl` ne fonctionne pas, utiliser `curl.exe` à la place.

### **Windows CMD**

1. **Ouvrir CMD**
2. **Copier-coller la commande** (remplacer `<TOKEN>` et `<CHAT_ID>`)
3. **Appuyer sur Entrée**

### **Linux/Mac Terminal**

1. **Ouvrir Terminal**
2. **Copier-coller la commande** (remplacer `<TOKEN>` et `<CHAT_ID>`)
3. **Appuyer sur Entrée**

---

## 📊 INTERPRÉTER LES RÉSULTATS

### **✅ Succès**

**Réponse** :
```json
{
  "ok": true,
  "result": {
    "message_id": 123,
    "from": {
      "id": 123456789,
      "is_bot": true,
      "first_name": "Votre Bot",
      "username": "votre_bot"
    },
    "chat": {
      "id": 1488999617,
      "first_name": "Votre Nom",
      "type": "private"
    },
    "date": 1234567890,
    "text": "Test depuis curl"
  }
}
```

**Signification** : ✅ **Message envoyé avec succès !** Vérifier Telegram pour voir le message.

---

### **❌ Erreur : "chat not found"**

**Réponse** :
```json
{
  "ok": false,
  "error_code": 400,
  "description": "Bad Request: chat not found"
}
```

**Causes possibles** :
1. ❌ Chat ID incorrect
2. ❌ Bot pas ajouté au chat/groupe
3. ❌ Chat ID au format string au lieu de nombre

**Solutions** :
- Vérifier Chat ID via `@userinfobot`
- Ajouter le bot au chat/groupe
- Vérifier que Chat ID est un nombre (pas une string)

---

### **❌ Erreur : "bot is not a member"**

**Réponse** :
```json
{
  "ok": false,
  "error_code": 403,
  "description": "Forbidden: bot is not a member of the group"
}
```

**Cause** : Bot pas dans le groupe

**Solution** : Ajouter le bot au groupe

---

### **❌ Erreur : "Unauthorized"**

**Réponse** :
```json
{
  "ok": false,
  "error_code": 401,
  "description": "Unauthorized"
}
```

**Cause** : Token invalide ou expiré

**Solution** : Vérifier le token via `@BotFather` → `/mybots`

---

## 🔐 SÉCURITÉ : NE PAS EXPOSER LE TOKEN

**⚠️ IMPORTANT** : Ne jamais partager votre token publiquement !

**Bonnes pratiques** :
- ✅ Utiliser des variables d'environnement
- ✅ Ne pas commit le token dans Git
- ✅ Utiliser un fichier `.env` (non commité)

**Exemple avec variable d'environnement** :

**Windows PowerShell** :
```powershell
$env:TELEGRAM_TOKEN = "123456789:ABC-DEF..."
$env:TELEGRAM_CHAT_ID = "1488999617"
curl.exe -X POST "https://api.telegram.org/bot$env:TELEGRAM_TOKEN/sendMessage" -H "Content-Type: application/json" -d "{\"chat_id\": $env:TELEGRAM_CHAT_ID, \"text\": \"Test\"}"
```

**Linux/Mac** :
```bash
export TELEGRAM_TOKEN="123456789:ABC-DEF..."
export TELEGRAM_CHAT_ID="1488999617"
curl -X POST "https://api.telegram.org/bot$TELEGRAM_TOKEN/sendMessage" -H "Content-Type: application/json" -d "{\"chat_id\": $TELEGRAM_CHAT_ID, \"text\": \"Test\"}"
```

---

## 🧪 TEST RAPIDE

**Étapes** :

1. **Récupérer Token** :
   - Ouvrir Telegram
   - Chercher `@BotFather`
   - Envoyer `/mybots`
   - Sélectionner votre bot
   - Cliquer sur "API Token"
   - Copier le token

2. **Récupérer Chat ID** :
   - Ouvrir Telegram
   - Chercher `@userinfobot`
   - Envoyer `/start`
   - Copier le Chat ID affiché

3. **Tester** :
   - Ouvrir PowerShell/CMD/Terminal
   - Remplacer `<TOKEN>` et `<CHAT_ID>` dans la commande
   - Exécuter la commande
   - Vérifier Telegram : message reçu ✅

---

## 📝 EXEMPLE COMPLET (Copier-Coller)

**Remplacez** :
- `YOUR_BOT_TOKEN` par votre token
- `YOUR_CHAT_ID` par votre Chat ID

**Windows PowerShell** :
```powershell
curl.exe -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage" -H "Content-Type: application/json" -d "{\"chat_id\": YOUR_CHAT_ID, \"text\": \"✅ Test depuis curl !\"}"
```

**Linux/Mac** :
```bash
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": YOUR_CHAT_ID, "text": "✅ Test depuis curl !"}'
```

---

## 🎯 RÉSUMÉ

1. **cURL** : Outil pour tester des APIs HTTP
2. **Remplacer** : `<TOKEN>` par votre Bot Token, `<CHAT_ID>` par votre Chat ID
3. **Exécuter** : Dans PowerShell/CMD/Terminal
4. **Vérifier** : Réponse `{"ok":true}` = succès ✅
5. **Erreur** : Vérifier Chat ID, Token, ou bot ajouté

**Bon test ! 🚀**


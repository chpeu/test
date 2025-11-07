# 📱 Guide de Vérification Telegram

**Comment vérifier que le bot est correctement configuré et ajouté**

---

## 🔍 1. VÉRIFIER QUE LE BOT EST AJOUTÉ AU CHAT/GROUPE

### **Pour un Chat Privé (1-to-1)**

Si vous utilisez votre Chat ID personnel (`1488999617`), le bot doit être dans votre liste de conversations :

1. **Ouvrir Telegram**
2. **Chercher le nom de votre bot** dans la liste de conversations
3. **Si le bot n'apparaît pas** :
   - Ouvrir une conversation avec le bot (chercher son nom via @BotFather)
   - Envoyer `/start` au bot
   - Le bot devrait répondre

### **Pour un Groupe**

Si vous utilisez un Chat ID de groupe (négatif, ex: `-123456789`) :

1. **Ouvrir le groupe Telegram**
2. **Vérifier les membres** :
   - Cliquer sur le nom du groupe (en haut)
   - Aller dans "Membres" ou "Participants"
   - **Chercher votre bot** dans la liste
3. **Si le bot n'est pas dans le groupe** :
   - Cliquer sur "Ajouter des membres"
   - Chercher votre bot par son nom (ex: `@votre_bot`)
   - Ajouter le bot au groupe

### **Pour un Channel**

Si vous utilisez un Chat ID de channel (négatif, ex: `-1001234567890`) :

1. **Ouvrir le channel Telegram**
2. **Vérifier les administrateurs** :
   - Cliquer sur le nom du channel (en haut)
   - Aller dans "Administrateurs"
   - **Chercher votre bot** dans la liste
3. **Si le bot n'est pas administrateur** :
   - Cliquer sur "Ajouter un administrateur"
   - Chercher votre bot par son nom
   - **Donner la permission "Envoyer des messages"** au minimum
   - Ajouter le bot

---

## 🔧 2. VÉRIFIER LES PERMISSIONS DU BOT

### **Dans un Groupe**

Le bot doit avoir la permission d'**envoyer des messages** :

1. **Ouvrir le groupe**
2. **Cliquer sur le nom du groupe** (en haut)
3. **Aller dans "Permissions"** ou "Paramètres"
4. **Vérifier que le bot peut** :
   - ✅ Envoyer des messages
   - ✅ (Optionnel) Envoyer des médias
   - ✅ (Optionnel) Ajouter des liens

### **Dans un Channel**

Le bot doit être **administrateur** avec la permission d'**envoyer des messages** :

1. **Ouvrir le channel**
2. **Cliquer sur le nom du channel** (en haut)
3. **Aller dans "Administrateurs"**
4. **Vérifier que le bot est administrateur** avec :
   - ✅ Permission "Envoyer des messages"
   - ✅ (Optionnel) Permission "Modifier les messages"

---

## 🧪 3. TESTER DIRECTEMENT L'API TELEGRAM

### **Méthode 1 : Via cURL (Terminal)**

```bash
# Remplacer <TOKEN> et <CHAT_ID> par vos valeurs
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": <CHAT_ID>, "text": "Test depuis terminal"}'
```

**Exemple** :
```bash
curl -X POST "https://api.telegram.org/bot123456789:ABC-DEF.../sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": 1488999617, "text": "Test depuis terminal"}'
```

**Résultats possibles** :
- ✅ `{"ok":true,"result":{...}}` → **Bot fonctionne !**
- ❌ `{"ok":false,"error_code":400,"description":"Bad Request: chat not found"}` → **Bot pas ajouté ou Chat ID incorrect**
- ❌ `{"ok":false,"error_code":403,"description":"Forbidden: bot is not a member of the group"}` → **Bot pas dans le groupe**
- ❌ `{"ok":false,"error_code":401,"description":"Unauthorized"}` → **Token invalide**

### **Méthode 2 : Via Python (Script de test)**

Créer un fichier `test_telegram.py` :

```python
import requests
import os

# Remplacer par vos valeurs
BOT_TOKEN = "123456789:ABC-DEF..."
CHAT_ID = 1488999617  # ou "-123456789" pour groupe

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

payload = {
    "chat_id": CHAT_ID,
    "text": "✅ Test depuis Python !"
}

response = requests.post(url, json=payload)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

if response.status_code == 200:
    print("✅ Message envoyé avec succès !")
else:
    error = response.json()
    print(f"❌ Erreur: {error.get('description', 'Unknown error')}")
```

**Exécuter** :
```bash
python test_telegram.py
```

### **Méthode 3 : Via l'Interface Web (`/settings`)**

1. **Aller sur** `http://localhost:5000/settings`
2. **Remplir** :
   - Bot Token
   - Chat ID
3. **Cliquer sur "📱 Tester Telegram"**
4. **Vérifier le résultat** :
   - ✅ Message reçu → **Bot fonctionne !**
   - ❌ Erreur "chat not found" → **Bot pas ajouté ou Chat ID incorrect**

---

## 🔎 4. VÉRIFIER LE CHAT ID

### **Pour un Chat Privé (1-to-1)**

1. **Ouvrir Telegram**
2. **Chercher** `@userinfobot`
3. **Démarrer une conversation** avec `@userinfobot`
4. **Envoyer** `/start`
5. **Le bot répondra avec votre Chat ID** (ex: `1488999617`)

### **Pour un Groupe**

1. **Ajouter** `@userinfobot` au groupe
2. **Envoyer** `/start` dans le groupe
3. **Le bot répondra avec le Chat ID du groupe** (négatif, ex: `-123456789`)

### **Pour un Channel**

1. **Ajouter** `@userinfobot` au channel (comme administrateur)
2. **Envoyer** `/start` dans le channel
3. **Le bot répondra avec le Chat ID du channel** (négatif, ex: `-1001234567890`)

**Note** : Les Chat IDs de groupes/channels sont **négatifs** et commencent souvent par `-100` pour les channels.

---

## 🔑 5. VÉRIFIER LE BOT TOKEN

1. **Ouvrir Telegram**
2. **Chercher** `@BotFather`
3. **Envoyer** `/mybots`
4. **Sélectionner votre bot**
5. **Cliquer sur "API Token"**
6. **Vérifier que le token correspond** à celui dans vos paramètres

**Format du token** : `123456789:ABC-DEF123456ghIkl-zyx57W2v1u123ew11`

---

## 🐛 6. DIAGNOSTIQUER LES ERREURS COURANTES

### **Erreur : "Bad Request: chat not found"**

**Causes possibles** :
1. ❌ **Chat ID incorrect** → Vérifier via `@userinfobot`
2. ❌ **Bot pas ajouté au chat/groupe** → Ajouter le bot
3. ❌ **Chat ID au format string au lieu de nombre** → Parser en `int`

**Solutions** :
- Vérifier Chat ID via `@userinfobot`
- Ajouter le bot au chat/groupe/channel
- Vérifier que le Chat ID est bien un nombre (pas une string)

### **Erreur : "Forbidden: bot is not a member of the group"**

**Cause** : Le bot n'est pas membre du groupe

**Solution** :
1. Ouvrir le groupe
2. Ajouter le bot au groupe (via "Ajouter des membres")
3. Vérifier que le bot apparaît dans la liste des membres

### **Erreur : "Unauthorized"**

**Cause** : Token invalide ou expiré

**Solution** :
1. Vérifier le token via `@BotFather` → `/mybots`
2. Régénérer le token si nécessaire
3. Mettre à jour le token dans les paramètres

### **Erreur : "Forbidden: bot was blocked by the user"**

**Cause** : L'utilisateur a bloqué le bot (chat privé)

**Solution** :
1. Débloquer le bot dans Telegram
2. Envoyer `/start` au bot
3. Réessayer

---

## ✅ 7. CHECKLIST DE VÉRIFICATION

Avant de tester, vérifier :

- [ ] **Bot Token** : Vérifié via `@BotFather` → `/mybots`
- [ ] **Chat ID** : Vérifié via `@userinfobot`
- [ ] **Bot ajouté** : Bot visible dans la liste de conversations (chat privé) OU dans les membres (groupe) OU dans les administrateurs (channel)
- [ ] **Permissions** : Bot peut envoyer des messages (groupe/channel)
- [ ] **Format Chat ID** : Nombre (pas string), négatif pour groupes/channels
- [ ] **Variables d'environnement** : `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` définies (si utilisées)

---

## 🚀 8. TEST FINAL

Une fois tout vérifié :

1. **Redémarrer le bot** (pour charger les nouvelles variables d'environnement)
2. **Aller sur** `http://localhost:5000/settings`
3. **Remplir** Token et Chat ID
4. **Cliquer sur "📱 Tester Telegram"**
5. **Vérifier Telegram** : Message reçu ✅

**Si ça ne fonctionne toujours pas** :
- Vérifier les logs backend pour erreurs détaillées
- Tester via cURL pour voir l'erreur exacte de l'API Telegram
- Vérifier que le bot n'est pas bloqué

---

## 📝 NOTES IMPORTANTES

1. **Chat ID de groupe** : Doit être **négatif** (ex: `-123456789`)
2. **Chat ID de channel** : Doit être **négatif** et souvent commence par `-100` (ex: `-1001234567890`)
3. **Chat ID privé** : **Positif** (ex: `1488999617`)
4. **Bot dans groupe** : Le bot doit être **membre** du groupe (pas juste invité)
5. **Bot dans channel** : Le bot doit être **administrateur** avec permission "Envoyer des messages"

---

**Bon test ! 🎉**


# 📱 Guide : Utiliser le même bot Telegram sur plusieurs instances

## ✅ Réponse courte

**Oui, vous pouvez utiliser le même bot Telegram sur plusieurs instances**, mais il faut faire attention aux **doublons de notifications**.

---

## 🔍 Comportement actuel

### Comment ça fonctionne

1. **Chaque instance** utilise le même `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`
2. **Toutes les instances** envoient leurs notifications au **même chat Telegram**
3. **Résultat** : Vous recevez toutes les notifications de toutes les instances dans le même chat

### ⚠️ Problèmes potentiels

1. **Doublons de notifications** :
   - Si plusieurs instances détectent le même setup, vous recevrez plusieurs notifications
   - Si plusieurs instances ouvrent/ferment des positions, vous recevrez plusieurs notifications

2. **Confusion** :
   - Difficile de savoir quelle instance a envoyé quelle notification
   - Pas de distinction visuelle entre les instances

3. **Spam** :
   - Si vous avez 3 instances qui scannent, vous pouvez recevoir 3x plus de notifications

---

## 🎯 Solutions recommandées

### Solution 1 : Préfixe d'instance dans les messages (Recommandé)

**Modifier les notifications pour inclure le port/ID de l'instance** :

```python
# Dans notifications/telegram_notifier.py
message = f"""
🟢 **POSITION OUVERTE** [Instance {instance_port}] 🟢

📊 **Symbole**: `{symbol}`
...
"""
```

**Avantages** :
- ✅ Facile à identifier quelle instance a envoyé
- ✅ Pas besoin de créer plusieurs bots
- ✅ Toutes les notifications dans un seul chat

**Inconvénients** :
- ⚠️ Peut être verbeux si beaucoup d'instances

---

### Solution 2 : Chats différents par instance

**Utiliser des chats/groups différents pour chaque instance** :

```bash
# Instance 1 (port 5000)
TELEGRAM_CHAT_ID=-1001234567890  # Groupe 1

# Instance 2 (port 5001)
TELEGRAM_CHAT_ID=-1001234567891  # Groupe 2

# Instance 3 (port 5002)
TELEGRAM_CHAT_ID=-1001234567892  # Groupe 3
```

**Avantages** :
- ✅ Notifications complètement séparées
- ✅ Facile à gérer chaque instance indépendamment

**Inconvénients** :
- ⚠️ Besoin de créer plusieurs groupes/chats
- ⚠️ Plus de chats à surveiller

---

### Solution 3 : Filtrer les notifications par instance

**Désactiver Telegram sur certaines instances** :

```bash
# Instance 1 (port 5000) - Telegram activé
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789

# Instance 2 (port 5001) - Telegram désactivé
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Instance 3 (port 5002) - Telegram désactivé
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

**Avantages** :
- ✅ Pas de doublons
- ✅ Simple à configurer

**Inconvénients** :
- ⚠️ Pas de notifications pour certaines instances

---

## 🔧 Implémentation : Préfixe d'instance

### Étape 1 : Modifier `telegram_notifier.py`

```python
# Dans notifications/telegram_notifier.py
class TelegramNotifier:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[Union[str, int]] = None,
        enabled: bool = True,
        throttle_seconds: int = 2,
        instance_id: Optional[str] = None  # 🔥 NOUVEAU
    ):
        self.instance_id = instance_id  # Ex: "5000", "5001", etc.
        # ...
    
    def _format_message(self, message: str) -> str:
        """Ajouter préfixe instance si disponible"""
        if self.instance_id:
            return f"[Instance {self.instance_id}] {message}"
        return message
```

### Étape 2 : Passer `instance_id` depuis `main.py`

```python
# Dans main.py
instance_port = os.getenv("PORT", "5000")

notification_manager = create_notification_manager(
    telegram_bot_token=TELEGRAM_BOT_TOKEN,
    telegram_chat_id=TELEGRAM_CHAT_ID,
    socketio_callback=socketio_callback,
    enable_batching=NOTIFICATION_BATCHING_ENABLED,
    instance_id=str(instance_port)  # 🔥 NOUVEAU
)
```

---

## 💾 Sauvegarde des tokens

### Méthode 1 : Fichier `.env` (Recommandé)

**Créer fichier `.env` à la racine du projet** :

```bash
# .env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890
TELEGRAM_CHAT_ID=123456789
```

**Le fichier `.env` est automatiquement chargé au démarrage** (via `python-dotenv`).

**⚠️ Important** : Ajouter `.env` au `.gitignore` :

```
.env
*.env
```

### Méthode 2 : Variables d'environnement système

**Windows PowerShell** :
```powershell
$env:TELEGRAM_BOT_TOKEN="123456789:ABC-DEF..."
$env:TELEGRAM_CHAT_ID="123456789"
python main.py
```

**Linux/Mac** :
```bash
export TELEGRAM_BOT_TOKEN="123456789:ABC-DEF..."
export TELEGRAM_CHAT_ID="123456789"
python main.py
```

### Méthode 3 : Interface web `/settings`

**Utiliser l'interface web** :
1. Aller sur `http://localhost:5000/settings`
2. Remplir Token et Chat ID
3. Cliquer "💾 Sauvegarder"
4. Les paramètres sont sauvegardés dans `.env`
5. **Redémarrer le bot** pour appliquer

---

## 📋 Configuration multi-instances

### Exemple : 3 instances avec même bot

**Instance 1 (port 5000)** :
```bash
# .env (ou variables d'environnement)
PORT=5000
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

**Instance 2 (port 5001)** :
```bash
# .env (ou variables d'environnement)
PORT=5001
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...  # Même token
TELEGRAM_CHAT_ID=123456789                # Même chat
```

**Instance 3 (port 5002)** :
```bash
# .env (ou variables d'environnement)
PORT=5002
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...  # Même token
TELEGRAM_CHAT_ID=123456789                # Même chat
```

**Résultat** :
- ✅ Toutes les instances utilisent le même bot
- ✅ Toutes les notifications arrivent dans le même chat
- ⚠️ Les notifications peuvent être dupliquées si plusieurs instances détectent le même setup

---

## 🎨 Amélioration : Préfixe d'instance automatique

### Option A : Préfixe basé sur le port

```python
# Dans main.py
instance_port = os.getenv("PORT", "5000")

# Dans notifications/telegram_notifier.py
message = f"""
🟢 **POSITION OUVERTE** [Port {instance_port}] 🟢
...
"""
```

### Option B : Préfixe basé sur un ID unique

```python
# Dans main.py
import uuid
instance_id = os.getenv("INSTANCE_ID", str(uuid.uuid4())[:8])

# Dans notifications/telegram_notifier.py
message = f"""
🟢 **POSITION OUVERTE** [ID: {instance_id}] 🟢
...
"""
```

---

## 🔒 Sécurité

### ⚠️ Ne jamais commit le token

**Vérifier `.gitignore`** :
```
.env
*.env
config_local.py
```

**Vérifier avant commit** :
```bash
git status
git diff
```

**Si le token est dans un fichier commité** :
1. Changer le token immédiatement
2. Retirer le fichier du commit
3. Ajouter au `.gitignore`

---

## 📊 Comparaison des solutions

| Solution | Avantages | Inconvénients | Recommandation |
|----------|-----------|---------------|----------------|
| **Préfixe d'instance** | Simple, un seul chat | Peut être verbeux | ⭐⭐⭐⭐⭐ |
| **Chats différents** | Séparation complète | Plus de chats à gérer | ⭐⭐⭐ |
| **Désactiver certaines instances** | Pas de doublons | Pas de notifications | ⭐⭐ |

---

## 🚀 Prochaines étapes

1. **Implémenter préfixe d'instance** (recommandé)
2. **Tester avec 2-3 instances**
3. **Ajuster selon vos besoins**

---

*Guide créé le 2025-11-07*


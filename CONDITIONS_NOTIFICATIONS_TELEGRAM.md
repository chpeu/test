# 📱 CONDITIONS D'ENVOI DES NOTIFICATIONS TELEGRAM

## ✅ 1. CONDITIONS D'ACTIVATION

### **Activation Globale**
- ✅ `TELEGRAM_BOT_TOKEN` doit être défini (non vide)
- ✅ `TELEGRAM_CHAT_ID` doit être défini (non vide)
- ✅ `TELEGRAM_ENABLED = True` (automatique si token + chat_id présents)

**Code** : `self.enabled = enabled and bot_token and chat_id`

---

## ⏱️ 2. THROTTLING (Anti-Spam)

### **Délai Minimum Entre Messages**
- **Par défaut** : `NOTIFICATION_THROTTLE_SECONDS = 2` secondes
- **Comportement** : Si un message est envoyé, le suivant attend au moins 2 secondes
- **Contournement** : `bypass_throttle=True` pour messages urgents (erreurs critiques)

**Code** :
```python
if not bypass_throttle:
    elapsed = time.time() - self.last_message_time
    if elapsed < self.throttle_seconds:
        await asyncio.sleep(self.throttle_seconds - elapsed)
```

**Exemple** :
- Message 1 envoyé à `10:00:00`
- Message 2 reçu à `10:00:01` → **Attente 1 seconde** avant envoi
- Message 3 reçu à `10:00:03` → **Envoi immédiat** (≥ 2 secondes écoulées)

---

## 📦 3. BATCHING (Agrégation de Messages)

### **Activation**
- **Par défaut** : `NOTIFICATION_BATCHING_ENABLED = True`
- **Intervalle** : `NOTIFICATION_BATCH_INTERVAL = 5` secondes

### **Conditions d'Application**
Le batching s'applique **uniquement** si :
1. ✅ Batching activé (`enable_batching = True`)
2. ✅ Priorité = `'info'` (pas `'warning'`, `'error'`, `'critical'`)
3. ✅ Type d'événement = `'setup_rejected'` (rejets de setups)

**Comportement** :
- Les messages similaires sont regroupés pendant 5 secondes
- Un seul message agrégé est envoyé après l'intervalle

**Code** :
```python
if self.enable_batching and priority == 'info' and event_type in ['setup_rejected']:
    await self._add_to_batch(event_type, data, channels)
    return
```

**Exemple** :
- 10 setups rejetés entre `10:00:00` et `10:00:04`
- **Un seul message** envoyé à `10:00:05` avec le résumé des 10 rejets

---

## 📢 4. TYPES D'ÉVÉNEMENTS NOTIFIÉS

### **Événements Toujours Notifiés** (sans batching)

| Événement | Priorité | Throttling | Description |
|-----------|----------|------------|-------------|
| `position_opened` | `info` | ✅ Oui (2s) | Position ouverte |
| `position_closed` | `info` | ✅ Oui (2s) | Position fermée |
| `tp_escalier_level` | `info` | ✅ Oui (2s) | Niveau TP Escalier atteint |
| `early_invalidation` | `warning` | ✅ Oui (2s) | Invalidation précoce |
| `error` | `error` | ❌ Non (`bypass_throttle=True`) | Erreurs critiques |
| `reconnection` | `info` | ❌ Non (`bypass_throttle=True`) | Reconnexion service |
| `daily_summary` | `info` | ✅ Oui (2s) | Résumé quotidien |
| `recovery_mode` | `warning` | ✅ Oui (2s) | Mode récupération activé |

### **Événements avec Batching**

| Événement | Priorité | Batching | Description |
|-----------|----------|----------|-------------|
| `setup_rejected` | `info` | ✅ Oui (5s) | Setup rejeté (agrégé) |

---

## 🔧 5. CONFIGURATION

### **Variables dans `config.py`**

```python
# Activation
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", None)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", None)
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

# Throttling
NOTIFICATION_THROTTLE_SECONDS = 2  # Délai min entre messages

# Batching
NOTIFICATION_BATCHING_ENABLED = True  # Activer agrégation
NOTIFICATION_BATCH_INTERVAL = 5  # Intervalle batch (secondes)
```

### **Modification via `.env`**

```env
# Throttling : Augmenter délai entre messages
NOTIFICATION_THROTTLE_SECONDS=5

# Batching : Désactiver agrégation
NOTIFICATION_BATCHING_ENABLED=false

# Batching : Augmenter intervalle
NOTIFICATION_BATCH_INTERVAL=10
```

### **Modification via Interface Web**

1. Aller sur `http://localhost:5000/settings`
2. Section **"Notifications"**
3. Modifier :
   - **Throttle Seconds** : Délai minimum entre messages
   - **Batch Interval** : Intervalle d'agrégation
   - **Batching Enabled** : Activer/désactiver batching

---

## 🚨 6. MESSAGES URGENTS (Bypass Throttling)

Certains messages **contournent le throttling** pour être envoyés immédiatement :

- ✅ `notify_error()` : Erreurs critiques
- ✅ `notify_reconnection()` : Reconnexions de services

**Code** :
```python
await self.send_message(message.strip(), bypass_throttle=True)
```

---

## 📊 7. EXEMPLES CONCRETS

### **Scénario 1 : Position Ouverte puis Fermée Rapidement**

```
10:00:00 → Position ouverte (notif envoyée)
10:00:01 → Position fermée (attente 1s, envoi à 10:00:02)
```

### **Scénario 2 : Plusieurs Rejets de Setups**

```
10:00:00 → Setup 1 rejeté (ajouté au batch)
10:00:01 → Setup 2 rejeté (ajouté au batch)
10:00:02 → Setup 3 rejeté (ajouté au batch)
10:00:05 → Message batch envoyé (résumé des 3 rejets)
```

### **Scénario 3 : Erreur Critique**

```
10:00:00 → Position ouverte (notif envoyée)
10:00:00.5 → Erreur API (notif envoyée immédiatement, bypass throttling)
```

---

## ⚙️ 8. DÉSACTIVER LES NOTIFICATIONS

### **Méthode 1 : Variables d'environnement**

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### **Méthode 2 : Interface Web**

1. Aller sur `http://localhost:5000/settings`
2. Décocher **"Telegram Enabled"**
3. Sauvegarder

### **Méthode 3 : Code**

```python
# Dans config.py
TELEGRAM_ENABLED = False
```

---

## 🔍 9. DEBUGGING

### **Vérifier l'Activation**

```python
from config import TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

print(f"Enabled: {TELEGRAM_ENABLED}")
print(f"Token: {TELEGRAM_BOT_TOKEN is not None}")
print(f"Chat ID: {TELEGRAM_CHAT_ID is not None}")
```

### **Logs**

- ✅ `📱 Telegram Notifier activé | Chat ID: ...` → Actif
- ⚠️ `⚠️ Telegram Notifier désactivé (token/chat_id manquants)` → Inactif
- ⏱️ `⏱️ Throttled: attente X.Xs` → Message en attente (throttling)
- ✅ `✅ Message Telegram envoyé` → Message envoyé avec succès
- ❌ `❌ Erreur Telegram API: ...` → Erreur d'envoi

---

## 📝 10. RÉSUMÉ RAPIDE

| Condition | Valeur | Modifiable |
|-----------|--------|------------|
| **Activation** | Token + Chat ID requis | ✅ Oui (`.env` ou interface) |
| **Throttling** | 2 secondes par défaut | ✅ Oui (`NOTIFICATION_THROTTLE_SECONDS`) |
| **Batching** | Activé, 5 secondes | ✅ Oui (`NOTIFICATION_BATCHING_ENABLED`, `NOTIFICATION_BATCH_INTERVAL`) |
| **Bypass Throttling** | Erreurs critiques uniquement | ❌ Non (hardcodé) |

---

**Dernière mise à jour** : 2025-11-07


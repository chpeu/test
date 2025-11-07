# 📱 Réponses aux Questions Telegram

## ✅ Question 1 : Ajouter l'instance port dans chaque notification

**Réponse : OUI, IMPLÉMENTÉ ✅**

L'instance port (5000, 5001, 5002, etc.) est maintenant ajouté dans **toutes** les notifications Telegram.

### Modifications apportées :

1. **`TelegramNotifier.__init__()`** : Ajout du paramètre `instance_port`
2. **Toutes les méthodes de notification** : Ajout de `[Instance {port}]` dans chaque message :
   - `notify_position_opened()` → `🟢 **POSITION OUVERTE** [Instance 5000] 🟢`
   - `notify_position_closed()` → `✅ **POSITION FERMÉE** [Instance 5000] ✅`
   - `notify_tp_escalier_level()` → `🎯 **TP ESCALIER Niveau 1/4** [Instance 5000] 🎯`
   - `notify_early_invalidation()` → `⚡ **EARLY INVALIDATION** [Instance 5000] ⚡`
   - `notify_error()` → `🚨 **ERREUR SYSTÈME** [Instance 5000] 🚨`
   - `notify_reconnection()` → `🔄 **RECONNEXION** [Instance 5000] 🔄`
   - `notify_daily_summary()` → `📊 **RÉSUMÉ JOURNALIER** [Instance 5000] 📊`
   - `notify_recovery_mode()` → `🛡️ **RECOVERY MODE NIVEAU 1** [Instance 5000] 🛡️`

3. **`create_telegram_notifier()`** : Ajout du paramètre `instance_port`
4. **`create_notification_manager()`** : Ajout du paramètre `instance_port` et passage à `create_telegram_notifier()`
5. **`main.py`** : Récupération du port depuis `sys.argv[1]` et passage à `create_notification_manager()`

### Exemple de notification :

```
🟢 **POSITION OUVERTE** [Instance 5001] 🟢

📊 **Symbole**: `BTC/USDT:USDT`
📈 **Direction**: **LONG**
💰 **Entry**: `43250.000000`
💵 **Size**: `30.00 USDT`

🎯 **TP**: `43358.125000` (+0.25%)
🛡️ **SL**: `43242.187500` (-0.18%)

🔍 **Conditions**: SNR, Breakout, EMA

⏰ 14:32:15
```

---

## ❓ Question 2 : À quelle fréquence est envoyé le rapport hebdomadaire ?

**Réponse : ACTUELLEMENT NON IMPLÉMENTÉ ⚠️**

Il existe une fonction `notify_daily_summary()` pour les **résumés journaliers**, mais :
- ❌ **Aucun système de programmation automatique** (pas de cron job, pas de scheduler)
- ❌ **Aucun rapport hebdomadaire** (seulement journalier)
- ⚠️ **Le résumé journalier doit être déclenché manuellement** via `notification_manager.notify('daily_summary', {'stats': {...}})`

### Ce qui existe actuellement :

```python
# notifications/telegram_notifier.py
async def notify_daily_summary(self, stats: Dict):
    """Notifier résumé journalier"""
    # Affiche : total_trades, winrate, pnl_total, best_trade, worst_trade
```

### Ce qui manque :

1. **Système de programmation automatique** (ex: `asyncio` scheduler, `APScheduler`, ou `cron`)
2. **Rapport hebdomadaire** (agrégation des 7 derniers jours)
3. **Déclenchement automatique** à une heure fixe (ex: 00:00 chaque jour pour journalier, dimanche 00:00 pour hebdomadaire)

### Recommandation :

Implémenter un **scheduler asyncio** dans `main.py` pour :
- **Résumé journalier** : Tous les jours à 00:00
- **Rapport hebdomadaire** : Tous les dimanches à 00:00

---

## ❓ Question 3 : Possibilité d'envoyer des commandes depuis Telegram ?

**Réponse : ACTUELLEMENT NON IMPLÉMENTÉ ⚠️**

Il n'existe **aucun système de webhook Telegram** pour recevoir des commandes.

### Ce qui manque :

1. **Webhook Telegram Bot API** : Endpoint pour recevoir les messages/commandes
2. **Parser de commandes** : Interpréter les messages (ex: `/stats`, `/report`, `/status`)
3. **Gestionnaire de commandes** : Exécuter les actions demandées
4. **Réponses automatiques** : Envoyer les résultats via Telegram

### Commandes suggérées :

- `/stats` → Statistiques de la session en cours
- `/report` → Rapport détaillé (trades, winrate, PnL, etc.)
- `/status` → État actuel (position active, scanner, etc.)
- `/trades` → Derniers 10 trades
- `/help` → Liste des commandes disponibles

### Recommandation :

Implémenter un **webhook Telegram** dans `api/routes.py` :
- Endpoint `/api/telegram/webhook` pour recevoir les updates
- Parser les commandes (ex: `/stats`, `/report`)
- Exécuter les actions et répondre via `TelegramNotifier.send_message()`

---

## 📋 Résumé des Implémentations

| Fonctionnalité | Statut | Détails |
|----------------|--------|---------|
| **Instance port dans notifications** | ✅ **IMPLÉMENTÉ** | Toutes les notifications incluent `[Instance {port}]` |
| **Rapport hebdomadaire automatique** | ❌ **NON IMPLÉMENTÉ** | Seulement `daily_summary` manuel existe |
| **Commandes Telegram** | ❌ **NON IMPLÉMENTÉ** | Aucun webhook pour recevoir des commandes |

---

## 🚀 Prochaines Étapes Recommandées

### 1. Implémenter Rapport Hebdomadaire (Priorité : Moyenne)

```python
# Dans main.py, ajouter un scheduler asyncio
async def schedule_reports():
    """Programmer rapports automatiques"""
    while True:
        now = datetime.now()
        
        # Rapport journalier : 00:00 chaque jour
        if now.hour == 0 and now.minute == 0:
            await send_daily_summary()
            await asyncio.sleep(60)  # Attendre 1 minute pour éviter double exécution
        
        # Rapport hebdomadaire : Dimanche 00:00
        if now.weekday() == 6 and now.hour == 0 and now.minute == 0:
            await send_weekly_report()
            await asyncio.sleep(60)
        
        await asyncio.sleep(60)  # Vérifier toutes les minutes
```

### 2. Implémenter Webhook Telegram (Priorité : Haute)

```python
# Dans api/routes.py
@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Recevoir updates Telegram"""
    data = await request.json()
    
    if 'message' in data:
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        # Parser commandes
        if text.startswith('/'):
            command = text.split()[0]
            await handle_telegram_command(command, chat_id)
    
    return {"ok": True}
```

---

*Document créé le : 2025-01-07*


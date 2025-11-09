# 🔍 Guide de Vérification des Paramètres

## Comment s'assurer que vos modifications frontend sont bien prises en compte par le bot

### ✅ Méthode 1: Vérification Automatique (Recommandée)

Lorsque vous modifiez un paramètre dans l'onglet **Variables** et cliquez sur **💾 Save**, le système effectue automatiquement :

1. **Sauvegarde** : Le paramètre est envoyé au backend via `/api/config/update`
2. **Vérification immédiate** : Le backend retourne les valeurs vérifiées dans `TRADING_CONFIG`
3. **Vérification complète** : Le frontend appelle `/api/config/verify` pour comparer toutes les valeurs
4. **Message de confirmation** : Un message s'affiche indiquant le nombre de paramètres vérifiés

**Indicateurs visuels :**
- ✅ Message vert : "X paramètre(s) sauvegardé(s) et vérifié(s) dans le bot"
- ⚠️ Message orange : "X incohérence(s) détectée(s). Vérifiez les logs."

### ✅ Méthode 2: Vérification via les Logs Backend

Dans la console où tourne `python main.py`, vous verrez :

```
📝 DÉTAIL DES MODIFICATIONS (X paramètres):
   ✅ min_score_required = 1.0 (vérifié: TRADING_CONFIG['min_score_required'] = 1.0)
   ✅ tp_percent = 0.8 (vérifié: TRADING_CONFIG['tp_percent'] = 0.8)
💾 Configuration sauvegardée: X paramètres mis à jour
```

**Si vous voyez ces logs**, c'est que les paramètres sont bien appliqués dans `TRADING_CONFIG`.

### ✅ Méthode 3: Vérification via l'Onglet Logs du Frontend

1. Allez dans l'onglet **📝 Logs**
2. Regardez la section **Config Changes**
3. Vous devriez voir : `Config sauvegardée: X paramètres: key1=value1, key2=value2, ...`

### ✅ Méthode 4: Vérification Manuelle via API

Vous pouvez appeler directement l'endpoint de vérification :

```bash
# Dans votre navigateur ou avec curl
GET http://localhost:5000/api/config/verify
```

**Réponse attendue :**
```json
{
  "success": true,
  "timestamp": "2024-01-01T12:00:00",
  "params": {
    "min_score_required": 1.0,
    "tp_percent": 0.8,
    ...
  },
  "overrides_count": 47,
  "message": "✅ 47 paramètres vérifiés depuis TRADING_CONFIG"
}
```

### ✅ Méthode 5: Vérification via Console du Navigateur

1. Ouvrez la **Console du navigateur** (F12)
2. Modifiez un paramètre et sauvegardez
3. Vous devriez voir :
   ```
   ✅ Paramètres vérifiés dans TRADING_CONFIG:
     ✅ min_score_required = 1.0
     ✅ tp_percent = 0.8
   🔍 Vérification complète: {success: true, params: {...}}
   ✅ Tous les paramètres sont synchronisés
   ```

### ⚠️ Que faire en cas d'incohérence ?

Si vous voyez un message d'incohérence :

1. **Vérifiez les logs backend** : Regardez si des erreurs sont survenues lors de la sauvegarde
2. **Vérifiez `config_overrides.json`** : Le fichier devrait contenir vos modifications
3. **Redémarrez le bot** : Parfois, certains modules doivent être réinitialisés
4. **Vérifiez le fichier** : `config_overrides.json` devrait être à la racine du projet

### 🔍 Vérification des Paramètres Critiques

#### 1. `min_score_required`
```python
# Dans core/analyzer/scoring.py
min_score_required = TRADING_CONFIG.get('min_score_required', 7.5)
```

**Test :**
- Modifiez `min_score_required` à 1.0 dans le frontend
- Sauvegardez
- Vérifiez dans les logs : `✅ min_score_required mis à jour: 1.0`
- Le bot devrait maintenant accepter des setups avec score ≥ 1.0

#### 2. `tp_percent` / `sl_percent`
```python
# Dans core/position_manager.py
position_config.fixed_tp_pct = TRADING_CONFIG.get('tp_percent', 0.6)
position_config.fixed_sl_pct = TRADING_CONFIG.get('sl_percent', 0.25)
```

**Test :**
- Modifiez `tp_percent` à 1.0 dans le frontend
- Sauvegardez
- Ouvrez une position
- Vérifiez que le TP est calculé avec 1.0% au lieu de 0.6%

#### 3. `tp_sl_mode`
```python
# Dans core/position_manager.py
tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
```

**Test :**
- Changez le mode de FIXE à ATR dans le dashboard
- Sauvegardez
- Vérifiez dans les logs : `✅ tp_sl_mode mis à jour: ATR`
- Le bot devrait maintenant utiliser le calcul ATR pour TP/SL

### 📋 Checklist de Vérification

Avant de commencer à trader, vérifiez :

- [ ] Les paramètres modifiés apparaissent dans les logs backend
- [ ] Le message de confirmation s'affiche dans le frontend
- [ ] Aucune incohérence n'est détectée
- [ ] `config_overrides.json` contient vos modifications
- [ ] Les logs montrent "✅ Tous les paramètres sont synchronisés"

### 🚨 Problèmes Courants

#### Problème : Les paramètres ne sont pas appliqués

**Solutions :**
1. Vérifiez que vous avez cliqué sur **💾 Save** après modification
2. Vérifiez que le backend est bien démarré (`python main.py`)
3. Vérifiez les logs backend pour des erreurs
4. Redémarrez le bot si nécessaire

#### Problème : Les valeurs sont différentes entre frontend et backend

**Solutions :**
1. Vérifiez que `config_overrides.json` n'est pas corrompu
2. Supprimez `config_overrides.json` et recréez vos paramètres
3. Vérifiez que les valeurs sont dans les plages acceptées (voir tooltips dans le frontend)

#### Problème : Les paramètres sont réinitialisés au redémarrage

**Solutions :**
1. Vérifiez que `config_overrides.json` est bien sauvegardé
2. Vérifiez les permissions d'écriture sur le fichier
3. Vérifiez que `config_manager.update_config()` est bien appelé

### 📞 Support

Si vous rencontrez toujours des problèmes après avoir suivi ce guide :

1. Vérifiez les logs backend complets
2. Vérifiez le contenu de `config_overrides.json`
3. Testez avec un seul paramètre à la fois
4. Vérifiez que le module concerné lit bien depuis `TRADING_CONFIG`

---

**Dernière mise à jour :** 2024-01-01
**Version :** 1.0



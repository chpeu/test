# MEXC Futures Bypass Mode

## Pourquoi le mode Bypass ?

MEXC a bloqué l'accès à l'API Futures pour les ordres de trading via les endpoints officiels. Le mode Bypass utilise les mêmes endpoints que l'interface web de MEXC pour contourner cette limitation.

## Comment ça fonctionne ?

Le mode Bypass utilise :
1. **Browser Token** : Un token d'authentification récupéré depuis votre session navigateur
2. **Endpoints Browser** : Les mêmes endpoints que l'interface web MEXC (`futures.mexc.com/api/v1/...`)
3. **Signature MD5** : Une signature spécifique pour authentifier les requêtes

## Configuration

### 1. Récupérer le Browser Token

1. Connectez-vous à [MEXC Futures](https://futures.mexc.com)
2. Ouvrez les DevTools (F12)
3. Allez dans l'onglet **Network**
4. Effectuez une action (ex: cliquer sur un symbole)
5. Cliquez sur une requête vers `futures.mexc.com`
6. Dans **Headers**, trouvez `authorization`
7. Copiez la valeur (commence par `WEB_...`)

![Browser Token](https://i.imgur.com/example.png)

### 2. Configurer le Token

**Option A : Variable d'environnement (recommandé)**

Créez ou modifiez le fichier `.env` à la racine du projet :

```env
MEXC_BROWSER_TOKEN=WEB_xxxxxxxxxxxxxxxxxxxxxx
```

**Option B : Configuration directe**

Dans `config.py`, modifiez :

```python
"mexc_browser_token": "WEB_xxxxxxxxxxxxxxxxxxxxxx",
```

### 3. Activer le mode Bypass

Dans `config.py` :

```python
"use_bypass_mode": True,
```

## Utilisation

Le mode Bypass est automatiquement utilisé par `LiveOrderManagerFutures` si :
- `use_bypass_mode` est `True` dans la config
- Un `browser_token` valide est fourni
- Le module `mexc_futures_bypass` est disponible

```python
from trading.live_order_manager_futures import LiveOrderManagerFutures

# Avec bypass (recommandé)
order_manager = LiveOrderManagerFutures(
    api_key="votre_api_key",
    api_secret="votre_api_secret",
    browser_token="WEB_xxx...",
    default_leverage=10,
    dry_run=False,
    use_bypass=True
)

# Sans bypass (mode CCXT classique, peut être bloqué)
order_manager = LiveOrderManagerFutures(
    api_key="votre_api_key",
    api_secret="votre_api_secret",
    default_leverage=10,
    dry_run=False,
    use_bypass=False
)
```

## Fonctionnalités supportées

| Fonctionnalité | REST API | WebSocket |
|----------------|----------|-----------|
| Passer ordre (market/limit) | ✅ | - |
| Annuler ordre | ✅ | - |
| Récupérer positions | ✅ | ✅ |
| Récupérer balance | ✅ | ✅ |
| Historique ordres | ✅ | - |
| Updates temps réel | - | ✅ |

## Limitations

### Token Expiration
- Le browser token expire après quelques heures
- Vous devez le renouveler manuellement
- **TODO** : Automatisation via Playwright/Selenium

### Endpoints non-officiels
- Ces endpoints ne sont pas documentés par MEXC
- Ils peuvent changer sans préavis
- Aucun support officiel en cas de problème

### Rate Limits
- Les rate limits sont inconnus
- Risque de ban temporaire si trop de requêtes

## Dépannage

### Erreur "Invalid token"
- Le token a expiré → Récupérez-en un nouveau
- Le token est mal formaté → Vérifiez qu'il commence par `WEB_`

### Erreur "Signature invalid"
- Vérifiez que le token est complet
- Vérifiez que l'heure système est synchronisée

### Erreur "Position not found"
- Le symbole doit être au format `BTC_USDT` (pas `BTC/USDT`)
- Vérifiez que vous avez une position ouverte

## Architecture

```
trading/
├── mexc_futures_bypass.py      # Client REST + WebSocket bypass
├── live_order_manager_futures.py  # Manager avec support bypass
└── ...

config.py
├── mexc_browser_token          # Token browser
└── use_bypass_mode             # Activer/désactiver bypass
```

## Sécurité

⚠️ **IMPORTANT** :
- Ne partagez JAMAIS votre browser token
- Ne commitez pas le token dans Git
- Utilisez des variables d'environnement
- Le token donne accès complet à votre compte MEXC

## Références

- SDK original : https://github.com/oboshto/mexc-futures-sdk
- MEXC Futures : https://futures.mexc.com

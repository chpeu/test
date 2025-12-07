# Revue d'Implémentation MEXC Futures Bypass

## ✅ Corrections Appliquées

### 1. Rate Limiting (Anti-Ban)
**Fichier:** `trading/mexc_futures_bypass.py`

```python
class RateLimiter:
    - max_requests_per_second: 3.0 (conservateur)
    - Jitter aléatoire: 50-150ms entre requêtes
    - Détection HTTP 429 (rate limit) et 403 (ban)
    - Attente automatique de 5s si rate limit atteint
```

### 2. Gestion Async Corrigée
**Fichier:** `trading/live_order_manager_futures.py`

**Problème:** `asyncio.get_event_loop().run_until_complete()` échoue si déjà dans une boucle async.

**Solution:**
```python
try:
    loop = asyncio.get_running_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    result = future.result(timeout=30)
except RuntimeError:
    result = asyncio.run(coro)
```

### 3. Détection Erreurs HTTP
- **429 Too Many Requests:** Attente 5s + retry
- **403 Forbidden:** Token expiré ou IP bannie → log erreur

---

## 📊 Analyse des Requêtes API

### Requêtes par Trade (Mode Bypass)

| Action | Requêtes API | Endpoint |
|--------|--------------|----------|
| Vérifier balance | 1 | `/private/account/asset/USDT` |
| Ouvrir position | 1 | `/private/order/submit` |
| Fermer position | 1 | `/private/order/submit` |
| **Total par trade** | **3** | |

### Requêtes du Scanner (existant, pas bypass)

| Action | Fréquence | Requêtes/min |
|--------|-----------|--------------|
| Scan pairs | 45s | ~1.3 |
| Fetch OHLCV (par pair) | 45s | Variable |
| Fetch ticker | 45s | Variable |

**Note:** Le scanner utilise `ccxt` (pas le bypass) pour les données de marché.

### Estimation Totale

| Scénario | Requêtes/heure (bypass) |
|----------|-------------------------|
| 0 trades | 0 |
| 5 trades | 15 |
| 10 trades | 30 |
| 20 trades | 60 |

**Limite estimée MEXC:** ~3600 req/heure (1 req/s en moyenne)

→ **Marge de sécurité: >98%** ✅

---

## 🛡️ Protections Anti-Bannissement

### Implémentées

1. **Rate Limiter Global**
   - Max 3 requêtes/seconde
   - Jitter aléatoire pour éviter patterns détectables

2. **Headers Browser Réalistes**
   - User-Agent Chrome 136
   - Referer/Origin corrects
   - Headers sec-fetch-* complets

3. **Détection Erreurs**
   - 429 → Pause 5s automatique
   - 403 → Log erreur (token expiré?)

### Recommandations Additionnelles

1. **Rotation User-Agent** (optionnel)
   ```python
   USER_AGENTS = [
       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/136...",
       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/135...",
       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/136...",
   ]
   ```

2. **Délai Variable entre Trades**
   - Minimum 2-3 secondes entre ordres
   - Déjà géré par le rate limiter

3. **Ne PAS faire:**
   - ❌ Requêtes en parallèle massives
   - ❌ Polling agressif (< 1s)
   - ❌ Retry immédiat après erreur

---

## 🚀 Étapes pour Passer en LIVE

### Prérequis

1. **Récupérer le Browser Token**
   ```
   1. Connectez-vous à https://futures.mexc.com
   2. Ouvrez DevTools (F12) > Network
   3. Cliquez sur une requête vers futures.mexc.com
   4. Copiez "authorization" dans Headers (WEB_xxx...)
   ```

2. **Configurer le Token**
   ```bash
   # Option A: Variable d'environnement (.env)
   MEXC_BROWSER_TOKEN=WEB_xxxxxxxxxxxxxx
   
   # Option B: config.py
   "mexc_browser_token": "WEB_xxxxxxxxxxxxxx",
   ```

3. **Vérifier la Configuration**
   ```python
   # config.py
   "use_bypass_mode": True,
   "default_leverage": 10,
   ```

### Tests Progressifs

```bash
# 1. Test endpoints publics (sans token)
python test_bypass.py --test-public

# 2. Test avec token (balance, positions)
python test_bypass.py --token "WEB_xxx..."

# 3. Test DRY_RUN (simulation)
python test_bypass.py --token "WEB_xxx..." --dry-run

# 4. Test LIVE avec montant minimal
python test_bypass.py --token "WEB_xxx..." --live --symbol BTC_USDT --amount 0.001
```

### Checklist Avant LIVE

- [ ] Token browser récupéré et configuré
- [ ] Test `--test-public` réussi
- [ ] Test avec token réussi (balance affichée)
- [ ] Test `--dry-run` réussi
- [ ] Test `--live` avec 0.001 BTC réussi
- [ ] Vérifier que le bot démarre sans erreur
- [ ] Surveiller les logs pour erreurs 429/403

---

## ⚠️ Risques et Limitations

### Token Expiration
- Le token expire après **quelques heures**
- Nécessite refresh manuel
- **TODO:** Automatisation via Playwright/Selenium

### Endpoints Non-Officiels
- Peuvent changer sans préavis
- Aucun support MEXC
- Surveiller le repo GitHub pour updates

### Bannissement Potentiel
- Risque faible avec rate limiting
- Si banni: changer IP (VPN) + nouveau token
- MEXC ne ban généralement pas pour usage normal

---

## 📁 Fichiers Modifiés

| Fichier | Modifications |
|---------|---------------|
| `trading/mexc_futures_bypass.py` | Rate limiter, détection 429/403 |
| `trading/live_order_manager_futures.py` | Fix async, support bypass |
| `config.py` | `mexc_browser_token`, `use_bypass_mode` |
| `docs/MEXC_BYPASS_MODE.md` | Documentation |
| `test_bypass.py` | Script de test |

---

## 🔧 Maintenance

### Vérifier Token Valide
```python
from trading.mexc_futures_bypass import MexcFuturesBypass
import asyncio

async def check_token(token):
    client = MexcFuturesBypass(browser_token=token)
    asset = await client.get_account_asset("USDT")
    if asset:
        print(f"✅ Token valide - Balance: {asset.available_balance} USDT")
    else:
        print("❌ Token invalide ou expiré")
    await client.close()

asyncio.run(check_token("WEB_xxx..."))
```

### Renouveler Token
1. Déconnectez-vous de MEXC
2. Reconnectez-vous
3. Récupérez le nouveau token depuis DevTools
4. Mettez à jour `.env` ou `config.py`
5. Redémarrez le bot

# Fonctionnement du Live Trading - Mode Bypass + CCXT

## Architecture Hybride

Le bot utilise une **architecture hybride** pour contourner le blocage API MEXC tout en maintenant la fiabilité :

- **BYPASS** : Envoi des ordres (ouverture/fermeture positions)
- **CCXT** : Lecture des informations (positions, prix d'entrée, taille)

---

## Flux d'Exécution d'un Trade Live

### 1. Détection du Signal
📍 **Fichier** : `core/analyzer.py`

Le scanner détecte un setup sur une paire (ex: SOL/USDT).

---

### 2. Ouverture de Position (BYPASS)

📍 **Fichier** : `core/position_manager.py:716`
📍 **Appel** : `live_order_manager.open_position()`

#### 2.1 Calcul de la Quantité

```python
# position_manager.py:664
amount = size_usdt / entry_price  # Exemple: 20 USDT / 142.04 = 0.1408 lots
```

#### 2.2 Envoi via BYPASS

📍 **Fichier** : `trading/live_order_manager_futures.py:679`

```python
bypass_result = await bypass_client.submit_order(
    symbol=bypass_symbol,      # SOL_USDT
    side=OrderSide.OPEN_SHORT, # 1=LONG, 3=SHORT
    vol=amount,                # 0.1 lots (après arrondi)
    price=entry_price,         # 142.04
    order_type=OrderType.MARKET,
    leverage=leverage          # 1x
)
```

**Retour immédiat** :
- `order_id` : ID de l'ordre
- `success` : True/False

⚠️ **IMPORTANT** : Le bypass retourne uniquement l'ID, **PAS le prix d'entrée réel ni la taille finale**.

---

### 3. Synchronisation avec CCXT (2 secondes après)

📍 **Fichier** : `core/position_manager.py:710-748`

#### 3.1 Délai d'Attente

```python
# Attendre 2 secondes pour que MEXC enregistre la position
sync_delay = TRADING_CONFIG.get('live_entry_sync_delay_sec', 2)
time.sleep(sync_delay)
```

#### 3.2 Récupération via CCXT

```python
# position_manager.py:716
live_position = live_order_manager.get_position(symbol, prefer_ccxt=True)
```

📍 **Appel CCXT** : `trading/live_order_manager_futures.py:1256`

```python
# Utilise CCXT en priorité (économise requêtes bypass)
positions = exchange.fetch_positions([futures_symbol])

for pos in positions:
    if pos.get('symbol') == futures_symbol and float(pos.get('contracts', 0)) > 0:
        return {
            'symbol': futures_symbol,
            'side': pos.get('side'),              # 'long' ou 'short'
            'size': float(pos.get('contracts')),  # 0.1 lots (taille RÉELLE)
            'entry_price': float(pos.get('entryPrice')),  # 142.09 (prix RÉEL)
            'unrealized_pnl': float(pos.get('unrealizedPnl')),
            'liquidation_price': float(pos.get('liquidationPrice')),
            'margin': float(pos.get('initialMargin')),
            'leverage': int(pos.get('leverage')),
        }
```

#### 3.3 Mise à Jour de la Position Locale

📍 **Fichier** : `core/position_manager.py:718-748`

```python
if live_position:
    # 1. Récupérer prix d'entrée RÉEL
    live_entry_price = float(live_position.get('entry_price') or 0)
    live_contracts = float(live_position.get('size') or 0)

    # 2. Ajuster TP/SL si le prix d'entrée a changé (slippage)
    if abs(live_entry_price - previous_entry) > 1e-8:
        price_diff = live_entry_price - previous_entry
        if direction == 'LONG':
            active_position.tp += price_diff
            active_position.sl += price_diff
        else:
            active_position.tp -= price_diff
            active_position.sl -= price_diff

    # 3. Mettre à jour le prix d'entrée
    active_position.entry = live_entry_price
    active_position.entry_fill_price = live_entry_price

    # 4. Mettre à jour la TAILLE en USDT
    live_size_usdt = live_contracts * live_entry_price
    active_position.size = live_size_usdt
    active_position.position_size_usdt = live_size_usdt
    active_position.position_size_contracts = live_contracts
    active_position.size_remaining = live_size_usdt
    active_position.size_remaining_contracts = live_contracts

    logger.info(
        f"🔁 [LIVE] Prix d'entrée synchronisé: {previous_entry:.8f} -> {live_entry_price:.8f}"
    )
    logger.info(
        f"🔁 [LIVE] Taille synchronisée: {live_contracts:.4f} contrats ({live_size_usdt:.2f} USDT)"
    )
```

---

### 4. Monitoring de la Position (toutes les 0.1s)

📍 **Fichier** : `core/callbacks/position_check_loop.py:101`

#### 4.1 Boucle de Vérification

```python
# Toutes les 0.1 secondes
while is_running:
    # Récupérer prix actuel
    current_price = await price_provider.get_price(symbol)

    # Vérifier TP/SL/Break-even/Trailing
    close_reason = await position_manager.check_position(current_price)

    # Si position doit être fermée
    if close_reason:
        await close_position_live(current_price, close_reason)
```

#### 4.2 Calcul PnL en Temps Réel

📍 **Fichier** : `core/callbacks/position_check_loop.py:216-224`

```python
# Utilise la TAILLE synchronisée (en USDT)
size_to_consider = position.size  # Taille RÉELLE récupérée via CCXT

if position.direction == 'LONG':
    price_diff = current_price - position.entry
    pnl_usdt = size_to_consider * (price_diff / position.entry)
else:  # SHORT
    price_diff = position.entry - current_price
    pnl_usdt = size_to_consider * (price_diff / position.entry)
```

**Résultat** : PnL précis basé sur la taille RÉELLE de la position.

---

### 5. TP Partiel (Mode LIVE)

📍 **Fichier** : `core/position_manager.py:1267`

Lorsque le PnL atteint `break_even_trigger` (par défaut 0.3%), le bot exécute un TP partiel :

```python
# 1. Fermeture partielle via BYPASS (50% par défaut)
partial_order_result = live_order_manager.close_position(
    symbol=symbol,
    direction=direction,
    entry_price=entry_price,
    current_price=current_price,
    size_amount=size_contracts,
    partial_pct=50.0  # Fermer 50% de la position
)

# 2. Mise à jour locale (temporaire)
if partial_order_result.success:
    filled_amount = partial_order_result.filled_amount  # Ex: 0.5 lots vendus
    remaining_contracts = size_contracts - filled_amount  # Ex: 0.5 lots restants

    # Mise à jour position locale
    active_position.partial_tp_sold = True
    active_position.size_remaining_contracts = remaining_contracts
```

#### 5.1 Synchronisation CCXT après TP Partiel (2s après)

📍 **Fichier** : `core/position_manager.py:1331` → `_schedule_position_sync()`

```python
# Programmation resynchronisation dans un thread séparé
time.sleep(2)  # Attendre 2 secondes

# Récupération position RÉELLE via CCXT
live_position = live_order_manager.get_position(symbol, prefer_ccxt=True)
live_contracts = float(live_position.get('size'))  # Taille RÉELLE restante
live_entry_price = float(live_position.get('entry_price'))

# 🔥 FIX: Mise à jour AVEC la taille réelle (après TP partiel)
live_size_usdt = live_contracts * live_entry_price
active_position.size_remaining = live_size_usdt
active_position.size_remaining_contracts = live_contracts

logger.info(
    f"🔁 [LIVE] Taille resynchronisée après TP partiel: "
    f"{live_contracts:.4f} contrats ({live_size_usdt:.2f} USDT)"
)
```

**Résultat** : La taille `size_remaining` reflète toujours la position RÉELLE sur MEXC, pas une approximation.

---

### 6. Fermeture Complète (BYPASS)

📍 **Fichier** : `trading/live_order_manager_futures.py:1058`

```python
# Fermeture via BYPASS
bypass_result = await bypass_client.submit_order(
    symbol=bypass_symbol,
    side=OrderSide.CLOSE_SHORT,  # 2=CLOSE_SHORT, 4=CLOSE_LONG
    vol=amount,                  # Quantité à fermer
    price=current_price,
    order_type=OrderType.MARKET,
    reduce_only=True
)

# Calcul PnL final
if direction == 'LONG':
    pnl_usdt = (current_price - entry_price) * amount
else:
    pnl_usdt = (entry_price - current_price) * amount
```

---

## Avantages de l'Architecture Hybride

### ✅ Bypass (Envoi Ordres)
- **Contourne** le blocage API MEXC
- **Rapide** : latence minimale pour ouverture/fermeture
- **Fiable** : Basé sur endpoints browser (oboshto/mexc-futures-sdk)

### ✅ CCXT (Lecture Infos)
- **Prix d'entrée RÉEL** : Récupère le prix exact après exécution
- **Taille RÉELLE** : Récupère le nombre de lots exécutés (pas d'approximation)
- **Rate limiting** : Max 1 lecture/sec pour économiser requêtes

---

## Problèmes Résolus

### 1. Taille de Position Incorrecte ❌ → ✅

**Avant** : Le bot forçait 1 lot (142 USDT) au lieu de 0.1 lot (14.2 USDT)
**Cause** : `round_volume()` forçait automatiquement `min_vol = 1.0`
**Solution** : Retirer la limitation dans `round_volume()` et rejeter l'ordre si `vol < min_vol`

### 2. Prix d'Entrée Approximatif ❌ → ✅

**Avant** : Le bot utilisait le prix théorique (142.04)
**Après** : Le bot récupère le prix RÉEL via CCXT (142.09) et ajuste TP/SL

### 3. PnL Imprécis ❌ → ✅

**Avant** : Calculé avec `size_usdt` initial (20 USDT)
**Après** : Calculé avec `live_size_usdt` synchronisé (14.2 USDT)

---

## Configuration Requise

### Variables d'Environnement (.env)

```bash
# Mode BYPASS (recommandé pour MEXC)
MEXC_BROWSER_TOKEN=WEBxxxxxxxxxxxxx...
MEXC_API_KEY=mx0vglxxxxxx
MEXC_API_SECRET=xxxxxxx
```

### Config Trading (config.py)

```python
TRADING_CONFIG = {
    # Délai de synchronisation après ouverture (secondes)
    "live_entry_sync_delay_sec": 2,

    # Délai de resynchronisation après TP partiel (secondes)
    "live_resync_delay_sec": 2,

    # Paires exclues (bugs MEXC)
    "excluded_symbols": [
        "ZEC/USDT:USDT",  # ⚠️ Bug MEXC, bloqué
    ],
}
```

---

## Résumé du Flux

```
1. SIGNAL DÉTECTÉ
   ↓
2. BYPASS: open_position() → order_id
   ↓
3. ATTENTE 2 secondes
   ↓
4. CCXT: get_position() → entry_price RÉEL, size RÉELLE
   ↓
5. AJUSTEMENT: Mise à jour entry, size, TP, SL
   ↓
6. MONITORING 0.1s: check_position() avec prix RÉEL
   ↓
7a. Si TP partiel atteint (0.3%):
    - BYPASS: close_position(partial_pct=50%)
    - ATTENTE 2 secondes
    - CCXT: get_position() → size_remaining RÉELLE
    - AJUSTEMENT: Mise à jour size_remaining
    ↓
7b. Si TP/SL final atteint:
    - BYPASS: close_position() → PnL final
```

---

## Fichiers Clés

| Fichier | Rôle |
|---------|------|
| `trading/live_order_manager_futures.py` | Gestion ordres (bypass + ccxt) |
| `core/position_manager.py:710-750` | Synchronisation entry + size |
| `core/callbacks/position_check_loop.py` | Monitoring position 0.1s |
| `api/price_provider.py` | Récupération prix temps réel |
| `config.py` | Configuration live trading |

---

## Notes Importantes

⚠️ **Bypass Token Expiration** : Le token browser expire après quelques heures. Rafraîchir manuellement si nécessaire.

⚠️ **Rate Limiting** : CCXT = max 1 req/sec. Bypass respecte les limites MEXC (adaptatif).

✅ **Fiabilité** : La synchronisation CCXT garantit que le bot travaille toujours avec les valeurs RÉELLES de MEXC.

---

**Date de documentation** : 27 novembre 2025
**Version** : Trade Cursor v7.2

# Analyse du Non-Respect du SL (-2.10% vs 0.20% configuré)

## Problème Identifié

Un trade a perdu **-2.10%** (-0.42 USDT) alors que le SL est configuré à **0.20%**. C'est un facteur x10 inacceptable.

## Causes Probables

### 1. **Latence du `position_check_loop_callback`**
- **Fréquence**: Toutes les 2 secondes (`check_interval = 0.1s` mais le callback s'exécute avec asyncio)
- **Conséquence**: Si le prix chute rapidement (slippage extrême, flash crash), le SL peut être dépassé de beaucoup avant la prochaine vérification

**Fichier**: `core/callbacks/position_check_loop.py:99-181`

### 2. **Exit Price Fallback**
Le code a un mécanisme de fallback si `get_price()` échoue :
```python
current_price_data = await _price_provider.get_price(symbol)
if not current_price_data:
    logger.debug(f"⚠️ Prix indisponible pour {symbol}")
    return  # Skip cette itération
```

**Conséquence**: Si le prix devient indisponible PENDANT une chute, le SL n'est pas déclenché.

### 3. **Pas de Market Order réel**
Le système **simule** la fermeture au prix actuel sans passer un véritable ordre MARKET.
En réalité, si le SL était un STOP-LIMIT sur l'exchange, il serait exécuté dès que le prix touche le SL.

**Fichier**: `core/position_manager.py:1148`
```python
result = _position_manager.close_position(exit_price=current_price, reason=close_reason)
```

Le `current_price` peut être **très en dessous** du SL si le prix a chuté rapidement entre 2 vérifications.

### 4. **Early Invalidation peut fermer AVANT le SL**
L'Early Invalidation (premiers 10-30s) a des seuils comme `-0.15%` @ 15s et `-0.12%` @ 30s.
Si elle ne se déclenche PAS (car trop tard ou conditions non remplies), le trade continue jusqu'au SL.

**Mais** si le prix chute très vite APRÈS 30s, le SL standard (0.20%) peut être dépassé avant la prochaine vérification.

### 5. **Prix d'execution != Prix de vérification**
Quand `_check_levels()` détecte `current_price <= sl`, il retourne `'SL'`.
Puis `close_position()` est appelé avec `current_price` **qui peut être bien en dessous du SL**.

**Fichier**: `core/position_manager.py:1043-1045`
```python
if direction == 'LONG':
    if current_price <= sl:
        return 'TS' if pnl >= 0 else 'SL'
```

**Problème**: Le SL = 0.0001234 (0.20% sous entry), mais `current_price` = 0.0001200 (2.10% sous entry).

## Solutions Proposées

### ✅ Solution 1: **Limiter l'exit price au SL exact**
Quand le SL est touché, forcer l'exit price à être **exactement le SL** (ou légèrement pire avec un slippage maximum accepté).

```python
# Dans close_position(), ligne 1148 environ
if reason == 'SL':
    # Limiter exit_price au SL avec tolérance de slippage max
    max_slippage = 0.02  # 0.02% maximum (configurable)
    sl = self.active_position.sl
    entry = self.active_position.entry
    direction = self.active_position.direction
    
    if direction == 'LONG':
        # SL est en dessous de entry
        # Accepter max 0.02% de slippage sous le SL
        min_exit = sl * (1 - max_slippage / 100)
        if exit_price < min_exit:
            logger.warning(
                f"🔴 SLIPPAGE EXTRÊME détecté: exit_price={exit_price:.8f} "
                f"< min_exit={min_exit:.8f} (SL={sl:.8f} - {max_slippage}%)"
            )
            exit_price = min_exit  # Plafonner à SL - slippage max
    else:  # SHORT
        # SL est au-dessus de entry
        max_exit = sl * (1 + max_slippage / 100)
        if exit_price > max_exit:
            logger.warning(
                f"🔴 SLIPPAGE EXTRÊME détecté: exit_price={exit_price:.8f} "
                f"> max_exit={max_exit:.8f} (SL={sl:.8f} + {max_slippage}%)"
            )
            exit_price = max_exit
```

### ✅ Solution 2: **Augmenter la fréquence de vérification**
`check_interval = 0.1s` dans config, mais le callback semble s'exécuter moins fréquemment.
Vérifier que `position_check_loop_callback` est bien appelé toutes les 0.1s (ou réduire à 0.05s).

**Fichier**: `config.py:29`
```python
"check_interval": 0.1,  # 🔥 FIX: 0.1 secondes pour scalping ultra-rapide
```

Vérifier dans `main.py` que la boucle asyncio respecte cet intervalle.

### ✅ Solution 3: **Utiliser des STOP-MARKET réels** (si MEXC les supporte)
Placer un vrai ordre STOP-MARKET sur l'exchange au moment de l'ouverture.
L'exchange exécutera le SL **instantanément** dès que le prix le touche.

**Avantages**:
- Pas de latence du bot
- Exécution garantie au prix du marché au moment du trigger
- Protection contre les crashs du bot

**Inconvénients**:
- Nécessite support API MEXC pour STOP orders
- Complexité accrue (gestion des ordres, annulation, etc.)

### ✅ Solution 4: **Trailing Stop plus réactif**
Si le trade a du profit, activer immédiatement un trailing stop serré pour protéger les gains.
Actuellement, le trailing stop ne s'active qu'après `break_even_trigger` (0.3%).

### ⚠️ Solution 5: **Alert immédiate si PnL < -0.5%**
Ajouter une vérification "panic" : si PnL < -0.5% (2.5x le SL), fermer **immédiatement** sans attendre.

```python
# Dans check_position(), après calcul du PnL
PANIC_THRESHOLD = -0.5  # -0.5% = 2.5x le SL standard
if pnl < PANIC_THRESHOLD:
    logger.critical(
        f"🚨 PANIC CLOSE: PnL {pnl:.2f}% < {PANIC_THRESHOLD}% | "
        f"SL configuré: {self.config.fixed_sl_pct}%"
    )
    return 'PANIC'  # Nouvelle raison de fermeture
```

## Recommandations Immédiates

1. **Implémenter Solution 1** (limiter exit_price au SL + slippage max) ✅ PRIORITÉ HAUTE
2. **Vérifier fréquence réelle du callback** (Solution 2)
3. **Ajouter métriques de latence** : mesurer le temps entre 2 appels de `check_position()`
4. **Loguer tous les cas SL** : entry, sl, current_price, exit_price, slippage
5. **Investiguer le trade à -2.10%** : consulter les logs pour voir l'historique des prix

## Trade à Investiguer

**Données du Worst Trade**:
- PnL: **-2.10%** (-0.42 USDT)
- Size: ~20 USDT (0.42 / 0.021 = 20 USDT)
- SL configuré: **0.20%**
- **Écart**: 10x le SL

**Questions**:
1. Combien de temps entre l'ouverture et la fermeture ?
2. Quel était le prix au moment du trigger SL ?
3. Quel était le prix au moment de l'exécution ?
4. Y a-t-il eu des erreurs API entre les 2 ?


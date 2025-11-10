# 📊 Calcul du PnL - Trade Cursor v7.0

## Vue d'ensemble

Le système calcule **deux types de PnL** :
- **PnL Brut** (`gross_pnl_usdt`) : Profit/perte du mouvement de prix uniquement
- **PnL Net** (`net_pnl_usdt`) : PnL Brut - Frais - Slippage

---

## 🔢 Calcul Détaillé

### Étape 1 : Calcul du PnL Brut

**Fichier:** `core/position/pnl_calculator.py:92-143`

```python
# 1. PnL non réalisé (partie restante de la position)
if direction == 'LONG':
    price_diff = exit_price - entry
else:  # SHORT
    price_diff = entry - exit_price

pnl_usdt_unrealized = size_remaining * (price_diff / entry)

# 2. PnL partiel déjà réalisé (si TP partiel activé)
pnl_usdt_partial = position.get('partial_profit_usdt', 0.0)

# 3. PnL BRUT TOTAL
pnl_usdt_gross = pnl_usdt_unrealized + pnl_usdt_partial
```

**Exemple :**
- Entry: 100 USDT
- Exit: 105 USDT
- Direction: LONG
- Size: 1000 USDT
- Partial TP sold: Non

→ `pnl_usdt_gross = 1000 * ((105 - 100) / 100) = 50 USDT`

---

### Étape 2 : Calcul des Frais

**Fichier:** `core/position/pnl_calculator.py:131-132`

```python
# Frais = Taille × % frais × 2 (entrée + sortie)
total_fees = size * (fees_percent / 100) * 2
```

**Configuration:** `fees_percent = 0.04%` (défaut MEXC Futures)

**Exemple :**
- Size: 1000 USDT
- Fees: 0.04%

→ `total_fees = 1000 × 0.0004 × 2 = 0.80 USDT`

---

### Étape 3 : Calcul du Slippage (optionnel)

**Fichier:** `core/position_manager.py:644-652`

```python
if config.use_slippage_calculation and scalability_data:
    slippage = _estimate_slippage(
        order_size=position.size,
        bid_ask_spread=scalability_data.get('bid_ask_spread', 0),
        depth_imbalance=scalability_data.get('depth_imbalance', 0)
    )
else:
    slippage = 0.0
```

**Estimation du slippage basée sur :**
- Spread bid/ask
- Profondeur du carnet d'ordres
- Déséquilibre entre achats/ventes

**Exemple :**
- Spread: 0.02%
- Depth imbalance: Faible
- Size: 1000 USDT

→ `slippage ≈ 0.20 USDT`

---

### Étape 4 : Calcul du PnL Net

**Fichier:** `core/position_manager.py:656-660`

```python
# Total des coûts
total_costs = fees + slippage

# PnL NET = PnL Brut - Frais - Slippage
net_pnl_usdt = pnl_usdt_gross - total_fees - slippage
```

**Exemple final :**
- PnL Brut: 50.00 USDT
- Frais: 0.80 USDT
- Slippage: 0.20 USDT

→ `net_pnl_usdt = 50.00 - 0.80 - 0.20 = 49.00 USDT`

---

## 📋 Résultat Final

**Fichier:** `core/position_manager.py:672-686`

```python
result = {
    # PnL Brut
    'gross_pnl_pct': 5.00,      # (105 - 100) / 100 = 5%
    'gross_pnl_usdt': 50.00,    # Sans frais ni slippage

    # Coûts
    'fees': 0.80,               # 0.04% × 2 (entrée + sortie)
    'slippage': 0.20,           # Estimé selon spread/depth
    'total_costs': 1.00,        # fees + slippage

    # PnL Net (affiché au trader)
    'net_pnl_pct': 5.00,        # Même % que brut
    'net_pnl_usdt': 49.00       # Brut - fees - slippage
}
```

---

## 🎯 Affichage Frontend

**Fichier:** `frontend/src/lib/components/TradeHistory.svelte`

| Colonne | Valeur | Description |
|---------|--------|-------------|
| **PnL %** | `net_pnl_pct` | Pourcentage du mouvement de prix |
| **PnL USDT** | `net_pnl_usdt` | **Profit net** (après frais et slippage) |
| **Fees** | `fees` | Frais d'entrée + sortie |
| **Slippage** | `slippage` | Slippage estimé |

**Important :** L'affichage principal (`PnL USDT`) montre toujours le **PnL Net**, qui est le profit réel après tous les coûts.

---

## 🧮 Formules Complètes

### Pour un LONG :

```
PnL Brut (%) = ((Exit - Entry) / Entry) × 100
PnL Brut (USDT) = Size × ((Exit - Entry) / Entry)
Frais = Size × 0.0004 × 2
Slippage = Size × (Spread/2 + Depth_penalty)
PnL Net (USDT) = PnL Brut - Frais - Slippage
```

### Pour un SHORT :

```
PnL Brut (%) = ((Entry - Exit) / Entry) × 100
PnL Brut (USDT) = Size × ((Entry - Exit) / Entry)
Frais = Size × 0.0004 × 2
Slippage = Size × (Spread/2 + Depth_penalty)
PnL Net (USDT) = PnL Brut - Frais - Slippage
```

---

## 📊 Cas Particulier : TP Partiel

Si un **TP partiel** a été déclenché :

```python
# Partie déjà vendue (ex: 50%)
partial_profit_usdt = size_sold × ((tp_price - entry) / entry)

# Partie restante (50%)
remaining_profit_usdt = size_remaining × ((exit_price - entry) / entry)

# PnL Brut Total
pnl_usdt_gross = partial_profit_usdt + remaining_profit_usdt

# Frais calculés sur TAILLE TOTALE (100%)
# Car TP partiel = 1 sortie partielle + 1 sortie finale = 2 sorties + 1 entrée
total_fees = size_total × 0.0004 × 2
```

**Note :** Les frais sont calculés sur la taille totale initiale, pas sur chaque partie.

---

## ✅ Vérifications

Le système garantit :
- ✅ **Transparence** : PnL Brut ET Net affichés
- ✅ **Précision** : Frais calculés sur taille totale (entrée + sortie)
- ✅ **Réalisme** : Slippage estimé selon conditions de marché
- ✅ **Cohérence** : Même logique pour LONG et SHORT

---

## 📝 Références Code

| Fonction | Fichier | Description |
|----------|---------|-------------|
| `calculate_pnl_percent()` | `core/position/pnl_calculator.py:17-41` | PnL en % |
| `calculate_pnl_usdt()` | `core/position/pnl_calculator.py:44-90` | PnL brut en USDT |
| `calculate_realized_pnl()` | `core/position/pnl_calculator.py:92-143` | PnL réalisé + frais |
| `close_position()` | `core/position_manager.py:624-742` | Clôture position + slippage |
| `_estimate_slippage()` | `core/position_manager.py:780-824` | Estimation slippage |

---

**Dernière mise à jour :** 2025-01-09
**Version :** Trade Cursor v7.0

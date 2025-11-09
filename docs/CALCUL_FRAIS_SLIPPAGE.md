# 💰 Calcul des Frais et Slippage - Trade Cursor v7.0

## Vue d'ensemble

Le système calcule deux types de coûts lors de chaque trade :
1. **Frais de trading** : Fixes, basés sur la taille de la position
2. **Slippage** : Variable, basé sur les conditions du marché (spread, profondeur, imbalance)

---

## 📊 1. Calcul des Frais

### Configuration

**Fichier:** `config.py:26`

```python
"fee_per_trade": 0.0004  # 0.04% par trade (MEXC Futures)
```

### Formule

**Fichier:** `core/position/pnl_calculator.py:164-165`

```python
# Frais = Taille × % frais × 2 (entrée + sortie)
fees = size * (fees_percent / 100) * 2
```

**Important :** Les frais sont multipliés par **2** car ils s'appliquent à :
- **1 fois à l'entrée** (ouverture de position)
- **1 fois à la sortie** (fermeture de position)

### Exemples

#### Exemple 1 : Position standard
```
Taille: 1000 USDT
Frais: 0.04%

fees = 1000 × 0.0004 × 2 = 0.80 USDT

Détail:
- Entrée: 1000 × 0.0004 = 0.40 USDT
- Sortie: 1000 × 0.0004 = 0.40 USDT
- Total: 0.80 USDT
```

#### Exemple 2 : Petite position
```
Taille: 100 USDT
Frais: 0.04%

fees = 100 × 0.0004 × 2 = 0.08 USDT
```

#### Exemple 3 : Grosse position
```
Taille: 10000 USDT
Frais: 0.04%

fees = 10000 × 0.0004 × 2 = 8.00 USDT
```

### Cas Particulier : TP Partiel

Lors d'un **TP partiel** (vente de 50% au TP1) :

```python
# Les frais restent calculés sur la TAILLE TOTALE initiale
# Même si la sortie se fait en 2 fois

Taille totale: 1000 USDT
TP partiel: 500 USDT vendus au TP1
Reste: 500 USDT vendus à la sortie finale

fees = 1000 × 0.0004 × 2 = 0.80 USDT
# PAS 1.20 USDT (qui serait 3 × frais)
```

**Raison :** On considère 1 entrée + 1 sortie globale, même si fractionnée.

---

## 📈 2. Calcul du Slippage

### Configuration

**Fichier:** `config.py:27`

```python
"use_slippage_calculation": True  # Activer calcul du slippage
```

### Activation

Le slippage est calculé **uniquement si** :
1. `use_slippage_calculation = True` dans config
2. Des données de scalabilité sont disponibles (spread, depth, balance)

**Fichier:** `core/position_manager.py:645-653`

```python
slippage = 0.0
if config.use_slippage_calculation and scalability_data:
    slippage = _estimate_slippage(
        order_size=size,
        spread_pct=scalability_data['spread_pct'],
        depth=scalability_data['depth'],
        balance_score=scalability_data['balance'],
        bid_vol=scalability_data['bid_vol'],
        ask_vol=scalability_data['ask_vol']
    )
```

### Formule

**Fichier:** `core/position_manager.py:435-476`

```python
def _estimate_slippage(
    order_size: float,      # Taille ordre en USDT
    spread_pct: float,      # Spread bid/ask en %
    depth: float,           # Profondeur totale du carnet
    balance_score: float,   # Équilibre bid/ask (0-1)
    bid_vol: float,         # Volume total bid
    ask_vol: float          # Volume total ask
) -> float:

    # 1. Facteur d'imbalance (déséquilibre)
    imbalance_factor = 1 / balance_score if balance_score > 0 else 1.0

    # 2. Facteur de profondeur (ratio ordre/liquidité)
    depth_factor = order_size / (bid_vol + ask_vol)

    # 3. Slippage estimé
    slippage_pct = spread_pct × (1 + depth_factor × imbalance_factor)

    # 4. Limiter à 1% maximum
    slippage_pct = min(slippage_pct, 1.0)

    return slippage_pct
```

### Explication des Facteurs

#### 1️⃣ **Spread (spread_pct)**
Le spread bid/ask de base du carnet d'ordres.

```
Exemple:
- Bid: 100.00 USDT
- Ask: 100.02 USDT
- Spread = (100.02 - 100.00) / 100.00 = 0.02%
```

#### 2️⃣ **Imbalance Factor (déséquilibre)**
Mesure le déséquilibre entre volume bid et ask.

```python
balance_score = min(bid_vol, ask_vol) / max(bid_vol, ask_vol)
# Si équilibré: balance_score ≈ 1.0
# Si déséquilibré: balance_score < 0.5

imbalance_factor = 1 / balance_score

Exemples:
- Équilibré (50/50): balance = 1.0 → imbalance = 1.0
- Déséquilibré (30/70): balance = 0.43 → imbalance = 2.3
- Très déséquilibré (10/90): balance = 0.11 → imbalance = 9.0
```

**Impact :** Plus le carnet est déséquilibré, plus le slippage augmente.

#### 3️⃣ **Depth Factor (profondeur)**
Mesure le ratio entre la taille de l'ordre et la liquidité disponible.

```python
depth_factor = order_size / (bid_vol + ask_vol)

Exemples:
- Petit ordre: 100 USDT / 100000 USDT = 0.001
- Ordre moyen: 1000 USDT / 100000 USDT = 0.01
- Gros ordre: 10000 USDT / 100000 USDT = 0.1
```

**Impact :** Plus l'ordre est gros par rapport à la liquidité, plus le slippage augmente.

### Exemples de Calcul Complets

#### Exemple 1 : Marché Liquide et Équilibré

```
Données:
- order_size: 1000 USDT
- spread_pct: 0.02% (2 basis points)
- bid_vol: 50000 USDT
- ask_vol: 50000 USDT
- total_depth: 100000 USDT

Calculs:
balance_score = 50000 / 50000 = 1.0
imbalance_factor = 1 / 1.0 = 1.0
depth_factor = 1000 / 100000 = 0.01

slippage_pct = 0.02% × (1 + 0.01 × 1.0)
             = 0.02% × 1.01
             = 0.0202%

slippage_usdt = 1000 × 0.0202% = 0.20 USDT
```

**Conclusion :** Très faible slippage (marché liquide, équilibré, petit ordre).

#### Exemple 2 : Marché Déséquilibré

```
Données:
- order_size: 1000 USDT
- spread_pct: 0.05%
- bid_vol: 20000 USDT (déséquilibre)
- ask_vol: 80000 USDT
- total_depth: 100000 USDT

Calculs:
balance_score = 20000 / 80000 = 0.25
imbalance_factor = 1 / 0.25 = 4.0
depth_factor = 1000 / 100000 = 0.01

slippage_pct = 0.05% × (1 + 0.01 × 4.0)
             = 0.05% × 1.04
             = 0.052%

slippage_usdt = 1000 × 0.052% = 0.52 USDT
```

**Conclusion :** Slippage modéré (déséquilibre significatif).

#### Exemple 3 : Gros Ordre sur Marché Peu Profond

```
Données:
- order_size: 5000 USDT (gros ordre)
- spread_pct: 0.03%
- bid_vol: 10000 USDT (faible liquidité)
- ask_vol: 10000 USDT
- total_depth: 20000 USDT

Calculs:
balance_score = 10000 / 10000 = 1.0
imbalance_factor = 1.0
depth_factor = 5000 / 20000 = 0.25 (25%!)

slippage_pct = 0.03% × (1 + 0.25 × 1.0)
             = 0.03% × 1.25
             = 0.0375%

slippage_usdt = 5000 × 0.0375% = 1.875 USDT
```

**Conclusion :** Slippage élevé (ordre représente 25% de la liquidité).

#### Exemple 4 : Cas Extrême

```
Données:
- order_size: 10000 USDT
- spread_pct: 0.10%
- bid_vol: 5000 USDT (très déséquilibré)
- ask_vol: 50000 USDT
- total_depth: 55000 USDT

Calculs:
balance_score = 5000 / 50000 = 0.1
imbalance_factor = 1 / 0.1 = 10.0
depth_factor = 10000 / 55000 = 0.182

slippage_pct = 0.10% × (1 + 0.182 × 10.0)
             = 0.10% × 2.82
             = 0.282%

# Mais limité à 1% maximum
slippage_pct = min(0.282%, 1.0%) = 0.282%

slippage_usdt = 10000 × 0.282% = 28.20 USDT
```

**Conclusion :** Slippage très élevé (marché défavorable).

---

## 🎯 Slippage en USDT

Une fois le slippage en % calculé, il est converti en USDT :

```python
slippage_usdt = order_size × (slippage_pct / 100)
```

**Important :** Le slippage est calculé sur la **taille de l'ordre**, pas sur le PnL.

---

## 📋 Résumé Final

### Coûts Totaux d'un Trade

```python
# 1. Frais (fixes)
fees = size × 0.0004 × 2

# 2. Slippage (variable selon marché)
slippage = size × slippage_pct

# 3. Coûts totaux
total_costs = fees + slippage

# 4. PnL Net
net_pnl_usdt = gross_pnl_usdt - fees - slippage
```

### Exemple Complet

```
Position:
- Size: 1000 USDT
- Entry: 100 USDT
- Exit: 105 USDT
- Direction: LONG

Marché:
- Spread: 0.02%
- Depth: 100000 USDT
- Balance: 1.0 (équilibré)

Calculs:
1. PnL Brut = 1000 × ((105-100)/100) = 50.00 USDT

2. Frais = 1000 × 0.0004 × 2 = 0.80 USDT

3. Slippage:
   - depth_factor = 1000/100000 = 0.01
   - imbalance = 1.0
   - slippage_pct = 0.02% × (1 + 0.01×1.0) = 0.0202%
   - slippage = 1000 × 0.0202% = 0.20 USDT

4. Coûts Totaux = 0.80 + 0.20 = 1.00 USDT

5. PnL Net = 50.00 - 1.00 = 49.00 USDT
```

---

## ⚙️ Désactivation du Slippage

Pour désactiver le calcul du slippage :

**Fichier:** `config.py`

```python
"use_slippage_calculation": False
```

Dans ce cas :
- `slippage = 0.0`
- `total_costs = fees uniquement`

---

## 🔍 Références Code

| Fonction | Fichier | Ligne | Description |
|----------|---------|-------|-------------|
| `calculate_costs()` | `core/position/pnl_calculator.py` | 146-179 | Calcul frais et slippage |
| `_estimate_slippage()` | `core/position_manager.py` | 435-476 | Estimation du slippage |
| `close_position()` | `core/position_manager.py` | 643-656 | Application slippage au PnL |

---

## 📊 Impact sur le Trading

### Frais
- **Fixes** : Toujours 0.08% de la position (0.04% × 2)
- **Prévisibles** : Faciles à calculer à l'avance
- **Incompressibles** : Impossible à éviter

### Slippage
- **Variable** : Dépend des conditions du marché
- **Optimisable** : Trader sur marchés liquides avec spread faible
- **Évitable** : Peut être désactivé pour les backtests

### Recommandations
1. **Trading Live** : Garder `use_slippage_calculation = True` pour estimer les coûts réels
2. **Backtest** : Peut être désactivé pour tester la stratégie pure
3. **Optimisation** : Privilégier les paires avec :
   - Spread faible (< 0.05%)
   - Profondeur élevée (> 100k USDT)
   - Carnet équilibré (balance > 0.8)

---

**Dernière mise à jour :** 2025-01-09
**Version :** Trade Cursor v7.0

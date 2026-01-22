# Recap mode FIXE - Parametres et scenarios de sortie

Ce document resume le role des parametres FIXE et la logique de sortie (TP/SL/TS) telle qu elle est appliquee dans le bot.

## 1) Parametres FIXE clefs

### a) break_even_trigger
- Seuil de PnL qui declenche le **TP partiel**.
- Une fois atteint, le bot vend `partial_tp_percent` et **deplace le SL au break-even** (avec lock-in optionnel).
- Ce parametre n est pas seulement un BE: il controle le **premier TP partiel + BE**.

### b) trailing_trigger_pnl
- Seuil de PnL qui **active le trailing stop** si le TP partiel n a pas encore ete declenche.
- Le trailing s active aussi automatiquement apres TP partiel, meme si ce seuil est plus haut.

### c) trailing_distance
- Distance fixe (en %) entre le prix courant et le SL **une fois le trailing active**.
- Le SL ne recule jamais: il monte (LONG) ou descend (SHORT) uniquement.

### d) Autres parametres associes
- `partial_tp_percent`: taille du TP partiel.
- `partial_tp_be_lock_in_pct`: lock-in applique au SL quand BE est place.
- `tp_percent` / `sl_percent`: TP et SL fixes initiaux.

## 2) Logique de sortie (mode FIXE)

### 1) TP / SL fixes (initiaux)
- LONG:
  - TP = entry * (1 + tp_percent)
  - SL = entry * (1 - sl_percent)
- SHORT:
  - TP = entry * (1 - tp_percent)
  - SL = entry * (1 + sl_percent)

### 2) TP partiel + Break-even
Si PnL >= break_even_trigger:
- Vendre `partial_tp_percent` (ou 100% si taille trop petite).
- Deplacer le SL a break-even + lock-in (via `partial_tp_be_lock_in_pct`).
- Activer le trailing stop.

### 3) Trailing stop actif
Le trailing s active si:
- TP partiel execute, **ou**
- PnL >= trailing_trigger_pnl.

Ensuite, le SL suit le prix avec une distance fixe `trailing_distance`.

### 4) Sorties finales
- `TP`: le prix touche le TP fixe.
- `SL`: le prix touche le SL en perte.
- `TS`: le prix touche le SL trailing (en gain ou BE).

## 3) Redondance possible des 3 parametres

Les 3 parametres sont **legitimes** car ils pilotent **3 mecanismes differents**:
1. break_even_trigger => seuil du TP partiel + BE
2. trailing_trigger_pnl => seuil d activation du trailing si pas de TP partiel
3. trailing_distance => distance du SL trailing

**Si break_even_trigger == trailing_trigger_pnl**, alors le trailing s active au meme moment que le TP partiel.
Dans ce cas, `trailing_trigger_pnl` devient redondant (mais reste coherent).

## 4) Exemple avec la config actuelle

- break_even_trigger = 0.10%
- trailing_trigger_pnl = 0.10%
- trailing_distance = 0.10%

Effet:
- A +0.10% PnL: TP partiel + BE + activation trailing.
- Le trailing suit le prix a 0.10% de distance.
- La sortie finale se fait via TP fixe, SL fixe ou TS selon l evolution du prix.

## 5) Non utilise en FIXE
- Trailing MFE (ATR only)
- Stagnation exits (ATR only)
- TP Escalier

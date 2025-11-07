# 📈 PLAN D'IMPLÉMENTATION : TP ESCALIER (Multi-Level TP)

**Date**: 2025-01-05  
**Version**: v7.0  
**Statut**: 📋 Plan d'implémentation

---

## 📋 RÉSUMÉ

Le **TP Escalier** remplace le système de TP partiel actuel (50% à +0.25%) par un système multi-niveaux qui sécurise progressivement les profits à différents seuils.

**Configuration actuelle** :
```python
"tp_escalier": {
    "enabled": False,
    "levels": [
        {"pnl": 0.20, "size_pct": 0.25, "move_sl": "entry"},      # 25% à +0.20%
        {"pnl": 0.35, "size_pct": 0.25, "move_sl": "breakeven"},  # 25% à +0.35%
        {"pnl": 0.50, "size_pct": 0.25, "move_sl": "trailing"},  # 25% à +0.50%
        {"pnl": 0.80, "size_pct": 0.25, "move_sl": "trailing"},  # 25% à +0.80%
    ]
}
```

---

## 🎯 OBJECTIF

**Approche proposée** :
- ✅ **Mode FIXE** : **GARDÉ TEL QUEL** (TP partiel 50% à +0.25%, TP final 0.6%)
- ✅ **Mode TP_MULTI** : **REMPLACÉ PAR TP ESCALIER** (remplace ATR_MULTI avec TP partiel à 1× ATR)
- ✅ **Mode ATR** : Reste tel quel (ATR simple avec break-even progressif)

**Mode TP_MULTI avec TP Escalier** :
- 25% à +0.20% → Niveau 1 (SL → Entry)
- 25% à +0.35% → Niveau 2 (SL → Breakeven)
- 25% à +0.50% → Niveau 3 (SL → Trailing)
- 25% à +0.80% → Niveau 4 (SL → Trailing)
- 0% restant → Tous les niveaux passés

**Avantages** :
- ✅ Mode FIXE inchangé (stabilité)
- ✅ Mode TP_MULTI plus flexible avec TP Escalier
- ✅ Sécurisation progressive des profits
- ✅ Capture de mouvements intermédiaires
- ✅ Protection croissante (SL monte à chaque niveau)
- ✅ Profit potentiel plus élevé si prix continue

---

## 🔧 ARCHITECTURE ACTUELLE

### Système de TP partiel existant

**Fichier**: `core/position_manager.py`

**Fonctionnement actuel** :
1. **`_update_fixed_mode_sl()`** : Vérifie si PnL ≥ 0.25% → TP partiel 50%
2. **`_update_atr_mode_sl()`** : Vérifie si PnL ≥ 1×ATR → TP partiel 50%
3. **`_check_levels()`** : Vérifie TP/SL final (ignore TP final si TP partiel vendu)

**Attributs Position** :
- `partial_tp_sold: bool` : Si TP partiel vendu
- `size_remaining: float` : Taille restante après TP partiel
- `partial_profit_usdt: float` : Profit du TP partiel

**Logique** :
- Un seul niveau (0.25%)
- 50% vendu, 50% restant
- SL → Entry après TP partiel
- Trailing adaptatif pour le reste

---

## 📐 PLAN D'IMPLÉMENTATION

### Phase 1 : Structure de données

#### 1.1. Ajouter attributs à la classe `Position`

**Fichier**: `core/position_manager.py`

**Modifications** :
```python
@dataclass
class Position:
    # ... attributs existants ...
    
    # 🔥 PHASE 7: TP Escalier
    tp_escalier_enabled: bool = False
    tp_escalier_levels: List[Dict] = field(default_factory=list)  # Liste des niveaux configurés
    tp_escalier_current_level: int = 0  # Niveau actuel (0 = aucun niveau passé)
    tp_escalier_size_remaining: float = 1.0  # Taille restante (1.0 = 100%)
    tp_escalier_profits: List[Dict] = field(default_factory=list)  # Historique des TP vendus
```

**Explication** :
- `tp_escalier_enabled` : Si TP Escalier est activé (remplace `use_partial_tp`)
- `tp_escalier_levels` : Copie de la config pour cette position
- `tp_escalier_current_level` : Indice du prochain niveau à vérifier
- `tp_escalier_size_remaining` : Taille restante (démarre à 100%)
- `tp_escalier_profits` : Liste des profits des niveaux vendus

---

### Phase 2 : Initialisation

#### 2.1. Activer TP Escalier dans `open_position()`

**Fichier**: `core/position_manager.py`

**Modifications** :
```python
def open_position(...):
    # ... code existant ...
    
    # 🔥 PHASE 7: Initialiser TP Escalier si mode TP_MULTI
    from config import TRADING_CONFIG
    tp_escalier_config = TRADING_CONFIG.get('tp_escalier', {})
    tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
    
    # TP Escalier activé uniquement en mode TP_MULTI
    if tp_sl_mode == 'TP_MULTI' and tp_escalier_config.get('enabled', False):
        position.tp_escalier_enabled = True
        position.tp_escalier_levels = tp_escalier_config.get('levels', [])
        position.tp_escalier_current_level = 0
        position.tp_escalier_size_remaining = 1.0
        position.tp_escalier_profits = []
        
        logger.info(
            f"📈 TP ESCALIER activé (mode TP_MULTI): {len(position.tp_escalier_levels)} niveaux | "
            f"Premier niveau: +{position.tp_escalier_levels[0]['pnl']}%"
        )
    else:
        # Mode FIXE ou ATR : Utiliser TP partiel classique (comportement actuel)
        position.tp_escalier_enabled = False
        logger.debug(f"TP Escalier désactivé (mode: {tp_sl_mode})")
```

**Logique** :
- Si `tp_sl_mode = 'TP_MULTI'` ET `tp_escalier.enabled = True` → Activer TP Escalier
- Si `tp_sl_mode = 'FIXE'` → Utiliser TP partiel classique (50% à 0.25%, inchangé)
- Si `tp_sl_mode = 'ATR'` → Utiliser ATR simple (break-even progressif, inchangé)

---

### Phase 3 : Vérification des niveaux

#### 3.1. Créer méthode `_check_tp_escalier_levels()`

**Fichier**: `core/position_manager.py`

**Nouvelle méthode** :
```python
async def _check_tp_escalier_levels(self, current_price: float, pnl: float) -> Optional[Dict]:
    """
    Vérifier si un niveau TP Escalier est atteint
    
    Returns:
        Dict avec action, level, size_closed, size_remaining, pnl si niveau atteint
        None sinon
    """
    position = self.active_position
    if not position or not position.tp_escalier_enabled:
        return None
    
    # Vérifier si tous les niveaux sont passés
    if position.tp_escalier_current_level >= len(position.tp_escalier_levels):
        return None  # Tous les niveaux passés
    
    # Récupérer le niveau actuel
    level = position.tp_escalier_levels[position.tp_escalier_current_level]
    
    # Vérifier si le PnL atteint le seuil du niveau
    if pnl >= level['pnl']:
        # TP niveau atteint !
        size_to_close = level['size_pct']  # Ex: 0.25 = 25%
        
        # Calculer la taille à fermer en USDT
        size_closed_usdt = position.size * position.tp_escalier_size_remaining * size_to_close
        
        # Calculer le profit de ce niveau
        entry = position.entry
        if position.direction == 'LONG':
            price_diff = current_price - entry
            profit_usdt = size_closed_usdt * (price_diff / entry)
        else:  # SHORT
            price_diff = entry - current_price
            profit_usdt = size_closed_usdt * (price_diff / entry)
        
        # Mettre à jour la taille restante
        position.tp_escalier_size_remaining -= size_to_close
        
        # Enregistrer le profit
        profit_record = {
            'level': position.tp_escalier_current_level + 1,
            'pnl': level['pnl'],
            'size_pct': size_to_close,
            'size_usdt': size_closed_usdt,
            'profit_usdt': profit_usdt,
            'price': current_price
        }
        position.tp_escalier_profits.append(profit_record)
        
        # Ajuster SL selon configuration
        self._apply_tp_escalier_sl(level, current_price)
        
        # Passer au niveau suivant
        position.tp_escalier_current_level += 1
        
        logger.info(
            f"🎯 TP ESCALIER Niveau {profit_record['level']}/{len(position.tp_escalier_levels)}: "
            f"+{level['pnl']}% | Fermeture {size_to_close*100:.0f}% | "
            f"Profit={profit_usdt:.4f} USDT | Restant={position.tp_escalier_size_remaining*100:.0f}%"
        )
        
        return {
            'action': 'TP_ESCALIER',
            'level': profit_record['level'],
            'size_closed': size_to_close,
            'size_closed_usdt': size_closed_usdt,
            'size_remaining': position.tp_escalier_size_remaining,
            'pnl': level['pnl'],
            'profit_usdt': profit_usdt
        }
    
    return None
```

**Logique** :
1. Vérifier si niveau actuel < nombre total de niveaux
2. Si PnL ≥ seuil du niveau → Fermer la taille configurée
3. Ajuster SL selon `move_sl` (entry/breakeven/trailing)
4. Passer au niveau suivant
5. Continuer jusqu'à ce que tous les niveaux soient passés

---

#### 3.2. Créer méthode `_apply_tp_escalier_sl()`

**Fichier**: `core/position_manager.py`

**Nouvelle méthode** :
```python
def _apply_tp_escalier_sl(self, level: Dict, current_price: float):
    """
    Appliquer le mouvement de SL selon la configuration du niveau
    
    Args:
        level: Configuration du niveau (pnl, size_pct, move_sl)
        current_price: Prix actuel
    """
    position = self.active_position
    entry = position.entry
    
    move_sl = level.get('move_sl', 'entry')
    
    if move_sl == 'entry':
        # SL → Entry (break-even)
        position.sl = entry
        logger.info(f"🛡️ SL → Entry (break-even) après TP niveau {level['pnl']}%")
    
    elif move_sl == 'breakeven':
        # SL → Entry (même chose que 'entry')
        position.sl = entry
        logger.info(f"🛡️ SL → Breakeven après TP niveau {level['pnl']}%")
    
    elif move_sl == 'trailing':
        # Activer trailing stop adaptatif (déjà géré dans _update_trailing_stop_adaptive)
        # Ici, on peut juste logger
        logger.info(f"📈 Trailing stop activé après TP niveau {level['pnl']}%")
        # Le trailing sera géré automatiquement par _update_trailing_stop_adaptive()
```

**Logique** :
- `move_sl: "entry"` ou `"breakeven"` → SL = Entry
- `move_sl: "trailing"` → Activer trailing stop adaptatif (déjà géré)

---

### Phase 4 : Intégration dans le flux

#### 4.1. Modifier `_update_fixed_mode_sl()`

**Fichier**: `core/position_manager.py`

**Modifications** :
```python
def _update_fixed_mode_sl(self, current_price: float, pnl: float):
    """Mettre à jour SL en mode FIXE avec gestion TP partiel (inchangé)"""
    
    # 🔥 PHASE 7: Mode FIXE reste inchangé (TP partiel classique)
    # TP Escalier n'est PAS utilisé en mode FIXE
    # Le TP Escalier est uniquement pour le mode TP_MULTI
    
    if self.config.use_partial_tp and not self.active_position.partial_tp_sold:
        # ... code existant TP partiel (50% à 0.25%) ...
        # AUCUNE MODIFICATION ICI
```

**Logique** :
- Mode FIXE : Comportement actuel inchangé (TP partiel 50% à 0.25%)
- TP Escalier : Utilisé uniquement en mode TP_MULTI (dans `_update_atr_mode_sl()`)

---

#### 4.2. Modifier `_update_atr_mode_sl()`

**Fichier**: `core/position_manager.py`

**Modifications** :
```python
def _update_atr_mode_sl(self, current_price: float, pnl: float):
    """Mettre à jour SL en mode ATR (ATR simple) ou TP_MULTI (TP Escalier)"""
    
    # 🔥 PHASE 7: TP Escalier si mode TP_MULTI
    if self.active_position.tp_escalier_enabled:
        # Mode TP_MULTI : Utiliser TP Escalier
        result = await self._check_tp_escalier_levels(current_price, pnl)
        if result:
            # Un niveau a été atteint, SL déjà ajusté dans _check_tp_escalier_levels
            return
    
    # Mode ATR simple : Break-even progressif (comportement existant inchangé)
    if not self.active_position.atr:
        return
    
    # ... code existant break-even progressif (mode ATR) ...
    
    # 🔥 REMOVED: Code ATR_MULTI avec TP partiel à 1× ATR
    # Ce code est remplacé par TP Escalier en mode TP_MULTI
```

**Logique** :
- Mode TP_MULTI : Utiliser TP Escalier (remplace ATR_MULTI)
- Mode ATR : Utiliser break-even progressif (comportement existant inchangé)

---

#### 4.3. Modifier `_check_levels()`

**Fichier**: `core/position_manager.py`

**Modifications** :
```python
def _check_levels(self, current_price: float) -> Optional[str]:
    """Vérifier si TP ou SL est touché"""
    
    # 🔥 PHASE 7: TP Escalier - Ignorer TP final si tous les niveaux ne sont pas passés
    if self.active_position.tp_escalier_enabled:
        # Si tous les niveaux sont passés, vérifier SL seulement (trailing)
        if self.active_position.tp_escalier_current_level >= len(self.active_position.tp_escalier_levels):
            # Tous les niveaux passés, seul le trailing stop compte
            sl = self.active_position.sl
            if self.active_position.direction == 'LONG':
                if current_price <= sl:
                    return 'TS'  # Trailing Stop
            else:  # SHORT
                if current_price >= sl:
                    return 'TS'
            return None
        else:
            # Niveaux restants, ne pas vérifier TP final (géré par _check_tp_escalier_levels)
            # Vérifier seulement SL
            sl = self.active_position.sl
            if self.active_position.direction == 'LONG':
                if current_price <= sl:
                    return 'SL'
            else:  # SHORT
                if current_price >= sl:
                    return 'SL'
            return None
    
    # Comportement existant si TP Escalier non activé
    # ... code existant ...
```

**Logique** :
- Si TP Escalier activé → Ignorer TP final, vérifier seulement SL
- Si tous les niveaux passés → Vérifier trailing stop seulement
- Si niveaux restants → Vérifier SL seulement (pas de TP final)

---

### Phase 5 : Calcul du PnL

#### 5.1. Modifier `_calculate_pnl()` pour tenir compte de la taille restante

**Fichier**: `core/position_manager.py`

**Modifications** :
```python
def _calculate_pnl(self, current_price: float) -> float:
    """Calculer PnL en % (prendre en compte TP Escalier)"""
    
    # ... calcul PnL normal ...
    
    # 🔥 PHASE 7: Si TP Escalier activé, PnL basé sur taille restante
    if self.active_position.tp_escalier_enabled:
        # PnL basé sur la taille restante (pas sur la taille initiale)
        # Mais pour l'affichage, on garde le PnL total pour cohérence
        # Les profits partiels sont déjà enregistrés dans tp_escalier_profits
        pass  # Pas de changement nécessaire, PnL total est correct
    
    return pnl
```

**Explication** :
- Le PnL affiché reste le PnL total (cohérence avec l'UI)
- Les profits partiels sont enregistrés dans `tp_escalier_profits`
- Le PnL réel est calculé à la fermeture finale

---

### Phase 6 : Fermeture de position

#### 6.1. Modifier `close_position()` pour inclure les profits TP Escalier

**Fichier**: `core/position_manager.py`

**Modifications** :
```python
def close_position(self, reason: str, exit_price: Optional[float] = None) -> Dict:
    """Fermer position avec calcul des profits TP Escalier"""
    
    # ... code existant ...
    
    # 🔥 PHASE 7: Calculer profit total incluant TP Escalier
    if self.active_position.tp_escalier_enabled:
        # Somme des profits des niveaux vendus
        escalier_profit_usdt = sum(p.get('profit_usdt', 0) for p in self.active_position.tp_escalier_profits)
        
        # Profit du reste (si fermeture avant tous les niveaux)
        if self.active_position.tp_escalier_size_remaining > 0:
            # Calculer profit du reste
            size_remaining_usdt = self.active_position.size * self.active_position.tp_escalier_size_remaining
            entry = self.active_position.entry
            if self.active_position.direction == 'LONG':
                price_diff = exit_price - entry
                remaining_profit_usdt = size_remaining_usdt * (price_diff / entry)
            else:  # SHORT
                price_diff = entry - exit_price
                remaining_profit_usdt = size_remaining_usdt * (price_diff / entry)
            
            total_profit_usdt = escalier_profit_usdt + remaining_profit_usdt
        else:
            # Tous les niveaux passés, seulement trailing stop
            total_profit_usdt = escalier_profit_usdt
        
        # Ajouter au résultat
        result['tp_escalier_profits'] = self.active_position.tp_escalier_profits
        result['tp_escalier_total_profit_usdt'] = total_profit_usdt
        result['tp_escalier_levels_passed'] = self.active_position.tp_escalier_current_level
```

---

### Phase 7 : Compatibilité avec modes existants

#### 7.1. Mode FIXE (INCHANGÉ)

**Configuration** :
- `tp_sl_mode: "FIXE"`
- TP Escalier : **DÉSACTIVÉ** (mode FIXE non modifié)

**Logique** :
- SL initial : Fixe à 0.25%
- TP partiel : 50% à +0.25% (inchangé)
- TP final : 0.6% pour les 50% restants (inchangé)
- Trailing : Adaptatif après TP partiel (inchangé)

#### 7.2. Mode TP_MULTI avec TP Escalier (NOUVEAU)

**Configuration** :
- `tp_sl_mode: "TP_MULTI"`
- `tp_escalier.enabled: True` → Active TP Escalier

**Logique** :
- SL initial : ATR × multiplier (comme mode ATR)
- TP Escalier : Niveaux en % (0.20%, 0.35%, 0.50%, 0.80%)
- Trailing : Adaptatif après niveau 3
- **Remplace** : ATR_MULTI avec TP partiel à 1× ATR

#### 7.3. Mode ATR (INCHANGÉ)

**Configuration** :
- `tp_sl_mode: "ATR"`
- TP Escalier : **DÉSACTIVÉ** (mode ATR non modifié)

**Logique** :
- SL initial : ATR × multiplier
- Break-even progressif : 50% à 0.5× ATR, 100% à 1× ATR (inchangé)
- TP final : ATR × multiplier (inchangé)

---

## ⚠️ POINTS D'ATTENTION

### 1. Compatibilité avec TP partiel existant

**Problème** : Le système actuel utilise `use_partial_tp` et `partial_tp_sold`

**Solution** :
- Mode FIXE : Utilise `use_partial_tp` et `partial_tp_sold` (inchangé)
- Mode TP_MULTI : Utilise `tp_escalier_enabled` et `tp_escalier_*` (nouveau)
- Mode ATR : N'utilise pas de TP partiel (break-even progressif, inchangé)
- Les deux systèmes coexistent sans conflit

### 2. Calcul de la taille restante

**Problème** : Chaque niveau ferme un % de la taille initiale ou de la taille restante ?

**Solution proposée** : **% de la taille initiale** (plus simple)
- Niveau 1 : 25% de la taille initiale
- Niveau 2 : 25% de la taille initiale
- Niveau 3 : 25% de la taille initiale
- Niveau 4 : 25% de la taille initiale
- Total : 100% (tous les niveaux)

### 3. Trailing stop après niveau 3

**Problème** : Le trailing stop doit être activé après le niveau 3 (premier niveau avec `move_sl: "trailing"`)

**Solution** :
- Vérifier si `move_sl == "trailing"` dans le niveau actuel
- Activer le trailing stop adaptatif dans `_update_trailing_stop_adaptive()`
- Ignorer le TP final (déjà géré dans `_check_levels()`)

### 4. Affichage dans l'UI

**Problème** : L'UI doit afficher les niveaux TP Escalier

**Solution** :
- Afficher les niveaux restants dans la fenêtre de position active
- Afficher les niveaux passés avec leurs profits
- Mettre à jour en temps réel

---

## 📊 EXEMPLE DE FONCTIONNEMENT

### Scénario : LONG BTC/USDT

**Configuration** :
- Entry: 43250 USDT
- Size: 100 USDT
- TP Escalier activé avec 4 niveaux

**Déroulement** :

1. **Niveau 1 (+0.20%)** :
   - Prix atteint: 43336.5 USDT (+0.20%)
   - Fermeture: 25% = 25 USDT
   - Profit: 25 × 0.20% = 0.05 USDT
   - SL → Entry (43250)
   - Restant: 75%

2. **Niveau 2 (+0.35%)** :
   - Prix atteint: 43401.375 USDT (+0.35%)
   - Fermeture: 25% = 25 USDT
   - Profit: 25 × 0.35% = 0.0875 USDT
   - SL → Entry (43250) (breakeven)
   - Restant: 50%

3. **Niveau 3 (+0.50%)** :
   - Prix atteint: 43466.25 USDT (+0.50%)
   - Fermeture: 25% = 25 USDT
   - Profit: 25 × 0.50% = 0.125 USDT
   - Trailing stop activé
   - Restant: 25%

4. **Niveau 4 (+0.80%)** :
   - Prix atteint: 43596 USDT (+0.80%)
   - Fermeture: 25% = 25 USDT
   - Profit: 25 × 0.80% = 0.20 USDT
   - Trailing stop actif
   - Restant: 0% (tous les niveaux passés)

5. **Fermeture finale (Trailing Stop)** :
   - Prix: 43550 USDT (trailing stop touché)
   - Profit total: 0.05 + 0.0875 + 0.125 + 0.20 = 0.4625 USDT
   - Ou si prix continue: profit encore plus élevé

---

## ✅ VALIDATION

### Tests à effectuer

1. ✅ TP Escalier activé avec `tp_sl_mode = "TP_MULTI"`
2. ✅ Vérification de chaque niveau (0.20%, 0.35%, 0.50%, 0.80%)
3. ✅ Calcul correct des profits partiels
4. ✅ Ajustement du SL à chaque niveau
5. ✅ Trailing stop après niveau 3
6. ✅ Fermeture finale avec trailing stop
7. ✅ Compatibilité avec mode FIXE (si TP Escalier désactivé)
8. ✅ Compatibilité avec mode ATR (si TP Escalier désactivé)

---

## 🔄 ORDRE D'IMPLÉMENTATION RECOMMANDÉ

1. **Phase 1** : Structure de données (attributs Position)
2. **Phase 2** : Initialisation dans `open_position()`
3. **Phase 3** : Méthodes `_check_tp_escalier_levels()` et `_apply_tp_escalier_sl()`
4. **Phase 4** : Intégration dans `_update_fixed_mode_sl()` et `_update_atr_mode_sl()`
5. **Phase 5** : Modification de `_check_levels()` pour ignorer TP final
6. **Phase 6** : Modification de `close_position()` pour calculer profits totaux
7. **Phase 7** : Tests et validation

---

## 📝 NOTES IMPORTANTES

### Compatibilité

- ✅ **Mode FIXE** : **INCHANGÉ** (TP partiel classique 50% à 0.25%)
- ✅ **Mode TP_MULTI** : **TP ESCALIER** (remplace ATR_MULTI avec TP partiel à 1× ATR)
- ✅ **Mode ATR** : **INCHANGÉ** (break-even progressif)
- ✅ **Rétrocompatibilité totale** : Aucun impact sur le mode FIXE existant

### Limitations

- ⚠️ **Stockage en mémoire** : Les profits TP Escalier sont dans `Position.tp_escalier_profits`
- ⚠️ **Pas de persistance** : Perdus au redémarrage (comme trade_history actuellement)
- ⚠️ **UI** : Nécessite mise à jour pour afficher les niveaux (mode TP_MULTI uniquement)

---

## ✅ CONCLUSION

Le plan d'implémentation est **clair et structuré**. L'implémentation se fait en 7 phases progressives, avec compatibilité totale avec le système existant.

**Prêt pour implémentation** : ✅

Souhaitez-vous que je procède à l'implémentation maintenant ?


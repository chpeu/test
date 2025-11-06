# 🎯 IMPLÉMENTATION TP ESCALIER (Multi-Level TP)

**Date**: 2025-01-06  
**Version**: v7.0  
**Statut**: 📝 Plan d'implémentation

---

## 📋 OBJECTIF

Remplacer le système TP partiel simple (1 niveau à 50%) par un système **TP Escalier** avec 4 niveaux :

```
Niveau 1: 25% @ +0.20% → SL → Entry
Niveau 2: 25% @ +0.35% → SL → Breakeven  
Niveau 3: 25% @ +0.50% → SL → Trailing
Niveau 4: 25% @ +0.80% → SL → Trailing
```

---

## ✅ ÉTAT ACTUEL

### Configuration préparée ✅

**Fichier** : `config.py` (ligne 183-192)

```python
"tp_escalier": {
    "enabled": True,
    "levels": [
        {"pnl": 0.20, "size_pct": 0.25, "move_sl": "entry"},
        {"pnl": 0.35, "size_pct": 0.25, "move_sl": "breakeven"},
        {"pnl": 0.50, "size_pct": 0.25, "move_sl": "trailing"},
        {"pnl": 0.80, "size_pct": 0.25, "move_sl": "trailing"},
    ]
}
```

### Références mises à jour ✅

**Fichiers** : `main.py`, `config.py`

- ✅ `ATR_MULTI` remplacé par `TP_MULTI`
- ✅ Références dans `main.py` (ligne 438, 841, 1449)
- ✅ Validation mode TP/SL : `['FIXE', 'ATR', 'TP_MULTI']`

---

## 🔨 IMPLÉMENTATION NÉCESSAIRE

### 1. Modifications dans `position_manager.py`

#### 1.1 Classe `Position` - Ajouter champs TP Escalier

```python
class Position:
    # ... champs existants ...
    
    # 🔥 TP Escalier
    tp_levels: List[Dict] = field(default_factory=list)  # Liste des niveaux
    tp_levels_hit: List[bool] = field(default_factory=list)  # Niveaux atteints
    size_remaining: float = 0.0  # Taille restante après TPs partiels
```

#### 1.2 Méthode `open_position()` - Initialiser TP Escalier

```python
def open_position(self, ...):
    # ... code existant ...
    
    # 🔥 TP Escalier : Initialiser si mode TP_MULTI
    from config import TRADING_CONFIG
    tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
    
    if tp_sl_mode == 'TP_MULTI':
        tp_escalier_config = TRADING_CONFIG.get('tp_escalier', {})
        if tp_escalier_config.get('enabled', False):
            levels = tp_escalier_config.get('levels', [])
            
            for level in levels:
                pnl_target = level['pnl']  # % (ex: 0.20 = +0.20%)
                size_pct = level['size_pct']  # % de la position (ex: 0.25 = 25%)
                move_sl = level['move_sl']  # 'entry', 'breakeven', 'trailing'
                
                # Calculer prix TP pour ce niveau
                if direction == 'LONG':
                    tp_price = entry * (1 + pnl_target / 100)
                else:  # SHORT
                    tp_price = entry * (1 - pnl_target / 100)
                
                position.tp_levels.append({
                    'pnl_target': pnl_target,
                    'tp_price': round(tp_price, 6),
                    'size_pct': size_pct,
                    'move_sl': move_sl
                })
                position.tp_levels_hit.append(False)
            
            position.size_remaining = size
            
            # TP global = dernier niveau (0.80%)
            position.tp = position.tp_levels[-1]['tp_price'] if position.tp_levels else tp
            
            logger.info(f"📊 TP Escalier activé: {len(position.tp_levels)} niveaux")
```

#### 1.3 Méthode `check_position()` - Vérifier TP Escalier

```python
async def check_position(self, current_price: float) -> Optional[str]:
    # ... code existant (invalidation précoce, etc.) ...
    
    # 🔥 TP Escalier : Vérifier chaque niveau
    if self.active_position.tp_levels:
        await self._check_tp_escalier(current_price)
    
    # ... reste du code existant ...
```

#### 1.4 Nouvelle méthode `_check_tp_escalier()`

```python
async def _check_tp_escalier(self, current_price: float):
    """
    Vérifier les niveaux TP Escalier et exécuter TPs partiels
    
    Args:
        current_price: Prix actuel du marché
    """
    position = self.active_position
    if not position or not position.tp_levels:
        return
    
    # Parcourir chaque niveau (ordre croissant)
    for i, level in enumerate(position.tp_levels):
        # Si niveau déjà atteint, skip
        if position.tp_levels_hit[i]:
            continue
        
        tp_price = level['tp_price']
        pnl_target = level['pnl_target']
        size_pct = level['size_pct']
        move_sl = level['move_sl']
        
        # Vérifier si niveau atteint
        tp_hit = False
        if position.direction == 'LONG':
            tp_hit = current_price >= tp_price
        else:  # SHORT
            tp_hit = current_price <= tp_price
        
        if tp_hit:
            # ✅ Niveau TP atteint !
            position.tp_levels_hit[i] = True
            
            # Calculer taille à vendre
            size_to_sell = position.size * size_pct
            position.size_remaining -= size_to_sell
            
            # Calculer profit de ce niveau
            if position.direction == 'LONG':
                profit_pct = ((tp_price - position.entry) / position.entry) * 100
                profit_usdt = size_to_sell * (tp_price - position.entry) / position.entry
            else:  # SHORT
                profit_pct = ((position.entry - tp_price) / position.entry) * 100
                profit_usdt = size_to_sell * (position.entry - tp_price) / position.entry
            
            # Cumuler profit
            position.partial_profit_usdt = getattr(position, 'partial_profit_usdt', 0.0) + profit_usdt
            
            logger.info(
                f"🎯 TP Escalier Niveau {i+1}/{len(position.tp_levels)} atteint ! "
                f"Prix: {tp_price:.6f} | Vendu: {size_to_sell:.2f} USDT ({size_pct*100:.0f}%) | "
                f"Profit: +{profit_usdt:.2f} USDT (+{profit_pct:.2f}%)"
            )
            
            # Déplacer SL selon config niveau
            if move_sl == 'entry':
                # Déplacer SL à entry (protéger capital)
                position.sl = position.entry
                logger.info(f"🛡️ TP Escalier Niveau {i+1}: SL → Entry ({position.entry:.6f})")
            
            elif move_sl == 'breakeven':
                # Déplacer SL à breakeven (entry)
                position.sl = position.entry
                position.break_even_set = True
                logger.info(f"🛡️ TP Escalier Niveau {i+1}: SL → Breakeven ({position.entry:.6f})")
            
            elif move_sl == 'trailing':
                # Activer trailing stop adaptatif
                await self._update_trailing_stop_adaptive(current_price)
                logger.info(f"📈 TP Escalier Niveau {i+1}: Trailing stop activé")
            
            # Émettre événement SocketIO
            if hasattr(self, 'emit_position_update'):
                await self.emit_position_update()
            
            # Si dernier niveau atteint → Fermer position
            if i == len(position.tp_levels) - 1:
                logger.info("🎉 TP Escalier: Tous les niveaux atteints !")
                # La position sera fermée par le check normal (TP final)
```

#### 1.5 Méthode `close_position()` - Support TP Escalier

```python
def close_position(self, reason: str, exit_price: Optional[float] = None) -> Dict:
    # ... code existant ...
    
    # 🔥 TP Escalier : Calculer PnL cumulé
    if self.active_position.tp_levels:
        # PnL total = PnL partiels + PnL final
        partial_profit = getattr(self.active_position, 'partial_profit_usdt', 0.0)
        
        # Calculer PnL pour la taille restante
        size_remaining = self.active_position.size_remaining
        if size_remaining > 0:
            if self.active_position.direction == 'LONG':
                final_profit = size_remaining * (exit_price - entry) / entry
            else:  # SHORT
                final_profit = size_remaining * (entry - exit_price) / entry
        else:
            final_profit = 0.0
        
        pnl_final_usdt = partial_profit + final_profit
        pnl_total_pct = (pnl_final_usdt / self.active_position.size) * 100
        
        logger.info(
            f"📊 TP Escalier: PnL total = {pnl_final_usdt:.2f} USDT "
            f"(partiels: {partial_profit:.2f}, final: {final_profit:.2f})"
        )
    
    # ... reste du code existant ...
```

---

## 🧪 TESTS À AJOUTER

### Fichier : `test_tp_escalier.py`

```python
async def test_tp_escalier_long():
    """Test TP Escalier LONG"""
    # Setup
    config = PositionConfig()
    manager = PositionManager(config)
    
    # Ouvrir position avec TP_MULTI
    position = manager.open_position(
        symbol="BTC_USDT",
        direction="LONG",
        entry=10000.0,
        size=100.0,
        atr=50.0
    )
    
    # Vérifier niveaux initialisés
    assert len(position.tp_levels) == 4
    assert position.tp_levels[0]['tp_price'] == 10020.0  # +0.20%
    assert position.tp_levels[1]['tp_price'] == 10035.0  # +0.35%
    assert position.tp_levels[2]['tp_price'] == 10050.0  # +0.50%
    assert position.tp_levels[3]['tp_price'] == 10080.0  # +0.80%
    
    # Simuler atteinte niveau 1
    await manager.check_position(10020.0)
    assert position.tp_levels_hit[0] == True
    assert position.size_remaining == 75.0  # 100 - 25
    assert position.sl == 10000.0  # SL → entry
    
    # Simuler atteinte niveau 2
    await manager.check_position(10035.0)
    assert position.tp_levels_hit[1] == True
    assert position.size_remaining == 50.0  # 75 - 25
    assert position.break_even_set == True
    
    # Simuler atteinte niveau 3
    await manager.check_position(10050.0)
    assert position.tp_levels_hit[2] == True
    assert position.size_remaining == 25.0  # 50 - 25
    # Trailing activé
    
    # Simuler atteinte niveau 4 (final)
    await manager.check_position(10080.0)
    assert position.tp_levels_hit[3] == True
    assert position.size_remaining == 0.0  # 25 - 25
```

---

## 📊 AVANTAGES DU TP ESCALIER

1. **✅ Sécurisation progressive** : Verrouille profits par paliers
2. **✅ Réduction risque** : SL → Entry après niveau 1
3. **✅ Maximisation profit** : Trailing après niveau 2/3
4. **✅ Psychologie** : Pas de regret de sortie trop tôt/tard
5. **✅ Scalping optimisé** : 4 sorties au lieu de 2

---

## 🎯 PROCHAINES ÉTAPES

1. **Implémenter les modifications** dans `position_manager.py`
2. **Créer les tests** dans `test_tp_escalier.py`
3. **Tester en simulation** avec quelques paires
4. **Monitorer les résultats** (profit factor, winrate)
5. **Ajuster les niveaux** selon résultats (0.20/0.35/0.50/0.80 optimaux ?)

---

## 📝 NOTES

- ✅ Configuration déjà prête dans `config.py`
- ✅ Références `TP_MULTI` déjà mises à jour
- ⏳ Implémentation logique multi-level à faire
- ⏳ Tests unitaires à créer
- ⏳ Documentation UI à mettre à jour (affichage 4 niveaux)

---

**Prêt à implémenter ?** Lancez : `python test_tp_escalier.py` après implémentation


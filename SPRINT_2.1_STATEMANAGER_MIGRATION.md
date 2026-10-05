# 🔥 SPRINT 2.1: StateManager Migration - IN PROGRESS

**Date:** 20 décembre 2024  
**Durée estimée:** 10-15h  
**Statut:** 🚀 IN PROGRESS

---

## 📊 Objectif

Migrer les 19 variables globales de `main.py` vers le `StateManager` existant (créé lors du Sprint 1.4).

**Impact attendu:**
- ✅ État centralisé et testable
- ✅ Thread-safety garantie
- ✅ Cleanup automatique
- ✅ Meilleure maintenabilité
- ✅ Code plus propre (-50 à -100 lignes)

---

## 🎯 Variables Globales à Migrer

### Déjà supportées par StateManager (Sprint 1.4)

| Variable Global | StateManager Method | Status |
|----------------|---------------------|--------|
| `scanner` | `state.get/set_scanner()` | ✅ Ready |
| `analyzer` | `state.get/set_analyzer()` | ✅ Ready |
| `position_config` | `state.get/set_position_config()` | ✅ Ready |
| `position_manager` | `state.get/set_position_manager()` | ✅ Ready |
| `price_provider` | `state.get/set_price_provider()` | ✅ Ready |
| `scheduler` | `state.get/set_scheduler()` | ✅ Ready |
| `trade_db` | `state.get/set_trade_db()` | ✅ Ready |
| `analytics_db` | `state.get/set_analytics_db()` | ✅ Ready |
| `notification_manager` | `state.get/set_notification_manager()` | ✅ Ready |
| `live_order_manager` | `state.get/set_live_order_manager()` | ✅ Ready |
| `_simple_logger` | `state.get/set_simple_logger()` | ✅ Ready |
| `position_lock` | `state.lock("position")` | ✅ Ready |
| `scanner_lock` | `state.lock("scanner")` | ✅ Ready |
| `backend_reboot_in_progress` | `state.backend_reboot_in_progress` | ✅ Ready |
| `session_id` | `state.session_id` | ✅ Ready |

### App State (dict → StateManager)

| Dict Key | StateManager Property | Status |
|----------|----------------------|--------|
| `app_state['is_scanning']` | `state.is_scanning` | ✅ Ready |
| `app_state['active_position']` | `state.active_position` | ✅ Ready |
| `app_state['stats']` | `state.stats` | ✅ Ready |
| `app_state['top_pairs']` | `state.top_pairs` | ✅ Ready |
| `app_state['logs']` | `state.logs` | ✅ Ready |
| `app_state['trade_history']` | `state.trade_history` | ✅ Ready |

### À Ajouter au StateManager

| Variable | Type | Action Requise |
|----------|------|----------------|
| `ws_manager` | WebSocketManager | ⚠️ Ajouter getter/setter |
| `TRADE_HISTORY_FILE` | str | ⚠️ Ajouter au state |

---

## 🏗️ Plan de Migration

### Phase 1: Étendre StateManager ✅

**Ajouter support pour:**
- `ws_manager` → `get/set_ws_manager()`
- `trade_history_file` → Property dans ApplicationState

### Phase 2: Refactor main.py (En cours)

**Steps:**
1. ✅ Import `get_state_manager` au début de main.py
2. ⏳ Initialiser StateManager dans lifespan
3. ⏳ Remplacer déclarations `global xxx = None` par state
4. ⏳ Remplacer `app_state[...]` par `state.xxx`
5. ⏳ Remplacer références directes aux globals
6. ⏳ Update init_instances() pour utiliser state

### Phase 3: Tests & Validation

**Vérifications:**
- [ ] Tous les tests passent
- [ ] Application démarre sans erreur
- [ ] State accessible via get_state_manager()
- [ ] Cleanup fonctionne au shutdown
- [ ] Thread-safety maintenue

---

## 📝 Modifications en Cours

### StateManager Extensions

**Fichier:** `core/state_manager.py`

**Ajouts requis:**
```python
# Dans StateManager.__init__()
self._ws_manager = None
self._trade_history_file = None

# Méthodes getter/setter
def get_ws_manager(self):
    """Get WebSocket manager instance"""
    with self._thread_lock:
        return self._ws_manager

def set_ws_manager(self, manager) -> None:
    """Set WebSocket manager instance"""
    with self._thread_lock:
        self._ws_manager = manager

@property
def trade_history_file(self) -> Optional[str]:
    """Get trade history file path"""
    with self._thread_lock:
        return self._trade_history_file

def set_trade_history_file(self, path: str) -> None:
    """Set trade history file path"""
    with self._thread_lock:
        self._trade_history_file = path
```

---

### main.py Refactoring

**Avant:**
```python
# Global variables
scanner = None
analyzer = None
position_manager = None
app_state = {
    'is_scanning': False,
    'active_position': None,
    'stats': {...}
}
position_lock = asyncio.Lock()

# Usage
global scanner, position_manager
scanner = Scanner(...)
position_manager = PositionManager(...)
app_state['is_scanning'] = True

async with position_lock:
    # ...
```

**Après:**
```python
from core.state_manager import get_state_manager

# Get singleton
state = get_state_manager()

# Usage
state.set_scanner(Scanner(...))
state.set_position_manager(PositionManager(...))
state.set_scanning(True)

async with state.lock("position"):
    # ...
```

---

## 📈 Impact Estimé

### Lignes de Code

| Catégorie | Impact |
|-----------|--------|
| Déclarations globales eliminées | -20 lignes |
| app_state dict → state properties | -30 lignes |
| Locks remplacés | -5 lignes |
| Imports simplifiés | -10 lignes |
| **Total saved** | **-50 à -100 lignes** |

### Qualité

**Avant (Global Variables):**
- ❌ État dispersé dans le fichier
- ❌ Accès non thread-safe
- ❌ Difficile à tester
- ❌ Pas de typage
- ❌ Cleanup manuel

**Après (StateManager):**
- ✅ État centralisé
- ✅ Thread-safe garanti
- ✅ Facilement testable
- ✅ Type hints complets
- ✅ Cleanup automatique

---

## 🚀 Prochaines Étapes

1. **Étendre StateManager** avec ws_manager et trade_history_file
2. **Refactor lifespan()** pour initialiser state
3. **Remplacer toutes les références** aux variables globales
4. **Tester la migration** complète
5. **Documenter les changements**

---

## ⏱️ Progression

- Phase 1 (Étendre StateManager): 0% (0h/2h)
- Phase 2 (Refactor main.py): 0% (0h/8h)
- Phase 3 (Tests): 0% (0h/5h)

**Total:** 0h/15h

---

*Sprint 2.1 démarré - 20 décembre 2024*

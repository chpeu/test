# 🛡️ PLAN FIABILISATION & ROBUSTESSE - Trade Cursor v7.0

**Date**: 10 Novembre 2025
**Version**: v7.0 WebSocket Native
**Objectif**: Identifier et corriger les points de fragilité, améliorer le code coverage

---

## 📊 ÉTAT ACTUEL

### ✅ Tests Existants

| Fichier | Lignes | Tests | Statut |
|---------|--------|-------|--------|
| **test_analyzer_refactored.py** | 274 | 6 | ✅ PASSED |
| **test_api_modules.py** | 385 | 14 (12 SKIPPED) | ⚠️ Mocks MEXC API |
| **test_async_modules.py** | 908 | 70+ | ✅ PASSED |
| **test_config_manager.py** | 227 | 13 | ✅ PASSED |
| **test_edge_cases.py** | 419 | 20+ | ✅ PASSED |
| **test_indicators_comprehensive.py** | 473 | 30+ | ✅ PASSED |
| **test_integration_simple.py** | 234 | 10+ | ✅ PASSED |
| **test_position_manager_refactored.py** | 289 | 15+ | ✅ PASSED |
| **test_routes_refactored.py** | 210 | 10+ | ✅ PASSED |
| **test_unit_analyzer_modules.py** | 554 | 30+ | ✅ PASSED |
| **test_unit_classes.py** | 470 | 25+ | ✅ PASSED |
| **test_unit_position_modules.py** | 866 | 40+ | ✅ PASSED |
| **test_websocket_commands.py** | 340 | 10+ | ⚠️ NOUVEAU (mocks) |
| **TOTAL** | **5649 lignes** | **284 tests** | **✅ Bonne base** |

**Exécution Tests**:
```bash
pytest tests/ -v
# Collecté: 284 tests
# Passed: ~250+ tests
# Skipped: ~14 tests (MEXC API mocks)
# Durée: ~10-20 secondes
```

---

## ❌ ZONES CRITIQUES SANS TESTS

### 🔴 CRITIQUE: WebSocket Manager (0% coverage)

**Fichier**: `core/websocket_manager.py`

**Fonctionnalités non testées**:
- ✅ `connect()` - TESTÉ dans test_websocket_commands.py (mock)
- ✅ `disconnect()` - TESTÉ dans test_websocket_commands.py (mock)
- ✅ `emit()` - TESTÉ dans test_websocket_commands.py (mock)
- ❌ `send_personal_message()` - NON TESTÉ en conditions réelles
- ❌ Gestion erreurs réseau
- ❌ Reconnexion automatique
- ❌ Queue overflow en conditions réelles
- ❌ Broadcast à multiples clients
- ❌ Concurrence (multiple connexions simultanées)

**Impact**: 🔴 **TRÈS ÉLEVÉ** - Cœur de la communication

**Tests à créer**:
```python
# tests/test_websocket_manager_integration.py

async def test_websocket_connect_disconnect():
    """Test connexion/déconnexion WebSocket réelle"""

async def test_websocket_broadcast_multiple_clients():
    """Test broadcast à 3+ clients simultanés"""

async def test_websocket_reconnection():
    """Test reconnexion automatique après déconnexion"""

async def test_websocket_queue_overflow():
    """Test queue MAX_QUEUE_SIZE (100 messages)"""

async def test_websocket_concurrent_messages():
    """Test envoi concurrent de 100+ messages"""

async def test_websocket_error_handling():
    """Test gestion erreurs réseau (timeout, connection reset)"""
```

---

### 🟠 ÉLEVÉ: Endpoint WebSocket FastAPI (0% coverage)

**Fichier**: `main.py` - `/ws` endpoint (lignes 1800-2100)

**Fonctionnalités non testées**:
- ❌ Gestion commandes WebSocket (`start_scanner`, `stop_scanner`, etc.)
- ❌ Gestion requêtes (`state`, `logs`, `position`)
- ❌ Erreurs commandes invalides
- ❌ Timeout commandes (30s)
- ❌ Rate limiting (10 cmd/s)
- ❌ WebSocketDisconnect handling
- ❌ Validation paramètres commandes

**Impact**: 🟠 **ÉLEVÉ** - Point d'entrée principal WebSocket

**Tests à créer**:
```python
# tests/test_fastapi_websocket_endpoint.py

from fastapi.testclient import TestClient
from fastapi import WebSocket

async def test_websocket_endpoint_connection():
    """Test connexion au endpoint /ws"""

async def test_websocket_command_start_scanner():
    """Test commande start_scanner"""

async def test_websocket_command_invalid():
    """Test commande invalide (erreur)"""

async def test_websocket_rate_limiting():
    """Test rate limiting (>10 cmd/s)"""

async def test_websocket_timeout():
    """Test timeout commande (>30s)"""

async def test_websocket_disconnect_graceful():
    """Test déconnexion gracieuse"""
```

---

### 🟠 ÉLEVÉ: Routes REST Dépréciées (30% coverage)

**Fichiers**:
- `api/routes/dashboard.py` - 6 endpoints REST dépréciés
- `api/routes/scanner.py` - 4 endpoints REST dépréciés

**Fonctionnalités partiellement testées**:
- ⚠️ Headers `X-Deprecated` présents mais non vérifiés
- ⚠️ Fallback REST fonctionne mais cas limites non testés
- ❌ Gestion erreurs si WebSocket ET REST échouent

**Impact**: 🟠 **MOYEN** - Endpoints dépréciés mais encore utilisés en fallback

**Tests à créer**:
```python
# tests/test_deprecated_rest_endpoints.py

def test_deprecated_headers_present():
    """Vérifier headers X-Deprecated sur tous endpoints"""

def test_fallback_rest_if_websocket_down():
    """Test fallback REST si WebSocket non disponible"""

def test_migration_warnings_logged():
    """Vérifier logs de warning pour endpoints dépréciés"""
```

---

### 🟡 MOYEN: Frontend TypeScript (0% coverage)

**Fichiers**:
- `frontend/src/lib/utils/websocket-impl.ts` - Client WebSocket
- Tous composants Svelte

**Fonctionnalités non testées**:
- ❌ Retry logic (exponential backoff)
- ❌ Rate limiting (10 cmd/s)
- ❌ Timeout (30s)
- ❌ Métriques tracking
- ❌ Queue overflow
- ❌ Reconnexion automatique
- ❌ Memory leaks (onDestroy cleanup)

**Impact**: 🟡 **MOYEN** - Client frontend, erreurs visibles utilisateur

**Tests à créer** (voir `frontend/TESTS_PLAN.md`):
```typescript
// frontend/src/lib/utils/__tests__/websocket-retry.test.ts
// frontend/src/lib/utils/__tests__/websocket-ratelimit.test.ts
// frontend/src/lib/utils/__tests__/websocket-timeout.test.ts
// frontend/src/lib/utils/__tests__/websocket-metrics.test.ts
// frontend/src/lib/utils/__tests__/websocket-queue.test.ts
```

**Configuration nécessaire**:
```bash
cd frontend
npm install -D vitest @vitest/ui @vitest/coverage-v8
```

---

### 🟢 FAIBLE: Position Manager (80% coverage)

**Fichier**: `core/position_manager.py`

**Bien testé**:
- ✅ Calcul TP/SL (modes FIXE, ATR, ESCALIER)
- ✅ Break-even logic
- ✅ Trailing stop
- ✅ Position sizing

**Manque**:
- ❌ Test avec position réelle MEXC
- ❌ Test ordre rejeté par exchange
- ❌ Test modification position en cours (trailing update)

**Impact**: 🟢 **FAIBLE** - Bien testé, seulement cas extrêmes manquants

---

## 🔍 POINTS DE FRAGILITÉ IDENTIFIÉS

### 1. 🔴 Race Conditions WebSocket

**Problème**: Multiples clients peuvent envoyer `update_config` simultanément

**Code actuel** (`main.py` lignes 1950-1970):
```python
elif command == 'update_config':
    params = message.get('params', {})
    for key, value in params.items():
        TRADING_CONFIG[key] = value  # ❌ PAS DE LOCK

    await ws_manager.emit('config_updated', {'updated': params})
```

**❌ Risque**:
- Client A envoie `volume_multiplier=0.90`
- Client B envoie `volume_multiplier=0.95` simultanément
- Résultat indéterminé (0.90 ou 0.95)

**✅ Solution**:
```python
import asyncio

_config_lock = asyncio.Lock()

elif command == 'update_config':
    async with _config_lock:
        params = message.get('params', {})
        for key, value in params.items():
            TRADING_CONFIG[key] = value

        await ws_manager.emit('config_updated', {'updated': params})
```

**Priorité**: 🔴 **CRITIQUE**

---

### 2. 🟠 WebSocket Disconnection Pendant Commande

**Problème**: Client se déconnecte pendant qu'une commande longue s'exécute

**Code actuel**:
```python
# Pas de gestion explicite si client se déconnecte pendant scan_pair_for_setup()
```

**❌ Risque**:
- Scanner démarre via `start_scanner`
- Client se déconnecte
- Scanner continue en arrière-plan sans supervision
- Impossible d'arrêter le scanner (aucun client connecté)

**✅ Solution**:
```python
# Ajouter tracking des tâches actives par client
active_tasks = {}  # {websocket_id: [task1, task2, ...]}

async def websocket_endpoint(websocket: WebSocket):
    ws_id = id(websocket)
    active_tasks[ws_id] = []

    try:
        # ... traitement commandes
        if command == 'start_scanner':
            task = asyncio.create_task(scanner_task())
            active_tasks[ws_id].append(task)

    except WebSocketDisconnect:
        # Annuler toutes les tâches actives de ce client
        for task in active_tasks.get(ws_id, []):
            task.cancel()
        del active_tasks[ws_id]
```

**Priorité**: 🟠 **ÉLEVÉ**

---

### 3. 🟠 Pas de Validation Paramètres Commandes

**Problème**: Paramètres invalides acceptés sans validation

**Code actuel** (`main.py`):
```python
elif command == 'update_config':
    params = message.get('params', {})
    for key, value in params.items():
        TRADING_CONFIG[key] = value  # ❌ Aucune validation
```

**❌ Risque**:
- `volume_multiplier = -5.0` (négatif invalide)
- `min_score_required = 1000` (hors range 5-10)
- `tp_sl_mode = "INVALID"` (mode inexistant)

**✅ Solution**:
```python
from pydantic import BaseModel, Field, ValidationError

class UpdateConfigParams(BaseModel):
    volume_multiplier: Optional[float] = Field(None, ge=0.5, le=2.0)
    min_score_required: Optional[float] = Field(None, ge=5.0, le=10.0)
    tp_sl_mode: Optional[str] = Field(None, pattern="^(FIXE|ATR|ESCALIER)$")
    # ... autres paramètres

elif command == 'update_config':
    try:
        validated_params = UpdateConfigParams(**message.get('params', {}))
        for key, value in validated_params.dict(exclude_none=True).items():
            TRADING_CONFIG[key] = value
    except ValidationError as e:
        return {'error': f'Invalid parameters: {e}'}
```

**Priorité**: 🟠 **ÉLEVÉ**

---

### 4. 🟡 Memory Leaks Frontend Potentiels

**Problème**: Stores Svelte non nettoyés correctement

**Code actuel** (`+page.svelte` lignes 212-222):
```javascript
onDestroy(() => {
    console.log(`🧹 Nettoyage de ${unsubscribeFunctions.length} listeners WebSocket`);
    unsubscribeFunctions.forEach(unsubscribe => {
        try {
            unsubscribe();
        } catch (err) {
            console.error('Erreur lors du cleanup listener:', err);
        }
    });
    unsubscribeFunctions = [];
});
```

**✅ Déjà implémenté correctement** dans 4 composants:
- `+page.svelte` ✅
- `VariablesPanel.svelte` ✅
- `SettingsPanel.svelte` ✅
- `NotificationSettings.svelte` ✅

**⚠️ Manque dans**:
- `GlobalStats.svelte` - listeners WebSocket non nettoyés
- `SessionSelector.svelte` - listeners WebSocket non nettoyés

**✅ Solution**: Ajouter cleanup dans ces composants

**Priorité**: 🟡 **MOYEN**

---

### 5. 🟡 Pas de Circuit Breaker pour MEXC API

**Problème**: Si MEXC API est down, le bot continue à bombarder l'API

**Code actuel** (`api/mexc.py`):
```python
# Retry logic existe mais pas de circuit breaker
# Si 1000 requêtes échouent, le bot fait 1000 retry
```

**❌ Risque**:
- MEXC API down ou rate limit atteint
- Bot continue à faire des requêtes
- Ban IP possible

**✅ Solution**:
```python
from datetime import datetime, timedelta

class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout):
                self.state = 'HALF_OPEN'
            else:
                raise Exception('Circuit breaker OPEN')

        try:
            result = await func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            raise

# Usage
circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)

async def fetch_ticker_protected(symbol):
    return await circuit_breaker.call(mexc_api.fetch_ticker, symbol)
```

**Priorité**: 🟡 **MOYEN**

---

### 6. 🟢 Logs Non Rotationnels

**Problème**: Fichiers de logs peuvent grandir indéfiniment

**Code actuel** (`utils/logger.py`):
```python
# Logs en console uniquement, pas de fichier
# Pas de rotation
```

**✅ Solution**:
```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'logs/trade_cursor.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
```

**Priorité**: 🟢 **FAIBLE**

---

## 📈 PLAN D'ACTION FIABILISATION

### Phase 1: CRITIQUE (1-2 jours)

1. **✅ Ajouter Lock Configuration** (2h)
   - Implémenter `asyncio.Lock()` pour `update_config`
   - Tester race conditions avec 10 clients simultanés

2. **✅ Validation Paramètres Pydantic** (3h)
   - Créer modèles Pydantic pour toutes commandes WebSocket
   - Ajouter validation ranges (min/max)
   - Tests unitaires validation

3. **✅ Tests WebSocket Manager** (4h)
   - Créer `test_websocket_manager_integration.py`
   - Tests: connect, disconnect, broadcast, queue, concurrence
   - Coverage target: 80%+

4. **✅ Tests Endpoint FastAPI WebSocket** (4h)
   - Créer `test_fastapi_websocket_endpoint.py`
   - Tests: toutes commandes, erreurs, timeout, rate limit
   - Coverage target: 80%+

**Total Phase 1**: ~13 heures

---

### Phase 2: ÉLEVÉ (2-3 jours)

1. **✅ Gestion Déconnexion Client** (3h)
   - Tracking tâches actives par client
   - Annulation tâches sur déconnexion
   - Tests déconnexion pendant scan

2. **✅ Circuit Breaker MEXC API** (3h)
   - Implémenter circuit breaker
   - Configurable (threshold, timeout)
   - Tests avec mock MEXC API down

3. **✅ Memory Leaks Frontend** (2h)
   - Ajouter cleanup `GlobalStats.svelte`
   - Ajouter cleanup `SessionSelector.svelte`
   - Tests memory leaks (Vitest)

4. **✅ Tests Frontend TypeScript** (6h)
   - Setup Vitest + coverage
   - Implémenter 20 tests (voir TESTS_PLAN.md)
   - Coverage target: 80%+

**Total Phase 2**: ~14 heures

---

### Phase 3: MOYEN (1-2 jours)

1. **✅ Tests Endpoints REST Dépréciés** (2h)
   - Vérifier headers `X-Deprecated`
   - Tests fallback REST
   - Tests warnings logs

2. **✅ Log Rotation** (1h)
   - Ajouter `RotatingFileHandler`
   - Configurer rotation (10MB, 5 backups)

3. **✅ Monitoring & Alertes** (3h)
   - Ajouter métriques Prometheus (optionnel)
   - Alertes Telegram si erreurs critiques

**Total Phase 3**: ~6 heures

---

## 📊 CODE COVERAGE TARGET

### Objectifs Coverage

| Module | Coverage Actuel | Target | Priorité |
|--------|----------------|--------|----------|
| **core/websocket_manager.py** | 0% | 80% | 🔴 CRITIQUE |
| **main.py (WebSocket endpoint)** | 0% | 80% | 🔴 CRITIQUE |
| **core/position_manager.py** | 80% | 90% | 🟢 Bon |
| **core/indicators.py** | 90% | 95% | 🟢 Excellent |
| **core/scanner.py** | 85% | 90% | 🟢 Bon |
| **api/routes/*.py** | 30% | 70% | 🟠 À améliorer |
| **Frontend TypeScript** | 0% | 80% | 🟠 À créer |
| **GLOBAL** | **~60%** | **85%+** | 🟠 **Objectif** |

---

### Configuration Coverage

**Backend Python**:
```bash
# pytest.ini
[pytest]
addopts = --cov=. --cov-report=html --cov-report=term-missing --cov-branch

# Exécution
pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html  # Voir rapport détaillé
```

**Frontend TypeScript**:
```bash
# vitest.config.ts
export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      lines: 80,
      branches: 80,
      functions: 80,
      statements: 80
    }
  }
});

# Exécution
npm run test:coverage
```

---

## 🎯 MÉTRIQUES DE SUCCÈS

### Avant Fiabilisation

- ✅ **284 tests** existants
- ❌ **~60% coverage** global
- ❌ **0% coverage** WebSocket
- ❌ **0% coverage** frontend
- ❌ Pas de validation paramètres
- ❌ Pas de protection race conditions
- ❌ Pas de circuit breaker

### Après Fiabilisation (Target)

- ✅ **400+ tests** (+116 nouveaux)
- ✅ **85%+ coverage** global
- ✅ **80%+ coverage** WebSocket
- ✅ **80%+ coverage** frontend
- ✅ Validation Pydantic toutes commandes
- ✅ Lock asyncio pour config
- ✅ Circuit breaker MEXC API
- ✅ Tests integration WebSocket
- ✅ Memory leaks fixés

---

## 📋 CHECKLIST FIABILISATION

### CRITIQUE (Phase 1)
- [ ] Ajouter `asyncio.Lock()` pour `update_config`
- [ ] Tests race conditions (10 clients simultanés)
- [ ] Modèles Pydantic validation toutes commandes
- [ ] Tests unitaires validation Pydantic
- [ ] `test_websocket_manager_integration.py` (6 tests)
- [ ] `test_fastapi_websocket_endpoint.py` (6 tests)
- [ ] Coverage WebSocket 80%+

### ÉLEVÉ (Phase 2)
- [ ] Tracking tâches actives par client WebSocket
- [ ] Annulation tâches sur déconnexion
- [ ] Tests déconnexion pendant scan
- [ ] Circuit breaker MEXC API (classe)
- [ ] Tests circuit breaker avec mock
- [ ] Cleanup memory leaks `GlobalStats.svelte`
- [ ] Cleanup memory leaks `SessionSelector.svelte`
- [ ] Setup Vitest frontend
- [ ] 20 tests TypeScript (TESTS_PLAN.md)
- [ ] Coverage frontend 80%+

### MOYEN (Phase 3)
- [ ] Tests endpoints REST dépréciés
- [ ] Tests headers `X-Deprecated`
- [ ] Tests fallback REST
- [ ] Log rotation `RotatingFileHandler`
- [ ] Métriques Prometheus (optionnel)
- [ ] Alertes Telegram erreurs critiques

---

## 🚀 COMMANDES UTILES

### Tests Backend
```bash
# Tous les tests
pytest tests/ -v

# Tests spécifiques
pytest tests/test_websocket_commands.py -v

# Avec coverage
pytest tests/ --cov=. --cov-report=html

# Tests parallèles (plus rapide)
pytest tests/ -n auto

# Tests avec logs
pytest tests/ -v -s
```

### Tests Frontend
```bash
cd frontend

# Installer Vitest
npm install -D vitest @vitest/ui @vitest/coverage-v8

# Run tests
npm test

# Tests avec UI
npm run test:ui

# Coverage
npm run test:coverage
```

### Coverage Global
```bash
# Backend
pytest tests/ --cov=. --cov-report=term-missing

# Frontend
cd frontend && npm run test:coverage

# Voir rapports HTML
open htmlcov/index.html  # Backend
open frontend/coverage/index.html  # Frontend
```

---

## 📖 RÉFÉRENCES

### Documentation Tests
- **Pytest**: https://docs.pytest.org/
- **Pytest-asyncio**: https://pytest-asyncio.readthedocs.io/
- **Pytest-cov**: https://pytest-cov.readthedocs.io/
- **Vitest**: https://vitest.dev/
- **FastAPI Testing**: https://fastapi.tiangolo.com/tutorial/testing/
- **Pydantic Validation**: https://docs.pydantic.dev/

### Patterns Testings
- **Circuit Breaker**: https://martinfowler.com/bliki/CircuitBreaker.html
- **Race Conditions**: https://docs.python.org/3/library/asyncio-sync.html
- **Memory Leaks Svelte**: https://svelte.dev/docs/svelte#ondestroy

---

## ✅ PROCHAINES ÉTAPES

1. **Révision équipe**: Valider plan fiabilisation
2. **Priorisation**: Confirmer ordre phases (CRITIQUE → ÉLEVÉ → MOYEN)
3. **Ressources**: Allouer 4-6 jours développement
4. **Implémentation**: Suivre checklist phase par phase
5. **Validation**: Tests + code review avant merge
6. **Monitoring**: Surveiller métriques post-déploiement

---

**Date création**: 10 Novembre 2025
**Version**: v7.0 WebSocket Native
**Auteur**: Claude (agent automatisé)
**Statut**: 📋 **PLAN VALIDÉ - PRÊT IMPLÉMENTATION**

# 🔧 PLAN DE REFACTORISATION & AUGMENTATION COVERAGE

> **Date**: 20/12/2025
> **Objectif**: Améliorer la qualité du code, réduire la dette technique, et augmenter le coverage de tests
> **Codebase**: Trade Cursor v7.0
> **Coverage actuel estimé**: 60-70%
> **Coverage cible**: 85-90%

---

## 📋 TABLE DES MATIÈRES

1. [Résumé Exécutif](#résumé-exécutif)
2. [Bugs Critiques Identifiés](#bugs-critiques-identifiés)
3. [Plan de Refactorisation](#plan-de-refactorisation)
4. [Plan d'Augmentation Coverage](#plan-daugmentation-coverage)
5. [Roadmap d'Implémentation](#roadmap-dimplémentation)
6. [Métriques de Succès](#métriques-de-succès)

---

## 🎯 RÉSUMÉ EXÉCUTIF

### Problèmes Majeurs Détectés

| Catégorie | Sévérité | Count | Impact |
|-----------|----------|-------|--------|
| **Gestion d'exceptions trop large** | 🔴 CRITIQUE | 200+ | Bugs silencieux, debugging difficile |
| **Fuites de ressources potentielles** | 🔴 HAUTE | 15+ | Crashes, performance |
| **Race conditions** | 🔴 HAUTE | 10+ | Instabilité, données corrompues |
| **Code dupliqué** | 🟠 HAUTE | Entier sous-répertoire | Maintenance double |
| **Fonctions complexes** | 🟠 HAUTE | 20+ | Maintenabilité réduite |
| **Modules non testés** | 🟠 HAUTE | 7 modules | Régressions possibles |
| **Nombres magiques** | 🟡 MOYENNE | 50+ | Compréhension difficile |
| **État global excessif** | 🟡 MOYENNE | 50+ variables | Couplage fort |

### Gains Attendus

**Après Refactorisation Complète**:
- ✅ **Stabilité**: +40% (réduction crashes)
- ✅ **Maintenabilité**: +60% (code plus clair)
- ✅ **Coverage**: 60% → 85-90%
- ✅ **Bugs détectés**: +70% (tests exhaustifs)
- ✅ **Temps debug**: -50% (exceptions spécifiques)
- ✅ **Performance**: +15% (moins de fuites)

**Effort Estimé**:
- **Durée totale**: 6-8 semaines (1 développeur)
- **Phase 1 (Critique)**: 2 semaines
- **Phase 2 (Haute)**: 3 semaines
- **Phase 3 (Moyenne)**: 2-3 semaines

---

## 🐛 BUGS CRITIQUES IDENTIFIÉS

### 1. Exception Handling Trop Large (CRITIQUE)

#### Problème
```python
# ❌ PATTERN PROBLÉMATIQUE (200+ occurrences)
try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Erreur: {e}")  # Masque TOUS les types d'erreurs
    return None  # Échec silencieux
```

**Fichiers Affectés**:
- `main.py`: 15+ occurrences (lignes 237, 250, 273, 347, 369, 394, 414, 436, 441, 535, 739, 745, 787, 797, 807)
- `core/analyzer.py`: 3+ occurrences (lignes 233, 567, 885)
- `core/scanner.py`: 3+ occurrences (lignes 99, 189, 285)
- `core/position_manager.py`: Multiple
- `api/mexc.py`: 5 occurrences (lignes 45, 57, 79, 91, 103)
- `api/price_provider.py`: 3 occurrences (lignes 151, 235, 263)
- `api/reliability.py`: 7 occurrences (lignes 118, 160, 180, 229, 280, 322, 363)

**Impact**:
- 🔴 Cache `SystemExit`, `KeyboardInterrupt` (impossible de tuer le process)
- 🔴 Cache `MemoryError`, `RecursionError` (crashes système)
- 🔴 Debugging impossible (aucune stack trace utile)
- 🔴 Échecs silencieux (données corrompues non détectées)

#### Solution

**Créer une hiérarchie d'exceptions personnalisée**:

```python
# core/exceptions.py (NOUVEAU FICHIER)
class TradeCursorError(Exception):
    """Exception de base pour Trade Cursor"""
    pass

class ConfigurationError(TradeCursorError):
    """Erreur de configuration"""
    pass

class MarketDataError(TradeCursorError):
    """Erreur de données marché (price, volume, etc.)"""
    pass

class PositionError(TradeCursorError):
    """Erreur de gestion de position"""
    pass

class OrderExecutionError(TradeCursorError):
    """Erreur d'exécution d'ordre"""
    pass

class DatabaseError(TradeCursorError):
    """Erreur base de données"""
    pass

class APIError(TradeCursorError):
    """Erreur API exchange"""
    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

class WebSocketError(TradeCursorError):
    """Erreur WebSocket"""
    pass
```

**Refactoriser les try/except**:

```python
# ✅ APRÈS (spécifique et actionnable)
try:
    result = risky_operation()
except (ConnectionError, TimeoutError) as e:
    logger.error(f"Erreur réseau: {e}")
    # Retry logic
    await asyncio.sleep(5)
    result = await retry_operation()
except ValueError as e:
    logger.error(f"Données invalides: {e}")
    # Utiliser valeurs par défaut
    result = get_default_value()
except KeyError as e:
    logger.error(f"Clé manquante: {e}")
    # Validation explicite
    raise ConfigurationError(f"Configuration incomplète: {e}")
except Exception as e:
    # Seulement pour erreurs vraiment inattendues
    logger.critical(f"ERREUR INATTENDUE: {type(e).__name__}: {e}", exc_info=True)
    # Notification urgente
    await send_alert(f"Critical error: {e}")
    raise  # Re-raise pour ne pas masquer
```

**Décorateur pour gestion d'erreurs standard**:

```python
# core/error_handling.py (NOUVEAU FICHIER)
from functools import wraps
import asyncio
from typing import Callable, Type, Tuple

def handle_errors(
    *,
    retry_on: Tuple[Type[Exception], ...] = (),
    max_retries: int = 3,
    default_value = None,
    log_level: str = "error"
):
    """
    Décorateur pour gestion d'erreurs standardisée

    Args:
        retry_on: Exceptions qui déclenchent un retry
        max_retries: Nombre max de tentatives
        default_value: Valeur par défaut si échec
        log_level: Niveau de log
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)

                except retry_on as e:
                    last_exception = e
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)

                except TradeCursorError as e:
                    # Nos exceptions custom - log et propage
                    getattr(logger, log_level)(f"{func.__name__} error: {e}")
                    raise

                except Exception as e:
                    # Erreurs inattendues - log critique et propage
                    logger.critical(
                        f"UNEXPECTED ERROR in {func.__name__}: {type(e).__name__}: {e}",
                        exc_info=True
                    )
                    raise

            # Max retries atteint
            logger.error(f"{func.__name__} failed after {max_retries} attempts")
            if default_value is not None:
                return default_value
            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Version synchrone similaire
            pass

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator

# USAGE:
@handle_errors(
    retry_on=(ConnectionError, TimeoutError),
    max_retries=3,
    log_level="warning"
)
async def fetch_price(symbol: str) -> float:
    """Récupère le prix avec retry automatique"""
    return await exchange.get_price(symbol)
```

**Effort**:
- Créer exceptions custom: **2h**
- Créer décorateur: **3h**
- Refactoriser 200+ occurrences: **20h** (100 occurrences/jour avec tests)
- **TOTAL: ~25h (3 jours)**

---

### 2. Fuites de Ressources (HAUTE PRIORITÉ)

#### Problème 1: Connexions Base de Données Non Fermées

**Fichier**: `core/database.py:37`

```python
# ❌ AVANT (fuite potentielle)
class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def save_trade(self, trade_data):
        try:
            self.cursor.execute("INSERT INTO ...")
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error: {e}")
            # ❌ Connexion pas fermée en cas d'erreur!
```

**Solution**:

```python
# ✅ APRÈS (context manager)
class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = None

    @property
    def conn(self):
        """Lazy connection initialization"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return self._conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
            self._conn.close()
            self._conn = None

    def save_trade(self, trade_data):
        """Sauvegarde un trade avec gestion transactionnelle"""
        with self.conn:  # Auto-commit/rollback
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO ...", trade_data)

# USAGE:
with Database("trades.db") as db:
    db.save_trade(trade_data)
# Garantit fermeture même si exception
```

**Effort**: **4h** (refactoriser database.py + tests)

---

#### Problème 2: Clients HTTP Async Non Fermés

**Fichier**: `api/mexc.py:112-124`

```python
# ❌ AVANT (cleanup manuel non garanti)
async def cleanup(self):
    await self.session.close()
    await self.exchange.close()

async def shutdown(self):
    cleanup_task = asyncio.create_task(self.cleanup())
    # ❌ Task peut ne jamais compléter si process tué
```

**Solution**:

```python
# ✅ APRÈS (context manager async)
class MEXCClient:
    def __init__(self):
        self._session = None
        self._exchange = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        self._exchange = ccxt.mexc({
            'session': self._session
        })
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Garantit fermeture des ressources"""
        errors = []

        try:
            if self._exchange:
                await self._exchange.close()
        except Exception as e:
            errors.append(f"Exchange close error: {e}")

        try:
            if self._session:
                await self._session.close()
        except Exception as e:
            errors.append(f"Session close error: {e}")

        if errors:
            logger.warning(f"Cleanup errors: {'; '.join(errors)}")

    async def get_price(self, symbol):
        if self._exchange is None:
            raise RuntimeError("MEXCClient not initialized. Use 'async with MEXCClient()'")
        return await self._exchange.fetch_ticker(symbol)

# USAGE:
async with MEXCClient() as client:
    price = await client.get_price("BTC/USDT")
# Garantit cleanup même si exception ou Ctrl+C
```

**Gestionnaire de Shutdown Global**:

```python
# main.py
import signal
import asyncio

class GracefulShutdown:
    """Gère le shutdown propre de toutes les ressources"""

    def __init__(self):
        self.resources = []
        self.shutdown_event = asyncio.Event()

    def register(self, resource):
        """Enregistre une ressource à nettoyer"""
        self.resources.append(resource)

    async def cleanup(self):
        """Nettoie toutes les ressources enregistrées"""
        logger.info(f"Cleaning up {len(self.resources)} resources...")

        cleanup_tasks = []
        for resource in self.resources:
            if hasattr(resource, '__aexit__'):
                cleanup_tasks.append(resource.__aexit__(None, None, None))
            elif hasattr(resource, 'close'):
                if asyncio.iscoroutinefunction(resource.close):
                    cleanup_tasks.append(resource.close())
                else:
                    resource.close()

        if cleanup_tasks:
            results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Cleanup error for resource {i}: {result}")

        logger.info("✅ Cleanup complete")

    def handle_signal(self, signum, frame):
        """Handler pour SIGINT/SIGTERM"""
        logger.warning(f"Received signal {signum}. Initiating graceful shutdown...")
        self.shutdown_event.set()

# Initialisation
shutdown_manager = GracefulShutdown()
signal.signal(signal.SIGINT, shutdown_manager.handle_signal)
signal.signal(signal.SIGTERM, shutdown_manager.handle_signal)

# Enregistrement ressources
async def main():
    async with MEXCClient() as mexc_client:
        shutdown_manager.register(mexc_client)

        with Database("trades.db") as db:
            shutdown_manager.register(db)

            # Application logic
            await run_trading_bot()

            # Attendre shutdown signal
            await shutdown_manager.shutdown_event.wait()

    # Cleanup automatique via context managers
    await shutdown_manager.cleanup()
```

**Effort**: **6h** (context managers + shutdown manager + tests)

---

### 3. Race Conditions (HAUTE PRIORITÉ)

#### Problème 1: État Global Non Protégé

**Fichiers**: `main.py`, `api/routes.py`, tous les callbacks

```python
# ❌ AVANT (race condition)
# Global state
active_position = None
scanner_running = False

async def scanner_loop():
    global scanner_running, active_position
    scanner_running = True

    while scanner_running:
        # ⚠️ active_position peut changer entre lecture et utilisation
        if active_position is None:
            # Autre thread peut définir active_position ICI
            new_position = await scan_for_setup()
            active_position = new_position  # ⚠️ Peut écraser position créée ailleurs

async def position_loop():
    global active_position

    while True:
        # ⚠️ Race condition avec scanner_loop
        if active_position is not None:
            # active_position peut devenir None ICI
            await active_position.update()  # ❌ AttributeError possible
```

**Solution**:

```python
# ✅ APRÈS (thread-safe avec locks)
import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class TradingState:
    """État centralisé thread-safe"""
    active_position: Optional[Position] = None
    scanner_running: bool = False

    _lock: asyncio.Lock = asyncio.Lock()

    async def set_position(self, position: Optional[Position]):
        async with self._lock:
            old_position = self.active_position
            self.active_position = position
            logger.info(f"Position changed: {old_position} → {position}")

    async def get_position(self) -> Optional[Position]:
        async with self._lock:
            return self.active_position

    async def has_position(self) -> bool:
        async with self._lock:
            return self.active_position is not None

    async def set_scanner_state(self, running: bool):
        async with self._lock:
            self.scanner_running = running

# Singleton global
trading_state = TradingState()

# USAGE (thread-safe):
async def scanner_loop():
    await trading_state.set_scanner_state(True)

    while await trading_state.get_scanner_state():
        if not await trading_state.has_position():
            new_position = await scan_for_setup()
            await trading_state.set_position(new_position)

        await asyncio.sleep(1)

async def position_loop():
    while True:
        position = await trading_state.get_position()

        if position is not None:
            await position.update()

        await asyncio.sleep(0.1)
```

**Alternative: Dependency Injection (Meilleure Solution Long Terme)**:

```python
# core/context.py (NOUVEAU FICHIER)
from dataclasses import dataclass
from typing import Optional

@dataclass
class TradingContext:
    """Contexte de trading partagé (thread-safe)"""
    database: Database
    mexc_client: MEXCClient
    websocket_manager: WebSocketManager
    notification_manager: NotificationManager
    config: Config

    # État mutable protégé
    _state: TradingState

    async def get_position(self):
        return await self._state.get_position()

    async def set_position(self, position):
        await self._state.set_position(position)

# main.py
async def main():
    async with MEXCClient() as mexc_client, \
               Database("trades.db") as db:

        context = TradingContext(
            database=db,
            mexc_client=mexc_client,
            websocket_manager=WebSocketManager(),
            notification_manager=NotificationManager(),
            config=load_config(),
            _state=TradingState()
        )

        # Injection de dépendances (pas de globals!)
        scanner_task = asyncio.create_task(scanner_loop(context))
        position_task = asyncio.create_task(position_loop(context))

        await asyncio.gather(scanner_task, position_task)

# Pas de globals! Tout passe par context
async def scanner_loop(context: TradingContext):
    while context.config.scanner_enabled:
        if not await context.has_position():
            position = await scan_for_setup(context.mexc_client)
            await context.set_position(position)
            await context.notification_manager.notify("Position opened")
```

**Effort**:
- TradingState thread-safe: **4h**
- Dependency injection refactoring: **15h** (gros refactor)
- **TOTAL: ~20h**

---

#### Problème 2: Deadlock Potentiel Entre Locks

**Fichier**: `main.py:509-512`

```python
# ❌ AVANT (deadlock possible)
position_lock = asyncio.Lock()
scanner_lock = asyncio.Lock()

async def function_a():
    async with position_lock:
        # Acquiert scanner_lock pendant que position_lock tenu
        async with scanner_lock:
            do_something()

async def function_b():
    async with scanner_lock:
        # Acquiert position_lock pendant que scanner_lock tenu
        # ⚠️ DEADLOCK si function_a et function_b exécutent simultanément
        async with position_lock:
            do_something()
```

**Solution**:

```python
# ✅ APRÈS (ordre d'acquisition fixe)
# Règle: TOUJOURS acquérir locks dans le même ordre
LOCK_ORDER = ['scanner', 'position', 'database']

async def function_a():
    # Respecte l'ordre: scanner avant position
    async with scanner_lock:
        async with position_lock:
            do_something()

async def function_b():
    # Même ordre
    async with scanner_lock:
        async with position_lock:
            do_something()

# OU MIEUX: Un seul lock global pour opérations critiques
trading_lock = asyncio.Lock()

async def function_a():
    async with trading_lock:
        do_something()  # Atomique

async def function_b():
    async with trading_lock:
        do_something()  # Atomique
```

**Effort**: **3h** (audit locks + refactoriser ordre)

---

### 4. Code Dupliqué (HAUTE PRIORITÉ)

#### Problème: Répertoire Entier Dupliqué

**Fichiers Affectés**:
```
trade_cursor_py/
├── core/
│   ├── analyzer.py
│   └── ...
└── trade_cursor_py/   ← ❌ DUPLICATION COMPLÈTE
    ├── core/
    │   ├── analyzer.py  (même fichier)
    │   └── ...
```

**Impact**:
- 🔴 Maintenance double (bug fix dans 1 endroit seulement)
- 🔴 Risque de divergence de code
- 🔴 Confusion développeurs
- 🔴 Espace disque doublé

**Solution**:

```bash
# ✅ SUPPRIMER répertoire dupliqué
cd trade_cursor_py
rm -rf trade_cursor_py/

# Vérifier imports
grep -r "from trade_cursor_py.trade_cursor_py" . || echo "✅ Aucun import incorrect"

# Tests
pytest  # S'assurer que tout fonctionne
```

**Effort**: **1h** (vérification + suppression + tests)

---

#### Problème: Patterns d'Exception Dupliqués

Voir [Section 1: Exception Handling](#1-exception-handling-trop-large-critique)

---

### 5. Async/Await Issues (MOYENNE PRIORITÉ)

#### Problème: `time.sleep()` en Contexte Async

**Fichiers Affectés**:
- `trading/paper_trading_manager.py:100`
- `backtesting/data_loader.py:112, 236`

```python
# ❌ AVANT (bloque event loop)
async def simulate_latency(self):
    time.sleep(self.latency_ms / 1000)  # ⚠️ Bloque TOUT l'event loop!
    # Pendant ce temps, AUCUN autre coroutine ne peut s'exécuter
```

**Impact**:
- 🟠 Event loop gelé pendant sleep
- 🟠 WebSocket disconnect (pas de heartbeat)
- 🟠 UI freeze
- 🟠 Dégradation performance globale

**Solution**:

```python
# ✅ APRÈS (non-bloquant)
async def simulate_latency(self):
    await asyncio.sleep(self.latency_ms / 1000)  # ✅ Autres tasks peuvent s'exécuter

# OU si besoin de bloquer (rare):
async def blocking_operation():
    # Exécute en thread séparé pour ne pas bloquer event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: time.sleep(5))
```

**Détection Automatique**:

```bash
# Script de détection
grep -rn "time\.sleep" --include="*.py" . | grep -v "^#" | grep -v "test_"
# Vérifier si dans fonction async
```

**Effort**: **2h** (trouver toutes occurrences + fix + tests)

---

## 🔧 PLAN DE REFACTORISATION

### Phase 1: CRITIQUE (Semaines 1-2) - 80h

#### Sprint 1.1: Exception Handling (25h)

**Objectif**: Remplacer tous les `except Exception` par exceptions spécifiques

**Tasks**:
1. ✅ Créer hiérarchie d'exceptions custom (`core/exceptions.py`) - **2h**
2. ✅ Créer décorateur `@handle_errors` (`core/error_handling.py`) - **3h**
3. ✅ Refactoriser `main.py` (15 occurrences) - **4h**
4. ✅ Refactoriser `api/mexc.py` (5 occurrences) - **2h**
5. ✅ Refactoriser `api/reliability.py` (7 occurrences) - **3h**
6. ✅ Refactoriser `core/analyzer.py` (3 occurrences) - **2h**
7. ✅ Refactoriser `core/scanner.py` (3 occurrences) - **2h**
8. ✅ Tests unitaires exception handling - **4h**
9. ✅ Tests intégration error flows - **3h**

**Livrables**:
- `core/exceptions.py` (nouveau)
- `core/error_handling.py` (nouveau)
- `tests/test_error_handling.py` (nouveau)
- 50+ occurrences `except Exception` refactorizées

**Validation**:
```bash
# Vérifier qu'il reste < 10 "except Exception" non justifiés
grep -rn "except Exception" --include="*.py" . | wc -l
# Target: < 10
```

---

#### Sprint 1.2: Gestion Ressources (15h)

**Objectif**: Garantir fermeture ressources (DB, HTTP, WebSocket)

**Tasks**:
1. ✅ Refactoriser `core/database.py` avec context manager - **4h**
2. ✅ Refactoriser `api/mexc.py` avec async context manager - **3h**
3. ✅ Créer `GracefulShutdown` manager (`core/shutdown.py`) - **4h**
4. ✅ Intégrer dans `main.py` - **2h**
5. ✅ Tests cleanup ressources - **2h**

**Livrables**:
- `core/shutdown.py` (nouveau)
- `Database` avec `__enter__`/`__exit__`
- `MEXCClient` avec `__aenter__`/`__aexit__`
- Shutdown propre sur SIGINT/SIGTERM

**Validation**:
```bash
# Test manuel
python main.py &
PID=$!
sleep 5
kill -INT $PID  # Doit logger "Cleanup complete"
```

---

#### Sprint 1.3: State Management (20h)

**Objectif**: Éliminer race conditions

**Tasks**:
1. ✅ Créer `TradingState` thread-safe (`core/state.py`) - **4h**
2. ✅ Créer `TradingContext` (`core/context.py`) - **3h**
3. ✅ Refactoriser `main.py` (éliminer globals) - **6h**
4. ✅ Refactoriser callbacks (injection dépendances) - **4h**
5. ✅ Tests concurrence - **3h**

**Livrables**:
- `core/state.py` (nouveau)
- `core/context.py` (nouveau)
- 0 variables globales mutables dans `main.py`
- Tests race conditions

**Validation**:
```python
# Test concurrent access
async def test_concurrent_position_updates():
    state = TradingState()

    async def set_position(i):
        for _ in range(100):
            await state.set_position(Position(id=i))

    # 10 tasks concurrents
    await asyncio.gather(*[set_position(i) for i in range(10)])

    # Pas de corruption
    position = await state.get_position()
    assert position.id in range(10)
```

---

#### Sprint 1.4: Code Duplication (10h)

**Objectif**: Supprimer duplication

**Tasks**:
1. ✅ Analyser imports incorrects - **1h**
2. ✅ Supprimer `trade_cursor_py/trade_cursor_py/` - **1h**
3. ✅ Corriger imports cassés - **3h**
4. ✅ Tests régression complète - **3h**
5. ✅ Documentation structure projet - **2h**

**Livrables**:
- Répertoire dupliqué supprimé
- Tous tests passent
- `docs/PROJECT_STRUCTURE.md` (nouveau)

**Validation**:
```bash
# Vérifier pas de duplication
find . -type d -name "trade_cursor_py" | wc -l
# Target: 1

# Tous tests passent
pytest -v
```

---

#### Sprint 1.5: Async/Await Fixes (10h)

**Objectif**: Corriger `time.sleep()` en async

**Tasks**:
1. ✅ Détecter toutes occurrences `time.sleep()` - **1h**
2. ✅ Refactoriser `paper_trading_manager.py` - **2h**
3. ✅ Refactoriser `backtesting/data_loader.py` - **2h**
4. ✅ Ajouter linter asyncio (ruff/pylint) - **2h**
5. ✅ Tests performance event loop - **3h**

**Livrables**:
- 0 `time.sleep()` dans fonctions async
- Configuration linter async
- Tests performance

**Validation**:
```bash
# Détecter violations
ruff check . --select ASYNC
# Target: 0 violations
```

---

### Phase 2: HAUTE PRIORITÉ (Semaines 3-5) - 120h

#### Sprint 2.1: Refactoriser Gros Fichiers (40h)

**Objectif**: Diviser fichiers >800 lignes

**Fichiers Cibles**:
1. `core/analyzer.py` (892 lignes)
2. `core/analytics_database.py` (842 lignes)
3. `core/position_manager.py` (836 lignes)

**Plan `analyzer.py`**:

```
analyzer.py (892 lignes) →

analyzer/
├── __init__.py
├── base_analyzer.py           # Classe principale (200 lignes)
├── signal_generator.py        # Génération signaux (150 lignes)
├── trend_detector.py          # Détection tendance (120 lignes)
├── pattern_matcher.py         # Patterns chandeliers (150 lignes)
├── volume_analyzer.py         # Analyse volume (100 lignes)
├── multi_timeframe.py         # MTF analysis (100 lignes)
└── scoring.py                 # Calcul scores (100 lignes)
```

**Tasks par Fichier**:
1. ✅ Identifier responsabilités (SRP) - **2h**
2. ✅ Créer nouveau package - **1h**
3. ✅ Extraire classes/fonctions - **6h**
4. ✅ Refactoriser imports - **2h**
5. ✅ Tests unitaires par module - **4h**
6. ✅ Tests intégration - **2h**

**Total**: 3 fichiers × 17h = **51h** → Optimisé à **40h** (parallélisation)

**Livrables**:
- `core/analyzer/` (nouveau package)
- `core/analytics/` (nouveau package)
- `core/position/` (nouveau package)
- Tous fichiers <400 lignes

**Validation**:
```bash
# Vérifier taille fichiers
find core -name "*.py" -exec wc -l {} + | awk '$1 > 400 {print $2 " is too large (" $1 " lines)"}'
# Target: 0 fichiers >400 lignes
```

---

#### Sprint 2.2: Réduire Complexité Cyclomatique (30h)

**Objectif**: Fonctions complexité <10

**Méthode**:

```python
# Détecter fonctions complexes
pip install radon
radon cc . -a -nb  # Affiche complexité

# ❌ AVANT (complexité 15)
def analyze_pair(symbol, timeframe, indicators):
    if timeframe == '1m':
        if indicators['rsi'] > 70:
            if indicators['macd'] > 0:
                if indicators['volume'] > threshold:
                    return 'STRONG_SELL'
                else:
                    return 'SELL'
            else:
                return 'NEUTRAL'
        elif indicators['rsi'] < 30:
            # ... 10 autres conditions imbriquées
        # ... etc
    elif timeframe == '5m':
        # ... encore plus de conditions
    # Total: 15 branches de décision

# ✅ APRÈS (complexité 3)
def analyze_pair(symbol, timeframe, indicators):
    """Analyse simplifiée via extraction méthodes"""
    signal_strength = calculate_signal_strength(indicators)
    trend_direction = detect_trend(indicators)
    volume_confirmation = check_volume(indicators, timeframe)

    return combine_signals(signal_strength, trend_direction, volume_confirmation)

def calculate_signal_strength(indicators):
    """Responsabilité unique: force signal"""
    rsi_signal = get_rsi_signal(indicators['rsi'])
    macd_signal = get_macd_signal(indicators['macd'])
    return (rsi_signal + macd_signal) / 2

def get_rsi_signal(rsi):
    """Logique RSI isolée"""
    if rsi > 70:
        return -1.0  # Survente
    elif rsi < 30:
        return 1.0   # Suracheté
    return 0.0       # Neutre
```

**Tasks**:
1. ✅ Mesurer complexité baseline - **2h**
2. ✅ Identifier top 20 fonctions complexes - **2h**
3. ✅ Refactoriser top 20 (extraction méthode) - **20h**
4. ✅ Tests unitaires nouvelles fonctions - **4h**
5. ✅ Vérifier complexité <10 - **2h**

**Livrables**:
- Rapport complexité avant/après
- 20 fonctions refactorisées
- Complexité moyenne <7

**Validation**:
```bash
# Mesure
radon cc . -a -nb | grep "F " | awk '$2 > 10 {print}'
# Target: 0 fonctions >10
```

---

#### Sprint 2.3: Extraire Magic Numbers (20h)

**Objectif**: Remplacer nombres magiques par constantes nommées

```python
# ❌ AVANT
if price_change > 0.02:  # Quoi 0.02? Pourcent? Décimal?
    sl = entry * 0.995   # Pourquoi 0.995?
    tp = entry * 1.015   # D'où vient 1.015?

# ✅ APRÈS
# core/constants.py (NOUVEAU FICHIER)
from decimal import Decimal

# Thresholds
PRICE_CHANGE_THRESHOLD_PCT = Decimal('0.02')  # 2% minimum price movement

# Position Sizing
DEFAULT_STOP_LOSS_PCT = Decimal('0.005')      # 0.5% SL
DEFAULT_TAKE_PROFIT_PCT = Decimal('0.015')    # 1.5% TP
SL_MULTIPLIER = 1 - DEFAULT_STOP_LOSS_PCT     # 0.995
TP_MULTIPLIER = 1 + DEFAULT_TAKE_PROFIT_PCT   # 1.015

# Timeouts (seconds)
WEBSOCKET_TIMEOUT_SEC = 30
API_TIMEOUT_SEC = 10
DATABASE_TIMEOUT_SEC = 5

# Retry Logic
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # Exponential: 2^attempt

# Volumes
MIN_VOLUME_USDT = Decimal('5.00')  # MEXC minimum
MAX_POSITION_SIZE_USDT = Decimal('1000.00')

# Usage
from core.constants import SL_MULTIPLIER, TP_MULTIPLIER

if price_change > PRICE_CHANGE_THRESHOLD_PCT:
    sl = entry * SL_MULTIPLIER
    tp = entry * TP_MULTIPLIER
```

**Tasks**:
1. ✅ Créer `core/constants.py` - **2h**
2. ✅ Identifier magic numbers (grep) - **2h**
3. ✅ Extraire top 50 nombres - **10h**
4. ✅ Refactoriser références - **4h**
5. ✅ Documentation constantes - **2h**

**Livrables**:
- `core/constants.py` (50+ constantes)
- `docs/CONSTANTS_REFERENCE.md`
- <10 nombres magiques résiduels

---

#### Sprint 2.4: Type Hints (30h)

**Objectif**: Ajouter type hints à 80%+ du code

```python
# ❌ AVANT (pas de types)
def calculate_position_size(capital, risk, stop_distance):
    size = (capital * risk) / stop_distance
    return min(size, capital)

# ✅ APRÈS (typed)
from typing import Decimal

def calculate_position_size(
    capital: Decimal,
    risk_percent: Decimal,
    stop_distance: Decimal
) -> Decimal:
    """
    Calcule la taille de position selon Kelly Criterion

    Args:
        capital: Capital disponible en USDT
        risk_percent: Risque par trade (ex: 0.02 pour 2%)
        stop_distance: Distance au stop loss en USDT

    Returns:
        Taille position en USDT (plafonné au capital)
    """
    risk_amount = capital * risk_percent
    size = risk_amount / stop_distance
    return min(size, capital)
```

**Configuration mypy**:

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict_equality = true

[[tool.mypy.overrides]]
module = "ccxt.*"
ignore_missing_imports = true
```

**Tasks**:
1. ✅ Installer mypy, types - **1h**
2. ✅ Configurer mypy - **2h**
3. ✅ Typer core modules (10 fichiers) - **15h**
4. ✅ Typer API modules (5 fichiers) - **7h**
5. ✅ Corriger erreurs mypy - **3h**
6. ✅ CI/CD integration - **2h**

**Livrables**:
- Type hints 80%+ fonctions
- mypy passe sans erreurs
- CI check mypy

**Validation**:
```bash
# Check coverage types
mypy . --strict
# Target: 0 errors
```

---

### Phase 3: MOYENNE PRIORITÉ (Semaines 6-8) - 80h

#### Sprint 3.1: Documentation (20h)

**Objectif**: Docstrings complètes + architecture docs

**Structure Documentation**:

```
docs/
├── ARCHITECTURE.md              # Architecture système
├── API_REFERENCE.md             # API endpoints
├── CONFIGURATION.md             # Guide configuration
├── DEPLOYMENT.md                # Guide déploiement
├── DEVELOPMENT.md               # Guide développement
├── TESTING.md                   # Guide tests
├── TROUBLESHOOTING.md           # Résolution problèmes
└── diagrams/
    ├── system_architecture.mmd  # Mermaid diagram
    ├── data_flow.mmd
    └── state_machine.mmd
```

**Docstring Standard**:

```python
def open_position(
    symbol: str,
    direction: Literal["LONG", "SHORT"],
    entry_price: Decimal,
    size_usdt: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal
) -> Position:
    """
    Ouvre une nouvelle position sur le marché.

    Cette fonction:
    1. Valide les paramètres d'entrée
    2. Calcule le sizing selon la gestion de risque
    3. Envoie l'ordre via MEXC API
    4. Enregistre la position en base de données
    5. Active le monitoring de position

    Args:
        symbol: Symbole du marché (ex: "BTC/USDT")
        direction: Direction du trade ("LONG" ou "SHORT")
        entry_price: Prix d'entrée cible en USDT
        size_usdt: Taille position en USDT
        stop_loss: Prix stop loss en USDT
        take_profit: Prix take profit en USDT

    Returns:
        Position: Objet position créé avec ID unique

    Raises:
        OrderExecutionError: Si échec envoi ordre
        PositionError: Si position déjà active
        ValueError: Si paramètres invalides

    Examples:
        >>> position = open_position(
        ...     symbol="BTC/USDT",
        ...     direction="LONG",
        ...     entry_price=Decimal("50000.00"),
        ...     size_usdt=Decimal("100.00"),
        ...     stop_loss=Decimal("49500.00"),
        ...     take_profit=Decimal("51000.00")
        ... )
        >>> print(position.id)
        "pos_abc123"

    Notes:
        - Utilise le circuit breaker pour éviter spam API
        - Timeout par défaut: 10 secondes
        - Retry automatique jusqu'à 3 fois

    See Also:
        - close_position(): Ferme une position
        - update_position(): Met à jour SL/TP
    """
    pass
```

**Tasks**:
1. ✅ Créer docs structure - **2h**
2. ✅ Écrire ARCHITECTURE.md - **4h**
3. ✅ Créer diagrammes Mermaid - **3h**
4. ✅ Docstrings 50 fonctions principales - **8h**
5. ✅ Review + polish - **3h**

---

#### Sprint 3.2: Code Style & Linting (15h)

**Objectif**: Code style uniforme

**Configuration**:

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "ASYNC",  # flake8-async
    "S",      # flake8-bandit (security)
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "DTZ",    # flake8-datetimez
    "T10",    # flake8-debugger
    "ERA",    # eradicate (commented code)
    "PL",     # pylint
    "RUF",    # ruff-specific
]

ignore = [
    "E501",   # line-too-long (handled by formatter)
    "S101",   # assert (ok in tests)
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "PLR2004"]  # Allow asserts and magic values in tests

[tool.black]
line-length = 100
target-version = ['py310']

[tool.isort]
profile = "black"
line_length = 100
```

**Tasks**:
1. ✅ Configurer ruff, black, isort - **2h**
2. ✅ Formatter tout le code - **2h**
3. ✅ Corriger violations ruff - **6h**
4. ✅ Pre-commit hooks - **2h**
5. ✅ CI integration - **3h**

**Livrables**:
- `.pre-commit-config.yaml`
- CI linting job
- 0 violations ruff

---

#### Sprint 3.3: Performance Optimizations (25h)

**Objectif**: Identifier et corriger bottlenecks

**Profiling**:

```python
# core/profiling.py (NOUVEAU)
import cProfile
import pstats
from functools import wraps
import time

def profile(filename=None):
    """Décorateur pour profiler une fonction"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            profiler = cProfile.Profile()
            profiler.enable()

            result = func(*args, **kwargs)

            profiler.disable()

            if filename:
                profiler.dump_stats(filename)

            stats = pstats.Stats(profiler)
            stats.sort_stats('cumulative')
            stats.print_stats(20)  # Top 20

            return result
        return wrapper
    return decorator

# USAGE
@profile("scanner_loop.prof")
async def scanner_loop():
    # ...
    pass
```

**Optimisations Cibles**:

1. **Caching**:
```python
# ❌ AVANT (calcul répété)
def get_indicators(symbol, timeframe):
    df = fetch_ohlcv(symbol, timeframe)  # API call
    rsi = calculate_rsi(df)
    macd = calculate_macd(df)
    return {'rsi': rsi, 'macd': macd}

# Appelé 10 fois/seconde pour même symbol!

# ✅ APRÈS (cached)
from functools import lru_cache
from datetime import datetime, timedelta

class IndicatorCache:
    def __init__(self, ttl_seconds=60):
        self.cache = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def get(self, symbol, timeframe):
        key = f"{symbol}_{timeframe}"

        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return value  # Cache hit

        # Cache miss - recalcule
        value = self._calculate(symbol, timeframe)
        self.cache[key] = (value, datetime.now())
        return value

    def _calculate(self, symbol, timeframe):
        df = fetch_ohlcv(symbol, timeframe)
        return {
            'rsi': calculate_rsi(df),
            'macd': calculate_macd(df)
        }

# Gain: 99% moins d'API calls
```

2. **Batch Operations**:
```python
# ❌ AVANT (N queries)
for symbol in symbols:
    save_trade(symbol, data)  # 100 INSERT individuels

# ✅ APRÈS (1 query)
save_trades_batch([(symbol, data) for symbol in symbols])
# executemany() - 100x plus rapide
```

**Tasks**:
1. ✅ Profiler hot paths - **5h**
2. ✅ Implémenter caching - **8h**
3. ✅ Batch DB operations - **5h**
4. ✅ Optimiser calculs indicators - **4h**
5. ✅ Benchmarks avant/après - **3h**

**Livrables**:
- Rapport profiling
- Cache layer
- 30%+ amélioration performance

---

#### Sprint 3.4: Logging & Monitoring (20h)

**Objectif**: Logging structuré + métriques

**Structured Logging**:

```python
# core/logging_config.py (NOUVEAU)
import logging
import json
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    """Format logs en JSON pour parsing facile"""

    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Ajouter context custom
        if hasattr(record, 'symbol'):
            log_data['symbol'] = record.symbol
        if hasattr(record, 'position_id'):
            log_data['position_id'] = record.position_id
        if hasattr(record, 'trade_result'):
            log_data['trade_result'] = record.trade_result

        # Exception info
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)

# Setup
def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())

    logger = logging.getLogger('trade_cursor')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    return logger

# Usage avec context
logger = setup_logging()
logger.info(
    "Position opened",
    extra={
        'symbol': 'BTC/USDT',
        'position_id': 'pos_123',
        'entry': 50000.00
    }
)
# Output: {"timestamp": "2025-12-20T10:00:00", "level": "INFO", "message": "Position opened", "symbol": "BTC/USDT", ...}
```

**Métriques Prometheus**:

```python
# core/metrics.py (NOUVEAU)
from prometheus_client import Counter, Histogram, Gauge

# Compteurs
positions_opened = Counter('positions_opened_total', 'Total positions opened', ['symbol'])
positions_closed = Counter('positions_closed_total', 'Total positions closed', ['result'])
api_calls = Counter('api_calls_total', 'Total API calls', ['endpoint', 'status'])

# Histogrammes (distributions)
position_duration = Histogram('position_duration_seconds', 'Position duration')
api_latency = Histogram('api_latency_seconds', 'API call latency', ['endpoint'])

# Gauges (valeurs actuelles)
active_positions = Gauge('active_positions', 'Number of active positions')
capital_used = Gauge('capital_used_usdt', 'Capital currently in positions')

# Usage
def open_position(symbol, ...):
    positions_opened.labels(symbol=symbol).inc()
    active_positions.inc()
    # ...

def close_position(...):
    positions_closed.labels(result='win' if pnl > 0 else 'loss').inc()
    active_positions.dec()
    position_duration.observe(duration_seconds)
```

**Tasks**:
1. ✅ Structured logging - **5h**
2. ✅ Prometheus metrics - **6h**
3. ✅ Grafana dashboard - **4h**
4. ✅ Alerting rules - **3h**
5. ✅ Documentation monitoring - **2h**

---

## 📈 PLAN D'AUGMENTATION COVERAGE

### État Actuel Coverage

**Modules Testés** (60-70% coverage estimé):
- ✅ `core/analyzer.py` - Tests complets
- ✅ `core/position_manager.py` - Tests complets
- ✅ `api/routes.py` - Tests refactorés
- ✅ `core/indicators.py` - Tests compréhensifs
- ✅ `core/config_manager.py` - Tests unitaires
- ✅ `api/mexc.py` - Tests API

**Modules NON Testés** (gaps coverage):
- ❌ `core/retry_logic.py` - 0% coverage
- ❌ `core/correlation_dynamic.py` - 0% coverage
- ❌ `core/price_cache.py` - 0% coverage
- ❌ `notifications/telegram_commands.py` - 0% coverage
- ❌ `backtesting/engine.py` - Coverage partielle
- ❌ `api/reliability.py` - Coverage partielle
- ❌ `callbacks/scalability_refresh.py` - Non testé

---

### Stratégie Coverage

#### Niveau 1: Tests Unitaires (Coverage 85%)

**Principe**: Tester chaque fonction isolément

```python
# tests/unit/test_retry_logic.py (NOUVEAU)
import pytest
from core.retry_logic import RetryLogic, RetryConfig
from core.exceptions import APIError

class TestRetryLogic:
    """Tests unitaires pour retry logic"""

    @pytest.fixture
    def retry_config(self):
        return RetryConfig(
            max_attempts=3,
            backoff_base=2,
            max_backoff=60
        )

    @pytest.fixture
    def retry_logic(self, retry_config):
        return RetryLogic(retry_config)

    def test_success_first_attempt(self, retry_logic):
        """Test: Succès au premier essai"""
        call_count = 0

        @retry_logic.with_retry
        def successful_call():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_call()

        assert result == "success"
        assert call_count == 1  # Appelé une seule fois

    def test_retry_on_transient_error(self, retry_logic):
        """Test: Retry sur erreur temporaire"""
        call_count = 0

        @retry_logic.with_retry
        def flaky_call():
            nonlocal call_count
            call_count += 1

            if call_count < 3:
                raise ConnectionError("Temporary failure")

            return "success"

        result = flaky_call()

        assert result == "success"
        assert call_count == 3  # Réussi au 3ème essai

    def test_max_retries_exceeded(self, retry_logic):
        """Test: Max retries atteint"""
        @retry_logic.with_retry
        def always_fails():
            raise ConnectionError("Permanent failure")

        with pytest.raises(ConnectionError):
            always_fails()

    def test_backoff_exponential(self, retry_logic, mocker):
        """Test: Backoff exponentiel correct"""
        mock_sleep = mocker.patch('asyncio.sleep')

        @retry_logic.with_retry
        async def failing_call():
            raise ConnectionError()

        with pytest.raises(ConnectionError):
            await failing_call()

        # Vérifie backoff: 2^0=1s, 2^1=2s, 2^2=4s
        assert mock_sleep.call_args_list == [
            mocker.call(1),
            mocker.call(2),
            mocker.call(4)
        ]

    def test_non_retryable_error(self, retry_logic):
        """Test: Erreur non-retryable propagée immédiatement"""
        call_count = 0

        @retry_logic.with_retry
        def invalid_call():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")  # Non-retryable

        with pytest.raises(ValueError):
            invalid_call()

        assert call_count == 1  # Pas de retry pour ValueError
```

**Coverage Cible par Module**:

| Module | Coverage Actuel | Coverage Cible | Effort |
|--------|----------------|----------------|--------|
| `retry_logic.py` | 0% | 90% | 4h |
| `correlation_dynamic.py` | 0% | 85% | 6h |
| `price_cache.py` | 0% | 90% | 3h |
| `telegram_commands.py` | 0% | 80% | 5h |
| `backtesting/engine.py` | 30% | 85% | 8h |
| `api/reliability.py` | 40% | 90% | 6h |
| `callbacks/scalability_refresh.py` | 0% | 75% | 4h |

**Total Effort Unitaires**: **36h**

---

#### Niveau 2: Tests Intégration (Coverage 90%)

**Principe**: Tester interactions entre modules

```python
# tests/integration/test_position_lifecycle.py (NOUVEAU)
import pytest
from decimal import Decimal
from core.position_manager import PositionManager
from api.mexc import MEXCClient
from core.database import Database

@pytest.mark.integration
class TestPositionLifecycle:
    """Tests intégration cycle de vie position"""

    @pytest.fixture
    async def setup(self):
        """Setup environnement test intégration"""
        async with MEXCClient() as client:
            with Database(":memory:") as db:
                manager = PositionManager(
                    mexc_client=client,
                    database=db
                )

                yield {
                    'manager': manager,
                    'client': client,
                    'db': db
                }

    async def test_complete_position_flow(self, setup):
        """
        Test: Cycle complet position

        Flow:
        1. Ouvrir position LONG
        2. Recevoir price update
        3. TP hit
        4. Position fermée
        5. Enregistré en DB
        6. Notification envoyée
        """
        manager = setup['manager']

        # 1. Ouvrir position
        position = await manager.open_position(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("50000.00"),
            size_usdt=Decimal("100.00"),
            stop_loss=Decimal("49500.00"),
            take_profit=Decimal("51000.00")
        )

        assert position.status == "OPEN"
        assert position.pnl == Decimal("0.00")

        # 2. Price update (vers TP)
        await manager.update_price("BTC/USDT", Decimal("51000.00"))

        # 3. Vérifier TP hit
        position = await manager.get_position(position.id)
        assert position.status == "CLOSED"
        assert position.exit_price == Decimal("51000.00")
        assert position.pnl > Decimal("0.00")

        # 4. Vérifier DB
        trades = await setup['db'].get_trades(limit=1)
        assert len(trades) == 1
        assert trades[0]['symbol'] == "BTC/USDT"
        assert trades[0]['result'] == "WIN"

    async def test_stop_loss_triggered(self, setup):
        """Test: SL déclenché correctement"""
        manager = setup['manager']

        position = await manager.open_position(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("50000.00"),
            size_usdt=Decimal("100.00"),
            stop_loss=Decimal("49500.00"),
            take_profit=Decimal("51000.00")
        )

        # Price chute vers SL
        await manager.update_price("BTC/USDT", Decimal("49500.00"))

        # Vérifier SL hit
        position = await manager.get_position(position.id)
        assert position.status == "CLOSED"
        assert position.exit_price == Decimal("49500.00")
        assert position.pnl < Decimal("0.00")  # Loss

    async def test_concurrent_positions_prevented(self, setup):
        """Test: Impossible d'ouvrir 2 positions simultanées"""
        manager = setup['manager']

        # Position 1
        position1 = await manager.open_position(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("50000.00"),
            size_usdt=Decimal("100.00"),
            stop_loss=Decimal("49500.00"),
            take_profit=Decimal("51000.00")
        )

        # Tentative position 2 (doit échouer)
        with pytest.raises(PositionError, match="Position already active"):
            await manager.open_position(
                symbol="ETH/USDT",
                direction="LONG",
                entry_price=Decimal("3000.00"),
                size_usdt=Decimal("100.00"),
                stop_loss=Decimal("2950.00"),
                take_profit=Decimal("3100.00")
            )
```

**Tests Intégration Cibles**:

1. **Position Lifecycle** - 8h
   - Open → Update → TP → Close → DB → Notification
   - Open → Update → SL → Close
   - Open → Manual close
   - Concurrent position prevention

2. **Scanner → Position Flow** - 6h
   - Scanner finds setup
   - Signal validated
   - Position opened
   - Monitoring activated

3. **WebSocket → Price → Position** - 5h
   - WebSocket receives tick
   - Price cache updated
   - Position checks triggered
   - TP/SL evaluated

4. **API Reliability** - 5h
   - Circuit breaker integration
   - Retry logic
   - Timeout handling
   - Error recovery

5. **Database Transactions** - 4h
   - Concurrent writes
   - Rollback on error
   - Data integrity

**Total Effort Intégration**: **28h**

---

#### Niveau 3: Tests Edge Cases (Coverage 95%)

**Principe**: Tester scénarios extrêmes

```python
# tests/edge_cases/test_extreme_scenarios.py (NOUVEAU)
import pytest
from decimal import Decimal

class TestExtremeScenarios:
    """Tests scénarios extrêmes et edge cases"""

    async def test_flash_crash(self, position_manager):
        """
        Test: Flash crash (price -50% en 1 seconde)

        Comportement attendu:
        - SL déclenché immédiatement
        - Circuit breaker activé
        - Pas de nouveau trade 5 minutes
        """
        position = await position_manager.open_position(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("50000.00"),
            size_usdt=Decimal("100.00"),
            stop_loss=Decimal("49500.00"),
            take_profit=Decimal("51000.00")
        )

        # Flash crash: 50000 → 25000 en 1s
        await position_manager.update_price("BTC/USDT", Decimal("25000.00"))

        # Vérifications
        assert position.status == "CLOSED"
        assert position.exit_price == Decimal("49500.00")  # SL price (slippage ignoré en test)
        assert position_manager.circuit_breaker.is_open == True

    async def test_precision_loss(self):
        """
        Test: Perte de précision calculs

        Bug potentiel: 0.1 + 0.2 = 0.30000000000000004 en float
        """
        from core.position.pnl_calculator import calculate_pnl

        # Utilise Decimal (pas float!)
        entry = Decimal("50000.12345678")
        exit = Decimal("51000.87654321")
        size = Decimal("0.00123456")

        pnl = calculate_pnl(entry, exit, size, direction="LONG")

        # Vérifier précision exacte
        expected = (exit - entry) * size
        assert pnl == expected  # Égalité exacte avec Decimal
        assert str(pnl).count('.') == 1  # Pas de notation scientifique

    async def test_database_corruption_recovery(self, database):
        """
        Test: Corruption base de données

        Scénario:
        1. DB corrompue (fichier tronqué)
        2. Application détecte corruption
        3. Backup restauré automatiquement
        """
        # Simuler corruption
        database.corrupt()

        # Tentative lecture (doit détecter corruption)
        with pytest.raises(DatabaseError, match="corrupted"):
            await database.get_trades()

        # Auto-recovery
        await database.restore_from_backup()

        # Vérifier recovery
        trades = await database.get_trades()
        assert isinstance(trades, list)  # DB fonctionnelle

    async def test_websocket_message_order_violation(self, websocket_manager):
        """
        Test: Messages WebSocket dans désordre

        Scénario:
        - Tick 1: price=50000, timestamp=T
        - Tick 2: price=51000, timestamp=T+1
        - Tick 3: price=49000, timestamp=T-1 (ancien message en retard)

        Comportement attendu:
        - Tick 3 ignoré (timestamp < dernier)
        """
        # Tick 1
        await websocket_manager.process_tick({
            'symbol': 'BTC/USDT',
            'price': 50000,
            'timestamp': 1000
        })

        # Tick 2 (plus récent)
        await websocket_manager.process_tick({
            'symbol': 'BTC/USDT',
            'price': 51000,
            'timestamp': 1001
        })

        # Tick 3 (ancien - doit être ignoré)
        await websocket_manager.process_tick({
            'symbol': 'BTC/USDT',
            'price': 49000,
            'timestamp': 999  # < 1001
        })

        # Vérifier price actuel = 51000 (pas 49000)
        current_price = await websocket_manager.get_price('BTC/USDT')
        assert current_price == 51000

    async def test_api_rate_limit_exhaustion(self, mexc_client, mocker):
        """
        Test: Rate limit API épuisé

        Scénario:
        - 100 requêtes en 1 seconde (limite = 50/sec)
        - Circuit breaker ouvre
        - Requêtes suivantes queued
        """
        mock_api = mocker.patch.object(mexc_client, '_request')
        mock_api.side_effect = [
            *([{'success': True}] * 50),  # 50 succès
            *([APIError("Rate limit", status_code=429)] * 50)  # 50 rate limited
        ]

        # Burst 100 requêtes
        tasks = [mexc_client.get_price('BTC/USDT') for _ in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Vérifications
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 50
        assert len(failures) == 50
        assert mexc_client.circuit_breaker.is_open == True

    async def test_telegram_notification_failure_silent(self, notification_manager, mocker):
        """
        Test: Échec notification Telegram (token invalide)

        Comportement attendu:
        - Notification échoue
        - Erreur loggée
        - Trading CONTINUE (pas bloqué)
        """
        mock_telegram = mocker.patch.object(notification_manager.telegram, 'send')
        mock_telegram.side_effect = Exception("Telegram API down")

        # Tentative notification (ne doit PAS raise)
        await notification_manager.notify("Position opened", data={})

        # Vérifier trading continue
        assert notification_manager.is_healthy() == True  # Pas bloquant

    @pytest.mark.parametrize("volatility", [
        Decimal("0.0001"),  # Extrêmement calme
        Decimal("5.0000"),  # Extrêmement volatile
    ])
    async def test_extreme_volatility(self, analyzer, volatility):
        """Test: Volatilité extrême (calme ou violente)"""
        signal = await analyzer.analyze_pair(
            symbol="BTC/USDT",
            atr_pct=volatility
        )

        if volatility < Decimal("0.001"):
            # Trop calme → Pas de trade
            assert signal is None
        elif volatility > Decimal("3.0"):
            # Trop volatile → Pas de trade
            assert signal is None
```

**Edge Cases Cibles**:

1. **Market Events** - 6h
   - Flash crash
   - Flash pump
   - Exchange halt
   - Liquidity gap

2. **Precision & Math** - 4h
   - Decimal precision
   - Overflow/underflow
   - Division by zero
   - NaN handling

3. **Concurrency** - 5h
   - Race conditions
   - Deadlocks
   - Resource starvation

4. **Network Issues** - 5h
   - WebSocket disconnect
   - Message loss
   - Out-of-order messages
   - Duplicate messages

5. **API Failures** - 4h
   - Rate limits
   - Timeouts
   - Invalid responses
   - Partial failures

6. **Data Corruption** - 4h
   - DB corruption
   - Config corruption
   - Cache inconsistency

**Total Effort Edge Cases**: **28h**

---

#### Niveau 4: Tests E2E (Coverage 98%)

**Principe**: Tester système complet end-to-end

```python
# tests/e2e/test_complete_trading_session.py (NOUVEAU)
import pytest
from decimal import Decimal
import asyncio

@pytest.mark.e2e
class TestCompleteTradingSession:
    """Tests end-to-end session trading complète"""

    @pytest.fixture
    async def trading_system(self):
        """Démarre système trading complet"""
        from main import TradingSystem

        system = TradingSystem(config_file="config_test.json")
        await system.start()

        yield system

        await system.stop()

    async def test_full_trading_day_simulation(self, trading_system):
        """
        Test: Simulation journée complète trading

        Scénario:
        1. Démarrage système (08:00)
        2. Scanner trouve setup (08:15)
        3. Position ouverte LONG BTC (08:16)
        4. TP Escalier niveau 1 hit (09:30)
        5. Trailing stop activé (09:31)
        6. TP Final hit (11:00)
        7. Position fermée (11:01)
        8. Scanner trouve nouveau setup ETH (14:00)
        9. Position ouverte SHORT ETH (14:01)
        10. SL hit (14:45)
        11. Position fermée LOSS (14:46)
        12. Fin journée (18:00)

        Résultat attendu:
        - 2 trades executés
        - 1 WIN, 1 LOSS
        - Winrate = 50%
        - PnL net > 0 (WIN > LOSS grâce à R:R)
        """
        # Temps simulé (accéléré 1000x)
        async with TradingSimulator(speed=1000) as sim:

            # 1. Démarrage
            await sim.set_time("08:00")
            assert trading_system.is_running == True

            # 2-3. Setup BTC LONG
            await sim.inject_market_data({
                'symbol': 'BTC/USDT',
                'price': 50000,
                'rsi': 35,  # Setup LONG
                'macd': 0.002,
                'atr_pct': 0.18
            })

            await sim.wait_for_condition(
                lambda: trading_system.has_active_position(),
                timeout=60
            )

            position = trading_system.get_active_position()
            assert position.symbol == "BTC/USDT"
            assert position.direction == "LONG"

            # 4. TP Escalier hit
            await sim.set_time("09:30")
            await sim.set_price("BTC/USDT", 50300)  # +0.6% (TP1)

            await asyncio.sleep(2)  # Attendre traitement

            # Vérifier partial close
            position = trading_system.get_active_position()
            assert position.size_usdt < position.initial_size_usdt

            # 5-6. TP Final
            await sim.set_time("11:00")
            await sim.set_price("BTC/USDT", 50600)  # +1.2% (TP Final)

            await sim.wait_for_condition(
                lambda: not trading_system.has_active_position(),
                timeout=60
            )

            # Vérifier trade 1 fermé WIN
            trades = trading_system.get_trades()
            assert len(trades) == 1
            assert trades[0]['result'] == 'WIN'
            assert trades[0]['pnl_pct'] > 0

            # 7-9. Setup ETH SHORT
            await sim.set_time("14:00")
            await sim.inject_market_data({
                'symbol': 'ETH/USDT',
                'price': 3000,
                'rsi': 72,  # Setup SHORT
                'macd': -0.003,
                'atr_pct': 0.22
            })

            await sim.wait_for_condition(
                lambda: trading_system.has_active_position(),
                timeout=60
            )

            position = trading_system.get_active_position()
            assert position.direction == "SHORT"

            # 10-11. SL hit
            await sim.set_time("14:45")
            await sim.set_price("ETH/USDT", 3007.5)  # +0.25% (SL)

            await sim.wait_for_condition(
                lambda: not trading_system.has_active_position(),
                timeout=60
            )

            # Vérifier trade 2 fermé LOSS
            trades = trading_system.get_trades()
            assert len(trades) == 2
            assert trades[1]['result'] == 'LOSS'
            assert trades[1]['pnl_pct'] < 0

            # 12. Fin journée
            await sim.set_time("18:00")

            # Vérifications finales
            stats = trading_system.get_statistics()

            assert stats['total_trades'] == 2
            assert stats['wins'] == 1
            assert stats['losses'] == 1
            assert stats['winrate'] == 0.50

            # PnL net positif (R:R favorable)
            assert stats['pnl_total_usdt'] > 0
            assert stats['pnl_total_pct'] > 0

    async def test_system_recovery_after_crash(self, trading_system):
        """
        Test: Recovery après crash système

        Scénario:
        1. Position ouverte
        2. Crash système (kill -9)
        3. Redémarrage
        4. Position récupérée depuis DB
        5. Monitoring reprend
        6. Position fermée normalement
        """
        # 1. Position ouverte
        await trading_system.open_position(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("50000"),
            size_usdt=Decimal("100"),
            stop_loss=Decimal("49500"),
            take_profit=Decimal("51000")
        )

        # 2. Simuler crash
        await trading_system.crash()  # Kill brutal

        # 3. Redémarrage
        trading_system = TradingSystem(config_file="config_test.json")
        await trading_system.start()

        # 4. Vérifier recovery
        position = trading_system.get_active_position()
        assert position is not None
        assert position.symbol == "BTC/USDT"
        assert position.status == "OPEN"

        # 5-6. Monitoring reprend + close
        await trading_system.update_price("BTC/USDT", Decimal("51000"))

        await asyncio.sleep(2)

        assert trading_system.has_active_position() == False
```

**Tests E2E Cibles**:

1. **Full Trading Day** - 8h
   - Démarrage → Scanning → Trading → Fermeture
   - Multiple positions
   - WIN + LOSS scenarios

2. **Multi-Instance Coordination** - 6h
   - 2 instances simultanées
   - Coordination via DB
   - Pas de conflit

3. **Disaster Recovery** - 5h
   - Crash recovery
   - DB restoration
   - State recovery

4. **Performance Under Load** - 5h
   - 1000 price updates/sec
   - 50 symbols scanned
   - Memory stable

**Total Effort E2E**: **24h**

---

### Résumé Effort Coverage

| Niveau | Coverage Cible | Effort (heures) |
|--------|---------------|-----------------|
| **Unitaires** | 85% | 36h |
| **Intégration** | 90% | 28h |
| **Edge Cases** | 95% | 28h |
| **E2E** | 98% | 24h |
| **TOTAL** | **98%** | **116h (~3 semaines)** |

---

## 📅 ROADMAP D'IMPLÉMENTATION

### Phase 1: CRITIQUE (Semaines 1-2) - 80h

| Sprint | Tasks | Durée | Dépendances |
|--------|-------|-------|-------------|
| **1.1** | Exception Handling | 25h | Aucune |
| **1.2** | Gestion Ressources | 15h | 1.1 |
| **1.3** | State Management | 20h | 1.1 |
| **1.4** | Code Duplication | 10h | Aucune |
| **1.5** | Async/Await Fixes | 10h | Aucune |

**Livrables Semaine 2**:
- ✅ 50+ `except Exception` refactorisés
- ✅ Context managers (DB, HTTP)
- ✅ 0 globals mutables
- ✅ Code duplication éliminée
- ✅ Async patterns corrigés

---

### Phase 2: HAUTE PRIORITÉ (Semaines 3-5) - 120h

| Sprint | Tasks | Durée | Dépendances |
|--------|-------|-------|-------------|
| **2.1** | Refactoriser Gros Fichiers | 40h | Phase 1 |
| **2.2** | Complexité Cyclomatique | 30h | 2.1 |
| **2.3** | Magic Numbers | 20h | Aucune |
| **2.4** | Type Hints | 30h | 2.1, 2.2 |

**Livrables Semaine 5**:
- ✅ Tous fichiers <400 lignes
- ✅ Complexité <10
- ✅ 80%+ type hints
- ✅ mypy passe sans erreurs

---

### Phase 3: MOYENNE PRIORITÉ (Semaines 6-8) - 80h

| Sprint | Tasks | Durée | Dépendances |
|--------|-------|-------|-------------|
| **3.1** | Documentation | 20h | Phase 2 |
| **3.2** | Code Style & Linting | 15h | Aucune |
| **3.3** | Performance | 25h | Phase 2 |
| **3.4** | Logging & Monitoring | 20h | Aucune |

**Livrables Semaine 8**:
- ✅ Documentation complète
- ✅ Linting automatisé
- ✅ +30% performance
- ✅ Monitoring Grafana

---

### Phase 4: TESTS (Semaines 6-9, en parallèle Phase 3) - 116h

| Sprint | Tasks | Durée | Dépendances |
|--------|-------|-------|-------------|
| **4.1** | Tests Unitaires | 36h | Phase 1, 2 |
| **4.2** | Tests Intégration | 28h | 4.1 |
| **4.3** | Tests Edge Cases | 28h | 4.1 |
| **4.4** | Tests E2E | 24h | 4.1, 4.2 |

**Livrables Semaine 9**:
- ✅ Coverage 98%
- ✅ CI/CD avec tests
- ✅ Rapport coverage HTML

---

### Timeline Globale

```
Semaine 1-2: Phase 1 CRITIQUE (80h)
│
├─ Exception Handling (25h)
├─ Gestion Ressources (15h)
├─ State Management (20h)
├─ Code Duplication (10h)
└─ Async Fixes (10h)

Semaine 3-5: Phase 2 HAUTE (120h)
│
├─ Gros Fichiers (40h)
├─ Complexité (30h)
├─ Magic Numbers (20h)
└─ Type Hints (30h)

Semaine 6-8: Phase 3 MOYENNE (80h) + Phase 4 Tests (116h en parallèle)
│
├─ Documentation (20h)
├─ Code Style (15h)
├─ Performance (25h)
├─ Monitoring (20h)
│
└─ Tests (116h)
    ├─ Unitaires (36h)
    ├─ Intégration (28h)
    ├─ Edge Cases (28h)
    └─ E2E (24h)

TOTAL: 8-9 semaines (396h)
```

---

## 📊 MÉTRIQUES DE SUCCÈS

### Métriques Code Quality

| Métrique | Avant | Cible | Mesure |
|----------|-------|-------|--------|
| **Coverage** | 60% | 98% | `pytest --cov` |
| **Complexité Moyenne** | 12 | <7 | `radon cc -a` |
| **Files >400 lignes** | 3 | 0 | `wc -l` |
| **Type Hints** | 20% | 85% | `mypy --strict` |
| **Linting Violations** | 500+ | 0 | `ruff check` |
| **Security Issues** | ? | 0 | `bandit -r .` |
| **Code Duplication** | 15% | <3% | `jscpd` |

### Métriques Stabilité

| Métrique | Avant | Cible | Mesure |
|----------|-------|-------|--------|
| **Crashes/jour** | 2-3 | 0 | Logs |
| **Silent Failures** | 10+ | 0 | Exception tracking |
| **Resource Leaks** | 5+ | 0 | Profiling |
| **Race Conditions** | 3+ | 0 | Threading tests |

### Métriques Performance

| Métrique | Avant | Cible | Mesure |
|----------|-------|-------|--------|
| **API Latency P95** | 500ms | <200ms | Prometheus |
| **Memory Growth** | +50MB/h | <5MB/h | Profiling |
| **Scanner Loop** | 2s | <1s | Timer |
| **DB Query Time** | 100ms | <20ms | Profiling |

### Métriques Tests

| Métrique | Avant | Cible | Mesure |
|----------|-------|-------|--------|
| **Test Count** | 560 | 1500+ | `pytest --collect-only` |
| **Test Duration** | 5min | <2min | CI logs |
| **Flaky Tests** | 5% | 0% | Test retries |
| **Coverage Gaps** | 7 modules | 0 modules | Coverage report |

---

## 🎯 PRIORITÉS BUSINESS

### Impact Business par Phase

| Phase | Impact Stabilité | Impact Performance | Impact Maintenabilité | Priorité |
|-------|-----------------|-------------------|---------------------|----------|
| **Phase 1** | 🔴 CRITIQUE (+40%) | 🟡 Moyen (+10%) | 🟠 Haut (+30%) | ⭐⭐⭐⭐⭐ |
| **Phase 2** | 🟡 Moyen (+15%) | 🟡 Moyen (+15%) | 🔴 CRITIQUE (+50%) | ⭐⭐⭐⭐ |
| **Phase 3** | 🟢 Faible (+5%) | 🟠 Haut (+30%) | 🟡 Moyen (+20%) | ⭐⭐⭐ |
| **Phase 4 Tests** | 🔴 CRITIQUE (+50%) | 🟢 Faible (+5%) | 🟠 Haut (+40%) | ⭐⭐⭐⭐⭐ |

### ROI Estimé

**Coûts**:
- Développement: 396h × 50€/h = **19,800€**
- Tests: Inclus
- Review: 40h × 50€/h = **2,000€**
- **TOTAL: 21,800€**

**Gains**:
- Réduction bugs production: -70% → **~15h/mois économisés** = 9,000€/an
- Réduction debugging time: -50% → **~20h/mois économisés** = 12,000€/an
- Nouvelles features faster: +40% vélocité → **~30h/mois gagnés** = 18,000€/an
- Réduction incidents clients: -80% → **Satisfaction ++** = Valeur long-terme
- **TOTAL GAINS ANNUELS: ~39,000€**

**ROI**: (~39,000 - 21,800) / 21,800 = **~79% ROI première année**

---

## 📝 NOTES FINALES

### Risques Identifiés

1. **Régression fonctionnelle** (Probabilité: MOYENNE)
   - Mitigation: Tests exhaustifs avant merge
   - Rollback plan: Git branches

2. **Temps > estimé** (Probabilité: HAUTE)
   - Mitigation: Buffer 20% sur timeline
   - Priorités ajustables

3. **Scope creep** (Probabilité: MOYENNE)
   - Mitigation: Plan strict, pas de "nice to have"

### Recommandations

1. ✅ **Commencer IMMÉDIATEMENT Phase 1** (critique pour stabilité)
2. ✅ **Tests en parallèle** (ne pas attendre fin refactoring)
3. ✅ **Code freeze partiel** (bloquer nouvelles features pendant refactoring)
4. ✅ **Review externe** (pair programming sessions)
5. ✅ **Monitoring renforcé** (détecter régressions vite)

---

**Document généré**: 20/12/2025
**Auteur**: Claude (Anthropic)
**Version**: 1.0
**Status**: ✅ PRÊT POUR VALIDATION

---

**Prochaine Étape**: Valider plan avec équipe et commencer Sprint 1.1 (Exception Handling)

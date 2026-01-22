# 🚀 Sprint 1.1 - Exception Handling - Quick Start

> **Status**: ✅ Infrastructure 100% | 🔄 Refactorisation 13%
> **Last Update**: 20/12/2025
> **Commits**: 938ecd2, 4b6c5fa

---

## 📦 INFRASTRUCTURE COMPLÈTE

### Fichiers Créés
```
core/
├── exceptions.py       (750 lignes) - 25+ exceptions custom
└── error_handling.py   (750 lignes) - Décorateurs @handle_errors

tests/
└── test_error_handling.py (700 lignes) - 57 tests (100% ✅)

docs/
├── PLAN_REFACTORISATION_COVERAGE.md    - Plan complet 396h
├── SPRINT_1_1_PROGRESS.md               - Progression détaillée
├── MAIN_PY_REFACTORING_EXAMPLES.md      - 7 patterns
├── SESSION_SUMMARY_20_12_2025.md        - Résumé session
├── REFACTORING_CHECKLIST.md             - Checklist 38+ occurrences
└── SPRINT_1_1_README.md                 - Ce fichier
```

---

## ⚡ QUICK REFERENCE

### Import dans votre fichier
```python
from core.exceptions import (
    TradeCursorError,
    NetworkError, APIError, RateLimitError,
    DatabaseError, DatabaseConnectionError,
    PositionError, OrderExecutionError,
    ConfigurationError, ValidationError,
)
from core.error_handling import handle_errors, ErrorContext
```

### Pattern 1: Décorateur Simple
```python
@handle_errors(
    retry_on=(NetworkError, RateLimitError),
    max_retries=3,
    backoff_base=2.0
)
async def fetch_price(symbol: str) -> float:
    return await exchange.get_price(symbol)
```

### Pattern 2: Exceptions Spécifiques
```python
try:
    result = await risky_operation()
except NetworkError as e:
    logger.warning(f"Network error: {e}")
    return await retry_operation()
except ValidationError as e:
    logger.error(f"Validation: {e}")
    raise
except TradeCursorError as e:
    logger.error(f"App error: {e}", exc_info=True)
    await send_alert(e)
except Exception as e:
    logger.critical(f"CRITICAL: {type(e).__name__}: {e}", exc_info=True)
    raise
```

### Pattern 3: Context Manager
```python
async with ErrorContext(
    operation="Opening position",
    symbol=symbol,
    on_error=lambda e: send_alert(f"Failed: {e}")
):
    await open_position(symbol)
```

---

## 📊 PROGRESSION

### Fichiers à Refactoriser

| Fichier | Occurrences | Fait | Restant | Priorité |
|---------|-------------|------|---------|----------|
| **main.py** | 20+ | 5 | 15+ | 🔴 P1 |
| **api/mexc.py** | 5 | 0 | 5 | 🔴 P1 |
| **api/reliability.py** | 7 | 0 | 7 | 🔴 P1 |
| **core/analyzer.py** | 3 | 0 | 3 | 🟡 P2 |
| **core/scanner.py** | 3 | 0 | 3 | 🟡 P2 |
| **TOTAL** | **38+** | **5** | **33+** | - |

**Progression**: 13% (5/38+)

---

## 🎯 NEXT STEPS

### Immédiat
1. **main.py**: API endpoints (5+)
2. **main.py**: Background tasks (3)
3. **api/mexc.py**: Order execution (CRITIQUE)

### Cette Semaine
4. Terminer main.py
5. Terminer api/mexc.py
6. Commencer api/reliability.py

---

## 🧪 TESTER

```bash
# Tous les tests
pytest tests/test_error_handling.py -v

# Tests spécifiques
pytest tests/test_error_handling.py::TestExceptionHierarchy -v
pytest tests/test_error_handling.py::TestHandleErrorsDecorator -v

# Avec coverage
pytest tests/test_error_handling.py --cov=core.exceptions --cov=core.error_handling
```

**Résultat attendu**: ✅ 57 passed

---

## 📚 DOCUMENTATION

### Lire d'abord
1. [MAIN_PY_REFACTORING_EXAMPLES.md](MAIN_PY_REFACTORING_EXAMPLES.md) - Patterns avec exemples
2. [REFACTORING_CHECKLIST.md](REFACTORING_CHECKLIST.md) - Liste complète occurrences

### Référence
3. [PLAN_REFACTORISATION_COVERAGE.md](PLAN_REFACTORISATION_COVERAGE.md) - Plan global
4. [SPRINT_1_1_PROGRESS.md](SPRINT_1_1_PROGRESS.md) - Progression détaillée
5. [SESSION_SUMMARY_20_12_2025.md](SESSION_SUMMARY_20_12_2025.md) - Résumé complet

---

## 🔥 PROBLÈMES FRÉQUENTS

### Q: Les tests échouent
**R**: Vérifier les imports et que le fichier test_error_handling.py est bien à jour

### Q: ImportError pour exceptions
**R**: Ajouter les imports au début du fichier (voir Quick Reference)

### Q: Quel pattern utiliser?
**R**: Voir [MAIN_PY_REFACTORING_EXAMPLES.md](MAIN_PY_REFACTORING_EXAMPLES.md) section "Choisir le pattern"

### Q: Exception non reconnue
**R**: Vérifier core/exceptions.py - 25+ exceptions disponibles

---

## ✅ CHECKLIST RAPIDE

Avant de refactoriser:
- [ ] Lire contexte (20 lignes avant/après)
- [ ] Identifier type d'opération
- [ ] Choisir pattern approprié
- [ ] Consulter exemples si besoin

Pendant:
- [ ] Remplacer `except Exception`
- [ ] Ajouter commentaires
- [ ] Adapter logging
- [ ] Ajouter contexte

Après:
- [ ] Tester comportement normal
- [ ] Tester erreurs
- [ ] Vérifier logs
- [ ] Mettre à jour checklist

---

## 🎓 RESSOURCES

### Exceptions Disponibles (25+)
- **Network**: `NetworkError`, `RateLimitError`, `APIError`
- **Database**: `DatabaseError`, `DatabaseConnectionError`, `DatabaseCorruptionError`
- **Position**: `PositionError`, `PositionAlreadyExistsError`, `PositionNotFoundError`
- **Order**: `OrderExecutionError`, `OrderRejectedError`, `InsufficientBalanceError`
- **Config**: `ConfigurationError`, `ValidationError`
- **WebSocket**: `WebSocketError`, `WebSocketDisconnectedError`
- Voir [core/exceptions.py](../core/exceptions.py) pour la liste complète

### Décorateurs Disponibles
- `@handle_errors` - Retry + logging + callbacks
- `@log_errors` - Logging simple
- `@suppress_errors` - Fail-safe
- `@retry_on_network_error` - Retry réseau
- Voir [core/error_handling.py](../core/error_handling.py) pour détails

---

## 📞 AIDE

**Stuck?** Consulter:
1. Exemples dans MAIN_PY_REFACTORING_EXAMPLES.md
2. Tests dans test_error_handling.py (usage réel)
3. Checklist dans REFACTORING_CHECKLIST.md
4. Code dans core/exceptions.py et core/error_handling.py

---

**Ready to continue! 🚀**

"""
🔥 SPRINT 1.5: Code Duplication - Decorators Module

Décorateurs pour éliminer la duplication de code.

Patterns adressés:
- Pattern 5: Async Exception Wrapping (100+ functions)
- Pattern 1: Error Handling with DEBUG_ENABLED (52+ occurrences)
"""

from .async_decorators import async_safe, log_errors, suppress_errors

__all__ = [
    'async_safe',
    'log_errors',
    'suppress_errors',
]

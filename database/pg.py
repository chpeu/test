"""Lightweight PostgreSQL helper utilities."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

try:
    from psycopg2 import pool
    from psycopg2 import extras as pg_extras
except ImportError:  # pragma: no cover
    pool = None  # type: ignore
    pg_extras = None  # type: ignore

logger = logging.getLogger(__name__)

_DEFAULT_CONN_SETTINGS: Dict[str, Any] = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "trade_cursor_ml"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

_MIN_CONN = int(os.getenv("POSTGRES_POOL_MIN", "1"))
_MAX_CONN = int(os.getenv("POSTGRES_POOL_MAX", "5"))

_pg_pool: Optional[pool.SimpleConnectionPool] = None


def _ensure_pool() -> pool.SimpleConnectionPool:
    if pool is None:
        raise RuntimeError("psycopg2 n'est pas disponible - installez psycopg2-binary")

    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = pool.SimpleConnectionPool(
                _MIN_CONN,
                _MAX_CONN,
                **_DEFAULT_CONN_SETTINGS,
            )
            logger.info(
                "✅ Pool PostgreSQL initialisé (%s@%s:%s)",
                _DEFAULT_CONN_SETTINGS["dbname"],
                _DEFAULT_CONN_SETTINGS["host"],
                _DEFAULT_CONN_SETTINGS["port"],
            )
        except Exception as exc:  # pragma: no cover
            logger.error("❌ Impossible de créer le pool PostgreSQL: %s", exc)
            raise
    return _pg_pool


@contextmanager
def get_connection() -> Generator["psycopg2.extensions.connection", None, None]:
    """Obtenir une connexion depuis le pool."""
    pool_instance = _ensure_pool()
    conn = pool_instance.getconn()
    try:
        yield conn
    finally:
        pool_instance.putconn(conn)


@contextmanager
def get_cursor(*, dict_cursor: bool = False):
    """Fournir un curseur prêt à l'emploi avec gestion commit/rollback."""
    if pg_extras is None:
        raise RuntimeError("psycopg2 n'est pas disponible")

    with get_connection() as conn:
        cursor_factory = pg_extras.RealDictCursor if dict_cursor else None
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:  # pragma: no cover
            cursor.close()


def close_pool() -> None:
    """Fermer proprement le pool (utilisé au shutdown)."""
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.closeall()
        _pg_pool = None
        logger.info("✅ Pool PostgreSQL fermé")


__all__ = ["get_connection", "get_cursor", "close_pool"]

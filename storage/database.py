"""
storage/database.py — Unified database initializer and connection helper.

Supports:
  1. SQLite for local development, testing, and isolated environments.
  2. Production PostgreSQL via DATABASE_URL using SQLAlchemy engine/connection pooling.

Ensures:
  - Transparent parameterized query mapping (? to :p0, :p1, ... for SQLAlchemy).
  - Row access parity: row["key"], row[0], and dict(row) work identically across both backends.
  - Safe, idempotent schema migrations (table creation, column additions, indexes).
"""

import os
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import current_app, g

# Thread-local storage for connections outside Flask app context
_thread_local = threading.local()

# Global SQLAlchemy engine cache
_sa_engine = None


# ── DDL (Standard ANSI SQL compatible with both SQLite and PostgreSQL) ───────
_CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user',  -- 'user' | 'admin' | 'demo'
    created_at    TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    is_demo       INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_CASES_TABLE = """
CREATE TABLE IF NOT EXISTS cases (
    case_id     TEXT PRIMARY KEY,
    user_id     TEXT REFERENCES users(user_id),
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    is_demo     INTEGER NOT NULL DEFAULT 0,
    demo_type   TEXT DEFAULT NULL               -- 'legacy' | 'live' | NULL (normal)
);
"""

_CREATE_EVIDENCE_TABLE = """
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id     TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(case_id),
    filename        TEXT NOT NULL,
    original_name   TEXT NOT NULL,
    modality        TEXT NOT NULL,          -- 'image' | 'audio' | 'video'
    mime_type       TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    file_size       INTEGER NOT NULL,
    uploaded_at     TEXT NOT NULL,
    analysis_status TEXT NOT NULL DEFAULT 'pending',
    analysis_json   TEXT DEFAULT NULL       -- stores raw JSON results
);
"""

_CREATE_REPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS reports (
    report_id   TEXT PRIMARY KEY,
    case_id     TEXT NOT NULL REFERENCES cases(case_id),
    filename    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    file_size   INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_CHAT_TABLE = """
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id    TEXT PRIMARY KEY,
    case_id       TEXT NOT NULL REFERENCES cases(case_id),
    role          TEXT NOT NULL,          -- 'user' | 'assistant'
    content       TEXT NOT NULL,
    metadata_json TEXT DEFAULT NULL,     -- structured response / citations / limitations
    created_at    TEXT NOT NULL
);
"""

_TABLES = [
    _CREATE_USERS_TABLE,
    _CREATE_CASES_TABLE,
    _CREATE_EVIDENCE_TABLE,
    _CREATE_REPORTS_TABLE,
    _CREATE_CHAT_TABLE,
]


# ── Row & Cursor Adapters for SQLAlchemy Compatibility ────────────────────────

class RowAdapter:
    """Dictionary-like mapping row compatible with sqlite3.Row."""

    def __init__(self, mapping: Optional[Dict[str, Any]], raw_tuple: Optional[tuple] = None):
        self._mapping = dict(mapping) if mapping is not None else {}
        self._tuple = raw_tuple or tuple(self._mapping.values())

    def __getitem__(self, item: Union[str, int]) -> Any:
        if isinstance(item, int):
            return self._tuple[item]
        return self._mapping[item]

    def get(self, key: str, default: Any = None) -> Any:
        return self._mapping.get(key, default)

    def keys(self):
        return self._mapping.keys()

    def values(self):
        return self._mapping.values()

    def items(self):
        return self._mapping.items()

    def __iter__(self):
        return iter(self._mapping)

    def __len__(self) -> int:
        return len(self._mapping)

    def __repr__(self) -> str:
        return repr(self._mapping)


class CursorAdapter:
    """Cursor wrapper standardizing fetchone, fetchall, and rowcount."""

    def __init__(self, result: Any):
        self._result = result
        self.rowcount = getattr(result, "rowcount", -1)

    def fetchone(self) -> Optional[RowAdapter]:
        try:
            mapping_row = self._result.mappings().fetchone()
            if mapping_row is None:
                return None
            return RowAdapter(mapping_row)
        except Exception:
            return None

    def fetchall(self) -> List[RowAdapter]:
        try:
            rows = self._result.mappings().fetchall()
            return [RowAdapter(r) for r in rows]
        except Exception:
            return []


class ConnectionAdapter:
    """Connection wrapper that adapts '?' parameter placeholders to SQLAlchemy named parameters."""

    def __init__(self, sa_connection: Any):
        self._conn = sa_connection
        self._in_transaction = False

    def execute(self, sql: str, params: Optional[Union[tuple, list, dict]] = None) -> CursorAdapter:
        from sqlalchemy import text

        if params is None:
            res = self._conn.execute(text(sql))
            return CursorAdapter(res)

        if isinstance(params, (tuple, list)):
            param_list = list(params)
            param_dict = {}
            idx = 0

            def _repl(match):
                nonlocal idx
                key = f"p{idx}"
                param_dict[key] = param_list[idx]
                idx += 1
                return f":{key}"

            adapted_sql = re.sub(r"\?", _repl, sql)
            res = self._conn.execute(text(adapted_sql), param_dict)
            return CursorAdapter(res)

        if isinstance(params, dict):
            res = self._conn.execute(text(sql), params)
            return CursorAdapter(res)

        res = self._conn.execute(text(sql))
        return CursorAdapter(res)

    def commit(self) -> None:
        try:
            self._conn.commit()
        except Exception:
            pass

    def rollback(self) -> None:
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


# ── SQLite native connection ──────────────────────────────────────────────────

def _connect_sqlite(db_path: Union[str, Path]) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _get_engine(database_url: str):
    """Create or return cached SQLAlchemy engine."""
    global _sa_engine
    if _sa_engine is not None:
        return _sa_engine

    import sqlalchemy as sa

    norm_url = database_url.strip()
    if norm_url.startswith("postgres://"):
        norm_url = "postgresql://" + norm_url[len("postgres://"):]

    engine_args: Dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    _sa_engine = sa.create_engine(norm_url, **engine_args)
    return _sa_engine


def get_database_url() -> Optional[str]:
    """Retrieve production DATABASE_URL if configured."""
    url = os.getenv("DATABASE_URL")
    if url and url.strip():
        return url.strip()
    try:
        cfg_url = current_app.config.get("DATABASE_URL")
        if cfg_url and str(cfg_url).strip():
            return str(cfg_url).strip()
    except RuntimeError:
        pass
    return None


# ── Public Database API ───────────────────────────────────────────────────────

def init_db(db_path: Optional[Union[str, Path]] = None, database_url: Optional[str] = None) -> None:
    """Create all tables and run idempotent migrations across SQLite and PostgreSQL.

    Can be called both inside and outside a Flask application context.
    Safely migrates existing databases without dropping tables or losing records.
    """
    target_url = database_url or get_database_url()

    if target_url and not target_url.startswith("sqlite://"):
        # ── PostgreSQL / SQLAlchemy initialization ────────────────────────────
        engine = _get_engine(target_url)
        with engine.connect() as conn:
            adapter = ConnectionAdapter(conn)
            # Create core tables
            for ddl in _TABLES:
                adapter.execute(ddl)

            # Idempotent Column Additions
            for col_sql in (
                "ALTER TABLE cases ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES users(user_id);",
                "ALTER TABLE cases ADD COLUMN IF NOT EXISTS is_demo INTEGER NOT NULL DEFAULT 0;",
                "ALTER TABLE cases ADD COLUMN IF NOT EXISTS demo_type TEXT DEFAULT NULL;",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_demo INTEGER NOT NULL DEFAULT 0;",
            ):
                try:
                    adapter.execute(col_sql)
                except Exception:
                    pass

            # Classify legacy demo case if not yet set
            try:
                adapter.execute("UPDATE cases SET demo_type = 'legacy' WHERE case_id = 'case_demo_sentinel' OR (is_demo = 1 AND demo_type IS NULL);")
            except Exception:
                pass

            # Indexes for fast lookup and uniqueness integrity
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS idx_cases_user_id ON cases(user_id);",
                "CREATE INDEX IF NOT EXISTS idx_cases_is_demo ON cases(is_demo);",
                "CREATE INDEX IF NOT EXISTS idx_cases_demo_type ON cases(demo_type);",
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
                "CREATE INDEX IF NOT EXISTS idx_evidence_case_id ON evidence(case_id);",
            ):
                try:
                    adapter.execute(idx_sql)
                except Exception:
                    pass

            adapter.commit()
        return

    # ── SQLite initialization ─────────────────────────────────────────────────
    if db_path is None:
        try:
            db_path = current_app.config["DB_PATH"]
        except RuntimeError:
            raise ValueError(
                "init_db() requires either a db_path/database_url argument or an active "
                "Flask application context."
            )

    _thread_local.last_db_path = db_path
    conn = _connect_sqlite(db_path)
    try:
        for ddl in _TABLES:
            conn.execute(ddl)

        # Check existing columns on cases table
        cursor = conn.execute("PRAGMA table_info(cases);")
        columns = [row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cursor.fetchall()]
        if "user_id" not in columns:
            conn.execute("ALTER TABLE cases ADD COLUMN user_id TEXT REFERENCES users(user_id);")
        if "is_demo" not in columns:
            conn.execute("ALTER TABLE cases ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0;")
        if "demo_type" not in columns:
            conn.execute("ALTER TABLE cases ADD COLUMN demo_type TEXT DEFAULT NULL;")

        # Classify legacy demo case if not yet set
        conn.execute("UPDATE cases SET demo_type = 'legacy' WHERE case_id = 'case_demo_sentinel' OR (is_demo = 1 AND demo_type IS NULL);")

        # Check existing columns on users table
        cursor_u = conn.execute("PRAGMA table_info(users);")
        columns_u = [row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cursor_u.fetchall()]
        if "is_demo" not in columns_u:
            conn.execute("ALTER TABLE users ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0;")

        # Indexes for fast lookup
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_user_id ON cases(user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_is_demo ON cases(is_demo);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_demo_type ON cases(demo_type);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_case_id ON evidence(case_id);")

        conn.commit()
    finally:
        conn.close()


def get_db(db_path: Optional[Union[str, Path]] = None) -> Any:
    """Return a per-request database connection from Flask's ``g`` or thread-local fallback."""
    from flask import has_app_context

    target_url = get_database_url()
    if target_url and not target_url.startswith("sqlite://"):
        engine = _get_engine(target_url)
        if has_app_context():
            if "sa_conn" not in g:
                g.sa_conn = engine.connect()
                g.db = ConnectionAdapter(g.sa_conn)
            return g.db
        # Thread-local fallback for scripts/tests
        if not hasattr(_thread_local, "sa_adapter") or _thread_local.sa_adapter is None:
            sa_conn = engine.connect()
            _thread_local.sa_adapter = ConnectionAdapter(sa_conn)
        return _thread_local.sa_adapter

    # SQLite connection path
    if has_app_context():
        if "db" not in g:
            path = db_path or current_app.config["DB_PATH"]
            g.db = _connect_sqlite(path)
        return g.db

    # Outside active Flask app context (unit tests / CLI scripts)
    path = db_path or getattr(_thread_local, "last_db_path", None)
    if path is None:
        from config import get_config
        cfg = get_config()
        path = cfg.DB_PATH

    path_str = str(Path(path).resolve())
    current_path = getattr(_thread_local, "_current_path", None)
    if not hasattr(_thread_local, "conn") or _thread_local.conn is None or current_path != path_str:
        if hasattr(_thread_local, "conn") and _thread_local.conn is not None:
            try:
                _thread_local.conn.close()
            except Exception:
                pass
        _thread_local.conn = _connect_sqlite(path)
        _thread_local._current_path = path_str

    return _thread_local.conn


def close_db(exception: Optional[BaseException] = None) -> None:  # noqa: ARG001
    """Close per-request database connections (teardown_appcontext hook)."""
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass
    sa_conn = g.pop("sa_conn", None)
    if sa_conn is not None:
        try:
            sa_conn.close()
        except Exception:
            pass

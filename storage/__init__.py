"""
storage/__init__.py — Storage subsystem initializer.

Imports and re-exports the public API of the storage package so callers
can simply do:

    from storage import db, cases_store, evidence_store
"""

from .database import init_db, get_db
from .cases_store import (
    create_case,
    get_case,
    list_cases,
    update_case,
)
from .evidence_store import (
    save_evidence,
    get_evidence,
    list_evidence,
    update_analysis,
    delete_evidence,
)
from .reports_store import (
    create_report,
    get_report,
    list_reports,
)
from .chat_store import (
    save_message,
    list_messages,
    clear_messages,
)

__all__ = [
    "init_db",
    "get_db",
    "create_case",
    "get_case",
    "list_cases",
    "update_case",
    "save_evidence",
    "get_evidence",
    "list_evidence",
    "update_analysis",
    "delete_evidence",
    "create_report",
    "get_report",
    "list_reports",
    "save_message",
    "list_messages",
    "clear_messages",
]


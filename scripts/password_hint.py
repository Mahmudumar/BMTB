"""Safe, backwards-compatible persistence helpers for password hints.

Hints are reminders, not encryption keys. This module does not log hint values.
"""
from typing import Any


def normalize_password_hint(value: Any) -> str:
    """Return a usable hint string, or an empty string for absent/malformed data."""
    if not isinstance(value, str):
        return ""
    return value.strip()


def load_password_hint(db: Any, settings_manager: Any = None) -> str:
    """Load the SQLite hint first, falling back to the legacy QSettings value."""
    try:
        hint = normalize_password_hint(db.get_config("password_hint"))
        if hint:
            return hint
    except Exception:
        pass

    if settings_manager is not None:
        try:
            return normalize_password_hint(settings_manager.password_hint)
        except Exception:
            pass
    return ""


def save_password_hint(db: Any, settings_manager: Any, value: Any) -> bool:
    """Save a non-empty explicit hint to both supported stores.

    Empty input is treated as no change so an omitted hint cannot erase an
    existing one. Returns True if at least one store accepted the value.
    """
    hint = normalize_password_hint(value)
    if not hint:
        return False

    saved = False
    try:
        db.set_config("password_hint", hint)
        saved = True
    except Exception:
        pass

    if settings_manager is not None:
        try:
            settings_manager.password_hint = hint
            saved = True
        except Exception:
            pass

    return saved

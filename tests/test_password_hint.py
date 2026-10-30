"""Focused tests for password hint persistence; all stores are in-memory mocks."""
from scripts.password_hint import (
    load_password_hint,
    normalize_password_hint,
    save_password_hint,
)


class FakeDB:
    def __init__(self, value=""):
        self.values = {"password_hint": value}
        self.fail_read = False
        self.fail_write = False

    def get_config(self, key):
        if self.fail_read:
            raise RuntimeError("simulated unavailable database")
        return self.values.get(key, "")

    def set_config(self, key, value):
        if self.fail_write:
            raise RuntimeError("simulated unavailable database")
        self.values[key] = value


class FakeSettings:
    def __init__(self, hint=""):
        self.password_hint = hint


def test_saved_hint_is_written_to_database_and_loaded():
    db = FakeDB()
    settings = FakeSettings()

    assert save_password_hint(db, settings, "  My reminder  ") is True
    assert db.values["password_hint"] == "My reminder"
    assert settings.password_hint == "My reminder"
    assert load_password_hint(db, settings) == "My reminder"


def test_database_hint_takes_precedence_over_legacy_settings_value():
    db = FakeDB("Database reminder")
    settings = FakeSettings("Older settings reminder")

    assert load_password_hint(db, settings) == "Database reminder"


def test_missing_empty_or_malformed_hints_are_safe():
    assert normalize_password_hint(None) == ""
    assert normalize_password_hint(123) == ""
    assert normalize_password_hint("   ") == ""
    assert load_password_hint(FakeDB(None), FakeSettings(None)) == ""
    assert load_password_hint(FakeDB(""), FakeSettings("")) == ""


def test_unavailable_database_falls_back_to_settings():
    db = FakeDB()
    db.fail_read = True

    assert load_password_hint(db, FakeSettings("Legacy reminder")) == "Legacy reminder"
    assert load_password_hint(db, FakeSettings(None)) == ""


def test_empty_hint_does_not_overwrite_existing_hint():
    db = FakeDB("Existing reminder")
    settings = FakeSettings("Existing reminder")

    assert save_password_hint(db, settings, "   ") is False
    assert db.values["password_hint"] == "Existing reminder"
    assert settings.password_hint == "Existing reminder"


def test_database_write_failure_keeps_settings_fallback_available():
    db = FakeDB()
    db.fail_write = True
    settings = FakeSettings()

    assert save_password_hint(db, settings, "Fallback reminder") is True
    assert db.values["password_hint"] == ""
    assert load_password_hint(db, settings) == "Fallback reminder"

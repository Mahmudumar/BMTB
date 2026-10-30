"""QSettings-backed application preference tests."""
import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtCore import QSettings

from scripts import Settings
from scripts.premium_manager import PremiumTracker


def test_security_and_editor_settings_round_trip(tmp_path, qapp):
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    settings = Settings()

    settings.require_password = False
    settings.autolock_enabled = True
    settings.autolock_minutes = 10
    settings.warn_if_unprotected = False
    settings.editor_font_size = 16
    settings.password_hint = "A private clue"

    settings.sync()
    reloaded = Settings()
    assert reloaded.require_password is False
    assert reloaded.autolock_enabled is True
    assert reloaded.autolock_minutes == 10
    assert reloaded.warn_if_unprotected is False
    assert reloaded.editor_font_size == 16
    assert reloaded.password_hint == "A private clue"


def test_settings_defaults_are_available(tmp_path, qapp):
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    settings = Settings()
    assert settings.editor_font_size == 10
    assert settings.autolock_minutes == 5
    assert settings.number_of_opens == 0


def test_premium_tracker_values_round_trip(tmp_path, qapp):
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    tracker = PremiumTracker(db=None)
    tracker.note_count = 25
    tracker.reminders_given = 2
    tracker.license_key = "test-license"

    tracker.sync()
    reloaded = PremiumTracker(db=None)
    assert reloaded.note_count == 25
    assert reloaded.reminders_given == 2
    assert reloaded.license_key == "test-license"

"""SQLite persistence tests using only temporary databases."""
import pytest

from scripts.database_manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / "notes.sqlite3"))
    yield manager
    manager.close()


def test_database_creates_required_tables(db):
    names = {
        row["name"]
        for row in db.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"notes", "config"} <= names


def test_create_read_update_and_rename_note(db):
    note_id = db.create_note("First", "private text")
    assert db.get_note_content(note_id) == ("First", "private text")

    db.save_note_content(note_id, "Updated", "new body")
    assert db.get_note_content(note_id) == ("Updated", "new body")

    db.rename_note(note_id, "Renamed")
    assert db.get_note_content(note_id) == ("Renamed", "new body")


def test_notes_are_returned_newest_first(db):
    first = db.create_note("First", "1")
    second = db.create_note("Second", "2")
    assert [row["id"] for row in db.get_all_notes()] == [second, first]
    assert [row["id"] for row in db.get_all_notes_with_content()] == [second, first]


def test_missing_note_returns_empty_string(db):
    assert db.get_note_content(99999) == ""


def test_config_insert_update_and_missing_value(db):
    assert db.get_config("missing") == ""
    db.set_config("theme", "dark")
    db.set_config("theme", "light")
    assert db.get_config("theme") == "light"


def test_delete_and_clear_notes_preserve_config(db):
    first = db.create_note("First", "one")
    db.create_note("Second", "two")
    db.set_config("password_hash", "test-only-hash")

    db.delete_note(first)
    assert len(db.get_all_notes()) == 1

    db.clear_database_notes()
    assert db.get_all_notes() == []
    assert db.get_config("password_hash") == "test-only-hash"


def test_data_survives_connection_reopen(tmp_path):
    path = str(tmp_path / "persistent.sqlite3")
    first = DatabaseManager(path)
    note_id = first.create_note("Saved", "body")
    first.set_config("setting", "value")
    first.close()

    second = DatabaseManager(path)
    try:
        assert second.get_note_content(note_id) == ("Saved", "body")
        assert second.get_config("setting") == "value"
    finally:
        second.close()

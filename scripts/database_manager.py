
import sqlite3

# import markdown
from scripts.constants import NOTES_DB



class DatabaseManager:
    def __init__(self, db_name=f"{NOTES_DB}"):
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        # first check if the file is there
    
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                is_markdown INTEGER DEFAULT 1
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        self.conn.commit()

    # ------------------------
    # Configuration
    # ------------------------

    def get_config(self, key):
        self.cursor.execute(
            "SELECT value FROM config WHERE key=?",
            (key,)
        )

        row = self.cursor.fetchone()
        return str(row["value"]) if row else ""

    def set_config(self, key, value):
        self.cursor.execute("""
            INSERT INTO config(key, value)
            VALUES(?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value=excluded.value
        """, (key, value))

        self.conn.commit()

    # ------------------------
    # Notes
    # ------------------------

    def get_all_notes_with_content(self):
        self.cursor.execute("""
            SELECT id, title, content
            FROM notes
            ORDER BY id DESC
        """)

        return self.cursor.fetchall()
    
    def get_all_notes(self):
        self.cursor.execute("""
            SELECT id, title
            FROM notes
            ORDER BY id DESC
        """)

        return self.cursor.fetchall()

    def get_note_content(self, note_id):
        self.cursor.execute("""
            SELECT content, title
            FROM notes
            WHERE id=?
        """, (note_id,))

        row = self.cursor.fetchone()
        return (row["title"], row["content"]) if row else ""

    def create_note(self, title, content):
        self.cursor.execute("""
            INSERT INTO notes(title, content, is_markdown)
            VALUES(?, ?, 1)
        """, (title, content,))

        self.conn.commit()
        return self.cursor.lastrowid

    def save_note_content(self, note_id, title, content):
        self.cursor.execute("""
            UPDATE notes
            SET content=?, title=?
            WHERE id=?
        """, (content, title, note_id))

        self.conn.commit()

    def rename_note(self, note_id, new_title):
        self.cursor.execute("""
            UPDATE notes
            SET title=?
            WHERE id=?
        """, (new_title, note_id))

        self.conn.commit()

    def delete_note(self, note_id):
        self.cursor.execute("""
            DELETE FROM notes
            WHERE id=?
        """, (note_id,))

        self.conn.commit()

    def clear_database_notes(self):
        self.cursor.execute("DELETE FROM notes")
        self.conn.commit()

    # ------------------------
    # Cleanup
    # ------------------------

    def close(self):
        self.conn.close()
